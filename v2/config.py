import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
BASE_DIR = Path(__file__).parent
ENV_PATH = BASE_DIR / ".env"
if not ENV_PATH.exists():
    ENV_PATH = BASE_DIR.parent / ".env"
load_dotenv(ENV_PATH)

# === API KEYS ===
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
FINNHUB_KEY = os.getenv("FINNHUB_KEY")
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "ardi-market-alerts")
PERPLEXITY_KEY = os.getenv("PERPLEXITY_KEY")
EXA_KEY = os.getenv("EXA_KEY")
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY")
EIA_KEY = os.getenv("EIA_KEY")

# === PATHS ===
V2_DIR = BASE_DIR
V1_DIR = BASE_DIR.parent
AGENT_OUTPUT_DIR = V2_DIR / "data" / "agent_outputs"
CACHE_DIR = V2_DIR / "data" / "cache"
DAILY_DIR = V2_DIR / "Daily"
WEEKLY_DIR = V2_DIR / "Weekly"

# === PORTFOLIO CONFIG ===
# NO POSITIONS EXIST YET — this is the planned portfolio
PORTFOLIO_BUDGET = 10000
CASH_RESERVE_PCT = 0.15  # minimum 15% cash at all times
MAX_POSITION_PCT = 0.15  # no single position > 15%

PLANNED_POSITIONS = {
    "LMT":   {"name": "Lockheed Martin",       "sector": "defence",    "planned": True},
    "RTX":   {"name": "Raytheon Technologies",  "sector": "defence",    "planned": True},
    "LNG":   {"name": "Cheniere Energy",        "sector": "energy_lng", "planned": True},
    "GLD":   {"name": "SPDR Gold Trust",        "sector": "safe_haven", "planned": True},
    "ITA":   {"name": "iShares US A&D ETF",     "sector": "defence_etf","planned": True, "under_review": True},
    "XOM":   {"name": "ExxonMobil",             "sector": "energy",     "planned": True},
    "CEG":   {"name": "Constellation Energy",   "sector": "nuclear",    "planned": True},
    "BAESY": {"name": "BAE Systems ADR",        "sector": "defence_eu", "planned": True},
}

# Phase B — buy on ceasefire
PHASE_B_POSITIONS = {
    "DAL": {"name": "Delta Air Lines",   "budget": 375, "trigger": "2 ceasefire signals"},
    "RCL": {"name": "Royal Caribbean",   "budget": 375, "trigger": "2 ceasefire signals"},
}

# Watchlist — broad universe for fallen angel scanning
SCAN_UNIVERSE = {
    "technology": ["AAPL","MSFT","GOOGL","META","AMZN","NVDA","AMD","INTC","ORCL","CRM","ADBE","NFLX","PYPL","UBER","LYFT","SNAP","PINS","RBLX","COIN","HOOD"],
    "airlines": ["DAL","UAL","AAL","LUV","JBLU","ALK"],
    "cruise": ["CCL","RCL","NCLH"],
    "hotels_travel": ["MAR","HLT","H","ABNB","BKNG","EXPE"],
    "retail": ["TGT","WMT","COST","DG","DLTR","M","KSS"],
    "energy": ["XOM","CVX","COP","SLB","HAL","OXY","DVN","PSX","VLO"],
    "defence": ["LMT","RTX","NOC","GD","HII","BA","LDOS","CACI"],
    "finance": ["JPM","BAC","WFC","C","GS","MS","AXP","V","MA","COF"],
    "healthcare": ["JNJ","PFE","MRNA","ABBV","MRK","LLY","UNH","CVS","HUM"],
    "real_estate": ["AMT","PLD","EQIX","SPG","O","VTR","WY"],
    "industrial": ["CAT","DE","MMM","GE","HON","EMR","ROK","ITW"],
    "construction": ["FLR","KBR","TTEK","PWR","MTZ"],
    "semiconductor": ["QCOM","AVGO","MU","AMAT","LRCX","TSM","ASML"],
    "cybersecurity": ["CRWD","PANW","ZS","FTNT","S","CYBR"],
    "shipping": ["ZIM","DAC","SBLK","MATX"],
    "nuclear": ["CEG","CCJ","UEC","NNE"],
    "biotech": ["MRNA","BNTX","NVAX","VRTX","REGN","BIIB"],
}

# All tickers for scanning (flattened)
ALL_TICKERS = sorted(set(
    list(PLANNED_POSITIONS.keys()) +
    list(PHASE_B_POSITIONS.keys()) +
    [t for sector in SCAN_UNIVERSE.values() for t in sector]
))

# Market indices and benchmarks
INDICES = ["^GSPC", "^VIX", "^VIX3M", "^DJI", "^NDX", "^RUT"]
COMMODITIES = ["CL=F", "BZ=F", "NG=F", "GC=F", "SI=F", "HG=F"]
CURRENCIES = ["DX-Y.NYB", "EURUSD=X", "USDJPY=X"]
TREASURIES = ["TLT", "IEF", "SHY"]

# === CRYPTO CONFIG ===
CRYPTO_HOLDINGS = {
    "ripple":             {"symbol": "XRP", "baseline": 1.40,     "largest": True},
    "bitcoin":            {"symbol": "BTC", "baseline": 71111.00, "largest": False},
    "stellar":            {"symbol": "XLM", "baseline": 0.1626,   "largest": False},
    "cardano":            {"symbol": "ADA", "baseline": 0.72,     "largest": False},
    "hedera-hashgraph":   {"symbol": "HBAR","baseline": 0.28,     "largest": False},
}

# === CONFLICT CONFIG ===
CONFLICT_START_DATE = "2026-02-28"
OIL_BASELINE = 64.56  # pre-conflict WTI

# === SIGNAL THRESHOLDS ===
CEASEFIRE_OIL_DROP_PCT = 3.0
CEASEFIRE_VIX_BELOW = 20
DANGER_OIL_SPIKE_PCT = 10.0
DANGER_VIX_ABOVE = 40
DANGER_SP500_WEEKLY_DROP_PCT = 5.0
DANGER_CREDIT_SPREAD_WIDEN_BPS = 100
STOP_LOSS_PCT = 0.15        # 15% below entry
PROFIT_TARGET_PCT = 0.25    # 25% above entry

# === FOMC DATES 2026 ===
FOMC_DATES = [
    "2026-01-28", "2026-03-18", "2026-05-06", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-11-04", "2026-12-16"
]

# === GOLD PRICE RULE ===
# GC=F (gold futures) is unreliable on cloud deployments
# Always use GLD ETF price × 10.1 as gold price estimate
# Sanity check: result must be between 1500 and 5000
GOLD_MULTIPLIER = 10.1
GOLD_MIN_SANE = 1500
GOLD_MAX_SANE = 5000
