# sandbox/core/synthetic_position_manager.py
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict
import time

from ..utils.validation import validate_position
from .fee_calculator import FeeCalculator
from .funding_manager import FundingManager

logger = logging.getLogger(__name__)

@dataclass
class SyntheticPosition:
    """Represents a single synthetic perpetual futures position with full cost details."""
    symbol: str
    size: float
    entry_price: float
    side: str
    leverage: float = 1.0
    order_type: str = 'taker'
    trade_fee: float = 0.0
    unrealized_pnl: float = 0.0
    # New field to track total funding payments
    funding_pnl: float = 0.0

@dataclass
class SyntheticAccount:
    account_id: str
    platform: str
    positions: List[SyntheticPosition] = field(default_factory=list)

class SyntheticPositionManager:
    def __init__(self, filepath='sandbox/config/synthetic_accounts.json'):
        self.accounts: Dict[str, SyntheticAccount] = {}
        self.funding_manager = FundingManager()
        self.last_funding_time = time.time()
        self.load_accounts(filepath)

    def load_accounts(self, filepath: str):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            for acc_data in data.get('accounts', []):
                account = SyntheticAccount(account_id=acc_data['account_id'], platform=acc_data['platform'])
                for pos_data in acc_data.get('positions', []):
                    if validate_position(pos_data).is_valid:
                        notional_value = abs(pos_data['size']) * pos_data['entry_price']
                        fee = FeeCalculator.calculate_fee(notional_value, pos_data.get('order_type', 'taker'))
                        
                        # Set initial P&L to be negative the opening fee
                        pos_data['trade_fee'] = fee
                        pos_data['unrealized_pnl'] = -fee
                        
                        account.positions.append(SyntheticPosition(**pos_data))
                self.accounts[account.account_id] = account
            logger.info(f"Loaded {len(self.accounts)} accounts with fee calculations.")
        except Exception as e:
            logger.error(f"Error loading accounts: {e}", exc_info=True)

    def update_pnl_and_funding(self, mark_price: float, perp_price: float):
        """Updates P&L from price moves and applies funding fees periodically."""
        current_time = time.time()

        # Apply funding fees every 8 hours (simulated)
        if current_time - self.last_funding_time >= FundingManager.FUNDING_INTERVAL_HOURS * 3600:
            self.funding_manager.apply_funding_fees(self.accounts, mark_price, perp_price)
            self.last_funding_time = current_time

        # Update P&L based on market movement
        for account in self.accounts.values():
            for position in account.positions:
                price_diff = mark_price - position.entry_price
                # Base P&L from price movement
                base_pnl = position.size * price_diff if position.side == 'long' else position.size * -price_diff
                # Total P&L = Base P&L - Opening Fee + Funding P&L
                position.unrealized_pnl = base_pnl - position.trade_fee + position.funding_pnl

    def get_portfolio_summary(self):
        total_exposure = sum(abs(pos.size) for acc in self.accounts.values() for pos in acc.positions)
        net_position = sum(pos.size if pos.side == 'long' else -pos.size for acc in self.accounts.values() for pos in acc.positions)
        total_pnl = sum(pos.unrealized_pnl for acc in self.accounts.values() for pos in acc.positions)
        return {"total_exposure": total_exposure, "net_position": net_position, "total_pnl": total_pnl, "accounts": self.accounts}

    def add_position(self, account_id: str, pos_data: dict):
        # If the account does not exist, create it automatically
        if account_id not in self.accounts:
            self.accounts[account_id] = SyntheticAccount(account_id=account_id, platform="sandbox")
        if not validate_position(pos_data).is_valid:
            raise ValueError("Invalid position data.")
        notional_value = abs(pos_data['size']) * pos_data['entry_price']
        fee = FeeCalculator.calculate_fee(notional_value, pos_data.get('order_type', 'taker'))
        pos_data['trade_fee'] = fee
        pos_data['unrealized_pnl'] = -fee
        pos_data['funding_pnl'] = 0.0
        self.accounts[account_id].positions.append(SyntheticPosition(**pos_data))
        return self.accounts[account_id].positions[-1]
