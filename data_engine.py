import yfinance as yf
import pandas as pd
import numpy as np
import requests
import json
import time
from datetime import datetime, timedelta
import pytz


# =============================================================================
# DATA ENGINE — Professional Market Data & Technical Analysis
# All technical indicators computed with pure pandas/numpy (no pandas_ta).
# Every function returns a dict with "status": "ok" or "status": "error".
# =============================================================================


def get_stock_price(ticker: str) -> dict:
    """
    Fetch current price data for a single ticker.

    Returns dict with:
        price, prev_close, change, change_pct,
        high_52w, low_52w, status
    """
    try:
        tk = yf.Ticker(ticker)
        info = tk.info or {}

        price = info.get("currentPrice") or info.get("regularMarketPrice")
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")

        # Fallback: pull from recent history if info fields are missing
        if price is None or prev_close is None:
            hist = tk.history(period="5d")
            if hist.empty:
                return {"status": "error", "error": f"No data for {ticker}"}
            price = price or float(hist["Close"].iloc[-1])
            prev_close = prev_close or float(hist["Close"].iloc[-2]) if len(hist) >= 2 else price

        change = round(price - prev_close, 4)
        change_pct = round((change / prev_close) * 100, 2) if prev_close else 0.0

        high_52w = info.get("fiftyTwoWeekHigh")
        low_52w = info.get("fiftyTwoWeekLow")

        # Fallback for 52-week range
        if high_52w is None or low_52w is None:
            hist_1y = tk.history(period="1y")
            if not hist_1y.empty:
                high_52w = high_52w or float(hist_1y["High"].max())
                low_52w = low_52w or float(hist_1y["Low"].min())

        return {
            "status": "ok",
            "ticker": ticker.upper(),
            "price": round(price, 2),
            "prev_close": round(prev_close, 2),
            "change": round(change, 2),
            "change_pct": change_pct,
            "high_52w": round(high_52w, 2) if high_52w else None,
            "low_52w": round(low_52w, 2) if low_52w else None,
        }
    except Exception as e:
        return {"status": "error", "ticker": ticker.upper(), "error": str(e)}


def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """RSI via exponential weighted mean (Wilder smoothing, com = period-1)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _compute_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD line, signal line, histogram — all via EWM."""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _compute_bollinger(series: pd.Series, period: int = 20, std_dev: int = 2):
    """Bollinger Bands: middle (SMA), upper, lower."""
    middle = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return upper, middle, lower


