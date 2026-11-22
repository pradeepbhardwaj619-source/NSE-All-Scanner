import io

import numpy as np
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Backtest", layout="wide")
st.title("🧪 Strategy Backtest")

UA = {"User-Agent": "Mozilla/5.0"}
INDEX_URLS = {
    "Nifty 50": "https://www.niftyindices.com/IndexConstituent/ind_nifty50list.csv",
    "Nifty 100": "https://www.niftyindices.com/IndexConstituent/ind_nifty100list.csv",
    "Nifty 500": "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv",
    "Nifty Total Market": "https://www.niftyindices.com/IndexConstituent/ind_niftytotalmarket_list.csv",
}


# ======================= ENGINE =======================
@st.cache_data(ttl=86400, show_spinner=False)
def get_symbols(universe):
    r = requests.get(INDEX_URLS[universe], headers=UA, timeout=60)
    r.raise_for_status()
    d = pd.read_csv(io.StringIO(r.text))
    return [s.strip() for s in d["Symbol"].astype(str)]


def _grab(tks):
    try:
        df = yf.download(tks, period="5y", progress=False, threads=True, auto_adjust=True)
    except Exception:
        return None
    if df is None or df.empty:
        return None
    if not isinstance(df.columns, pd.MultiIndex):
        df.columns = pd.MultiIndex.from_product([list(df.columns), [tks[0]]])
    return df


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def download(symbols):
    tickers = [s + ".NS" for s in symbols]
    parts = []
    for i in range(0, len(tickers), 100):
        df = _grab(tickers[i:i + 100])
        if df is not None:
            parts.append(df)
    got = set()
    for p in parts:
        cl = p["Close"]
        got |= set(cl.columns[cl.notna().any()])
    missing = [t for t in tickers if t not in got]
    for i in range(0, len(missing), 25):
        df = _grab(missing[i:i + 25])
        if df is not None:
            parts.append(df)
    if not parts:
        return None
    full = pd.concat(parts, axis=1)
    out = {}
    for k in ["Open", "High", "Low", "Close"]:
        x = full[k]
        x = x.T.groupby(level=0).first().T
        out[k] = x
    good = out["Close"].columns[out["Close"].notna().sum() > 300]
    for k in out:
        out[k] = out[k][good]
    cov = out["Close"].notna().mean(axis=1)
    keep = cov[cov > 0.5].index
    for k in out:
        out[k] = out[k].loc[keep].sort_index()
    return out


def prepare(data, rs_thr, n_window, use50, use200):
    O, H, L, C = data["Open"], data["High"], data["Low"], data["Close"]
    idx = C.index

    # RS 3M rating (universe ke andar), har hafte ke last din se agle hafte ke liye
    ret63 = C.pct_change(63)
    rs = ret63.rank(axis=1, pct=True) * 98 + 1
    rs_week = rs.resample("W-FRI").last().shift(1).reindex(idx, method="bfill")
    elig = (rs_week >= rs_thr).values
    rsv = rs_week.fillna(0).values

    # Trend filter (pichle din ke close ke hisaab se)
    ok = pd.DataFrame(True, index=idx, columns=C.columns)
    if use50:
        ok = ok & (C > C.rolling(50).mean())
    if use200:
        ok = ok & (C > C.rolling(200).mean())
    trend = ok.shift(1, fill_value=False).values

    # 20D low setup
    newlow = (L < L.rolling(20).min().shift(1)).values
    T, S = newlow.shape
    ar = np.arange(T)[:, None]
    last_low = np.maximum.accumulate(np.where(newlow, ar, -1), axis=0)
    ll_prev = np.vstack([np.full((1, S), -1), last_low[:-1]])
    if n_window is None:
        active = ll_prev >= 0
    else:
        active = (ll_prev >= 0) & ((ar - 1 - ll_prev) <= n_window)

    h20 = H.rolling(20).max().shift(1).values
    l20 = L.rolling(20).min().shift(1).values
    Ov, Hv, Lv, Cv = O.values, H.values, L.values, C.values
    base = (elig & trend & active & (Hv >= h20)
            & np.isfinite(h20) & np.isfinite(l20) & np.isfinite(Ov))
    return {
        "O": Ov, "H": Hv, "L": Lv, "C": Cv, "base": base, "h20": h20, "l20": l20,
        "ll_prev": ll_prev, "rsv": rsv, "syms": [str(s).replace(".NS", "") for s in C.columns],
        "dates": idx,
    }


