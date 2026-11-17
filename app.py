import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import io
import time

st.set_page_config(page_title="Super RS Scanner", layout="wide")
st.title("🦅 Super RS Scanner: Top 750 Liquid Universe")
st.markdown("**(Top 750 Liquidity -> 200-DMA & 10Cr -> 3M RS >= 80 -> Sniper Entry & 20M High Check)**")

# --- STATIC NSE SECTOR MAPPING (100% BLOCK-PROOF) ---
NSE_SECTORS = {
    # IT & Tech
    "TCS": "Technology", "INFY": "Technology", "HCLTECH": "Technology", "WIPRO": "Technology", 
    "LTIM": "Technology", "TECHM": "Technology", "PERSISTENT": "Technology", "COFORGE": "Technology",
    "CYIENT": "Technology", "KPITTECH": "Technology", "TATAELXSI": "Technology", "MPHASIS": "Technology",
    "OLECTRA": "Technology", "TANLA": "Technology", "OFSS": "Technology", "ZENTEC": "Technology",
    
    # Financials & Banks
    "HDFCBANK": "Financials", "ICICIBANK": "Financials", "SBIN": "Financials", "KOTAKBANK": "Financials",
    "AXISBANK": "Financials", "INDUSINDBK": "Financials", "BAJFINANCE": "Financials", "BAJAJFINSV": "Financials",
    "CHOLAFIN": "Financials", "MUTHOOTFIN": "Financials", "RECLTD": "Financials", "PFC": "Financials",
    "IREDA": "Financials", "JIOFIN": "Financials", "SOUTHBANK": "Financials", "DHANBANK": "Financials",
    "MOTILALOFS": "Financials", "ANGELONE": "Financials", "BSE": "Financials", "MCX": "Financials",
    "LICHSGFIN": "Financials", "PNB": "Financials", "KTKBANK": "Financials",
    
    # Healthcare & Pharma
    "SUNPHARMA": "Healthcare", "CIPLA": "Healthcare", "DIVISLAB": "Healthcare", "DRREDDY": "Healthcare",
    "APOLLOHOSP": "Healthcare", "MAXHEALTH": "Healthcare", "LUPIN": "Healthcare", "AUROPHARMA": "Healthcare",
    "BIOCON": "Healthcare", "GLENMARK": "Healthcare", "SYNGENE": "Healthcare", "LAURUSLABS": "Healthcare",
    "NATCOPHARM": "Healthcare", "GRANULES": "Healthcare", "ALEMBICLTD": "Healthcare", "GLAND": "Healthcare",
    
    # Auto & Ancillaries
    "TATAMOTORS": "Auto", "M&M": "Auto", "MARUTI": "Auto", "BAJAJ-AUTO": "Auto", "EICHERMOT": "Auto",
    "HEROMOTOCO": "Auto", "TVSMOTOR": "Auto", "ASHOKLEY": "Auto", "BOSCHLTD": "Auto", "MRF": "Auto",
    "BALKRISIND": "Auto", "SONACOMS": "Auto", "MOTHERSON": "Auto", "SSWL": "Auto", "ALICON": "Auto",
    "KROSS": "Auto", "MENONBE": "Auto",
    
    # Energy & Power
    "RELIANCE": "Energy", "ONGC": "Energy", "NTPC": "Energy", "POWERGRID": "Energy", "TATAPOWER": "Energy",
    "ADANIGREEN": "Energy", "ADANIPOWER": "Energy", "COALINDIA": "Energy", "IOC": "Energy", "BPCL": "Energy",
    "GAIL": "Energy", "HINDOILEXP": "Energy", "SUZLON": "Energy", "NHPC": "Energy", "SJVN": "Energy",
    
    # Capital Goods, Defense & Infrastructure
    "LT": "Capital Goods", "HAL": "Capital Goods", "BEL": "Capital Goods", "BHEL": "Capital Goods",
    "SIEMENS": "Capital Goods", "ABB": "Capital Goods", "CUMMINSIND": "Capital Goods", "CGPOWER": "Capital Goods",
    "BDL": "Capital Goods", "MAZDOCK": "Capital Goods", "COCHINSHIP": "Capital Goods", "GRSE": "Capital Goods",
    "TITAGARH": "Capital Goods", "RVNL": "Capital Goods", "IRFC": "Capital Goods", "IRCON": "Capital Goods",
    "ENGINERSIN": "Capital Goods",
    
    # Consumer & Retail
    "HUL": "Consumer", "ITC": "Consumer", "NESTLEIND": "Consumer", "BRITANNIA": "Consumer", "TATACONSUM": "Consumer",
    "TITAN": "Consumer", "ASIANPAINT": "Consumer", "PIDILITIND": "Consumer", "TRENT": "Consumer",
    "ZOMATO": "Consumer", "DMART": "Consumer", "NYKAA": "Consumer", "RAYMOND": "Consumer", "STYLEBAAZA": "Consumer",
    "PARAGMILK": "Consumer",
    
    # Basic Materials, Metals & Chemicals
    "TATASTEEL": "Materials", "JSWSTEEL": "Materials", "HINDALCO": "Materials", "COALINDIA": "Materials",
    "VEDL": "Materials", "SRF": "Materials", "PIIND": "Materials", "TATACHEM": "Materials", "DEEPAKNTR": "Materials",
    "AARTIIND": "Materials", "CHEMPLASTS": "Materials", "SHYAMMETL": "Materials",
    
    # Realty & Hospitality
    "DLF": "Realty", "MACROTECH": "Realty", "GODREJPROP": "Realty", "OBEROIRLTY": "Realty", "PRESTIGE": "Realty",
    "INDHOTEL": "Realty", "CHALET": "Realty", "LEMONTREE": "Realty", "THELEELA": "Realty", "ORIENTHOT": "Realty",
    
    # Media & Telecom
    "BHARTIARTL": "Telecom", "IDEA": "Telecom", "INDUSTOWER": "Telecom", "SUNTV": "Media", "ZEEL": "Media",
    "PVRINOX": "Media", "SAREGAMA": "Media", "TIPSMUSIC": "Media"
}