def get_technical_signals(ticker: str) -> dict:
    """
    Full technical analysis for a ticker using pure pandas/numpy.

    Computes:
        - RSI (14-period)
        - MACD (12, 26, 9)
        - 50-day and 200-day simple moving averages + crossover detection
        - Bollinger Bands (20, 2)
        - Volume analysis (current vs 20-day average)

    Returns plain-English explanations suitable for beginners.
    """
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="1y")
        if hist.empty or len(hist) < 30:
            return {"status": "error", "ticker": ticker.upper(),
                    "error": "Insufficient historical data"}

        close = hist["Close"]
        volume = hist["Volume"]
        signals = []

        # --- RSI ---
        rsi_series = _compute_rsi(close, 14)
        rsi_val = round(float(rsi_series.iloc[-1]), 2)
        if rsi_val >= 70:
            rsi_signal = "OVERBOUGHT"
            rsi_explain = (f"RSI is {rsi_val} (above 70). The stock may be overheated — "
                           "it has risen a lot recently and could pull back.")
        elif rsi_val <= 30:
            rsi_signal = "OVERSOLD"
            rsi_explain = (f"RSI is {rsi_val} (below 30). The stock may be beaten down — "
                           "it could be due for a bounce.")
        else:
            rsi_signal = "NEUTRAL"
            rsi_explain = (f"RSI is {rsi_val} (between 30-70). "
                           "Momentum is in a normal range — no extreme signal.")

        # --- MACD ---
        macd_line, signal_line, histogram = _compute_macd(close, 12, 26, 9)
        macd_val = round(float(macd_line.iloc[-1]), 4)
        signal_val = round(float(signal_line.iloc[-1]), 4)
        hist_val = round(float(histogram.iloc[-1]), 4)

        # Check for recent crossover (last 3 bars)
        macd_cross = "NONE"
        for i in range(-3, 0):
            if len(histogram) >= abs(i) + 1:
                prev_h = histogram.iloc[i - 1]
                curr_h = histogram.iloc[i]
                if prev_h < 0 and curr_h >= 0:
                    macd_cross = "BULLISH_CROSS"
                elif prev_h > 0 and curr_h <= 0:
                    macd_cross = "BEARISH_CROSS"

        if macd_cross == "BULLISH_CROSS":
            macd_explain = ("MACD just crossed above its signal line — a bullish sign. "
                            "Think of it like short-term momentum turning positive.")
        elif macd_cross == "BEARISH_CROSS":
            macd_explain = ("MACD just crossed below its signal line — a bearish sign. "
                            "Short-term momentum is fading.")
        elif macd_val > signal_val:
            macd_explain = ("MACD is above the signal line — momentum is currently bullish, "
                            "but no fresh crossover in the last few days.")
        else:
            macd_explain = ("MACD is below the signal line — momentum is currently bearish, "
                            "but no fresh crossover in the last few days.")

        # --- Moving Averages ---
        ma50 = close.rolling(window=50).mean()
        ma200 = close.rolling(window=200).mean()
        ma50_val = round(float(ma50.iloc[-1]), 2) if len(ma50.dropna()) > 0 else None
        ma200_val = round(float(ma200.iloc[-1]), 2) if len(ma200.dropna()) > 0 else None

        ma_cross = "NONE"
        ma_explain = ""
        if ma50_val is not None and ma200_val is not None:
            # Check for golden/death cross in last 5 bars
            for i in range(-5, 0):
                if len(ma50.dropna()) >= abs(i) + 1 and len(ma200.dropna()) >= abs(i) + 1:
                    prev_50 = ma50.iloc[i - 1]
                    curr_50 = ma50.iloc[i]
                    prev_200 = ma200.iloc[i - 1]
                    curr_200 = ma200.iloc[i]
                    if not (np.isnan(prev_50) or np.isnan(prev_200)):
                        if prev_50 < prev_200 and curr_50 >= curr_200:
                            ma_cross = "GOLDEN_CROSS"
                        elif prev_50 > prev_200 and curr_50 <= curr_200:
                            ma_cross = "DEATH_CROSS"

            if ma_cross == "GOLDEN_CROSS":
                ma_explain = ("Golden Cross detected — the 50-day average crossed above the "
                              "200-day average. Historically a strong bullish signal.")
            elif ma_cross == "DEATH_CROSS":
                ma_explain = ("Death Cross detected — the 50-day average crossed below the "
                              "200-day average. This is often a warning of further declines.")
            elif ma50_val > ma200_val:
                ma_explain = (f"50-day MA (${ma50_val}) is above 200-day MA (${ma200_val}). "
                              "The overall trend is bullish.")
            else:
                ma_explain = (f"50-day MA (${ma50_val}) is below 200-day MA (${ma200_val}). "
                              "The overall trend is bearish.")
        else:
            ma_explain = "Not enough history to compute both 50-day and 200-day moving averages."

        # --- Bollinger Bands ---
        bb_upper, bb_middle, bb_lower = _compute_bollinger(close, 20, 2)
        last_close = float(close.iloc[-1])
        bb_upper_val = round(float(bb_upper.iloc[-1]), 2) if not np.isnan(bb_upper.iloc[-1]) else None
        bb_lower_val = round(float(bb_lower.iloc[-1]), 2) if not np.isnan(bb_lower.iloc[-1]) else None
        bb_middle_val = round(float(bb_middle.iloc[-1]), 2) if not np.isnan(bb_middle.iloc[-1]) else None

        bb_signal = "NEUTRAL"
        bb_explain = ""
        if bb_upper_val and bb_lower_val:
            bb_width = bb_upper_val - bb_lower_val
            if last_close >= bb_upper_val:
                bb_signal = "ABOVE_UPPER"
                bb_explain = ("Price is at or above the upper Bollinger Band — the stock is "
                              "stretched to the upside and may pull back.")
            elif last_close <= bb_lower_val:
                bb_signal = "BELOW_LOWER"
                bb_explain = ("Price is at or below the lower Bollinger Band — the stock is "
                              "stretched to the downside and may bounce.")
            else:
                bb_explain = ("Price is within the Bollinger Bands — no extreme reading. "
                              f"Trading range: ${bb_lower_val} to ${bb_upper_val}.")

            # Squeeze detection (narrow bands)
            if bb_middle_val and bb_middle_val > 0:
                bb_pct_width = bb_width / bb_middle_val
                if bb_pct_width < 0.05:
                    bb_explain += (" Bands are very tight (squeeze) — a big move may be coming.")
        else:
            bb_explain = "Not enough data to compute Bollinger Bands."

        # --- Volume ---
        vol_avg_20 = float(volume.rolling(window=20).mean().iloc[-1]) if len(volume) >= 20 else None
        vol_current = float(volume.iloc[-1])
        vol_ratio = round(vol_current / vol_avg_20, 2) if vol_avg_20 and vol_avg_20 > 0 else None

        if vol_ratio:
            if vol_ratio >= 2.0:
                vol_explain = (f"Volume is {vol_ratio}x the 20-day average — unusually heavy. "
                               "Big players may be making moves.")
            elif vol_ratio >= 1.5:
                vol_explain = (f"Volume is {vol_ratio}x the 20-day average — elevated. "
                               "More interest than usual.")
            elif vol_ratio <= 0.5:
                vol_explain = (f"Volume is only {vol_ratio}x the 20-day average — very light. "
                               "Not much conviction behind today's move.")
            else:
                vol_explain = f"Volume is {vol_ratio}x the 20-day average — within normal range."
        else:
            vol_explain = "Volume data unavailable or insufficient."

        return {
            "status": "ok",
            "ticker": ticker.upper(),
            "price": round(last_close, 2),
            "rsi": {"value": rsi_val, "signal": rsi_signal, "explain": rsi_explain},
            "macd": {
                "macd": macd_val, "signal": signal_val, "histogram": hist_val,
                "cross": macd_cross, "explain": macd_explain,
            },
            "moving_averages": {
                "ma50": ma50_val, "ma200": ma200_val,
                "cross": ma_cross, "explain": ma_explain,
            },
            "bollinger": {
                "upper": bb_upper_val, "middle": bb_middle_val, "lower": bb_lower_val,
                "signal": bb_signal, "explain": bb_explain,
            },
            "volume": {
                "current": int(vol_current),
                "avg_20d": int(vol_avg_20) if vol_avg_20 else None,
                "ratio": vol_ratio,
                "explain": vol_explain,
            },
        }
    except Exception as e:
        return {"status": "error", "ticker": ticker.upper(), "error": str(e)}


