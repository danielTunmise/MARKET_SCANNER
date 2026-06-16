import os
import requests
import asyncio
import json
import pytz
from datetime import datetime, timedelta
import pandas as pd
from dotenv import load_dotenv
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from fastapi import FastAPI, WebSocket

# Load environment variables from the .env file
load_dotenv()

# Retrieve API credentials from the environment
API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

active_trades = []
trade_history = []

def fetch_alpaca_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not API_KEY or not SECRET_KEY:
        raise ValueError("Alpaca API keys not found. Please set ALPACA_API_KEY and ALPACA_SECRET_KEY in your .env file.")

    # Initialize the historical data client
    client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

    # 100 5-minute candles roughly equals 1.5 trading days. 
    # We look back 5 days to safely account for weekends and holidays.
    start_time = datetime.now() - timedelta(days=5)

    # Define the request parameters for 5-minute data
    request_params_5m = StockBarsRequest(
        symbol_or_symbols=["SPY", "QQQ"],
        timeframe=TimeFrame(5, TimeFrameUnit.Minute),
        start=start_time
    )

    # Fetch the 5-minute data
    bars_5m = client.get_stock_bars(request_params_5m)

    # Alpaca returns a MultiIndex DataFrame by default (symbol, timestamp).
    # We reset the index to turn 'symbol' and 'timestamp' into standard columns.
    df_5m = bars_5m.df.reset_index()

    # Convert timestamp to America/New_York timezone
    df_5m['timestamp'] = df_5m['timestamp'].dt.tz_convert('America/New_York')

    # Define the request parameters for 1-minute data
    request_params_1m = StockBarsRequest(
        symbol_or_symbols=["SPY", "QQQ"],
        timeframe=TimeFrame(1, TimeFrameUnit.Minute),
        start=start_time
    )

    # Fetch the 1-minute data
    bars_1m = client.get_stock_bars(request_params_1m)
    df_1m = bars_1m.df.reset_index()
    df_1m['timestamp'] = df_1m['timestamp'].dt.tz_convert('America/New_York')

    # Define the exact columns requested
    columns = ["timestamp", "open", "high", "low", "close"]

    # Filter by symbol, grab the last 400 rows for 5m, isolate the columns, and reset index
    spy_5m_df = df_5m[df_5m["symbol"] == "SPY"].tail(400)[columns].reset_index(drop=True)
    qqq_5m_df = df_5m[df_5m["symbol"] == "QQQ"].tail(400)[columns].reset_index(drop=True)

    # Filter by symbol, grab the last 1000 rows for 1m, isolate the columns, and reset index
    spy_1m_df = df_1m[df_1m["symbol"] == "SPY"].tail(1000)[columns].reset_index(drop=True)
    qqq_1m_df = df_1m[df_1m["symbol"] == "QQQ"].tail(1000)[columns].reset_index(drop=True)

    return spy_5m_df, qqq_5m_df, spy_1m_df, qqq_1m_df

def find_most_recent_trend(df: pd.DataFrame, max_lookback: int = 100) -> str:
    trend = 'NONE'
    last_swing_high = None
    last_swing_low = None
    
    df = df.tail(max_lookback)
    
    for i in range(1, len(df)):
        prev_candle = df.iloc[i - 1]
        curr_candle = df.iloc[i]
        
        prev_down = prev_candle['close'] < prev_candle['open']
        prev_up = prev_candle['close'] > prev_candle['open']
        curr_down = curr_candle['close'] < curr_candle['open']
        curr_up = curr_candle['close'] > curr_candle['open']
        
        if prev_down and curr_up:
            last_swing_low = min(prev_candle['low'], curr_candle['low'])
            
        if prev_up and curr_down:
            last_swing_high = max(prev_candle['high'], curr_candle['high'])
            
        if last_swing_low is not None and curr_candle['close'] < last_swing_low:
            trend = 'BEARISH'
            
        if last_swing_high is not None and curr_candle['close'] > last_swing_high:
            trend = 'BULLISH'
            
    return trend

def get_trend(df: pd.DataFrame) -> int:
    trend = find_most_recent_trend(df, max_lookback=50)
    if trend == 'BULLISH': return 1
    if trend == 'BEARISH': return -1
    return 0

