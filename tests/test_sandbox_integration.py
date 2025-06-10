import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from sandbox.api.websocket_extension import SandboxService
from sandbox.config.sandbox_config import SANDBOX_CONFIG

class TestSandboxIntegration(unittest.TestCase):
    def setUp(self):
        self.data_hub = AsyncMock()
        self.pricing_engine = MagicMock()
        self.sandbox_service = SandboxService(self.data_hub, self.pricing_engine)

    async def test_get_current_analysis(self):
        # Mock data_hub.get_current_price to return test market data
        self.data_hub.get_current_price.return_value = 50000.0
        
        # Mock position_manager and risk_engine
        self.sandbox_service.position_manager.get_portfolio_summary.return_value = {"net_position": 1.0}
        self.sandbox_service.risk_engine.analyze_risk.return_value = {"risk_level": "low"}
        
        # Mock hedging_engine to return a test hedging plan
        self.sandbox_service.hedging_engine.devise_hedging_plan.return_value = MagicMock(
            strategy_name="Protective Put",
            confidence_score=0.8,
            options_needed=[{"type": "put", "strike": 50000.0, "expiry_hours": 4.0, "quantity": 1.0, "cost_per_unit": 100.0}],
            reasoning="Protect long position of 1.00 BTC against downside risk."
        )
        
        # Call get_current_analysis
        result = await self.sandbox_service.get_current_analysis()
        
        # Verify the result includes available expiries
        self.assertIn("available_expiries", result)
        self.assertEqual(result["available_expiries"], SANDBOX_CONFIG.DEFAULT_EXPIRY_HOURS)
        
        # Verify the hedging plan is included
        self.assertIn("hedging_plan", result)
        self.assertIsNotNone(result["hedging_plan"])
        
        # Verify other fields are present
        self.assertIn("is_running", result)
        self.assertIn("portfolio_summary", result)
        self.assertIn("risk_analysis", result)
        self.assertIn("current_mark_price", result)

if __name__ == "__main__":
    unittest.main() 