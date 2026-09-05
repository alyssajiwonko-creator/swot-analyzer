"""
data_fetcher.py
----------------
Thin wrapper around yfinance that pulls everything the SWOT engine needs for
one ticker: company profile, key stats, financial statements, price history,
and recent news headlines.

Every field is fetched defensively -- Yahoo Finance's `info` dict is
inconsistent across tickers (a micro-cap may be missing half the fields a
mega-cap has), so every lookup goes through `_get()` and callers should
always be ready to see `None`.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd
import yfinance as yf


@dataclass
class CompanyData:
    ticker: str
    fetched_at: dt.datetime

    # Identity
    short_name: Optional[str] = None
    long_name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    employees: Optional[int] = None
    summary: Optional[str] = None
    website: Optional[str] = None

    # Price / market
    current_price: Optional[float] = None
    previous_close: Optional[float] = None
    market_cap: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    beta: Optional[float] = None
    avg_volume: Optional[float] = None
    shares_outstanding: Optional[float] = None
    price_quote_time: Optional[str] = None  # human label re: staleness

    # Valuation
    trailing_pe: Optional[float] = None
    forward_pe: Optional[float] = None
    peg_ratio: Optional[float] = None
    price_to_book: Optional[float] = None
    ev_to_ebitda: Optional[float] = None

    # Profitability
    profit_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    gross_margin: Optional[float] = None
    return_on_equity: Optional[float] = None
    return_on_assets: Optional[float] = None
    revenue_growth: Optional[float] = None
    earnings_growth: Optional[float] = None

    # Balance sheet / liquidity / leverage
    total_debt: Optional[float] = None
    total_cash: Optional[float] = None
    current_ratio: Optional[float] = None
    quick_ratio: Optional[float] = None
    debt_to_equity: Optional[float] = None

    # Cash flow
    free_cashflow: Optional[float] = None
    operating_cashflow: Optional[float] = None

    # Dividends / ownership / sentiment
    dividend_yield: Optional[float] = None
    payout_ratio: Optional[float] = None
    held_by_insiders: Optional[float] = None
    held_by_institutions: Optional[float] = None
    short_percent_of_float: Optional[float] = None
    recommendation_key: Optional[str] = None
    target_mean_price: Optional[float] = None
    number_of_analyst_opinions: Optional[int] = None

    # Raw tables (for deep-dive charts)
    price_history: pd.DataFrame = field(default_factory=pd.DataFrame)
    income_stmt: pd.DataFrame = field(default_factory=pd.DataFrame)
    balance_sheet: pd.DataFrame = field(default_factory=pd.DataFrame)
    cashflow_stmt: pd.DataFrame = field(default_factory=pd.DataFrame)
    quarterly_income_stmt: pd.DataFrame = field(default_factory=pd.DataFrame)

    # Interest expense, pulled separately from the income statement for
    # interest-coverage risk (not present in `info`)
    interest_expense: Optional[float] = None
    operating_income: Optional[float] = None

    news: list[dict[str, Any]] = field(default_factory=list)

    errors: list[str] = field(default_factory=list)


def _get(info: dict, *keys: str) -> Any:
    """Return the first present, non-None value for any of `keys`."""
    for k in keys:
        v = info.get(k)
        if v is not None:
            return v
    return None


def _row_value(df: pd.DataFrame, row_names: list[str], col_index: int = 0) -> Optional[float]:
    """Pull a single most-recent-period value out of a yfinance statement
    DataFrame (rows = line items, columns = periods, most recent first)."""
    if df is None or df.empty:
        return None
    for name in row_names:
        if name in df.index:
            try:
                val = df.loc[name].iloc[col_index]
                if pd.notna(val):
                    return float(val)
            except (IndexError, KeyError, ValueError, TypeError):
                continue
    return None


def fetch_company_data(ticker_symbol: str) -> CompanyData:
    ticker_symbol = ticker_symbol.strip().upper()
    data = CompanyData(ticker=ticker_symbol, fetched_at=dt.datetime.now())

    try:
        tk = yf.Ticker(ticker_symbol)
    except Exception as e:  # pragma: no cover - defensive
        data.errors.append(f"Could not initialize ticker: {e}")
        return data

    # ---- info dict (profile, valuation, key stats) ----
    info: dict = {}
    try:
        info = tk.get_info() or {}
    except Exception as e:
        data.errors.append(f"Could not fetch company info from Yahoo Finance: {e}")

    if info:
        data.short_name = _get(info, "shortName")
        data.long_name = _get(info, "longName")
        data.sector = _get(info, "sector")
        data.industry = _get(info, "industry")
        data.country = _get(info, "country")
        data.employees = _get(info, "fullTimeEmployees")
        data.summary = _get(info, "longBusinessSummary")
        data.website = _get(info, "website")

        data.current_price = _get(info, "currentPrice", "regularMarketPrice")
        data.previous_close = _get(info, "previousClose", "regularMarketPreviousClose")
        data.market_cap = _get(info, "marketCap")
        data.fifty_two_week_high = _get(info, "fiftyTwoWeekHigh")
        data.fifty_two_week_low = _get(info, "fiftyTwoWeekLow")
        data.beta = _get(info, "beta")
        data.avg_volume = _get(info, "averageVolume")
        data.shares_outstanding = _get(info, "sharesOutstanding")

        data.trailing_pe = _get(info, "trailingPE")
        data.forward_pe = _get(info, "forwardPE")
        data.peg_ratio = _get(info, "trailingPegRatio", "pegRatio")
        data.price_to_book = _get(info, "priceToBook")
        data.ev_to_ebitda = _get(info, "enterpriseToEbitda")

        data.profit_margin = _get(info, "profitMargins")
        data.operating_margin = _get(info, "operatingMargins")
        data.gross_margin = _get(info, "grossMargins")
        data.return_on_equity = _get(info, "returnOnEquity")
        data.return_on_assets = _get(info, "returnOnAssets")
        data.revenue_growth = _get(info, "revenueGrowth")
        data.earnings_growth = _get(info, "earningsGrowth")

        data.total_debt = _get(info, "totalDebt")
        data.total_cash = _get(info, "totalCash")
        data.current_ratio = _get(info, "currentRatio")
        data.quick_ratio = _get(info, "quickRatio")
        data.debt_to_equity = _get(info, "debtToEquity")

        data.free_cashflow = _get(info, "freeCashflow")
        data.operating_cashflow = _get(info, "operatingCashflow")

        data.dividend_yield = _get(info, "dividendYield")
        data.payout_ratio = _get(info, "payoutRatio")
        data.held_by_insiders = _get(info, "heldPercentInsiders")
        data.held_by_institutions = _get(info, "heldPercentInstitutions")
        data.short_percent_of_float = _get(info, "shortPercentOfFloat")
        data.recommendation_key = _get(info, "recommendationKey")
        data.target_mean_price = _get(info, "targetMeanPrice")
        data.number_of_analyst_opinions = _get(info, "numberOfAnalystOpinions")

    # ---- price history (for volatility + trend charts) ----
    try:
        hist = tk.history(period="1y", interval="1d", auto_adjust=True)
        if hist is not None and not hist.empty:
            data.price_history = hist
            last_ts = hist.index[-1]
            data.price_quote_time = pd.Timestamp(last_ts).strftime("%Y-%m-%d %H:%M")
    except Exception as e:
        data.errors.append(f"Could not fetch price history: {e}")

    # ---- financial statements (for interest coverage, trends) ----
    try:
        data.income_stmt = tk.income_stmt if tk.income_stmt is not None else pd.DataFrame()
    except Exception as e:
        data.errors.append(f"Could not fetch income statement: {e}")
    try:
        data.balance_sheet = tk.balance_sheet if tk.balance_sheet is not None else pd.DataFrame()
    except Exception as e:
        data.errors.append(f"Could not fetch balance sheet: {e}")
    try:
        data.cashflow_stmt = tk.cashflow if tk.cashflow is not None else pd.DataFrame()
    except Exception as e:
        data.errors.append(f"Could not fetch cash flow statement: {e}")
    try:
        data.quarterly_income_stmt = (
            tk.quarterly_income_stmt if tk.quarterly_income_stmt is not None else pd.DataFrame()
        )
    except Exception as e:
        data.errors.append(f"Could not fetch quarterly income statement: {e}")

    data.interest_expense = _row_value(
        data.income_stmt, ["Interest Expense", "Interest Expense Non Operating"]
    )
    data.operating_income = _row_value(data.income_stmt, ["Operating Income"])
    if data.free_cashflow is None:
        data.free_cashflow = _row_value(data.cashflow_stmt, ["Free Cash Flow"])
    if data.operating_cashflow is None:
        data.operating_cashflow = _row_value(
            data.cashflow_stmt, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"]
        )

    # ---- recent news (used by the market-restrictions scanner) ----
    try:
        news_items = tk.get_news(count=25) or []
        cleaned = []
        for item in news_items:
            content = item.get("content", item)  # newer yfinance nests under "content"
            title = content.get("title") or item.get("title")
            if not title:
                continue
            link = (
                content.get("canonicalUrl", {}).get("url")
                if isinstance(content.get("canonicalUrl"), dict)
                else content.get("clickThroughUrl", {}).get("url") if isinstance(content.get("clickThroughUrl"), dict) else None
            ) or item.get("link")
            publisher = (
                content.get("provider", {}).get("displayName")
                if isinstance(content.get("provider"), dict)
                else item.get("publisher")
            )
            pub_date = content.get("pubDate") or item.get("providerPublishTime")
            cleaned.append(
                {
                    "title": title,
                    "link": link,
                    "publisher": publisher,
                    "published": pub_date,
                }
            )
        data.news = cleaned
    except Exception as e:
        data.errors.append(f"Could not fetch recent news: {e}")

    return data
