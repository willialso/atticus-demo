import requests
import json
import websocket
import time
from datetime import datetime

BASE_URL = 'https://atticus-demo.onrender.com'
WS_URL = 'wss://atticus-demo.onrender.com/ws'

def get_valid_strike_and_expiry():
    response = requests.get(f"{BASE_URL}/market/option-chains")
    data = response.json()
    chains = data.get('chains', {})
    for expiry, chain in chains.items():
        calls = chain.get('calls', [])
        if calls:
            return calls[0]['strike'], int(expiry)
    return 110000.0, 120  # fallback

def test_health_check():
    print("\n=== Testing Health Check ===")
    response = requests.get(f"{BASE_URL}/")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.status_code == 200

def test_market_price():
    print("\n=== Testing Market Price ===")
    response = requests.get(f"{BASE_URL}/market/price")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.status_code == 200

def test_option_chains():
    print("\n=== Testing Option Chains ===")
    response = requests.get(f"{BASE_URL}/market/option-chains")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200

def test_black_scholes():
    print("\n=== Testing Black-Scholes ===")
    data = {
        "current_price": 108000.0,
        "strike_price": 110000.0,
        "time_to_expiry_years": 0.1,
        "option_type": "call",
        "risk_free_rate": 0.05,
        "volatility": 0.8
    }
    response = requests.post(f"{BASE_URL}/blackscholes/calculate", json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200

def test_create_user():
    print("\n=== Testing Create User ===")
    data = {
        "user_id": f"test_user_{int(time.time())}",
        "initial_btc_balance": 0.01
    }
    response = requests.post(f"{BASE_URL}/users/create", json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200, response.json().get('user_id')

def test_portfolio(user_id):
    print("\n=== Testing Portfolio ===")
    response = requests.get(f"{BASE_URL}/users/{user_id}/portfolio")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200

def test_execute_trade(user_id, strike, expiry):
    print("\n=== Testing Execute Trade ===")
    data = {
        "user_id": user_id,
        "option_type": "call",
        "strike": strike,
        "expiry_minutes": expiry,
        "quantity": 0.1,
        "side": "buy"
    }
    response = requests.post(f"{BASE_URL}/trades/execute", json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200, response.json().get('position_id')

def test_close_position(user_id, position_id):
    print("\n=== Testing Close Position ===")
    data = {
        "user_id": user_id,
        "position_id": position_id
    }
    response = requests.post(f"{BASE_URL}/positions/close", json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200

def test_sandbox_update_account():
    print("\n=== Testing Sandbox Update Account ===")
    data = {
        "account_id": f"test_account_{int(time.time())}",
        "platform": "test_platform",
        "positions": [
            {
                "symbol": "BTC-USD",
                "size": 0.1,
                "side": "long",
                "entry_price": 108000.0
            }
        ]
    }
    response = requests.post(f"{BASE_URL}/sandbox/update-account", json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200

def test_sandbox_execute_trade():
    print("\n=== Testing Sandbox Execute Trade ===")
    data = {
        "user_id": f"test_user_{int(time.time())}",
        "option_type": "call",
        "strike": 110000.0,
        "expiry_minutes": 120,
        "quantity": 0.1,
        "side": "buy"
    }
    response = requests.post(f"{BASE_URL}/sandbox/trades/execute", json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.status_code == 200

def test_websocket():
    print("\n=== Testing WebSocket Connection ===")
    try:
        ws = websocket.create_connection(WS_URL)
        print("WebSocket connection established")
        test_message = {"type": "ping", "timestamp": datetime.now().isoformat()}
        ws.send(json.dumps(test_message))
        print("Test message sent")
        response = ws.recv()
        print(f"Received: {response}")
        ws.close()
        print("WebSocket connection closed")
        return True
    except Exception as e:
        print(f"WebSocket test failed: {str(e)}")
        return False

def run_all_tests():
    print("Starting comprehensive endpoint tests...")
    health_check_ok = test_health_check()
    market_price_ok = test_market_price()
    option_chains_ok = test_option_chains()
    black_scholes_ok = test_black_scholes()
    create_user_ok, user_id = test_create_user()
    portfolio_ok = False
    execute_trade_ok = False
    close_position_ok = False
    strike, expiry = get_valid_strike_and_expiry()
    if create_user_ok and user_id:
        portfolio_ok = test_portfolio(user_id)
        execute_trade_ok, position_id = test_execute_trade(user_id, strike, expiry)
        if execute_trade_ok and position_id:
            close_position_ok = test_close_position(user_id, position_id)
    sandbox_update_ok = test_sandbox_update_account()
    sandbox_trade_ok = test_sandbox_execute_trade()
    websocket_ok = test_websocket()
    print("\n=== Test Summary ===")
    print(f"Health Check: {'✅' if health_check_ok else '❌'}")
    print(f"Market Price: {'✅' if market_price_ok else '❌'}")
    print(f"Option Chains: {'✅' if option_chains_ok else '❌'}")
    print(f"Black-Scholes: {'✅' if black_scholes_ok else '❌'}")
    print(f"Create User: {'✅' if create_user_ok else '❌'}")
    print(f"Portfolio: {'✅' if portfolio_ok else '❌'}")
    print(f"Execute Trade: {'✅' if execute_trade_ok else '❌'}")
    print(f"Close Position: {'✅' if close_position_ok else '❌'}")
    print(f"Sandbox Update: {'✅' if sandbox_update_ok else '❌'}")
    print(f"Sandbox Trade: {'✅' if sandbox_trade_ok else '❌'}")
    print(f"WebSocket: {'✅' if websocket_ok else '❌'}")

if __name__ == "__main__":
    run_all_tests() 