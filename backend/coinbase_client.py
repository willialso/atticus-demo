# backend/coinbase_client.py
import websocket
import json
import time
import threading
from backend import config # Assuming your config.py has COINBASE_PRODUCT_ID
from backend.utils import setup_logger # Using your logger

logger = setup_logger(__name__)

# Using the URL you confirmed worked before.
# Let's make it configurable or use the one that you know works.
# config.py should have COINBASE_WS_URL = "wss://ws-feed.exchange.coinbase.com" if this is preferred
# For now, let's hardcode the one you said worked:
COINBASE_WS_URL_EFFECTIVE = "wss://ws-feed.exchange.coinbase.com" # Changed from config.COINBASE_WS_URL for this test

coinbase_btc_price_info = {'bid': None, 'ask': None, 'price': None, 'last_update_time': None}

def on_coinbase_message(ws, message):
    global coinbase_btc_price_info
    try:
        data = json.loads(message)
        # The ticker message from ws-feed.exchange.coinbase.com might differ slightly
        # from ws-feed.pro.coinbase.com. Adjust parsing as needed.
        # Common fields are 'type', 'product_id', 'price', 'best_bid', 'best_ask'
        if data.get("type") == "ticker" and data.get("product_id") == config.COINBASE_PRODUCT_ID:
            if "price" in data:
                coinbase_btc_price_info['price'] = float(data["price"])
            if "best_bid" in data:
                coinbase_btc_price_info['bid'] = float(data["best_bid"])
            if "best_ask" in data:
                coinbase_btc_price_info['ask'] = float(data["best_ask"])
            coinbase_btc_price_info['last_update_time'] = time.time()
            # logger.debug(f"Coinbase Update: Bid: {coinbase_btc_price_info['bid']}, Ask: {coinbase_btc_price_info['ask']}, Last: {coinbase_btc_price_info['price']}")
    except Exception as e:
        logger.error(f"Coinbase: Error processing message: {message} - {e}", exc_info=True)

def on_coinbase_error(ws, error):
    # This often prints the handshake error like the 520 you saw
    logger.error(f"Coinbase WebSocket error: {error}")

def on_coinbase_close(ws, close_status_code, close_msg):
    logger.info(f"Coinbase WebSocket closed: {close_status_code} {close_msg}")

def on_coinbase_open(ws_app): # Note: websocket-client passes the WebSocketApp instance
    logger.info(f"Coinbase WebSocket connection opened to {COINBASE_WS_URL_EFFECTIVE}")
    subscribe_message = {
        "type": "subscribe",
        "product_ids": [config.COINBASE_PRODUCT_ID],
        # Using the nested channel structure you had
        "channels": [{"name": "ticker", "product_ids": [config.COINBASE_PRODUCT_ID]}]
    }
    # Alternative simpler structure often used with ws-feed.pro.coinbase.com
    # subscribe_message = {
    #     "type": "subscribe",
    #     "product_ids": [config.COINBASE_PRODUCT_ID],
    #     "channels": ["ticker"]
    # }
    try:
        ws_app.send(json.dumps(subscribe_message))
        logger.info(f"Sent subscription message to Coinbase ticker channel for {config.COINBASE_PRODUCT_ID}")
    except Exception as e:
        logger.error(f"Coinbase: Error sending subscription message: {e}", exc_info=True)

def start_coinbase_ws():
    logger.info(f"Attempting to connect to Coinbase WebSocket at {COINBASE_WS_URL_EFFECTIVE}")
    while True: # Keep trying to connect
        try:
            ws = websocket.WebSocketApp(COINBASE_WS_URL_EFFECTIVE,
                                        on_open=on_coinbase_open,
                                        on_message=on_coinbase_message,
                                        on_error=on_coinbase_error,
                                        on_close=on_coinbase_close)
            ws.run_forever(ping_interval=30, ping_timeout=10) # Added ping to keep alive
        except Exception as e:
            logger.error(f"Coinbase: Exception in WebSocket run_forever loop: {e}", exc_info=True)
        
        logger.info("Coinbase: Reconnecting WebSocket in 10 seconds...")
        time.sleep(10)

# To test this file directly:
if __name__ == '__main__':
    # Setup basic logging for direct test
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # Ensure config is loaded if you rely on it for PRODUCT_ID
    # For direct test, you might hardcode it or ensure config.py is found
    if not hasattr(config, 'COINBASE_PRODUCT_ID'):
        class MockConfig: COINBASE_PRODUCT_ID = "BTC-USD"
        config = MockConfig
        
    start_coinbase_ws()
