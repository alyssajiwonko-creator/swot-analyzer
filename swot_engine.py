"""
swot_engine.py
---------------
Synthesizes CompanyData + FinancialRiskReport + MarketRestrictionsReport into
a classic four-quadrant SWOT (Strengths / Weaknesses / Opportunities /
Threats), with Weaknesses and Threats deliberately weighted toward the two
deep-dive areas the user cares about most: financial risk and market/
regulatory restrictions.
"""

from __future__ import annotations

from dataclasses import dataclass

from data_fetcher import CompanyData
from financial_risk import FinancialRiskReport
from market_restrictions import MarketRestrictionsReport


@dataclass
class SwotItem:
    text: str
    detail: str = ""


@dataclass
class SwotReport:
    strengths: list[SwotItem]
    weaknesses: list[SwotItem]
    opportunities: list[SwotItem]
    threats: list[SwotItem]


def build_swot(d: CompanyData, risk: FinancialRiskReport, restrictions: MarketRestrictionsReport) -> SwotReport:
    strengths: list[SwotItem] = []
    weaknesses: list[SwotItem] = []
    opportunities: list[SwotItem] = []
    threats: list[SwotItem] = []

    # ---------------- Strengths ----------------
    for f in risk.factors:
        if f.level == "Low" and f.score is not None:
            strengths.append(SwotItem(f"Strong {f.name.lower()} ({f.value_display})", f.explanation))

    if d.return_on_equity is not None and d.return_on_equity > 0.20:
        strengths.append(SwotItem(
            f"High return on equity ({d.return_on_equity * 100:.1f}%) indicates efficient use of capital.",
        ))
    if d.free_cashflow is not None and d.free_cashflow > 0:
        strengths.append(SwotItem("Positive free cash flow gives the company internal funding flexibility "
                                   "without relying on debt or equity markets."))
    if d.held_by_institutions is not None and 0.4 <= d.held_by_institutions <= 0.85:
        strengths.append(SwotItem(
            f"Healthy institutional ownership ({d.held_by_institutions * 100:.0f}%) suggests broad "
            "professional investor confidence without extreme concentration."
        ))
    if not strengths:
        strengths.append(SwotItem("No standout low-risk financial metrics were identified from available data.",
                                   "This may reflect genuinely mixed fundamentals or gaps in Yahoo Finance's data for this ticker."))

    # ---------------- Weaknesses (financial-risk weighted) ----------------
    for f in risk.factors:
        if f.level in ("Elevated", "High") and f.score is not None:
            weaknesses.append(SwotItem(f"{f.name} is a financial-risk weak point ({f.value_display}, {f.level.lower()} risk).",
                                        f.explanation))
    if risk.overall_level in ("Elevated", "High"):
        weaknesses.append(SwotItem(
            f"Composite financial risk score is {risk.overall_score}/100 ({risk.overall_level.lower()}) -- "
            "materially above what a conservative screen would consider comfortable.",
        ))
    if risk.data_gaps:
        weaknesses.append(SwotItem(
            "Several standard risk metrics are not disclosed/available via Yahoo Finance "
            f"({', '.join(risk.data_gaps[:5])}{'...' if len(risk.data_gaps) > 5 else ''}), "
            "limiting how complete this risk picture can be.",
        ))
    if not weaknesses:
        weaknesses.append(SwotItem("No elevated financial-risk factors were identified from available data."))

    # ---------------- Opportunities ----------------
    if d.revenue_growth is not None and d.revenue_growth > 0.10:
        opportunities.append(SwotItem(f"Revenue growing at {d.revenue_growth * 100:.1f}% YoY suggests expanding "
                                       "demand or market share."))
    if d.earnings_growth is not None and d.earnings_growth > 0.10:
        opportunities.append(SwotItem(f"Earnings growing at {d.earnings_growth * 100:.1f}% YoY."))
    if d.target_mean_price and d.current_price and d.target_mean_price > d.current_price:
        upside = (d.target_mean_price - d.current_price) / d.current_price
        opportunities.append(SwotItem(
            f"Analyst consensus target price implies {upside * 100:.1f}% upside from the current price.",
            "Analyst targets are opinions, not guarantees -- treat as one input among many.",
        ))
    if d.trailing_pe is not None and 0 < d.trailing_pe < 15 and (d.revenue_growth or 0) > 0:
        opportunities.append(SwotItem(
            f"Trailing P/E of {d.trailing_pe:.1f} alongside positive revenue growth may indicate the "
            "market is undervaluing near-term fundamentals (worth further diligence)."
        ))
    if d.dividend_yield is not None and d.dividend_yield > 0.02 and (d.payout_ratio or 1) < 0.6:
        opportunities.append(SwotItem(
            f"Dividend yield of {d.dividend_yield * 100:.1f}% with a payout ratio under 60% leaves room "
            "for continued or growing shareholder returns."
        ))
    if not opportunities:
        opportunities.append(SwotItem("No clear growth or valuation-upside signals were identified from available data."))

    # ---------------- Threats (market-restrictions weighted) ----------------
    if restrictions.regulatory_intensity in ("High", "Elevated"):
        threats.append(SwotItem(
            f"Operates in a sector with {restrictions.regulatory_intensity.lower()} baseline regulatory "
            f"intensity ({restrictions.sector or 'sector unclassified'}).",
            restrictions.regulatory_note,
        ))
    for cat, count in restrictions.flag_counts.items():
        sample = next((nf for nf in restrictions.news_flags if nf.category == cat), None)
        threats.append(SwotItem(
            f"{count} recent headline(s) flagged under '{cat}'.",
            f"Example: \"{sample.title}\"" if sample else "",
        ))
    for f in risk.factors:
        if f.category == "Market Volatility" and f.level in ("Elevated", "High") and f.score is not None:
            threats.append(SwotItem(f"{f.name} signals elevated market-risk exposure ({f.value_display}).",
                                     f.explanation))
    if restrictions.unscanned_reason:
        threats.append(SwotItem("Regulatory/legal news could not be screened for this ticker.",
                                 restrictions.unscanned_reason))
    if not threats:
        threats.append(SwotItem("No elevated regulatory, legal, or market-volatility flags were identified "
                                 "from available data."))

    return SwotReport(strengths=strengths, weaknesses=weaknesses, opportunities=opportunities, threats=threats)
