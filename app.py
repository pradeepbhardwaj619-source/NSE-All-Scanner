import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import io
import time

st.set_page_config(page_title="Master RS & Sniper Entry Scanner", layout="wide")
st.title("🦅 Full NSE - Premium Universe Sniper Scanner")
st.write("Flow: 200-DMA & 10Cr Turnover -> MCap > 1000Cr -> Top 20% RS -> 🎯 Sniper Entry Tag & Post-BO Max Drawdown")

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

if st.button("Start Premium Market Scan (~2000 Stocks)"):
    status = st.empty()
    progress_bar = st.progress(0)
    
    tickers = get_all_nse()
    total_tickers = len(tickers)
    
    chunk_size = 200
    stage1_results = []
    
    for i in range(0, total_tickers, chunk_size):
        chunk = tickers[i:i + chunk_size]
        status.text(f"Step 1/3: Filtering 200-DMA & 10Cr Turnover - Batch {i//chunk_size + 1}...")
        
        data = yf.download(chunk, period="1y", interval="1d", group_by="ticker", progress=False, threads=True)
        
        for t in chunk:
            try:
                if len(chunk) == 1:
                    df = data.dropna(subset=['Close'])
                else:
                    if t not in data.columns.levels[0]: continue
                    df = data[t].dropna(subset=['Close'])
                
                if len(df) > 200:
                    cmp = float(df['Close'].iloc[-1])
                    if cmp < 10: continue 
                    
                    sma_200 = float(df['Close'].rolling(window=200).mean().iloc[-1])
                    
                    if cmp < sma_200: continue
                    
                    df['Avg_Vol_20'] = df['Volume'].shift(1).rolling(window=20).mean()
                    avg_vol_20 = float(df['Avg_Vol_20'].iloc[-1])
                    
                    if (avg_vol_20 * cmp) < 100000000: continue
                        
                    sma_20 = float(df['Close'].rolling(window=20).mean().iloc[-1])
                    sma_50 = float(df['Close'].rolling(window=50).mean().iloc[-1])
                    
                    df['Prev_20D_High'] = df['High'].shift(1).rolling(window=20).max()
                    df['Prev_20D_Low'] = df['Low'].shift(1).rolling(window=20).min()
                    
                    df['Is_Low'] = df['Low'] <= df['Prev_20D_Low']
                    df['Is_High'] = df['High'] >= df['Prev_20D_High']
                    
                    last_60 = df.tail(60)
                    low_days = last_60[last_60['Is_Low']]
                    
                    max_drawdown = 0.0
                    
                    if not low_days.empty:
                        recent_low_date = low_days.index[-1]
                        subset = last_60.loc[recent_low_date:]
                        breakouts = subset[subset['Is_High']]
                        
                        low_dt_obj = recent_low_date.date()
                        
                        if len(breakouts) > 0:
                            bo_date = breakouts.index[0]
                            bo_price = breakouts['Prev_20D_High'].iloc[0]
                            bo_dt_obj = bo_date.date()
                            bo_status = "✅ Triggered"
                            
                            # ==========================================
                            # POST-BREAKOUT MAX DRAWDOWN CALCULATION
                            # ==========================================
                            post_bo_data = last_60.loc[bo_date:]
                            min_post_bo_low = float(post_bo_data['Low'].min())
                            # Drawdown is calculated from the BO price to the lowest low hit afterwards
                            if min_post_bo_low < bo_price:
                                max_drawdown = ((min_post_bo_low - bo_price) / bo_price) * 100
                            else:
                                max_drawdown = 0.0
                                
                        else:
                            bo_price = float(df['Prev_20D_High'].iloc[-1])
                            bo_dt_obj = None
                            bo_status = "⏳ Waiting"
                    else:
                        low_dt_obj = None
                        bo_price = float(df['Prev_20D_High'].iloc[-1])
                        bo_dt_obj = None
                        bo_status = "❌ No Low"
                    
                    # SNIPER SETUP LOGIC (Anti-Overextended Rule)
                    low_20d = float(df['Low'].tail(20).min())
                    recent_10d_low = float(df['Low'].tail(10).min())
                    
                    passes_pro_setup = False
                    if (sma_20 > sma_50 > sma_200) and (recent_10d_low == low_20d):
                        if bo_status == "✅ Triggered":
                            dist_from_bo = ((cmp - bo_price) / bo_price) * 100
                            if dist_from_bo <= 5.0:  
                                passes_pro_setup = True
                        elif bo_status == "⏳ Waiting":
                            dist_to_bo = ((bo_price - cmp) / cmp) * 100
                            if dist_to_bo <= 5.0:
                                passes_pro_setup = True
                    
                    latest_vol = float(df['Volume'].iloc[-1])
                    vol_alert = "🚀 High Vol" if latest_vol > (1.5 * avg_vol_20) else "-"
                    
                    dist_to_high = ((bo_price - cmp) / cmp) * 100 if bo_status == "⏳ Waiting" else ((cmp - bo_price) / bo_price) * 100
                    ret_3m = ((cmp - float(df['Close'].iloc[-63])) / float(df['Close'].iloc[-63])) * 100
                    symbol_clean = t.replace(".NS", "")
                    
                    stage1_results.append({
                        "Stock": symbol_clean,
                        "Close": cmp,
                        "3M Return %": ret_3m,
                        "Passes Setup": passes_pro_setup,
                        "Vol Alert": vol_alert,
                        "Last 20D Low": low_dt_obj,
                        "BO Status": bo_status,
                        "Trigger Date": bo_dt_obj,
                        "Max Drawdown %": max_drawdown if bo_status == "✅ Triggered" else None,
                        "% From Entry": dist_to_high,
                        "20 SMA": sma_20,
                        "50 SMA": sma_50,
                        "200 SMA": sma_200,
                        "Chart": f"https://in.tradingview.com/chart/?symbol=NSE:{symbol_clean}",
                        "Fundamentals": f"https://www.screener.in/company/{symbol_clean}/"
                    })
            except Exception:
                pass
                
        progress_bar.progress(min((i + chunk_size) / total_tickers, 0.6))
        time.sleep(0.5)
        
    stage2_results = []
    total_stage1 = len(stage1_results)
    
    for idx, row in enumerate(stage1_results):
        status.text(f"Step 2/3: Checking Market Cap for {total_stage1} strong stocks ({idx+1}/{total_stage1})...")
        try:
            tkr = yf.Ticker(row['Stock'] + ".NS")
            mcap_cr = tkr.fast_info['marketCap'] / 10000000
            
            if mcap_cr >= 1000:
                row['MCap (Cr)'] = round(mcap_cr, 2)
                stage2_results.append(row)
        except Exception:
            pass
        
        progress_bar.progress(0.6 + (0.3 * ((idx + 1) / total_stage1)))
        
    status.text("Step 3/3: Calculating True Premium RS & Tagging Sniper Entries...")
    progress_bar.progress(1.0)
    
    if stage2_results:
        df_all = pd.DataFrame(stage2_results)
        df_all['3M RS'] = (df_all['3M Return %'].rank(pct=True) * 100)
        
        final_df = df_all[df_all['3M RS'] >= 80].copy()
        
        status.empty()
        progress_bar.empty()
        
        if not final_df.empty:
            final_df['Entry Alert'] = final_df['Passes Setup'].apply(lambda x: "🎯 Sniper Entry" if x else "-")
            
            final_df = final_df.sort_values(by="3M RS", ascending=False)
            final_df = final_df.drop(columns=['3M Return %', 'Passes Setup'])
            
            cols = final_df.columns.tolist()
            cols.insert(1, cols.pop(cols.index('MCap (Cr)')))
            cols.insert(2, cols.pop(cols.index('Entry Alert')))
            final_df = final_df[cols]
            
            sniper_count = len(final_df[final_df['Entry Alert'] == "🎯 Sniper Entry"])
            
            st.success(f"✅ {len(final_df)} Premium RS Leaders Found! ({sniper_count} Fresh '🎯 Sniper Entry' setups)")
            
            st.dataframe(
                final_df.round(2), 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "Last 20D Low": st.column_config.DateColumn("Last 20D Low", format="DD-MMM-YYYY"),
                    "Trigger Date": st.column_config.DateColumn("Trigger Date", format="DD-MMM-YYYY"),
                    "Max Drawdown %": st.column_config.NumberColumn("Post-BO Drawdown", format="%.2f %%"),
                    "% From Entry": st.column_config.NumberColumn("% From Entry", format="%.2f %%"),
                    "Chart": st.column_config.LinkColumn("📈 Chart", display_text="Open TV"),
                    "Fundamentals": st.column_config.LinkColumn("📊 Fundamentals", display_text="Screener"),
                    "MCap (Cr)": st.column_config.NumberColumn("MCap (Cr)", format="₹%d Cr")
                }
            )
        else:
            st.warning("Aaj Premium Universe में कोई स्टॉक टॉप RS क्राइटेरिया पास नहीं कर पाया।")
    else:
        st.error("Market data fetch करने में एरर आई।")
