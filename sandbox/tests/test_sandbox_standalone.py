import asyncio
import logging
import pytest
import sys
import os

# Ensure the project root is in the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from sandbox.api.websocket_extension import SandboxWebSocketExtension

logging.basicConfig(level=logging.INFO)

@pytest.mark.asyncio
async def test_full_sandbox_workflow():
    """Tests the full end-to-end sandbox workflow on the backend."""
    print("\n--- Testing Sandbox Workflow ---")
    
    # 1. Initialize the sandbox extension
    extension = SandboxWebSocketExtension()
    assert extension.position_manager.accounts, "Should load accounts on init"
    print("✅ Sandbox extension initialized and accounts loaded.")

    # 2. Simulate a market data update from the demo's websocket
    btc_price = 110000.0
    volatility = 0.95
    extension.update_market_data(btc_price, volatility)
    assert extension.latest_market_data["btc_price"] == btc_price
    print(f"✅ Market data updated: BTC Price ${btc_price}, Volatility {volatility*100}%")

    # 3. Manually trigger updates that the loop would perform
    extension.position_manager.update_pnl(btc_price)
    print("✅ P&L updated based on new market price.")
    
    # Check if P&L calculation is reasonable
    summary_before_hedge = extension.position_manager.get_portfolio_summary()
    assert summary_before_hedge['total_pnl'] != 0
    print(f"Portfolio PnL: ${summary_before_hedge['total_pnl']:.2f}")

    # 4. Analyze risk
    risk_analysis = extension.risk_engine.analyze_risk()
    assert 'delta_exposure' in risk_analysis
    print(f"✅ Risk analysis performed. Portfolio Delta: {risk_analysis['delta_exposure']:.2f}")

    # 5. Devise a hedging plan
    hedging_plan = extension.hedging_engine.devise_hedging_plan(
        extension.latest_market_data,
        summary_before_hedge
    )
    assert hedging_plan is not None, "Hedging engine should recommend a strategy"
    print(f"✅ Hedging plan devised: Recommends '{hedging_plan.strategy_name}'")
    print(f"   Reason: {hedging_plan.reasoning}")

    # 6. Get data for frontend
    frontend_data = extension.get_sandbox_data_for_frontend()
    assert frontend_data['portfolio_summary']['total_exposure'] > 0
    assert frontend_data['hedging_plan'] is not None
    print("✅ Data packet for frontend generated successfully.")
    
    print("\n--- Sandbox Workflow Test Passed ---")

# To run this test: pytest sandbox/tests/test_sandbox_workflow.py
