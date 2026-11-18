import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="My Stock Scanner", layout="wide")
st.title("📊 My Stock Scanner")

EMA_PERIODS = {"D": [20, 50, 200], "W": [10, 20, 50], "M": [10, 20]}
UNIVERSES = ["Nifty 50", "Nifty 100", "Nifty 500", "Nifty Total Market", "All NSE"]


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

sb.subheader("RSI")
rsi_d = sb.slider("RSI Daily", 0, 100, (0, 100))
rsi_w = sb.slider("RSI Weekly", 0, 100, (0, 100))
rsi_m = sb.slider("RSI Monthly", 0, 100, (0, 100))

sb.subheader("Price above EMA")
ema_sel = {}
for tf, name in [("D", "Daily"), ("W", "Weekly"), ("M", "Monthly")]:
    ema_sel[tf] = sb.multiselect(f"{name} EMA", EMA_PERIODS[tf], default=[])

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
f = df.copy()
f = f[f[rs_col] >= rs_min]

if rsi_d != (0, 100):
    f = f[f["RSI_D"].between(*rsi_d)]
if rsi_w != (0, 100):
    f = f[f["RSI_W"].between(*rsi_w)]
if rsi_m != (0, 100):
    f = f[f["RSI_M"].between(*rsi_m)]

for tf, periods in ema_sel.items():
    for p in periods:
        f = f[f[f"EMA{p}_{tf}"] > 0]

if vol_min > 0:
    f = f[f["VolRatio"] >= vol_min]

if mcap_min > 0 or mcap_max < 10_000_000:
    f = f[f["MCap(Cr)"].between(mcap_min, mcap_max)]

f = f[f["Price"].between(price_min, price_max)]
f = f.sort_values(rs_col, ascending=False)

st.success(f"{len(f)} stocks mile (total {len(df)} scanned)")

cols = ["Stock", "Price", "MCap(Cr)", rs_col, "RSI_D", "RSI_W", "RSI_M", "VolRatio"]
cols += [f"EMA{p}_{tf}" for tf, ps in EMA_PERIODS.items() for p in ps]
show = f[cols].rename(columns={rs_col: "RS 3M", "VolRatio": "Vol x"})
show["Vol x"] = show["Vol x"].round(2)
show["MCap(Cr)"] = show["MCap(Cr)"].round(0)

st.dataframe(show, use_container_width=True, height=700, hide_index=True)
st.download_button("⬇️ CSV download", show.to_csv(index=False), "scan.csv")
st.caption("EMA columns = price EMA se kitne % door hai (+ matlab EMA ke upar). Market cap sirf top 1000 liquid stocks ka hai.")
