# backend/data_hub.py
import asyncio
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class DataHub:
    """
    A thread-safe, centralized class to hold and manage shared market data.
    This acts as the non-disruptive 'middle script' or message bus.
    """
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._lock = asyncio.Lock() # Use an asyncio Lock for async safety
        logger.info("Data Hub initialized.")

    async def update_data(self, new_data: Dict[str, Any]):
        """Atomically updates the shared data from any source."""
        async with self._lock:
            self._data.update(new_data)
            # Prune old data if necessary to prevent memory leaks
            if len(self._data) > 100:
                self._data.pop(next(iter(self._data)), None)

    async def get_data(self) -> Dict[str, Any]:
        """Atomically retrieves a copy of the shared data."""
        async with self._lock:
            return self._data.copy()

    def get_current_price(self) -> float:
        """Get the current BTC price from the data hub."""
        return self._data.get('btc_price', 50000.0)  # Default to 50000.0 if no price is set

# Create a single, global instance to be shared across the application
data_hub = DataHub()
