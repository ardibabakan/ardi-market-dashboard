"""
Rate-limited API call wrapper.
Prevents getting blocked by Yahoo Finance and other sources.
"""
import time
import logging
import yfinance as yf
import pandas as pd

logger = logging.getLogger("ardi.rate_limiter")

def rate_limited_download(ticker, start=None, end=None,
                          period=None, max_retries=5, base_delay=0.5):
    for attempt in range(max_retries):
        try:
            time.sleep(base_delay)
            kwargs = {"auto_adjust": True, "progress": False, "timeout": 30}
            if period:
                kwargs["period"] = period
            else:
                if start: kwargs["start"] = start
                if end: kwargs["end"] = end
            data = yf.download(ticker, **kwargs)
            if data.empty:
                logger.warning(f"No data for {ticker}")
                return None
            return data
        except Exception as e:
            wait = base_delay * (2 ** attempt)
            logger.warning(f"Attempt {attempt+1} failed for {ticker}: {e}. Waiting {wait:.1f}s")
            time.sleep(wait)
    logger.error(f"All retries failed for {ticker}")
    return None

def batch_download(tickers, start=None, end=None, period=None,
                   batch_size=5, delay=2.0):
    results = {}
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        logger.info(f"Downloading batch: {batch}")
        for ticker in batch:
            results[ticker] = rate_limited_download(
                ticker, start=start, end=end, period=period)
        if i + batch_size < len(tickers):
            time.sleep(delay)
    return results
