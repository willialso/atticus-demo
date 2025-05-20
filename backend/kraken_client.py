# backend/kraken_client.py
import websocket
import json
import time
import threading
from backend import config # Assuming config.py for KRAKEN_PAIRS or similar
from backend.utils import setup_logger

logger = setup_logger(__name__)

KRAKEN_WS_URL = "wss://ws.kraken.com/v2" # WebSocket API v2 endpoint [1]
KRAKEN_TRADING_PAIR = "BTC/USD" # Common representation, Kraken might use XBT/USD [1]

kraken_btc_price_info = {'bid': None, 'ask': None, 'price': None, 'last_update_time': None}

def on_kraken_message(ws, message):
    global kraken_btc_price_info
    try:
        data = json.loads(message)
        # logger.debug(f"Kraken message: {data}")

        if isinstance(data, dict) and data.get("channel") == "ticker" and "data" in data:
            payload = data["data"][0] # Ticker data is usually in a list
            # Expected payload fields for ticker: ask, bid, last_trade [1]
            # Kraken uses "a" for ask array, "b" for bid array, "c" for last trade array
            # We need the price from these arrays (first element)
            if "ask" in payload: #Kraken V2 Spot uses full names
                kraken_btc_price_info['ask'] = float(payload["ask"])
            if "bid" in payload:
                kraken_btc_price_info['bid'] = float(payload["bid"])
            if "last_trade" in payload and "price" in payload["last_trade"]: # Check if last_trade and price within it exists
                 kraken_btc_price_info['price'] = float(payload["last_trade"]["price"])
            elif "last" in payload: # Some ticker streams might use 'last'
                 kraken_btc_price_info['price'] = float(payload["last"])


            kraken_btc_price_info['last_update_time'] = time.time()
            # logger.debug(f"Kraken Update: Bid: {kraken_btc_price_info['bid']}, Ask: {kraken_btc_price_info['ask']}, Last: {kraken_btc_price_info['price']}")
        
        elif isinstance(data, dict) and data.get("method") == "subscribe":
            if data.get("success", False):
                logger.info(f"Kraken: Successfully subscribed to {data.get('result', {}).get('channel')}")
            else:
                logger.error(f"Kraken: Subscription failed: {data.get('error')}")

    except Exception as e:
        logger.error(f"Kraken: Error processing message: {message} - {e}", exc_info=True)

def on_kraken_error(ws, error):
    logger.error(f"Kraken WebSocket error: {error}")

def on_kraken_close(ws, close_status_code, close_msg):
    logger.info(f"Kraken WebSocket closed: {close_status_code} {close_msg}")

def on_kraken_open(ws_app):
    logger.info(f"Kraken WebSocket connection opened to {KRAKEN_WS_URL}")
    subscribe_message = {
        "method": "subscribe",
        "params": {
            "channel": "ticker",
            "symbol": [KRAKEN_TRADING_PAIR], # Use the pair format Kraken expects e.g. "XBT/USD" or "BTC/USD"
            # "snapshot": True # Optional: request initial snapshot
        },
        # "req_id": int(time.time()) # Optional request ID
    }
    try:
        ws_app.send(json.dumps(subscribe_message))
        logger.info(f"Sent subscription message to Kraken ticker channel for {KRAKEN_TRADING_PAIR}")
    except Exception as e:
        logger.error(f"Kraken: Error sending subscription message: {e}", exc_info=True)

def start_kraken_ws():
    logger.info(f"Attempting to connect to Kraken WebSocket at {KRAKEN_WS_URL}")
    while True:
        try:
            # For Kraken, sometimes disabling SSL verification can help with certain proxies/networks,
            # but it's less secure. Try without first. sslopt={"cert_reqs": ssl.CERT_NONE}
            ws = websocket.WebSocketApp(KRAKEN_WS_URL,
                                        on_open=on_kraken_open,
                                        on_message=on_kraken_message,
                                        on_error=on_kraken_error,
                                        on_close=on_kraken_close)
            ws.run_forever(ping_interval=20, ping_timeout=10) # Kraken recommends pings
        except Exception as e:
            logger.error(f"Kraken: Exception in WebSocket run_forever loop: {e}", exc_info=True)
        
        logger.info("Kraken: Reconnecting WebSocket in 10 seconds...")
        time.sleep(10)

# To test this file directly:
if __name__ == '__main__':
    import logging # For direct test
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    start_kraken_ws()
