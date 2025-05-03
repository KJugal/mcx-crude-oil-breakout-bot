import os
import time
import requests
import pandas as pd
import plotly.graph_objs as go
import streamlit as st
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve API credentials securely
CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")

# Dhan API base URL
BASE_URL = "https://api.dhan.co"
HEADERS = {
    "access-token": ACCESS_TOKEN,
    "client-id": CLIENT_ID
}

# Constants for trading logic
BREAKOUT_MARGIN = 0.002  # 0.2%
STOP_LOSS_PERCENT = 0.006
TAKE_PROFIT_PERCENT = 0.01
AUTO_MODE = st.sidebar.checkbox("Auto-Trade Mode")

# Helper Functions

def get_crude_token():
    """Get Crude Oil instrument ID and trading symbol."""
    url = f"{BASE_URL}/instruments/mcx"
    res = requests.get(url)
    df = pd.DataFrame(res.json())
    crude_df = df[(df['trading_symbol'].str.contains("CRUDEOIL")) & 
                  (df['instrument_type'] == 'FUT')]
    crude_df = crude_df.sort_values(by='expiry_date')
    return crude_df.iloc[0]['instrument_id'], crude_df.iloc[0]['trading_symbol']

def fetch_candles(instrument_id):
    """Fetch the 5-minute candle data for the instrument."""
    url = f"{BASE_URL}/market/v1/instruments/history"
    params = {
        'instrument_id': instrument_id,
        'exchange_segment': 'MCX',
        'interval': '5m',
        'from_date': (datetime.now().date()).isoformat(),
        'to_date': (datetime.now().date()).isoformat()
    }
    response = requests.get(url, headers=HEADERS, params=params)
    data = response.json()
    df = pd.DataFrame(data['data'])
    df['time'] = pd.to_datetime(df['start_time'])
    df['close'] = df['close_price'].astype(float)
    df['high'] = df['high_price'].astype(float)
    df['low'] = df['low_price'].astype(float)
    df['open'] = df['open_price'].astype(float)
    return df[['time', 'open', 'high', 'low', 'close']]

def detect_breakout(df):
    """Detect if the price has broken out."""
    breakout_threshold = df['high'][-10:].mean() * (1 + BREAKOUT_MARGIN)
    last_close = df['close'].iloc[-1]
    return last_close > breakout_threshold, last_close

def place_order(price, instrument_id, qty=1):
    """Place a buy order with stop loss and take profit."""
    order_url = f"{BASE_URL}/orders"
    sl = round(price * (1 - STOP_LOSS_PERCENT), 1)
    tp = round(price * (1 + TAKE_PROFIT_PERCENT), 1)

    order_payload = {
        "transaction_type": "BUY",
        "exchange_segment": "MCX",
        "product_type": "INTRADAY",
        "order_type": "MARKET",
        "instrument_id": instrument_id,
        "quantity": qty,
        "price": 0,
        "stop_loss": sl,
        "target": tp,
        "validity": "DAY"
    }

    response = requests.post(order_url, json=order_payload, headers=HEADERS)
    return response.json()

# Streamlit App UI

st.title("MCX Crude Oil Breakout Bot (Dhan API)")
st.markdown("**Strategy:** Falling wedge breakout with SL/TP")

instrument_id, trading_symbol = get_crude_token()
st.sidebar.markdown(f"**Tracking:** `{trading_symbol}`")

placeholder = st.empty()
log = st.empty()

while True:
    try:
        df = fetch_candles(instrument_id)

        # Plot candlestick chart
        fig = go.Figure(data=[go.Candlestick(x=df['time'],
                                           open=df['open'], high=df['high'],
                                           low=df['low'], close=df['close'])])
        fig.update_layout(xaxis_rangeslider_visible=False, title="Live Chart")
        placeholder.plotly_chart(fig, use_container_width=True)

        breakout, last_price = detect_breakout(df)

        if breakout:
            msg = f"\n**Breakout detected!** @ ₹{last_price}" \
                  f"\nPlacing order..." if AUTO_MODE else "\nManual mode active."
            log.markdown(msg)

            if AUTO_MODE:
                order_resp = place_order(last_price, instrument_id)
                log.json(order_resp)
                time.sleep(3600)  # Prevent retrading for 1 hour
        else:
            log.markdown(f"{datetime.now().strftime('%H:%M:%S')} - No breakout")

        time.sleep(60)

    except Exception as e:
        log.error(f"Error: {e}")
        time.sleep(60)
