# binance_client.py
import websocket
import json
import time
import threading

BINANCE_WS_URL = "wss://stream.binance.com:9443/ws/btcusdt@bookTicker" # For BTC/USDT best bid/ask
binance_btc_price_info = {'bid': None, 'ask': None}

def on_binance_message(ws, message):
    global binance_btc_price_info
    data = json.loads(message)
    # Binance bookTicker structure: {'u': updateId, 's': symbol, 'b': bestBidPrice, 'B': bestBidQty, 'a': bestAskPrice, 'A': bestAskQty}
    binance_btc_price_info['bid'] = float(data.get('b', 0))
    binance_btc_price_info['ask'] = float(data.get('a', 0))
    # print(f"Binance Update: Bid: {binance_btc_price_info['bid']}, Ask: {binance_btc_price_info['ask']}")

def on_binance_error(ws, error):
    print(f"Binance Error: {error}")

def on_binance_close(ws, close_status_code, close_msg):
    print("Binance WebSocket connection closed")

def on_binance_open(ws):
    print("Binance WebSocket connection opened.")
    # No explicit subscribe message needed for this specific stream URL

def start_binance_ws():
    ws = websocket.WebSocketApp(BINANCE_WS_URL,
                              on_open=on_binance_open,
                              on_message=on_binance_message,
                              on_error=on_binance_error,
                              on_close=on_binance_close)
    ws.run_forever()

# binance_thread = threading.Thread(target=start_binance_ws)
# binance_thread.daemon = True
# binance_thread.start()
