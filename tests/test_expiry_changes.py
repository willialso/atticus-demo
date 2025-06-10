import unittest
from backend import config
from backend.advanced_pricing_engine import AdvancedPricingEngine
from backend.volatility_engine import AdvancedVolatilityEngine
from backend.alpha_signals import AlphaSignalGenerator
import time

class TestExpiryChanges(unittest.TestCase):
    def setUp(self):
        # Initialize dependencies
        self.vol_engine = AdvancedVolatilityEngine()
        self.alpha_generator = AlphaSignalGenerator()
        
        # Initialize pricing engine with dependencies
        self.pricing_engine = AdvancedPricingEngine(
            volatility_engine=self.vol_engine,
            alpha_signal_generator=self.alpha_generator
        )
        
        # Set a test price
        self.test_price = 50000.0
        self.pricing_engine.current_price = self.test_price
        self.vol_engine.update_price(self.test_price)

    def test_expiry_configurations(self):
        """Test that expiry configurations are correctly updated"""
        # Test available expiries
        self.assertEqual(config.AVAILABLE_EXPIRIES_MINUTES, [120, 240, 480, 720])
        
        # Test expiry labels
        expected_labels = {
            120: "2-Hour",
            240: "4-Hour",
            480: "8-Hour",
            720: "12-Hour"
        }
        self.assertEqual(config.EXPIRY_LABELS, expected_labels)
        
        # Test strike ranges
        expected_strike_ranges = {
            120: {"num_itm": 7, "num_otm": 7, "step_pct": 0.015},
            240: {"num_itm": 5, "num_otm": 5, "step_pct": 0.02},
            480: {"num_itm": 5, "num_otm": 5, "step_pct": 0.03},
            720: {"num_itm": 4, "num_otm": 4, "step_pct": 0.04}
        }
        self.assertEqual(config.STRIKE_RANGES_BY_EXPIRY, expected_strike_ranges)
        
        # Test volatility adjustments
        self.assertEqual(config.VOLATILITY_SHORT_EXPIRY_ADJUSTMENTS, {120: 1.025})

    def test_strike_generation(self):
        """Test that strike generation works correctly for new expiries"""
        for expiry in config.AVAILABLE_EXPIRIES_MINUTES:
            strikes = self.pricing_engine.generate_strikes_for_expiry(expiry)
            self.assertIsNotNone(strikes)
            self.assertGreater(len(strikes), 0)
            
            # Verify strike spacing
            strike_params = config.STRIKE_RANGES_BY_EXPIRY[expiry]
            expected_strikes = strike_params["num_itm"] + strike_params["num_otm"] + 1  # +1 for ATM
            self.assertEqual(len(strikes), expected_strikes)
            
            # Verify strike spacing is within expected range
            for i in range(len(strikes)-1):
                spacing = abs(strikes[i+1] - strikes[i]) / self.test_price
                self.assertGreaterEqual(spacing, strike_params["step_pct"] * 0.9)  # Allow 10% tolerance

    def test_volatility_calculations(self):
        """Test that volatility calculations work correctly for new expiries"""
        for expiry in config.AVAILABLE_EXPIRIES_MINUTES:
            # Test ATM volatility
            atm_vol = self.vol_engine.get_expiry_adjusted_volatility(
                expiry_minutes=expiry,
                strike_price=self.test_price,
                underlying_price=self.test_price
            )
            self.assertGreaterEqual(atm_vol, config.MIN_VOLATILITY)
            self.assertLessEqual(atm_vol, config.MAX_VOLATILITY)
            
            # Test OTM volatility (higher strike)
            otm_strike = self.test_price * 1.1
            otm_vol = self.vol_engine.get_expiry_adjusted_volatility(
                expiry_minutes=expiry,
                strike_price=otm_strike,
                underlying_price=self.test_price
            )
            self.assertGreaterEqual(otm_vol, config.MIN_VOLATILITY)
            self.assertLessEqual(otm_vol, config.MAX_VOLATILITY)

    def test_option_chain_generation(self):
        """Test that option chains are generated correctly for new expiries"""
        for expiry in config.AVAILABLE_EXPIRIES_MINUTES:
            chain = self.pricing_engine.generate_option_chain(expiry)
            self.assertIsNotNone(chain)
            
            # Verify chain structure
            self.assertEqual(chain.expiry_minutes, expiry)
            self.assertEqual(chain.expiry_label, config.EXPIRY_LABELS[expiry])
            
            # Verify calls and puts
            self.assertGreater(len(chain.calls), 0)
            self.assertGreater(len(chain.puts), 0)
            
            # Verify strike coverage
            all_strikes = set()
            for call in chain.calls:
                all_strikes.add(call.strike)
            for put in chain.puts:
                all_strikes.add(put.strike)
            
            expected_strikes = self.pricing_engine.generate_strikes_for_expiry(expiry)
            self.assertEqual(set(expected_strikes), all_strikes)

if __name__ == '__main__':
    unittest.main() 