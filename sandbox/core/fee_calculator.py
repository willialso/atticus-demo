# sandbox/core/fee_calculator.py

class FeeCalculator:
    """
    Calculates trading fees based on a standard maker/taker model.
    OKX and Kraken have similar baseline fee structures for perpetuals.
    """
    # Standard baseline fees for retail volume tiers
    MAKER_FEE_RATE = 0.0002  # 0.02%
    TAKER_FEE_RATE = 0.0005  # 0.05%

    @staticmethod
    def calculate_fee(notional_value: float, order_type: str = 'taker') -> float:
        """
        Calculates the trade fee for a given notional value and order type.
        
        Args:
            notional_value: The total value of the trade (size * price).
            order_type: 'maker' or 'taker'.
        
        Returns:
            The calculated trade fee.
        """
        rate = FeeCalculator.MAKER_FEE_RATE if order_type == 'maker' else FeeCalculator.TAKER_FEE_RATE
        return notional_value * rate
