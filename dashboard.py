#!/usr/bin/env python3
"""
ARDI MARKET DASHBOARD — World-Aware Edition
Streamlit web app with 6 tabs, stop loss/profit alerts,
conflict phase tracker, mobile responsive.
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json
import os
import glob
import re
from datetime import datetime, date, timedelta
import pytz
import requests

# ── Page config ──────────────────────────────────────────────
st.set_page_config(
    page_title="Ardi Market Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Mobile-friendly CSS
st.markdown("""<style>
    .block-container {padding-top: 1rem; padding-bottom: 1rem;}
    [data-testid="stMetricValue"] {font-size: 1.1rem;}
    .stTabs [data-baseweb="tab"] {font-size: 1rem; padding: 8px 16px;}
    @media (max-width: 768px) {
        .block-container {padding-left: 0.5rem; padding-right: 0.5rem;}
        [data-testid="stMetricValue"] {font-size: 0.95rem;}
        h1 {font-size: 1.5rem !important;}
        h2 {font-size: 1.2rem !important;}
    }
</style>""", unsafe_allow_html=True)

# ── Constants ────────────────────────────────────────────────
PACIFIC = pytz.timezone("America/Los_Angeles")
NOW = datetime.now(PACIFIC)
TODAY_STR = NOW.strftime("%Y-%m-%d")
TODAY_DISPLAY = NOW.strftime("%A, %B %d, %Y")
TIME_DISPLAY = NOW.strftime("%I:%M %p Pacific")
WAR_START = date(2026, 2, 28)
DAYS_SINCE_WAR = (NOW.date() - WAR_START).days
PRE_CONFLICT_OIL = 64.56
ENTRY_DATE = date(2026, 3, 13)
LTCG_DATE = date(2027, 3, 13)
LTCG_DAYS = (LTCG_DATE - NOW.date()).days

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DAILY_DIR = os.path.join(BASE_DIR, "Daily")
FOUNDATION_PATH = os.path.join(BASE_DIR, "AGENT_9_FOUNDATION_PATCH.json")

PORTFOLIO_TICKERS = ["LMT", "RTX", "LNG", "GLD", "ITA", "XOM", "CEG", "BAESY"]
WATCH_TICKERS = ["DAL", "RCL"]

FOMC_DATES = [
    date(2026, 1, 28), date(2026, 3, 18), date(2026, 5, 6), date(2026, 6, 17),
    date(2026, 7, 29), date(2026, 9, 16), date(2026, 11, 4), date(2026, 12, 16),
]

# ── Helpers ──────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_foundation():
    if os.path.exists(FOUNDATION_PATH):
        with open(FOUNDATION_PATH) as f:
            return json.load(f)
    return None


def find_latest_daily(prefix):
    pattern = os.path.join(DAILY_DIR, f"{prefix}*.md")
    files = sorted(glob.glob(pattern), reverse=True)
    return files[0] if files else None


def load_daily_md(prefix):
    path_today = os.path.join(DAILY_DIR, f"{prefix}{TODAY_STR}.md")
    if os.path.exists(path_today):
        with open(path_today) as f:
            return f.read(), False
    latest = find_latest_daily(prefix)
    if latest:
        with open(latest) as f:
            return f.read(), True
    return None, True


@st.cache_data(ttl=120)
def pull_prices(tickers, period="1mo"):
    try:
        data = yf.download(tickers, period=period, progress=False, auto_adjust=True, threads=True)
        return data
    except Exception:
        return None


@st.cache_data(ttl=120)
def pull_single(ticker, period="5d"):
    try:
        tk = yf.Ticker(ticker)
        h = tk.history(period=period)
        if len(h) > 0:
            return round(float(h["Close"].iloc[-1]), 2)
    except Exception:
        pass
    return None


@st.cache_data(ttl=300)
def pull_crypto():
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "bitcoin,ripple,stellar,cardano,hedera-hashgraph",
                    "vs_currencies": "usd", "include_24hr_change": "true"},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


@st.cache_data(ttl=300)
def pull_crypto_global():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global", timeout=10)
        if r.status_code == 200:
            return r.json().get("data", {})
    except Exception:
        pass
    return None


def make_sparkline(series, color="deepskyblue", height=80):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        y=series.values, x=list(range(len(series))),
        mode="lines", line=dict(color=color, width=2),
        fill="tozeroy", fillcolor="rgba(0,191,255,0.08)",
    ))
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0), height=height,
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def conflict_phase():
    if DAYS_SINCE_WAR <= 0:
        return "Pre-conflict", "gray"
    elif DAYS_SINCE_WAR < 21:
        return f"Day {DAYS_SINCE_WAR} — Still in bottom window (expect Day 21)", "#e67e22"
    elif DAYS_SINCE_WAR <= 42:
        return f"Day {DAYS_SINCE_WAR} — Past typical bottom, recovery phase", "#27ae60"
    else:
        return f"Day {DAYS_SINCE_WAR} — Extended conflict", "#3498db"


def next_fomc():
    for fd in FOMC_DATES:
        if fd >= NOW.date():
            return fd, (fd - NOW.date()).days
    return None, None


# ── Load foundation data ────────────────────────────────────
foundation = load_foundation()
if foundation is None:
    st.error("Foundation file not found. Run Agent 9 first.")
    st.stop()

positions = foundation["step2_portfolio"]["positions"]
cash_reserve = foundation["step2_portfolio"]["cash_remaining"]
earnings_data = foundation["step3_earnings"]
crypto_baseline = foundation["step7_crypto"]

entry_map = {}
for t in PORTFOLIO_TICKERS:
    p = positions[t]
    entry_map[t] = {
        "entry": p["current_price"],
        "shares": p["shares_to_buy"],
        "cost": p["total_cost"],
        "name": p["full_name"],
        "desc": p["description"],
        "stop_loss": round(p["current_price"] * 0.85, 2),
        "profit_target": round(p["current_price"] * 1.25, 2),
    }

# ── Pull live prices ─────────────────────────────────────────
all_tickers = PORTFOLIO_TICKERS + WATCH_TICKERS
hist_data = pull_prices(all_tickers, period="1mo")

live = {}
for t in all_tickers:
    try:
        if hist_data is not None and isinstance(hist_data.columns, pd.MultiIndex):
            close = hist_data["Close"][t].dropna()
        elif hist_data is not None:
            close = hist_data["Close"].dropna()
        else:
            close = pd.Series()
        if len(close) > 0:
            live[t] = {"price": round(float(close.iloc[-1]), 2), "series": close}
        else:
            live[t] = {"price": entry_map.get(t, {}).get("entry", 0), "series": pd.Series()}
    except Exception:
        live[t] = {"price": entry_map.get(t, {}).get("entry", 0), "series": pd.Series()}

# Macro
vix_val = pull_single("^VIX")
vix3m_val = pull_single("^VIX3M")
oil_val = pull_single("CL=F")
sp_val = pull_single("^GSPC")
tlt_val = pull_single("TLT")

# Oil previous day
oil_prev = None
try:
    oil_hist = yf.Ticker("CL=F").history(period="5d")
    if len(oil_hist) >= 2:
        oil_prev = round(float(oil_hist["Close"].iloc[-2]), 2)
except Exception:
    pass

# ── Portfolio calculations ───────────────────────────────────
total_entry = sum(entry_map[t]["cost"] for t in PORTFOLIO_TICKERS)
total_current = sum(live[t]["price"] * entry_map[t]["shares"] for t in PORTFOLIO_TICKERS)
total_gl = total_current - total_entry
total_pct = (total_gl / total_entry * 100) if total_entry > 0 else 0
portfolio_val = total_current + cash_reserve

# ── Compute signals ──────────────────────────────────────────
ceasefire_signals = []
ceasefire_fired = 0

# Oil drop
oil_chg = 0
if oil_val and oil_prev and oil_prev > 0:
    oil_chg = ((oil_val - oil_prev) / oil_prev) * 100
    fired = oil_chg <= -3
    ceasefire_signals.append(("Oil dropped 3%+ in one day", fired, f"Oil changed {oil_chg:+.1f}% today"))
    if fired: ceasefire_fired += 1
else:
    ceasefire_signals.append(("Oil dropped 3%+ in one day", False, "Data unavailable"))

# VIX < 20
if vix_val is not None:
    fired = vix_val < 20
    ceasefire_signals.append(("Fear index (VIX) below 20", fired, f"VIX at {vix_val:.1f}"))
    if fired: ceasefire_fired += 1
else:
    ceasefire_signals.append(("Fear index (VIX) below 20", False, "Unavailable"))

# VIX term structure
if vix_val and vix3m_val:
    fired = vix_val > vix3m_val
    label = "Backwardation — near-term resolution expected" if fired else "Contango — normal"
    ceasefire_signals.append(("VIX term structure ceasefire signal", fired,
                              f"VIX {vix_val:.1f} vs VIX3M {vix3m_val:.1f} — {label}"))
    if fired: ceasefire_fired += 1
else:
    ceasefire_signals.append(("VIX term structure ceasefire signal", False, "Unavailable"))

ceasefire_signals.append(("Iranian FM uses peace language", None, "MANUAL CHECK"))
ceasefire_signals.append(("Mediator country announces talks", None, "MANUAL CHECK"))
ceasefire_signals.append(("Trump makes clear peace statement", None, "MANUAL CHECK"))

escalation_signals = []
escalation_fired = 0

if oil_val and oil_prev and oil_prev > 0:
    fired = oil_chg >= 10
    escalation_signals.append(("Oil spiked 10%+ in one day", fired, f"Oil {oil_chg:+.1f}%"))
    if fired: escalation_fired += 1
else:
    escalation_signals.append(("Oil spiked 10%+ in one day", False, "Unavailable"))

if vix_val is not None:
    fired = vix_val > 40
    escalation_signals.append(("Fear index (VIX) above 40", fired, f"VIX {vix_val:.1f}"))
    if fired: escalation_fired += 1
else:
    escalation_signals.append(("Fear index (VIX) above 40", False, "Unavailable"))

escalation_signals.append(("Iran nuclear announcement", None, "MANUAL CHECK"))
escalation_signals.append(("China moves on Taiwan", None, "MANUAL CHECK"))
escalation_signals.append(("US carrier attacked", None, "MANUAL CHECK"))

# ── Action from daily file ───────────────────────────────────
daily_content, daily_stale = load_daily_md("STOCKS_")
action_text = "HOLD EVERYTHING. No trades needed today."
action_color = "green"

if daily_content:
    for line in daily_content.split("\n"):
        if "TODAY'S ACTION" in line.upper():
            idx = daily_content.index(line)
            for nl in daily_content[idx:].split("\n")[1:5]:
                stripped = nl.strip().strip("#").strip()
                if stripped and len(stripped) > 10:
                    action_text = stripped
                    break
            break

if "BLACK SWAN" in action_text.upper() or "DANGER" in action_text.upper() or "DO NOT TRADE" in action_text.upper():
    action_color = "red"
elif "STOP LOSS" in action_text.upper():
    action_color = "red"
elif "BUY" in action_text.upper() or "OPPORTUNITY" in action_text.upper():
    action_color = "blue"
elif "REVIEW" in action_text.upper() or "WARNING" in action_text.upper() or "EARNINGS" in action_text.upper():
    action_color = "orange"

# ── Stop loss / profit target checks ─────────────────────────
alerts = []
for t in PORTFOLIO_TICKERS:
    e = entry_map[t]
    cp = live[t]["price"]
    if cp <= e["stop_loss"]:
        alerts.append(("STOP_LOSS", t, e, cp))
    elif cp >= e["profit_target"]:
        alerts.append(("PROFIT_TARGET", t, e, cp))


# ══════════════════════════════════════════════════════════════
# RENDER
# ══════════════════════════════════════════════════════════════

# Refresh + auto-refresh
col_hdr1, col_hdr2 = st.columns([9, 1])
with col_hdr2:
    if st.button("Refresh"):
        st.cache_data.clear()
        st.rerun()

st.markdown('<meta http-equiv="refresh" content="3600">', unsafe_allow_html=True)

# Header
st.markdown("# Good morning Ardi")
st.caption(f"Data updated daily at 3 AM Pacific | Last updated: {TODAY_DISPLAY}")
st.markdown(f"**{TODAY_DISPLAY}** | {TIME_DISPLAY}")

# Conflict phase indicator
phase_text, phase_color = conflict_phase()
st.markdown(
    f'<div style="background:{phase_color};color:white;padding:8px 16px;border-radius:8px;'
    f'font-size:15px;margin:4px 0 8px 0;display:inline-block">'
    f'Iran Conflict — {phase_text}</div>',
    unsafe_allow_html=True,
)

if daily_stale:
    st.info("Today's report not ready yet (generates at 3 AM Pacific). Showing most recent data.")

# Portfolio headline
st.markdown(
    f'<h2 style="margin-bottom:0">Portfolio: <span style="color:{"#2ecc71" if total_gl >= 0 else "#e74c3c"}">'
    f'${portfolio_val:,.2f}</span></h2>',
    unsafe_allow_html=True,
)
sign = "+" if total_gl >= 0 else ""
st.markdown(f"Invested: ${total_entry:,.2f} | Change: **{sign}${total_gl:,.2f}** ({sign}{total_pct:.1f}%) | Cash: ${cash_reserve:,.2f}")

# Action box
box_colors = {"green": "#27ae60", "blue": "#2980b9", "red": "#c0392b", "orange": "#e67e22"}
bg = box_colors.get(action_color, "#27ae60")
st.markdown(
    f'<div style="background:{bg};color:white;padding:16px 20px;border-radius:10px;'
    f'font-size:17px;margin:12px 0 20px 0"><strong>TODAY\'S ACTION:</strong> {action_text}</div>',
    unsafe_allow_html=True,
)

# Stop loss / profit alerts
for alert_type, ticker, edata, current_price in alerts:
    if alert_type == "STOP_LOSS":
        st.error(
            f"STOP LOSS HIT — {ticker} ({edata['name']}) is at ${current_price:.2f}, "
            f"below your ${edata['stop_loss']:.2f} stop loss. "
            f"You paid ${edata['entry']:.2f}. Consider selling on Fidelity."
        )
    else:
        st.success(
            f"PROFIT TARGET — {ticker} ({edata['name']}) hit ${current_price:.2f}, "
            f"above your ${edata['profit_target']:.2f} target! "
            f"Consider selling half to lock in gains."
        )

# ── 6 Tabs ───────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "My Stocks", "War Signals", "Opportunities", "Momentum", "My Crypto", "World Events"
])

# ══════════════════════════════════════════════════════════════
# TAB 1 — MY STOCKS
# ══════════════════════════════════════════════════════════════
with tab1:
    st.subheader("Your 8 Positions")

    for row_start in range(0, 8, 2):
        cols = st.columns(2)
        for ci, idx in enumerate(range(row_start, min(row_start + 2, 8))):
            t = PORTFOLIO_TICKERS[idx]
            e = entry_map[t]
            cp = live[t]["price"]
            gl_d = round(cp * e["shares"] - e["cost"], 2)
            gl_p = round((gl_d / e["cost"]) * 100, 1) if e["cost"] > 0 else 0

            # Badge logic
            badge_text, badge_color = "HOLD", "#27ae60"
            if cp <= e["stop_loss"]:
                badge_text, badge_color = "STOP LOSS", "#c0392b"
            elif cp >= e["profit_target"]:
                badge_text, badge_color = "TAKE PROFIT", "#f39c12"
            elif gl_p <= -15:
                badge_text, badge_color = "REVIEW", "#e74c3c"
            elif gl_p <= -10:
                badge_text, badge_color = "MONITOR", "#e67e22"
            elif gl_p >= 20:
                badge_text, badge_color = "STRONG", "#2ecc71"

            with cols[ci]:
                st.markdown(
                    f'<span style="background:{badge_color};color:white;padding:3px 10px;'
                    f'border-radius:12px;font-size:13px;float:right">{badge_text}</span>',
                    unsafe_allow_html=True,
                )
                st.markdown(f"**{t}** — {e['name']}")
                st.caption(e["desc"])

                mc1, mc2, mc3 = st.columns(3)
                mc1.metric("Entry", f"${e['entry']:.2f}")
                mc2.metric("Now", f"${cp:.2f}")
                delta_str = f"{'+' if gl_d >= 0 else ''}${gl_d:.2f} ({'+' if gl_p >= 0 else ''}{gl_p:.1f}%)"
                mc3.metric("P/L", delta_str)

                # Stop loss / profit target line
                st.caption(f"Stop loss: ${e['stop_loss']:.2f} | Profit target: ${e['profit_target']:.2f}")

                series = live[t].get("series", pd.Series())
                if len(series) > 2:
                    line_color = "#2ecc71" if gl_d >= 0 else "#e74c3c"
                    st.plotly_chart(make_sparkline(series, color=line_color),
                                    use_container_width=True, key=f"spark_{t}")

                with st.expander("30 / 90 day outlook"):
                    if t in ["LMT", "RTX", "ITA", "BAESY"]:
                        st.write(f"**30d:** ${cp*1.03:.2f}–${cp*1.08:.2f} (defense demand high during conflict)")
                        st.write(f"**90d:** ${cp*1.08:.2f}–${cp*1.15:.2f} (elevated military spending)")
                    elif t in ["XOM", "LNG"]:
                        st.write(f"**30d:** ${cp*0.97:.2f}–${cp*1.05:.2f} (oil volatile around war premium)")
                        st.write(f"**90d:** ${cp*0.90:.2f}–${cp*1.10:.2f} (depends on ceasefire)")
                    elif t == "GLD":
                        st.write(f"**30d:** ${cp*1.02:.2f}–${cp*1.07:.2f} (gold rises with uncertainty)")
                        st.write(f"**90d:** ${cp*1.05:.2f}–${cp*1.12:.2f} (safe haven bid)")
                    elif t == "CEG":
                        st.write(f"**30d:** ${cp*0.95:.2f}–${cp*1.08:.2f} (nuclear volatile)")
                        st.write(f"**90d:** ${cp*1.05:.2f}–${cp*1.20:.2f} (AI power demand)")

                # Earnings
                earn = earnings_data.get(t, {})
                ed = earn.get("next_earnings")
                if ed and ed not in ["Not available", "Error"]:
                    try:
                        edate = datetime.strptime(ed, "%Y-%m-%d").date()
                        days_to = (edate - NOW.date()).days
                        if 0 < days_to <= 7:
                            st.error(f"URGENT: Earnings in {days_to} days ({ed})")
                        elif 0 < days_to <= 21:
                            st.warning(f"Earnings in {days_to} days ({ed})")
                        elif days_to > 0:
                            st.caption(f"Earnings: {ed} ({days_to} days)")
                        else:
                            st.caption(f"Last reported: {ed}")
                    except Exception:
                        pass

                st.markdown("---")

    # Tax tracking
    st.caption(f"Tax note: Hold all positions until March 13, 2027 ({LTCG_DAYS} days) for lower long-term capital gains rate.")

    # Watchlist
    st.subheader("Waiting to Buy (Phase B)")
    wc1, wc2 = st.columns(2)
    for i, t in enumerate(WATCH_TICKERS):
        p = positions.get(t, {})
        cp = live[t]["price"]
        with [wc1, wc2][i]:
            st.markdown(f"**{t}** — {p.get('full_name', t)}")
            st.caption(p.get("description", ""))
            st.metric("Price now", f"${cp:.2f}")
            st.info(f"WAITING — Buy when 2+ ceasefire signals fire. Currently {ceasefire_fired}/6.")

    # FOMC
    fomc_date, fomc_days = next_fomc()
    if fomc_date and fomc_days is not None and fomc_days <= 14:
        st.warning(f"Fed meeting in {fomc_days} days ({fomc_date}). Rate cut = buy more. Rate hike = hold cash.")

    # Correlation check
    defense_tickers = ["LMT", "RTX", "ITA"]
    defense_changes = []
    for dt in defense_tickers:
        e = entry_map.get(dt)
        if e and e["cost"] > 0:
            cp = live[dt]["price"]
            pct = round((cp * e["shares"] - e["cost"]) / e["cost"] * 100, 1)
            defense_changes.append((dt, pct))
    if len(defense_changes) == 3:
        all_same = all(c[1] >= 0 for c in defense_changes) or all(c[1] < 0 for c in defense_changes)
        if all_same and any(abs(c[1]) > 1 for c in defense_changes):
            direction = "up" if defense_changes[0][1] >= 0 else "down"
            st.info(
                f"Defence stocks moved together ({direction}): "
                + ", ".join(f"{c[0]} {c[1]:+.1f}%" for c in defense_changes)
                + " — This is normal, they are related."
            )

    # Portfolio chart
    st.subheader("Portfolio Value Over Time")
    if hist_data is not None:
        try:
            port_series = None
            for t in PORTFOLIO_TICKERS:
                shares = entry_map[t]["shares"]
                if isinstance(hist_data.columns, pd.MultiIndex):
                    s = hist_data["Close"][t].dropna() * shares
                else:
                    s = hist_data["Close"].dropna() * shares
                port_series = s if port_series is None else port_series.add(s, fill_value=0)
            if port_series is not None:
                port_series = port_series + cash_reserve
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=port_series.index, y=port_series.values,
                    mode="lines", fill="tozeroy",
                    line=dict(color="#2ecc71" if total_gl >= 0 else "#e74c3c", width=2),
                    fillcolor="rgba(46,204,113,0.1)" if total_gl >= 0 else "rgba(231,76,60,0.1)",
                ))
                fig.add_hline(y=10000, line_dash="dash", line_color="gray",
                              annotation_text="$10,000 starting value")
                fig.update_layout(
                    height=300, margin=dict(l=0, r=0, t=20, b=0),
                    yaxis_title="Portfolio ($)",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig, use_container_width=True)
        except Exception:
            st.caption("Could not generate portfolio chart.")


# ══════════════════════════════════════════════════════════════
# TAB 2 — WAR SIGNALS
# ══════════════════════════════════════════════════════════════
with tab2:
    phase_text_t, phase_color_t = conflict_phase()
    st.subheader(f"War Signal Tracker — {phase_text_t}")
    st.caption("Iran-US-Israel conflict started February 28, 2026")

    left, right = st.columns(2)

    with left:
        st.markdown("### Ceasefire Signals")
        st.progress(min(ceasefire_fired / 6, 1.0))
        st.caption(f"{ceasefire_fired} of 6 signals fired")

        for name, fired, detail in ceasefire_signals:
            if fired is True:
                st.markdown(f"🟢 **{name}**")
            elif fired is False:
                st.markdown(f"⚪ {name}")
            else:
                st.markdown(f"🔵 {name}")
            st.caption(f"   {detail}")

        # Perplexity search buttons for manual checks
        st.markdown("**Manual checks — search on Perplexity:**")
        perplexity_searches = [
            ("Iranian FM peace language", "Iranian+foreign+minister+peace+ceasefire+statement+today"),
            ("Mediator country announced", "Iran+US+ceasefire+mediator+country+today"),
            ("Trump peace statement", "Trump+Iran+ceasefire+peace+statement+today"),
        ]
        for label, query in perplexity_searches:
            st.markdown(f"[Search: {label}](https://www.perplexity.ai/search?q={query})")

        st.info("Buy DAL + RCL when 2 or more signals fire.")

    with right:
        st.markdown("### Danger Signals")
        st.progress(min(escalation_fired / 5, 1.0) if escalation_fired > 0 else 0.0)
        st.caption(f"{escalation_fired} of 5 signals fired")

        for name, fired, detail in escalation_signals:
            if fired is True:
                st.markdown(f"🔴 **{name}**")
            elif fired is False:
                st.markdown(f"⚪ {name}")
            else:
                st.markdown(f"🔵 {name}")
            st.caption(f"   {detail}")

        if escalation_fired > 0:
            st.error("DANGER SIGNAL FIRED. Call Fidelity: 800-343-3548")
        else:
            st.success("No danger signals. Positions safe.")

    # Key numbers
    st.markdown("---")
    st.subheader("Key Market Numbers")
    k1, k2, k3, k4 = st.columns(4)

    with k1:
        if oil_val:
            premium = round(oil_val - PRE_CONFLICT_OIL, 2)
            prem_pct = round((premium / PRE_CONFLICT_OIL) * 100, 1)
            st.metric("Oil", f"${oil_val:.2f}", f"+${premium:.2f} war premium")
        else:
            st.metric("Oil", "N/A")

    with k2:
        if vix_val is not None:
            labels = {15: "Calm", 20: "Slightly worried", 30: "Worried", 40: "Very worried"}
            vl = "PANIC"
            for thresh, lab in sorted(labels.items()):
                if vix_val < thresh:
                    vl = lab
                    break
            st.metric("VIX", f"{vix_val:.1f}", vl)
        else:
            st.metric("VIX", "N/A")

    with k3:
        if sp_val:
            st.metric("S&P 500", f"{sp_val:,.0f}")
        else:
            st.metric("S&P 500", "N/A")

    with k4:
        if tlt_val:
            st.metric("Bonds (TLT)", f"${tlt_val:.2f}")
            if tlt_val < 85:
                st.caption("Falling — possible petrodollar disruption")
        else:
            st.metric("Bonds", "N/A")

    # Oil analysis
    if oil_val:
        st.markdown("---")
        st.subheader("Oil Market Analysis")
        premium = oil_val - PRE_CONFLICT_OIL
        cf_low = round(oil_val - premium * 0.80, 2)
        cf_high = round(oil_val - premium * 0.60, 2)
        st.markdown(
            f"Oil at **${oil_val:.2f}**. Pre-war: ~${PRE_CONFLICT_OIL}. "
            f"War premium: **${premium:.2f}**. "
            f"After ceasefire (Gulf War analog): **${cf_low:.2f}–${cf_high:.2f}**. "
            f"When oil drops: XOM falls, DAL and RCL rise."
        )

    # FOMC
    fomc_d, fomc_dy = next_fomc()
    if fomc_d:
        st.markdown("---")
        st.markdown(f"**Next Fed Meeting:** {fomc_d} ({fomc_dy} days away)")
        if fomc_dy and fomc_dy <= 14:
            st.warning("Fed meeting soon. Rate cut = buy. Rate hike = hold cash.")


# ══════════════════════════════════════════════════════════════
# TAB 3 — OPPORTUNITIES (Fallen Angels)
# ══════════════════════════════════════════════════════════════
with tab3:
    st.subheader("Fallen Angel Scanner — All Opportunities")
    st.caption("Stocks down 30%+ from 52-week highs. No limit — showing every one found.")

    broad_content, broad_stale = load_daily_md("BROAD_UNIVERSE_")

    if broad_content:
        # Parse sections
        sections = {"fa": [], "approaching": [], "sector": [], "recon": []}
        current_section = None
        current_lines = []

        for line in broad_content.split("\n"):
            lu = line.upper()
            if "FALLEN ANGEL OPPORTUNITIES" in lu and "30%" in line:
                current_section = "fa"
                continue
            elif "APPROACHING FALLEN ANGEL" in lu:
                current_section = "approaching"
                continue
            elif "SECTOR HEALTH" in lu:
                current_section = "sector"
                continue
            elif "RECONSTRUCTION WATCH" in lu:
                current_section = "recon"
                continue
            elif "CRYPTO" in lu and "UPDATE" in lu:
                current_section = None
                continue
            elif "MACRO CONTEXT" in lu:
                current_section = None
                continue
            elif line.startswith("-----"):
                continue

            if current_section and line.strip():
                sections[current_section].append(line)

        # Sector health
        if sections["sector"]:
            st.subheader("Sector Health Check")
            for line in sections["sector"]:
                st.markdown(line)
            st.markdown("---")

        # Fallen angels — ALL of them
        if sections["fa"]:
            st.subheader(f"Fallen Angels ({len([l for l in sections['fa'] if l.startswith('###') or (l.startswith('**') and 'down' in l.lower())])} found)")
            for line in sections["fa"]:
                st.markdown(line)
        else:
            st.info("No fallen angels found today.")

        # Approaching
        if sections["approaching"]:
            st.markdown("---")
            st.subheader("Approaching Fallen Angel Territory (20-29% drops)")
            st.caption("Watch list — approaching the 30% threshold")
            for line in sections["approaching"]:
                st.markdown(line)

        # Reconstruction watch
        if sections["recon"]:
            st.markdown("---")
            st.subheader("Reconstruction Watch")
            st.caption(f"These become buys in Phase C (Day 100+). Currently Day {DAYS_SINCE_WAR}.")
            for line in sections["recon"]:
                st.markdown(line)
    else:
        st.warning("No broad universe scan found. Run the daily runner first.")


# ══════════════════════════════════════════════════════════════
# TAB 4 — MOMENTUM
# ══════════════════════════════════════════════════════════════
with tab4:
    st.subheader("Momentum Scanner")
    st.caption("Stocks rising strongly — up 20%+ from 52-week lows in relevant sectors.")

    if broad_content:
        # Look for momentum section
        momentum_lines = []
        in_momentum = False
        for line in broad_content.split("\n"):
            if "MOMENTUM" in line.upper() and ("SCANNER" in line.upper() or "OPPORTUNITIES" in line.upper()):
                in_momentum = True
                continue
            if in_momentum:
                if line.startswith("-----") or ("CRYPTO" in line.upper() and "UPDATE" in line.upper()):
                    in_momentum = False
                    continue
                if line.strip():
                    momentum_lines.append(line)

        if momentum_lines:
            for line in momentum_lines:
                st.markdown(line)
        else:
            st.info(
                "Momentum data not yet available. "
                "The upgraded daily runner will generate momentum opportunities starting tomorrow."
            )

        # Show defence sector as built-in momentum
        st.markdown("---")
        st.subheader("Built-in Momentum — Your Defence Holdings")
        st.caption("Defence stocks typically rise during active conflicts.")
        for t in ["LMT", "RTX", "ITA", "BAESY"]:
            e = entry_map[t]
            cp = live[t]["price"]
            gl_p = round((cp - e["entry"]) / e["entry"] * 100, 1)
            color = "green" if gl_p >= 0 else "red"
            st.markdown(f"**{t}** — ${cp:.2f} ({'+' if gl_p >= 0 else ''}{gl_p:.1f}% from entry)")
    else:
        st.warning("Run the daily runner first to generate momentum data.")


# ══════════════════════════════════════════════════════════════
# TAB 5 — MY CRYPTO
# ══════════════════════════════════════════════════════════════
with tab5:
    st.subheader("Your Crypto Portfolio")

    crypto_live = pull_crypto()
    crypto_global = pull_crypto_global()

    coin_map = {
        "ripple": ("XRP", "XRP", "Ardi's largest holding — cross-border payments between banks."),
        "bitcoin": ("Bitcoin", "BTC", "Original cryptocurrency and digital gold."),
        "stellar": ("Stellar", "XLM", "Payment network for developing countries."),
        "cardano": ("Cardano", "ADA", "Proof-of-stake blockchain."),
        "hedera-hashgraph": ("Hedera", "HBAR", "Enterprise ledger backed by Google, IBM, Boeing."),
    }
    display_order = ["ripple", "bitcoin", "stellar", "cardano", "hedera-hashgraph"]

    if crypto_live:
        for cid in display_order:
            name, ticker, desc = coin_map[cid]
            live_p = crypto_live.get(cid, {}).get("usd", 0)
            chg_24h = crypto_live.get(cid, {}).get("usd_24h_change", 0)
            baseline_p = crypto_baseline.get(cid, {}).get("price_usd", 0)

            chg_from_base = round(((live_p - baseline_p) / baseline_p) * 100, 2) if baseline_p else 0
            dollar_chg = round(live_p - baseline_p, 6) if baseline_p else 0

            if cid == "ripple":
                st.markdown("### XRP — Your Largest Holding")

            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f"**{name}** ({ticker})")
            c1.caption(desc)
            c2.metric("Now", f"${live_p:,.6f}" if live_p < 1 else f"${live_p:,.2f}")
            c3.metric("Baseline", f"${baseline_p:,.6f}" if baseline_p and baseline_p < 1 else f"${baseline_p:,.2f}")
            c4.metric("Change", f"{chg_from_base:+.1f}%", f"24h: {chg_24h:+.1f}%")
            st.markdown("---")
    else:
        st.warning("Could not fetch live crypto prices.")
        for cid in display_order:
            name, ticker, desc = coin_map[cid]
            bp = crypto_baseline.get(cid, {}).get("price_usd", 0)
            st.markdown(f"**{name} ({ticker}):** ${bp}")

    # Global crypto
    if crypto_global:
        st.subheader("Overall Crypto Market")
        mc1, mc2, mc3 = st.columns(3)
        cap = crypto_global.get("total_market_cap", {}).get("usd", 0)
        btc_dom = crypto_global.get("market_cap_percentage", {}).get("btc", 0)
        mc1.metric("Market Cap", f"${cap/1e12:.2f}T")
        mc2.metric("BTC Dominance", f"{btc_dom:.1f}%")
        # Fear & greed explanation
        mc3.markdown(
            "**Crypto Fear & Greed Guide:**\n"
            "- 0-25: Extreme Fear (panic selling)\n"
            "- 25-50: Fear (cautious)\n"
            "- 50-75: Greed (confident buying)\n"
            "- 75-100: Extreme Greed (bubble risk)"
        )


# ══════════════════════════════════════════════════════════════
# TAB 6 — WORLD EVENTS
# ══════════════════════════════════════════════════════════════
with tab6:
    st.subheader("World Events — Portfolio Impact")
    st.caption("Global events that could affect your holdings, ranked by impact.")

    if daily_content:
        # Look for black swan alerts
        if "BLACK SWAN" in daily_content.upper():
            st.error("BLACK SWAN ALERT detected in today's report. Read your STOCKS file immediately.")

        # Look for global events / portfolio impact section
        event_lines = []
        in_events = False
        for line in daily_content.split("\n"):
            lu = line.upper()
            if "GLOBAL EVENT" in lu or "PORTFOLIO IMPACT" in lu or "WORLD EVENT" in lu:
                in_events = True
                continue
            if in_events:
                if line.startswith("-----") or line.startswith("##"):
                    if event_lines:
                        break
                if line.strip():
                    event_lines.append(line)

        if event_lines:
            for line in event_lines:
                st.markdown(line)
        else:
            st.info(
                "World events data will appear here once the upgraded daily runner "
                "generates its first report. The new runner scans economics, geopolitics, "
                "commodities, regulations, and more — globally with no limits."
            )

    # Always show key live data
    st.markdown("---")
    st.subheader("Live Global Indicators")

    g1, g2, g3, g4 = st.columns(4)
    with g1:
        if oil_val:
            st.metric("Oil (WTI)", f"${oil_val:.2f}")
    with g2:
        gold_val = pull_single("GC=F")
        if gold_val:
            st.metric("Gold", f"${gold_val:,.0f}")
    with g3:
        if vix_val:
            st.metric("VIX", f"{vix_val:.1f}")
    with g4:
        if sp_val:
            st.metric("S&P 500", f"{sp_val:,.0f}")

    # Perplexity prompt
    st.markdown("---")
    st.subheader("Morning Intelligence Checklist")
    st.markdown(
        "Open [Perplexity.ai](https://www.perplexity.ai) and paste this prompt:"
    )
    perp_prompt = (
        f"I own: LMT, RTX, LNG, GLD, ITA, XOM, CEG, BAESY. "
        f"Watching: DAL, RCL. Crypto: XRP, BTC, XLM, ADA, HBAR. "
        f"Iran war Day {DAYS_SINCE_WAR}, Ukraine Year 4. "
        f"Scan every global news source from last 24 hours. "
        f"Find everything affecting my portfolio. "
        f"Check: ceasefire signals, danger signals, XRP news, "
        f"Fed news, fallen angel opportunities, black swans. "
        f"Give me one recommended action."
    )
    st.code(perp_prompt, language=None)


# ── Footer ───────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "**Access from anywhere:** This dashboard works on any device worldwide. "
    "Bookmark this page on your iPhone for instant access."
)
st.caption(f"Ardi Market Dashboard | Refreshes every 60 min | {TIME_DISPLAY}")