def find_5m_fvgs(df: pd.DataFrame) -> list:
    active_fvgs = []
    
    # Iterate up to the second-to-last candle to find FVGs
    for i in range(2, len(df) - 1):
        c1 = df.iloc[i - 2]
        c2 = df.iloc[i - 1]
        c3 = df.iloc[i]
        
        fvg = None
        # Check for new FVGs
        if c3['low'] > c1['high']:
            fvg = {
                'type': 'BULLISH', 'top': c3['low'], 'bottom': c1['high'], 'timestamp': c2['timestamp']
            }
        elif c3['high'] < c1['low']:
            fvg = {
                'type': 'BEARISH', 'top': c1['low'], 'bottom': c3['high'], 'timestamp': c2['timestamp']
            }
            
        if fvg:
            is_invalidated = False
            # Loop through all subsequent rows up to the second-to-last candle
            for j in range(i + 1, len(df) - 1):
                sub_candle = df.iloc[j]
                if fvg['type'] == 'BULLISH':
                    if sub_candle['low'] <= fvg['bottom']:
                        is_invalidated = True
                        break
                elif fvg['type'] == 'BEARISH':
                    if sub_candle['high'] >= fvg['top']:
                        is_invalidated = True
                        break
                        
            if not is_invalidated:
                active_fvgs.append(fvg)
            
    return active_fvgs[-5:]

def check_active_fvgs(df: pd.DataFrame, shared_trend: int, symbol: str) -> tuple[bool, list]:
    fvgs = find_5m_fvgs(df)
    latest_candle = df.iloc[-1]
    
    fvg_data = []
    if not fvgs:
        return False, fvg_data
        
    has_aligned_tap = False
    for fvg in fvgs:
        # 3. Directional FVG Filter
        if shared_trend == 1 and fvg['type'] != 'BULLISH':
            continue
        if shared_trend == -1 and fvg['type'] != 'BEARISH':
            continue
            
        is_tap = False
        is_overrun = False
        
        if fvg['type'] == 'BULLISH':
            if latest_candle['low'] <= fvg['bottom']:
                is_overrun = True
            elif latest_candle['low'] <= fvg['top']:
                is_tap = True
        elif fvg['type'] == 'BEARISH':
            if latest_candle['high'] >= fvg['top']:
                is_overrun = True
            elif latest_candle['high'] >= fvg['bottom']:
                is_tap = True
                
        if is_overrun:
            status = "Discarded (Overrun)"
        elif is_tap:
            status = "TAPPED (Aligned) - 5m FVG Tapped - Ready for 1m Chart Execution"
            has_aligned_tap = True
        else:
            status = "Open (Untouched)"
                
        fvg_data.append({
            "type": fvg['type'],
            "timestamp": str(fvg['timestamp']),
            "gap": f"{fvg['bottom']:.2f} - {fvg['top']:.2f}",
            "status": status
        })
        
    return has_aligned_tap, fvg_data

def check_1m_ifvg_on_latest(df_1m: pd.DataFrame, active_5m_trend: str) -> bool:
    if len(df_1m) < 3:
        return False
        
    latest_candle = df_1m.iloc[-1]
    
    for i in range(2, len(df_1m) - 1):
        c1 = df_1m.iloc[i - 2]
        c3 = df_1m.iloc[i]
        
        if active_5m_trend == 'BULLISH':
            if c3['high'] < c1['low']:  # 1m Bearish FVG
                top = c1['low']
                already_confirmed = False
                for j in range(i + 1, len(df_1m) - 1):
                    if df_1m.iloc[j]['close'] > top:
                        already_confirmed = True
                        break
                if not already_confirmed and latest_candle['close'] > top:
                    return True
                    
        elif active_5m_trend == 'BEARISH':
            if c3['low'] > c1['high']:  # 1m Bullish FVG
                bottom = c1['high']
                already_confirmed = False
                for j in range(i + 1, len(df_1m) - 1):
                    if df_1m.iloc[j]['close'] < bottom:
                        already_confirmed = True
                        break
                if not already_confirmed and latest_candle['close'] < bottom:
                    return True
                    
    return False

