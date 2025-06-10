import unittest
from fastapi.testclient import TestClient
from backend.api import app
from backend import config
import json
import time

class TestAPIEndpoints(unittest.TestCase):
    def setUp(self):
        """Set up test environment before each test."""
        self.client = TestClient(app)
        
        # Initialize test data
        self.test_user = "test_user_1"
        self.test_trade = {
            "user_id": self.test_user,
            "option_type": "call",
            "strike": 50000.0,
            "expiry_minutes": 120,  # Using valid expiry from config
            "quantity": 1.0,
            "side": "buy"
        }
        
        # Mock market data
        self.mock_price = 50000.0
        self.mock_volatility = 0.25

    def test_health_check(self):
        """Test the health check endpoint."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("version", data)

    def test_market_price(self):
        """Test the market price endpoint."""
        response = self.client.get("/market/price")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("price", data)
        self.assertIn("timestamp", data)
        self.assertIn("exchange_status", data)

    def test_volatility_surface(self):
        """Test the volatility surface endpoint."""
        response = self.client.get("/market/volatility-surface")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Check response structure
        self.assertIn("volatility_metrics", data)
        self.assertIn("volatility_surface", data)
        self.assertIn("timestamp", data)
        
        # Check volatility metrics
        metrics = data["volatility_metrics"]
        self.assertIn("current_volatility", metrics)
        self.assertIn("historical_volatility", metrics)
        self.assertIn("implied_volatility", metrics)
        
        # Check volatility surface
        surface = data["volatility_surface"]
        for expiry, chain_data in surface.items():
            self.assertIn("volatility_used", chain_data)
            self.assertIn("strikes_and_ivs", chain_data)
            
            # Check strikes and IVs
            for strike_data in chain_data["strikes_and_ivs"]:
                self.assertIn("strike", strike_data)
                self.assertIn("implied_vol", strike_data)
                self.assertIn("option_type", strike_data)
                self.assertIn("moneyness", strike_data)

    def test_option_chains(self):
        """Test the option chains endpoint."""
        # Test with specific expiry
        response = self.client.get("/market/option-chains?expiry_minutes=120")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("chains", data)
        self.assertIn("120", data["chains"])
        
        # Test without expiry (should return all chains)
        response = self.client.get("/market/option-chains")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("chains", data)
        for expiry in config.AVAILABLE_EXPIRIES_MINUTES:
            self.assertIn(str(expiry), data["chains"])

    def test_portfolio_analysis(self):
        """Test the portfolio analysis endpoint."""
        # Test risk analysis
        response = self.client.get(f"/users/{self.test_user}/portfolio/analysis?analysis_type=risk")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["user_id"], self.test_user)
        self.assertEqual(data["analysis_type"], "risk")
        self.assertIn("analysis", data)
        risk_analysis = data["analysis"]
        self.assertIn("net_delta", risk_analysis)
        self.assertIn("total_exposure", risk_analysis)
        self.assertIn("var_95", risk_analysis)
        self.assertIn("max_loss", risk_analysis)
        self.assertIn("risk_score", risk_analysis)
        
        # Test performance analysis
        response = self.client.get(f"/users/{self.test_user}/portfolio/analysis?analysis_type=performance")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["analysis_type"], "performance")
        perf_analysis = data["analysis"]
        self.assertIn("total_return", perf_analysis)
        self.assertIn("roi", perf_analysis)
        self.assertIn("sharpe_ratio", perf_analysis)
        self.assertIn("win_rate", perf_analysis)
        self.assertIn("avg_trade_duration", perf_analysis)
        
        # Test Greeks analysis
        response = self.client.get(f"/users/{self.test_user}/portfolio/analysis?analysis_type=greeks")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["analysis_type"], "greeks")
        greeks_analysis = data["analysis"]
        self.assertIn("total_delta", greeks_analysis)
        self.assertIn("total_gamma", greeks_analysis)
        self.assertIn("total_theta", greeks_analysis)
        self.assertIn("total_vega", greeks_analysis)
        self.assertIn("delta_hedging_recommendation", greeks_analysis)

    def test_sandbox_trade_execution(self):
        """Test the sandbox trade execution endpoint."""
        # Test valid trade
        response = self.client.post("/sandbox/trades/execute", json=self.test_trade)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("trade_id", data)
        self.assertIn("result", data)
        
        # Test invalid trade (negative quantity)
        invalid_trade = self.test_trade.copy()
        invalid_trade["quantity"] = -1.0
        response = self.client.post("/sandbox/trades/execute", json=invalid_trade)
        self.assertEqual(response.status_code, 400)
        
        # Test invalid trade (invalid expiry)
        invalid_trade = self.test_trade.copy()
        invalid_trade["expiry_minutes"] = 999  # Invalid expiry
        response = self.client.post("/sandbox/trades/execute", json=invalid_trade)
        self.assertEqual(response.status_code, 400)
        
        # Test invalid trade (missing required field)
        invalid_trade = self.test_trade.copy()
        del invalid_trade["strike"]
        response = self.client.post("/sandbox/trades/execute", json=invalid_trade)
        self.assertEqual(response.status_code, 422)  # Validation error

    def test_error_handling(self):
        """Test error handling for various scenarios."""
        # Test invalid analysis type
        response = self.client.get(f"/users/{self.test_user}/portfolio/analysis?analysis_type=invalid")
        self.assertEqual(response.status_code, 400)
        
        # Test non-existent user
        response = self.client.get("/users/nonexistent_user/portfolio/analysis")
        self.assertEqual(response.status_code, 404)
        
        # Test invalid expiry in option chains
        response = self.client.get("/market/option-chains?expiry_minutes=999")
        self.assertEqual(response.status_code, 400)

if __name__ == '__main__':
    unittest.main() 