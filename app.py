import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import io
import time

st.set_page_config(page_title="Super RS Scanner", layout="wide")
st.title("🦅 Super RS Scanner: The Ultimate Momentum Setup")
st.markdown("**Rules: Top 750 (10Cr+ T.O) -> 200 DMA -> 3M RS > 80 (ALL SHOWN) -> Sniper Entries**")

# --- YOUR PERSONAL GOOGLE SHEET WEBHOOK ---
WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbwkhNOJYeXvW1kSFWyXYFzbQmrLDhgQP71YM9bFI7FqnNw2In5ZnAGS0kxB7ntZIfWZ/exec"

# --- MASSIVE NSE500 SECTOR DICTIONARY ---
KNOWN_SECTORS = {
    "TCS":"IT", "INFY":"IT", "HCLTECH":"IT", "WIPRO":"IT", "LTIM":"IT", "TECHM":"IT", "PERSISTENT":"IT", "COFORGE":"IT", "CYIENT":"IT", "KPITTECH":"IT", "TATAELXSI":"IT", "MPHASIS":"IT", "TANLA":"IT", "OFSS":"IT", "ZENTEC":"IT", "SONATSOFTW":"IT", "BSOFT":"IT", "INTELLECT":"IT", "MASTEK":"IT", "NEWGEN":"IT",
    "HDFCBANK":"Finance", "ICICIBANK":"Finance", "SBIN":"Finance", "KOTAKBANK":"Finance", "AXISBANK":"Finance", "INDUSINDBK":"Finance", "BAJFINANCE":"Finance", "BAJAJFINSV":"Finance", "CHOLAFIN":"Finance", "MUTHOOTFIN":"Finance", "RECLTD":"Finance", "PFC":"Finance", "IREDA":"Finance", "JIOFIN":"Finance", "SOUTHBANK":"Finance", "DHANBANK":"Finance", "MOTILALOFS":"Finance", "ANGELONE":"Finance", "BSE":"Finance", "MCX":"Finance", "LICHSGFIN":"Finance", "PNB":"Finance", "KTKBANK":"Finance", "IDFCFIRSTB":"Finance", "YESBANK":"Finance", "CANBK":"Finance", "UNIONBANK":"Finance", "IOB":"Finance", "CUB":"Finance", "FEDERALBNK":"Finance", "ABCAPITAL":"Finance", "M&MFIN":"Finance", "SUNDARMFIN":"Finance", "POONAWALLA":"Finance", "IEX":"Finance", "CDSL":"Finance",
    "SUNPHARMA":"Pharma", "CIPLA":"Pharma", "DIVISLAB":"Pharma", "DRREDDY":"Pharma", "APOLLOHOSP":"Pharma", "MAXHEALTH":"Pharma", "LUPIN":"Pharma", "AUROPHARMA":"Pharma", "BIOCON":"Pharma", "GLENMARK":"Pharma", "SYNGENE":"Pharma", "LAURUSLABS":"Pharma", "NATCOPHARM":"Pharma", "GRANULES":"Pharma", "ALEMBICLTD":"Pharma", "GLAND":"Pharma", "YATHARTH":"Pharma", "MEDPLUS":"Pharma", "SANOFI":"Pharma", "ABBOTINDIA":"Pharma", "PFIZER":"Pharma", "FORTIS":"Pharma", "NARAYANA":"Pharma", "NH":"Pharma",
    "TATAMOTORS":"Auto", "M&M":"Auto", "MARUTI":"Auto", "BAJAJ-AUTO":"Auto", "EICHERMOT":"Auto", "HEROMOTOCO":"Auto", "TVSMOTOR":"Auto", "ASHOKLEY":"Auto", "BOSCHLTD":"Auto", "MRF":"Auto", "BALKRISIND":"Auto", "SONACOMS":"Auto", "MOTHERSON":"Auto", "SSWL":"Auto", "ALICON":"Auto", "KROSS":"Auto", "MENONBE":"Auto", "GREAVESCOT":"Auto", "AMARAJABAT":"Auto", "EXIDEIND":"Auto", "CEATLTD":"Auto", "APOLLOTYRE":"Auto", "MINDAIND":"Auto", "ENDURANCE":"Auto",
    "RELIANCE":"Energy", "ONGC":"Energy", "NTPC":"Energy", "POWERGRID":"Energy", "TATAPOWER":"Energy", "ADANIGREEN":"Energy", "ADANIPOWER":"Energy", "COALINDIA":"Energy", "IOC":"Energy", "BPCL":"Energy", "GAIL":"Energy", "HINDOILEXP":"Energy", "SUZLON":"Energy", "NHPC":"Energy", "SJVN":"Energy", "IGL":"Energy", "MGL":"Energy", "GUJGASLTD":"Energy", "PETRONET":"Energy", "OIL":"Energy", "TORNTPOWER":"Energy", "JSWENERGY":"Energy",
    "LT":"Cap Goods", "HAL":"Defense", "BEL":"Defense", "BHEL":"Cap Goods", "SIEMENS":"Cap Goods", "ABB":"Cap Goods", "CUMMINSIND":"Cap Goods", "CGPOWER":"Cap Goods", "BDL":"Defense", "MAZDOCK":"Defense", "COCHINSHIP":"Defense", "GRSE":"Defense", "TITAGARH":"Rail", "RVNL":"Rail", "IRFC":"Rail", "IRCON":"Rail", "ENGINERSIN":"Cap Goods", "POLYCAB":"Cap Goods", "KEI":"Cap Goods", "HAVELLS":"Cap Goods", "DIXON":"Cap Goods", "VOLTAS":"Cap Goods", "BLUESTARCO":"Cap Goods", "THERMAX":"Cap Goods", "AIAENG":"Cap Goods",
    "HUL":"FMCG", "ITC":"FMCG", "NESTLEIND":"FMCG", "BRITANNIA":"FMCG", "TATACONSUM":"FMCG", "TITAN":"Consumer", "ASIANPAINT":"Consumer", "PIDILITIND":"Consumer", "TRENT":"Consumer", "ZOMATO":"Consumer", "DMART":"Consumer", "NYKAA":"Consumer", "RAYMOND":"Consumer", "STYLEBAAZA":"Consumer", "PARAGMILK":"FMCG", "MARICO":"FMCG", "DABUR":"FMCG", "GODREJCP":"FMCG", "COLPAL":"FMCG", "VARROC":"FMCG", "VBL":"FMCG", "RADICO":"FMCG", "UBL":"FMCG", "PAGEIND":"Consumer", "BATAINDIA":"Consumer",
    "TATASTEEL":"Metals", "JSWSTEEL":"Metals", "HINDALCO":"Metals", "VEDL":"Metals", "SRF":"Chemicals", "PIIND":"Chemicals", "TATACHEM":"Chemicals", "DEEPAKNTR":"Chemicals", "AARTIIND":"Chemicals", "CHEMPLASTS":"Chemicals", "SHYAMMETL":"Metals", "SAIL":"Metals", "NMDC":"Metals", "NATIONALUM":"Metals", "JINDALSTEL":"Metals", "UPL":"Chemicals", "COROMANDEL":"Chemicals", "NAVINFLUOR":"Chemicals", "ATUL":"Chemicals", "GUJALKALI":"Chemicals",
    "DLF":"Realty", "MACROTECH":"Realty", "GODREJPROP":"Realty", "OBEROIRLTY":"Realty", "PRESTIGE":"Realty", "ULTRACEMCO":"Cement", "SHREECEM":"Cement", "AMBUJACEM":"Cement", "ACC":"Cement", "DALBHARAT":"Cement", "RAMCOCEM":"Cement", "JKCEMENT":"Cement", "LODHA":"Realty", "SOBHA":"Realty", "BRIGADE":"Realty",
    "BHARTIARTL":"Telecom", "IDEA":"Telecom", "INDUSTOWER":"Telecom", "SUNTV":"Media", "ZEEL":"Media", "PVRINOX":"Media", "SAREGAMA":"Media", "TIPSMUSIC":"Media", "INDHOTEL":"Hotels", "CHALET":"Hotels", "LEMONTREE":"Hotels", "THELEELA":"Hotels", "ORIENTHOT":"Hotels", "TATACOMM":"Telecom"
}