def simulate(A, sl_mode, sl_pct, tgt_pct, max_pos, cost_pct, start_idx):
    O, H, L, C = A["O"], A["H"], A["L"], A["C"]
    base, h20, l20, ll_prev, rsv = A["base"], A["h20"], A["l20"], A["ll_prev"], A["rsv"]
    syms, dates = A["syms"], A["dates"]
    T, S = C.shape

    in_pos = np.zeros(S, bool)
    entry = np.full(S, np.nan)
    sl = np.full(S, np.nan)
    tgt = np.full(S, np.nan)
    ent_i = np.zeros(S, int)
    consumed = np.full(S, -1)
    alloc = 1.0 / max_pos
    cost = cost_pct / 100.0
    state = {"realized": 0.0}
    trades = []
    n = T - start_idx
    equity = np.ones(n)
    expo = np.zeros(n)

    def close_trade(s, d, px, result):
        net = px / entry[s] - 1 - cost
        state["realized"] += alloc * net
        trades.append({
            "Stock": syms[s],
            "Entry Date": dates[ent_i[s]],
            "Entry": round(entry[s], 2),
            "SL": round(sl[s], 2),
            "Target": round(tgt[s], 2) if np.isfinite(tgt[s]) else np.nan,
            "Exit Date": dates[d],
            "Exit": round(px, 2),
            "Result": result,
            "PnL %": round(net * 100, 2),
            "Risk %": round((entry[s] - sl[s]) / entry[s] * 100, 2),
            "Days": (dates[d] - dates[ent_i[s]]).days,
        })
        in_pos[s] = False

    for d in range(start_idx, T):
        o, h, l, c = O[d], H[d], L[d], C[d]

        if in_pos.any():
            sl_hit = in_pos & (l <= sl)
            tg_hit = in_pos & ~sl_hit & (h >= tgt)
            for s in np.flatnonzero(sl_hit):
                px = o[s] if o[s] <= sl[s] else sl[s]
                close_trade(s, d, px, "SL")
            for s in np.flatnonzero(tg_hit):
                px = o[s] if o[s] >= tgt[s] else tgt[s]
                close_trade(s, d, px, "Target")

        slots = max_pos - int(in_pos.sum())
        if slots > 0:
            cand = base[d] & ~in_pos & (ll_prev[d] > consumed)
            ids = np.flatnonzero(cand)
            if len(ids) > slots:
                ids = ids[np.argsort(-rsv[d][ids])[:slots]]
            for s in ids:
                trig = h20[d, s]
                ep = o[s] if o[s] >= trig else trig
                if sl_mode == "20D":
                    sl_s = l20[d, s]
                elif sl_mode == "Fixed":
                    sl_s = ep * (1 - sl_pct / 100.0)
                else:
                    sl_s = max(l20[d, s], ep * (1 - sl_pct / 100.0))
                if sl_s >= ep:
                    sl_s = ep * 0.9
                consumed[s] = ll_prev[d, s]
                entry[s] = ep
                sl[s] = sl_s
                tgt[s] = ep * (1 + tgt_pct / 100.0) if tgt_pct > 0 else np.inf
                ent_i[s] = d
                in_pos[s] = True
                if l[s] <= sl_s:
                    close_trade(s, d, sl_s, "SL")

        mtm = 0.0
        if in_pos.any():
            ii = np.flatnonzero(in_pos)
            cc = np.where(np.isnan(c[ii]), entry[ii], c[ii])
            mtm = alloc * float(np.sum(cc / entry[ii] - 1))
        equity[d - start_idx] = 1.0 + state["realized"] + mtm
        expo[d - start_idx] = in_pos.sum() / max_pos

    for s in np.flatnonzero(in_pos):
        last = C[:, s]
        last = last[~np.isnan(last)]
        px = last[-1] if len(last) else entry[s]
        trades.append({
            "Stock": syms[s],
            "Entry Date": dates[ent_i[s]],
            "Entry": round(entry[s], 2),
            "SL": round(sl[s], 2),
            "Target": round(tgt[s], 2) if np.isfinite(tgt[s]) else np.nan,
            "Exit Date": pd.NaT,
            "Exit": round(px, 2),
            "Result": "Open",
            "PnL %": round((px / entry[s] - 1) * 100, 2),
            "Risk %": round((entry[s] - sl[s]) / entry[s] * 100, 2),
            "Days": (dates[-1] - dates[ent_i[s]]).days,
        })

    tr = pd.DataFrame(trades)
    return tr, equity, expo


