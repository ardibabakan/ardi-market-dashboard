"""
Push notification sender via ntfy.sh.
Sends alerts to Ardi's iPhone.
"""
import requests
import logging

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import NTFY_TOPIC

logger = logging.getLogger("ardi.ntfy")

NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"

def send_alert(title: str, message: str, priority: str = "default",
               tags: list = None):
    """
    Send a push notification.
    priority: min, low, default, high, urgent
    tags: emoji tags like ["warning"], ["rotating_light"], ["chart_with_upwards_trend"]
    """
    if not NTFY_TOPIC:
        logger.warning("NTFY_TOPIC not set — alert not sent")
        return False

    headers = {
        "Title": title,
        "Priority": priority,
    }
    if tags:
        headers["Tags"] = ",".join(tags)

    try:
        response = requests.post(NTFY_URL, data=message.encode("utf-8"), headers=headers)
        if response.status_code == 200:
            logger.info(f"Alert sent: {title}")
            return True
        else:
            logger.error(f"ntfy returned {response.status_code}: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Failed to send alert: {e}")
        return False

def send_danger_alert(signal_name: str, details: str):
    """Red alert — danger signal fired."""
    send_alert(
        title=f"DANGER SIGNAL: {signal_name}",
        message=f"{details}\n\nDo NOT trade. If positions are open, call Fidelity: 800-343-3548",
        priority="urgent",
        tags=["rotating_light", "warning"]
    )

def send_ceasefire_alert(signal_name: str, count: int):
    """Blue alert — ceasefire signal fired."""
    send_alert(
        title=f"CEASEFIRE SIGNAL: {signal_name}",
        message=f"Signal count: {count}/6\n{'BUY DAL + RCL NOW' if count >= 2 else 'Watching — need 2 to trigger Phase B'}",
        priority="high" if count >= 2 else "default",
        tags=["blue_circle"]
    )

def send_stop_loss_alert(ticker: str, current: float, stop: float):
    """Amber alert — stop loss hit."""
    send_alert(
        title=f"STOP LOSS: {ticker}",
        message=f"{ticker} at ${current:.2f} — below stop loss of ${stop:.2f}\nReview position immediately.",
        priority="high",
        tags=["warning"]
    )

def send_opportunity_alert(ticker: str, reason: str):
    """Green alert — opportunity detected."""
    send_alert(
        title=f"OPPORTUNITY: {ticker}",
        message=reason,
        priority="default",
        tags=["chart_with_upwards_trend"]
    )

def send_system_health(message: str, ok: bool = True):
    """System health notification."""
    if ok:
        logger.info(f"System health OK: {message}")
    else:
        send_alert(
            title="SYSTEM ISSUE",
            message=message,
            priority="high",
            tags=["warning"]
        )
