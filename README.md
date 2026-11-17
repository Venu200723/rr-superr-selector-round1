# RR SupeRR Selector S2 · Round 1: Most Reliable Players Under Pressure

Interactive dashboard: https://venu200723.github.io/rr-superr-selector-round1/

- `index.html`: the dashboard (static page, no tracking)
- `RR_SupeRR_Selector_Round1_Report.pdf`: the methodology report
- `batter_rankings.csv`, `bowler_rankings.csv`, `top10_*.csv`: output tables
- `src/`: the reproducible pipeline (`analysis.py` → `auction_targets.py` → `build_report.py` → `build_dashboard.py`). The raw data pack is not included.
- `rr_auction_targets.csv`, `rr_proposed_xi.csv`, `rr_retained_squad.csv`, `rr_target_verification.csv`: IPL 2027 mini-auction update from the 17 Nov 2026 retention lists (`src/retention/retention_2027.json`).
