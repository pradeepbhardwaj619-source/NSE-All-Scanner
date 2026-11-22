import io
import datetime
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests
import yfinance as yf

UA = {"User-Agent": "Mozilla/5.0"}
INDEX_URLS = {
    "Nifty 50": "https://www.niftyindices.com/IndexConstituent/ind_nifty50list.csv",
    "Nifty 100": "https://www.niftyindices.com/IndexConstituent/ind_nifty100list.csv",
    "Nifty 500": "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv",
    "Nifty Total Market": "https://www.niftyindices.com/IndexConstituent/ind_niftytotalmarket_list.csv",
}
EMA_PERIODS = {"D": [20, 50, 200], "W": [10, 20, 50], "M": [10, 20]}
MIN_CANDLES = 25
MCAP_TOP_N = 1500


def fetch_csv(url):
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text))


def get_index_members():
    out = {}
    for name, url in INDEX_URLS.items():
        try:
            d = fetch_csv(url)
            out[name] = set(d["Symbol"].astype(str).str.strip())
            print(name, len(out[name]))
        except Exception as e:
            print("Index list fail:", name, e)
            out[name] = set()
    return out


def get_all_nse(members):
    """Returns dict {symbol: series}. Saari series (EQ, BE, SM, ST...) shamil hain."""
    series_map = {}
    try:
        d = fetch_csv("https://archives.nseindia.com/content/equities/EQUITY_L.csv")
        d.columns = [c.strip() for c in d.columns]
        d["SYMBOL"] = d["SYMBOL"].astype(str).str.strip()
        d["SERIES"] = d["SERIES"].astype(str).str.strip()
        for sym, ser in zip(d["SYMBOL"], d["SERIES"]):
            series_map[sym] = ser
        print("NSE list rows:", len(series_map))
        print("Series counts:", d["SERIES"].value_counts().to_dict())
    except Exception as e:
        print("NSE list fail, fallback to index lists:", e)
    for mem in members.values():
        for sym in mem:
            series_map.setdefault(sym, "EQ")
    return series_map


def rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return float((100 - 100 / (1 + up / dn)).iloc[-1])


def resample_close(s, tf):
    if tf == "W":
        return s.resample("W-FRI").last().dropna()
    try:
        return s.resample("ME").last().dropna()
    except ValueError:
        return s.resample("M").last().dropna()


def fetch(tks):
    out = {}
    try:
        df = yf.download(tks, period="5y", group_by="ticker",
                         progress=False, threads=True, auto_adjust=False)
    except Exception as e:
        print("Batch fail", e)
        return out
    if df is None or df.empty:
        return out
    if isinstance(df.columns, pd.MultiIndex):
        avail = set(df.columns.get_level_values(0))
        for t in tks:
            if t in avail:
                sub = df[t].dropna(subset=["Close"])
                if len(sub) > 0:
                    out[t] = sub
    elif len(tks) == 1:
        sub = df.dropna(subset=["Close"])
        if len(sub) > 0:
            out[tks[0]] = sub
    return out


def main():
    members = get_index_members()
    series_map = get_all_nse(members)
    symbols = sorted(series_map.keys())
    tickers = [s + ".NS" for s in symbols]
    print("Total symbols to scan:", len(symbols))

    data = {}
    for i in range(0, len(tickers), 200):
        print("Downloading batch", i // 200 + 1, "of", len(tickers) // 200 + 1)
        data.update(fetch(tickers[i:i + 200]))

    missing = [t for t in tickers if t not in data]
    print("Missing after first pass:", len(missing), "- retrying")
    for i in range(0, len(missing), 50):
        data.update(fetch(missing[i:i + 50]))
    missing = [t for t in tickers if t not in data]
    print("No data from Yahoo:", len(missing))
    print("Sample:", missing[:40])

    rows = []
    short_hist = 0
    for sym in symbols:
        t = sym + ".NS"
        d = data.get(t)
        if d is None:
            continue
        try:
            if len(d) < MIN_CANDLES:
                short_hist += 1
                continue
            c, v = d["Close"], d["Volume"]
            price = float(c.iloc[-1])
            avg20 = v.iloc[-21:-1].mean()
            high20 = float(d["High"].iloc[-20:].max())
            prev_high20 = float(d["High"].iloc[-21:-1].max())
            low20 = float(d["Low"].iloc[-20:].min())
            lowser = d["Low"]
            nl_pos = np.flatnonzero((lowser < lowser.rolling(20).min().shift(1)).values)
            days_since_low = float(len(lowser) - 1 - nl_pos[-1]) if len(nl_pos) else np.nan

            def ret3m(k):
                n = 63
                if len(c) > n + k:
                    return float(c.iloc[-1 - k] / c.iloc[-1 - k - n] - 1) * 100
                return np.nan

            row = {
                "Stock": sym,
                "Series": series_map[sym],
                "Price": round(price, 2),
                "Ret3M": ret3m(0),
                "Ret3M_1W": ret3m(5),
                "Ret3M_2W": ret3m(10),
                "Ret3M_1M": ret3m(21),
                "High20D": round(high20, 2),
                "DistBO": round((high20 / price - 1) * 100, 2),
                "BreakLevel": round(prev_high20, 2),
                "Low20D": round(low20, 2),
                "DaysSinceLow": days_since_low,
                "SwingRisk": round((high20 - low20) / high20 * 100, 2),
                "Brk": int(price > prev_high20),
                "VolRatio": float(v.iloc[-1] / avg20) if avg20 > 0 else np.nan,
                "Turnover(Cr)": float(price * v.tail(20).mean() / 1e7),
            }
            series = {"D": c, "W": resample_close(c, "W"), "M": resample_close(c, "M")}
            for tf, s in series.items():
                row[f"RSI_{tf}"] = round(rsi(s), 1) if len(s) > 15 else np.nan
                for p in EMA_PERIODS[tf]:
                    if len(s) > p:
                        ema = s.ewm(span=p, adjust=False).mean().iloc[-1]
                        row[f"EMA{p}_{tf}"] = round((s.iloc[-1] / ema - 1) * 100, 2)
                    else:
                        row[f"EMA{p}_{tf}"] = np.nan
            rows.append(row)
        except Exception as e:
            print("Skip", sym, e)
            continue

    df = pd.DataFrame(rows)
    print("Stocks processed:", len(df), "| too little history (<", MIN_CANDLES, "candles):", short_hist)

    lags = {"": "Ret3M", "_1W": "Ret3M_1W", "_2W": "Ret3M_2W", "_1M": "Ret3M_1M"}
    universes = dict(members)
    universes["All NSE"] = set(df["Stock"])
    for name, mem in universes.items():
        mask = df["Stock"].isin(mem)
        for suffix, ret_col in lags.items():
            col = f"RS_{name}{suffix}"
            df[col] = np.nan
            if mask.sum() > 0:
                df.loc[mask, col] = (df.loc[mask, ret_col].rank(pct=True) * 98 + 1).round(0)

    top = df.nlargest(MCAP_TOP_N, "Turnover(Cr)")["Stock"].tolist()

    def mcap(sym):
        try:
            return sym, yf.Ticker(sym + ".NS").fast_info["marketCap"] / 1e7
        except Exception:
            return sym, np.nan

    with ThreadPoolExecutor(8) as ex:
        caps = dict(ex.map(mcap, top))
    df["MCap(Cr)"] = df["Stock"].map(caps)

    df.to_csv("data.csv", index=False)
    ist = datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)
    with open("updated.txt", "w") as fh:
        fh.write(ist.strftime("%d-%b-%Y %H:%M IST"))
    print("Done")


if __name__ == "__main__":
    main()
