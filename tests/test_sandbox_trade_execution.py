import pytest
from fastapi.testclient import TestClient
from backend.api import app
from backend.volatility_engine import AdvancedVolatilityEngine
from backend.alpha_signals import AlphaSignalGenerator
from backend.advanced_pricing_engine import AdvancedPricingEngine
from backend.portfolio_hedger import PortfolioHedger
from backend.trade_executor import TradeExecutor
from sandbox.api.websocket_extension import SandboxService
import os

# Test-specific mock classes - these will never be used in production
class TestDataHub:
    """Mock data hub for testing only. Never used in production."""
    def __init__(self):
        self.is_running = True
        self.current_price = 50000.0
        self.last_update = None
        self.connected = True
        
    def get_current_price(self):
        return self.current_price
        
    def start(self):
        self.is_running = True
        
    def stop(self):
        self.is_running = False
        
    def is_connected(self):
        return self.connected
        
    def get_last_update(self):
        return self.last_update
        
    def update_price(self, price):
        self.current_price = price
        self.last_update = None

class TestSandboxTradeExecution:
    @pytest.fixture(autouse=True)
    def setup_test_environment(self):
        """Set up test environment before each test."""
        # Set test environment variables
        os.environ["ATTICUS_DEMO_MODE"] = "true"
        os.environ["ATTICUS_CORS_ORIGINS"] = "http://localhost:3000"
        
        self.client = TestClient(app)
        
        # Use test-specific mock data hub
        self.test_data_hub = TestDataHub()
        
        # Initialize required components
        self.volatility_engine = AdvancedVolatilityEngine()
        self.alpha_signal_generator = AlphaSignalGenerator()
        self.pricing_engine = AdvancedPricingEngine(
            volatility_engine=self.volatility_engine,
            alpha_signal_generator=self.alpha_signal_generator
        )
        
        # Initialize pricing engine with current price
        current_price = self.test_data_hub.get_current_price()
        self.pricing_engine.current_price = current_price
        self.pricing_engine.current_volatility = 0.25  # Set a default volatility
        
        self.hedger = PortfolioHedger(pricing_engine=self.pricing_engine)
        self.trade_executor = TradeExecutor(
            pricing_engine=self.pricing_engine,
            hedger=self.hedger
        )
        
        # Initialize sandbox service with test data hub
        self.sandbox_service = SandboxService(
            data_hub=self.test_data_hub,
            pricing_engine=self.pricing_engine,
            trade_executor=self.trade_executor
        )
        self.sandbox_service.start()
        
        # Add components to app state
        app.state.sandbox_service = self.sandbox_service
        app.state.trade_executor = self.trade_executor
        app.state.pricing_engine = self.pricing_engine
        app.state.data_feed_manager = self.test_data_hub
        
        yield
        
        # Cleanup after each test
        if hasattr(self, 'sandbox_service'):
            self.sandbox_service.stop()
        if hasattr(self, 'test_data_hub'):
            self.test_data_hub.stop()

    def test_execute_sandbox_trade(self):
        """Test the sandbox trade execution endpoint."""
        # Prepare test trade request
        trade_request = {
            "user_id": "test_user",
            "option_type": "call",
            "strike": 50000.0,
            "expiry_minutes": 120,
            "quantity": 1.0,
            "side": "buy"
        }
        
        # Make request to endpoint
        response = self.client.post(
            "/sandbox/trades/execute",
            json=trade_request
        )
        
        # Print response body if not 200
        if response.status_code != 200:
            print("Response status:", response.status_code)
            print("Response body:", response.text)
        
        # Verify response
        assert response.status_code == 200
        response_data = response.json()
        assert "trade_id" in response_data
        assert "status" in response_data
        assert response_data["status"] == "success"

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
        
        assert response.status_code == 400  # Bad request
        response_data = response.json()
        assert "detail" in response_data
        assert "quantity" in str(response_data["detail"]).lower()

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
        
        assert response.status_code == 400  # Bad request
        response_data = response.json()
        assert "detail" in response_data
        assert "strike" in str(response_data["detail"]).lower()

    def test_execute_sandbox_trade_invalid_request(self):
        """Test sandbox trade execution with invalid request format."""
        # Test with missing required fields
        invalid_request = {
            "user_id": "test_user",
            "option_type": "call"
            # Missing required fields
        }
        
        response = self.client.post(
            "/sandbox/trades/execute",
            json=invalid_request
        )
        
        assert response.status_code == 422  # Validation error
        response_data = response.json()
        assert "detail" in response_data 