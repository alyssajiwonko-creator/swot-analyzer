"""
financial_risk.py
------------------
Turns the raw CompanyData pulled from Yahoo Finance into a structured
financial-risk assessment: a set of scored risk factors across liquidity,
leverage, profitability, volatility, valuation, and cash flow, plus an
overall composite score.

Scoring convention: every factor is scored 0-100 where HIGHER = RISKIER.
Thresholds are general-purpose heuristics (not industry-adjusted) and are
intentionally conservative/transparent so a user can see exactly why a
score landed where it did -- this is a screening tool, not investment advice.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from data_fetcher import CompanyData

LEVELS = ["Low", "Moderate", "Elevated", "High"]


def _level_from_score(score: float) -> str:
    if score < 25:
        return "Low"
    if score < 50:
        return "Moderate"
    if score < 75:
        return "Elevated"
    return "High"


def _clamp(x: float, lo: float = 0, hi: float = 100) -> float:
    return max(lo, min(hi, x))


@dataclass
class RiskFactor:
    category: str
    name: str
    value_display: str
    score: Optional[float]  # 0-100, higher = riskier; None if data unavailable
    level: str
    explanation: str


@dataclass
class FinancialRiskReport:
    overall_score: Optional[float]
    overall_level: str
    factors: list[RiskFactor]
    category_scores: dict[str, Optional[float]]
    data_gaps: list[str]


def _pct(x: Optional[float]) -> str:
    return f"{x * 100:.1f}%" if x is not None else "n/a"


def _num(x: Optional[float], decimals: int = 2) -> str:
    return f"{x:.{decimals}f}" if x is not None else "n/a"


def _score_band(value: Optional[float], bands: list[tuple[float, float]], reverse: bool = False) -> Optional[float]:
    """
    Piecewise-linear scoring helper.
    `bands` is a list of (value_threshold, risk_score) control points, sorted
    by value ascending. Score is interpolated between control points and
    clamped at the ends. If `reverse` is True, higher raw values mean LOWER
    risk (e.g. current ratio), so bands should already encode that mapping.
    """
    if value is None:
        return None
    xs = [b[0] for b in bands]
    ys = [b[1] for b in bands]
    if value <= xs[0]:
        return _clamp(ys[0])
    if value >= xs[-1]:
        return _clamp(ys[-1])
    for i in range(len(xs) - 1):
        if xs[i] <= value <= xs[i + 1]:
            span = xs[i + 1] - xs[i]
            t = (value - xs[i]) / span if span else 0
            return _clamp(ys[i] + t * (ys[i + 1] - ys[i]))
    return _clamp(ys[-1])


def assess_financial_risk(d: CompanyData) -> FinancialRiskReport:
    factors: list[RiskFactor] = []
    gaps: list[str] = []

    # ---------------- Liquidity risk ----------------
    cr_score = _score_band(d.current_ratio, [(0.5, 100), (1.0, 70), (1.5, 40), (2.0, 15), (3.0, 5)])
    factors.append(
        RiskFactor(
            "Liquidity", "Current Ratio", _num(d.current_ratio), cr_score,
            _level_from_score(cr_score) if cr_score is not None else "Unknown",
            "Current assets vs. current liabilities. Below 1.0 means short-term obligations "
            "exceed short-term assets -- a red flag for near-term solvency.",
        )
    )
    if d.current_ratio is None:
        gaps.append("Current ratio")

    qr_score = _score_band(d.quick_ratio, [(0.3, 100), (0.7, 70), (1.0, 40), (1.5, 15), (2.5, 5)])
    factors.append(
        RiskFactor(
            "Liquidity", "Quick Ratio", _num(d.quick_ratio), qr_score,
            _level_from_score(qr_score) if qr_score is not None else "Unknown",
            "Like the current ratio but excludes inventory -- a stricter test of whether the "
            "company can cover near-term liabilities with its most liquid assets.",
        )
    )
    if d.quick_ratio is None:
        gaps.append("Quick ratio")

    # ---------------- Leverage risk ----------------
    # yfinance reports debtToEquity as a percentage-style number (e.g. 150 = 1.5x)
    dte = d.debt_to_equity / 100 if d.debt_to_equity is not None and d.debt_to_equity > 5 else d.debt_to_equity
    dte_score = _score_band(dte, [(0.0, 5), (0.5, 25), (1.0, 50), (2.0, 80), (3.5, 100)])
    factors.append(
        RiskFactor(
            "Leverage", "Debt-to-Equity", f"{dte:.2f}x" if dte is not None else "n/a", dte_score,
            _level_from_score(dte_score) if dte_score is not None else "Unknown",
            "Total debt relative to shareholder equity. Higher leverage amplifies both gains "
            "and losses and increases refinancing / bankruptcy risk in downturns.",
        )
    )
    if dte is None:
        gaps.append("Debt-to-equity")

    interest_coverage = None
    if d.operating_income is not None and d.interest_expense not in (None, 0):
        interest_coverage = abs(d.operating_income / d.interest_expense)
    ic_score = _score_band(interest_coverage, [(1.0, 100), (2.0, 75), (4.0, 45), (8.0, 15), (15.0, 5)])
    factors.append(
        RiskFactor(
            "Leverage", "Interest Coverage", f"{interest_coverage:.1f}x" if interest_coverage else "n/a",
            ic_score, _level_from_score(ic_score) if ic_score is not None else "Unknown",
            "Operating income divided by interest expense -- how many times over the company "
            "can pay the interest on its debt from operating profit. Below 2x is a distress signal.",
        )
    )
    if interest_coverage is None:
        gaps.append("Interest coverage (interest expense not reported)")

    # ---------------- Profitability risk ----------------
    pm_score = _score_band(d.profit_margin, [(-0.2, 100), (0.0, 75), (0.05, 50), (0.15, 20), (0.30, 5)])
    factors.append(
        RiskFactor(
            "Profitability", "Net Profit Margin", _pct(d.profit_margin), pm_score,
            _level_from_score(pm_score) if pm_score is not None else "Unknown",
            "Net income as a share of revenue. Thin or negative margins leave little cushion "
            "if costs rise or pricing power weakens.",
        )
    )
    if d.profit_margin is None:
        gaps.append("Net profit margin")

    roe_score = _score_band(d.return_on_equity, [(-0.1, 100), (0.0, 70), (0.05, 50), (0.15, 20), (0.25, 5)])
    factors.append(
        RiskFactor(
            "Profitability", "Return on Equity", _pct(d.return_on_equity), roe_score,
            _level_from_score(roe_score) if roe_score is not None else "Unknown",
            "Net income relative to shareholder equity -- how efficiently the company turns "
            "equity capital into profit.",
        )
    )
    if d.return_on_equity is None:
        gaps.append("Return on equity")

    rg_score = _score_band(d.revenue_growth, [(-0.2, 100), (0.0, 65), (0.05, 40), (0.15, 15), (0.3, 5)])
    factors.append(
        RiskFactor(
            "Profitability", "Revenue Growth (YoY)", _pct(d.revenue_growth), rg_score,
            _level_from_score(rg_score) if rg_score is not None else "Unknown",
            "Year-over-year revenue growth. Shrinking or stagnant revenue raises questions "
            "about competitive position and demand.",
        )
    )
    if d.revenue_growth is None:
        gaps.append("Revenue growth")

    # ---------------- Volatility / market risk ----------------
    beta_score = _score_band(d.beta, [(0.5, 10), (1.0, 30), (1.3, 55), (1.8, 80), (2.5, 100)])
    factors.append(
        RiskFactor(
            "Market Volatility", "Beta (vs. broad market)", _num(d.beta), beta_score,
            _level_from_score(beta_score) if beta_score is not None else "Unknown",
            "Sensitivity of the stock's price to overall market moves. Beta above 1.3 means "
            "the stock has historically swung noticeably more than the market.",
        )
    )
    if d.beta is None:
        gaps.append("Beta")

    range_position = None
    if d.current_price and d.fifty_two_week_high and d.fifty_two_week_low and d.fifty_two_week_high > d.fifty_two_week_low:
        range_position = (d.current_price - d.fifty_two_week_low) / (d.fifty_two_week_high - d.fifty_two_week_low)
    # Being pinned near the 52-week low is the riskier signal here
    drawdown_score = _score_band(range_position, [(0.0, 90), (0.25, 65), (0.5, 40), (0.75, 20), (1.0, 10)]) if range_position is not None else None
    factors.append(
        RiskFactor(
            "Market Volatility", "Position in 52-Week Range",
            f"{range_position * 100:.0f}% of range" if range_position is not None else "n/a",
            drawdown_score, _level_from_score(drawdown_score) if drawdown_score is not None else "Unknown",
            "Where the current price sits between its 52-week low (0%) and high (100%). "
            "Trading near the low can reflect deteriorating fundamentals or sentiment.",
        )
    )
    if range_position is None:
        gaps.append("52-week range position")

    short_score = _score_band(d.short_percent_of_float, [(0.01, 10), (0.03, 30), (0.06, 55), (0.10, 80), (0.20, 100)])
    factors.append(
        RiskFactor(
            "Market Volatility", "Short Interest (% of float)", _pct(d.short_percent_of_float), short_score,
            _level_from_score(short_score) if short_score is not None else "Unknown",
            "Share of the tradable float sold short. Elevated short interest signals the "
            "market sees meaningful downside risk (and can also fuel volatility via squeezes).",
        )
    )
    if d.short_percent_of_float is None:
        gaps.append("Short interest")

    # ---------------- Valuation risk ----------------
    pe_score = _score_band(d.trailing_pe, [(5, 10), (15, 25), (25, 45), (40, 70), (70, 95)]) if d.trailing_pe and d.trailing_pe > 0 else (95 if d.trailing_pe is not None and d.trailing_pe <= 0 else None)
    factors.append(
        RiskFactor(
            "Valuation", "Trailing P/E", _num(d.trailing_pe, 1), pe_score,
            _level_from_score(pe_score) if pe_score is not None else "Unknown",
            "Price relative to trailing earnings. A very high (or negative) P/E means the "
            "stock is pricing in a lot of future growth -- more room to disappoint.",
        )
    )
    if d.trailing_pe is None:
        gaps.append("Trailing P/E")

    # ---------------- Cash flow risk ----------------
    fcf_margin = None
    rev = _row_value_placeholder(d)
    fcf_score = None
    if d.free_cashflow is not None and d.market_cap:
        fcf_yield = d.free_cashflow / d.market_cap
        fcf_score = _score_band(fcf_yield, [(-0.1, 100), (0.0, 70), (0.02, 45), (0.06, 15), (0.12, 5)])
        factors.append(
            RiskFactor(
                "Cash Flow", "Free Cash Flow Yield", _pct(fcf_yield), fcf_score,
                _level_from_score(fcf_score) if fcf_score is not None else "Unknown",
                "Free cash flow relative to market cap. Negative or thin FCF yield means the "
                "business is burning cash relative to its valuation, or reliant on external financing.",
            )
        )
    else:
        factors.append(
            RiskFactor("Cash Flow", "Free Cash Flow Yield", "n/a", None, "Unknown",
                        "Free cash flow or market cap not available from Yahoo Finance for this ticker.")
        )
        gaps.append("Free cash flow yield")

    # ---------------- Composite scores ----------------
    category_scores: dict[str, Optional[float]] = {}
    for cat in ["Liquidity", "Leverage", "Profitability", "Market Volatility", "Valuation", "Cash Flow"]:
        cat_scores = [f.score for f in factors if f.category == cat and f.score is not None]
        category_scores[cat] = round(sum(cat_scores) / len(cat_scores), 1) if cat_scores else None

    weights = {
        "Liquidity": 0.20,
        "Leverage": 0.25,
        "Profitability": 0.20,
        "Market Volatility": 0.15,
        "Valuation": 0.10,
        "Cash Flow": 0.10,
    }
    weighted_sum = 0.0
    weight_total = 0.0
    for cat, score in category_scores.items():
        if score is not None:
            weighted_sum += score * weights[cat]
            weight_total += weights[cat]
    overall = round(weighted_sum / weight_total, 1) if weight_total > 0 else None

    return FinancialRiskReport(
        overall_score=overall,
        overall_level=_level_from_score(overall) if overall is not None else "Unknown",
        factors=factors,
        category_scores=category_scores,
        data_gaps=gaps,
    )


def _row_value_placeholder(d: CompanyData):
    # kept for potential future revenue-based cash-burn metrics; currently unused
    return None
