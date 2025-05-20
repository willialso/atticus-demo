# okx_client.py
import websocket
import json
import time
import threading

OKX_WS_URL = "wss://ws.okx.com:8443/ws/v5/public"
okx_btc_price_info = {'bid': None, 'ask': None}

def on_okx_message(ws, message):
    global okx_btc_price_info
    data = json.loads(message)
    if data.get('arg', {}).get('channel') == 'tickers' and data.get('data'):
        ticker_data = data['data'][0]
        okx_btc_price_info['bid'] = float(ticker_data.get('bidPx', 0))
        okx_btc_price_info['ask'] = float(ticker_data.get('askPx', 0))
        # print(f"OKX Update: Bid: {okx_btc_price_info['bid']}, Ask: {okx_btc_price_info['ask']}")
    elif data.get('event') == 'error':
        print(f"OKX WS Error: {data.get('msg')}")

def on_okx_error(ws, error):
    print(f"OKX Error: {error}")

def on_okx_close(ws, close_status_code, close_msg):
    print("OKX WebSocket connection closed")

def on_okx_open(ws):
    print("OKX WebSocket connection opened.")
    subscribe_message = {
        "op": "subscribe",
        "args": [
            {"channel": "tickers", "instId": "BTC-USDT"}
        ]
    }
    ws.send(json.dumps(subscribe_message))

def start_okx_ws():
    ws = websocket.WebSocketApp(OKX_WS_URL,
                              on_open=on_okx_open,
                              on_message=on_okx_message,
                              on_error=on_okx_error,
                              on_close=on_okx_close)
    ws.run_forever()

# okx_thread = threading.Thread(target=start_okx_ws)
# okx_thread.daemon = True
# okx_thread.start()
