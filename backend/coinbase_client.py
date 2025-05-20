# coinbase_client.py
import websocket
import json
import time
import threading

COINBASE_WS_URL = "wss://ws-feed.pro.coinbase.com"
coinbase_btc_price_info = {'bid': None, 'ask': None, 'price': None} # Global to store latest price

def on_coinbase_message(ws, message):
    global coinbase_btc_price_info
    data = json.loads(message)
    if data.get('type') == 'ticker':
        coinbase_btc_price_info['bid'] = float(data.get('best_bid', 0))
        coinbase_btc_price_info['ask'] = float(data.get('best_ask', 0))
        coinbase_btc_price_info['price'] = float(data.get('price', 0)) # Last trade price
        # print(f"Coinbase Update: Bid: {coinbase_btc_price_info['bid']}, Ask: {coinbase_btc_price_info['ask']}, Last: {coinbase_btc_price_info['price']}")

def on_coinbase_error(ws, error):
    print(f"Coinbase Error: {error}")

def on_coinbase_close(ws, close_status_code, close_msg):
    print("Coinbase WebSocket connection closed")
    # Optional: Implement reconnection logic here

def on_coinbase_open(ws):
    print("Coinbase WebSocket connection opened.")
    subscribe_message = {
        "type": "subscribe",
        "product_ids": ["BTC-USD"],
        "channels": ["ticker"] # Ticker channel provides best_bid and best_ask [1, 10]
    }
    ws.send(json.dumps(subscribe_message))

def start_coinbase_ws():
    ws = websocket.WebSocketApp(COINBASE_WS_URL,
                              on_open=on_coinbase_open,
                              on_message=on_coinbase_message,
                              on_error=on_coinbase_error,
                              on_close=on_coinbase_close)
    ws.run_forever()

# To run this client in a separate thread:
# coinbase_thread = threading.Thread(target=start_coinbase_ws)
# coinbase_thread.daemon = True # Allows main program to exit even if thread is still running
# coinbase_thread.start()