def send_telegram_alert(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials missing. Skipping alert.")
        return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error sending Telegram alert: {e}")

def calculate_stop_loss(df_1m: pd.DataFrame, direction: str) -> float:
    n = len(df_1m)
    limit = max(1, n - 15)
    
    for i in range(n - 1, limit, -1):
        c1 = df_1m.iloc[i - 1]
        c2 = df_1m.iloc[i]
        
        if direction == 'LONG':
            if c1['close'] < c1['open'] and c2['close'] > c2['open']:
                return float(min(c1['low'], c2['low']))
        elif direction == 'SHORT':
            if c1['close'] > c1['open'] and c2['close'] < c2['open']:
                return float(max(c1['high'], c2['high']))
                
    if direction == 'LONG':
        return float(df_1m.iloc[-15:]['low'].min())
    else:
        return float(df_1m.iloc[-15:]['high'].max())

def check_1m_entry(spy_1m_df: pd.DataFrame, qqq_1m_df: pd.DataFrame, shared_trend: int, spy_5m_df: pd.DataFrame, qqq_5m_df: pd.DataFrame) -> list:
    alerts = []
    if shared_trend == 0:
        return alerts
        
    active_5m_trend = 'BULLISH' if shared_trend == 1 else 'BEARISH'
    spy_trigger = check_1m_ifvg_on_latest(spy_1m_df, active_5m_trend)
    qqq_trigger = check_1m_ifvg_on_latest(qqq_1m_df, active_5m_trend)
    
    if spy_trigger or qqq_trigger:
        # The Final Safety Check: Recalculate 5m trend immediately
        spy_trend_now = get_trend(spy_5m_df)
        qqq_trend_now = get_trend(qqq_5m_df)
        
        still_aligned = (spy_trend_now == shared_trend) and (qqq_trend_now == shared_trend)
        
        trigger_df = spy_1m_df if spy_trigger else qqq_1m_df
        symbol = "SPY" if spy_trigger else "QQQ"
        timestamp = trigger_df.iloc[-1]['timestamp']
        direction = "LONG" if active_5m_trend == 'BULLISH' else "SHORT"
        
        if still_aligned:
            entry = float(trigger_df.iloc[-1]['close'])
            sl = calculate_stop_loss(trigger_df, direction)
            risk = abs(entry - sl)
            tp = entry + (risk * 4) if direction == "LONG" else entry - (risk * 4)
            
            trade = {
                "id": str(timestamp),
                "asset": symbol,
                "direction": direction,
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "status": "ACTIVE"
            }
            active_trades.append(trade)
            
            msg = f"🟢 EXECUTE TRADE: {direction} at {timestamp} | 1m IFVG Confirmed on {symbol}"
            send_telegram_alert(msg)
            alerts.append(msg)
        else:
            msg = "❌ Trade Cancelled: 5m Trend lost alignment before 1m entry."
            send_telegram_alert(msg)
            alerts.append(msg)
            
    return alerts

def update_active_trades(current_spy_price: float, current_qqq_price: float):
    global active_trades, trade_history
    remaining_trades = []
    completed_messages = []
    
    for trade in active_trades:
        current_price = current_spy_price if trade["asset"] == "SPY" else current_qqq_price
        
        if trade["direction"] == "LONG":
            if current_price <= trade["sl"]:
                trade["status"] = "❌ 1R LOSS"
                trade_history.append(trade)
                completed_messages.append(f"❌ TRADE CLOSED: 1R LOSS on {trade['asset']} {trade['direction']} at {current_price:.2f}")
            elif current_price >= trade["tp"]:
                trade["status"] = "✅ 4R WIN"
                trade_history.append(trade)
                completed_messages.append(f"✅ TRADE CLOSED: 4R WIN on {trade['asset']} {trade['direction']} at {current_price:.2f}")
            else:
                remaining_trades.append(trade)
        else: # SHORT
            if current_price >= trade["sl"]:
                trade["status"] = "❌ 1R LOSS"
                trade_history.append(trade)
                completed_messages.append(f"❌ TRADE CLOSED: 1R LOSS on {trade['asset']} {trade['direction']} at {current_price:.2f}")
            elif current_price <= trade["tp"]:
                trade["status"] = "✅ 4R WIN"
                trade_history.append(trade)
                completed_messages.append(f"✅ TRADE CLOSED: 4R WIN on {trade['asset']} {trade['direction']} at {current_price:.2f}")
            else:
                remaining_trades.append(trade)
                
    active_trades[:] = remaining_trades
    return completed_messages

app = FastAPI()

@app.get("/")
@app.head("/")
async def health_check():
    return {"status": "awake", "message": "Scanner is running 24/7"}

active_connections: list[WebSocket] = []

@app.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        if websocket in active_connections:
            active_connections.remove(websocket)

async def scanner_task():
    send_telegram_alert('🚀 Market Scanner Initialized & Telegram Alerts Active!')
    
    has_alerted_open = False
    last_alerted_trend = 0
    is_currently_tapping = False
    ny_tz = pytz.timezone('America/New_York')

    current_date = None
    trade_executed_today = False
    shutdown_message_sent_today = False

    while True:
        try:
            now_ny = datetime.now(ny_tz)
            ny_time = now_ny.strftime('%H:%M')
            today_date = now_ny.date()
            is_weekend = now_ny.weekday() >= 5
            
            if current_date != today_date:
                current_date = today_date
                trade_executed_today = False
                shutdown_message_sent_today = False
                has_alerted_open = False
                last_alerted_trend = 0
                is_currently_tapping = False

            # 1. Time Gate (NY Session)
            if is_weekend or not ('09:30' <= ny_time < '16:00'):
                if current_date == today_date and not shutdown_message_sent_today and not is_weekend and ny_time >= '16:00':
                    send_telegram_alert('🛑 SYSTEM SHUTDOWN: Market closed. See you tomorrow.')
                    shutdown_message_sent_today = True

                spy_active_fvgs = []
                qqq_active_fvgs = []
                
                payload = {
                    "timestamp": str(datetime.now()),
                    "spy_trend": 0,
                    "qqq_trend": 0,
                    "shared_trend": 0,
                    "spy_active_fvgs": spy_active_fvgs,
                    "qqq_active_fvgs": qqq_active_fvgs,
                    "execution_alerts": [],
                    "active_trades": active_trades,
                    "trade_history": trade_history
                }
                payload_json = json.dumps(payload)
                
                disconnected_clients = []
                for client in active_connections:
                    try:
                        await client.send_text(payload_json)
                    except Exception:
                        disconnected_clients.append(client)
                for client in disconnected_clients:
                    active_connections.remove(client)
                
                has_alerted_open = False

                now = datetime.now()
                seconds_to_sleep = 60 - now.second
                await asyncio.sleep(seconds_to_sleep)
                continue
            
            if not has_alerted_open:
                send_telegram_alert('🔔 NYSE OPEN: Session started, scanning active.')
                has_alerted_open = True

            spy_data, qqq_data, spy_1m_df, qqq_1m_df = fetch_alpaca_data()

            spy_trend = 0
            qqq_trend = 0
            shared_trend = 0
            execution_alerts = []
            spy_active_fvgs = []
            qqq_active_fvgs = []

            if not trade_executed_today:
                # 2. Trend Alignment (Index Correlation)
                spy_trend = get_trend(spy_data)
                qqq_trend = get_trend(qqq_data)
                
                shared_trend = spy_trend if (spy_trend == qqq_trend and spy_trend != 0) else 0
                    
                if shared_trend != 0:
                    if shared_trend != last_alerted_trend:
                        trend_str = "BULLISH" if shared_trend == 1 else "BEARISH"
                        send_telegram_alert(f"✅ SYSTEM ALIGNED: SPY and QQQ are now {trend_str}.")
                        last_alerted_trend = shared_trend

                    spy_tap, spy_active_fvgs = check_active_fvgs(spy_data, shared_trend, "SPY")
                    qqq_tap, qqq_active_fvgs = check_active_fvgs(qqq_data, shared_trend, "QQQ")

                    if spy_tap or qqq_tap:
                        if not is_currently_tapping:
                            send_telegram_alert("🎯 ALIGNED TAP DETECTED: 5m FVG touched. Hunting for 1m Inverse FVG...")
                            is_currently_tapping = True
                        prev_active_count = len(active_trades)
                        execution_alerts = check_1m_entry(spy_1m_df, qqq_1m_df, shared_trend, spy_data, qqq_data)
                        if len(active_trades) > prev_active_count:
                            trade_executed_today = True
                    else:
                        is_currently_tapping = False
                else:
                    last_alerted_trend = 0
                    is_currently_tapping = False

            current_spy_price = float(spy_1m_df.iloc[-1]['close'])
            current_qqq_price = float(qqq_1m_df.iloc[-1]['close'])
            completed_messages = update_active_trades(current_spy_price, current_qqq_price)

            for msg in completed_messages:
                send_telegram_alert(msg)

            if trade_executed_today and not shutdown_message_sent_today and len(active_trades) == 0:
                if len(completed_messages) > 0:
                    send_telegram_alert('🛑 SYSTEM SHUTDOWN: Daily setup completed. System offline until tomorrow.')
                    shutdown_message_sent_today = True

            payload = {
                "timestamp": str(datetime.now()),
                "spy_trend": spy_trend,
                "qqq_trend": qqq_trend,
                "shared_trend": shared_trend,
                "spy_active_fvgs": spy_active_fvgs,
                "qqq_active_fvgs": qqq_active_fvgs,
                "execution_alerts": execution_alerts,
                "active_trades": active_trades,
                "trade_history": trade_history
            }
            
            payload_json = json.dumps(payload)
            
            disconnected_clients = []
            for client in active_connections:
                try:
                    await client.send_text(payload_json)
                except Exception:
                    disconnected_clients.append(client)
                    
            for client in disconnected_clients:
                active_connections.remove(client)
        except Exception as e:
            print(f"Error in scanner loop: {e}")
        
        now = datetime.now()
        seconds_to_sleep = 60 - now.second
        await asyncio.sleep(seconds_to_sleep)

@app.on_event('startup')
async def startup_event():
    asyncio.create_task(scanner_task())