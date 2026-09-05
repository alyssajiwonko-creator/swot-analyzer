"""
market_restrictions.py
------------------------
Assembles a picture of the structural / regulatory constraints a company
faces in the broad market: sector-level regulatory exposure, ownership /
governance structure, analyst sentiment, and a keyword scan of recent news
headlines for regulatory, legal, and geopolitical flags.

Note on data sources: Yahoo Finance does not provide a "regulatory risk"
field. This module infers exposure from (a) a static sector->regulatory
intensity map that reflects how heavily each GICS-style sector is typically
regulated, and (b) live news headlines pulled via yfinance, scanned for
keywords. The news scan is a heuristic screen, not a legal/compliance
determination -- always read the linked articles before drawing conclusions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field

from data_fetcher import CompanyData

# Baseline regulatory intensity by sector -- a rough, general-knowledge
# heuristic about how much scrutiny/regulation an industry typically faces
# (antitrust, licensing, rate regulation, safety, environmental, etc.)
SECTOR_REGULATORY_INTENSITY: dict[str, tuple[str, str]] = {
    "Financial Services": ("High", "Banks, insurers, and asset managers face capital requirements, "
                                    "consumer-protection rules, and direct oversight from banking/securities regulators."),
    "Healthcare": ("High", "Drug/device approval pathways, reimbursement policy (Medicare/Medicaid), and "
                            "patient-safety regulation create material approval and pricing risk."),
    "Utilities": ("High", "Rates, service territories, and capital projects are typically set or approved "
                           "by public utility commissions, limiting pricing and expansion flexibility."),
    "Energy": ("High", "Extraction, transport, and emissions are subject to environmental permitting, "
                        "safety regulation, and geopolitical/export policy."),
    "Basic Materials": ("Elevated", "Mining, chemicals, and industrial materials face environmental permitting "
                                     "and, increasingly, carbon/emissions policy."),
    "Communication Services": ("Elevated", "Media, telecom, and large platforms face spectrum licensing, content "
                                            "regulation, and antitrust/competition scrutiny in major markets."),
    "Technology": ("Elevated", "Large-cap tech faces antitrust actions, data-privacy law (GDPR-style regimes), "
                                "export controls on advanced hardware, and AI-specific regulation taking shape globally."),
    "Consumer Defensive": ("Moderate", "Food, beverage, and household-staples companies face safety, labeling, "
                                        "and advertising regulation, generally less disruptive than licensed industries."),
    "Industrials": ("Moderate", "Safety, labor, and trade policy (tariffs) are the primary regulatory levers; "
                                 "defense-related industrials also face export-control regimes."),
    "Real Estate": ("Moderate", "Zoning, land use, and (for REITs) tax-structure rules shape operations."),
    "Consumer Cyclical": ("Moderate", "Retail and discretionary businesses face consumer-protection and, for "
                                       "global supply chains, trade-policy exposure."),
}

DEFAULT_REGULATORY_NOTE = (
    "No sector-specific regulatory profile available for this industry classification; "
    "treat as a general-market baseline and rely on the news scan below."
)

# Keyword categories used to scan headlines for restriction signals.
KEYWORD_CATEGORIES: dict[str, list[str]] = {
    "Antitrust / Competition": [
        r"antitrust", r"monopoly", r"monopolist", r"competition (authority|watchdog|probe)",
        r"ftc\b", r"doj\b", r"merger (block|challenge)", r"anti-competitive",
    ],
    "Regulatory / Compliance": [
        r"\bsec\b", r"regulat(or|ion|ors)", r"compliance", r"fine[sd]?\b", r"penalt(y|ies)",
        r"investigat(ion|ed|ing)", r"subpoena", r"consent decree", r"license (revoke|suspend)",
    ],
    "Litigation / Legal": [
        r"lawsuit", r"sues?\b", r"sued\b", r"class action", r"settlement", r"court rul", r"appeal",
    ],
    "Trade / Tariffs / Geopolitical": [
        r"tariff", r"trade war", r"export control", r"sanction", r"import ban", r"customs",
        r"geopolitic", r"embargo",
    ],
    "Data Privacy / Cyber": [
        r"data breach", r"privacy", r"gdpr", r"cyberattack", r"hack(ed|ing)?\b",
    ],
    "Labor / Environmental": [
        r"strike\b", r"union\b", r"labor dispute", r"osha", r"epa\b", r"emissions", r"environmental",
    ],
}

_COMPILED = {
    cat: [re.compile(p, re.IGNORECASE) for p in patterns]
    for cat, patterns in KEYWORD_CATEGORIES.items()
}


@dataclass
class NewsFlag:
    category: str
    title: str
    link: str | None
    publisher: str | None
    published: object


@dataclass
class MarketRestrictionsReport:
    sector: str | None
    industry: str | None
    regulatory_intensity: str
    regulatory_note: str
    news_flags: list[NewsFlag] = dc_field(default_factory=list)
    flag_counts: dict[str, int] = dc_field(default_factory=dict)
    ownership_notes: list[str] = dc_field(default_factory=list)
    sentiment_notes: list[str] = dc_field(default_factory=list)
    unscanned_reason: str | None = None


def assess_market_restrictions(d: CompanyData) -> MarketRestrictionsReport:
    sector = d.sector
    intensity, note = SECTOR_REGULATORY_INTENSITY.get(sector, ("Unclassified", DEFAULT_REGULATORY_NOTE))

    report = MarketRestrictionsReport(
        sector=sector, industry=d.industry, regulatory_intensity=intensity, regulatory_note=note
    )

    # ---- news keyword scan ----
    if not d.news:
        report.unscanned_reason = (
            "No recent news items were returned by Yahoo Finance for this ticker, "
            "so no regulatory/legal signal could be screened from headlines."
        )
    else:
        counts = {cat: 0 for cat in KEYWORD_CATEGORIES}
        seen_titles = set()
        for item in d.news:
            title = item.get("title") or ""
            if not title or title in seen_titles:
                continue
            for cat, patterns in _COMPILED.items():
                if any(p.search(title) for p in patterns):
                    report.news_flags.append(
                        NewsFlag(
                            category=cat,
                            title=title,
                            link=item.get("link"),
                            publisher=item.get("publisher"),
                            published=item.get("published"),
                        )
                    )
                    counts[cat] += 1
                    seen_titles.add(title)
        report.flag_counts = {k: v for k, v in counts.items() if v > 0}

    # ---- ownership / governance notes ----
    if d.held_by_institutions is not None:
        pct = d.held_by_institutions * 100
        if pct >= 80:
            report.ownership_notes.append(
                f"Institutional ownership is very high ({pct:.0f}%), which can mean strong external "
                "oversight but also concentrated voting power and index-flow sensitivity."
            )
        elif pct <= 20:
            report.ownership_notes.append(
                f"Institutional ownership is low ({pct:.0f}%), which can mean less analyst/institutional "
                "scrutiny and potentially thinner research coverage."
            )
    if d.held_by_insiders is not None:
        pct = d.held_by_insiders * 100
        if pct >= 20:
            report.ownership_notes.append(
                f"Insider ownership is high ({pct:.0f}%) -- founder/management control can limit "
                "minority-shareholder influence over strategic decisions."
            )

    # ---- analyst sentiment as a market-access proxy ----
    if d.recommendation_key:
        report.sentiment_notes.append(
            f"Consensus analyst recommendation: {d.recommendation_key.replace('_', ' ').title()}"
            + (f" across {d.number_of_analyst_opinions} analysts." if d.number_of_analyst_opinions else ".")
        )
    if d.target_mean_price and d.current_price:
        upside = (d.target_mean_price - d.current_price) / d.current_price
        report.sentiment_notes.append(
            f"Mean analyst price target implies {upside * 100:+.1f}% vs. the current price."
        )

    return report
