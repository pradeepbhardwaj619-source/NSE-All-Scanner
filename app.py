import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import io
import time

st.set_page_config(page_title="My Private MarketSmith", layout="wide")

# --- STATIC NSE SECTOR MAPPING ---
NSE_SECTORS = {
    "TCS": "Technology", "INFY": "Technology", "HCLTECH": "Technology", "WIPRO": "Technology", 
    "HDFCBANK": "Financials", "ICICIBANK": "Financials", "SBIN": "Financials", "KOTAKBANK": "Financials",
    "SUNPHARMA": "Healthcare", "CIPLA": "Healthcare", "DIVISLAB": "Healthcare", "DRREDDY": "Healthcare",
    "TATAMOTORS": "Auto", "M&M": "Auto", "MARUTI": "Auto", "BAJAJ-AUTO": "Auto",
    "RELIANCE": "Energy", "ONGC": "Energy", "NTPC": "Energy", "POWERGRID": "Energy",
    "LT": "Capital Goods", "HAL": "Capital Goods", "BEL": "Capital Goods", "BHEL": "Capital Goods",
    "HUL": "Consumer", "ITC": "Consumer", "NESTLEIND": "Consumer", "BRITANNIA": "Consumer",
    "TATASTEEL": "Materials", "JSWSTEEL": "Materials", "HINDALCO": "Materials", "VEDL": "Materials",
    "DLF": "Realty", "MACROTECH": "Realty", "GODREJPROP": "Realty", "OBEROIRLTY": "Realty",
    "BHARTIARTL": "Telecom", "IDEA": "Telecom", "SUNTV": "Media", "ZEEL": "Media"
}

def get_sector_offline(ticker):
    clean_ticker = ticker.replace(".NS", "")
    return NSE_SECTORS.get(clean_ticker, "Other / Emerging")

# --- RSI CALCULATION FUNCTION ---
def calculate_rsi(data, periods=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=periods).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=periods).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

@st.cache_data(ttl=3600) # Caches data for 1 hour so filters run instantly
def fetch_and_prepare_data():
    url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(url, headers=headers)
    df = pd.read_csv(io.StringIO(res.text))
    tickers = [str(sym).strip() + ".NS" for sym in df['SYMBOL'].tolist() if sym.strip() not in ['NIFTY', 'BANKNIFTY']]
    
    chunk_size = 500
    data_frames = []
    
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i:i + chunk_size]
        df_chunk = yf.download(chunk, period="2y", group_by="ticker", progress=False, threads=True)
        data_frames.append(df_chunk)
        
    full_data = pd.concat(data_frames, axis=1)
    
    if isinstance(full_data.columns, pd.MultiIndex):
        closes = full_data.xs('Close', level=1, axis=1)
        volumes = full_data.xs('Volume', level=1, axis=1)
    else:
        return pd.DataFrame()
        
    valid_tickers = closes.notna().sum()[closes.notna().sum() >= 200].index
    closes = closes[valid_tickers]
    volumes = volumes[valid_tickers]
    
    # Base Calculations (Vectorized for speed)
    cmp = closes.iloc[-1]
    turnover_cr = (volumes.tail(20).mean() * cmp) / 10000000
    
    ret_3m = (cmp / closes.iloc[-63]) - 1
    rs_rating = ret_3m.rank(pct=True) * 100
    
    dma_20 = closes.rolling(20).mean().iloc[-1]
    dma_50 = closes.rolling(50).mean().iloc[-1]
    dma_200 = closes.rolling(200).mean().iloc[-1]
    
    rsi_daily = calculate_rsi(closes).iloc[-1]
    rsi_weekly = calculate_rsi(closes.resample('W-FRI').last()).iloc[-1]
    rsi_monthly = calculate_rsi(closes.resample('M').last()).iloc[-1]
    
    vol_20_avg = volumes.tail(20).mean()
    vol_today = volumes.iloc[-1]
    vol_spike = vol_today > (1.5 * vol_20_avg)
    
    master_df = pd.DataFrame({
        'CMP (₹)': cmp,
        'Turnover (Cr)': turnover_cr,
        '3M RS Rating': rs_rating,
        '20 DMA': dma_20,
        '50 DMA': dma_50,
        '200 DMA': dma_200,
        'Daily RSI': rsi_daily,
        'Weekly RSI': rsi_weekly,
        'Monthly RSI': rsi_monthly,
        'High Volume': vol_spike
    })
    master_df['Stock'] = [t.replace(".NS", "") for t in master_df.index]
    master_df['Sector'] = [get_sector_offline(t) for t in master_df.index]
    
    return master_df.dropna()

