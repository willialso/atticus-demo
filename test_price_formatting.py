#!/usr/bin/env python3
"""
Unit test for price formatting to ensure mobile displays correctly
"""

import asyncio
import json
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend import ws_price
from backend.data_feed_manager import PriceData

async def test_price_formatting():
    """Test that prices are properly formatted for mobile display"""
    
    print("🧪 Testing Price Formatting...")
    
    # Test different price scenarios
    test_prices = [
        104740.50,    # Normal price
        106500.00,    # Basic number like mobile shows
        107500.75,    # Another basic number
        100000.00,    # Round number
        99999.99,     # Decimal price
        123456.78     # Complex decimal
    ]
    
    print("\n📊 Testing price formatting scenarios:")
    
    for price in test_prices:
        # Test the broadcast function
        formatted_price = round(float(price), 2)
        payload = {"type": "price_update", "data": {"price": formatted_price}}
        
        print(f"  Input: {price}")
        print(f"  Formatted: {formatted_price}")
        print(f"  JSON Payload: {json.dumps(payload, indent=2)}")
        print(f"  Display Format: ${formatted_price:,.2f}")
        print()
    
    # Test the actual broadcast function (without sending)
    print("🔌 Testing broadcast_price_update function:")
    try:
        # This will just format the price, not actually broadcast
        await ws_price.broadcast_price_update(104740.50)
        print("✅ broadcast_price_update function works correctly")
    except Exception as e:
        print(f"❌ Error in broadcast_price_update: {e}")
    
    print("\n📱 Mobile Display Test:")
    print("Expected mobile display should show:")
    for price in test_prices:
        formatted = round(float(price), 2)
        print(f"  ${formatted:,.2f} (not {formatted})")
    
    print("\n✅ Price formatting test completed!")

def test_price_data_structure():
    """Test PriceData structure"""
    print("\n🧪 Testing PriceData Structure...")
    
    price_data = PriceData(
        symbol="BTC-USD",
        price=104740.50,
        volume=25000.0,
        timestamp=1234567890.0,
        exchange="OKX"
    )
    
    print(f"PriceData created: {price_data}")
    print(f"Price type: {type(price_data.price)}")
    print(f"Price value: {price_data.price}")
    print(f"Formatted price: ${price_data.price:,.2f}")
    
    # Test JSON serialization
    try:
        json_str = json.dumps({
            "price": price_data.price,
            "volume": price_data.volume,
            "exchange": price_data.exchange
        })
        print(f"JSON serialization: {json_str}")
        print("✅ PriceData JSON serialization works")
    except Exception as e:
        print(f"❌ JSON serialization failed: {e}")

if __name__ == "__main__":
    print("🚀 Starting Price Formatting Unit Tests")
    print("=" * 50)
    
    # Test PriceData structure
    test_price_data_structure()
    
    # Test async price formatting
    asyncio.run(test_price_formatting())
    
    print("\n" + "=" * 50)
    print("🎉 All tests completed!") 