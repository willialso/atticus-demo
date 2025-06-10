import unittest
import requests
import json
import time

class TestSandboxEndpoints(unittest.TestCase):
    def setUp(self):
        self.base_url = 'http://localhost:8000'
        self.test_account = {
            'account_id': 'test_user',
            'platform': 'sandbox',
            'positions': []
        }
        self.test_trade = {
            'user_id': 'test_user',
            'option_type': 'call',
            'strike': 50000.0,
            'expiry_minutes': 60,
            'quantity': 1.0,
            'side': 'buy',
            'symbol': 'BTC-CALL'
        }

    def test_update_account(self):
        """Test updating a sandbox account."""
        response = requests.post(
            f'{self.base_url}/sandbox/update-account',
            json=self.test_account
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('message', data)

    def test_execute_trade(self):
        """Test executing a sandbox trade."""
        # First update the account
        requests.post(
            f'{self.base_url}/sandbox/update-account',
            json=self.test_account
        )
        
        # Then execute the trade
        response = requests.post(
            f'{self.base_url}/sandbox/trades/execute',
            json=self.test_trade
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('trade_id', data)
        self.assertIn('position', data)
        self.assertIn('portfolio_summary', data)
        self.assertIn('risk_analysis', data)
        self.assertIn('hedging_plan', data)

if __name__ == '__main__':
    unittest.main() 