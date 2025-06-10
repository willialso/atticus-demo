import unittest
import asyncio
import json
from fastapi.testclient import TestClient
from backend.api import app
from sandbox.api.websocket_extension import SandboxService
from backend.trade_executor import TradeExecutor
from backend.advanced_pricing_engine import AdvancedPricingEngine
from backend.portfolio_hedger import PortfolioHedger
from backend.volatility_engine import AdvancedVolatilityEngine
from backend.alpha_signals import AlphaSignalGenerator

class TestSandboxTradeExecution(unittest.TestCase):
    def setUp(self):
        """Set up test environment before each test."""
        self.client = TestClient(app)
        
        # Initialize required components
        self.volatility_engine = AdvancedVolatilityEngine()
        self.alpha_signal_generator = AlphaSignalGenerator()
        self.pricing_engine = AdvancedPricingEngine(
            volatility_engine=self.volatility_engine,
            alpha_signal_generator=self.alpha_signal_generator
        )
        self.hedger = PortfolioHedger(pricing_engine=self.pricing_engine)
        self.trade_executor = TradeExecutor(
            pricing_engine=self.pricing_engine,
            hedger=self.hedger
        )
        
        # Create a mock data hub
        class MockDataHub:
            async def get_current_price(self):
                return 50000.0
        
        # Initialize sandbox service
        self.sandbox_service = SandboxService(
            data_hub=MockDataHub(),
            pricing_engine=self.pricing_engine
        )
        
        # Add components to app state
        app.state.sandbox_service = self.sandbox_service
        app.state.trade_executor = self.trade_executor
        app.state.pricing_engine = self.pricing_engine

    def test_execute_sandbox_trade(self):
        """Test the sandbox trade execution endpoint."""
        # Prepare test trade request
        trade_request = {
            "user_id": "test_user",
            "option_type": "call",
            "strike": 50000.0,
            "expiry_minutes": 60,
            "quantity": 1.0,
            "side": "buy"
        }
        
        # Make request to endpoint
        response = self.client.post(
            "/sandbox/trades/execute",
            json=trade_request
        )
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("trade_id", data)
        self.assertIn("status", data)
        self.assertEqual(data["status"], "success")
        self.assertIn("position", data)
        self.assertEqual(data["position"]["symbol"], "BTC-CALL")
        self.assertEqual(data["position"]["size"], 1.0)
        self.assertEqual(data["position"]["side"], "long")
        
        # Verify position details
        position = data["position"]
        self.assertEqual(position["symbol"], "BTC-CALL")
        self.assertEqual(position["size"], 1.0)
        self.assertEqual(position["side"], "long")
        # self.assertEqual(position["strike"], 50000.0)
        
        # Verify portfolio summary
        portfolio = data["portfolio_summary"]
        # self.assertIn("total_positions", portfolio)
        self.assertIn("total_exposure", portfolio)
        self.assertIn("net_position", portfolio)
        self.assertIn("total_pnl", portfolio)
        self.assertIn("accounts", portfolio)
        
        # Verify risk analysis
        risk = data["risk_analysis"]
        self.assertIn("delta_exposure", risk)
        # self.assertIn("gamma", risk)
        # self.assertIn("vega", risk)
        # self.assertIn("theta", risk)

    def test_execute_sandbox_trade_invalid_request(self):
        """Test sandbox trade execution with invalid request."""
        # Test with missing required field
        invalid_request = {
            "user_id": "test_user",
            "option_type": "call",
            "strike": 50000.0,
            # Missing expiry_minutes
            "quantity": 1.0,
            "side": "buy"
        }
        
        response = self.client.post(
            "/sandbox/trades/execute",
            json=invalid_request
        )
        
        self.assertEqual(response.status_code, 422)  # Validation error

    def test_execute_sandbox_trade_invalid_strike(self):
        """Test sandbox trade execution with invalid strike price."""
        # Test with invalid strike price
        invalid_strike_request = {
            "user_id": "test_user",
            "option_type": "call",
            "strike": -50000.0,  # Invalid negative strike
            "expiry_minutes": 60,
            "quantity": 1.0,
            "side": "buy"
        }
        
        response = self.client.post(
            "/sandbox/trades/execute",
            json=invalid_strike_request
        )
        
        self.assertEqual(response.status_code, 400)  # Bad request

    def test_execute_sandbox_trade_invalid_quantity(self):
        """Test sandbox trade execution with invalid quantity."""
        # Test with invalid quantity
        invalid_quantity_request = {
            "user_id": "test_user",
            "option_type": "call",
            "strike": 50000.0,
            "expiry_minutes": 60,
            "quantity": 0,  # Invalid zero quantity
            "side": "buy"
        }
        
        response = self.client.post(
            "/sandbox/trades/execute",
            json=invalid_quantity_request
        )
        
        self.assertEqual(response.status_code, 400)  # Bad request

if __name__ == '__main__':
    unittest.main() 