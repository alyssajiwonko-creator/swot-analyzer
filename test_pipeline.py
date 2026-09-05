"""
Offline smoke test for the analysis pipeline (financial_risk, market_restrictions,
swot_engine) using hand-built mock CompanyData objects instead of live Yahoo
Finance calls -- this sandbox's network egress blocks finance.yahoo.com, so this
is how the logic gets exercised before shipping. Run on a machine with normal
internet access and `streamlit run app.py` to test against real data.
"""
import datetime as dt
import numpy as np
import pandas as pd

from data_fetcher import CompanyData
from financial_risk import assess_financial_risk
from market_restrictions import assess_market_restrictions
from swot_engine import build_swot


def make_price_history():
    dates = pd.date_range(end=dt.datetime.now(), periods=252, freq="B")
    prices = 150 + np.cumsum(np.random.normal(0, 2, size=len(dates)))
    return pd.DataFrame({"Close": prices, "Open": prices, "High": prices + 1, "Low": prices - 1,
                          "Volume": np.random.randint(1_000_000, 5_000_000, size=len(dates))}, index=dates)


def healthy_company():
    d = CompanyData(ticker="TEST", fetched_at=dt.datetime.now())
    d.short_name = "Test Healthy Co"
    d.long_name = "Test Healthy Corporation"
    d.sector = "Technology"
    d.industry = "Software - Infrastructure"
    d.country = "United States"
    d.current_price = 190.0
    d.previous_close = 188.0
    d.market_cap = 3_000_000_000_000
    d.fifty_two_week_high = 200.0
    d.fifty_two_week_low = 140.0
    d.beta = 1.1
    d.trailing_pe = 28.0
    d.forward_pe = 25.0
    d.price_to_book = 12.0
    d.profit_margin = 0.25
    d.operating_margin = 0.30
    d.return_on_equity = 0.35
    d.revenue_growth = 0.12
    d.earnings_growth = 0.15
    d.current_ratio = 1.8
    d.quick_ratio = 1.5
    d.debt_to_equity = 80  # yfinance-style percent number -> 0.8x
    d.free_cashflow = 90_000_000_000
    d.operating_cashflow = 100_000_000_000
    d.dividend_yield = 0.005
    d.payout_ratio = 0.15
    d.held_by_institutions = 0.62
    d.held_by_insiders = 0.07
    d.short_percent_of_float = 0.008
    d.recommendation_key = "buy"
    d.target_mean_price = 210.0
    d.number_of_analyst_opinions = 40
    d.operating_income = 30_000_000_000
    d.interest_expense = 500_000_000
    d.price_history = make_price_history()
    d.news = [
        {"title": "Test Healthy Co unveils new product line", "link": "https://example.com/1", "publisher": "Reuters", "published": 1719800000},
        {"title": "Analysts raise price target on Test Healthy Co", "link": "https://example.com/2", "publisher": "Bloomberg", "published": 1719800000},
        {"title": "FTC opens antitrust probe into Test Healthy Co's app store practices", "link": "https://example.com/3", "publisher": "WSJ", "published": 1719800000},
        {"title": "EU regulators fine Test Healthy Co over data privacy violations", "link": "https://example.com/4", "publisher": "FT", "published": 1719800000},
    ]
    return d


def risky_company():
    d = CompanyData(ticker="RISK", fetched_at=dt.datetime.now())
    d.short_name = "Risky Ventures"
    d.long_name = "Risky Ventures Inc"
    d.sector = "Energy"
    d.industry = "Oil & Gas E&P"
    d.country = "United States"
    d.current_price = 8.0
    d.previous_close = 8.5
    d.market_cap = 500_000_000
    d.fifty_two_week_high = 40.0
    d.fifty_two_week_low = 7.5
    d.beta = 2.1
    d.trailing_pe = -5.0
    d.forward_pe = None
    d.price_to_book = 0.6
    d.profit_margin = -0.30
    d.operating_margin = -0.10
    d.return_on_equity = -0.40
    d.revenue_growth = -0.15
    d.earnings_growth = -0.50
    d.current_ratio = 0.7
    d.quick_ratio = 0.4
    d.debt_to_equity = 320  # -> 3.2x
    d.free_cashflow = -200_000_000
    d.operating_cashflow = -50_000_000
    d.dividend_yield = None
    d.payout_ratio = None
    d.held_by_institutions = 0.15
    d.held_by_insiders = 0.35
    d.short_percent_of_float = 0.18
    d.recommendation_key = "hold"
    d.target_mean_price = 9.0
    d.number_of_analyst_opinions = 5
    d.operating_income = -100_000_000
    d.interest_expense = 80_000_000
    d.price_history = make_price_history()
    d.news = [
        {"title": "Risky Ventures sued by shareholders over disclosure failures", "link": "https://example.com/5", "publisher": "Reuters", "published": 1719800000},
        {"title": "Risky Ventures faces new tariff exposure amid trade war escalation", "link": "https://example.com/6", "publisher": "Bloomberg", "published": 1719800000},
    ]
    return d


def empty_company():
    # simulates a ticker Yahoo barely has data for
    d = CompanyData(ticker="THIN", fetched_at=dt.datetime.now())
    d.short_name = "Thin Data Co"
    d.sector = None
    return d


def run_case(label, company):
    print(f"\n{'=' * 70}\n{label}: {company.ticker}\n{'=' * 70}")
    risk = assess_financial_risk(company)
    restrictions = assess_market_restrictions(company)
    swot = build_swot(company, risk, restrictions)

    print(f"Overall risk score: {risk.overall_score} ({risk.overall_level})")
    print("Category scores:", risk.category_scores)
    print(f"Data gaps: {risk.data_gaps}")
    print(f"Regulatory intensity: {restrictions.regulatory_intensity}")
    print(f"News flag categories: {restrictions.flag_counts}")

    for quadrant_name, items in [("STRENGTHS", swot.strengths), ("WEAKNESSES", swot.weaknesses),
                                  ("OPPORTUNITIES", swot.opportunities), ("THREATS", swot.threats)]:
        print(f"\n{quadrant_name} ({len(items)}):")
        for it in items:
            print(f"  - {it.text}")

    # sanity assertions
    assert risk.overall_level in ("Low", "Moderate", "Elevated", "High", "Unknown")
    assert len(swot.strengths) >= 1
    assert len(swot.weaknesses) >= 1
    assert len(swot.opportunities) >= 1
    assert len(swot.threats) >= 1
    print("\n[OK] all quadrants populated, no exceptions raised.")


if __name__ == "__main__":
    np.random.seed(42)
    run_case("HEALTHY COMPANY (should score low/moderate risk)", healthy_company())
    run_case("RISKY COMPANY (should score high risk)", risky_company())
    run_case("THIN-DATA COMPANY (mostly missing fields)", empty_company())
    print("\nAll pipeline smoke tests passed.")
