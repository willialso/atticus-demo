# main_app.py
import time
import threading
from coinbase_client import start_coinbase_ws, coinbase_btc_price_info
from binance_client import start_binance_ws, binance_btc_price_info
from okx_client import start_okx_ws, okx_btc_price_info
from dynamic_pricing import get_option_chain, update_price_history

# --- Start WebSocket Clients in Threads ---
print("Starting WebSocket clients...")
threading.Thread(target=start_coinbase_ws, daemon=True).start()
threading.Thread(target=start_binance_ws, daemon=True).start()
threading.Thread(target=start_okx_ws, daemon=True).start()

# Allow some time for connections to establish and initial data to arrive
print("Waiting for initial price data...")
time.sleep(10)

# --- Main Loop to Generate and Display Option Chain ---
if __name__ == "__main__":
    try:
        while True:
            # Use Coinbase price as the primary source for our platform's underlying price
            platform_btc_price = coinbase_btc_price_info.get('price') # Or (bid+ask)/2

            if platform_btc_price:
                print(f"\n--- Platform BTC Price (Coinbase): ${platform_btc_price:.2f} ---")
                
                # Generate our platform's option chain
                our_option_chain = get_option_chain(platform_btc_price)
                print("Atticus Platform Options (15 min expiry):")
                for option in our_option_chain:
                    print(f"  {option['type'].upper()} @ ${option['strike']:.2f} (Premium: {option['premium']:.8f} BTC) - {option['moneyness']}")

                # Display competitor pricing (conceptual for now)
                if binance_btc_price_info.get('bid'):
                    print(f"\nCompetitor Binance: Bid ${binance_btc_price_info['bid']:.2f}, Ask ${binance_btc_price_info['ask']:.2f}")
                if okx_btc_price_info.get('bid'):
                    print(f"Competitor OKX:      Bid ${okx_btc_price_info['bid']:.2f}, Ask ${okx_btc_price_info['ask']:.2f}")
                
                # Here, you would also calculate premiums for competitor options if they offered identical products
                # For the demo, you might just show their spot bid/ask.
                # For "% less than competitors", you'd need to find a comparable option (same strike, expiry)
                # on their platform, get its premium, and compare. This is complex as products may not align perfectly.
                # A simpler demo approach: "Our ATM Call premium: X, Market Average ATM Call premium: Y (simulated)"

            else:
                print("Waiting for platform BTC price from Coinbase...")

            time.sleep(5) # Update option chain every 5 seconds

    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        # Websocket clients are daemon threads, they will exit when main thread exits.
        # If you had non-daemon threads or explicit ws.close() needs, do them here.
        print("Application terminated.")

