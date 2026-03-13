#!/usr/bin/env python3
"""
ARDI MARKET DASHBOARD v2.0
Professional financial dashboard — clean, readable at 5 AM.
Every number formatted. Every color meaningful.
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import json, os, glob
from datetime import datetime, date, timedelta
import pytz, requests

# ─── Page setup ──────────────────────────────────────────────
st.set_page_config(page_title="Ardi Dashboard", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""<style>
.block-container{padding-top:.8rem;padding-bottom:.5rem}
[data-testid="stMetricValue"]{font-size:1.15rem}
[data-testid="stMetricDelta"]{font-size:.85rem}
.stTabs [data-baseweb="tab"]{font-size:.95rem;padding:10px 18px;font-weight:600}
.card{background:#f8f9fa;border-radius:10px;padding:16px;margin-bottom:12px;border:1px solid #e9ecef}
.card-red{background:#FCEBEB;border:1px solid #f5c6cb}
.card-green{background:#EAF3DE;border:1px solid #c3e6cb}
.card-amber{background:#FAEEDA;border:1px solid #ffeeba}
.card-blue{background:#E6F1FB;border:1px solid #b8daff}
.heatbox{border-radius:8px;padding:10px 14px;text-align:center;margin:4px}
.badge{display:inline-block;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:600;color:white}
.signal-row{padding:6px 0;border-bottom:1px solid #eee}
@media(max-width:768px){
    .block-container{padding-left:.5rem;padding-right:.5rem}
    h1{font-size:1.4rem!important} h2{font-size:1.1rem!important}
    [data-testid="stMetricValue"]{font-size:.95rem}
}
</style>""", unsafe_allow_html=True)

# ─── Constants ───────────────────────────────────────────────
PAC = pytz.timezone("America/Los_Angeles")
NOW = datetime.now(PAC)
TODAY = NOW.strftime("%Y-%m-%d")
TODAY_NICE = NOW.strftime("%A, %B %d, %Y")
TIME_NICE = NOW.strftime("%I:%M %p Pacific")
WAR_START = date(2026, 2, 28)
WAR_DAYS = max((NOW.date() - WAR_START).days, 0)
OIL_BASE = 64.56
ENTRY_DATE = date(2026, 3, 13)
LTCG_DATE = date(2027, 3, 13)
LTCG_DAYS = max((LTCG_DATE - NOW.date()).days, 0)
FOMC = [date(2026,3,18), date(2026,5,6), date(2026,6,17),
        date(2026,7,29), date(2026,9,16), date(2026,11,4), date(2026,12,16)]
TICKERS = ["LMT","RTX","LNG","GLD","ITA","XOM","CEG","BAESY"]
WATCH = ["DAL","RCL"]

BASE = os.path.dirname(os.path.abspath(__file__))
DAILY = os.path.join(BASE, "Daily")
FOUND = os.path.join(BASE, "AGENT_9_FOUNDATION_PATCH.json")

# ─── Helpers ─────────────────────────────────────────────────
def fmt(v): return f"${v:,.2f}"
def pct(v): return f"{'+' if v>=0 else ''}{v:.1f}%"
def dpct(v): return f"{'+' if v>=0 else ''}${v:,.2f}"

def colored_box(text, style="card"):
    st.markdown(f'<div class="{style}">{text}</div>', unsafe_allow_html=True)

def heatbox(label, value, color):
    st.markdown(
        f'<div class="heatbox" style="background:{color};color:white">'
        f'<div style="font-weight:700;font-size:15px">{label}</div>'
        f'<div style="font-size:18px;font-weight:800">{value}</div></div>',
        unsafe_allow_html=True)

def badge_html(text, bg):
    return f'<span class="badge" style="background:{bg}">{text}</span>'

@st.cache_data(ttl=3600)
def load_found():
    if os.path.exists(FOUND):
        with open(FOUND) as f: return json.load(f)
    return None

def load_md(pfx):
    p = os.path.join(DAILY, f"{pfx}{TODAY}.md")
    if os.path.exists(p):
        with open(p) as f: return f.read(), False
    files = sorted(glob.glob(os.path.join(DAILY, f"{pfx}*.md")), reverse=True)
    if files:
        with open(files[0]) as f: return f.read(), True
    return None, True

@st.cache_data(ttl=3600)
def prices(tickers, period="1mo"):
    try: return yf.download(tickers, period=period, progress=False, auto_adjust=True, threads=True)
    except: return None

@st.cache_data(ttl=3600)
def price1(ticker):
    try:
        h = yf.Ticker(ticker).history(period="5d")
        if len(h)>0: return round(float(h["Close"].iloc[-1]),2)
    except: pass
    return None

@st.cache_data(ttl=3600)
def price_pair(ticker):
    try:
        h = yf.Ticker(ticker).history(period="5d")
        if len(h)>=2: return round(float(h["Close"].iloc[-1]),2), round(float(h["Close"].iloc[-2]),2)
        if len(h)==1: return round(float(h["Close"].iloc[-1]),2), None
    except: pass
    return None, None

@st.cache_data(ttl=3600)
def crypto():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price",
            params={"ids":"bitcoin,ripple,stellar,cardano,hedera-hashgraph",
                    "vs_currencies":"usd","include_24hr_change":"true"},timeout=10)
        if r.status_code==200: return r.json()
    except: pass
    return None

@st.cache_data(ttl=3600)
def crypto_global():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global",timeout=10)
        if r.status_code==200: return r.json().get("data",{})
    except: pass
    return None

@st.cache_data(ttl=3600)
def crypto_fng():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1",timeout=10)
        if r.status_code==200:
            d = r.json().get("data",[{}])[0]
            return int(d.get("value",50)), d.get("value_classification","Neutral")
    except: pass
    return None, None