def metrics(tr, equity, expo, dates, start_idx):
    closed = tr[tr["Result"] != "Open"] if len(tr) else tr
    n = len(closed)
    out = {"Trades": n, "Open": int((tr["Result"] == "Open").sum()) if len(tr) else 0}
    if n > 0:
        wins = closed[closed["PnL %"] > 0]["PnL %"]
        loss = closed[closed["PnL %"] <= 0]["PnL %"]
        out["Win %"] = round(len(wins) / n * 100, 1)
        out["Avg Win %"] = round(wins.mean(), 2) if len(wins) else 0.0
        out["Avg Loss %"] = round(loss.mean(), 2) if len(loss) else 0.0
        out["Expectancy %"] = round(closed["PnL %"].mean(), 2)
        gl = -loss.sum()
        out["Profit Factor"] = round(wins.sum() / gl, 2) if gl > 0 else np.nan
        out["Avg Days"] = round(closed["Days"].mean(), 0)
    else:
        for k in ["Win %", "Avg Win %", "Avg Loss %", "Expectancy %", "Profit Factor", "Avg Days"]:
            out[k] = np.nan
    out["Return %"] = round((equity[-1] - 1) * 100, 1)
    yrs = max((dates[-1] - dates[start_idx]).days / 365.25, 0.1)
    out["CAGR %"] = round((equity[-1] ** (1 / yrs) - 1) * 100, 1) if equity[-1] > 0 else np.nan
    peak = np.maximum.accumulate(equity)
    out["Max DD %"] = round(float((equity / peak - 1).min() * 100), 1)
    out["Exposure %"] = round(float(expo.mean() * 100), 0)
    return out


def parse_nums(s):
    out = []
    for part in s.replace(" ", "").split(","):
        if part:
            try:
                out.append(float(part))
            except ValueError:
                pass
    return sorted(set(out))


# ======================= UI =======================
with st.expander("📜 Rules aur assumptions (ek baar padh lo)"):
    st.markdown(
        """
**Strategy ke rules**
- Universe: jo chuno (Nifty 500 etc). RS 3M rating us universe ke andar nikalti hai.
- **Har hafte** Friday close par RS banta hai, aur wahi list **agle poore hafte** ke liye eligible hoti hai.
- Price pichle din ke close par 50 DMA aur 200 DMA ke upar ho (checkbox se on/off).
- Stock ne pichle N din ke andar naya **20D low** banaya ho (N slider se, ya "koi limit nahi"). Tab GTT track hota hai. GTT **pichle 20 din ke high** par rehta hai, aur high roz update hota hai.
- Jis din high us level ko touch kare, usi level par buy. Agar gap-up khule, to **open price par** buy (asli fill jaisa).
- Ek 20D low par ek hi trade. Dobara trade ke liye naya 20D low chahiye.
- Stop loss: 20D low, ya entry se fixed %, ya dono me se jo paas ho (Smart). Target %: jo likhoge.
- Holding ka koi time limit nahi. Exit sirf SL ya Target par.
- Ek saath max trades tak. Jyada signals aaye to **sabse high RS** wale lete hain. Har trade ko capital ka barabar hissa milta hai.

**Honest assumptions (result ko zyada achha dikhne se bachane ke liye)**
- Ek hi din SL aur Target dono touch ho jayein to **SL pehle** maana jata hai.
- Entry wale din agar low SL ko touch kare, to usi din SL hit maana jata hai. Entry wale din Target nahi gina jata.
- Gap-down SL ke neeche khule to exit **open price** par hota hai, SL par nahi.
- Cost + slippage har trade se kata jata hai.
- Sirf **aaj ke index members** liye hain, to survivorship bias hai (jo stocks index se nikal gaye wo nahi hain). Asli result thoda kam ho sakta hai.
- Prices Yahoo se split/dividend adjusted hain.
"""
    )

c1, c2 = st.columns(2)
universe = c1.selectbox("Universe", ["Nifty 500", "Nifty Total Market", "Nifty 100", "Nifty 50"], index=0)
years = c2.selectbox("Backtest period", [1, 2, 3, 4], index=2, format_func=lambda x: f"Last {x} year")

c3, c4 = st.columns(2)
rs_thr = c3.slider("Weekly RS 3M (min)", 50, 99, 80)
n_window = c4.slider("20D low kitne din ke andar bana ho (max)", 3, 60, 10)
no_limit = st.checkbox("Koi limit nahi (pehle kabhi bhi 20D low bana ho)", False)

c5, c6 = st.columns(2)
use50 = c5.checkbox("Price > 50 DMA", True)
use200 = c6.checkbox("Price > 200 DMA", True)

c7, c8 = st.columns(2)
max_pos = int(c7.number_input("Ek saath max trades", 1, 50, 10))
cost_pct = float(c8.number_input("Cost + slippage per trade (%)", 0.0, 3.0, 0.2, 0.05))