def get_short_interest(ticker: str) -> dict:
    """
    Retrieve short-interest data from yfinance info.

    Returns shortRatio, shortPercentOfFloat, and a squeeze-risk assessment.
    """
    try:
        tk = yf.Ticker(ticker)
        info = tk.info or {}

        short_ratio = info.get("shortRatio")
        short_pct = info.get("shortPercentOfFloat")
        shares_short = info.get("sharesShort")
        shares_outstanding = info.get("sharesOutstanding")
        float_shares = info.get("floatShares")

        # Convert short percent to a more readable number
        short_pct_display = round(short_pct * 100, 2) if short_pct else None

        # Squeeze risk assessment
        squeeze_risk = "LOW"
        squeeze_explain = ""
        if short_pct and short_ratio:
            if short_pct >= 0.20 and short_ratio >= 5:
                squeeze_risk = "HIGH"
                squeeze_explain = (
                    f"Short interest is very high ({short_pct_display}% of float, "
                    f"{short_ratio} days to cover). A short squeeze is a real possibility "
                    "if the stock starts rising — shorts could be forced to buy back shares, "
                    "accelerating the move up."
                )
            elif short_pct >= 0.10 or short_ratio >= 4:
                squeeze_risk = "MODERATE"
                squeeze_explain = (
                    f"Elevated short interest ({short_pct_display}% of float, "
                    f"{short_ratio} days to cover). Not extreme, but enough that a "
                    "strong rally could trigger some short covering."
                )
            else:
                squeeze_explain = (
                    f"Short interest is relatively low ({short_pct_display}% of float, "
                    f"{short_ratio} days to cover). Squeeze risk is minimal."
                )
        elif short_pct:
            if short_pct >= 0.20:
                squeeze_risk = "HIGH"
                squeeze_explain = f"Short percent of float is very high at {short_pct_display}%."
            elif short_pct >= 0.10:
                squeeze_risk = "MODERATE"
                squeeze_explain = f"Short percent of float is elevated at {short_pct_display}%."
            else:
                squeeze_explain = f"Short percent of float is {short_pct_display}% — low squeeze risk."
        else:
            squeeze_explain = "Short interest data not available for this ticker."

        return {
            "status": "ok",
            "ticker": ticker.upper(),
            "short_ratio": short_ratio,
            "short_pct_of_float": short_pct_display,
            "shares_short": shares_short,
            "float_shares": float_shares,
            "squeeze_risk": squeeze_risk,
            "explain": squeeze_explain,
        }
    except Exception as e:
        return {"status": "error", "ticker": ticker.upper(), "error": str(e)}


