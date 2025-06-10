import asyncio
import logging
import pytest
import sys
import os

# Ensure the project root is in the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from sandbox.api.websocket_extension import SandboxService

logging.basicConfig(level=logging.INFO)

@pytest.mark.asyncio
async def test_full_sandbox_workflow():
    """Tests the full end-to-end sandbox workflow on the backend."""
    print("\n--- Testing Sandbox Workflow ---")
    
    # Mock objects for data_hub and pricing_engine
    class MockDataHub:
        def get_current_price(self):
            return 110000.0
    class MockPricingEngine:
        current_volatility = 0.95
        def generate_option_chain(self, expiry):
            return None
    
    # 1. Initialize the sandbox extension
    extension = SandboxService(MockDataHub(), MockPricingEngine())
    assert hasattr(extension.position_manager, 'accounts'), "Should load accounts on init"
    print("✅ Sandbox extension initialized and accounts loaded.")

    # 2. Get current analysis (hedging, risk, portfolio)
    analysis = await extension.get_current_analysis()
    assert analysis["current_mark_price"] == 110000.0, "Should reflect mock price"
    assert "hedging_plan" in analysis and analysis["hedging_plan"] is not None, "Hedging plan should be present"
    assert "risk_analysis" in analysis and analysis["risk_analysis"] is not None, "Risk analysis should be present"
    print(f"✅ Analysis: Hedging plan: {analysis['hedging_plan']}, Risk: {analysis['risk_analysis']}")

    print("\n--- Sandbox Workflow Test Passed ---")

# To run this test: pytest sandbox/tests/test_sandbox_workflow.py