def sparkline(series, color="#3498db", h=70):
    fig = go.Figure(go.Scatter(y=series.values, x=list(range(len(series))),
        mode="lines", line=dict(color=color,width=2),
        fill="tozeroy", fillcolor=color.replace(")",",0.08)").replace("rgb","rgba") if "rgb" in color else f"rgba(52,152,219,0.08)"))
    fig.update_layout(margin=dict(l=0,r=0,t=0,b=0), height=h,
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig

def next_fomc():
    for d in FOMC:
        if d >= NOW.date(): return d, (d-NOW.date()).days
    return None, None

# ─── Load data ───────────────────────────────────────────────
fd = load_found()
if fd is None:
    st.error("Foundation file missing. Run Agent 9 first.")
    st.stop()

pos = fd["step2_portfolio"]["positions"]
cash = fd["step2_portfolio"]["cash_remaining"]
earn = fd["step3_earnings"]
cbase = fd["step7_crypto"]

emap = {}
for t in TICKERS:
    p = pos[t]
    emap[t] = dict(entry=p["current_price"], shares=p["shares_to_buy"],
        cost=p["total_cost"], name=p["full_name"], desc=p["description"],
        sl=round(p["current_price"]*0.85,2), pt=round(p["current_price"]*1.25,2))

# Live prices
hdata = prices(TICKERS+WATCH, "1mo")
live = {}
for t in TICKERS+WATCH:
    try:
        if hdata is not None and isinstance(hdata.columns, pd.MultiIndex):
            c = hdata["Close"][t].dropna()
        elif hdata is not None:
            c = hdata["Close"].dropna()
        else: c = pd.Series()
        live[t] = {"p": round(float(c.iloc[-1]),2), "s": c} if len(c)>0 else {"p": emap.get(t,{}).get("entry",0), "s": pd.Series()}
    except:
        live[t] = {"p": emap.get(t,{}).get("entry",0), "s": pd.Series()}

# Macro
vix, _ = price_pair("^VIX")
vix3m = price1("^VIX3M")
oil, oil_prev = price_pair("CL=F")
sp = price1("^GSPC")
tlt = price1("TLT")
gold = price1("GC=F")

# Portfolio calc
tot_entry = sum(emap[t]["cost"] for t in TICKERS)
tot_now = sum(live[t]["p"]*emap[t]["shares"] for t in TICKERS)
tot_gl = tot_now - tot_entry
tot_pct = (tot_gl/tot_entry*100) if tot_entry>0 else 0
port_val = tot_now + cash

# Signals
oil_chg = ((oil-oil_prev)/oil_prev*100) if oil and oil_prev and oil_prev>0 else 0
cf_sigs, cf_fired = [], 0
if oil and oil_prev and oil_prev>0:
    f = oil_chg<=-3
    cf_sigs.append(("Oil dropped 3%+ in one day", f, f"Oil {oil_chg:+.1f}% today"))
    if f: cf_fired+=1
else: cf_sigs.append(("Oil dropped 3%+ in one day", False, "Unavailable"))

if vix is not None:
    f = vix<20
    cf_sigs.append(("VIX below 20", f, f"VIX at {vix:.1f}"))
    if f: cf_fired+=1
else: cf_sigs.append(("VIX below 20", False, "Unavailable"))

if vix and vix3m:
    f = vix>vix3m
    cf_sigs.append(("VIX backwardation", f, f"VIX {vix:.1f} vs VIX3M {vix3m:.1f}"))
    if f: cf_fired+=1
else: cf_sigs.append(("VIX backwardation", False, "Unavailable"))

cf_sigs += [("Iranian FM peace language", None, "Manual check"),
            ("Mediator country announced", None, "Manual check"),
            ("Trump peace statement", None, "Manual check")]

esc_sigs, esc_fired = [], 0
if oil and oil_prev and oil_prev>0:
    f = oil_chg>=10
    esc_sigs.append(("Oil spiked 10%+", f, f"Oil {oil_chg:+.1f}%"))
    if f: esc_fired+=1
else: esc_sigs.append(("Oil spiked 10%+", False, "Unavailable"))
if vix is not None:
    f = vix>40
    esc_sigs.append(("VIX above 40", f, f"VIX {vix:.1f}"))
    if f: esc_fired+=1
else: esc_sigs.append(("VIX above 40", False, "Unavailable"))
esc_sigs += [("Iran nuclear announcement", None, "Manual check"),
             ("China-Taiwan escalation", None, "Manual check"),
             ("US carrier attacked", None, "Manual check")]

# Action
dc, stale = load_md("STOCKS_")
act = "HOLD EVERYTHING. No trades needed today."
act_color = "#27ae60"
if dc:
    for line in dc.split("\n"):
        if "TODAY'S ACTION" in line.upper():
            idx = dc.index(line)
            for nl in dc[idx:].split("\n")[1:5]:
                s = nl.strip().strip("#").strip()
                if s and len(s)>10: act=s; break
            break
for kw,c in [("BLACK SWAN","#c0392b"),("DANGER","#c0392b"),("DO NOT TRADE","#c0392b"),
             ("STOP LOSS","#c0392b"),("BUY","#2980b9"),("OPPORTUNITY","#2980b9"),
             ("REVIEW","#e67e22"),("WARNING","#e67e22"),("EARNINGS","#e67e22")]:
    if kw in act.upper(): act_color=c; break

# Alerts
alerts = []
for t in TICKERS:
    e=emap[t]; cp=live[t]["p"]
    if cp<=e["sl"]: alerts.append(("SL",t,e,cp))
    elif cp>=e["pt"]: alerts.append(("PT",t,e,cp))

# ═════════════════════════════════════════════════════════════
# RENDER
# ═════════════════════════════════════════════════════════════

# Refresh
c1,c2 = st.columns([9,1])
with c2:
    if st.button("Refresh"): st.cache_data.clear(); st.rerun()
st.markdown('<meta http-equiv="refresh" content="3600">', unsafe_allow_html=True)

# ── HEADER ───────────────────────────────────────────────────
st.markdown(f'<div style="font-size:18px;font-weight:500;margin-bottom:2px">Good morning Ardi</div>', unsafe_allow_html=True)
st.markdown(f'<div style="font-size:12px;color:#888;margin-bottom:12px">'
    f'{TODAY_NICE} &middot; {TIME_NICE} &middot; Data updated daily at 3 AM</div>', unsafe_allow_html=True)

if stale:
    st.info("Today's report not ready yet. Showing most recent data.")

# Row 2: Portfolio | vs S&P | Conflict
h1, h2, h3 = st.columns([4,4,3])
with h1:
    pcolor = "#3B6D11" if tot_gl>=0 else "#A32D2D"
    st.markdown(f'<div style="font-size:36px;font-weight:800;color:{pcolor};line-height:1.1">{fmt(port_val)}</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="font-size:14px;color:{pcolor};margin-top:2px">{dpct(tot_gl)} ({pct(tot_pct)}) since March 13</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="font-size:12px;color:#888;margin-top:4px">Invested: {fmt(tot_entry)} &middot; Cash: {fmt(cash)}</div>', unsafe_allow_html=True)

with h2:
    if sp:
        sp_base = 5900
        sp_pct = ((sp-sp_base)/sp_base)*100
        diff = tot_pct - sp_pct
        vc = "#3B6D11" if diff>=0 else "#A32D2D"
        word = "outperforming" if diff>=0 else "underperforming"
        st.markdown(f'<div style="font-size:14px;margin-top:8px"><b>vs S&P 500:</b></div>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:13px">Your portfolio {pct(tot_pct)} vs S&P {pct(sp_pct)}</div>', unsafe_allow_html=True)
        st.markdown(f'<div style="font-size:15px;font-weight:700;color:{vc}">{word.title()} by {abs(diff):.1f}%</div>', unsafe_allow_html=True)
    else:
        st.caption("S&P 500 data unavailable")

with h3:
    if WAR_DAYS<21: pc,ptxt="#e67e22",f"Day {WAR_DAYS} &middot; Bottom window: Day 21"
    elif WAR_DAYS<=42: pc,ptxt="#27ae60",f"Day {WAR_DAYS} &middot; Past bottom, recovery"
    else: pc,ptxt="#2980b9",f"Day {WAR_DAYS} &middot; Extended conflict"
    st.markdown(f'<div style="background:{pc};color:white;padding:12px 16px;border-radius:10px;'
        f'text-align:center;margin-top:6px"><div style="font-weight:700;font-size:14px">Iran Conflict</div>'
        f'<div style="font-size:12px;margin-top:2px">{ptxt}</div></div>', unsafe_allow_html=True)

# Action box
st.markdown(f'<div style="background:{act_color};color:white;padding:14px 20px;border-radius:10px;'
    f'font-size:16px;margin:10px 0 16px 0"><b>TODAY\'S ACTION:</b> {act}</div>', unsafe_allow_html=True)

# Stop loss / profit alerts
for at,tk,ed,cp in alerts:
    if at=="SL":
        st.markdown(f'<div class="card-red" style="border-radius:10px;padding:14px 18px;margin-bottom:8px">'
            f'<b style="color:#A32D2D;font-size:16px">STOP LOSS HIT — {tk}</b><br>'
            f'<span style="font-size:13px">Price: {fmt(cp)} &middot; Stop: {fmt(ed["sl"])} &middot; Entry: {fmt(ed["entry"])}<br>'
            f'Fidelity: Search {tk} &rarr; Sell &rarr; Market Order &rarr; {ed["shares"]} shares &rarr; Submit</span></div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="card-green" style="border-radius:10px;padding:14px 18px;margin-bottom:8px">'
            f'<b style="color:#3B6D11;font-size:16px">PROFIT TARGET — {tk}</b><br>'
            f'<span style="font-size:13px">Price: {fmt(cp)} &middot; Target: {fmt(ed["pt"])} &middot; Entry: {fmt(ed["entry"])}<br>'
            f'Consider selling half ({ed["shares"]//2} shares) on Fidelity to lock in gains.</span></div>', unsafe_allow_html=True)

# Data freshness bar
st.markdown(f'<div style="font-size:11px;color:#aaa;margin-bottom:8px">'
    f'Live prices via yfinance &middot; Crypto via CoinGecko &middot; '
    f'Next full report: tomorrow 3 AM Pacific</div>', unsafe_allow_html=True)

# ── TABS ─────────────────────────────────────────────────────
tab1,tab2,tab3,tab4,tab5,tab6 = st.tabs(["My Stocks","War Signals","Opportunities","Momentum","My Crypto","World Events"])

# ═════════════════════════════════════════════════════════════
# TAB 1 — MY STOCKS
# ═════════════════════════════════════════════════════════════
with tab1:
    # Heat map
    st.markdown('<div style="font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#888;margin-bottom:6px">Portfolio at a glance</div>', unsafe_allow_html=True)
    hcols = st.columns(4)
    for i,t in enumerate(TICKERS):
        e=emap[t]; cp=live[t]["p"]
        gl_pct = round((cp-e["entry"])/e["entry"]*100,1) if e["entry"]>0 else 0
        bg = "#EAF3DE" if gl_pct>=0 else "#FCEBEB"
        tc = "#3B6D11" if gl_pct>=0 else "#A32D2D"
        with hcols[i%4]:
            st.markdown(f'<div class="heatbox" style="background:{bg}">'
                f'<div style="font-weight:700;font-size:14px;color:#333">{t}</div>'
                f'<div style="font-size:20px;font-weight:800;color:{tc}">{pct(gl_pct)}</div>'
                f'<div style="font-size:11px;color:#888">{fmt(cp)}</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    # Two columns: stocks | allocation+calendar
    left_col, right_col = st.columns([6,4])

    with left_col:
        st.markdown('<div style="font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#888;margin-bottom:8px">Your 8 positions</div>', unsafe_allow_html=True)

        for t in TICKERS:
            e=emap[t]; cp=live[t]["p"]
            gl_d = round(cp*e["shares"]-e["cost"],2)
            gl_p = round((gl_d/e["cost"])*100,1) if e["cost"]>0 else 0

            # Card style
            card_cls = "card"
            if cp<=e["sl"]: card_cls="card-red"
            elif cp>=e["pt"]: card_cls="card-green"

            badge_t,badge_c = "HOLD","#27ae60"
            if cp<=e["sl"]: badge_t,badge_c="STOP LOSS","#c0392b"
            elif cp>=e["pt"]: badge_t,badge_c="TAKE PROFIT","#f39c12"
            elif gl_p<=-15: badge_t,badge_c="REVIEW","#e74c3c"
            elif gl_p<=-10: badge_t,badge_c="MONITOR","#e67e22"
            elif gl_p>=20: badge_t,badge_c="STRONG","#2ecc71"

            pl_color = "#3B6D11" if gl_d>=0 else "#A32D2D"

            st.markdown(f'<div class="{card_cls}" style="border-radius:10px;padding:16px">'
                f'<div style="display:flex;justify-content:space-between;align-items:center">'
                f'<div><span style="font-size:16px;font-weight:700">{t}</span> '
                f'<span style="font-size:12px;color:#888">{e["name"]}</span></div>'
                f'{badge_html(badge_t,badge_c)}</div>'
                f'<div style="display:flex;gap:24px;margin-top:10px">'
                f'<div><div style="font-size:11px;color:#888">You paid</div><div style="font-size:15px;font-weight:600">{fmt(e["entry"])}</div></div>'
                f'<div><div style="font-size:11px;color:#888">Now</div><div style="font-size:15px;font-weight:600">{fmt(cp)}</div></div>'
                f'<div><div style="font-size:11px;color:#888">Your P&L</div>'
                f'<div style="font-size:15px;font-weight:700;color:{pl_color}">{dpct(gl_d)} ({pct(gl_p)})</div></div></div>'
                f'<div style="font-size:11px;color:#999;margin-top:8px">'
                f'Stop: {fmt(e["sl"])} &middot; Target: {fmt(e["pt"])} &middot; '
                f'{e["shares"]} share{"s" if e["shares"]!=1 else ""}</div>'
                f'</div>', unsafe_allow_html=True)

            # Sparkline
            series = live[t].get("s", pd.Series())
            if len(series)>3:
                lc = "#3B6D11" if gl_d>=0 else "#A32D2D"
                st.plotly_chart(sparkline(series, lc, 55), use_container_width=True, key=f"sp_{t}")

            # Earnings
            ed = earn.get(t,{}).get("next_earnings")
            if ed and ed not in ["Not available","Error"]:
                try:
                    edt = datetime.strptime(ed,"%Y-%m-%d").date()
                    dys = (edt-NOW.date()).days
                    if 0<dys<=7: st.markdown(f'<div class="card-red" style="padding:8px 12px;border-radius:6px;font-size:12px"><b>URGENT:</b> Earnings in {dys} days ({ed})</div>', unsafe_allow_html=True)
                    elif 0<dys<=21: st.markdown(f'<div class="card-amber" style="padding:8px 12px;border-radius:6px;font-size:12px">Earnings in {dys} days ({ed})</div>', unsafe_allow_html=True)
                    elif dys>0: st.caption(f"Earnings: {ed} ({dys} days)")
                    else: st.caption(f"Last reported: {ed}")
                except: pass

        # Watchlist
        st.markdown('<div style="font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#888;margin:16px 0 8px 0">Waiting to buy (Phase B)</div>', unsafe_allow_html=True)
        for t in WATCH:
            p=pos.get(t,{}); cp=live[t]["p"]
            st.markdown(f'<div class="card-blue" style="border-radius:10px;padding:14px">'
                f'<b>{t}</b> — {p.get("full_name",t)}<br>'
                f'<span style="font-size:18px;font-weight:700">{fmt(cp)}</span><br>'
                f'<span style="font-size:12px;color:#555">Buy when 2+ ceasefire signals fire ({cf_fired}/6 now)</span></div>', unsafe_allow_html=True)

    with right_col:
        # Allocation chart
        st.markdown('<div style="font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#888;margin-bottom:8px">How your $10,000 is split</div>', unsafe_allow_html=True)
        cats = {"LMT":"Defence","RTX":"Defence","ITA":"Defence","BAESY":"Defence",
                "LNG":"Energy","XOM":"Energy","GLD":"Safe Haven","CEG":"Nuclear"}
        colors = {"Defence":"#2980b9","Energy":"#27ae60","Safe Haven":"#f39c12","Nuclear":"#8e44ad","Cash":"#95a5a6"}
        alloc = {}
        for t in TICKERS:
            cat = cats[t]
            alloc[cat] = alloc.get(cat,0) + emap[t]["cost"]
        alloc["Cash Reserve"] = cash
        labels = list(alloc.keys())
        values = list(alloc.values())
        bar_colors = [colors.get(l,"#95a5a6") for l in labels]

        fig = go.Figure(go.Bar(y=labels, x=values, orientation="h",
            marker_color=bar_colors, text=[f"{fmt(v)} ({v/10000*100:.0f}%)" for v in values],
            textposition="inside", textfont=dict(color="white",size=12)))
        fig.update_layout(height=220, margin=dict(l=0,r=0,t=0,b=0),
            xaxis=dict(visible=False), yaxis=dict(autorange="reversed"),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

        # Economic calendar
        st.markdown('<div style="font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#888;margin:16px 0 8px 0">Economic calendar</div>', unsafe_allow_html=True)

        events = []
        # FOMC
        fd_d, fd_dy = next_fomc()
        if fd_d: events.append((fd_d, fd_dy, "Fed Meeting (FOMC)", "HIGH"))
        # Earnings
        for t in TICKERS:
            ed = earn.get(t,{}).get("next_earnings")
            if ed and ed not in ["Not available","Error"]:
                try:
                    edt=datetime.strptime(ed,"%Y-%m-%d").date()
                    dys=(edt-NOW.date()).days
                    if dys>0: events.append((edt, dys, f"{t} Earnings", "HIGH" if dys<=14 else "MEDIUM"))
                except: pass
        # Tax
        events.append((LTCG_DATE, LTCG_DAYS, "Long-term tax qualification", "MEDIUM"))

        events.sort(key=lambda x:x[1])
        for ed,dy,name,imp in events[:8]:
            ic = {"HIGH":"#c0392b","MEDIUM":"#e67e22","LOW":"#95a5a6"}.get(imp,"#95a5a6")
            st.markdown(f'<div style="display:flex;align-items:center;padding:5px 0;border-bottom:1px solid #eee">'
                f'<span class="badge" style="background:{ic};font-size:10px;margin-right:8px">{imp}</span>'
                f'<span style="font-size:13px"><b>{name}</b> — {ed} ({dy}d)</span></div>', unsafe_allow_html=True)

    # Portfolio vs S&P chart
    st.markdown("---")
    st.markdown('<div style="font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#888;margin-bottom:6px">Portfolio value over time</div>', unsafe_allow_html=True)
    if hdata is not None:
        try:
            ps = None
            for t in TICKERS:
                sh = emap[t]["shares"]
                s = hdata["Close"][t].dropna()*sh if isinstance(hdata.columns,pd.MultiIndex) else hdata["Close"].dropna()*sh
                ps = s if ps is None else ps.add(s, fill_value=0)
            if ps is not None:
                ps = ps + cash
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=ps.index, y=ps.values, mode="lines", name="Your Portfolio",
                    line=dict(color="#2980b9",width=2.5)))
                fig.add_hline(y=10000, line_dash="dash", line_color="#ccc", annotation_text="$10,000 start")
                fig.update_layout(height=250, margin=dict(l=0,r=0,t=20,b=0),
                    yaxis_title="Value ($)", legend=dict(orientation="h",y=1.12),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)
        except: st.caption("Chart unavailable")

    st.caption(f"Tax: Hold until March 13, 2027 ({LTCG_DAYS} days) for lower capital gains rate.")

# ═════════════════════════════════════════════════════════════
# TAB 2 — WAR SIGNALS
# ═════════════════════════════════════════════════════════════
with tab2:
    # Top metrics
    m1,m2,m3,m4 = st.columns(4)
    with m1:
        if oil:
            prem = round(oil-OIL_BASE,2)
            st.metric("Oil (WTI)", fmt(oil), f"+{fmt(prem)} war premium")
        else: st.metric("Oil","N/A")
    with m2:
        if vix is not None:
            vl = "Calm" if vix<15 else "Normal" if vix<20 else "Worried" if vix<30 else "Scared" if vix<40 else "PANIC"
            st.metric("VIX",f"{vix:.1f}",vl)
        else: st.metric("VIX","N/A")
    with m3:
        if sp: st.metric("S&P 500",f"{sp:,.0f}")
        else: st.metric("S&P 500","N/A")
    with m4:
        if gold: st.metric("Gold",f"${gold:,.0f}")
        else: st.metric("Gold","N/A")

    st.markdown("---")
    lc, rc = st.columns(2)

    with lc:
        st.markdown(f'<div style="font-size:14px;font-weight:700">Ceasefire Signals — {cf_fired} of 6 fired</div>'
            f'<div style="font-size:12px;color:#888;margin-bottom:8px">Buy DAL + RCL when 2 fire</div>', unsafe_allow_html=True)
        st.progress(min(cf_fired/6,1.0))
        for name,fired,detail in cf_sigs:
            dot = "🟢" if fired is True else ("🟡" if fired is None else "⚪")
            st.markdown(f'<div class="signal-row">{dot} <b>{name}</b><br><span style="font-size:12px;color:#888;margin-left:22px">{detail}</span></div>', unsafe_allow_html=True)

        st.markdown("**Manual checks:**")
        for label,q in [("Iranian FM peace","Iranian+foreign+minister+ceasefire+today"),
                        ("Mediator announced","Iran+US+ceasefire+mediator+today"),
                        ("Trump statement","Trump+Iran+peace+ceasefire+today")]:
            st.markdown(f'<a href="https://www.perplexity.ai/search?q={q}" target="_blank" '
                f'style="font-size:13px;margin-left:8px">Search: {label}</a>', unsafe_allow_html=True)

        if cf_fired>=2:
            st.markdown(f'<div class="card-green" style="border-radius:10px;padding:14px;margin-top:8px">'
                f'<b style="color:#3B6D11">BUY SIGNAL:</b> Use $375 for DAL + $375 for RCL from cash reserve.<br>'
                f'Fidelity: Search ticker &rarr; Buy &rarr; Limit Order &rarr; Submit</div>', unsafe_allow_html=True)

    with rc:
        st.markdown(f'<div style="font-size:14px;font-weight:700">Danger Signals — {esc_fired} of 5</div>'
            f'<div style="font-size:12px;color:#888;margin-bottom:8px">If ANY fires — stop everything</div>', unsafe_allow_html=True)
        st.progress(min(esc_fired/5,1.0) if esc_fired>0 else 0.0)
        for name,fired,detail in esc_sigs:
            dot = "🔴" if fired is True else ("🟡" if fired is None else "⚪")
            st.markdown(f'<div class="signal-row">{dot} <b>{name}</b><br><span style="font-size:12px;color:#888;margin-left:22px">{detail}</span></div>', unsafe_allow_html=True)
        if esc_fired>0:
            st.markdown(f'<div class="card-red" style="border-radius:10px;padding:14px;margin-top:8px">'
                f'<b style="color:#A32D2D">DANGER — Do not trade today. Fidelity: 800-343-3548</b></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="card-green" style="border-radius:10px;padding:10px;margin-top:8px;text-align:center">'
                f'<span style="color:#3B6D11;font-weight:600">No danger signals. Positions safe.</span></div>', unsafe_allow_html=True)

    # Oil analysis
    if oil:
        st.markdown("---")
        prem = oil-OIL_BASE; pp = (prem/OIL_BASE)*100
        cfl = round(oil-prem*0.80,2); cfh = round(oil-prem*0.60,2)
        st.markdown(f'<div style="font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#888">Oil market</div>', unsafe_allow_html=True)
        oc1,oc2,oc3,oc4 = st.columns(4)
        oc1.metric("Pre-war", fmt(OIL_BASE))
        oc2.metric("Now", fmt(oil))
        oc3.metric("War Premium", f"+{fmt(prem)}", f"+{pp:.0f}%")
        oc4.metric("After Ceasefire", f"{fmt(cfl)}–{fmt(cfh)}")
        st.caption("When oil drops: XOM falls, DAL and RCL rise. Gulf War 1991: premium collapsed 60-80%.")

    # Conflict timeline
    st.markdown("---")
    st.markdown('<div style="font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#888">Conflict timeline</div>', unsafe_allow_html=True)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0,WAR_DAYS,21,42,100], y=[0]*5, mode="markers+text",
        marker=dict(size=[12,18,14,14,14], color=["#888","#e67e22" if WAR_DAYS<21 else "#27ae60","#e74c3c","#27ae60","#3498db"]),
        text=["Feb 28<br>Start",f"Day {WAR_DAYS}<br>TODAY","Day 21<br>Typical Bottom","Day 42<br>Ceasefire Window","Day 100+<br>Reconstruction"],
        textposition="top center", textfont=dict(size=11)))
    fig.update_layout(height=120, margin=dict(l=20,r=20,t=50,b=10),
        xaxis=dict(range=[-5,110],showgrid=False,zeroline=False),
        yaxis=dict(visible=False), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    fd_d,fd_dy = next_fomc()
    if fd_d:
        st.markdown(f'<div class="card-blue" style="border-radius:8px;padding:10px;text-align:center">'
            f'<b>Next Fed Meeting:</b> {fd_d} ({fd_dy} days) &middot; Rate cut = buy more &middot; Rate hike = hold cash</div>', unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════
# TAB 3 — OPPORTUNITIES
# ═════════════════════════════════════════════════════════════
with tab3:
    bc, bs = load_md("BROAD_UNIVERSE_")
    if bc:
        secs = {"sector":[],"fa":[],"approaching":[],"recon":[]}
        cur = None
        for line in bc.split("\n"):
            lu = line.upper()
            if "SECTOR HEALTH" in lu: cur="sector"; continue
            elif "FALLEN ANGEL OPPORTUNITIES" in lu and "30%" in line: cur="fa"; continue
            elif "APPROACHING FALLEN ANGEL" in lu: cur="approaching"; continue
            elif "RECONSTRUCTION WATCH" in lu: cur="recon"; continue
            elif "CRYPTO" in lu and "UPDATE" in lu: cur=None; continue
            elif "MACRO CONTEXT" in lu: cur=None; continue
            elif line.startswith("-----"): continue
            if cur and line.strip(): secs[cur].append(line)

        # Sector heat map
        if secs["sector"]:
            st.markdown('<div style="font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#888;margin-bottom:8px">Sector health — deeper red = more opportunity</div>', unsafe_allow_html=True)
            scols = st.columns(3)
            for i,line in enumerate(secs["sector"]):
                # Parse sector line
                try:
                    parts = line.split(":**")
                    if len(parts)>=2:
                        sname = parts[0].replace("**","").strip()
                        rest = parts[1].strip()
                        # Extract percentage
                        import re
                        m = re.search(r'(-?\d+\.?\d*)%', rest)
                        pval = float(m.group(1)) if m else 0
                        # Color based on drop
                        if pval<=-30: bg="#c0392b"
                        elif pval<=-20: bg="#e74c3c"
                        elif pval<=-10: bg="#e67e22"
                        else: bg="#95a5a6"
                        tc = "white"
                        with scols[i%3]:
                            st.markdown(f'<div class="heatbox" style="background:{bg};color:{tc}">'
                                f'<div style="font-weight:600;font-size:12px">{sname}</div>'
                                f'<div style="font-size:16px;font-weight:800">{pval:.0f}%</div></div>', unsafe_allow_html=True)
                except: pass
            st.markdown("---")

        # Fallen angels
        if secs["fa"]:
            fa_count = len([l for l in secs["fa"] if l.startswith("###") or (l.startswith("**") and "—" in l and "Watch" not in l)])
            st.markdown(f'<div style="font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#888;margin-bottom:8px">Fallen angels — {fa_count} found (all shown, no limit)</div>', unsafe_allow_html=True)
            for line in secs["fa"]:
                st.markdown(line)
        else:
            st.info("No fallen angels found today.")

        if secs["approaching"]:
            st.markdown("---")
            st.markdown('<div style="font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#888;margin-bottom:8px">Approaching fallen angel territory (20-29%)</div>', unsafe_allow_html=True)
            for line in secs["approaching"]: st.markdown(line)

        if secs["recon"]:
            st.markdown("---")
            st.markdown(f'<div style="font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#888;margin-bottom:8px">Reconstruction watch — Phase C (Day 100+, currently Day {WAR_DAYS})</div>', unsafe_allow_html=True)
            for line in secs["recon"]: st.markdown(line)
    else:
        st.warning("Run the daily runner first.")

# ═════════════════════════════════════════════════════════════
# TAB 4 — MOMENTUM
# ═════════════════════════════════════════════════════════════
with tab4:
    st.markdown(f'<div class="card-blue" style="border-radius:10px;padding:14px">'
        f'<b>Momentum Scanner</b><br><span style="font-size:13px">'
        f'Stocks going UP strongly — up 20%+ from recent low in relevant sectors. '
        f'The opposite of fallen angels.</span></div>', unsafe_allow_html=True)

    if bc:
        mlines = []
        inm = False
        for line in bc.split("\n"):
            if "MOMENTUM" in line.upper() and ("SCANNER" in line.upper() or "OPPORTUNIT" in line.upper()):
                inm=True; continue
            if inm:
                if line.startswith("-----") or ("CRYPTO" in line.upper() and "UPDATE" in line.upper()): inm=False; continue
                if line.strip(): mlines.append(line)
        if mlines:
            for line in mlines: st.markdown(line)
        else:
            st.info("Momentum data generates with the upgraded daily runner. Check back tomorrow.")

    st.markdown("---")
    st.markdown('<div style="font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#888;margin-bottom:8px">Built-in momentum — your defence and energy holdings</div>', unsafe_allow_html=True)
    mc = st.columns(3)
    for i,t in enumerate(["LMT","RTX","ITA","BAESY","LNG","XOM"]):
        e=emap[t]; cp=live[t]["p"]
        gp = round((cp-e["entry"])/e["entry"]*100,1)
        bg = "#EAF3DE" if gp>=0 else "#FCEBEB"
        tc = "#3B6D11" if gp>=0 else "#A32D2D"
        with mc[i%3]:
            st.markdown(f'<div class="heatbox" style="background:{bg}">'
                f'<div style="font-weight:700;font-size:14px;color:#333">{t}</div>'
                f'<div style="font-size:18px;font-weight:800;color:{tc}">{pct(gp)}</div>'
                f'<div style="font-size:11px;color:#888">{fmt(cp)}</div></div>', unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════
# TAB 5 — MY CRYPTO
# ═════════════════════════════════════════════════════════════
with tab5:
    cl = crypto(); cg = crypto_global()
    fng_val, fng_label = crypto_fng()

    # Top metrics
    cm1,cm2,cm3,cm4 = st.columns(4)
    with cm1:
        if cg:
            cap = cg.get("total_market_cap",{}).get("usd",0)
            cm1.metric("Crypto Market Cap", f"${cap/1e12:.2f}T")
    with cm2:
        if cg:
            bd = cg.get("market_cap_percentage",{}).get("btc",0)
            cm2.metric("BTC Dominance", f"{bd:.1f}%")
    with cm3:
        if fng_val:
            fc = "#c0392b" if fng_val<25 else "#e67e22" if fng_val<50 else "#27ae60" if fng_val<75 else "#8e44ad"
            cm3.markdown(f'<div style="text-align:center"><div style="font-size:11px;color:#888">Fear & Greed</div>'
                f'<div style="font-size:24px;font-weight:800;color:{fc}">{fng_val}</div>'
                f'<div style="font-size:12px;color:{fc}">{fng_label}</div></div>', unsafe_allow_html=True)
        else:
            cm3.metric("Fear & Greed", "N/A")
    with cm4:
        if cl and "ripple" in cl:
            xrp_24 = cl["ripple"].get("usd_24h_change",0)
            cm4.metric("XRP 24h", pct(xrp_24))

    st.markdown("---")

    coins = {"ripple":("XRP","XRP","Largest holding — cross-border bank payments"),
             "bitcoin":("Bitcoin","BTC","Original cryptocurrency, digital gold"),
             "stellar":("Stellar","XLM","Payments for developing countries"),
             "cardano":("Cardano","ADA","Proof-of-stake blockchain"),
             "hedera-hashgraph":("Hedera","HBAR","Enterprise ledger — Google, IBM, Boeing")}

    # XRP featured
    if cl and "ripple" in cl:
        xp = cl["ripple"].get("usd",0)
        xb = cbase.get("ripple",{}).get("price_usd",0)
        xchg = round(((xp-xb)/xb)*100,2) if xb else 0
        x24 = cl["ripple"].get("usd_24h_change",0)
        xcolor = "#3B6D11" if xchg>=0 else "#A32D2D"
        st.markdown(f'<div class="card" style="border-radius:12px;padding:18px;border-left:4px solid #2980b9">'
            f'<div style="font-size:16px;font-weight:700">XRP — Your Largest Crypto Holding</div>'
            f'<div style="display:flex;gap:32px;margin-top:10px">'
            f'<div><div style="font-size:11px;color:#888">Now</div><div style="font-size:22px;font-weight:800">${xp}</div></div>'
            f'<div><div style="font-size:11px;color:#888">Baseline</div><div style="font-size:18px;font-weight:600">${xb}</div></div>'
            f'<div><div style="font-size:11px;color:#888">Since Start</div><div style="font-size:18px;font-weight:700;color:{xcolor}">{pct(xchg)}</div></div>'
            f'<div><div style="font-size:11px;color:#888">24h</div><div style="font-size:16px">{pct(x24)}</div></div></div>'
            f'<div style="font-size:12px;color:#888;margin-top:8px">SEC/Ripple Watch: XRP moves violently on court news. '
            f'<a href="https://www.perplexity.ai/search?q=XRP+Ripple+SEC+news+today" target="_blank">Check Perplexity</a></div>'
            f'</div>', unsafe_allow_html=True)

    # Other coins grid
    st.markdown("")
    ocols = st.columns(2)
    for i,cid in enumerate(["bitcoin","stellar","cardano","hedera-hashgraph"]):
        name,ticker,desc = coins[cid]
        if cl and cid in cl:
            cp = cl[cid].get("usd",0)
            c24 = cl[cid].get("usd_24h_change",0)
        else:
            cp = cbase.get(cid,{}).get("price_usd",0); c24=0
        bp = cbase.get(cid,{}).get("price_usd",0)
        chg = round(((cp-bp)/bp)*100,2) if bp else 0
        cc = "#3B6D11" if chg>=0 else "#A32D2D"
        pfmt = f"${cp:,.2f}" if cp>=1 else f"${cp:,.6f}"
        bfmt = f"${bp:,.2f}" if bp>=1 else f"${bp:,.6f}"
        with ocols[i%2]:
            st.markdown(f'<div class="card" style="border-radius:10px;padding:14px">'
                f'<div style="font-weight:700">{name} ({ticker})</div>'
                f'<div style="font-size:12px;color:#888">{desc}</div>'
                f'<div style="display:flex;gap:20px;margin-top:8px">'
                f'<div><span style="font-size:11px;color:#888">Now:</span> <b>{pfmt}</b></div>'
                f'<div><span style="font-size:11px;color:#888">Base:</span> {bfmt}</div>'
                f'<div><span style="font-size:11px;color:#888">Chg:</span> <span style="color:{cc};font-weight:600">{pct(chg)}</span></div>'
                f'<div><span style="font-size:11px;color:#888">24h:</span> {pct(c24)}</div></div></div>', unsafe_allow_html=True)

    # Context
    if fng_val:
        feeling = "extreme fear — people are panic selling" if fng_val<25 else "fear — cautious market" if fng_val<50 else "greed — confident buying" if fng_val<75 else "extreme greed — bubble risk"
        st.caption(f"The Fear & Greed Index is at {fng_val} ({fng_label}). Investors are feeling {feeling}.")

# ═════════════════════════════════════════════════════════════
# TAB 6 — WORLD EVENTS
# ═════════════════════════════════════════════════════════════
with tab6:
    # Black swan check
    if dc and "BLACK SWAN" in dc.upper():
        st.markdown(f'<div class="card-red" style="border-radius:10px;padding:16px">'
            f'<b style="color:#A32D2D;font-size:16px">BLACK SWAN ALERT</b><br>'
            f'An unusual event was detected. Read your STOCKS file immediately.</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="card" style="border-radius:8px;padding:10px;text-align:center">'
            f'<span style="color:#888;font-size:13px">No black swan events detected today</span></div>', unsafe_allow_html=True)

    # Live indicators
    st.markdown("---")
    st.markdown('<div style="font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#888;margin-bottom:8px">Live global indicators</div>', unsafe_allow_html=True)
    g1,g2,g3,g4 = st.columns(4)
    if oil: g1.metric("Oil (WTI)", fmt(oil))
    if gold: g2.metric("Gold", f"${gold:,.0f}")
    if vix: g3.metric("VIX", f"{vix:.1f}")
    if sp: g4.metric("S&P 500", f"{sp:,.0f}")

    # World events from daily file
    if dc:
        evlines = []
        in_ev = False
        for line in dc.split("\n"):
            lu = line.upper()
            if any(k in lu for k in ["GLOBAL EVENT","PORTFOLIO IMPACT","WORLD EVENT","MACRO NUMBER"]):
                in_ev=True; continue
            if in_ev:
                if line.startswith("-----") or (line.startswith("##") and "ACTION" not in line.upper()):
                    if evlines: break
                if line.strip(): evlines.append(line)
        if evlines:
            st.markdown("---")
            st.markdown('<div style="font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#888;margin-bottom:8px">Market context</div>', unsafe_allow_html=True)
            for line in evlines: st.markdown(line)

    # Perplexity prompt
    st.markdown("---")
    st.markdown('<div style="font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:#888;margin-bottom:8px">Morning intelligence checklist</div>', unsafe_allow_html=True)
    st.markdown("Open [Perplexity.ai](https://www.perplexity.ai) and paste:")
    pp = (f"I own: LMT, RTX, LNG, GLD, ITA, XOM, CEG, BAESY. "
        f"Watching: DAL, RCL. Crypto: XRP, BTC, XLM, ADA, HBAR. "
        f"Iran war Day {WAR_DAYS}, Ukraine Year 4. "
        f"Scan every global news source from last 24 hours. "
        f"Find everything affecting my portfolio. "
        f"Check: ceasefire signals, danger signals, XRP news, "
        f"Fed news, fallen angels, black swans. One recommended action.")
    st.code(pp, language=None)

# ─── Footer ──────────────────────────────────────────────────
st.markdown("---")
st.markdown(f'<div style="text-align:center;font-size:12px;color:#aaa">'
    f'Ardi Market Dashboard v2.0 &middot; {TIME_NICE} &middot; '
    f'Works on any device &middot; Bookmark for instant access</div>', unsafe_allow_html=True)
