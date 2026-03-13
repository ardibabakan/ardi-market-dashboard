---
COMPLETE SYSTEM AUDIT — March 13, 2026
=======================================

TOTAL FILES READ: 10
TOTAL PROBLEMS FOUND: 17
TOTAL PROBLEMS FIXED: 17
TOTAL UPGRADES MADE: 14

PROBLEMS FIXED:
1. DAILY_RUNNER_PROMPT.txt — Was 32 lines, war-only. Rewritten to 442 lines, world-aware.
2. DAILY_RUNNER_PROMPT.txt — No black swan detection. Added Section B.
3. DAILY_RUNNER_PROMPT.txt — No stop loss/profit alerts. Added Section K.
4. DAILY_RUNNER_PROMPT.txt — No tax tracking, FOMC, weekly, momentum. Added Sections L, M, N, H.
5. DAILY_RUNNER_PROMPT.txt — Fallen angels capped at 5. Now unlimited.
6. dashboard.py — Only 4 tabs. Now 6 tabs (added World Events and Momentum).
7. dashboard.py — No stop loss/profit indicators. Added to every stock card.
8. dashboard.py — No conflict phase indicator. Added with color-coded Day 21 bottom window.
9. dashboard.py — hist_data None crash. Added null check before accessing .columns.
10. dashboard.py — Unused val_color variable. Removed.
11. dashboard.py — No crypto fear & greed, Perplexity, reconstruction. All added.
12. push_to_github.sh — No error handling, only 4 files. Now handles errors, adds all files.
13. launch_dashboard.sh — No streamlit install check. Added.
14. FOUNDATION_PATCH_SUMMARY.md — BAESY -23 days warning. Noted as past (non-breaking).
15. STOCKS_2026-03-13.md — Generic fallen angel reasons. Fixed in new prompt (specific reasons required).
16. BROAD_UNIVERSE_2026-03-13.md — Only 5+1 angels shown. Fixed in new prompt (no limit).
17. requirements.txt — Missing openpyxl. Added.

UPGRADES MADE:
1. Daily runner: World-aware scanning (economics, geopolitics, commodities, weather, health, tech, regulatory)
2. Daily runner: Black swan detector (unprecedented events, institutional stress, 10%+ moves)
3. Daily runner: Stop loss alerts at -15% with Fidelity sell instructions
4. Daily runner: Profit target alerts at +25% with half-position sell instructions
5. Daily runner: Tax tracking (long-term capital gains qualification date)
6. Daily runner: FOMC/Fed tracker with rate cut/hike action guidance
7. Daily runner: Weekly summary every Monday (performance, thesis check)
8. Daily runner: Correlation warning for LMT/RTX/ITA defence cluster
9. Daily runner: Perplexity morning intelligence checklist
10. Daily runner: Momentum scanner for rising stocks
11. Dashboard: 6 tabs (was 4) — added World Events and Momentum
12. Dashboard: Stop loss/profit target on every stock card with visual alerts
13. Dashboard: Conflict phase indicator with Day 21 bottom window tracking
14. Dashboard: Mobile responsive CSS, Perplexity search links, FOMC warning

SHELL SCRIPT FIXES:
- run_daily.sh: Added set -e, exit code checking, prompt file check, fallback claude path
- push_to_github.sh: Added error handling, checks for staged changes before commit, adds all file types
- launch_dashboard.sh: Added streamlit install check

ITEMS NEEDING MANUAL ATTENTION:
1. GitHub repo not yet created — run: gh auth login && gh repo create ardi-market-dashboard --public --source=. --remote=origin --push
2. Streamlit Cloud not yet connected — deploy at share.streamlit.io after GitHub push
3. launchctl scheduler not yet loaded — run: launchctl load ~/Library/LaunchAgents/com.ardi.dailyrunner.plist
4. First world-aware daily report generates tomorrow at 3 AM (or run manually)

HONEST SYSTEM GRADE:
Before this audit: C+ (functional but war-tunnel-vision, no safety alerts, narrow scanning)
After this audit: A- (world-aware, safety nets, 6-tab dashboard, but needs first live run to verify)
Remaining weaknesses:
- Cannot access real-time news (Claude relies on market data as proxy for events)
- Perplexity manual checks still needed for geopolitical signals 4-6
- No SMS/push notification when danger signals fire (would need Twilio or similar)
- Fallen angel "why it dropped" analysis depends on AI reasoning, not live news feeds
- No backtesting of the thesis against historical data

WHAT TO BUILD NEXT IN ORDER OF PRIORITY:
1. Run the first world-aware daily report and verify output quality
2. Complete GitHub + Streamlit Cloud deployment
3. Add SMS alerts via Twilio when danger signals fire
4. Add automated Perplexity API integration (when available)
5. Build backtesting module comparing thesis predictions to actual outcomes
6. Add options flow scanner (unusual options activity detection)
7. Add earnings whisper numbers (consensus vs actual tracking)
8. Build portfolio rebalancing suggestions based on sector drift
---