def detect_volume_anomalies(tickers: list) -> dict:
    """
    Scan a list of tickers for volume anomalies (2x+ the 20-day average).

    Returns a list of anomalies sorted by volume ratio (highest first).
    """
    try:
        anomalies = []
        errors = []

        for ticker in tickers:
            try:
                tk = yf.Ticker(ticker)
                hist = tk.history(period="1mo")
                if hist.empty or len(hist) < 5:
                    errors.append({"ticker": ticker, "error": "Insufficient data"})
                    time.sleep(0.5)
                    continue

                volume = hist["Volume"]
                vol_avg = float(volume.iloc[:-1].rolling(window=20, min_periods=5).mean().iloc[-1])
                vol_current = float(volume.iloc[-1])
                close = float(hist["Close"].iloc[-1])

                if vol_avg > 0:
                    ratio = round(vol_current / vol_avg, 2)
                    if ratio >= 2.0:
                        anomalies.append({
                            "ticker": ticker.upper(),
                            "volume": int(vol_current),
                            "avg_volume_20d": int(vol_avg),
                            "ratio": ratio,
                            "price": round(close, 2),
                            "explain": (
                                f"{ticker.upper()} traded {ratio}x its normal volume — "
                                "something is driving unusual interest. Check for news, "
                                "earnings, or institutional activity."
                            ),
                        })
            except Exception as inner_e:
                errors.append({"ticker": ticker, "error": str(inner_e)})
            time.sleep(0.5)

        anomalies.sort(key=lambda x: x["ratio"], reverse=True)

        return {
            "status": "ok",
            "anomalies": anomalies,
            "count": len(anomalies),
            "scanned": len(tickers),
            "errors": errors if errors else None,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def get_stocktwits_sentiment(ticker: str) -> dict:
    """
    Pull sentiment data from the StockTwits API for a given ticker.

    Computes bull/bear ratio and overall sentiment label.
    """
    try:
        url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker.upper()}.json"
        resp = requests.get(url, timeout=10)

        if resp.status_code != 200:
            return {
                "status": "error",
                "ticker": ticker.upper(),
                "error": f"StockTwits returned HTTP {resp.status_code}",
            }

        data = resp.json()
        messages = data.get("messages", [])

        bull = 0
        bear = 0
        total = len(messages)

        for msg in messages:
            sentiment = msg.get("entities", {}).get("sentiment")
            if sentiment:
                if sentiment.get("basic") == "Bullish":
                    bull += 1
                elif sentiment.get("basic") == "Bearish":
                    bear += 1

        if bear > 0:
            ratio = round(bull / bear, 2)
        else:
            ratio = float(bull) if bull > 0 else 0.0

        if bull + bear == 0:
            label = "NO_SENTIMENT"
            explain = "No tagged sentiment in recent messages — people are posting but not declaring bull or bear."
        elif ratio >= 3.0:
            label = "VERY_BULLISH"
            explain = (f"StockTwits crowd is overwhelmingly bullish ({bull} bulls vs {bear} bears). "
                       "Be cautious — extreme crowd optimism can sometimes precede pullbacks.")
        elif ratio >= 1.5:
            label = "BULLISH"
            explain = f"StockTwits leans bullish ({bull} bulls vs {bear} bears). Positive social sentiment."
        elif ratio >= 0.67:
            label = "MIXED"
            explain = f"StockTwits sentiment is mixed ({bull} bulls vs {bear} bears). No clear consensus."
        elif ratio >= 0.33:
            label = "BEARISH"
            explain = f"StockTwits leans bearish ({bull} bulls vs {bear} bears). Negative social sentiment."
        else:
            label = "VERY_BEARISH"
            explain = (f"StockTwits crowd is very bearish ({bull} bulls vs {bear} bears). "
                       "Extreme pessimism can sometimes signal a bottom — contrarian opportunity?")

        return {
            "status": "ok",
            "ticker": ticker.upper(),
            "bull": bull,
            "bear": bear,
            "total_messages": total,
            "bull_bear_ratio": ratio,
            "sentiment": label,
            "explain": explain,
        }
    except Exception as e:
        return {"status": "error", "ticker": ticker.upper(), "error": str(e)}


