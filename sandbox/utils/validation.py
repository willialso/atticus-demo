from dataclasses import dataclass
from typing import List, Optional, Dict

@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]

def validate_position(position_data: Dict) -> ValidationResult:
    errors = []
    if 'symbol' not in position_data or not isinstance(position_data['symbol'], str):
        errors.append("Missing or invalid 'symbol'")
    if 'size' not in position_data or not isinstance(position_data['size'], (int, float)):
        errors.append("Missing or invalid 'size'")
    if 'entry_price' not in position_data or not isinstance(position_data['entry_price'], (int, float)) or position_data['entry_price'] <= 0:
        errors.append("Missing or invalid 'entry_price'")
    if 'side' not in position_data or position_data['side'] not in ['long', 'short']:
        errors.append("Missing or invalid 'side'")
    return ValidationResult(is_valid=not errors, errors=errors)
