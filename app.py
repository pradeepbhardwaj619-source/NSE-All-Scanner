import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="My Stock Scanner", layout="wide")
st.title("📊 My Stock Scanner")

EMA_PERIODS = {"D": [20, 50, 200], "W": [10, 20, 50], "M": [10, 20]}
UNIVERSES = ["Nifty 50", "Nifty 100", "Nifty 500", "Nifty Total Market", "All NSE"]
CMP = {"1 Week ago": "_1W", "2 Weeks ago": "_2W", "1 Month ago": "_1M"}


@st.cache_data(ttl=300)
def load():
    data = pd.read_csv("data.csv")
    try:
        with open("updated.txt") as fh:
            upd = fh.read().strip()
    except Exception:
        upd = "unknown"
    return data, upd


@st.cache_data(ttl=3600)
def load_sector_map():
    m = pd.read_csv("sector_map.csv")
    m["Symbol"] = m["Symbol"].astype(str).str.strip()
    m["Index"] = m["Index"].astype(str).str.strip()
    if "Group" not in m.columns:
        m["Group"] = m["Index"]
    if "Core" not in m.columns:
        m["Core"] = 1
    return m


def primary_sector(smap):
    """Har stock ka 'sahi' sector: core sector index pehle, phir sabse chhota (specific) index."""
    t = smap.copy()
    t["Size"] = t["Index"].map(t.groupby("Index")["Symbol"].nunique())
    t = t.sort_values(["Core", "Size", "Index"], ascending=[False, True, True]).drop_duplicates("Symbol")
    return t.set_index("Symbol")["Group"].to_dict(), t.set_index("Symbol")["Index"].to_dict()


def sector_table(data, smap, bench, method, min_n):
    """Har index ka 3M return (constituents se), benchmark se muqabla."""
    agg = (lambda s: s.mean()) if method.startswith("Equal") else (lambda s: s.median())
    has_lag = "Ret3M_1W" in data.columns
    bmask = data[f"RS_{bench}"].notna()
    b0 = agg(data.loc[bmask, "Ret3M"].dropna())
    b1 = agg(data.loc[bmask, "Ret3M_1W"].dropna()) if has_lag else np.nan
    rows, skipped = [], []
    for name, g in smap.groupby("Index"):
        syms = set(g["Symbol"])
        m = data[data["Stock"].isin(syms)]
        v = m["Ret3M"].dropna()
        if len(v) < min_n:
            skipped.append(f"{name} ({len(v)})")
            continue
        r0 = agg(v)
        ex = r0 - b0
        chg = np.nan
        if has_lag:
            chg = ex - (agg(m["Ret3M_1W"].dropna()) - b1)
        rows.append({
            "Index": name,
            "Stocks": f"{len(v)}/{len(syms)}",
            "Ret 3M %": round(r0, 1),
            "Bench 3M %": round(b0, 1),
            "Excess pp": round(ex, 1),
            "Excess chg vs 1W": round(chg, 1) if np.isfinite(chg) else np.nan,
            "Stocks beating %": round((v > b0).mean() * 100, 0),
        })
    out = pd.DataFrame(rows)
    if len(out):
        out = out.sort_values("Excess pp", ascending=False).reset_index(drop=True)
    return out, skipped


TOP_OPTS = {"Top 1": 1, "Top 2": 2, "Top 3": 3, "Top 4": 4, "Top 5": 5, "Top 7": 7,
            "Top 10": 10, "Sab (jo beat kar rahe)": 999}

try:
    df, updated = load()
except FileNotFoundError:
    st.error("data.csv nahi mila. GitHub > Actions > 'Update Data' > Run workflow chalao.")
    st.stop()

st.caption(f"Data last updated: {updated}")

sb = st.sidebar
sb.header("Filters")

uni = sb.selectbox("RS Universe", UNIVERSES, index=3)
rs_min = sb.slider("3M RS Rating (min)", 1, 99, 80)

sb.subheader("🏭 Sector RS (3M)")
sec_on = sb.checkbox("Sector RS filter on", True)
sec_bench = sb.selectbox("Sector ko kisse beat karna hai",
                         ["Nifty 500", "Nifty Total Market", "Nifty 100", "Nifty 50"], index=0)
sec_method = sb.selectbox("Index ka return kaise nikale", ["Equal-weight average", "Median"])
sec_top_lbl = sb.selectbox("Kitne top sectors se stocks lene hain", list(TOP_OPTS.keys()), index=2)
sec_min_n = sb.slider("Index me kam se kam valid stocks", 3, 15, 5)

sb.subheader("RS Trend (Rising / Declining)")
cmp_label = sb.selectbox("Compare RS with", list(CMP.keys()))
rs_trend = sb.selectbox("RS Trend filter", ["All", "Rising", "Declining"])
rs_thr = sb.slider("Rising / Declining = RS change of at least (points)", 1, 30, 5)

