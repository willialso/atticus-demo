# backend/trade_executor.py

import asyncio
import time
import uuid
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from backend import config
from backend.utils import setup_logger

logger = setup_logger(__name__)

class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"

class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"

class PositionSide(Enum):
    LONG = "long"  # Bought options
    SHORT = "short"  # Sold options

@dataclass
class TradeOrder:
    order_id: str
    user_id: str
    symbol: str
    side: OrderSide
    quantity: float
    premium_per_contract: float
    total_premium: float
    option_type: str  # "call" or "put"
    strike: float
    expiry_minutes: int
    timestamp: float
    status: OrderStatus = OrderStatus.PENDING
    fill_price: Optional[float] = None
    greeks: Dict[str, float] = field(default_factory=dict)

@dataclass
class Position:
    position_id: str
    user_id: str
    symbol: str
    side: PositionSide  # long (bought) or short (sold)
    option_type: str  # "call" or "put"
    strike: float
    expiry_minutes: int
    expiry_timestamp: float
    quantity: float
    entry_premium: float
    current_market_value: float
    unrealized_pnl: float
    current_delta: float
    current_gamma: float
    current_theta: float
    current_vega: float
    entry_timestamp: float
    entry_btc_price: float
    is_expired: bool = False

    def is_open(self) -> bool:
        """Check if position is still open (not expired)."""
        return not self.is_expired and time.time() < self.expiry_timestamp

    def update_unrealized_pnl(self, current_btc_price: float):
        """Update position's unrealized P&L based on current BTC price."""
        self._update_position_value(current_btc_price)

    def _update_position_value(self, current_price: float):
        """Update position market value and P&L in real-time."""
        try:
            # Calculate intrinsic value
            if self.option_type == "call":
                intrinsic_value = max(0, current_price - self.strike)
            else:  # put
                intrinsic_value = max(0, self.strike - current_price)

            # Calculate time value using simplified model
            time_remaining = max(0, (self.expiry_timestamp - time.time()) / 3600)  # Hours
            time_value = intrinsic_value * 0.1 * time_remaining if time_remaining > 0 else 0

            # Total option value
            total_option_value = intrinsic_value + time_value
            self.current_market_value = total_option_value * self.quantity

            # Calculate P&L based on position side
            if self.side == PositionSide.LONG:
                # Long positions: profit when market value > entry premium
                self.unrealized_pnl = self.current_market_value - abs(self.entry_premium)
            else:  # SHORT
                # Short positions: profit when market value < entry premium received
                self.unrealized_pnl = abs(self.entry_premium) - self.current_market_value

        except Exception as e:
            logger.error(f"❌ Position value update error: {e}")

@dataclass
class UserAccount:
    user_id: str
    btc_balance: float
    usd_balance: float
    total_portfolio_value: float
    active_positions: List[Position] = field(default_factory=list)
    trade_history: List[TradeOrder] = field(default_factory=list)
    daily_pnl: float = 0.0
    total_pnl: float = 0.0

    @property
    def positions(self) -> List[Position]:
        """Alias for active_positions for compatibility."""
        return self.active_positions