# ==========================================
# 🎛️ SIDEBAR CONTROL PANEL
# ==========================================
st.sidebar.title("🎛️ Control Panel")
st.sidebar.markdown("Turn on the filters you want to use.")

# 1. Turnover / Size Filter (Replacement for Market Cap)
use_size = st.sidebar.checkbox("🟢 Size / Liquidity Filter", value=True)
if use_size:
    min_turnover = st.sidebar.slider("Min Daily Turnover (in Crores)", 1, 500, 10, help="10 Cr turnover approx = 1000+ Cr Market Cap")

# 2. RS Filter
use_rs = st.sidebar.checkbox("🟢 3M Relative Strength (RS)", value=True)
if use_rs:
    min_rs = st.sidebar.slider("Min RS Rating", 10, 99, 80)

# 3. RSI Filter (Multi-Timeframe)
use_rsi = st.sidebar.checkbox("🟢 RSI Filter")
if use_rsi:
    rsi_tf = st.sidebar.selectbox("RSI Timeframe", ["Daily RSI", "Weekly RSI", "Monthly RSI"])
    rsi_cond = st.sidebar.radio("Condition", ["Greater Than (>)", "Less Than (<)"])
    rsi_val = st.sidebar.slider("RSI Value", 10, 90, 60)

# 4. Moving Average (DMA) Filter
use_dma = st.sidebar.checkbox("🟢 Moving Average Filter")
if use_dma:
    dma_tf = st.sidebar.selectbox("Select DMA", ["20 DMA", "50 DMA", "200 DMA"])
    dma_cond = st.sidebar.radio("Price is:", ["Above DMA", "Below DMA"])

# 5. Volume Filter
use_vol = st.sidebar.checkbox("🟢 High Volume Spike")

# 6. Sector Filter
use_sector = st.sidebar.checkbox("🟢 Sector Filter")
if use_sector:
    all_sectors = sorted(list(set(NSE_SECTORS.values())) + ["Other / Emerging"])
    selected_sectors = st.sidebar.multiselect("Select Sectors", all_sectors, default=all_sectors[:3])

st.sidebar.divider()
if st.sidebar.button("🔄 Force Refresh Market Data"):
    st.cache_data.clear()
    st.rerun()

# ==========================================
# 📊 MAIN APP LOGIC
# ==========================================
st.title("🦅 My Private Market Scanner")

with st.spinner("Loading base market data... (Takes ~1 min only for the first time)"):
    df = fetch_and_prepare_data()

if df.empty:
    st.error("Failed to fetch data. Please try again.")
    st.stop()

# APPLYING ACTIVE FILTERS MODULARLY
filtered_df = df.copy()

if use_size:
    filtered_df = filtered_df[filtered_df['Turnover (Cr)'] >= min_turnover]

if use_rs:
    filtered_df = filtered_df[filtered_df['3M RS Rating'] >= min_rs]

if use_rsi:
    if rsi_cond == "Greater Than (>)":
        filtered_df = filtered_df[filtered_df[rsi_tf] >= rsi_val]
    else:
        filtered_df = filtered_df[filtered_df[rsi_tf] <= rsi_val]

if use_dma:
    if dma_cond == "Above DMA":
        filtered_df = filtered_df[filtered_df['CMP (₹)'] > filtered_df[dma_tf]]
    else:
        filtered_df = filtered_df[filtered_df['CMP (₹)'] < filtered_df[dma_tf]]

if use_vol:
    filtered_df = filtered_df[filtered_df['High Volume'] == True]

if use_sector:
    filtered_df = filtered_df[filtered_df['Sector'].isin(selected_sectors)]

# Formatting the final output
filtered_df = filtered_df[['Stock', 'Sector', 'CMP (₹)', 'Turnover (Cr)', '3M RS Rating', 'Daily RSI', 'Weekly RSI', 'Monthly RSI', '20 DMA', '50 DMA', '200 DMA', 'High Volume']]

for col in ['CMP (₹)', 'Turnover (Cr)', '3M RS Rating', 'Daily RSI', 'Weekly RSI', 'Monthly RSI', '20 DMA', '50 DMA', '200 DMA']:
    filtered_df[col] = filtered_df[col].round(2)

filtered_df = filtered_df.sort_values(by='3M RS Rating', ascending=False).reset_index(drop=True)

st.success(f"🎯 Found **{len(filtered_df)}** stocks matching your custom criteria.")

st.dataframe(
    filtered_df.style.map(lambda x: 'color: #00CC96; font-weight:bold' if x else '', subset=['High Volume']),
    use_container_width=True,
    height=600
)
