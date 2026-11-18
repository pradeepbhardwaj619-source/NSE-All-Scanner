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

rs_col = f"RS_{uni}"
prev_col = f"RS_{uni}{CMP[cmp_label]}"
has_prev = prev_col in df.columns

f = df.copy()
f = f[f[rs_col] >= rs_min]
f = f.copy()

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

if vol_min > 0:
    f = f[f["VolRatio"] >= vol_min]

if mcap_min > 0 or mcap_max < 10_000_000:
    f = f[f["MCap(Cr)"].between(mcap_min, mcap_max)]

f = f[f["Price"].between(price_min, price_max)]
f = f.sort_values(rs_col, ascending=False).copy()

st.success(f"{len(f)} stocks mile (total {len(df)} scanned)")

cols = ["Stock", "Price"]
if "Brk" in f.columns:
    f["Setup"] = np.where(f["Brk"] == 1, "Breakout", np.where(f["DistBO"] <= bo_dist, "Near", "-"))
    cols += ["High20D", "DistBO", "BreakLevel", "Setup"]
cols += [rs_col]
if has_prev:
    cols += [prev_col, "RS Chg", "RS Trend"]
cols += ["MCap(Cr)", "VolRatio", "RSI_D", "RSI_W", "RSI_M"]
cols += [f"EMA{p}_{tf}" for tf, ps in EMA_PERIODS.items() for p in ps]

rename = {rs_col: "RS 3M", "VolRatio": "Vol x", "DistBO": "Dist to 20D High %", "BreakLevel": "Prev 20D High"}
if has_prev:
    rename[prev_col] = "RS Prev"
show = f[cols].rename(columns=rename)
show["Vol x"] = show["Vol x"].round(2)
show["MCap(Cr)"] = show["MCap(Cr)"].round(0)

st.dataframe(show, use_container_width=True, height=700, hide_index=True)
st.download_button("⬇️ CSV download", show.to_csv(index=False), "scan.csv")
st.caption(f"RS Prev = {cmp_label} ka RS rating. RS Chg = RS 3M minus RS Prev (jaise 60 se 80 = +20, Rising).")
st.caption("20D High = last 20 candles (aaj ki candle ke saath) ka sabse high, TradingView ke 20 period Donchian upper jaisa. Dist to 20D High % = price us high se kitna neeche hai (0 = high par).")
st.caption("Prev 20D High = aaj ko chhod ke pichle 20 din ka high (breakout level). Setup = Breakout jab price ne is level ko paar kiya, Near jab breakout nahi hua par 20D High ke paas hai.")
st.caption("EMA columns = price EMA se kitne % door hai (+ matlab EMA ke upar). Market cap sirf top 1000 liquid stocks ka hai.")
