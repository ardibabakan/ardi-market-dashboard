#!/usr/bin/env python3
"""
Ardi Market Command Center v3.0
Professional Streamlit Financial Dashboard — 8 tabs, live data, war signals.
"""

import streamlit as st
import json
import os
import sys
from datetime import datetime, date, timedelta

# ---------------------------------------------------------------------------
# Data engine import (graceful fallback)
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from data_engine import (
        get_technical_signals,
        get_crypto_onchain_data,
        get_options_activity,
        get_stocktwits_sentiment,
        get_short_interest,
        get_analyst_ratings,
        get_macro_indicators,
    )
    ENGINE = True
except Exception:
    ENGINE = False

# ---------------------------------------------------------------------------
# Third-party imports
# ---------------------------------------------------------------------------
import yfinance as yf
import pandas as pd
import numpy as np

try:
    import plotly.graph_objects as go
    import plotly.express as px
    PLOTLY = True
except Exception:
    PLOTLY = False

try:
    import requests as _requests
except Exception:
    _requests = None

# ---------------------------------------------------------------------------
# Page config & auto-refresh
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Ardi Market Command Center",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    '<meta http-equiv="refresh" content="3600">',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Color system & CSS
# ---------------------------------------------------------------------------
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.green-box  { background:#EAF3DE; color:#3B6D11; padding:12px 16px; border-radius:8px; margin:4px 0; }
.red-box    { background:#FCEBEB; color:#A32D2D; padding:12px 16px; border-radius:8px; margin:4px 0; }
.amber-box  { background:#FAEEDA; color:#633806; padding:12px 16px; border-radius:8px; margin:4px 0; }
.blue-box   { background:#E6F1FB; color:#185FA5; padding:12px 16px; border-radius:8px; margin:4px 0; }
.section-label { font-size:11px; text-transform:uppercase; letter-spacing:2px; color:#888;
                 margin:18px 0 6px 0; font-weight:600; }
.big-value  { font-size:36px; font-weight:700; margin:0; line-height:1.2; }
.heat-tile  { display:inline-block; padding:10px 14px; border-radius:6px; margin:3px;
              text-align:center; font-weight:600; font-size:13px; min-width:70px; }
.card       { border:1px solid #e0e0e0; border-radius:10px; padding:16px; margin:8px 0; }
.card-red   { border:1px solid #A32D2D; background:#FDF5F5; border-radius:10px; padding:16px; margin:8px 0; }
.card-green { border:1px solid #3B6D11; background:#F6FAF0; border-radius:10px; padding:16px; margin:8px 0; }
.signal-dot-green { display:inline-block; width:12px; height:12px; border-radius:50%;
                    background:#3B6D11; margin-right:6px; vertical-align:middle; }
.signal-dot-gray  { display:inline-block; width:12px; height:12px; border-radius:50%;
                    background:#bbb; margin-right:6px; vertical-align:middle; }
.signal-dot-amber { display:inline-block; width:12px; height:12px; border-radius:50%;
                    background:#D4910A; margin-right:6px; vertical-align:middle; }
@media (max-width:768px) {
    .big-value { font-size:26px; }
    .heat-tile { min-width:55px; padding:7px 8px; font-size:11px; }
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PORTFOLIO_TICKERS = ["LMT", "RTX", "LNG", "GLD", "ITA", "XOM", "CEG", "BAESY"]
WATCHLIST_TICKERS = ["DAL", "RCL"]
ALL_TICKERS = PORTFOLIO_TICKERS + WATCHLIST_TICKERS
INITIAL_PORTFOLIO = 10000.0
INVESTED = 8499.67
CASH = 1500.33
WAR_START = date(2026, 2, 28)
ENTRY_DATE = date(2026, 3, 13)
LTCG_DATE = date(2027, 3, 13)
OIL_BASELINE = 64.56
FOMC_DATES = ["Mar 18", "May 6", "Jun 17", "Jul 29", "Sep 16", "Nov 4", "Dec 16"]
CRYPTO_IDS = {
    "bitcoin": {"ticker": "BTC", "baseline": 71111},
    "ripple": {"ticker": "XRP", "baseline": 1.40},
    "stellar": {"ticker": "XLM", "baseline": 0.162602},
    "cardano": {"ticker": "ADA", "baseline": 0.267326},
    "hedera-hashgraph": {"ticker": "HBAR", "baseline": 0.095206},
}
SCAN_UNIVERSE = (
    "DAL,UAL,AAL,LUV,JBLU,CCL,RCL,NCLH,MAR,HLT,ABNB,"
    "ZS,CRWD,PANW,FTNT,CYBR,S,NFLX,META,SNAP,PINS,RBLX,COIN,"
    "BA,GE,MMM,ZIM,SBLK,DAC,TLRY,CGC,NNE,CCJ,UEC,"
    "FLR,KBR,PWR,MTZ,NVDA,AMD,INTC,QCOM,MU,"
    "XOM,CVX,COP,OXY,SLB,ORCL,CRM,ADBE,PYPL,UBER,LYFT,HOOD"
).split(",")

# ---------------------------------------------------------------------------
# Load foundation JSON
# ---------------------------------------------------------------------------
FOUNDATION_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "AGENT_9_FOUNDATION_PATCH.json",
)


@st.cache_data(ttl=3600)
def load_foundation():
    try:
        with open(FOUNDATION_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}


FOUNDATION = load_foundation()
POSITIONS = FOUNDATION.get("step2_portfolio", {}).get("positions", {})
EARNINGS = FOUNDATION.get("step3_earnings", {})
CRYPTO_FOUNDATION = FOUNDATION.get("step7_crypto", {})

# ---------------------------------------------------------------------------
# Helpers: formatting
# ---------------------------------------------------------------------------


def fmt_dollar(v):
    return f"${v:,.2f}"


def fmt_pct(v):
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.1f}%"


def color_class(v):
    if v > 0:
        return "green-box"
    elif v < 0:
        return "red-box"
    return "blue-box"


def _safe_float(val):
    """Extract a float from a value that might be a Series or scalar."""
    if isinstance(val, pd.Series):
        return float(val.iloc[0])
    return float(val)


# ---------------------------------------------------------------------------
# Data fetching (cached)
# ---------------------------------------------------------------------------


@st.cache_data(ttl=3600)
def fetch_current_prices(tickers):
    prices = {}
    for t in tickers:
        try:
            info = yf.Ticker(t).fast_info
            prices[t] = float(info.get("lastPrice", info.get("last_price", 0)))
        except Exception:
            prices[t] = 0.0
    return prices


@st.cache_data(ttl=3600)
def fetch_hist(ticker, period="1mo"):
    try:
        df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def fetch_spy_change():
    try:
        df = yf.download("SPY", start="2026-03-12", auto_adjust=True, progress=False)
        if df.empty or len(df) < 2:
            return 0.0
        first = _safe_float(df["Close"].iloc[0])
        last = _safe_float(df["Close"].iloc[-1])
        return ((last - first) / first) * 100
    except Exception:
        return 0.0


@st.cache_data(ttl=3600)
def fetch_war_indicators():
    result = {}
    mapping = {
        "CL=F": "Oil",
        "^VIX": "VIX",
        "GLD": "Gold",
        "^GSPC": "S&P 500",
        "TLT": "TLT",
    }
    for sym, name in mapping.items():
        try:
            info = yf.Ticker(sym).fast_info
            result[name] = float(info.get("lastPrice", info.get("last_price", 0)))
        except Exception:
            result[name] = 0.0
    return result


@st.cache_data(ttl=3600)
def fetch_52w_data(tickers):
    results = {}
    for t in tickers:
        try:
            info = yf.Ticker(t).fast_info
            high = float(info.get("yearHigh", info.get("year_high", 0)))
            price = float(info.get("lastPrice", info.get("last_price", 0)))
            if high > 0:
                drop_pct = ((price - high) / high) * 100
                results[t] = {"price": price, "high_52w": high, "drop_pct": drop_pct}
        except Exception:
            pass
    return results


@st.cache_data(ttl=3600)
def fetch_momentum_data(tickers):
    results = {}
    for t in tickers:
        try:
            info = yf.Ticker(t).fast_info
            low = float(info.get("yearLow", info.get("year_low", 0)))
            price = float(info.get("lastPrice", info.get("last_price", 0)))
            if low > 0:
                gain_pct = ((price - low) / low) * 100
                if gain_pct >= 20:
                    results[t] = {"price": price, "low_52w": low, "gain_pct": gain_pct}
        except Exception:
            pass
    return results


@st.cache_data(ttl=3600)
def fetch_crypto_prices():
    prices = {}
    if _requests is None:
        return prices
    ids_str = ",".join(CRYPTO_IDS.keys())
    try:
        r = _requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={
                "ids": ids_str,
                "vs_currencies": "usd",
                "include_24hr_change": "true",
            },
            timeout=10,
        )
        data = r.json()
        for cid in CRYPTO_IDS:
            if cid in data:
                prices[cid] = {
                    "price": data[cid].get("usd", 0),
                    "change_24h": data[cid].get("usd_24h_change", 0),
                }
    except Exception:
        pass
    return prices


@st.cache_data(ttl=3600)
def fetch_fear_greed():
    if _requests is None:
        return {"value": "N/A", "label": "N/A"}
    try:
        r = _requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        d = r.json()["data"][0]
        return {"value": d["value"], "label": d["value_classification"]}
    except Exception:
        return {"value": "N/A", "label": "N/A"}


@st.cache_data(ttl=3600)
def fetch_crypto_global():
    if _requests is None:
        return {}
    try:
        r = _requests.get("https://api.coingecko.com/api/v3/global", timeout=10)
        data = r.json().get("data", {})
        return {
            "market_cap": data.get("total_market_cap", {}).get("usd", 0),
            "btc_dominance": data.get("market_cap_percentage", {}).get("btc", 0),
        }
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Compute portfolio values
# ---------------------------------------------------------------------------
current_prices = fetch_current_prices(ALL_TICKERS)

portfolio_value = CASH
position_data = {}
for _t in PORTFOLIO_TICKERS:
    _pos = POSITIONS.get(_t, {})
    _entry_price = _pos.get("current_price", 0)
    _shares = _pos.get("shares_to_buy", 0)
    _cost_basis = _pos.get("total_cost", 0)
    _cur_price = current_prices.get(_t, _entry_price)
    _cur_value = _cur_price * _shares
    _pnl = _cur_value - _cost_basis
    _pnl_pct = (_pnl / _cost_basis * 100) if _cost_basis else 0
    _stop_loss = _entry_price * 0.85
    _profit_target = _entry_price * 1.25
    portfolio_value += _cur_value
    position_data[_t] = {
        "name": _pos.get("full_name", _t),
        "description": _pos.get("description", ""),
        "entry": _entry_price,
        "current": _cur_price,
        "shares": _shares,
        "cost": _cost_basis,
        "value": _cur_value,
        "pnl": _pnl,
        "pnl_pct": _pnl_pct,
        "stop_loss": _stop_loss,
        "profit_target": _profit_target,
        "earnings": EARNINGS.get(_t, {}).get("next_earnings", "N/A"),
    }

total_change = portfolio_value - INITIAL_PORTFOLIO
total_change_pct = (total_change / INITIAL_PORTFOLIO) * 100
spy_change = fetch_spy_change()

today = date.today()
conflict_day = (today - WAR_START).days

# ---------------------------------------------------------------------------
# HEADER (always visible)
# ---------------------------------------------------------------------------
now = datetime.now()
greeting = (
    "Good morning"
    if now.hour < 12
    else ("Good afternoon" if now.hour < 17 else "Good evening")
)

st.markdown(
    '<p class="section-label">'
    + greeting
    + " Ardi &mdash; "
    + now.strftime("%A, %B %d, %Y")
    + " &middot; "
    + now.strftime("%I:%M %p")
    + "</p>",
    unsafe_allow_html=True,
)

pv_color = "#3B6D11" if portfolio_value >= INITIAL_PORTFOLIO else "#A32D2D"
st.markdown(
    '<p class="big-value" style="color:'
    + pv_color
    + '">'
    + fmt_dollar(portfolio_value)
    + "</p>",
    unsafe_allow_html=True,
)

chg_cls = color_class(total_change)
st.markdown(
    '<div class="'
    + chg_cls
    + '">Change: '
    + fmt_dollar(total_change)
    + " ("
    + fmt_pct(total_change_pct)
    + ") since March 13 &nbsp;|&nbsp; Invested: "
    + fmt_dollar(INVESTED)
    + " &middot; Cash: "
    + fmt_dollar(CASH)
    + "</div>",
    unsafe_allow_html=True,
)

# vs S&P
alpha = total_change_pct - spy_change
alpha_cls = color_class(alpha)
st.markdown(
    '<div class="'
    + alpha_cls
    + '">vs S&P 500: Portfolio '
    + fmt_pct(total_change_pct)
    + " | S&P "
    + fmt_pct(spy_change)
    + " | Alpha: "
    + fmt_pct(alpha)
    + "</div>",
    unsafe_allow_html=True,
)

# Conflict phase badge
if conflict_day < 21:
    badge_cls = "amber-box"
    phase_label = "Conflict Day " + str(conflict_day) + " &mdash; Early Phase (hold defense)"
elif conflict_day <= 42:
    badge_cls = "green-box"
    phase_label = "Conflict Day " + str(conflict_day) + " &mdash; Ceasefire Window (watch signals)"
else:
    badge_cls = "blue-box"
    phase_label = "Conflict Day " + str(conflict_day) + " &mdash; Extended Phase (reassess thesis)"
st.markdown(
    '<div class="' + badge_cls + '">' + phase_label + "</div>",
    unsafe_allow_html=True,
)

# Action box
stop_hit = [t for t, d in position_data.items() if d["current"] <= d["stop_loss"]]
target_hit = [t for t, d in position_data.items() if d["current"] >= d["profit_target"]]

if stop_hit:
    action_cls = "red-box"
    action_msg = (
        "STOP LOSS TRIGGERED: "
        + ", ".join(stop_hit)
        + " &mdash; Review positions immediately"
    )
elif target_hit:
    action_cls = "green-box"
    action_msg = (
        "PROFIT TARGET HIT: "
        + ", ".join(target_hit)
        + " &mdash; Consider taking profits"
    )
elif 21 <= conflict_day <= 42:
    action_cls = "blue-box"
    action_msg = "Ceasefire window open &mdash; Watch for DAL/RCL entry opportunity"
else:
    action_cls = "green-box"
    action_msg = "HOLD &mdash; All positions within range. No action required."
st.markdown(
    '<div class="' + action_cls + '">' + action_msg + "</div>",
    unsafe_allow_html=True,
)

for _t in stop_hit:
    st.markdown(
        '<div class="red-box">ALERT: '
        + _t
        + " at "
        + fmt_dollar(position_data[_t]["current"])
        + " below stop loss "
        + fmt_dollar(position_data[_t]["stop_loss"])
        + "</div>",
        unsafe_allow_html=True,
    )
for _t in target_hit:
    st.markdown(
        '<div class="green-box">ALERT: '
        + _t
        + " at "
        + fmt_dollar(position_data[_t]["current"])
        + " above profit target "
        + fmt_dollar(position_data[_t]["profit_target"])
        + "</div>",
        unsafe_allow_html=True,
    )

st.markdown("---")

# ===========================================================================
# TABS
# ===========================================================================
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(
    [
        "My Stocks",
        "Technical Analysis",
        "War Signals",
        "Opportunities",
        "Momentum",
        "My Crypto",
        "World Events",
        "Risk Dashboard",
    ]
)

# ===========================================================================
# TAB 1 - My Stocks
# ===========================================================================
with tab1:
    st.markdown(
        '<p class="section-label">Today\'s Heat Map</p>', unsafe_allow_html=True
    )

    # Heat map tiles
    tiles_html = ""
    for _t in PORTFOLIO_TICKERS:
        _d = position_data[_t]
        day_chg_pct = _d["pnl_pct"]
        try:
            _hist = fetch_hist(_t, period="2d")
            if len(_hist) >= 2:
                _prev = _safe_float(_hist["Close"].iloc[-2])
                _cur = _safe_float(_hist["Close"].iloc[-1])
                day_chg_pct = ((_cur - _prev) / _prev) * 100 if _prev else 0
        except Exception:
            pass
        bg = "#EAF3DE" if day_chg_pct >= 0 else "#FCEBEB"
        fg = "#3B6D11" if day_chg_pct >= 0 else "#A32D2D"
        tiles_html += (
            '<span class="heat-tile" style="background:'
            + bg
            + ";color:"
            + fg
            + '">'
            + _t
            + "<br>"
            + fmt_pct(day_chg_pct)
            + "</span>"
        )
    st.markdown(tiles_html, unsafe_allow_html=True)

    # Two columns
    left_col, right_col = st.columns([3, 2])

    with left_col:
        st.markdown(
            '<p class="section-label">Portfolio Holdings</p>',
            unsafe_allow_html=True,
        )
        for _t in PORTFOLIO_TICKERS:
            _d = position_data[_t]
            sl_hit = _d["current"] <= _d["stop_loss"]
            pt_hit = _d["current"] >= _d["profit_target"]
            card_cls = (
                "card-red" if sl_hit else ("card-green" if pt_hit else "card")
            )
            pnl_color = "#3B6D11" if _d["pnl"] >= 0 else "#A32D2D"

            # Sparkline
            if PLOTLY:
                try:
                    _hist = fetch_hist(_t, period="1mo")
                    if not _hist.empty:
                        close_vals = _hist["Close"].values.flatten().tolist()
                        _fig = go.Figure(
                            go.Scatter(
                                y=close_vals,
                                mode="lines",
                                line=dict(
                                    color=(
                                        "#3B6D11"
                                        if _d["pnl"] >= 0
                                        else "#A32D2D"
                                    ),
                                    width=2,
                                ),
                            )
                        )
                        _fig.update_layout(
                            height=60,
                            margin=dict(l=0, r=0, t=0, b=0),
                            xaxis=dict(visible=False),
                            yaxis=dict(visible=False),
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                        )
                        st.plotly_chart(
                            _fig, use_container_width=True, key="spark_" + _t
                        )
                except Exception:
                    pass

            st.markdown(
                '<div class="'
                + card_cls
                + '"><strong>'
                + _t
                + "</strong> &mdash; "
                + _d["name"]
                + "<br>"
                + '<small style="color:#888">'
                + _d["description"]
                + "</small><br>"
                + "Entry: "
                + fmt_dollar(_d["entry"])
                + " &middot; Current: "
                + fmt_dollar(_d["current"])
                + " &middot; Shares: "
                + str(_d["shares"])
                + "<br>"
                + '<span style="color:'
                + pnl_color
                + ';font-weight:600">P&L: '
                + fmt_dollar(_d["pnl"])
                + " ("
                + fmt_pct(_d["pnl_pct"])
                + ")</span><br>"
                + "Stop Loss: "
                + fmt_dollar(_d["stop_loss"])
                + " &middot; Target: "
                + fmt_dollar(_d["profit_target"])
                + "<br>"
                + "Earnings: "
                + _d["earnings"]
                + "</div>",
                unsafe_allow_html=True,
            )

    with right_col:
        st.markdown(
            '<p class="section-label">Allocation</p>', unsafe_allow_html=True
        )
        if PLOTLY:
            labels = list(PORTFOLIO_TICKERS) + ["Cash"]
            values = [position_data[t]["value"] for t in PORTFOLIO_TICKERS] + [
                CASH
            ]
            _fig = px.pie(names=labels, values=values, hole=0.4)
            _fig.update_traces(textinfo="label+percent", textfont_size=11)
            _fig.update_layout(
                height=350,
                margin=dict(l=0, r=0, t=20, b=0),
                showlegend=False,
            )
            st.plotly_chart(_fig, use_container_width=True)
        else:
            for _t in PORTFOLIO_TICKERS:
                alloc = position_data[_t]["value"] / portfolio_value * 100
                st.write(_t + ": " + str(round(alloc, 1)) + "%")

        # Economic calendar
        st.markdown(
            '<p class="section-label">Upcoming Events</p>',
            unsafe_allow_html=True,
        )
        for _t in PORTFOLIO_TICKERS:
            earn = EARNINGS.get(_t, {}).get("next_earnings", "N/A")
            if earn not in ("N/A", "Not available"):
                st.markdown(
                    '<div class="blue-box">'
                    + _t
                    + " Earnings: "
                    + earn
                    + "</div>",
                    unsafe_allow_html=True,
                )
        st.markdown(
            '<div class="amber-box">Next FOMC: '
            + FOMC_DATES[0]
            + " 2026</div>",
            unsafe_allow_html=True,
        )

    # Watchlist
    st.markdown(
        '<p class="section-label">Watchlist (Ceasefire Plays)</p>',
        unsafe_allow_html=True,
    )
    wl_cols = st.columns(2)
    for i, _t in enumerate(WATCHLIST_TICKERS):
        _pos = POSITIONS.get(_t, {})
        _cur = current_prices.get(_t, _pos.get("current_price", 0))
        _entry_watch = _pos.get("current_price", 0)
        _chg = (
            ((_cur - _entry_watch) / _entry_watch * 100)
            if _entry_watch
            else 0
        )
        _cls = color_class(_chg)
        with wl_cols[i]:
            st.markdown(
                '<div class="'
                + _cls
                + '"><strong>'
                + _t
                + "</strong> &mdash; "
                + _pos.get("full_name", _t)
                + "<br>Baseline: "
                + fmt_dollar(_entry_watch)
                + " &middot; Now: "
                + fmt_dollar(_cur)
                + " &middot; "
                + fmt_pct(_chg)
                + "<br><small>"
                + _pos.get("description", "")
                + "</small></div>",
                unsafe_allow_html=True,
            )

    # Portfolio chart
    st.markdown(
        '<p class="section-label">Portfolio Value Over Time</p>',
        unsafe_allow_html=True,
    )
    if PLOTLY:
        try:
            tickers_str = " ".join(PORTFOLIO_TICKERS)
            hist_all = yf.download(
                tickers_str,
                start="2026-03-12",
                auto_adjust=True,
                progress=False,
            )
            if not hist_all.empty and "Close" in hist_all.columns:
                close_df = hist_all["Close"]
                port_vals = []
                for idx in close_df.index:
                    row = close_df.loc[idx]
                    day_val = CASH
                    for _t in PORTFOLIO_TICKERS:
                        _shares = POSITIONS.get(_t, {}).get("shares_to_buy", 0)
                        try:
                            price_val = (
                                float(row[_t])
                                if isinstance(row, pd.Series)
                                else float(row)
                            )
                        except Exception:
                            price_val = 0
                        if pd.notna(price_val):
                            day_val += price_val * _shares
                    port_vals.append({"date": idx, "value": day_val})
                if port_vals:
                    pv_df = pd.DataFrame(port_vals)
                    _fig = go.Figure(
                        go.Scatter(
                            x=pv_df["date"],
                            y=pv_df["value"],
                            mode="lines+markers",
                            line=dict(color="#3B6D11", width=2),
                        )
                    )
                    _fig.add_hline(
                        y=INITIAL_PORTFOLIO,
                        line_dash="dash",
                        line_color="#A32D2D",
                        annotation_text="$10,000 baseline",
                    )
                    _fig.update_layout(
                        height=300,
                        margin=dict(l=0, r=0, t=20, b=0),
                        yaxis_title="Portfolio Value ($)",
                    )
                    st.plotly_chart(_fig, use_container_width=True)
        except Exception:
            st.info("Portfolio chart data loading...")

    # Tax note
    days_to_ltcg = (LTCG_DATE - today).days
    st.markdown(
        '<div class="amber-box">Hold until March 13, 2027 for long-term capital gains ('
        + str(days_to_ltcg)
        + " days remaining)</div>",
        unsafe_allow_html=True,
    )

# ===========================================================================
# TAB 2 - Technical Analysis
# ===========================================================================
with tab2:
    st.markdown(
        '<p class="section-label">Technical Analysis</p>',
        unsafe_allow_html=True,
    )

    if ENGINE:
        for _t in PORTFOLIO_TICKERS:
            with st.expander(
                _t + " - " + position_data[_t]["name"], expanded=False
            ):
                try:
                    signals = get_technical_signals(_t)
                    if signals and isinstance(signals, dict) and signals.get("status") == "ok":
                        cols_ta = st.columns(4)
                        # data_engine returns nested dicts: rsi={value,signal,explain}
                        _rsi_data = signals.get("rsi", {})
                        rsi = _rsi_data.get("value", 50) if isinstance(_rsi_data, dict) else (float(_rsi_data) if _rsi_data else 50)
                        rsi_color = (
                            "#A32D2D"
                            if rsi > 70
                            else ("#3B6D11" if rsi < 30 else "#888")
                        )
                        cols_ta[0].markdown(
                            '<div class="card"><strong>RSI</strong><br>'
                            + '<span style="color:'
                            + rsi_color
                            + ';font-size:24px;font-weight:700">'
                            + str(round(rsi, 1))
                            + "</span><br><small>"
                            + (_rsi_data.get("signal", "") if isinstance(_rsi_data, dict) else "")
                            + "</small></div>",
                            unsafe_allow_html=True,
                        )

                        _macd_data = signals.get("macd", {})
                        macd_val = _macd_data.get("macd", 0) if isinstance(_macd_data, dict) else (float(_macd_data) if _macd_data else 0)
                        macd_cross = _macd_data.get("cross", "") if isinstance(_macd_data, dict) else ""
                        macd_color = "#3B6D11" if float(macd_val) > 0 else "#A32D2D"
                        cols_ta[1].markdown(
                            '<div class="card"><strong>MACD</strong><br>'
                            + '<span style="color:'
                            + macd_color
                            + ';font-size:24px;font-weight:700">'
                            + str(round(float(macd_val), 2))
                            + "</span><br><small>"
                            + macd_cross.replace("_", " ")
                            + "</small></div>",
                            unsafe_allow_html=True,
                        )

                        _ma_data = signals.get("moving_averages", {})
                        ma50 = _ma_data.get("ma50", 0) if isinstance(_ma_data, dict) else 0
                        ma200 = _ma_data.get("ma200", 0) if isinstance(_ma_data, dict) else 0
                        ma_cross = _ma_data.get("cross", "NONE") if isinstance(_ma_data, dict) else "NONE"
                        if ma50 and ma200 and float(ma50) > 0 and float(ma200) > 0:
                            cross = "Golden Cross" if ma_cross == "GOLDEN_CROSS" else ("Death Cross" if ma_cross == "DEATH_CROSS" else ("Above MA200" if float(ma50) > float(ma200) else "Below MA200"))
                            cross_color = "#3B6D11" if float(ma50) > float(ma200) else "#A32D2D"
                        else:
                            cross = "N/A"
                            cross_color = "#888"
                        cols_ta[2].markdown(
                            '<div class="card"><strong>MA 50/200</strong><br>'
                            + '<span style="color:'
                            + cross_color
                            + ';font-weight:600">'
                            + cross
                            + "</span></div>",
                            unsafe_allow_html=True,
                        )

                        _vol_data = signals.get("volume", {})
                        vol_ratio = _vol_data.get("ratio", 1.0) if isinstance(_vol_data, dict) else 1.0
                        vol_label = f"{vol_ratio}x avg" if vol_ratio else "normal"
                        cols_ta[3].markdown(
                            '<div class="card"><strong>Volume</strong><br>'
                            + str(vol_label)
                            + "</div>",
                            unsafe_allow_html=True,
                        )

                        _bb_data = signals.get("bollinger", {})
                        bb_upper = _bb_data.get("upper", 0) if isinstance(_bb_data, dict) else 0
                        bb_lower = _bb_data.get("lower", 0) if isinstance(_bb_data, dict) else 0
                        if bb_upper and bb_lower:
                            st.write(
                                "Bollinger Bands: Upper "
                                + fmt_dollar(float(bb_upper))
                                + " | Lower "
                                + fmt_dollar(float(bb_lower))
                            )

                        if PLOTLY:
                            _hist = fetch_hist(_t, period="3mo")
                            if not _hist.empty:
                                _fig = go.Figure(
                                    go.Candlestick(
                                        x=_hist.index,
                                        open=_hist["Open"].values.flatten(),
                                        high=_hist["High"].values.flatten(),
                                        low=_hist["Low"].values.flatten(),
                                        close=_hist["Close"]
                                        .values.flatten(),
                                    )
                                )
                                _fig.update_layout(
                                    height=350,
                                    margin=dict(l=0, r=0, t=20, b=0),
                                    xaxis_rangeslider_visible=False,
                                )
                                st.plotly_chart(
                                    _fig,
                                    use_container_width=True,
                                    key="candle_" + _t,
                                )
                    else:
                        _err = signals.get("error", "") if isinstance(signals, dict) else ""
                        st.info(f"Technical data loading for {_t}. {_err}")
                except Exception as e:
                    st.info(f"Technical data loading for {_t}. Refresh in a moment.")
    else:
        st.markdown(
            '<div class="amber-box">'
            "Technical analysis loading... Run data_engine.py first to enable"
            " full RSI, MACD, Bollinger, and candlestick charts."
            "</div>",
            unsafe_allow_html=True,
        )
        # Fallback: basic charts with inline yfinance
        for _t in PORTFOLIO_TICKERS:
            with st.expander(
                _t + " - " + position_data[_t]["name"], expanded=False
            ):
                if PLOTLY:
                    try:
                        _hist = fetch_hist(_t, period="3mo")
                        if not _hist.empty:
                            close_vals = _hist["Close"].values.flatten()
                            # Basic RSI
                            delta = pd.Series(close_vals).diff()
                            gain = (
                                delta.where(delta > 0, 0).rolling(14).mean()
                            )
                            loss = (
                                (-delta.where(delta < 0, 0))
                                .rolling(14)
                                .mean()
                            )
                            rs = gain / loss
                            rsi_series = 100 - (100 / (1 + rs))
                            rsi_val = (
                                float(rsi_series.iloc[-1])
                                if not pd.isna(rsi_series.iloc[-1])
                                else 50
                            )

                            # MA50
                            ma50_val = (
                                float(
                                    pd.Series(close_vals)
                                    .rolling(50)
                                    .mean()
                                    .iloc[-1]
                                )
                                if len(close_vals) >= 50
                                else float(close_vals[-1])
                            )
                            ma200_val = (
                                float(
                                    pd.Series(close_vals)
                                    .rolling(200)
                                    .mean()
                                    .iloc[-1]
                                )
                                if len(close_vals) >= 200
                                else 0
                            )

                            rsi_color = (
                                "#A32D2D"
                                if rsi_val > 70
                                else (
                                    "#3B6D11" if rsi_val < 30 else "#888"
                                )
                            )
                            c1, c2 = st.columns(2)
                            c1.markdown(
                                '<div class="card"><strong>RSI(14)</strong><br>'
                                + '<span style="color:'
                                + rsi_color
                                + ';font-size:20px;font-weight:700">'
                                + str(round(rsi_val, 1))
                                + "</span></div>",
                                unsafe_allow_html=True,
                            )

                            if ma200_val > 0:
                                cross_label = (
                                    "Golden Cross"
                                    if ma50_val > ma200_val
                                    else "Death Cross"
                                )
                                cross_c = (
                                    "#3B6D11"
                                    if ma50_val > ma200_val
                                    else "#A32D2D"
                                )
                                c2.markdown(
                                    '<div class="card"><strong>MA 50/200</strong><br>'
                                    + '<span style="color:'
                                    + cross_c
                                    + ';font-weight:600">'
                                    + cross_label
                                    + "</span></div>",
                                    unsafe_allow_html=True,
                                )
                            else:
                                c2.markdown(
                                    '<div class="card"><strong>MA 50</strong><br>'
                                    + fmt_dollar(ma50_val)
                                    + "</div>",
                                    unsafe_allow_html=True,
                                )

                            # Candlestick chart
                            _fig = go.Figure(
                                go.Candlestick(
                                    x=_hist.index,
                                    open=_hist["Open"].values.flatten(),
                                    high=_hist["High"].values.flatten(),
                                    low=_hist["Low"].values.flatten(),
                                    close=_hist["Close"].values.flatten(),
                                )
                            )
                            _fig.update_layout(
                                height=300,
                                margin=dict(l=0, r=0, t=20, b=0),
                                xaxis_rangeslider_visible=False,
                            )
                            st.plotly_chart(
                                _fig,
                                use_container_width=True,
                                key="candle_fb_" + _t,
                            )
                    except Exception:
                        st.info("Chart unavailable for " + _t)
                else:
                    st.info("Install plotly for charts: pip install plotly")

# ===========================================================================
# TAB 3 - War Signals
# ===========================================================================
with tab3:
    st.markdown(
        '<p class="section-label">Geopolitical War Dashboard</p>',
        unsafe_allow_html=True,
    )

    war_data = fetch_war_indicators()
    oil_price = war_data.get("Oil", 0)
    vix_val = war_data.get("VIX", 0)
    sp_val = war_data.get("S&P 500", 0)
    gold_val = war_data.get("Gold", 0)
    tlt_val = war_data.get("TLT", 0)

    # Top metrics row
    m1, m2, m3, m4, m5 = st.columns(5)
    oil_premium = (
        ((oil_price - OIL_BASELINE) / OIL_BASELINE * 100)
        if OIL_BASELINE
        else 0
    )
    oil_cls = (
        "red-box"
        if oil_premium > 15
        else ("amber-box" if oil_premium > 5 else "green-box")
    )
    m1.markdown(
        '<div class="'
        + oil_cls
        + '"><strong>Oil</strong><br>'
        + fmt_dollar(oil_price)
        + "<br>Premium: "
        + fmt_pct(oil_premium)
        + "</div>",
        unsafe_allow_html=True,
    )

    vix_label = (
        "Extreme Fear"
        if vix_val > 30
        else ("Fear" if vix_val > 20 else "Normal")
    )
    vix_cls = (
        "red-box"
        if vix_val > 30
        else ("amber-box" if vix_val > 20 else "green-box")
    )
    m2.markdown(
        '<div class="'
        + vix_cls
        + '"><strong>VIX</strong><br>'
        + str(round(vix_val, 1))
        + "<br>"
        + vix_label
        + "</div>",
        unsafe_allow_html=True,
    )

    m3.markdown(
        '<div class="blue-box"><strong>S&P 500</strong><br>'
        + "{:,.0f}".format(sp_val)
        + "</div>",
        unsafe_allow_html=True,
    )
    m4.markdown(
        '<div class="blue-box"><strong>Gold</strong><br>'
        + fmt_dollar(gold_val)
        + "</div>",
        unsafe_allow_html=True,
    )
    m5.markdown(
        '<div class="blue-box"><strong>TLT</strong><br>'
        + fmt_dollar(tlt_val)
        + "</div>",
        unsafe_allow_html=True,
    )

    # Two columns: ceasefire vs danger signals
    cease_col, danger_col = st.columns(2)

    # Oil day-over-day change for signal checks
    _oil_prev = 0
    try:
        _oil_hist = yf.Ticker("CL=F").history(period="5d")
        if len(_oil_hist) >= 2:
            _oil_prev = float(_oil_hist["Close"].iloc[-2])
    except Exception:
        pass
    _oil_day_chg = ((oil_price - _oil_prev) / _oil_prev * 100) if _oil_prev > 0 else 0

    # VIX3M for term structure check
    _vix3m = 0
    try:
        _vix3m_info = yf.Ticker("^VIX3M").fast_info
        _vix3m = float(_vix3m_info.get("lastPrice", _vix3m_info.get("last_price", 0)))
    except Exception:
        pass

    ceasefire_signals = [
        ("Oil dropped 3%+ in one day", _oil_day_chg <= -3, oil_price > 0),
        ("VIX below 20", vix_val < 20, vix_val > 0),
        ("VIX backwardation (VIX > VIX3M)", vix_val > _vix3m and _vix3m > 0, vix_val > 0 and _vix3m > 0),
        ("Iranian FM uses peace language", False, False),
        ("Mediator country announces talks", False, False),
        ("Trump makes clear peace statement", False, False),
    ]

    danger_signals = [
        ("Oil spiked 10%+ in one day", _oil_day_chg >= 10, oil_price > 0),
        ("VIX above 40", vix_val > 40, vix_val > 0),
        ("S&P drops 5%+ in a week", False, False),
        ("Confirmed escalation news", False, False),
        ("US military asset attacked", False, False),
    ]

    with cease_col:
        st.markdown(
            '<p class="section-label">Ceasefire Signals</p>',
            unsafe_allow_html=True,
        )
        fired_count = 0
        for label, fired, auto_check in ceasefire_signals:
            if auto_check:
                dot = "signal-dot-green" if fired else "signal-dot-gray"
                if fired:
                    fired_count += 1
            else:
                dot = "signal-dot-amber"
            st.markdown(
                '<span class="' + dot + '"></span> ' + label,
                unsafe_allow_html=True,
            )
        st.markdown("**" + str(fired_count) + "/6 signals fired**")

    with danger_col:
        st.markdown(
            '<p class="section-label">Danger Signals</p>',
            unsafe_allow_html=True,
        )
        dfired = 0
        for label, fired, auto_check in danger_signals:
            if auto_check:
                dot = "signal-dot-green" if fired else "signal-dot-gray"
                if fired:
                    dfired += 1
            else:
                dot = "signal-dot-amber"
            st.markdown(
                '<span class="' + dot + '"></span> ' + label,
                unsafe_allow_html=True,
            )
        st.markdown("**" + str(dfired) + "/5 danger signals fired**")

    # Perplexity links for manual signals
    st.markdown(
        '<p class="section-label">Manual Check Links</p>',
        unsafe_allow_html=True,
    )
    perp_queries = [
        (
            "Iran ceasefire / peace talks",
            "https://www.perplexity.ai/search?q=Iran+US+Israel+ceasefire+peace+talks+today",
        ),
        (
            "Iran conflict escalation",
            "https://www.perplexity.ai/search?q=Iran+US+Israel+conflict+escalation+today",
        ),
        (
            "Trump Iran peace statement",
            "https://www.perplexity.ai/search?q=Trump+Iran+ceasefire+peace+statement+today",
        ),
    ]
    for label, url in perp_queries:
        st.markdown("[" + label + "](" + url + ")")

    # Conflict timeline
    st.markdown(
        '<p class="section-label">Conflict Timeline</p>',
        unsafe_allow_html=True,
    )
    if PLOTLY:
        milestones = [
            {"day": 0, "label": "War Start (Feb 28)"},
            {"day": conflict_day, "label": "TODAY (Day " + str(conflict_day) + ")"},
            {"day": 21, "label": "Day 21 (Ceasefire Window)"},
            {"day": 42, "label": "Day 42 (Window Close)"},
            {"day": 100, "label": "Day 100 (Protracted)"},
        ]
        colors_tl = ["#A32D2D", "#185FA5", "#3B6D11", "#633806", "#888"]
        _fig = go.Figure()
        for i_ms, ms in enumerate(milestones):
            _fig.add_trace(
                go.Scatter(
                    x=[ms["day"]],
                    y=[0],
                    mode="markers+text",
                    marker=dict(size=16, color=colors_tl[i_ms]),
                    text=[ms["label"]],
                    textposition="top center",
                    showlegend=False,
                )
            )
        _fig.update_layout(
            height=150,
            margin=dict(l=0, r=0, t=40, b=0),
            yaxis=dict(visible=False, range=[-0.5, 0.5]),
            xaxis=dict(title="Conflict Day"),
        )
        st.plotly_chart(_fig, use_container_width=True)

    # Oil analysis
    st.markdown(
        '<p class="section-label">Oil Analysis</p>', unsafe_allow_html=True
    )
    ceasefire_oil_target = OIL_BASELINE * 1.05
    st.markdown(
        '<div class="blue-box">'
        + "Baseline (pre-conflict): "
        + fmt_dollar(OIL_BASELINE)
        + " &middot; Current: "
        + fmt_dollar(oil_price)
        + " &middot; Premium: "
        + fmt_pct(oil_premium)
        + "<br>Ceasefire target (oil normalizes): below "
        + fmt_dollar(ceasefire_oil_target)
        + "</div>",
        unsafe_allow_html=True,
    )

    # FOMC tracker
    st.markdown(
        '<p class="section-label">FOMC 2026 Schedule</p>',
        unsafe_allow_html=True,
    )
    fomc_html = ""
    for _d in FOMC_DATES:
        fomc_html += (
            '<span class="heat-tile" style="background:#E6F1FB;color:#185FA5">'
            + _d
            + "</span>"
        )
    st.markdown(fomc_html, unsafe_allow_html=True)

# ===========================================================================
# TAB 4 - Opportunities
# ===========================================================================
with tab4:
    st.markdown(
        '<p class="section-label">Fallen Angels & Opportunities</p>',
        unsafe_allow_html=True,
    )

    scan_data = fetch_52w_data(SCAN_UNIVERSE)

    # Sector grouping
    SECTORS = {
        "Airlines": ["DAL", "UAL", "AAL", "LUV", "JBLU"],
        "Cruise & Travel": ["CCL", "RCL", "NCLH", "MAR", "HLT", "ABNB"],
        "Cybersecurity": ["ZS", "CRWD", "PANW", "FTNT", "CYBR", "S"],
        "Social/Tech": ["NFLX", "META", "SNAP", "PINS", "RBLX", "COIN"],
        "Industrial/Ship": ["BA", "GE", "MMM", "ZIM", "SBLK", "DAC"],
        "Cannabis/Nuclear": ["TLRY", "CGC", "NNE", "CCJ", "UEC"],
        "Construction": ["FLR", "KBR", "PWR", "MTZ"],
        "Semiconductors": ["NVDA", "AMD", "INTC", "QCOM", "MU"],
        "Energy": ["XOM", "CVX", "COP", "OXY", "SLB"],
        "Software/Fintech": [
            "ORCL",
            "CRM",
            "ADBE",
            "PYPL",
            "UBER",
            "LYFT",
            "HOOD",
        ],
    }

    # Sector heat map
    st.markdown(
        '<p class="section-label">Sector Heat Map (Avg Drop from 52w High)</p>',
        unsafe_allow_html=True,
    )
    sector_tiles = ""
    for sector, tickers_in_sector in SECTORS.items():
        drops = [
            scan_data[t]["drop_pct"]
            for t in tickers_in_sector
            if t in scan_data
        ]
        avg_drop = float(np.mean(drops)) if drops else 0
        if avg_drop <= -30:
            bg, fg = "#FCEBEB", "#A32D2D"
        elif avg_drop <= -20:
            bg, fg = "#FAEEDA", "#633806"
        elif avg_drop <= -10:
            bg, fg = "#E6F1FB", "#185FA5"
        else:
            bg, fg = "#EAF3DE", "#3B6D11"
        sector_tiles += (
            '<span class="heat-tile" style="background:'
            + bg
            + ";color:"
            + fg
            + '">'
            + sector
            + "<br>"
            + str(round(avg_drop, 1))
            + "%</span>"
        )
    st.markdown(sector_tiles, unsafe_allow_html=True)

    # Fallen angels (30%+)
    fallen = {
        t: d for t, d in scan_data.items() if d["drop_pct"] <= -30
    }
    st.markdown(
        '<p class="section-label">Fallen Angels (30%+ Below 52w High) &mdash; '
        + str(len(fallen))
        + " Found</p>",
        unsafe_allow_html=True,
    )
    for fa_t, fa_d in sorted(
        fallen.items(), key=lambda x: x[1]["drop_pct"]
    ):
        with st.expander(
            fa_t + ": " + str(round(fa_d["drop_pct"], 1)) + "% from 52w high"
        ):
            st.markdown(
                '<div class="red-box">Current: '
                + fmt_dollar(fa_d["price"])
                + " &middot; 52w High: "
                + fmt_dollar(fa_d["high_52w"])
                + " &middot; Drop: "
                + str(round(fa_d["drop_pct"], 1))
                + "%</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                "[Research on Perplexity](https://www.perplexity.ai/search?q="
                + fa_t
                + "+stock+why+dropped+recovery)"
            )

    # Approaching (20-29%)
    approaching = {
        t: d
        for t, d in scan_data.items()
        if -30 < d["drop_pct"] <= -20
    }
    st.markdown(
        '<p class="section-label">Approaching (20-29% Below 52w High) &mdash; '
        + str(len(approaching))
        + " Found</p>",
        unsafe_allow_html=True,
    )
    for ap_t, ap_d in sorted(
        approaching.items(), key=lambda x: x[1]["drop_pct"]
    ):
        with st.expander(
            ap_t
            + ": "
            + str(round(ap_d["drop_pct"], 1))
            + "% from 52w high"
        ):
            st.markdown(
                '<div class="amber-box">Current: '
                + fmt_dollar(ap_d["price"])
                + " &middot; 52w High: "
                + fmt_dollar(ap_d["high_52w"])
                + " &middot; Drop: "
                + str(round(ap_d["drop_pct"], 1))
                + "%</div>",
                unsafe_allow_html=True,
            )

    # Reconstruction watch
    st.markdown(
        '<p class="section-label">Reconstruction Watch</p>',
        unsafe_allow_html=True,
    )
    for _t in ["FLR", "KBR"]:
        if _t in scan_data:
            _d = scan_data[_t]
            st.markdown(
                '<div class="blue-box"><strong>'
                + _t
                + "</strong> &middot; Current: "
                + fmt_dollar(_d["price"])
                + " &middot; 52w High: "
                + fmt_dollar(_d["high_52w"])
                + " &middot; "
                + str(round(_d["drop_pct"], 1))
                + "% from high</div>",
                unsafe_allow_html=True,
            )

# ===========================================================================
# TAB 5 - Momentum
# ===========================================================================
with tab5:
    st.markdown(
        '<p class="section-label">Momentum Stocks (20%+ from 52w Low)</p>',
        unsafe_allow_html=True,
    )

    momentum_universe = list(set(SCAN_UNIVERSE + PORTFOLIO_TICKERS))
    momentum_data = fetch_momentum_data(momentum_universe)

    if momentum_data:
        for mom_t, mom_d in sorted(
            momentum_data.items(),
            key=lambda x: x[1]["gain_pct"],
            reverse=True,
        ):
            in_portfolio = mom_t in PORTFOLIO_TICKERS
            tag = (
                ' <span style="color:#185FA5;font-weight:600">[OWNED]</span>'
                if in_portfolio
                else ""
            )
            st.markdown(
                '<div class="green-box"><strong>'
                + mom_t
                + "</strong>"
                + tag
                + " &middot; "
                + fmt_pct(mom_d["gain_pct"])
                + " from 52w low &middot; Current: "
                + fmt_dollar(mom_d["price"])
                + " &middot; Low: "
                + fmt_dollar(mom_d["low_52w"])
                + "</div>",
                unsafe_allow_html=True,
            )
    else:
        st.info(
            "No stocks 20%+ from 52-week low in scan universe."
        )

    # Portfolio momentum
    st.markdown(
        '<p class="section-label">Your Portfolio Momentum</p>',
        unsafe_allow_html=True,
    )
    defense_tickers = ["LMT", "RTX", "ITA", "BAESY"]
    energy_tickers = ["XOM", "LNG", "CEG"]

    for group_name, group_tickers in [
        ("Defense Holdings", defense_tickers),
        ("Energy Holdings", energy_tickers),
    ]:
        st.markdown("**" + group_name + "**")
        for _t in group_tickers:
            _d = position_data.get(_t, {})
            if _d:
                _cls = color_class(_d["pnl"])
                st.markdown(
                    '<div class="'
                    + _cls
                    + '">'
                    + _t
                    + ": "
                    + fmt_pct(_d["pnl_pct"])
                    + " &middot; P&L: "
                    + fmt_dollar(_d["pnl"])
                    + "</div>",
                    unsafe_allow_html=True,
                )

# ===========================================================================
# TAB 6 - My Crypto
# ===========================================================================
with tab6:
    st.markdown(
        '<p class="section-label">Crypto Portfolio</p>',
        unsafe_allow_html=True,
    )

    crypto_prices = fetch_crypto_prices()
    fg_data = fetch_fear_greed()
    crypto_global = fetch_crypto_global()

    # Top metrics
    mc1, mc2, mc3, mc4 = st.columns(4)
    mkt_cap = crypto_global.get(
        "market_cap",
        CRYPTO_FOUNDATION.get("market_overview", {}).get(
            "total_market_cap_usd", 0
        ),
    )
    btc_dom = crypto_global.get(
        "btc_dominance",
        CRYPTO_FOUNDATION.get("market_overview", {}).get(
            "btc_dominance", 0
        ),
    )

    mc1.markdown(
        '<div class="blue-box"><strong>Market Cap</strong><br>$'
        + str(round(mkt_cap / 1e12, 2))
        + "T</div>",
        unsafe_allow_html=True,
    )
    mc2.markdown(
        '<div class="blue-box"><strong>BTC Dominance</strong><br>'
        + str(round(btc_dom, 1))
        + "%</div>",
        unsafe_allow_html=True,
    )

    fg_val = fg_data.get("value", "N/A")
    fg_label = fg_data.get("label", "N/A")
    fg_cls = (
        "red-box"
        if fg_label in ("Extreme Fear", "Fear")
        else (
            "green-box"
            if fg_label in ("Greed", "Extreme Greed")
            else "amber-box"
        )
    )
    mc3.markdown(
        '<div class="'
        + fg_cls
        + '"><strong>Fear & Greed</strong><br>'
        + str(fg_val)
        + " ("
        + str(fg_label)
        + ")</div>",
        unsafe_allow_html=True,
    )

    xrp_data = crypto_prices.get("ripple", {})
    xrp_price = xrp_data.get("price", CRYPTO_IDS["ripple"]["baseline"])
    xrp_chg = xrp_data.get("change_24h", 0)
    xrp_cls = color_class(xrp_chg)
    mc4.markdown(
        '<div class="'
        + xrp_cls
        + '"><strong>XRP 24h</strong><br>'
        + fmt_dollar(xrp_price)
        + " ("
        + fmt_pct(xrp_chg)
        + ")</div>",
        unsafe_allow_html=True,
    )

    # XRP featured section
    st.markdown(
        '<p class="section-label">XRP (Largest Holding)</p>',
        unsafe_allow_html=True,
    )
    xrp_baseline = CRYPTO_IDS["ripple"]["baseline"]
    xrp_total_chg = (
        ((xrp_price - xrp_baseline) / xrp_baseline * 100)
        if xrp_baseline
        else 0
    )
    xrp_total_cls = color_class(xrp_total_chg)
    xrp_desc = CRYPTO_FOUNDATION.get("ripple", {}).get("description", "")
    st.markdown(
        '<div class="'
        + xrp_total_cls
        + '"><strong>XRP</strong> &mdash; '
        + xrp_desc
        + "<br>Baseline: "
        + fmt_dollar(xrp_baseline)
        + " &middot; Current: "
        + fmt_dollar(xrp_price)
        + " &middot; Change: "
        + fmt_pct(xrp_total_chg)
        + "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "[SEC XRP Watch on Perplexity]"
        "(https://www.perplexity.ai/search?q=SEC+XRP+Ripple+lawsuit+ruling+latest)"
    )

    # Other 4 coins in 2x2
    st.markdown(
        '<p class="section-label">Other Holdings</p>',
        unsafe_allow_html=True,
    )
    other_coins = ["bitcoin", "stellar", "cardano", "hedera-hashgraph"]
    grid_cols = st.columns(2)
    for i_coin, cid in enumerate(other_coins):
        col = grid_cols[i_coin % 2]
        cp = crypto_prices.get(cid, {})
        live_price = cp.get("price", CRYPTO_IDS[cid]["baseline"])
        live_chg = cp.get("change_24h", 0)
        baseline = CRYPTO_IDS[cid]["baseline"]
        total_chg = (
            ((live_price - baseline) / baseline * 100) if baseline else 0
        )
        _cls = color_class(total_chg)
        coin_name = CRYPTO_FOUNDATION.get(cid, {}).get("name", cid)
        ticker = CRYPTO_IDS[cid]["ticker"]
        with col:
            st.markdown(
                '<div class="'
                + _cls
                + '"><strong>'
                + ticker
                + "</strong> ("
                + coin_name
                + ")<br>Price: "
                + fmt_dollar(live_price)
                + " &middot; 24h: "
                + fmt_pct(live_chg)
                + "<br>From baseline: "
                + fmt_pct(total_chg)
                + "</div>",
                unsafe_allow_html=True,
            )

    # Comparison table
    st.markdown(
        '<p class="section-label">All Coins Comparison</p>',
        unsafe_allow_html=True,
    )
    table_rows = []
    for cid, meta in CRYPTO_IDS.items():
        cp = crypto_prices.get(cid, {})
        live_p = cp.get("price", meta["baseline"])
        chg24 = cp.get("change_24h", 0)
        from_base = (
            ((live_p - meta["baseline"]) / meta["baseline"] * 100)
            if meta["baseline"]
            else 0
        )
        table_rows.append(
            {
                "Coin": meta["ticker"],
                "Price": fmt_dollar(live_p),
                "24h Change": fmt_pct(chg24),
                "From Baseline": fmt_pct(from_base),
                "Baseline": fmt_dollar(meta["baseline"]),
            }
        )
    st.dataframe(
        pd.DataFrame(table_rows), use_container_width=True, hide_index=True
    )

# ===========================================================================
# TAB 7 - World Events
# ===========================================================================
with tab7:
    st.markdown(
        '<p class="section-label">World Events & Intelligence</p>',
        unsafe_allow_html=True,
    )

    # Live indicators (use war_data already fetched)
    st.markdown(
        '<p class="section-label">Live Market Indicators</p>',
        unsafe_allow_html=True,
    )
    w1, w2, w3, w4 = st.columns(4)
    w1.markdown(
        '<div class="blue-box"><strong>Oil</strong><br>'
        + fmt_dollar(oil_price)
        + "</div>",
        unsafe_allow_html=True,
    )
    w2.markdown(
        '<div class="blue-box"><strong>Gold</strong><br>'
        + fmt_dollar(gold_val)
        + "</div>",
        unsafe_allow_html=True,
    )
    w3.markdown(
        '<div class="'
        + vix_cls
        + '"><strong>VIX</strong><br>'
        + str(round(vix_val, 1))
        + "</div>",
        unsafe_allow_html=True,
    )
    w4.markdown(
        '<div class="blue-box"><strong>S&P 500</strong><br>'
        + "{:,.0f}".format(sp_val)
        + "</div>",
        unsafe_allow_html=True,
    )

    # Perplexity intelligence prompt
    st.markdown(
        '<p class="section-label">Perplexity Intelligence Prompt</p>',
        unsafe_allow_html=True,
    )
    perp_prompt = (
        "You are a geopolitical market analyst. Today is "
        + today.strftime("%B %d, %Y")
        + ", Day "
        + str(conflict_day)
        + " of the Iran-US-Israel conflict (started Feb 28, 2026).\n\n"
        + "My portfolio: LMT (1 share), RTX (6), LNG (4), GLD (2), ITA (5), "
        + "XOM (7), CEG (4), BAESY (10). Cash: $1,500.33.\n"
        + "Watching: DAL, RCL (ceasefire plays).\n"
        + "Crypto: XRP (largest), BTC, XLM, ADA, HBAR.\n\n"
        + "Current readings:\n"
        + "- Oil: "
        + fmt_dollar(oil_price)
        + " (baseline: $64.56, premium: "
        + fmt_pct(oil_premium)
        + ")\n"
        + "- VIX: "
        + str(round(vix_val, 1))
        + "\n"
        + "- Gold: "
        + fmt_dollar(gold_val)
        + "\n"
        + "- S&P 500: "
        + "{:,.0f}".format(sp_val)
        + "\n\n"
        + "Questions:\n"
        + "1. What is the latest on Iran-US-Israel conflict and ceasefire signals?\n"
        + "2. Any military escalation, new strikes, or diplomatic moves in last 24 hours?\n"
        + "3. Oil market outlook given the Iran war premium?\n"
        + "4. Should I adjust any positions based on today's developments?\n"
        + "5. Any ceasefire signals to enter DAL or RCL?\n"
        + "6. XRP/Ripple SEC lawsuit developments?\n"
        + "7. Ukraine war update — any changes affecting European defence (BAESY)?\n"
    )
    st.code(perp_prompt, language="text")

    # FOMC tracker
    st.markdown(
        '<p class="section-label">FOMC 2026 Schedule</p>',
        unsafe_allow_html=True,
    )
    fomc_display = ""
    for _d in FOMC_DATES:
        fomc_display += (
            '<span class="heat-tile" style="background:#E6F1FB;color:#185FA5">'
            + _d
            + "</span>"
        )
    st.markdown(fomc_display, unsafe_allow_html=True)

    # Macro context
    st.markdown(
        '<p class="section-label">Macro Context</p>', unsafe_allow_html=True
    )
    gpr = FOUNDATION.get("step6_gpr", {})
    shipping = FOUNDATION.get("step5_shipping", {})
    gpr_value = gpr.get("value", "N/A")
    gpr_text = gpr.get("plain_english", "")
    st.markdown(
        '<div class="blue-box"><strong>Geopolitical Risk Index:</strong> '
        + str(gpr_value)
        + " (Normal ~100, Gulf War 280, 9/11 350)<br>"
        + gpr_text
        + "</div>",
        unsafe_allow_html=True,
    )
    ship_current = shipping.get("current", 0)
    ship_trend = shipping.get("trend", "N/A")
    ship_text = shipping.get("plain_english", "")
    st.markdown(
        '<div class="blue-box"><strong>Shipping (ZIM proxy):</strong> $'
        + str(round(ship_current, 2))
        + " &middot; Trend: "
        + ship_trend
        + "<br>"
        + ship_text
        + "</div>",
        unsafe_allow_html=True,
    )

    if ENGINE:
        try:
            macro = get_macro_indicators()
            if macro:
                st.markdown(
                    '<p class="section-label">Macro Indicators (Data Engine)</p>',
                    unsafe_allow_html=True,
                )
                for k, v in macro.items():
                    st.write("**" + str(k) + ":** " + str(v))
        except Exception:
            pass

# ===========================================================================
# TAB 8 - Risk Dashboard
# ===========================================================================
with tab8:
    st.markdown(
        '<p class="section-label">Risk Dashboard</p>', unsafe_allow_html=True
    )

    # Risk metrics
    r1, r2, r3, r4 = st.columns(4)

    # Portfolio beta (approximate)
    defense_weight = (
        sum(
            position_data[t]["value"]
            for t in ["LMT", "RTX", "ITA", "BAESY"]
        )
        / portfolio_value
    )
    energy_weight = (
        sum(position_data[t]["value"] for t in ["XOM", "LNG", "CEG"])
        / portfolio_value
    )
    gold_weight = position_data["GLD"]["value"] / portfolio_value
    # Defense ~0.7 beta, Energy ~1.1, Gold ~0.1
    est_beta = (
        defense_weight * 0.7 + energy_weight * 1.1 + gold_weight * 0.1
    )
    beta_cls = "green-box" if est_beta < 1 else "amber-box"
    r1.markdown(
        '<div class="'
        + beta_cls
        + '"><strong>Est. Beta</strong><br>'
        + str(round(est_beta, 2))
        + "</div>",
        unsafe_allow_html=True,
    )

    # Max drawdown
    max_dd = min(d["pnl_pct"] for d in position_data.values())
    dd_cls = (
        "red-box"
        if max_dd < -15
        else ("amber-box" if max_dd < -5 else "green-box")
    )
    r2.markdown(
        '<div class="'
        + dd_cls
        + '"><strong>Max Drawdown</strong><br>'
        + fmt_pct(max_dd)
        + "</div>",
        unsafe_allow_html=True,
    )

    # Defense concentration
    defense_conc = defense_weight * 100
    conc_cls = "amber-box" if defense_conc > 40 else "green-box"
    r3.markdown(
        '<div class="'
        + conc_cls
        + '"><strong>Defense Concentration</strong><br>'
        + str(round(defense_conc, 1))
        + "%</div>",
        unsafe_allow_html=True,
    )

    # Cash reserve
    cash_pct = CASH / portfolio_value * 100
    cash_cls = "green-box" if cash_pct > 10 else "amber-box"
    r4.markdown(
        '<div class="'
        + cash_cls
        + '"><strong>Cash Reserve</strong><br>'
        + str(round(cash_pct, 1))
        + "%</div>",
        unsafe_allow_html=True,
    )

    # Correlation warning
    st.markdown(
        '<p class="section-label">Correlation Warnings</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="amber-box">'
        "<strong>High Correlation:</strong> LMT, RTX, and ITA are all US defense stocks. "
        "They move together during geopolitical events. If defense sentiment reverses, "
        "all three will decline simultaneously. Consider this concentrated risk."
        "</div>",
        unsafe_allow_html=True,
    )

    # Stress test scenarios
    st.markdown(
        '<p class="section-label">Stress Test Scenarios</p>',
        unsafe_allow_html=True,
    )

    scenarios = [
        {
            "name": "Sudden Ceasefire",
            "description": (
                "War ends abruptly. Defense stocks drop 10-15%, oil drops 15-20%, "
                "gold drops 5%. Travel/airlines surge 15-25%."
            ),
            "impacts": {
                "LMT": -12,
                "RTX": -12,
                "LNG": -10,
                "GLD": -5,
                "ITA": -12,
                "XOM": -8,
                "CEG": -3,
                "BAESY": -12,
            },
        },
        {
            "name": "Major Escalation",
            "description": (
                "Conflict escalates significantly. Defense stocks surge 10-15%, "
                "oil spikes 20%+, VIX above 35."
            ),
            "impacts": {
                "LMT": 12,
                "RTX": 12,
                "LNG": 15,
                "GLD": 8,
                "ITA": 12,
                "XOM": 10,
                "CEG": 5,
                "BAESY": 12,
            },
        },
        {
            "name": "Broad Market Crash (-20%)",
            "description": (
                "Systemic selloff. Most stocks fall. Gold may hold or rise. "
                "High-beta names hit hardest."
            ),
            "impacts": {
                "LMT": -15,
                "RTX": -18,
                "LNG": -20,
                "GLD": 5,
                "ITA": -18,
                "XOM": -20,
                "CEG": -22,
                "BAESY": -15,
            },
        },
        {
            "name": "Oil Shock ($100+)",
            "description": (
                "Oil spikes above $100 on supply disruption. Energy surges, "
                "consumers hurt, recession fears."
            ),
            "impacts": {
                "LMT": 3,
                "RTX": 3,
                "LNG": 20,
                "GLD": 5,
                "ITA": 3,
                "XOM": 18,
                "CEG": 5,
                "BAESY": 3,
            },
        },
    ]

    for scenario in scenarios:
        with st.expander(scenario["name"]):
            st.write(scenario["description"])
            total_impact = 0
            for _t, impact_pct in scenario["impacts"].items():
                _d = position_data[_t]
                dollar_impact = _d["value"] * impact_pct / 100
                total_impact += dollar_impact
                _cls = color_class(impact_pct)
                st.markdown(
                    '<div class="'
                    + _cls
                    + '">'
                    + _t
                    + ": "
                    + fmt_pct(impact_pct)
                    + " &rarr; "
                    + fmt_dollar(dollar_impact)
                    + "</div>",
                    unsafe_allow_html=True,
                )
            total_cls = color_class(total_impact)
            total_impact_pct = total_impact / portfolio_value * 100
            st.markdown(
                '<div class="'
                + total_cls
                + '"><strong>Total Portfolio Impact: '
                + fmt_dollar(total_impact)
                + " ("
                + fmt_pct(total_impact_pct)
                + ")</strong></div>",
                unsafe_allow_html=True,
            )

    # Short interest (inline yfinance — no data engine needed)
    st.markdown(
        '<p class="section-label">Short Interest</p>',
        unsafe_allow_html=True,
    )
    si_rows = []
    for _t in PORTFOLIO_TICKERS:
        try:
            _info = yf.Ticker(_t).info
            _sr = _info.get("shortRatio") or 0
            _spf = _info.get("shortPercentOfFloat") or 0
            _spf = round(_spf * 100, 1) if _spf < 1 else round(_spf, 1)
            _squeeze = "HIGH" if _sr > 5 else ("MODERATE" if _sr > 2 else "LOW")
            si_rows.append({"Stock": _t, "Days to Cover": round(_sr, 1),
                           "Short % Float": str(_spf) + "%", "Squeeze Risk": _squeeze})
        except Exception:
            si_rows.append({"Stock": _t, "Days to Cover": "N/A",
                           "Short % Float": "N/A", "Squeeze Risk": "N/A"})
    if si_rows:
        st.dataframe(pd.DataFrame(si_rows), use_container_width=True, hide_index=True)

    # Analyst ratings (inline yfinance)
    st.markdown(
        '<p class="section-label">Analyst Ratings</p>',
        unsafe_allow_html=True,
    )
    ar_rows = []
    for _t in PORTFOLIO_TICKERS:
        try:
            _info = yf.Ticker(_t).info
            _rec = (_info.get("recommendationKey") or "N/A").replace("_", " ").title()
            _target = _info.get("targetMeanPrice")
            _num = _info.get("numberOfAnalystOpinions") or 0
            _cur = current_prices.get(_t, 0)
            _upside = round((_target - _cur) / _cur * 100, 1) if _target and _cur else 0
            ar_rows.append({"Stock": _t, "Rating": _rec, "Analysts": _num,
                           "Target": fmt_dollar(_target) if _target else "N/A",
                           "Upside": fmt_pct(_upside) if _target else "N/A"})
        except Exception:
            ar_rows.append({"Stock": _t, "Rating": "N/A", "Analysts": 0,
                           "Target": "N/A", "Upside": "N/A"})
    if ar_rows:
        st.dataframe(pd.DataFrame(ar_rows), use_container_width=True, hide_index=True)

    # Sentiment note (StockTwits unreliable on cloud)
    st.markdown(
        '<p class="section-label">Sentiment</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="blue-box">'
        "For real-time sentiment check "
        '<a href="https://www.perplexity.ai/search?q=LMT+RTX+XOM+CEG+stock+sentiment+today" '
        'target="_blank">Perplexity for stock sentiment</a> or visit StockTwits.com directly.'
        "</div>",
        unsafe_allow_html=True,
    )

# ===========================================================================
# FOOTER
# ===========================================================================
st.markdown("---")
st.markdown(
    '<p style="text-align:center;color:#888;font-size:12px">'
    "Ardi Market Command Center v3.0 &middot; Access: ardi-market-dashboard.streamlit.app"
    "</p>",
    unsafe_allow_html=True,
)