sb.subheader("RSI")
rsi_d = sb.slider("RSI Daily", 0, 100, (0, 100))
rsi_w = sb.slider("RSI Weekly", 0, 100, (0, 100))
rsi_m = sb.slider("RSI Monthly", 0, 100, (0, 100))

sb.subheader("Price above EMA")
ema_sel = {}
for tf, name in [("D", "Daily"), ("W", "Weekly"), ("M", "Monthly")]:
    ema_sel[tf] = sb.multiselect(f"{name} EMA", EMA_PERIODS[tf], default=[])

sb.subheader("20 Day High Breakout")
bo_mode = sb.selectbox(
    "Setup",
    ["All", "Breakout + Near", "Only Breakout", "Only Near"],
)
bo_dist = sb.slider("Near = max distance to 20D high (%)", 1, 20, 5)
low_on = sb.checkbox("Pehle 20D low bana ho (look back)", False)
low_days = sb.slider("20D low kitne din ke andar bana (max)", 1, 60, 10)

sb.subheader("Volume")
vol_min = sb.number_input("Volume / 20D avg (min x)", 0.0, 50.0, 0.0, 0.1)

sb.subheader("Market Cap (Cr)")
mc1, mc2 = sb.columns(2)
mcap_min = mc1.number_input("Min", 0, 10_000_000, 0, 500)
mcap_max = mc2.number_input("Max", 0, 10_000_000, 10_000_000, 500)

sb.subheader("Price (₹)")
p1, p2 = sb.columns(2)
price_min = p1.number_input("Min ", 0, 1_000_000, 0, 50)
price_max = p2.number_input("Max ", 0, 1_000_000, 1_000_000, 50)

sb.subheader("Liquidity")
turn_min = sb.number_input("Min avg turnover (Cr/day)", 0.0, 100000.0, 0.0, 0.5)

series_sel = []
if "Series" in df.columns:
    sb.subheader("NSE Series")
    series_all = sorted(df["Series"].dropna().unique().tolist())
    series_sel = sb.multiselect(
        "EQ = normal, BE = trade-to-trade, SM/ST = SME",
        series_all,
        default=series_all,
    )

rs_col = f"RS_{uni}"
prev_col = f"RS_{uni}{CMP[cmp_label]}"
has_prev = prev_col in df.columns

sec_tbl, sec_skipped, sel_names, sect_of, best_rank, smap = None, [], [], None, None, None
sector_of, prim_index = {}, {}
try:
    smap = load_sector_map()
    sector_of, prim_index = primary_sector(smap)
except FileNotFoundError:
    if sec_on:
        st.warning("sector_map.csv repo me nahi mili. Use upload karo. Tab tak sector filter band hai.")
    sec_on = False
if sec_on:
    sec_tbl, sec_skipped = sector_table(df, smap, sec_bench, sec_method, sec_min_n)
    beating = sec_tbl[sec_tbl["Excess pp"] > 0] if len(sec_tbl) else sec_tbl
    sel_names = beating.head(TOP_OPTS[sec_top_lbl])["Index"].tolist() if len(beating) else []
    rank_of = {n: i + 1 for i, n in enumerate(sel_names)}
    ssel = smap[smap["Index"].isin(sel_names)].copy()
    ssel["rank"] = ssel["Index"].map(rank_of)
    ssel = ssel.sort_values("rank")
    sect_of = ssel.groupby("Symbol")["Index"].apply(lambda s: " | ".join(s))
    best_rank = ssel.groupby("Symbol")["rank"].min()

f = df.copy()
if rs_min > 1:
    f = f[f[rs_col] >= rs_min]
f = f.copy()

if sec_on:
    f = f[f["Stock"].isin(sect_of.index)].copy()
    f["Beating Indices"] = f["Stock"].map(sect_of)
    f["Index Rank"] = f["Stock"].map(best_rank)

if has_prev:
    f["RS Chg"] = (f[rs_col] - f[prev_col]).round(0)
    f["RS Trend"] = np.where(
        f["RS Chg"].isna(), "-",
        np.where(f["RS Chg"] >= rs_thr, "📈 Rising",
                 np.where(f["RS Chg"] <= -rs_thr, "📉 Declining", "➡️ Flat")),
    )
    if rs_trend == "Rising":
        f = f[f["RS Chg"] >= rs_thr]
    elif rs_trend == "Declining":
        f = f[f["RS Chg"] <= -rs_thr]
elif rs_trend != "All":
    st.warning("RS trend data abhi nahi bana. GitHub Actions me Update Data dobara run karo.")

