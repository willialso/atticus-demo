# sandbox/core/risk_engine.py
import logging
from typing import Dict
from .synthetic_position_manager import SyntheticPositionManager
from ..config.sandbox_config import SANDBOX_CONFIG
from .liquidation_manager import LiquidationManager

logger = logging.getLogger(__name__)

class RiskEngine:
    def __init__(self, position_manager: SyntheticPositionManager):
        self.position_manager = position_manager

    def analyze_risk(self, mark_price: float) -> Dict:
        """Analyzes portfolio for delta exposure and critical liquidation risk."""
        summary = self.position_manager.get_portfolio_summary()
        net_position = summary.get('net_position', 0)
        alerts = []

        # 1. Check Delta Exposure
        if abs(net_position) > SANDBOX_CONFIG.MAX_PORTFOLIO_DELTA:
            alert_msg = f"High Delta Exposure: Portfolio delta ({net_position:.2f}) exceeds threshold ({SANDBOX_CONFIG.MAX_PORTFOLIO_DELTA})."
            alerts.append({"severity": "high", "type": "delta_limit", "message": alert_msg})

        # 2. Check Liquidation Risk for each position
        for account in self.position_manager.accounts.values():
            for position in account.positions:
                if position.leverage > 1: # Only check leveraged positions
                    check_result = LiquidationManager.check_liquidation(position, mark_price)
                    if check_result.is_at_risk:
                        alert_msg = (
                            f"LIQUIDATION ALERT for {account.account_id}: Position {position.symbol} "
                            f"({position.size} BTC {position.side}) is at risk. "
                            f"Mark Price: ${mark_price:.2f}, Est. Liq. Price: ${check_result.liquidation_price:.2f}"
                        )
                        logger.critical(alert_msg) # Use CRITICAL for liquidations
                        alerts.append({"severity": "critical", "type": "liquidation_risk", "message": alert_msg})

        return {"delta_exposure": net_position, "alerts": alerts}
