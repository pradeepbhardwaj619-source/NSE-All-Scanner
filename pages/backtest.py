import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import requests
import io
import time

st.set_page_config(page_title="Premium Sniper Backtester", layout="wide")
st.title("📊 Premium Universe Sniper Backtest")
st.write("Rules: 200-DMA & 10Cr -> Top 20% RS -> 20D Pullback -> Breaks 20D High -> Select TGT or 20D Low SL")

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

# Dropdown for multiple profit booking targets
target_choice = st.selectbox("🎯 Select Profit Booking Target:", ["6%", "8%", "10%"])
target_multiplier = {"6%": 1.06, "8%": 1.08, "10%": 1.10}[target_choice]

if st.button(f"Start Backtest with {target_choice} Target (~4-5 Mins)"):
    status = st.empty()
    progress = st.progress(0)
    
    try:
        tickers = get_all_nse()
    except Exception as e:
        st.error(f"Error reading NSE List: {e}")
        st.stop()
        
    start_date = "2024-03-01"
    end_date = datetime.datetime.today().strftime('%Y-%m-%d')
    backtest_start = pd.to_datetime("2024-09-01")
    
    close_list, high_list, low_list, vol_list = [], [], [], []
    chunk_size = 200
    total_tickers = len(tickers)
    total_batches = (total_tickers // chunk_size) + 1
    
    for i in range(0, total_tickers, chunk_size):
        chunk = tickers[i:i + chunk_size]
        current_batch = (i // chunk_size) + 1
        status.text(f"Step 1/4: Downloading Data - Batch {current_batch} of {total_batches}...")
        
        try:
            temp_data = yf.download(chunk, start=start_date, end=end_date, progress=False, threads=True)
            if not temp_data.empty:
                if len(chunk) == 1:
                    close_list.append(temp_data[['Close']].rename(columns={'Close': chunk[0]}))
                    high_list.append(temp_data[['High']].rename(columns={'High': chunk[0]}))
                    low_list.append(temp_data[['Low']].rename(columns={'Low': chunk[0]}))
                    vol_list.append(temp_data[['Volume']].rename(columns={'Volume': chunk[0]}))
                else:
                    close_list.append(temp_data['Close'])
                    high_list.append(temp_data['High'])
                    low_list.append(temp_data['Low'])
                    vol_list.append(temp_data['Volume'])
        except Exception:
            pass
        
        progress.progress(min(0.3 * ((i + chunk_size) / total_tickers), 0.3))
        time.sleep(0.5) 
        
    status.text("Step 2/4: Merging Data & Calculating True RS Matrix...")
    progress.progress(0.35)
    
    if not close_list:
        st.error("Data download failed. Check network or try again.")
        st.stop()
        
    close_df = pd.concat(close_list, axis=1)
    high_df = pd.concat(high_list, axis=1)
    low_df = pd.concat(low_list, axis=1)
    vol_df = pd.concat(vol_list, axis=1)
    
    progress.progress(0.4)
    
    roll_ret_63 = close_df.pct_change(periods=63)
    rs_matrix = roll_ret_63.rank(axis=1, pct=True) * 100

    status.text(f"Step 3/4: Simulating Trades (Entry -> {target_choice} TGT or 20D Low SL)...")
    progress.progress(0.6)
    
    all_trades = []
    valid_tickers = close_df.columns
    total_ticks = len(valid_tickers)
    
    for idx, ticker in enumerate(valid_tickers):
        if idx % 100 == 0:
            status.text(f"Step 3/4: Simulating Trades... ({idx}/{total_ticks} Stocks Checked)")
            
        df = pd.DataFrame({
            'Close': close_df[ticker],
            'High': high_df[ticker],
            'Low': low_df[ticker],
            'Volume': vol_df[ticker],
            'RS': rs_matrix[ticker]
        }).dropna()
        
        if len(df) < 100:
            continue
            
        df['SMA_20'] = df['Close'].rolling(20).mean()
        df['SMA_50'] = df['Close'].rolling(50).mean()
        df['SMA_200'] = df['Close'].rolling(200).mean()
        
        df['Turnover'] = df['Close'] * df['Volume'].shift(1).rolling(20).mean()
        
        # PROVEN LOGIC: 20-Day High Breakout
        df['Prev_20D_High'] = df['High'].shift(1).rolling(20).max()
        df['Prev_20D_Low'] = df['Low'].shift(1).rolling(20).min()
        df['Recent_10D_Low'] = df['Low'].rolling(10).min()
        
        in_trade = False
        entry_price = 0.0
        entry_date = None
        target_price = 0.0
        sl_price = 0.0
        
        df_backtest = df[df.index >= backtest_start]
        
        for date, row in df_backtest.iterrows():
            if not in_trade:
                if row['Close'] > row['SMA_200'] and row['Turnover'] > 100000000:
                    if row['RS'] >= 80 and row['SMA_20'] > row['SMA_50'] > row['SMA_200']:
                        # Pullback confirm
                        if row['Recent_10D_Low'] == row['Prev_20D_Low']:
                            # Breakout confirm (STRICT 20-DAY HIGH)
                            if row['High'] >= row['Prev_20D_High'] and row['Prev_20D_High'] > row['SMA_20']:
                                in_trade = True
                                entry_date = date
                                entry_price = row['Prev_20D_High'] 
                                
                                target_price = entry_price * target_multiplier
                                sl_price = float(row['Prev_20D_Low'])           
                                
                                if sl_price >= entry_price:
                                    sl_price = entry_price * 0.90
            else:
                exit_price = 0.0
                exit_date = date
                trade_result = ""
                
                if row['Low'] <= sl_price:
                    exit_price = sl_price
                    trade_result = "🔴 Stop Loss"
                elif row['High'] >= target_price:
                    exit_price = target_price
                    trade_result = "🟢 Target Hit"
                
                if trade_result != "":
                    pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                    days_held = (exit_date - entry_date).days
                    
                    all_trades.append({
                        "Stock": ticker.replace(".NS", ""),
                        "Entry Date": entry_date.strftime('%Y-%m-%d'),
                        "Entry Price": round(entry_price, 2),
                        "Exit Date": exit_date.strftime('%Y-%m-%d'),
                        "Exit Price": round(exit_price, 2),
                        "Result": trade_result,
                        "PnL %": round(pnl_pct, 2),
                        "Days Held": days_held
                    })
                    
                    in_trade = False

    status.text("Step 4/4: Generating Backtest Report...")
    progress.progress(1.0)
    
    if all_trades:
        trades_df = pd.DataFrame(all_trades)
        
        total_trades = len(trades_df)
        wins = len(trades_df[trades_df['Result'] == "🟢 Target Hit"])
        win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
        avg_days = trades_df['Days Held'].mean()
        
        st.success(f"✅ {target_choice} Target & 20D Low SL Backtest Completed!")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Trades", total_trades)
        col2.metric("Win Rate", f"{win_rate:.2f}%")
        col3.metric("Total Winners", wins)
        col4.metric("Avg Days Held", f"{avg_days:.0f} Days")
        
        st.subheader("📜 Detailed Trade Log")
        st.dataframe(trades_df.sort_values(by="Entry Date", ascending=False), use_container_width=True)
    else:
        st.warning("No trades triggered under these strict rules in the selected timeframe.")
