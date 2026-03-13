#!/usr/bin/env python3
"""
ARDI MARKET DASHBOARD
Streamlit web app — run with: streamlit run dashboard.py
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import json
import os
import glob
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

# ── Constants ────────────────────────────────────────────────
PACIFIC = pytz.timezone("America/Los_Angeles")
NOW = datetime.now(PACIFIC)
TODAY_STR = NOW.strftime("%Y-%m-%d")
TODAY_DISPLAY = NOW.strftime("%A, %B %d, %Y")
TIME_DISPLAY = NOW.strftime("%I:%M %p Pacific")
WAR_START = date(2026, 2, 28)
DAYS_SINCE_WAR = (NOW.date() - WAR_START).days
PRE_CONFLICT_OIL = 64.56

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DAILY_DIR = os.path.join(BASE_DIR, "Daily")
FOUNDATION_PATH = os.path.join(BASE_DIR, "AGENT_9_FOUNDATION_PATCH.json")

PORTFOLIO_TICKERS = ["LMT", "RTX", "LNG", "GLD", "ITA", "XOM", "CEG", "BAESY"]
WATCH_TICKERS = ["DAL", "RCL"]

# ── Helpers ──────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_foundation():
    if os.path.exists(FOUNDATION_PATH):
        with open(FOUNDATION_PATH) as f:
            return json.load(f)
    return None


def find_latest_daily(prefix):
    """Find the most recent daily file matching a prefix."""
    pattern = os.path.join(DAILY_DIR, f"{prefix}*.md")
    files = sorted(glob.glob(pattern), reverse=True)
    if files:
        return files[0]
    return None


def load_daily_md(prefix):
    path_today = os.path.join(DAILY_DIR, f"{prefix}{TODAY_STR}.md")
    stale = False
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
    """Pull price history for a list of tickers."""
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
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": "bitcoin,ripple,stellar,cardano,hedera-hashgraph",
            "vs_currencies": "usd",
            "include_24hr_change": "true",
        }
        r = requests.get(url, params=params, timeout=10)
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


def color_delta(val, fmt="${:,.2f}"):
    """Return colored metric string."""
    if val >= 0:
        return f"**:green[+{fmt.format(val)}]**"
    return f"**:red[{fmt.format(val)}]**"


def pct_color(val):
    if val >= 0:
        return f":green[+{val:.1f}%]"
    return f":red[{val:.1f}%]"


def make_sparkline(series, color="deepskyblue", height=80):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        y=series.values, x=list(range(len(series))),
        mode="lines", line=dict(color=color, width=2),
        fill="tozeroy", fillcolor="rgba(0,191,255,0.08)",
    ))
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=height, xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


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
    }

# ── Pull live prices ─────────────────────────────────────────
all_tickers = PORTFOLIO_TICKERS + WATCH_TICKERS
hist_data = pull_prices(all_tickers, period="1mo")

live = {}
for t in all_tickers:
    try:
        if isinstance(hist_data.columns, pd.MultiIndex):
            close = hist_data["Close"][t].dropna()
        else:
            close = hist_data["Close"].dropna()
        live[t] = {"price": round(float(close.iloc[-1]), 2), "series": close}
    except Exception:
        live[t] = {"price": entry_map.get(t, {}).get("entry", 0), "series": pd.Series()}

# Macro
vix_val = pull_single("^VIX")
vix3m_val = pull_single("^VIX3M")
oil_val = pull_single("CL=F")
sp_val = pull_single("^GSPC")
tlt_val = pull_single("TLT")

# ── Portfolio calculations ───────────────────────────────────
total_entry = sum(entry_map[t]["cost"] for t in PORTFOLIO_TICKERS)
total_current = sum(live[t]["price"] * entry_map[t]["shares"] for t in PORTFOLIO_TICKERS)
total_gl = total_current - total_entry
total_pct = (total_gl / total_entry * 100) if total_entry > 0 else 0
portfolio_val = total_current + cash_reserve

# ── Determine today's action ────────────────────────────────
# Read from daily file if available, otherwise compute
daily_content, daily_stale = load_daily_md("STOCKS_")

action_text = "HOLD EVERYTHING. No trades needed today."
action_color = "green"

if daily_content:
    for line in daily_content.split("\n"):
        if "TODAY'S ACTION" in line.upper():
            idx = daily_content.index(line)
            next_lines = daily_content[idx:].split("\n")
            for nl in next_lines[1:5]:
                stripped = nl.strip().strip("#").strip()
                if stripped and len(stripped) > 10:
                    action_text = stripped
                    break
            break

if "DANGER" in action_text.upper() or "DO NOT TRADE" in action_text.upper():
    action_color = "red"
elif "BUY" in action_text.upper() or "OPPORTUNITY" in action_text.upper():
    action_color = "blue"
elif "REVIEW" in action_text.upper() or "WARNING" in action_text.upper():
    action_color = "orange"

# ── Ceasefire / escalation signal computation ────────────────
ceasefire_signals = []
ceasefire_fired = 0

# Oil drop check
oil_prev = None
try:
    oil_tk = yf.Ticker("CL=F")
    oil_hist = oil_tk.history(period="5d")
    if len(oil_hist) >= 2:
        oil_prev = round(float(oil_hist["Close"].iloc[-2]), 2)
except Exception:
    pass

if oil_val and oil_prev and oil_prev > 0:
    oil_chg = ((oil_val - oil_prev) / oil_prev) * 100
    fired = oil_chg <= -3
    ceasefire_signals.append(("Oil dropped 3%+ in one day", fired, f"Oil changed {oil_chg:+.1f}% today"))
    if fired:
        ceasefire_fired += 1
else:
    ceasefire_signals.append(("Oil dropped 3%+ in one day", False, "Data unavailable"))

# VIX below 20
if vix_val is not None:
    fired = vix_val < 20
    ceasefire_signals.append(("Fear index (VIX) below 20", fired, f"VIX at {vix_val:.1f}"))
    if fired:
        ceasefire_fired += 1
else:
    ceasefire_signals.append(("Fear index (VIX) below 20", False, "Unavailable"))

# VIX term structure
if vix_val and vix3m_val:
    fired = vix_val > vix3m_val
    label = "Backwardation — market expects near-term resolution" if fired else "Contango — normal"
    ceasefire_signals.append(("VIX term structure ceasefire signal", fired, f"VIX {vix_val:.1f} vs VIX3M {vix3m_val:.1f} — {label}"))
    if fired:
        ceasefire_fired += 1
else:
    ceasefire_signals.append(("VIX term structure ceasefire signal", False, "Unavailable"))

ceasefire_signals.append(("Iranian FM uses peace language", None, "MANUAL CHECK — understandingwar.org"))
ceasefire_signals.append(("Mediator country announces talks", None, "MANUAL CHECK — news"))
ceasefire_signals.append(("Trump makes clear peace statement", None, "MANUAL CHECK — news"))

escalation_signals = []
escalation_fired = 0

if oil_val and oil_prev and oil_prev > 0:
    oil_chg = ((oil_val - oil_prev) / oil_prev) * 100
    fired = oil_chg >= 10
    escalation_signals.append(("Oil spiked 10%+ in one day", fired, f"Oil changed {oil_chg:+.1f}%"))
    if fired:
        escalation_fired += 1
else:
    escalation_signals.append(("Oil spiked 10%+ in one day", False, "Unavailable"))

if vix_val is not None:
    fired = vix_val > 40
    escalation_signals.append(("Fear index (VIX) above 40", fired, f"VIX at {vix_val:.1f}"))
    if fired:
        escalation_fired += 1
else:
    escalation_signals.append(("Fear index (VIX) above 40", False, "Unavailable"))

escalation_signals.append(("Iran nuclear announcement", None, "MANUAL CHECK"))
escalation_signals.append(("China moves on Taiwan", None, "MANUAL CHECK"))
escalation_signals.append(("US carrier attacked", None, "MANUAL CHECK"))


# ══════════════════════════════════════════════════════════════
# RENDER
# ══════════════════════════════════════════════════════════════

# ── Refresh button + auto-refresh ────────────────────────────
col_hdr1, col_hdr2 = st.columns([9, 1])
with col_hdr2:
    if st.button("Refresh"):
        st.cache_data.clear()
        st.rerun()

# Auto-refresh every 60 min
st.markdown(
    '<meta http-equiv="refresh" content="3600">',
    unsafe_allow_html=True,
)

# ── Header ───────────────────────────────────────────────────
st.markdown(f"# Good morning Ardi")
st.caption(
    "Data updated daily at 3 AM Pacific | "
    "Hosted on Streamlit Cloud | "
    "Last updated: " + TODAY_DISPLAY
)
st.markdown(f"**{TODAY_DISPLAY}** | {TIME_DISPLAY} | Day **{DAYS_SINCE_WAR}** of Iran conflict")

if daily_stale:
    st.info(
        "Today's report is not ready yet. The daily runner generates it at 3 AM Pacific. "
        "Showing the most recent available data in the meantime."
    )

# Portfolio headline
val_color = "green" if total_gl >= 0 else "red"
st.markdown(
    f'<h2 style="margin-bottom:0">Portfolio: <span style="color:{"#2ecc71" if total_gl >= 0 else "#e74c3c"}">'
    f'${portfolio_val:,.2f}</span></h2>',
    unsafe_allow_html=True,
)
sign = "+" if total_gl >= 0 else ""
st.markdown(f"Invested: ${total_entry:,.2f} | Change: **{sign}${total_gl:,.2f}** ({sign}{total_pct:.1f}%) | Cash reserve: ${cash_reserve:,.2f}")

# Action box
box_colors = {"green": "#27ae60", "blue": "#2980b9", "red": "#c0392b", "orange": "#e67e22"}
bg = box_colors.get(action_color, "#27ae60")
st.markdown(
    f'<div style="background:{bg};color:white;padding:16px 20px;border-radius:10px;'
    f'font-size:17px;margin:12px 0 20px 0"><strong>TODAY\'S ACTION:</strong> {action_text}</div>',
    unsafe_allow_html=True,
)

# ── Tabs ─────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["My Stocks", "War Signals", "New Opportunities", "My Crypto"])

# ══════════════════════════════════════════════════════════════
# TAB 1 — MY STOCKS
# ══════════════════════════════════════════════════════════════
with tab1:
    st.subheader("Your 8 Positions")

    # 2-column grid
    for row_start in range(0, 8, 2):
        cols = st.columns(2)
        for ci, idx in enumerate(range(row_start, min(row_start + 2, 8))):
            t = PORTFOLIO_TICKERS[idx]
            e = entry_map[t]
            cp = live[t]["price"]
            gl_d = round(cp * e["shares"] - e["cost"], 2)
            gl_p = round((gl_d / e["cost"]) * 100, 1) if e["cost"] > 0 else 0

            badge_text = "HOLD"
            badge_color = "#27ae60"
            if gl_p <= -15:
                badge_text = "REVIEW"
                badge_color = "#e74c3c"
            elif gl_p <= -10:
                badge_text = "MONITOR"
                badge_color = "#e67e22"
            elif gl_p >= 20:
                badge_text = "STRONG"
                badge_color = "#2ecc71"

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

                series = live[t].get("series", pd.Series())
                if len(series) > 2:
                    line_color = "#2ecc71" if gl_d >= 0 else "#e74c3c"
                    st.plotly_chart(make_sparkline(series, color=line_color), use_container_width=True, key=f"spark_{t}")

                # Expandable targets
                with st.expander("30 / 90 day outlook"):
                    if t in ["LMT", "RTX", "ITA", "BAESY"]:
                        st.write(f"**30 days:** ${cp * 1.03:.2f}–${cp * 1.08:.2f} (defense demand remains high during conflict)")
                        st.write(f"**90 days:** ${cp * 1.08:.2f}–${cp * 1.15:.2f} (continued elevated military spending)")
                    elif t in ["XOM", "LNG"]:
                        st.write(f"**30 days:** ${cp * 0.97:.2f}–${cp * 1.05:.2f} (oil volatile around war premium)")
                        st.write(f"**90 days:** ${cp * 0.90:.2f}–${cp * 1.10:.2f} (depends on ceasefire timing)")
                    elif t == "GLD":
                        st.write(f"**30 days:** ${cp * 1.02:.2f}–${cp * 1.07:.2f} (gold rises with uncertainty)")
                        st.write(f"**90 days:** ${cp * 1.05:.2f}–${cp * 1.12:.2f} (safe haven bid continues)")
                    elif t == "CEG":
                        st.write(f"**30 days:** ${cp * 0.95:.2f}–${cp * 1.08:.2f} (nuclear volatile but uptrend)")
                        st.write(f"**90 days:** ${cp * 1.05:.2f}–${cp * 1.20:.2f} (AI power demand supports long-term)")

                # Earnings
                earn = earnings_data.get(t, {})
                ed = earn.get("next_earnings")
                if ed and ed not in ["Not available", "Error"]:
                    try:
                        edate = datetime.strptime(ed, "%Y-%m-%d").date()
                        days_to = (edate - NOW.date()).days
                        if 0 < days_to <= 21:
                            st.warning(f"Earnings in {days_to} days ({ed})")
                        elif days_to > 0:
                            st.caption(f"Earnings: {ed} ({days_to} days)")
                        else:
                            st.caption(f"Last reported: {ed}")
                    except Exception:
                        pass

                st.markdown("---")

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
            st.info(f"WAITING — Buy when 2+ ceasefire signals fire. Currently {ceasefire_fired}/6 fired.")

    # Portfolio total chart
    st.subheader("Portfolio Value Over Time")
    if hist_data is not None:
        try:
            port_series = pd.Series(0.0, index=[])
            for t in PORTFOLIO_TICKERS:
                shares = entry_map[t]["shares"]
                if isinstance(hist_data.columns, pd.MultiIndex):
                    s = hist_data["Close"][t].dropna() * shares
                else:
                    s = hist_data["Close"].dropna() * shares
                if len(port_series) == 0:
                    port_series = s
                else:
                    port_series = port_series.add(s, fill_value=0)
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
                yaxis_title="Portfolio Value ($)",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            st.caption("Could not generate portfolio chart.")


# ══════════════════════════════════════════════════════════════
# TAB 2 — WAR SIGNALS
# ══════════════════════════════════════════════════════════════
with tab2:
    st.subheader(f"War Signal Tracker — Day {DAYS_SINCE_WAR}")
    st.caption(f"Iran-US-Israel conflict started February 28, 2026")

    left, right = st.columns(2)

    with left:
        st.markdown("### Ceasefire Signals")
        st.progress(ceasefire_fired / 6)
        st.caption(f"{ceasefire_fired} of 6 signals fired")

        for name, fired, detail in ceasefire_signals:
            if fired is True:
                st.markdown(f"🟢 **{name}**")
                st.caption(f"   {detail}")
            elif fired is False:
                st.markdown(f"⚪ {name}")
                st.caption(f"   {detail}")
            else:
                st.markdown(f"⚪ {name}")
                st.caption(f"   {detail}")

        st.info("Buy Delta (DAL) and Royal Caribbean (RCL) when 2 or more signals fire.")

    with right:
        st.markdown("### Danger Signals")
        danger_progress = escalation_fired / 5 if escalation_fired > 0 else 0
        st.progress(danger_progress)
        st.caption(f"{escalation_fired} of 5 signals fired")

        for name, fired, detail in escalation_signals:
            if fired is True:
                st.markdown(f"🔴 **{name}**")
                st.caption(f"   {detail}")
            elif fired is False:
                st.markdown(f"⚪ {name}")
                st.caption(f"   {detail}")
            else:
                st.markdown(f"⚪ {name}")
                st.caption(f"   {detail}")

        if escalation_fired > 0:
            st.error("DANGER SIGNAL FIRED. Call Fidelity immediately: 800-343-3548")
        else:
            st.success("No danger signals firing. Positions safe.")

    # Key numbers
    st.markdown("---")
    st.subheader("Key Market Numbers")

    k1, k2, k3, k4 = st.columns(4)

    with k1:
        if oil_val:
            premium = round(oil_val - PRE_CONFLICT_OIL, 2)
            prem_pct = round((premium / PRE_CONFLICT_OIL) * 100, 1)
            st.metric("Oil Price", f"${oil_val:.2f}", f"+${premium:.2f} war premium ({prem_pct}%)")
        else:
            st.metric("Oil Price", "Unavailable")

    with k2:
        if vix_val is not None:
            if vix_val < 15:
                vix_label = "Calm"
            elif vix_val < 20:
                vix_label = "Slightly worried"
            elif vix_val < 30:
                vix_label = "Worried"
            elif vix_val < 40:
                vix_label = "Very worried"
            else:
                vix_label = "PANIC"
            st.metric("Fear Index (VIX)", f"{vix_val:.1f}", vix_label)
        else:
            st.metric("Fear Index (VIX)", "Unavailable")

    with k3:
        if sp_val:
            sp_baseline = 5900
            sp_chg = round(((sp_val - sp_baseline) / sp_baseline) * 100, 1)
            st.metric("S&P 500", f"{sp_val:,.0f}", f"{sp_chg:+.1f}% vs Feb 28")
        else:
            st.metric("S&P 500", "Unavailable")

    with k4:
        if tlt_val:
            st.metric("Bonds (TLT)", f"${tlt_val:.2f}")
            if tlt_val < 85:
                st.caption("Bonds falling — possible petrodollar disruption")
            else:
                st.caption("Bonds stable")
        else:
            st.metric("Bonds (TLT)", "Unavailable")

    # Oil analysis
    if oil_val:
        st.markdown("---")
        st.subheader("Oil Market Analysis")
        premium = oil_val - PRE_CONFLICT_OIL
        cf_low = round(oil_val - premium * 0.80, 2)
        cf_high = round(oil_val - premium * 0.60, 2)
        st.markdown(
            f"Oil is at **${oil_val:.2f}**. Before the war it was ~${PRE_CONFLICT_OIL}. "
            f"The war adds **${premium:.2f}** to the price (the war premium). "
            f"When a ceasefire happens, oil is expected to fall to **${cf_low:.2f}–${cf_high:.2f}** "
            f"(based on the 1991 Gulf War pattern where 60-80% of the premium collapsed). "
            f"At that point oil companies like XOM drop and airlines like DAL rise."
        )


# ══════════════════════════════════════════════════════════════
# TAB 3 — NEW OPPORTUNITIES
# ══════════════════════════════════════════════════════════════
with tab3:
    st.subheader("Fallen Angel Scanner")

    broad_content, broad_stale = load_daily_md("BROAD_UNIVERSE_")

    if broad_content:
        # Parse fallen angel section
        in_fa = False
        in_approaching = False
        in_sector = False
        fa_blocks = []
        current_block = []
        approaching_lines = []
        sector_lines = []

        for line in broad_content.split("\n"):
            if "FALLEN ANGEL OPPORTUNITIES" in line.upper() and "30%" in line:
                in_fa = True
                in_approaching = False
                in_sector = False
                continue
            if "APPROACHING FALLEN ANGEL" in line.upper():
                if current_block:
                    fa_blocks.append("\n".join(current_block))
                    current_block = []
                in_fa = False
                in_approaching = True
                in_sector = False
                continue
            if "SECTOR HEALTH" in line.upper():
                in_sector = True
                in_fa = False
                in_approaching = False
                continue
            if "CRYPTO" in line.upper() and "UPDATE" in line.upper():
                if current_block:
                    fa_blocks.append("\n".join(current_block))
                in_fa = False
                in_approaching = False
                in_sector = False
                continue
            if line.startswith("-----"):
                if in_fa and current_block:
                    fa_blocks.append("\n".join(current_block))
                    current_block = []
                if in_approaching:
                    in_approaching = False
                if in_sector:
                    in_sector = False
                continue

            if in_fa:
                if line.startswith("### ") or (line.startswith("**") and "—" in line and "Watch" not in line):
                    if current_block:
                        fa_blocks.append("\n".join(current_block))
                        current_block = []
                current_block.append(line)
            elif in_approaching:
                approaching_lines.append(line)
            elif in_sector:
                sector_lines.append(line)

        if current_block:
            fa_blocks.append("\n".join(current_block))

        # Display fallen angel cards
        if fa_blocks:
            for block in fa_blocks:
                if block.strip():
                    with st.container():
                        st.markdown(block)
                        st.markdown("---")
        else:
            st.info("No strong fallen angel opportunities found today.")

        # Sector heat map
        if sector_lines:
            st.subheader("Sector Health Check")
            for line in sector_lines:
                if line.strip():
                    st.markdown(line)

        # Approaching
        if approaching_lines:
            st.subheader("Stocks Approaching Fallen Angel Territory (20-29% drops)")
            st.caption("These are approaching the 30% threshold — start watching them now.")
            for line in approaching_lines:
                if line.strip():
                    st.markdown(line)
    else:
        st.warning("No broad universe scan found. Run the daily runner first.")


# ══════════════════════════════════════════════════════════════
# TAB 4 — MY CRYPTO
# ══════════════════════════════════════════════════════════════
with tab4:
    st.subheader("Your Crypto Portfolio")

    crypto_live = pull_crypto()
    crypto_global = pull_crypto_global()

    coin_map = {
        "ripple": ("XRP", "XRP", "Ardi's largest crypto holding — fast cross-border payments between banks."),
        "bitcoin": ("Bitcoin", "BTC", "The original cryptocurrency and digital gold."),
        "stellar": ("Stellar", "XLM", "Payment network connecting banks in developing countries."),
        "cardano": ("Cardano", "ADA", "Proof-of-stake blockchain for sustainability."),
        "hedera-hashgraph": ("Hedera", "HBAR", "Enterprise-grade ledger backed by Google, IBM, Boeing."),
    }

    # Show XRP first
    display_order = ["ripple", "bitcoin", "stellar", "cardano", "hedera-hashgraph"]

    if crypto_live:
        for cid in display_order:
            name, ticker, desc = coin_map[cid]
            live_p = crypto_live.get(cid, {}).get("usd", 0)
            chg_24h = crypto_live.get(cid, {}).get("usd_24h_change", 0)
            baseline_p = crypto_baseline.get(cid, {}).get("price_usd", 0)

            if baseline_p and baseline_p > 0:
                chg_from_base = round(((live_p - baseline_p) / baseline_p) * 100, 2)
                dollar_chg = round(live_p - baseline_p, 6)
            else:
                chg_from_base = 0
                dollar_chg = 0

            is_xrp = cid == "ripple"
            if is_xrp:
                st.markdown("### XRP — Your Largest Holding")

            with st.container():
                c1, c2, c3, c4 = st.columns(4)
                c1.markdown(f"**{name}** ({ticker})")
                c1.caption(desc)

                c2.metric("Price Now", f"${live_p:,.6f}" if live_p < 1 else f"${live_p:,.2f}")
                c3.metric("Baseline", f"${baseline_p:,.6f}" if baseline_p < 1 else f"${baseline_p:,.2f}")

                delta_label = f"{'+' if chg_from_base >= 0 else ''}{chg_from_base:.1f}% since baseline"
                c4.metric("Change", f"${dollar_chg:+,.6f}" if abs(dollar_chg) < 1 else f"${dollar_chg:+,.2f}", delta_label)

                st.caption(f"24h change: {chg_24h:+.2f}%")
                st.markdown("---")
    else:
        st.warning("Could not fetch live crypto prices. Showing baseline from foundation.")
        for cid in display_order:
            name, ticker, desc = coin_map[cid]
            bp = crypto_baseline.get(cid, {}).get("price_usd", 0)
            st.markdown(f"**{name} ({ticker}):** ${bp}")

    # Global crypto market
    if crypto_global:
        st.subheader("Overall Crypto Market")
        mc1, mc2 = st.columns(2)
        cap = crypto_global.get("total_market_cap", {}).get("usd", 0)
        btc_dom = crypto_global.get("market_cap_percentage", {}).get("btc", 0)
        mc1.metric("Total Market Cap", f"${cap / 1e12:.2f}T")
        mc2.metric("Bitcoin Dominance", f"{btc_dom:.1f}%")


# ── Footer ───────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "**Access this dashboard from anywhere:**  \n"
    "You are viewing this on Streamlit Cloud.  \n"
    "This dashboard works on any phone, computer, or tablet "
    "anywhere in the world — no WiFi restrictions.  \n"
    "Bookmark this page on your iPhone for instant access."
)
st.caption(f"Dashboard built by Agent 9 | Data refreshes every 60 minutes | Last loaded: {TIME_DISPLAY}")
