"""
Validates data from all sources before it enters the system.
Catches bad values (NaN, None, out-of-range) before they
corrupt analysis.
"""
import logging
import math

logger = logging.getLogger("ardi.validator")

def validate_price(value, ticker="unknown", min_price=0.01, max_price=999999):
    if value is None:
        logger.warning(f"Price for {ticker} is None")
        return None
    try:
        v = float(value)
        if math.isnan(v) or math.isinf(v):
            logger.warning(f"Price for {ticker} is NaN/Inf")
            return None
        if v < min_price or v > max_price:
            logger.warning(f"Price for {ticker} out of range: {v}")
            return None
        return v
    except (TypeError, ValueError):
        logger.warning(f"Price for {ticker} not numeric: {value}")
        return None

def validate_percentage(value, name="unknown", min_val=-100, max_val=10000):
    if value is None:
        return None
    try:
        v = float(value)
        if math.isnan(v) or math.isinf(v):
            return None
        if v < min_val or v > max_val:
            logger.warning(f"Percentage {name} out of range: {v}")
            return None
        return v
    except (TypeError, ValueError):
        return None

def validate_gold_price(gld_price):
    """Gold price must use GLD x 10.1 and be between 1500-5000."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import GOLD_MULTIPLIER, GOLD_MIN_SANE, GOLD_MAX_SANE
    if gld_price is None:
        return None
    est = gld_price * GOLD_MULTIPLIER
    if GOLD_MIN_SANE < est < GOLD_MAX_SANE:
        return round(est, 2)
    logger.warning(f"Gold price estimate {est} outside sane range")
    return None

def validate_vix(value):
    return validate_price(value, "VIX", min_price=5, max_price=100)

def validate_rsi(value):
    return validate_percentage(value, "RSI", min_val=0, max_val=100)