def get_sector_offline(ticker):
    clean_ticker = ticker.replace(".NS", "")
    return NSE_SECTORS.get(clean_ticker, "Other / Emerging")

@st.cache_data(ttl=86400)
def get_all_nse():
    url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(url, headers=headers)
    df = pd.read_csv(io.StringIO(res.text))
    if ' SERIES' in df.columns:
        df = df[df[' SERIES'].str.strip() == 'EQ']
    elif 'SERIES' in df.columns:
        df = df[df['SERIES'].str.strip() == 'EQ']
    return [str(sym).strip() + ".NS" for sym in df['SYMBOL'].tolist()]

if st.button("🚀 Start Super Scan (~1 Min)"):
    status = st.empty()
    progress = st.progress(0)
    
    status.text("Step 1/5: Fetching NSE Equities...")
    try:
        tickers = get_all_nse()
    except Exception as e:
        st.error(f"List Fetch Error: {e}")
        st.stop()
    
    status.text(f"Step 2/5: Downloading 2 Years Data for {len(tickers)} Stocks...")
    progress.progress(0.1)
    
    chunk_size = 500
    data_frames = []
    total_batches = (len(tickers) // chunk_size) + 1
    
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i:i + chunk_size]
        status.text(f"Step 2/5: Downloading Data... Batch {i//chunk_size + 1}/{total_batches}")
        df_chunk = yf.download(chunk, period="2y", group_by="ticker", progress=False, threads=True)
        data_frames.append(df_chunk)
        progress.progress(0.1 + (0.3 * (i / len(tickers))))
    
    full_data = pd.concat(data_frames, axis=1)
    
    try:
        if isinstance(full_data.columns, pd.MultiIndex):
            closes = full_data.xs('Close', level=1, axis=1)
            volumes = full_data.xs('Volume', level=1, axis=1)
            highs = full_data.xs('High', level=1, axis=1)
            lows = full_data.xs('Low', level=1, axis=1)
        else:
            st.error("Data structure error from Yahoo Finance.")
            st.stop()
    except Exception as e:
        st.error(f"Extraction Error: {e}")
        st.stop()
        
    status.text("Step 3/5: Filtering Top 750 by Liquidity (Anti-Operator Game)...")
    progress.progress(0.5)
    
    valid_counts = closes.notna().sum()
    valid_tickers = valid_counts[valid_counts >= 200].index
    
    closes = closes[valid_tickers]
    volumes = volumes[valid_tickers]
    highs = highs[valid_tickers]
    lows = lows[valid_tickers]
    
    avg_vol_20 = volumes.tail(20).mean()
    cmp = closes.iloc[-1]
    avg_turnover = cmp * avg_vol_20
    
    top_750_tickers = avg_turnover.nlargest(750).index.tolist()
    
    closes = closes[top_750_tickers]
    volumes = volumes[top_750_tickers]
    highs = highs[top_750_tickers]
    lows = lows[top_750_tickers]
    avg_turnover = avg_turnover[top_750_tickers]
    
    status.text("Step 4/5: Calculating True RS Rating & Momentum on Top 750...")
    progress.progress(0.7)
    
    sma_200 = closes.rolling(window=200).mean().iloc[-1]
    valid_base = (closes.iloc[-1] > sma_200) & (avg_turnover >= 100000000)
    final_tickers = valid_base[valid_base].index.tolist()
    
    closes = closes[final_tickers]
    highs = highs[final_tickers]
    lows = lows[final_tickers]
    volumes = volumes[final_tickers]
    
    ret_3m_current = (closes.iloc[-1] / closes.iloc[-63]) - 1
    rs_current = ret_3m_current.rank(pct=True) * 100
    
    ret_3m_prev = (closes.iloc[-6] / closes.iloc[-68]) - 1
    rs_prev = ret_3m_prev.rank(pct=True) * 100
    
    top_rs_tickers = rs_current[rs_current >= 80].index.tolist()
    
    status.text("Step 5/5: Finding Sniper Entries, 20M Highs & Lightning Fast Sectors...")
    progress.progress(0.85)
    
    results = []
    for t in top_rs_tickers:
        c_close = closes[t]
        c_high = highs[t]
        c_vol = volumes[t]
        
        cmp_val = c_close.iloc[-1]
        c_rs = rs_current[t]
        p_rs = rs_prev[t]
        
        if c_rs > p_rs + 2:
            rs_mom = "📈 Rising"
        elif c_rs < p_rs - 2:
            rs_mom = "📉 Cooling"
        else:
            rs_mom = "⚖️ Stable"
            
        sma20 = c_close.rolling(20).mean().iloc[-1]
        sma50 = c_close.rolling(50).mean().iloc[-1]
        
        dist_20 = ((cmp_val - sma20) / sma20) * 100
        dist_50 = ((cmp_val - sma50) / sma50) * 100
        
        prev_20d_high = c_high.iloc[-21:-1].max()
        dist_to_breakout = ((prev_20d_high - cmp_val) / cmp_val) * 100
        
        high_20m = c_high.tail(420).max()
        dist_to_20m_high = ((high_20m - cmp_val) / cmp_val) * 100
        
        super_setup = ""
        if dist_to_20m_high <= 5.0:  
            super_setup = "⭐ A+ 20M High"
            
        if cmp_val >= prev_20d_high:
            setup = "🔥 20D Breakout"
            dist_to_breakout = 0.0
        elif 0 < dist_to_breakout <= 7.0:
            setup = "⚠️ Near Breakout"
        elif -2 <= dist_20 <= 4 or -2 <= dist_50 <= 4:
            setup = "🟢 Pullback Setup"
        else:
            setup = "⏳ Consolidating"
            
        vol_20_avg = c_vol.iloc[-21:-1].mean()
        if c_vol.iloc[-1] > (1.5 * vol_20_avg):
            vol_alert = "🚀 High Vol"
        else:
            vol_alert = "-"
            
        suggested_target = cmp_val * 1.08
        suggested_sl = cmp_val * 0.85
        
        # --- INSTANT SECTOR FETCH (No API Calls!) ---
        sector_name = get_sector_offline(t)
            
        results.append({
            "Stock": t.replace(".NS", ""),
            "Sector": sector_name,
            "CMP (₹)": round(cmp_val, 2),
            "3M RS Rating": round(c_rs, 1),
            "Super Setup": super_setup, 
            "Entry Setup": setup,
            "Dist. to BO (%)": round(dist_to_breakout, 2),
            "Dist. to 20M High (%)": round(dist_to_20m_high, 2), 
            "Volume Alert": vol_alert,
            "Target (8%)": round(suggested_target, 2),
            "Max SL (-15%)": round(suggested_sl, 2)
        })

    progress.progress(0.95)
    
    if results:
        df_results = pd.DataFrame(results)
        
        df_results['Setup_Score'] = df_results['Entry Setup'].map({"🔥 20D Breakout": 1, "⚠️ Near Breakout": 2, "🟢 Pullback Setup": 3, "⏳ Consolidating": 4})
        df_results['Super_Score'] = df_results['Super Setup'].map({"⭐ A+ 20M High": 1, "": 2})
        df_results = df_results.sort_values(by=["Super_Score", "Setup_Score", "3M RS Rating"], ascending=[True, True, False]).drop(columns=['Setup_Score', 'Super_Score']).reset_index(drop=True)
        
        progress.progress(1.0)
        status.empty()
        
        st.success(f"✅ Scan Complete! Found {len(df_results)} Institutional Grade Momentum Leaders.")
        
        st.subheader("🧩 Sector Sentiment (Money Flow)")
        
        sector_counts = df_results['Sector'].value_counts()
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.write("**Stocks per Sector:**")
            for sector, count in sector_counts.items():
                st.write(f"- **{sector}**: {count} stocks")
                
        with col2:
            st.write("**🔥 Actionable & ⭐ Super Setups by Sector:**")
            action_stocks = df_results[(df_results['Entry Setup'].isin(['🔥 20D Breakout', '⚠️ Near Breakout'])) | (df_results['Super Setup'] == '⭐ A+ 20M High')]
            
            if not action_stocks.empty:
                for sector in sector_counts.index:
                    sec_action = action_stocks[action_stocks['Sector'] == sector]
                    if not sec_action.empty:
                        stock_details = []
                        for _, row in sec_action.iterrows():
                            badges = ""
                            if row['Super Setup'] == '⭐ A+ 20M High': badges += "⭐"
                            if row['Entry Setup'] == '🔥 20D Breakout': badges += "🔥"
                            if row['Entry Setup'] == '⚠️ Near Breakout': badges += "⚠️"
                            if row['Volume Alert'] == '🚀 High Vol': badges += "🚀"
                            stock_details.append(f"{row['Stock']} ({badges})")
                            
                        st.markdown(f"**{sector}**: " + ", ".join(stock_details))
            else:
                st.write("No strong breakouts or volume spikes today.")
                
        st.divider()
        st.subheader("📋 Detailed Scanner Results")
        
        def highlight_setup(s):
            if s == "🔥 20D Breakout":
                return "color: #FF4B4B; font-weight: bold"
            elif s == "⚠️ Near Breakout":
                return "color: #FFA500; font-weight: bold"
            elif s == "🟢 Pullback Setup":
                return "color: #00CC96; font-weight: bold"
            return ""
            
        def highlight_super(s):
            if s == "⭐ A+ 20M High":
                return "background-color: #FFFF00; color: #000000; font-weight: bold"
            return ""
            
        st.dataframe(
            df_results.style.map(highlight_setup, subset=['Entry Setup']).map(highlight_super, subset=['Super Setup']),
            use_container_width=True,
            height=600
        )
    else:
        progress.progress(1.0)
        status.empty()
        st.warning("No stocks passed all filters today. Market might be weak.")
