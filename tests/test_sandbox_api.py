import unittest
import json
import requests

class TestSandboxAPI(unittest.TestCase):
    def setUp(self):
        self.base_url = 'http://localhost:8000'  # Adjust if your API runs on a different port
        self.test_account = {
            'account_id': 'test_account_1',
            'platform': 'test_platform',
            'positions': [
                {
                    'symbol': 'BTC-USD',
                    'size': 1.0,
                    'entry_price': 50000.0,
                    'side': 'long',
                    'leverage': 1.0,
                    'order_type': 'market'
                }
            ]
        }

    def test_update_synthetic_account(self):
        # Test updating an existing account
        response = requests.post(f'{self.base_url}/sandbox/update-account', json=self.test_account)
        self.assertEqual(response.status_code, 200)
        self.assertIn('success', response.json())
        self.assertEqual(response.json()['message'], f"Account {self.test_account['account_id']} updated successfully.")

        # Test adding a new account
        new_account = {
            'account_id': 'new_account_1',
            'platform': 'new_platform',
            'positions': []
        }
        response = requests.post(f'{self.base_url}/sandbox/update-account', json=new_account)
        self.assertEqual(response.status_code, 200)
        self.assertIn('success', response.json())
        self.assertEqual(response.json()['message'], f"Account {new_account['account_id']} updated successfully.")

if __name__ == '__main__':
    unittest.main() 