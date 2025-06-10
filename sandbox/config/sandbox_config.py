from dataclasses import dataclass, field
from typing import Dict, List

@dataclass
class SandboxConfig:
    SANDBOX_MODE_ENABLED: bool = True
    RISK_CHECK_INTERVAL_SECONDS: float = 5.0
    HEDGING_CHECK_INTERVAL_SECONDS: float = 10.0
    LOG_LEVEL: str = "INFO"
    MAX_PORTFOLIO_DELTA: float = 0.2
    VOLATILITY_SPIKE_THRESHOLD: float = 1.2 # 120%
    DEFAULT_EXPIRY_HOURS: List[float] = field(default_factory=lambda: [2, 4, 8, 12])
    DEFAULT_STRIKE_OFFSETS: Dict[str, float] = field(default_factory=lambda: {
        "OTM": 0.05, "ATM": 0.0, "ITM": -0.05
    })

SANDBOX_CONFIG = SandboxConfig()
