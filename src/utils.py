"""
Utility functions for the SMC bot
"""

import json
from datetime import datetime
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


def format_price(price: float, decimals: int = 5) -> str:
    """
    Format price for display
    
    Args:
        price: Price value
        decimals: Number of decimal places
    
    Returns:
        Formatted price string
    """
    return f"{price:.{decimals}f}"


def calculate_pips(entry: float, exit: float, decimals: int = 5) -> float:
    """
    Calculate pips between two prices
    
    Args:
        entry: Entry price
        exit: Exit price
        decimals: Price decimal places
    
    Returns:
        Pips moved
    """
    pip_value = 10 ** (-decimals)
    return abs((exit - entry) / pip_value)


def calculate_risk_reward(entry: float, sl: float, tp: float) -> float:
    """
    Calculate risk:reward ratio
    
    Args:
        entry: Entry price
        sl: Stop loss price
        tp: Take profit price
    
    Returns:
        Risk:reward ratio
    """
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    
    if risk == 0:
        return 0
    
    return reward / risk


def get_trading_session() -> str:
    """
    Get current trading session
    
    Returns:
        Session name (e.g., 'London', 'New York')
    """
    hour = datetime.utcnow().hour
    
    if 8 <= hour < 17:
        return "London"
    elif 13 <= hour < 22:
        return "New York"
    elif 0 <= hour < 9:
        return "Tokyo"
    elif 21 <= hour < 24:
        return "Sydney"
    
    return "Overlap"


def serialize_alert(alert: Any) -> Dict:
    """
    Serialize alert for JSON storage
    
    Args:
        alert: Alert object
    
    Returns:
        Serializable dict
    """
    return {
        "type": alert.alert_type.value,
        "severity": alert.severity.value,
        "symbol": alert.symbol,
        "timeframe": alert.timeframe,
        "title": alert.title,
        "message": alert.message,
        "timestamp": alert.timestamp.isoformat(),
    }


def load_config(config_path: str = "config.yaml") -> Dict:
    """
    Load configuration from YAML
    
    Args:
        config_path: Path to config file
    
    Returns:
        Configuration dict
    """
    try:
        import yaml
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {str(e)}")
        return {}


def get_volatility_bias(recent_prices: list) -> str:
    """
    Determine volatility bias from price movement
    
    Args:
        recent_prices: List of recent prices
    
    Returns:
        Bias: 'high' or 'low'
    """
    if len(recent_prices) < 2:
        return "unknown"
    
    # Calculate average price change
    changes = [abs(recent_prices[i] - recent_prices[i-1]) for i in range(1, len(recent_prices))]
    avg_change = sum(changes) / len(changes) if changes else 0
    
    return "high" if avg_change > 0.01 else "low"
