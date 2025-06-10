import os
import json
import time
from typing import Dict, Any

def ensure_data_directories():
    """Create data directory structure if it doesn't exist"""
    directories = [
        'sandbox/data/mock_accounts/account_snapshots',
        'sandbox/data/mock_accounts/position_history', 
        'sandbox/data/mock_accounts/balance_history',
        'sandbox/data/strategy_logs/hedging_executions',
        'sandbox/data/strategy_logs/strategy_performance',
        'sandbox/data/backtest_results/strategy_backtests',
        'sandbox/data/backtest_results/portfolio_backtests',
        'sandbox/data/backtest_results/performance_reports'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

def save_json_data(file_path: str, data: Dict[str, Any]):
    """Save data to JSON file with automatic directory creation"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2, default=str)

def append_json_log(file_path: str, data: Dict[str, Any]):
    """Append data to JSON log file"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    with open(file_path, 'a') as f:
        f.write(json.dumps(data, default=str) + '\n')