if rsi_d != (0, 100):
    f = f[f["RSI_D"].between(*rsi_d)]
if rsi_w != (0, 100):
    f = f[f["RSI_W"].between(*rsi_w)]
if rsi_m != (0, 100):
    f = f[f["RSI_M"].between(*rsi_m)]

for tf, periods in ema_sel.items():
    for p in periods:
        f = f[f[f"EMA{p}_{tf}"] > 0]

if "Brk" in f.columns:
    is_brk = f["Brk"] == 1
    is_near = (~is_brk) & (f["DistBO"] <= bo_dist)
    if bo_mode == "Only Breakout":
        f = f[is_brk]
    elif bo_mode == "Only Near":
        f = f[is_near]
    elif bo_mode == "Breakout + Near":
        f = f[is_brk | is_near]
elif bo_mode != "All":
    st.warning("Breakout data abhi nahi bana. GitHub Actions me Update Data dobara run karo.")

if low_on:
    if "DaysSinceLow" in f.columns:
        f = f[f["DaysSinceLow"] <= low_days]
    else:
        st.warning("20D low data abhi nahi bana. GitHub Actions me Update Data dobara run karo.")

if vol_min > 0:
    f = f[f["VolRatio"] >= vol_min]

if mcap_min > 0 or mcap_max < 10_000_000:
    f = f[f["MCap(Cr)"].between(mcap_min, mcap_max)]

if turn_min > 0:
    f = f[f["Turnover(Cr)"] >= turn_min]

if series_sel:
    f = f[f["Series"].isin(series_sel)]

f = f[f["Price"].between(price_min, price_max)]
f = f.sort_values(rs_col, ascending=False).copy()

if sec_on:
    n_beat = int((sec_tbl["Excess pp"] > 0).sum()) if len(sec_tbl) else 0
    if n_beat == 0:
        st.warning(f"Abhi koi bhi index {sec_bench} ko 3M me beat nahi kar raha, isliye sector filter se koi stock nahi aayega.")
    else:
        st.info(f"🏭 {len(sec_tbl)} indices me se {n_beat} {sec_bench} ko beat kar rahe hain. "
                f"Top {len(sel_names)} select hue: " + ", ".join(sel_names))
    with st.expander("Sector RS table (3M)"):
        if len(sec_tbl):
            t_ = sec_tbl.copy()
            beat_rank = {n: i + 1 for i, n in enumerate(sec_tbl.loc[sec_tbl["Excess pp"] > 0, "Index"])}
            t_.insert(0, "Rank", t_["Index"].map(beat_rank).fillna("-"))
            t_["Selected"] = t_["Index"].apply(lambda n: "✅" if n in sel_names else "")
            st.dataframe(t_, use_container_width=True, hide_index=True)
        if sec_skipped:
            st.caption("Valid stocks kam hone se chhoote indices: " + ", ".join(sec_skipped))
        matched = int(smap["Symbol"].isin(df["Stock"]).sum())
        st.caption(
            f"Excess pp = index ka 3M return minus {sec_bench} ka 3M return (percentage points). "
            f"Index return us index ke stocks ke 3M return se banta hai ({sec_method}). "
            f"Sector CSV ke {len(smap)} entries me se {matched} scanner data me mile. "
            "Jo stock kisi bhi chune hue index me nahi hai (jaise Bank, IT, Pharma ke stocks, agar unka index CSV nahi diya), wo is filter me nahi aayega."
        )

st.success(f"{len(f)} stocks mile (total {len(df)} scanned)")

