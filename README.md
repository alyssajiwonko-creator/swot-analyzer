# SWOT Analyzer — Financial Risk & Market Restrictions

A Streamlit app: type in a stock ticker, pull data from Yahoo Finance, and get
a full SWOT analysis (Strengths / Weaknesses / Opportunities / Threats) with
two dedicated deep-dive sections:

1. **Financial risk** — liquidity, leverage, profitability, market volatility,
   valuation, and cash-flow risk, each scored 0–100 with a plain-English
   explanation.
2. **Market restrictions** — sector-level regulatory intensity plus a live
   keyword scan of recent news headlines for antitrust, regulatory, legal,
   trade/tariff, data-privacy, and labor/environmental flags.

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open the local URL Streamlit prints (usually `http://localhost:8501`)
and enter a ticker (e.g. `AAPL`, `MSFT`, `TSLA`) in the sidebar.

## Project structure

| File | Purpose |
|---|---|
| `data_fetcher.py` | Pulls company profile, key stats, financial statements, price history, and news from Yahoo Finance via `yfinance`. |
| `financial_risk.py` | Scores 12 financial-risk factors across 6 categories (liquidity, leverage, profitability, market volatility, valuation, cash flow). |
| `market_restrictions.py` | Sector regulatory-intensity heuristic + keyword scan of recent news for regulatory/legal/trade signals. |
| `swot_engine.py` | Synthesizes the above into the four SWOT quadrants (Weaknesses & Threats are weighted toward financial risk and market restrictions). |
| `app.py` | The Streamlit UI: Overview, SWOT Summary, Financial Risk Deep-Dive, Market Restrictions Deep-Dive, and Export tabs. |
| `test_pipeline.py` | Offline smoke test of the analysis logic against hand-built mock data (healthy / risky / thin-data companies). Run with `python3 test_pipeline.py`. |
| `test_app.py` | Headless UI test using Streamlit's `AppTest` framework — simulates typing a ticker and clicking Analyze. Run with `python3 test_app.py`. |

## Important notes on the data

- **Not truly real-time.** Free Yahoo Finance access (via `yfinance`) is
  typically delayed 15–20 minutes and can occasionally lag further. There is
  no free *true* real-time feed for U.S. equities; if you need tick-level
  data you'd need a paid provider (e.g. Polygon.io, IEX Cloud, a broker API)
  — the `data_fetcher.py` module is written so you could swap in a different
  source without touching the risk/SWOT logic.
- **Yahoo's unofficial API can change.** `yfinance` scrapes/wraps endpoints
  Yahoo doesn't officially support for third parties, so a field going
  missing or the whole thing breaking after a Yahoo-side change is a known
  risk. Every field lookup in `data_fetcher.py` is defensive (`.get()` with
  fallbacks) and the UI degrades gracefully (shows "n/a" / flags a data gap)
  rather than crashing when a field isn't there.
- **The regulatory/restrictions signal is a heuristic, not a compliance
  tool.** `market_restrictions.py` combines (a) a general sector →
  regulatory-intensity mapping and (b) a keyword scan of recent headline
  *titles* only (not full article text). It's meant to surface things worth
  reading, not to be an authoritative legal risk assessment — always click
  through to the source article.
- **This is a research/screening aid, not investment advice.** Risk scores
  use general-purpose thresholds that aren't adjusted per industry (e.g. a
  "high" debt-to-equity threshold for a bank looks very different from one
  for a software company). Use it as a starting point for your own
  diligence, not a final verdict.

## Testing note

This project was built and tested in a sandboxed environment whose network
egress blocks `finance.yahoo.com`, so the analysis logic and full Streamlit
UI (including all 5 tabs, both light/normal and high-risk color paths) were
verified end-to-end against realistic **mock** data (`test_pipeline.py`,
`test_app.py`) rather than a live call. On your machine, with normal internet
access, `yfinance` will hit Yahoo Finance directly — run
`python3 test_pipeline.py` once after install as a quick sanity check, and if
you hit a field-name mismatch (Yahoo does rename fields occasionally), it'll
show up as a "data gap" in the UI rather than a crash, and is a one-line fix
in `data_fetcher.py`.

## Customizing

- **Add tickers to a watchlist / batch mode:** the whole pipeline is three
  function calls — `fetch_company_data(ticker)` →
  `assess_financial_risk(data)` / `assess_market_restrictions(data)` →
  `build_swot(data, risk, restrictions)` — so wrapping it in a loop over a
  list of tickers for a batch report is straightforward.
- **Adjust risk thresholds:** each factor in `financial_risk.py` uses a
  `_score_band(value, [(threshold, risk_score), ...])` control-point list —
  edit the numbers to make scoring stricter/looser or industry-specific.
- **Add more regulatory keywords:** extend `KEYWORD_CATEGORIES` in
  `market_restrictions.py`.
