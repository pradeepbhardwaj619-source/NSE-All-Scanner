import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import io
import time
import concurrent.futures

st.set_page_config(page_title="Super RS Scanner", layout="wide")
st.title("🦅 Super RS Scanner: Top 750 Liquid Universe")
st.markdown("**(Top 750 Liquidity -> 200-DMA & 10Cr -> 3M RS >= 80 -> RS Momentum -> Sniper Entry)**")

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

# Fast API call to get Sector for final stocks only
def get_sector(ticker):
    try:
        info = yf.Ticker(ticker).info
        return info.get('sector', 'Unknown')
    except Exception:
        return 'Unknown'

if st.button("🚀 Start Super Scan (~1 Min)"):
    status = st.empty()
    progress = st.progress(0)
    
    status.text("Step 1/6: Fetching NSE Equities...")
    try:
        tickers = get_all_nse()
    except Exception as e:
        st.error(f"List Fetch Error: {e}")
        st.stop()
    
    status.text(f"Step 2/6: Downloading Data for {len(tickers)} Stocks...")
    progress.progress(0.1)
    
    chunk_size = 500
    data_frames = []
    total_batches = (len(tickers) // chunk_size) + 1
    
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i:i + chunk_size]
        status.text(f"Step 2/6: Downloading Data... Batch {i//chunk_size + 1}/{total_batches}")
        df_chunk = yf.download(chunk, period="1y", group_by="ticker", progress=False, threads=True)
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
        
    status.text("Step 3/6: Filtering Top 750 by Liquidity (Anti-Operator Game)...")
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
    
    status.text("Step 4/6: Calculating True RS Rating & Momentum on Top 750...")
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
    
    status.text("Step 5/6: Finding Sniper Entries & Breakouts...")
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
        if cmp_val >= prev_20d_high:
            setup = "🔥 20D Breakout"
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
            
        results.append({
            "Ticker": t,
            "Stock": t.replace(".NS", ""),
            "CMP (₹)": round(cmp_val, 2),
            "3M RS Rating": round(c_rs, 1),
            "RS Momentum": rs_mom,
            "Entry Setup": setup,
            "Volume Alert": vol_alert,
            "Suggested TGT (8%)": round(suggested_target, 2),
            "Suggested Max SL (-15%)": round(suggested_sl, 2)
        })

    status.text("Step 6/6: Fetching Sector details for final stocks... (Fast)")
    progress.progress(0.95)
    
    if results:
        df_results = pd.DataFrame(results)
        
        # Parallel fetch for only the selected 30-50 stocks (Very Fast)
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            sectors = list(executor.map(get_sector, df_results['Ticker'].tolist()))
        
        df_results.insert(2, 'Sector', sectors)
        df_results = df_results.drop(columns=['Ticker'])
        df_results = df_results.sort_values(by="3M RS Rating", ascending=False).reset_index(drop=True)
        
        progress.progress(1.0)
        status.empty()
        
        st.success(f"✅ Scan Complete! Found {len(df_results)} Institutional Grade Momentum Leaders.")
        
        # --- SECTOR SUMMARY LOGIC ---
        st.subheader("🧩 Sector Sentiment (Where is the Money Flowing?)")
        
        sector_counts = df_results['Sector'].value_counts()
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.write("**Stocks per Sector:**")
            for sector, count in sector_counts.items():
                st.write(f"- **{sector}**: {count} stocks")
                
        with col2:
            st.write("**🔥 Breakout & 🚀 High Volume Leaders by Sector:**")
            # Filter stocks that have either a Breakout or High Volume
            action_stocks = df_results[(df_results['Entry Setup'] == '🔥 20D Breakout') | (df_results['Volume Alert'] == '🚀 High Vol')]
            
            if not action_stocks.empty:
                for sector in sector_counts.index:
                    sec_action = action_stocks[action_stocks['Sector'] == sector]
                    if not sec_action.empty:
                        stock_details = []
                        for _, row in sec_action.iterrows():
                            badges = ""
                            if row['Entry Setup'] == '🔥 20D Breakout': badges += "🔥"
                            if row['Volume Alert'] == '🚀 High Vol': badges += "🚀"
                            stock_details.append(f"{row['Stock']} ({badges})")
                            
                        st.markdown(f"**{sector}**: " + ", ".join(stock_details))
            else:
                st.write("No strong breakouts or volume spikes today.")
                
        st.divider()
        st.subheader("📋 Detailed Scanner Results")
        
        def highlight_breakout(s):
            if s == "🔥 20D Breakout":
                return "color: #FF4B4B; font-weight: bold"
            elif s == "🟢 Pullback Setup":
                return "color: #00CC96; font-weight: bold"
            return ""
            
        st.dataframe(
            df_results.style.map(highlight_breakout, subset=['Entry Setup']),
            use_container_width=True,
            height=600
        )
    else:
        progress.progress(1.0)
        status.empty()
        st.warning("No stocks passed all filters today. Market might be weak.")