st.subheader("Stop Loss options")
sl_modes = st.multiselect(
    "Kaunse SL compare karne hain",
    ["20D Low", "Fixed %", "Smart (20D Low, max risk %)"],
    default=["20D Low", "Fixed %"],
)
sl_text = st.text_input("SL % values (Fixed aur Smart ke liye, comma se alag)", "10,15")

st.subheader("Target options")
tgt_text = st.text_input("Target % values (0 likhoge to target nahi, sirf SL)", "6,8,10,15")

if st.button("▶️ Run Backtest", type="primary"):
    sl_vals = parse_nums(sl_text)
    tgt_vals = parse_nums(tgt_text)
    configs = []
    if "20D Low" in sl_modes:
        configs.append(("20D", 0.0, "20D Low"))
    for p in sl_vals:
        if "Fixed %" in sl_modes:
            configs.append(("Fixed", p, f"Fixed {p:g}%"))
        if "Smart (20D Low, max risk %)" in sl_modes:
            configs.append(("Smart", p, f"Smart {p:g}%"))
    if not configs or not tgt_vals:
        st.error("Kam se kam ek SL option aur ek target value daalo.")
        st.stop()
    if len(configs) * len(tgt_vals) > 40:
        st.error("Ek baar me 40 se zyada combinations nahi. SL ya target kam karo.")
        st.stop()

    with st.spinner("Data download ho raha hai (pehli baar 1-3 min, phir cache me rehta hai)..."):
        try:
            symbols = get_symbols(universe)
            data = download(tuple(symbols))
        except Exception as e:
            st.error(f"Data nahi aaya: {e}")
            st.stop()
    if data is None or data["Close"].shape[1] < 5:
        st.error("Yahoo se data nahi aaya. Thodi der baad dobara try karo.")
        st.stop()

    A = prepare(data, rs_thr, None if no_limit else n_window, use50, use200)
    dates = A["dates"]
    start_idx = int(dates.searchsorted(dates[-1] - pd.DateOffset(years=years)))
    start_idx = max(start_idx, 200)

    rows, details = [], {}
    prog = st.progress(0.0)
    total = len(configs) * len(tgt_vals)
    k = 0
    for mode, p, sl_label in configs:
        for t in tgt_vals:
            tr, eq, ex = simulate(A, mode, p, t, max_pos, cost_pct, start_idx)
            m = metrics(tr, eq, ex, dates, start_idx)
            tl = "No target" if t <= 0 else f"{t:g}%"
            row = {"SL": sl_label, "Target": tl}
            row.update(m)
            rows.append(row)
            label = f"SL {sl_label} | Target {tl}"
            details[label] = (tr, pd.Series((eq - 1) * 100, index=dates[start_idx:]))
            k += 1
            prog.progress(k / total)
    prog.empty()

    table = pd.DataFrame(rows).sort_values("Return %", ascending=False).reset_index(drop=True)
    st.session_state["bt"] = {
        "table": table,
        "details": details,
        "meta": f"{universe} | {len(A['syms'])} stocks | {dates[start_idx].date()} se {dates[-1].date()} | RS >= {rs_thr} | max {max_pos} trades",
    }

bt = st.session_state.get("bt")
if bt:
    st.divider()
    st.success(bt["meta"])
    st.subheader("📊 Comparison (Return % ke hisaab se sorted)")
    st.dataframe(bt["table"], use_container_width=True, hide_index=True)
    st.caption(
        "Return % = poore capital par net return. Win %, Expectancy aur Profit Factor sirf band hue trades ke hain. "
        "Open = abhi tak khule trades (unka profit/loss Return % me shamil hai)."
    )

    st.subheader("🔍 Kisi ek combination ki detail")
    pick = st.selectbox("Combination chuno", list(bt["details"].keys()))
    tr, eq = bt["details"][pick]
    st.write("**Portfolio return % (time ke saath)**")
    st.line_chart(eq)
    if len(tr):
        show = tr.copy()
        show["Entry Date"] = pd.to_datetime(show["Entry Date"]).dt.strftime("%Y-%m-%d")
        show["Exit Date"] = pd.to_datetime(show["Exit Date"]).dt.strftime("%Y-%m-%d")
        show = show.sort_values("Entry Date", ascending=False)
        st.write(f"**Trade log ({len(show)} trades)**")
        st.dataframe(show, use_container_width=True, hide_index=True, height=500)
        st.download_button("⬇️ Trade log CSV", show.to_csv(index=False), "trades.csv")
    else:
        st.info("Is combination me koi trade nahi bana.")
