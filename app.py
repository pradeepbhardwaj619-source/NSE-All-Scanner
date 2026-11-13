import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import io
import time

st.set_page_config(page_title="All NSE Breakout Scanner", layout="wide")
st.title("🦅 All NSE Universe - First Breakout Scanner")
st.write("Tracking Fresh 20D Breakouts, Volume Alerts, Top 20% RS & Market Cap > 1000 Cr.")

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

if st.button("Start Full Market Scan (~2000 Stocks)"):
    status = st.empty()
    progress_bar = st.progress(0)
    
    tickers = get_all_nse()
    total_tickers = len(tickers)
    
    # 200 ke chote batch taaki RAM full na ho aur hang na ho
    chunk_size = 200
    results = []
    
    for i in range(0, total_tickers, chunk_size):
        chunk = tickers[i:i + chunk_size]
        status.text(f"Processing Batch {i//chunk_size + 1} of {(total_tickers//chunk_size) + 1} (Up to {min(i+chunk_size, total_tickers)} stocks)...")
        
        # Download chunk
        data = yf.download(chunk, period="1y", interval="1d", group_by="ticker", progress=False, threads=True)
        
        # Haath-o-haath chunk process karke memory free karna
        for t in chunk:
            try:
                # Handle edge case if chunk has only 1 ticker
                if len(chunk) == 1:
                    df = data.dropna(subset=['Close'])
                else:
                    if t not in data.columns.levels[0]: continue
                    df = data[t].dropna(subset=['Close'])
                
                if len(df) > 200:
                    cmp = float(df['Close'].iloc[-1])
                    if cmp < 10: continue # Penny stock filter
                        
                    sma_20 = float(df['Close'].rolling(window=20).mean().iloc[-1])
                    sma_50 = float(df['Close'].rolling(window=50).mean().iloc[-1])
                    sma_200 = float(df['Close'].rolling(window=200).mean().iloc[-1])
                    
                    df['Prev_20D_High'] = df['High'].shift(1).rolling(window=20).max()
                    df['Prev_20D_Low'] = df['Low'].shift(1).rolling(window=20).min()
                    df['Avg_Vol_20'] = df['Volume'].shift(1).rolling(window=20).mean()
                    
                    latest_vol = float(df['Volume'].iloc[-1])
                    avg_vol_20 = float(df['Avg_Vol_20'].iloc[-1])
                    
                    # Turnover filter (>2Cr)
                    if (avg_vol_20 * cmp) < 20000000: continue
                        
                    vol_alert = "🚀 High Vol" if latest_vol > (1.5 * avg_vol_20) else "-"
                    
                    df['Is_Low'] = df['Low'] <= df['Prev_20D_Low']
                    df['Is_High'] = df['High'] >= df['Prev_20D_High']
                    
                    last_60 = df.tail(60)
                    low_days = last_60[last_60['Is_Low']]
                    
                    if not low_days.empty:
                        recent_low_date = low_days.index[-1]
                        subset = last_60.loc[recent_low_date:]
                        breakouts = subset[subset['Is_High']]
                        low_dt_str = recent_low_date.strftime("%d-%b")
                        
                        if len(breakouts) > 0:
                            bo_price = breakouts['Prev_20D_High'].iloc[0]
                            bo_dt_str = breakouts.index[0].strftime("%d-%b")
                            bo_status = f"✅ Triggered ({bo_dt_str})"
                        else:
                            bo_price = float(df['Prev_20D_High'].iloc[-1])
                            bo_status = "⏳ Waiting"
                    else:
                        low_dt_str = "-"
                        bo_price = float(df['Prev_20D_High'].iloc[-1])
                        bo_status = "No recent 20D Low"
                    
                    diff_pct = ((cmp - bo_price) / bo_price) * 100
                    ret_3m = ((cmp - float(df['Close'].iloc[-63])) / float(df['Close'].iloc[-63])) * 100
                    symbol_clean = t.replace(".NS", "")
                    
                    results.append({
                        "Stock": symbol_clean,
                        "Close": cmp,
                        "3M Return %": ret_3m,
                        "Vol Alert": vol_alert,
                        "Last 20D Low": low_dt_str,
                        "First BO Status": bo_status,
                        "BO Level": bo_price,
                        "% From Entry": diff_pct,
                        "20 SMA": sma_20,
                        "50 SMA": sma_50,
                        "200 SMA": sma_200,
                        "Chart": f"https://in.tradingview.com/chart/?symbol=NSE:{symbol_clean}",
                        "Fundamentals": f"https://www.screener.in/company/{symbol_clean}/"
                    })
            except Exception:
                pass
                
        progress_bar.progress(min((i + chunk_size) / total_tickers, 1.0))
        time.sleep(0.5) # Server ko saans lene ke liye aade second ka break
        
    status.text("Filtering Technicals & Fetching Market Cap (Sirf filtered stocks ka)...")
    
    if results:
        df_all = pd.DataFrame(results)
        df_all['3M RS'] = (df_all['3M Return %'].rank(pct=True) * 100)
        
        # Pehle technical filters lagao taaki list choti ho jaye
        pre_final = df_all[
            (df_all['3M RS'] >= 80) & 
            (df_all['Close'] > df_all['200 SMA']) & 
            (df_all['Close'] > df_all['20 SMA']) & 
            (df_all['20 SMA'] > df_all['50 SMA'])
        ]
        
        # Market Cap > 1000 Cr filter (Sirf bache hue choti list par apply hoga)
        final_list = []
        for idx, row in pre_final.iterrows():
            try:
                tkr = yf.Ticker(row['Stock'] + ".NS")
                mcap = tkr.fast_info['marketCap']
                mcap_cr = mcap / 10000000
                
                if mcap_cr >= 1000:
                    row_dict = row.to_dict()
                    row_dict['MCap (Cr)'] = round(mcap_cr, 2)
                    final_list.append(row_dict)
            except Exception:
                pass
                
        status.empty()
        progress_bar.empty()
        
        if final_list:
            final_df = pd.DataFrame(final_list).sort_values(by="3M RS", ascending=False).drop(columns=['3M Return %'])
            st.success(f"✅ {len(final_df)} Stocks Found! (Top 20% RS, 200-DMA & Market Cap > 1000 Cr Passed)")
            
            # Columns ko reorder kar rahe hain taaki MCap dikh sake
            cols = final_df.columns.tolist()
            cols.insert(1, cols.pop(cols.index('MCap (Cr)')))
            final_df = final_df[cols]
            
            st.dataframe(
                final_df.round(2), 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "Chart": st.column_config.LinkColumn("📈 Chart", display_text="Open TV"),
                    "Fundamentals": st.column_config.LinkColumn("📊 Fundamentals", display_text="Screener"),
                    "% From Entry": st.column_config.NumberColumn("% From Entry", format="%.2f %%"),
                    "MCap (Cr)": st.column_config.NumberColumn("MCap (Cr)", format="₹%d Cr")
                }
            )
        else:
            st.warning("Aaj koi stock saare rules (aur Market Cap > 1000Cr) pass nahi kar paya.")