class TradeExecutor:
    """Enhanced trade executor with full buy/sell functionality and ultra-fast performance."""

    def __init__(self, pricing_engine, hedger):
        self.pricing_engine = pricing_engine
        self.hedger = hedger
        self.user_accounts: Dict[str, UserAccount] = {}
        self.active_positions: Dict[str, Position] = {}
        self.completed_trades: List[TradeOrder] = []
        self.position_callbacks: List = []
        self._last_greeks_update = 0  # Initialize for Greeks update tracking
        logger.info("✅ Trade executor initialized with buy/sell functionality")

    def create_user_account(self, user_id: str, initial_btc_balance: float = 0.01) -> UserAccount:
        """Create a new user account with initial balance."""
        current_btc_price = self.pricing_engine.current_price or 110000
        usd_equivalent = initial_btc_balance * current_btc_price

        account = UserAccount(
            user_id=user_id,
            btc_balance=initial_btc_balance,
            usd_balance=usd_equivalent,
            total_portfolio_value=usd_equivalent
        )

        self.user_accounts[user_id] = account
        logger.info(f"👤 Created account for {user_id} with {initial_btc_balance} BTC (${usd_equivalent:.2f})")
        return account

    def execute_trade(self, order: TradeOrder) -> Tuple[bool, str, Optional[Position]]:
        """Execute both BUY and SELL orders with proper risk management."""
        try:
            # Get or create user account
            if order.user_id not in self.user_accounts:
                self.create_user_account(order.user_id)

            account = self.user_accounts[order.user_id]
            current_btc_price = self.pricing_engine.current_price

            # Validate order
            validation_result = self._validate_order(order, account, current_btc_price)
            if not validation_result[0]:
                order.status = OrderStatus.REJECTED
                return False, validation_result[1], None

            # Execute based on order side
            if order.side == OrderSide.BUY:
                return self._execute_buy_order(order, account, current_btc_price)
            else:  # OrderSide.SELL
                return self._execute_sell_order(order, account, current_btc_price)

        except Exception as e:
            logger.error(f"❌ Trade execution error: {e}")
            order.status = OrderStatus.REJECTED
            return False, f"Execution error: {str(e)}", None

    def _validate_order(self, order: TradeOrder, account: UserAccount, current_price: float) -> Tuple[bool, str]:
        """Validate order parameters and account balances."""
        # Basic validation
        if order.quantity <= 0:
            return False, "Invalid quantity"
        if order.strike <= 0:
            return False, "Invalid strike price"
        if order.expiry_minutes not in config.AVAILABLE_EXPIRIES_MINUTES:
            return False, f"Invalid expiry. Available: {config.AVAILABLE_EXPIRIES_MINUTES}"

        # Balance validation for BUY orders
        if order.side == OrderSide.BUY:
            required_btc = order.total_premium / current_price
            if account.btc_balance < required_btc:
                return False, f"Insufficient balance. Need {required_btc:.6f} BTC, have {account.btc_balance:.6f} BTC"

        # For SELL orders, check margin requirements (simplified)
        if order.side == OrderSide.SELL:
            # For naked selling, require minimum balance as margin
            margin_required_btc = (order.strike * order.quantity * 0.1) / current_price  # 10% margin
            if account.btc_balance < margin_required_btc:
                return False, f"Insufficient margin for naked sell. Need {margin_required_btc:.6f} BTC"

        return True, "Order validated"

    def _execute_buy_order(self, order: TradeOrder, account: UserAccount, current_price: float) -> Tuple[bool, str, Optional[Position]]:
        """Execute BUY order - user pays premium to buy options."""
        try:
            # Calculate costs
            premium_btc = order.total_premium / current_price

            # Deduct premium from account
            account.btc_balance -= premium_btc
            account.usd_balance = account.btc_balance * current_price

            # Create LONG position
            position = self._create_position(
                order=order,
                side=PositionSide.LONG,
                entry_premium=order.total_premium,
                current_price=current_price
            )

            # Add to active positions
            account.active_positions.append(position)
            self.active_positions[position.position_id] = position

            # Update order status
            order.status = OrderStatus.FILLED
            order.fill_price = order.premium_per_contract
            account.trade_history.append(order)

            # Update portfolio value
            self._update_portfolio_value(account, current_price)

            # Notify hedger
            if self.hedger:
                self.hedger.add_position(position)

            logger.info(f"💰 BUY executed: {order.user_id} bought {order.quantity} {order.option_type.upper()} @ ${order.strike} for ${order.total_premium:.2f}")
            return True, "Buy order executed successfully", position

        except Exception as e:
            logger.error(f"❌ Buy order execution error: {e}")
            return False, f"Buy execution failed: {str(e)}", None

    def _execute_sell_order(self, order: TradeOrder, account: UserAccount, current_price: float) -> Tuple[bool, str, Optional[Position]]:
        """Execute SELL order - user receives premium for selling options (creates short position)."""
        try:
            # Calculate premium received
            premium_btc = order.total_premium / current_price

            # Credit premium to account (user receives money for selling)
            account.btc_balance += premium_btc
            account.usd_balance = account.btc_balance * current_price

            # Create SHORT position (unlimited risk for calls, limited for puts)
            position = self._create_position(
                order=order,
                side=PositionSide.SHORT,
                entry_premium=-order.total_premium,  # Negative because it's credit received
                current_price=current_price
            )

            # Add to active positions
            account.active_positions.append(position)
            self.active_positions[position.position_id] = position

            # Update order status
            order.status = OrderStatus.FILLED
            order.fill_price = order.premium_per_contract
            account.trade_history.append(order)

            # Update portfolio value
            self._update_portfolio_value(account, current_price)

            # Notify hedger about short position
            if self.hedger:
                self.hedger.add_position(position)

            logger.info(f"💸 SELL executed: {order.user_id} sold {order.quantity} {order.option_type.upper()} @ ${order.strike} for ${order.total_premium:.2f} premium")
            return True, "Sell order executed successfully", position

        except Exception as e:
            logger.error(f"❌ Sell order execution error: {e}")
            return False, f"Sell execution failed: {str(e)}", None

    def _create_position(self, order: TradeOrder, side: PositionSide, entry_premium: float, current_price: float) -> Position:
        """Create a new position from an executed order."""
        expiry_timestamp = time.time() + (order.expiry_minutes * 60)

        position = Position(
            position_id=f"pos_{uuid.uuid4().hex[:8]}",
            user_id=order.user_id,
            symbol=order.symbol,
            side=side,
            option_type=order.option_type,
            strike=order.strike,
            expiry_minutes=order.expiry_minutes,
            expiry_timestamp=expiry_timestamp,
            quantity=order.quantity,
            entry_premium=entry_premium,
            current_market_value=0.0,  # Will be updated
            unrealized_pnl=0.0,
            current_delta=order.greeks.get('delta', 0),
            current_gamma=order.greeks.get('gamma', 0),
            current_theta=order.greeks.get('theta', 0),
            current_vega=order.greeks.get('vega', 0),
            entry_timestamp=time.time(),
            entry_btc_price=current_price
        )

        # Calculate initial market value
        position._update_position_value(current_price)
        return position

    # +++ FIXED METHOD: Now accepts current_btc_price parameter +++
    def update_position_marks(self, current_btc_price: float = None):
        """
        Update all active positions with current market data - OPTIMIZED.
        
        Args:
            current_btc_price: Current BTC price for mark-to-market calculations.
                              If None, will try to get from pricing_engine.
        """
        if current_btc_price is None:
            current_btc_price = self.pricing_engine.current_price
            if not current_btc_price:
                logger.warning("No current BTC price available for position mark updates")
                return

        if current_btc_price <= 0:
            logger.warning(f"Invalid BTC price for position marks: {current_btc_price}")
            return

        current_time = time.time()
        expired_positions = []

        for position in self.active_positions.values():
            if not position.is_expired:
                # Check for expiry first
                if current_time >= position.expiry_timestamp:
                    expired_positions.append(position)
                    continue

                # Update position value
                position._update_position_value(current_btc_price)

                # Update Greeks if available (optimized - less frequent)
                if hasattr(self, '_last_greeks_update') and (current_time - self._last_greeks_update) < 5:
                    continue  # Skip Greeks update if updated recently

                try:
                    option_chain = self.pricing_engine.generate_option_chain(position.expiry_minutes)
                    if option_chain:
                        quotes = option_chain.calls if position.option_type == "call" else option_chain.puts
                        for quote in quotes:
                            if abs(quote.strike - position.strike) < 1.0:
                                position.current_delta = quote.delta
                                position.current_gamma = quote.gamma
                                position.current_theta = quote.theta
                                position.current_vega = quote.vega
                                break
                except Exception as e:
                    logger.debug(f"Greeks update error: {e}")

        self._last_greeks_update = current_time

        # Auto-settle expired positions
        for position in expired_positions:
            self._settle_expired_position(position, current_btc_price)

        # Update all user portfolio values
        for account in self.user_accounts.values():
            self._update_portfolio_value(account, current_btc_price)

        logger.debug(f"Updated position marks with BTC price: ${current_btc_price:,.2f}")
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def _update_portfolio_value(self, account: UserAccount, current_price: float):
        """Update total portfolio value including positions."""
        # Base value from BTC balance
        base_value = account.btc_balance * current_price

        # Add unrealized P&L from all positions
        positions_pnl = sum(pos.unrealized_pnl for pos in account.active_positions if not pos.is_expired)

        account.total_portfolio_value = base_value + positions_pnl

        # Update daily P&L (simplified - would need proper daily tracking)
        account.daily_pnl = positions_pnl
        account.total_pnl = positions_pnl

    def check_and_settle_expired_options(self) -> List[Position]:
        """Check for expired options and settle them automatically."""
        current_time = time.time()
        current_price = self.pricing_engine.current_price
        settled_positions = []

        for position in list(self.active_positions.values()):
            if current_time >= position.expiry_timestamp and not position.is_expired:
                settlement_result = self._settle_expired_position(position, current_price)
                if settlement_result:
                    settled_positions.append(position)

        return settled_positions

    def _settle_expired_position(self, position: Position, current_price: float) -> bool:
        """Settle an expired option position."""
        try:
            # Calculate final settlement value
            if position.option_type == "call":
                settlement_value = max(0, current_price - position.strike)
            else:  # put
                settlement_value = max(0, position.strike - current_price)

            final_value = settlement_value * position.quantity

            # Update account balance based on position side
            account = self.user_accounts[position.user_id]

            if position.side == PositionSide.LONG:
                # Long position: receive settlement value
                settlement_btc = final_value / current_price
                account.btc_balance += settlement_btc
            else:  # SHORT
                # Short position: pay settlement value
                settlement_btc = final_value / current_price
                account.btc_balance -= settlement_btc

            # Mark position as expired and calculate final P&L
            position.is_expired = True
            position.current_market_value = final_value

            if position.side == PositionSide.LONG:
                position.unrealized_pnl = final_value - abs(position.entry_premium)
            else:  # SHORT
                position.unrealized_pnl = abs(position.entry_premium) - final_value

            # Remove from active positions
            if position.position_id in self.active_positions:
                del self.active_positions[position.position_id]

            # Remove from account active positions
            account.active_positions = [p for p in account.active_positions if p.position_id != position.position_id]

            # Update portfolio value
            account.usd_balance = account.btc_balance * current_price
            self._update_portfolio_value(account, current_price)

            logger.info(f"⏰ Settled expired position: {position.position_id} for ${final_value:.2f}")
            return True

        except Exception as e:
            logger.error(f"❌ Position settlement error: {e}")
            return False

    def get_user_portfolio_summary(self, user_id: str) -> Optional[Dict]:
        """Get comprehensive portfolio summary for a user - OPTIMIZED."""
        if user_id not in self.user_accounts:
            return None

        account = self.user_accounts[user_id]
        current_price = self.pricing_engine.current_price or 110000

        # Update portfolio value
        self._update_portfolio_value(account, current_price)

        active_positions_data = []
        for position in account.active_positions:
            if not position.is_expired:
                time_remaining = max(0, position.expiry_timestamp - time.time())

                # Calculate breakeven
                if position.side == PositionSide.LONG:
                    if position.option_type == "call":
                        breakeven = position.strike + abs(position.entry_premium) / position.quantity
                    else:  # put
                        breakeven = position.strike - abs(position.entry_premium) / position.quantity
                else:  # SHORT
                    if position.option_type == "call":
                        breakeven = position.strike + abs(position.entry_premium) / position.quantity
                    else:  # put
                        breakeven = position.strike - abs(position.entry_premium) / position.quantity

                # Calculate max profit/loss
                if position.side == PositionSide.LONG:
                    max_loss = abs(position.entry_premium)
                    max_profit = "Unlimited" if position.option_type == "call" else position.strike * position.quantity - abs(position.entry_premium)
                else:  # SHORT
                    max_profit = abs(position.entry_premium)
                    max_loss = "Unlimited" if position.option_type == "call" else position.strike * position.quantity - abs(position.entry_premium)

                active_positions_data.append({
                    "position_id": position.position_id,
                    "side": position.side.value,
                    "option_type": position.option_type,
                    "strike": position.strike,
                    "quantity": position.quantity,
                    "entry_premium": position.entry_premium,
                    "current_value": position.current_market_value,
                    "unrealized_pnl": position.unrealized_pnl,
                    "pnl_percentage": (position.unrealized_pnl / abs(position.entry_premium)) * 100 if position.entry_premium != 0 else 0,
                    "expiry_timestamp": position.expiry_timestamp,
                    "time_remaining": time_remaining,
                    "time_remaining_formatted": f"{int(time_remaining//3600)}h {int((time_remaining%3600)//60)}m",
                    "entry_btc_price": position.entry_btc_price,
                    "breakeven": breakeven,
                    "max_profit": max_profit,
                    "max_loss": max_loss,
                    "greeks": {
                        "delta": position.current_delta,
                        "gamma": position.current_gamma,
                        "theta": position.current_theta,
                        "vega": position.current_vega
                    }
                })

        return {
            "user_id": user_id,
            "btc_balance": account.btc_balance,
            "usd_balance": account.usd_balance,
            "total_portfolio_value": account.total_portfolio_value,
            "daily_pnl": account.daily_pnl,
            "total_pnl": account.total_pnl,
            "active_positions": active_positions_data,
            "total_positions": len(active_positions_data),
            "last_updated": time.time()
        }

    def close_position(self, user_id: str, position_id: str, partial_quantity: Optional[float] = None) -> Tuple[bool, str]:
        """Close a specific position early (before expiration) - ENHANCED."""
        try:
            if position_id not in self.active_positions:
                return False, "Position not found"

            position = self.active_positions[position_id]
            if position.user_id != user_id:
                return False, "Position does not belong to user"

            current_price = self.pricing_engine.current_price

            # Determine quantity to close
            close_quantity = partial_quantity if partial_quantity else position.quantity
            if close_quantity > position.quantity:
                return False, "Cannot close more than position size"

            # Calculate current option value for closing
            if position.option_type == "call":
                option_value = max(0, current_price - position.strike)
            else:
                option_value = max(0, position.strike - current_price)

            total_value = option_value * close_quantity
            account = self.user_accounts[user_id]

            # Close position based on side
            if position.side == PositionSide.LONG:
                # Selling to close long position
                value_btc = total_value / current_price
                account.btc_balance += value_btc
            else:  # SHORT
                # Buying to close short position
                value_btc = total_value / current_price
                account.btc_balance -= value_btc

            # Handle partial vs full close
            if close_quantity == position.quantity:
                # Full close - remove position
                del self.active_positions[position_id]
                account.active_positions = [p for p in account.active_positions if p.position_id != position_id]
                close_type = "fully closed"
            else:
                # Partial close - reduce position size
                position.quantity -= close_quantity
                position.entry_premium *= (position.quantity / (position.quantity + close_quantity))
                close_type = f"partially closed ({close_quantity} of {position.quantity + close_quantity})"

            # Update portfolio
            account.usd_balance = account.btc_balance * current_price
            self._update_portfolio_value(account, current_price)

            logger.info(f"🔒 Closed position {position_id}: {close_type} for ${total_value:.2f}")
            return True, f"Position {close_type} for ${total_value:.2f}"

        except Exception as e:
            logger.error(f"❌ Position close error: {e}")
            return False, f"Close failed: {str(e)}"

    def get_platform_risk_summary(self) -> Dict:
        """Get platform-wide risk metrics."""
        total_exposure = 0
        net_delta = 0
        position_count = len(self.active_positions)

        for position in self.active_positions.values():
            if not position.is_expired:
                total_exposure += abs(position.current_market_value)

                # Calculate net delta exposure
                if position.side == PositionSide.LONG:
                    net_delta += position.current_delta * position.quantity
                else:  # SHORT
                    net_delta -= position.current_delta * position.quantity

        return {
            "total_positions": position_count,
            "total_exposure_usd": total_exposure,
            "net_delta_exposure": net_delta,
            "platform_utilization": min(100, (total_exposure / 1000000) * 100),  # % of 1M limit
            "risk_status": "low" if net_delta < 10 else "medium" if net_delta < 50 else "high"
        }
