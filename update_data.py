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
    try:
        d = fetch_csv("https://archives.nseindia.com/content/equities/EQUITY_L.csv")
        d.columns = [c.strip() for c in d.columns]
        d = d[d["SERIES"].astype(str).str.strip() == "EQ"]
        syms = [s.strip() for s in d["SYMBOL"]]
        print("NSE list", len(syms))
        return syms
    except Exception as e:
        print("NSE list fail, fallback to index lists:", e)
        allsyms = set()
        for s in members.values():
            allsyms |= s
        return sorted(allsyms)


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


def main():
    members = get_index_members()
    symbols = get_all_nse(members)
    tickers = [s + ".NS" for s in symbols]

    frames = []
    for i in range(0, len(tickers), 200):
        print("Downloading batch", i // 200 + 1, "of", len(tickers) // 200 + 1)
        try:
            frames.append(
                yf.download(tickers[i:i + 200], period="5y", group_by="ticker",
                            progress=False, threads=True, auto_adjust=False)
            )
        except Exception as e:
            print("Batch fail", e)
    raw = pd.concat(frames, axis=1)

    rows = []
    for sym in symbols:
        t = sym + ".NS"
        try:
            d = raw[t].dropna(subset=["Close"])
            if len(d) < 200:
                continue
            c, v = d["Close"], d["Volume"]
            avg20 = v.iloc[-21:-1].mean()
            high20 = float(d["High"].iloc[-20:].max())
            prev_high20 = float(d["High"].iloc[-21:-1].max())
            row = {
                "Stock": sym,
                "Price": round(float(c.iloc[-1]), 2),
                "Ret3M": float(c.iloc[-1] / c.iloc[-64] - 1) * 100,
                "Ret3M_1W": float(c.iloc[-6] / c.iloc[-69] - 1) * 100,
                "Ret3M_2W": float(c.iloc[-11] / c.iloc[-74] - 1) * 100,
                "Ret3M_1M": float(c.iloc[-22] / c.iloc[-85] - 1) * 100,
                "High20D": round(high20, 2),
                "DistBO": round((high20 / float(c.iloc[-1]) - 1) * 100, 2),
                "BreakLevel": round(prev_high20, 2),
                "Brk": int(float(c.iloc[-1]) > prev_high20),
                "VolRatio": float(v.iloc[-1] / avg20) if avg20 > 0 else np.nan,
                "Turnover(Cr)": float(c.iloc[-1] * v.tail(20).mean() / 1e7),
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
        except Exception:
            continue

    df = pd.DataFrame(rows)
    print("Stocks processed:", len(df))

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

    top = df.nlargest(1000, "Turnover(Cr)")["Stock"].tolist()

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