def get_crypto_onchain_data() -> dict:
    """
    Pull crypto market data from CoinGecko, fear & greed from alternative.me,
    and compute altcoin-season metrics.

    Tracked coins: Bitcoin, Ripple (XRP), Stellar (XLM), Cardano (ADA),
                   Hedera (HBAR).
    """
    try:
        coins = "bitcoin,ripple,stellar,cardano,hedera-hashgraph"
        cg_url = (
            "https://api.coingecko.com/api/v3/coins/markets"
            "?vs_currency=usd"
            f"&ids={coins}"
            "&order=market_cap_desc"
            "&per_page=10"
            "&page=1"
            "&sparkline=false"
            "&price_change_percentage=1h,24h,7d,30d"
        )
        headers = {"Accept": "application/json"}

        cg_resp = requests.get(cg_url, headers=headers, timeout=15)
        time.sleep(0.5)

        coin_data = []
        if cg_resp.status_code == 200:
            for c in cg_resp.json():
                coin_data.append({
                    "id": c.get("id"),
                    "symbol": c.get("symbol", "").upper(),
                    "name": c.get("name"),
                    "price": c.get("current_price"),
                    "market_cap": c.get("market_cap"),
                    "volume_24h": c.get("total_volume"),
                    "change_1h": c.get("price_change_percentage_1h_in_currency"),
                    "change_24h": c.get("price_change_percentage_24h_in_currency"),
                    "change_7d": c.get("price_change_percentage_7d_in_currency"),
                    "change_30d": c.get("price_change_percentage_30d_in_currency"),
                    "ath": c.get("ath"),
                    "ath_change_pct": c.get("ath_change_percentage"),
                })
        else:
            coin_data = None

        # Global market data
        time.sleep(0.5)
        global_data = {}
        try:
            g_resp = requests.get(
                "https://api.coingecko.com/api/v3/global",
                headers=headers, timeout=10,
            )
            if g_resp.status_code == 200:
                gd = g_resp.json().get("data", {})
                global_data = {
                    "total_market_cap_usd": gd.get("total_market_cap", {}).get("usd"),
                    "total_volume_24h_usd": gd.get("total_volume", {}).get("usd"),
                    "btc_dominance": round(gd.get("market_cap_percentage", {}).get("btc", 0), 2),
                    "eth_dominance": round(gd.get("market_cap_percentage", {}).get("eth", 0), 2),
                    "active_cryptos": gd.get("active_cryptocurrencies"),
                }
        except Exception:
            global_data = {"error": "Could not fetch global data"}

        # Fear & Greed Index
        time.sleep(0.5)
        fear_greed = {}
        try:
            fg_resp = requests.get(
                "https://api.alternative.me/fng/?limit=1", timeout=10,
            )
            if fg_resp.status_code == 200:
                fg_data = fg_resp.json().get("data", [{}])[0]
                fg_val = int(fg_data.get("value", 0))
                fg_class = fg_data.get("value_classification", "Unknown")
                fear_greed = {
                    "value": fg_val,
                    "classification": fg_class,
                    "explain": (
                        f"Crypto Fear & Greed Index is {fg_val}/100 ({fg_class}). "
                        + ("Extreme fear often signals buying opportunities — "
                           "people are panicking." if fg_val <= 25
                           else "Extreme greed often signals caution — "
                                "people may be overconfident." if fg_val >= 75
                           else "Sentiment is in a moderate zone.")
                    ),
                }
        except Exception:
            fear_greed = {"error": "Could not fetch Fear & Greed index"}

        # Altcoin season calculation
        # If majority of tracked altcoins outperform BTC over 30d, it is altcoin season
        altcoin_season = {}
        if coin_data:
            btc = next((c for c in coin_data if c["id"] == "bitcoin"), None)
            alts = [c for c in coin_data if c["id"] != "bitcoin"]
            if btc and btc.get("change_30d") is not None:
                btc_30d = btc["change_30d"]
                outperformers = [
                    a["symbol"] for a in alts
                    if a.get("change_30d") is not None and a["change_30d"] > btc_30d
                ]
                pct = round(len(outperformers) / len(alts) * 100, 1) if alts else 0
                if pct >= 75:
                    season = "ALTCOIN_SEASON"
                    season_explain = (
                        f"{pct}% of tracked alts are outperforming BTC over 30 days. "
                        "It is altcoin season — money is flowing into smaller coins."
                    )
                elif pct >= 50:
                    season = "LEANING_ALTS"
                    season_explain = (
                        f"{pct}% of tracked alts outperform BTC over 30 days. "
                        "Alts are gaining ground but it is not full altcoin season yet."
                    )
                else:
                    season = "BTC_DOMINANT"
                    season_explain = (
                        f"Only {pct}% of tracked alts outperform BTC over 30 days. "
                        "Bitcoin is leading — money prefers the safety of BTC."
                    )
                altcoin_season = {
                    "season": season,
                    "alt_outperform_pct": pct,
                    "outperformers": outperformers,
                    "btc_30d_change": round(btc_30d, 2),
                    "explain": season_explain,
                }

        return {
            "status": "ok",
            "coins": coin_data,
            "global": global_data,
            "fear_greed": fear_greed,
            "altcoin_season": altcoin_season,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def get_options_activity(ticker: str) -> dict:
    """
    Analyze options activity: put/call ratio and unusual activity detection.

    Uses yfinance option chain data for the nearest expiration.
    """
    try:
        tk = yf.Ticker(ticker)
        expirations = tk.options
        if not expirations:
            return {"status": "error", "ticker": ticker.upper(),
                    "error": "No options data available"}

        # Use nearest expiration
        exp = expirations[0]
        chain = tk.option_chain(exp)
        calls = chain.calls
        puts = chain.puts

        total_call_vol = int(calls["volume"].sum()) if "volume" in calls.columns else 0
        total_put_vol = int(puts["volume"].sum()) if "volume" in puts.columns else 0
        total_call_oi = int(calls["openInterest"].sum()) if "openInterest" in calls.columns else 0
        total_put_oi = int(puts["openInterest"].sum()) if "openInterest" in puts.columns else 0

        # Put/Call ratio by volume
        pc_ratio_vol = round(total_put_vol / total_call_vol, 2) if total_call_vol > 0 else None
        # Put/Call ratio by open interest
        pc_ratio_oi = round(total_put_oi / total_call_oi, 2) if total_call_oi > 0 else None

        # Interpret P/C ratio
        if pc_ratio_vol is not None:
            if pc_ratio_vol > 1.5:
                pc_signal = "VERY_BEARISH"
                pc_explain = (
                    f"Put/Call volume ratio is {pc_ratio_vol} — much more put buying than calls. "
                    "Traders are hedging or betting on a decline. However, extreme put buying "
                    "can sometimes be a contrarian bullish signal."
                )
            elif pc_ratio_vol > 1.0:
                pc_signal = "BEARISH"
                pc_explain = (
                    f"Put/Call volume ratio is {pc_ratio_vol} — slightly more puts than calls. "
                    "Leaning bearish, but not extreme."
                )
            elif pc_ratio_vol > 0.5:
                pc_signal = "NEUTRAL"
                pc_explain = (
                    f"Put/Call volume ratio is {pc_ratio_vol} — a healthy balance. "
                    "No strong directional bias from options traders."
                )
            else:
                pc_signal = "BULLISH"
                pc_explain = (
                    f"Put/Call volume ratio is {pc_ratio_vol} — heavy call buying. "
                    "Options traders are positioned for upside."
                )
        else:
            pc_signal = "NO_DATA"
            pc_explain = "Could not compute put/call ratio — no volume data."

        # Unusual activity detection: strikes with volume >> open interest
        unusual = []
        for label, df in [("CALL", calls), ("PUT", puts)]:
            if "volume" in df.columns and "openInterest" in df.columns:
                for _, row in df.iterrows():
                    vol = row.get("volume", 0) or 0
                    oi = row.get("openInterest", 0) or 0
                    if vol > 0 and oi > 0 and vol >= 5 * oi and vol >= 100:
                        unusual.append({
                            "type": label,
                            "strike": float(row["strike"]),
                            "volume": int(vol),
                            "open_interest": int(oi),
                            "vol_oi_ratio": round(vol / oi, 1),
                        })

        unusual.sort(key=lambda x: x.get("vol_oi_ratio", 0), reverse=True)
        unusual = unusual[:10]  # Top 10

        unusual_explain = ""
        if unusual:
            unusual_explain = (
                f"Found {len(unusual)} strikes with unusual activity (volume 5x+ open interest). "
                "This often signals big or informed bets being placed."
            )

        return {
            "status": "ok",
            "ticker": ticker.upper(),
            "expiration": exp,
            "total_call_volume": total_call_vol,
            "total_put_volume": total_put_vol,
            "total_call_oi": total_call_oi,
            "total_put_oi": total_put_oi,
            "pc_ratio_volume": pc_ratio_vol,
            "pc_ratio_oi": pc_ratio_oi,
            "pc_signal": pc_signal,
            "pc_explain": pc_explain,
            "unusual_activity": unusual,
            "unusual_explain": unusual_explain,
        }
    except Exception as e:
        return {"status": "error", "ticker": ticker.upper(), "error": str(e)}


def get_analyst_ratings(ticker: str) -> dict:
    """
    Pull analyst ratings and price targets from yfinance info.

    Returns recommendation, target prices, number of analysts, and explanation.
    """
    try:
        tk = yf.Ticker(ticker)
        info = tk.info or {}

        recommendation = info.get("recommendationKey", "").replace("_", " ").title()
        recommendation_mean = info.get("recommendationMean")
        target_high = info.get("targetHighPrice")
        target_low = info.get("targetLowPrice")
        target_mean = info.get("targetMeanPrice")
        target_median = info.get("targetMedianPrice")
        num_analysts = info.get("numberOfAnalystOpinions")
        current_price = info.get("currentPrice") or info.get("regularMarketPrice")

        # Upside/downside calculation
        upside = None
        if target_mean and current_price and current_price > 0:
            upside = round(((target_mean - current_price) / current_price) * 100, 2)

        # Build explanation
        parts = []
        if recommendation:
            parts.append(f"Wall Street consensus: {recommendation}.")
        if num_analysts:
            parts.append(f"Based on {num_analysts} analyst(s).")
        if target_mean and current_price:
            if upside and upside > 0:
                parts.append(
                    f"Average price target is ${target_mean:.2f}, implying {upside}% upside "
                    f"from the current ${current_price:.2f}."
                )
            elif upside and upside < 0:
                parts.append(
                    f"Average price target is ${target_mean:.2f}, implying {abs(upside)}% "
                    f"downside from the current ${current_price:.2f}."
                )
        if target_low and target_high:
            parts.append(f"Target range: ${target_low:.2f} (low) to ${target_high:.2f} (high).")

        explain = " ".join(parts) if parts else "No analyst rating data available for this ticker."

        # Recommendation mean scale: 1=Strong Buy, 2=Buy, 3=Hold, 4=Sell, 5=Strong Sell
        rating_scale = None
        if recommendation_mean:
            if recommendation_mean <= 1.5:
                rating_scale = "STRONG_BUY"
            elif recommendation_mean <= 2.5:
                rating_scale = "BUY"
            elif recommendation_mean <= 3.5:
                rating_scale = "HOLD"
            elif recommendation_mean <= 4.5:
                rating_scale = "SELL"
            else:
                rating_scale = "STRONG_SELL"

        return {
            "status": "ok",
            "ticker": ticker.upper(),
            "recommendation": recommendation,
            "recommendation_mean": recommendation_mean,
            "rating_scale": rating_scale,
            "target_high": target_high,
            "target_low": target_low,
            "target_mean": target_mean,
            "target_median": target_median,
            "num_analysts": num_analysts,
            "current_price": current_price,
            "upside_pct": upside,
            "explain": explain,
        }
    except Exception as e:
        return {"status": "error", "ticker": ticker.upper(), "error": str(e)}


def get_macro_indicators() -> dict:
    """
    Pull key macroeconomic indicators from the FRED CSV API.

    - 10-Year Treasury Yield (DGS10)
    - 2-Year Treasury Yield (DGS2)
    - Yield curve spread (10Y - 2Y)
    - Oil price war premium calculation (baseline $64.56)

    No API key required for the CSV observation endpoint.
    """
    try:
        fred_base = "https://fred.stlouisfed.org/graph/fredgraph.csv"
        today = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        def _fetch_fred(series_id: str):
            """Fetch the latest value from FRED CSV API."""
            url = f"{fred_base}?id={series_id}&cosd={start}&coed={today}"
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                return None
            lines = resp.text.strip().split("\n")
            # Walk backwards to find the latest non-empty, non-'.' value
            for line in reversed(lines[1:]):
                parts = line.split(",")
                if len(parts) >= 2 and parts[1].strip() not in ("", "."):
                    try:
                        return float(parts[1].strip())
                    except ValueError:
                        continue
            return None

        yield_10y = _fetch_fred("DGS10")
        time.sleep(0.5)
        yield_2y = _fetch_fred("DGS2")
        time.sleep(0.5)

        # Yield curve spread
        spread = None
        yield_explain = ""
        if yield_10y is not None and yield_2y is not None:
            spread = round(yield_10y - yield_2y, 2)
            if spread < 0:
                yield_explain = (
                    f"The yield curve is INVERTED (10Y {yield_10y}% - 2Y {yield_2y}% = "
                    f"{spread}%). An inverted yield curve has historically preceded recessions. "
                    "It means investors expect economic trouble ahead and are demanding more "
                    "for short-term lending than long-term."
                )
            elif spread < 0.5:
                yield_explain = (
                    f"The yield curve is FLAT (10Y {yield_10y}% - 2Y {yield_2y}% = "
                    f"{spread}%). A flat curve suggests uncertainty about economic growth. "
                    "The bond market is not clearly signaling expansion or recession."
                )
            else:
                yield_explain = (
                    f"The yield curve is NORMAL (10Y {yield_10y}% - 2Y {yield_2y}% = "
                    f"+{spread}%). A healthy positive spread signals the bond market "
                    "expects continued economic growth."
                )
        else:
            yield_explain = "Could not retrieve Treasury yields from FRED."

        # Oil price — use FRED WTI (DCOILWTICO)
        oil_price = _fetch_fred("DCOILWTICO")
        time.sleep(0.5)

        oil_baseline = 64.56  # Baseline price for war premium calculation
        oil_premium = None
        oil_explain = ""
        if oil_price is not None:
            oil_premium = round(oil_price - oil_baseline, 2)
            oil_pct = round((oil_premium / oil_baseline) * 100, 2)
            if oil_premium > 15:
                oil_explain = (
                    f"Oil is at ${oil_price:.2f}/barrel, a ${oil_premium} premium "
                    f"({oil_pct}%) above the ${oil_baseline} baseline. This is a significant "
                    "geopolitical/war premium — elevated energy costs act as a tax on consumers "
                    "and businesses, dragging on economic growth."
                )
            elif oil_premium > 5:
                oil_explain = (
                    f"Oil is at ${oil_price:.2f}/barrel, a ${oil_premium} premium "
                    f"({oil_pct}%) above the ${oil_baseline} baseline. A moderate premium — "
                    "some geopolitical risk is priced in but not extreme."
                )
            elif oil_premium > 0:
                oil_explain = (
                    f"Oil is at ${oil_price:.2f}/barrel, only ${oil_premium} above the "
                    f"${oil_baseline} baseline ({oil_pct}%). Minimal war premium — "
                    "energy markets are relatively calm."
                )
            else:
                oil_explain = (
                    f"Oil is at ${oil_price:.2f}/barrel, actually ${abs(oil_premium)} "
                    f"BELOW the ${oil_baseline} baseline. No war premium — "
                    "energy prices are suppressed, which generally helps consumers."
                )
        else:
            oil_explain = "Could not retrieve oil price data from FRED."

        return {
            "status": "ok",
            "treasury": {
                "yield_10y": yield_10y,
                "yield_2y": yield_2y,
                "spread": spread,
                "explain": yield_explain,
            },
            "oil": {
                "price": oil_price,
                "baseline": oil_baseline,
                "war_premium": oil_premium,
                "explain": oil_explain,
            },
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
