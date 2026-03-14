"""
Technical Analysis Agent — Layer 2 Analysis
Ardi Market Command Center v2

Computes RSI, MACD, Bollinger Bands, MA crossovers, volume ratio
for all 8 portfolio tickers from cached price history.
"""
import json, logging, sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import PLANNED_POSITIONS, CACHE_DIR, AGENT_OUTPUT_DIR
from lib.supabase_client import insert
from lib.safe_scalar import safe_scalar
from lib.data_validator import validate_rsi

import pandas as pd
import numpy as np

logger = logging.getLogger("ardi.layer2.technical")

PORTFOLIO_TICKERS = list(PLANNED_POSITIONS.keys())


def _load_history(ticker):
    """Load cached price history for a ticker."""
    path = CACHE_DIR / f"{ticker}_hist.json"
    if not path.exists():
        logger.warning(f"No cached history for {ticker}")
        return None
    try:
        with open(path) as f:
            raw = json.load(f)
        df = pd.DataFrame(raw)
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.set_index("Date").sort_index()
        elif "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").sort_index()
        else:
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
        # Normalize column names to lowercase
        df.columns = [c.lower() for c in df.columns]
        return df
    except Exception as e:
        logger.warning(f"Failed to load history for {ticker}: {e}")
        return None


def _compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def _compute_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _rsi_signal(rsi_val):
    if rsi_val is None:
        return "UNKNOWN"
    if rsi_val > 70:
        return "OVERBOUGHT"
    if rsi_val < 30:
        return "OVERSOLD"
    return "NEUTRAL"


def _score_indicators(rsi_sig, macd_cross, ma_status, bb_pos, vol_ratio):
    """Count bullish signals and assign an overall score."""
    bullish = 0
    total = 5
    if rsi_sig == "OVERSOLD":
        bullish += 1
    elif rsi_sig == "NEUTRAL":
        bullish += 0.5
    if macd_cross == "BULLISH":
        bullish += 1
    if ma_status == "GOLDEN_CROSS":
        bullish += 1
    elif ma_status == "ABOVE_BOTH":
        bullish += 0.75
    if bb_pos and bb_pos < 0.3:
        bullish += 1
    elif bb_pos and bb_pos < 0.7:
        bullish += 0.5
    if vol_ratio and vol_ratio > 1.5:
        bullish += 1
    elif vol_ratio and vol_ratio > 1.0:
        bullish += 0.5

    ratio = bullish / total
    if ratio >= 0.8:
        return "STRONG"
    if ratio >= 0.6:
        return "BULLISH"
    if ratio >= 0.4:
        return "NEUTRAL"
    if ratio >= 0.2:
        return "BEARISH"
    return "WEAK"


def _analyze_ticker(ticker, df):
    """Run all technical indicators for a single ticker."""
    close = df["close"] if "close" in df.columns else None
    volume = df["volume"] if "volume" in df.columns else None

    if close is None or len(close) < 26:
        return None

    # RSI
    rsi_series = _compute_rsi(close, 14)
    rsi_val = safe_scalar(rsi_series.iloc[-1]) if len(rsi_series) > 0 else None
    rsi_val = validate_rsi(rsi_val)
    rsi_sig = _rsi_signal(rsi_val)

    # MACD
    macd_line, signal_line, histogram = _compute_macd(close)
    macd_val = safe_scalar(macd_line.iloc[-1])
    macd_sig_val = safe_scalar(signal_line.iloc[-1])
    macd_hist = safe_scalar(histogram.iloc[-1])
    # Crossover: current histogram positive, previous negative
    macd_cross = "NEUTRAL"
    if len(histogram) >= 2:
        prev_hist = safe_scalar(histogram.iloc[-2])
        if macd_hist > 0 and prev_hist <= 0:
            macd_cross = "BULLISH"
        elif macd_hist < 0 and prev_hist >= 0:
            macd_cross = "BEARISH"

    # Moving averages
    ma50 = safe_scalar(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None
    ma200 = safe_scalar(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None
    current_price = safe_scalar(close.iloc[-1])

    ma_status = "INSUFFICIENT_DATA"
    if ma50 and ma200:
        if ma50 > ma200 and current_price > ma50:
            ma_status = "GOLDEN_CROSS"
        elif ma50 > ma200:
            ma_status = "ABOVE_BOTH"
        elif ma50 < ma200 and current_price < ma50:
            ma_status = "DEATH_CROSS"
        else:
            ma_status = "BELOW_BOTH"

    # Bollinger Bands
    bb_upper, bb_lower, bb_position = None, None, None
    if len(close) >= 20:
        sma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std()
        bb_upper = safe_scalar((sma20 + 2 * std20).iloc[-1])
        bb_lower = safe_scalar((sma20 - 2 * std20).iloc[-1])
        if bb_upper and bb_lower and bb_upper != bb_lower:
            bb_position = round((current_price - bb_lower) / (bb_upper - bb_lower), 4)

    # Volume ratio
    vol_ratio = None
    if volume is not None and len(volume) >= 20:
        avg_vol = safe_scalar(volume.rolling(20).mean().iloc[-1])
        cur_vol = safe_scalar(volume.iloc[-1])
        if avg_vol > 0:
            vol_ratio = round(cur_vol / avg_vol, 4)

    overall = _score_indicators(rsi_sig, macd_cross, ma_status, bb_position, vol_ratio)

    return {
        "ticker": ticker,
        "rsi": round(rsi_val, 2) if rsi_val is not None else None,
        "rsi_signal": rsi_sig,
        "macd": round(macd_val, 4),
        "macd_signal_line": round(macd_sig_val, 4),
        "macd_histogram": round(macd_hist, 4),
        "macd_crossover": macd_cross,
        "ma50": round(ma50, 2) if ma50 else None,
        "ma200": round(ma200, 2) if ma200 else None,
        "ma_status": ma_status,
        "bb_upper": round(bb_upper, 2) if bb_upper else None,
        "bb_lower": round(bb_lower, 2) if bb_lower else None,
        "bb_position": bb_position,
        "volume_ratio": vol_ratio,
        "overall_score": overall,
    }


def run():
    """Main entry point."""
    logger.info("Technical Analysis Agent starting...")
    results = {}
    records_written = 0

    for ticker in PORTFOLIO_TICKERS:
        df = _load_history(ticker)
        if df is None:
            continue
        analysis = _analyze_ticker(ticker, df)
        if analysis is None:
            logger.warning(f"Insufficient data for {ticker}")
            continue

        results[ticker] = analysis
        insert("technical_analysis", analysis)
        records_written += 1

    # Write local JSON
    output_path = AGENT_OUTPUT_DIR / "technical_agent_output.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Technical Agent complete. {records_written} records.")
    return {"status": "ok", "records": records_written, "data": results}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