if len(f):
    f_sec = f.assign(Sector=f["Stock"].map(sector_of).fillna("Unmapped"))
    g = f_sec.groupby("Sector").agg(
        Stocks=("Stock", "count"),
        AvgRS=(rs_col, "mean"),
        Avg3M=("Ret3M", "mean"),
        Top=("Stock", lambda s: ", ".join(list(s)[:6])),
    )
    g["Share %"] = (g["Stocks"] / len(f_sec) * 100).round(0)
    g = g.sort_values(["Stocks", "AvgRS"], ascending=[False, False])
    core_groups = set(smap.loc[smap["Core"] == 1, "Group"]) if smap is not None else set()
    known = g[g.index.isin(core_groups)]
    n_other = int(g.loc[~g.index.isin(core_groups), "Stocks"].sum())
    if len(known):
        top3 = [f"{i} ({int(r.Stocks)})" for i, r in known.head(3).iterrows()]
        lead = known.iloc[0]
        st.info(f"🔝 Is list me sabse zyada stocks **{known.index[0]}** sector se hain: "
                f"{int(lead['Stocks'])} / {len(f_sec)} ({int(lead['Share %'])}%). "
                f"Top 3: " + ", ".join(top3))
        if len(f_sec) < 10:
            st.caption("List chhoti hai (10 se kam stocks), isliye sector ka trend pakka nahi maanna.")
    if n_other:
        st.caption(f"{n_other} stocks ka asli sector pata nahi (sirf thematic index jaise Recent IPOs, Rural, MNC me hain, "
                   "ya sector_map me nahi hain). Inhe upar ke sector ranking me nahi gina.")
    with st.expander("📊 Sector-wise breakdown (is list ka)", expanded=True):
        st.bar_chart(g["Stocks"])
        bt = g.reset_index()[["Sector", "Stocks", "Share %", "AvgRS", "Avg3M", "Top"]].rename(
            columns={"AvgRS": "Avg RS", "Avg3M": "Avg 3M %", "Top": "Top stocks (RS ke order me)"})
        bt["Avg RS"] = bt["Avg RS"].round(0)
        bt["Avg 3M %"] = bt["Avg 3M %"].round(1)
        st.dataframe(bt, use_container_width=True, hide_index=True)
        st.caption("Har stock ka ek hi 'primary' sector ginta hai: pehle core sector index (jaise Pharma, IT, Banks), "
                   "nahi mila to sabse chhota thematic index. Isliye Reliance jaise multi-index stocks double nahi gine jate.")

f["Sector"] = f["Stock"].map(sector_of).fillna("Unmapped")
cols = ["Stock", "Sector"] + (["Beating Indices", "Index Rank"] if sec_on else []) + (["Series"] if "Series" in f.columns else []) + ["Price"]
if "Brk" in f.columns:
    f["Setup"] = np.where(f["Brk"] == 1, "Breakout", np.where(f["DistBO"] <= bo_dist, "Near", "-"))
    cols += ["High20D", "DistBO", "BreakLevel", "Setup"]
for extra in ["DaysSinceLow", "Low20D", "SwingRisk"]:
    if extra in f.columns:
        cols.append(extra)
cols += [rs_col]
if has_prev:
    cols += [prev_col, "RS Chg", "RS Trend"]
cols += ["MCap(Cr)", "Turnover(Cr)", "VolRatio", "RSI_D", "RSI_W", "RSI_M"]
cols += [f"EMA{p}_{tf}" for tf, ps in EMA_PERIODS.items() for p in ps]

rename = {rs_col: "RS 3M", "VolRatio": "Vol x", "DistBO": "Dist to 20D High %", "BreakLevel": "Prev 20D High",
          "DaysSinceLow": "Days since 20D Low", "Low20D": "20D Low (SL)", "SwingRisk": "Risk to 20D Low %"}
if has_prev:
    rename[prev_col] = "RS Prev"
show = f[cols].rename(columns=rename)
show["Vol x"] = show["Vol x"].round(2)
show["MCap(Cr)"] = show["MCap(Cr)"].round(0)
show["Turnover(Cr)"] = show["Turnover(Cr)"].round(2)

st.dataframe(show, use_container_width=True, height=700, hide_index=True)
st.download_button("⬇️ CSV download", show.to_csv(index=False), "scan.csv")
st.caption(f"RS Prev = {cmp_label} ka RS rating. RS Chg = RS 3M minus RS Prev (jaise 60 se 80 = +20, Rising).")
st.caption("20D High = last 20 candles (aaj ki candle ke saath) ka sabse high, TradingView ke 20 period Donchian upper jaisa. Dist to 20D High % = price us high se kitna neeche hai (0 = high par).")
st.caption("Days since 20D Low = pichli baar kitne din pehle stock ne naya 20D low banaya (0 = aaj). 20D Low (SL) = last 20 din ka sabse low. Risk to 20D Low % = 20D High par entry aur 20D Low par SL ka gap.")
st.caption("Prev 20D High = aaj ko chhod ke pichle 20 din ka high (breakout level). Setup = Breakout jab price ne is level ko paar kiya, Near jab breakout nahi hua par 20D High ke paas hai.")
st.caption("EMA columns = price EMA se kitne % door hai (+ matlab EMA ke upar). Market cap sirf top 1500 liquid stocks ka hai. Nayi listing (3 mahine se kam) ka RS nahi banta.")


with st.expander("🔎 Kisi stock ke saare indices dekho"):
    q = st.text_input("Stock symbol (jaise RELIANCE)", "").strip().upper()
    if q and smap is not None:
        r_ = smap[smap["Symbol"] == q]
        if r_.empty:
            st.write("Ye stock sector_map me nahi mila.")
        else:
            st.write(f"**Primary sector:** {sector_of.get(q, '-')} (index: {prim_index.get(q, '-')})")
            st.write("**Saare indices:** " + ", ".join(sorted(r_["Index"])))