def get_sector_offline(ticker):
    clean_ticker = ticker.replace(".NS", "")
    return KNOWN_SECTORS.get(clean_ticker, "Emerging / Midcap")

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
        else:
            st.error("Data structure error from Yahoo Finance.")
            st.stop()
    except Exception as e:
        st.error(f"Extraction Error: {e}")
        st.stop()
        
    status.text("Step 3/5: Filtering Top 750 (10Cr+ T.O) & > 200 DMA...")
    progress.progress(0.5)
    
    valid_counts = closes.notna().sum()
    valid_tickers = valid_counts[valid_counts >= 200].index
    
    closes = closes[valid_tickers]
    volumes = volumes[valid_tickers]
    highs = highs[valid_tickers]
    
    avg_vol_20 = volumes.tail(20).mean()
    cmp = closes.iloc[-1]
    avg_turnover = (cmp * avg_vol_20) / 10000000 
    
    top_750_tickers = avg_turnover.nlargest(750).index.tolist()
    
    closes = closes[top_750_tickers]
    volumes = volumes[top_750_tickers]
    highs = highs[top_750_tickers]
    
    status.text("Step 4/5: Calculating RS Ratings & Filtering (RS >= 80)...")
    progress.progress(0.7)
    
    sma_200_all = closes.rolling(window=200).mean().iloc[-1]
    valid_base = closes.iloc[-1] > sma_200_all
    final_tickers = valid_base[valid_base].index.tolist()
    
    closes = closes[final_tickers]
    highs = highs[final_tickers]
    volumes = volumes[final_tickers]
    
    ret_3m_current = (closes.iloc[-1] / closes.iloc[-63]) - 1
    rs_current = ret_3m_current.rank(pct=True) * 100
    
    ret_3m_prev = (closes.iloc[-6] / closes.iloc[-68]) - 1
    rs_prev = ret_3m_prev.rank(pct=True) * 100
    
    top_rs_tickers = rs_current[rs_current >= 80].index.tolist()
    
    status.text("Step 5/5: Finding Setups, Trend Sequences & Proximity...")
    progress.progress(0.85)
    
    results = []
    for t in top_rs_tickers:
        c_close = closes[t]
        c_high = highs[t]
        c_vol = volumes[t]
        
        cmp_val = c_close.iloc[-1]
        c_rs = rs_current[t]
        p_rs = rs_prev[t]
        
        if c_rs > p_rs + 2: rs_mom = "📈 Rising"
        elif c_rs < p_rs - 2: rs_mom = "📉 Cooling"
        else: rs_mom = "⚖️ Stable"
            
        sma20 = c_close.rolling(20).mean().iloc[-1]
        sma50 = c_close.rolling(50).mean().iloc[-1]
        sma200 = c_close.rolling(200).mean().iloc[-1]
        
        prev_20d_high = c_high.iloc[-21:-1].max()
        dist_to_breakout = ((prev_20d_high - cmp_val) / cmp_val) * 100
        
        ma_sequence = "-"
        if (prev_20d_high > sma20) and (sma20 > sma50) and (sma50 > sma200):
            ma_sequence = "✅ Aligned"
            
        high_20m = c_high.tail(420).max()
        dist_to_20m_high = ((high_20m - cmp_val) / cmp_val) * 100
        
        if cmp_val >= prev_20d_high: setup = "🔥 20D Breakout"
        elif 0 < dist_to_breakout <= 7.0: setup = "⚠️ Near Breakout"
        else: setup = "⏳ Consolidating"
            
        vol_20_avg = c_vol.iloc[-21:-1].mean()
        if c_vol.iloc[-1] > (1.5 * vol_20_avg): vol_alert = "🚀 High Vol"
        else: vol_alert = "-"
            
        suggested_target = cmp_val * 1.08
        suggested_sl = cmp_val * 0.85
            
        results.append({
            "Stock": t.replace(".NS", ""),
            "Sector": get_sector_offline(t),
            "CMP (₹)": round(cmp_val, 2),
            "3M RS": round(c_rs, 1),
            "RS Mom": rs_mom,
            "Trend": ma_sequence,
            "Setup": setup,
            "Dist BO %": round(max(0, dist_to_breakout), 2),
            "Dist 20M High %": round(dist_to_20m_high, 2),
            "Volume": vol_alert,
            "TGT (8%)": round(suggested_target, 2),
            "SL (-15%)": round(suggested_sl, 2),
            "_mom_score": 1 if rs_mom == "📈 Rising" else (2 if rs_mom == "⚖️ Stable" else 3),
            "_setup_score": 1 if setup == "🔥 20D Breakout" else (2 if setup == "⚠️ Near Breakout" else 3)
        })

    progress.progress(1.0)
    status.empty()
    
    if results:
        df_results = pd.DataFrame(results)
        df_results = df_results.sort_values(by=["_mom_score", "_setup_score", "3M RS"], ascending=[True, True, False])
        df_results = df_results.drop(columns=['_mom_score', '_setup_score']).reset_index(drop=True)
        
        st.success(f"✅ Scan Complete! Found {len(df_results)} Stocks with RS > 80.")
        
        # --- NEW INTEGRATED BUTTON TO UPDATE GOOGLE SHEET ---
        st.divider()
        col_btn, col_msg = st.columns([1, 3])
        with col_btn:
            push_clicked = st.button("📤 Push to Google Sheet")
            
        if push_clicked:
            with st.spinner("Pushing stocks to your Google Sheet..."):
                # Format to "NSE:TCS" for your Google Finance formulas
                stock_list = ["NSE:" + s for s in df_results['Stock'].tolist()]
                payload = {"stocks": stock_list}
                try:
                    res = requests.post(WEBHOOK_URL, json=payload)
                    if res.status_code == 200:
                        st.success(f"✅ Successfully sent {len(stock_list)} stocks to your sheet!")
                    else:
                        st.error(f"❌ Error from Google: {res.text}")
                except Exception as e:
                    st.error(f"Connection Error: {e}")
        st.divider()
        
        st.subheader("🧩 Sector Sentiment (Money Flow)")
        sector_counts = df_results['Sector'].value_counts()
        
        col1, col2 = st.columns([1, 2])
        with col1:
            st.write("**Stocks per Sector:**")
            for sector, count in sector_counts.items():
                st.write(f"- **{sector}**: {count} stocks")
                
        with col2:
            st.write("**🔥 Actionable (Breakouts / High Vol) by Sector:**")
            action_stocks = df_results[(df_results['Setup'].isin(['🔥 20D Breakout', '⚠️ Near Breakout'])) | (df_results['Volume'] == '🚀 High Vol')]
            if not action_stocks.empty:
                for sector in sector_counts.index:
                    sec_action = action_stocks[action_stocks['Sector'] == sector]
                    if not sec_action.empty:
                        stock_details = []
                        for _, row in sec_action.iterrows():
                            badges = ""
                            if row['Setup'] == '🔥 20D Breakout': badges += "🔥"
                            if row['Setup'] == '⚠️ Near Breakout': badges += "⚠️"
                            if row['Volume'] == '🚀 High Vol': badges += "🚀"
                            stock_details.append(f"{row['Stock']} ({badges})")
                        st.markdown(f"**{sector}**: " + ", ".join(stock_details))
            else:
                st.write("No strong breakouts or volume spikes today.")
                
        st.subheader("📋 Detailed Scanner Results")
        def highlight_setup(s):
            if s == "🔥 20D Breakout": return "color: #FF4B4B; font-weight: bold"
            elif s == "⚠️ Near Breakout": return "color: #FFA500; font-weight: bold"
            return ""
        def highlight_seq(s):
            if s == "✅ Aligned": return "color: #00CC96; font-weight: bold"
            return ""
        def highlight_mom(s):
            if s == "📈 Rising": return "color: #00CC96; font-weight: bold"
            elif s == "📉 Cooling": return "color: #FF4B4B"
            return ""

        st.dataframe(
            df_results.style.map(highlight_setup, subset=['Setup'])
                           .map(highlight_seq, subset=['Trend'])
                           .map(highlight_mom, subset=['RS Mom']),
            use_container_width=True,
            height=700
        )
    else:
        st.warning("No stocks passed the base filters today.")
