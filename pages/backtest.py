import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
import requests
import io

st.set_page_config(page_title="Nifty 500 Sniper Backtester", layout="wide")
st.title("📊 Nifty 500 Sniper Backtest (Sept 2024 - Present)")
st.write("Rules: Top 20% RS + 20D Pullback Breakout -> 10% Target or 10% Stop Loss")

@st.cache_data(ttl=86400)
def get_nifty_500():
    # Fetching Nifty 500 from Wikipedia with proper User-Agent to avoid 403 Forbidden
    url = "https://en.wikipedia.org/wiki/NIFTY_500"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    response = requests.get(url, headers=headers)
    tables = pd.read_html(io.StringIO(response.text))
    df = tables[2] # The 3rd table on the page contains the constituents
    return [str(sym).strip() + ".NS" for sym in df['Symbol'].tolist()]

if st.button("Start Nifty 500 Backtest (~1-2 Mins)"):
    status = st.empty()
    progress = st.progress(0)
    
    try:
        tickers = get_nifty_500()
    except Exception as e:
        st.error(f"Error fetching Nifty 500 list: {e}")
        st.stop()
        
    start_date = "2024-03-01"
    end_date = datetime.datetime.today().strftime('%Y-%m-%d')
    backtest_start = pd.to_datetime("2024-09-01")
    
    status.text("Step 1/4: Downloading Daily Data for Nifty 500...")
    data = yf.download(tickers, start=start_date, end=end_date, progress=False, threads=True)
    
    if isinstance(data.columns, pd.MultiIndex):
        close_df = data['Close']
        high_df = data['High']
        low_df = data['Low']
        vol_df = data['Volume']
    else:
        st.error("Error formatting data. Ensure yfinance is updated.")
        st.stop()
        
    status.text("Step 2/4: Calculating Daily Relative Strength (RS) Matrix...")
    progress.progress(0.4)
    
    roll_ret_63 = close_df.pct_change(periods=63)
    rs_matrix = roll_ret_63.rank(axis=1, pct=True) * 100

    status.text("Step 3/4: Running Trade Simulation (Entry -> Target/SL)...")
    progress.progress(0.6)
    
    all_trades = []
    
    valid_tickers = close_df.columns
    total_ticks = len(valid_tickers)
    
    for idx, ticker in enumerate(valid_tickers):
        if idx % 50 == 0:
            status.text(f"Step 3/4: Simulating Trades... ({idx}/{total_ticks})")
            
        df = pd.DataFrame({
            'Close': close_df[ticker],
            'High': high_df[ticker],
            'Low': low_df[ticker],
            'Volume': vol_df[ticker],
            'RS': rs_matrix[ticker]
        }).dropna()
        
        if len(df) < 200:
            continue
            
        df['SMA_20'] = df['Close'].rolling(20).mean()
        df['SMA_50'] = df['Close'].rolling(50).mean()
        df['SMA_200'] = df['Close'].rolling(200).mean()
        df['Turnover'] = df['Close'] * df['Volume'].shift(1).rolling(20).mean()
        
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
                        if row['Recent_10D_Low'] == row['Prev_20D_Low']:
                            if row['High'] >= row['Prev_20D_High'] and row['Prev_20D_High'] > row['SMA_20']:
                                in_trade = True
                                entry_date = date
                                entry_price = row['Prev_20D_High'] 
                                target_price = entry_price * 1.10
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
        win_rate = (wins / total_trades) * 100
        avg_days = trades_df['Days Held'].mean()
        
        st.success("✅ Nifty 500 Backtest Completed!")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Trades", total_trades)
        col2.metric("Win Rate", f"{win_rate:.2f}%")
        col3.metric("Total Winners", wins)
        col4.metric("Avg Days Held", f"{avg_days:.0f} Days")
        
        st.subheader("📜 Detailed Trade Log")
        st.dataframe(trades_df.sort_values(by="Entry Date", ascending=False), use_container_width=True)
    else:
        st.warning("No trades triggered in Nifty 500 during this timeframe.")
