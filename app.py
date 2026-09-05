"""
SWOT Analyzer -- Financial Risk & Market Restrictions
=======================================================
Streamlit app: type in a ticker, pull live-ish data from Yahoo Finance
(via yfinance), and get a full SWOT analysis with deep-dive sections on
financial risk and market/regulatory restrictions.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data_fetcher import fetch_company_data, CompanyData
from financial_risk import assess_financial_risk, FinancialRiskReport, _level_from_score
from market_restrictions import assess_market_restrictions, MarketRestrictionsReport
from swot_engine import build_swot, SwotReport

# ---------------------------------------------------------------------------
# Palette (validated categorical / status colors -- see project README)
# ---------------------------------------------------------------------------
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"

SERIES_BLUE = "#2a78d6"
SERIES_ORANGE = "#eb6834"
SERIES_AQUA = "#1baf7a"
SERIES_YELLOW = "#eda100"
SERIES_RED = "#e34948"

STATUS_GOOD = "#0ca30c"
STATUS_WARNING = "#fab219"
STATUS_SERIOUS = "#ec835a"
STATUS_CRITICAL = "#d03b3b"

LEVEL_COLOR = {
    "Low": STATUS_GOOD,
    "Moderate": STATUS_WARNING,
    "Elevated": STATUS_SERIOUS,
    "High": STATUS_CRITICAL,
    "Unknown": INK_MUTED,
}

QUADRANT_COLOR = {
    "Strengths": SERIES_AQUA,
    "Weaknesses": SERIES_YELLOW,
    "Opportunities": SERIES_BLUE,
    "Threats": SERIES_RED,
}

PLOTLY_FONT = dict(family="system-ui, -apple-system, 'Segoe UI', sans-serif", color=INK_PRIMARY)

st.set_page_config(page_title="SWOT Analyzer", page_icon="📊", layout="wide")


# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def load_all(ticker: str):
    company = fetch_company_data(ticker)
    risk = assess_financial_risk(company)
    restrictions = assess_market_restrictions(company)
    swot = build_swot(company, risk, restrictions)
    return company, risk, restrictions, swot


def fmt_money(x, suffix=""):
    if x is None:
        return "n/a"
    abs_x = abs(x)
    if abs_x >= 1e12:
        return f"${x / 1e12:.2f}T{suffix}"
    if abs_x >= 1e9:
        return f"${x / 1e9:.2f}B{suffix}"
    if abs_x >= 1e6:
        return f"${x / 1e6:.2f}M{suffix}"
    return f"${x:,.0f}{suffix}"


def fmt_pct(x):
    return f"{x * 100:.1f}%" if x is not None else "n/a"


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("📊 SWOT Analyzer")
    st.caption("Financial risk & market restrictions, from Yahoo Finance data.")
    ticker_input = st.text_input("Ticker symbol", value="AAPL", placeholder="e.g. AAPL, MSFT, TSLA").strip().upper()
    run = st.button("Analyze", type="primary", width='stretch')
    st.markdown("---")
    st.markdown(
        "**About the data**\n\n"
        "- Pulled live from Yahoo Finance via `yfinance`. Quotes are typically "
        "delayed ~15-20 minutes, not tick-by-tick real-time.\n"
        "- Cached for 5 minutes per ticker to avoid hammering Yahoo's endpoints.\n"
        "- Regulatory/legal signal comes from a keyword scan of recent headlines "
        "plus a general sector regulatory-intensity heuristic -- **not** a legal "
        "or compliance determination.\n"
        "- This is a research/screening aid, not investment advice."
    )

if "last_ticker" not in st.session_state:
    st.session_state["last_ticker"] = None

if run and ticker_input:
    st.session_state["last_ticker"] = ticker_input

active_ticker = st.session_state["last_ticker"]

if not active_ticker:
    st.title("SWOT Analyzer")
    st.write(
        "Enter a ticker in the sidebar and click **Analyze** to generate a SWOT analysis "
        "with dedicated deep-dives on financial risk and market/regulatory restrictions."
    )
    st.stop()

with st.spinner(f"Pulling data for {active_ticker} from Yahoo Finance..."):
    try:
        company, risk, restrictions, swot = load_all(active_ticker)
    except Exception as e:
        st.error(f"Something went wrong fetching data for {active_ticker}: {e}")
        st.stop()

if company.short_name is None and company.long_name is None and not company.news and company.current_price is None:
    st.error(
        f"Couldn't find data for '{active_ticker}'. Double-check the ticker symbol "
        "(Yahoo Finance format, e.g. `BRK-B` not `BRK.B`)."
    )
    if company.errors:
        with st.expander("Technical details"):
            for e in company.errors:
                st.code(e)
    st.stop()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
name = company.long_name or company.short_name or active_ticker
st.title(f"{name} ({company.ticker})")
sub_bits = [b for b in [company.sector, company.industry, company.country] if b]
if sub_bits:
    st.caption(" · ".join(sub_bits))

hcols = st.columns(5)
hcols[0].metric("Price", f"${company.current_price:,.2f}" if company.current_price else "n/a",
                 delta=(f"{(company.current_price - company.previous_close):+.2f}"
                        if company.current_price and company.previous_close else None))
hcols[1].metric("Market Cap", fmt_money(company.market_cap))
hcols[2].metric("Overall Financial Risk", f"{risk.overall_score}/100" if risk.overall_score is not None else "n/a",
                 help="0 = lowest risk, 100 = highest risk. See the Financial Risk tab for the breakdown.")
hcols[3].metric("Regulatory Intensity", restrictions.regulatory_intensity,
                 help=restrictions.regulatory_note)
hcols[4].metric("Beta", f"{company.beta:.2f}" if company.beta is not None else "n/a")

if company.price_quote_time:
    st.caption(f"Last price bar: {company.price_quote_time} · fetched {company.fetched_at.strftime('%Y-%m-%d %H:%M:%S')} "
               "(local session time) · quotes are delayed, not real-time.")

if company.errors:
    with st.expander(f"⚠️ {len(company.errors)} data source warning(s)"):
        for e in company.errors:
            st.write(f"- {e}")

tab_overview, tab_swot, tab_risk, tab_restrictions, tab_export = st.tabs(
    ["Overview", "SWOT Summary", "Financial Risk Deep-Dive", "Market Restrictions Deep-Dive", "Export"]
)

# ---------------------------------------------------------------------------
# Overview tab
# ---------------------------------------------------------------------------
with tab_overview:
    left, right = st.columns([2, 1])
    with left:
        if company.price_history is not None and not company.price_history.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=company.price_history.index, y=company.price_history["Close"],
                mode="lines", line=dict(color=SERIES_BLUE, width=2),
                name="Close", hovertemplate="%{x|%b %d, %Y}<br>$%{y:.2f}<extra></extra>",
            ))
            fig.update_layout(
                title="1-Year Price History", font=PLOTLY_FONT, plot_bgcolor=SURFACE, paper_bgcolor=SURFACE,
                xaxis=dict(showgrid=False, linecolor=GRID), yaxis=dict(showgrid=True, gridcolor=GRID, title="Price ($)"),
                margin=dict(l=10, r=10, t=40, b=10), height=380, hovermode="x unified",
            )
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No price history available for this ticker.")

        if company.summary:
            with st.expander("Business summary"):
                st.write(company.summary)

    with right:
        st.subheader("Key stats")
        stats = {
            "Trailing P/E": f"{company.trailing_pe:.1f}" if company.trailing_pe else "n/a",
            "Forward P/E": f"{company.forward_pe:.1f}" if company.forward_pe else "n/a",
            "Price / Book": f"{company.price_to_book:.2f}" if company.price_to_book else "n/a",
            "Profit Margin": fmt_pct(company.profit_margin),
            "Revenue Growth (YoY)": fmt_pct(company.revenue_growth),
            "Dividend Yield": fmt_pct(company.dividend_yield),
            "52w Range": (f"${company.fifty_two_week_low:,.2f} - ${company.fifty_two_week_high:,.2f}"
                          if company.fifty_two_week_low and company.fifty_two_week_high else "n/a"),
            "Analyst Rating": (company.recommendation_key.replace("_", " ").title()
                                if company.recommendation_key else "n/a"),
        }
        for k, v in stats.items():
            c1, c2 = st.columns([1.4, 1])
            c1.write(k)
            c2.write(f"**{v}**")

# ---------------------------------------------------------------------------
# SWOT tab
# ---------------------------------------------------------------------------
with tab_swot:
    st.caption(
        "Strengths & Opportunities highlight favorable signals; Weaknesses & Threats are "
        "deliberately weighted toward financial risk and market/regulatory restrictions."
    )

    def render_quadrant(title: str, items, color: str):
        st.markdown(
            f"<div style='border-left:4px solid {color}; padding-left:0.75rem;'>"
            f"<h4 style='margin-bottom:0.25rem;color:{INK_PRIMARY};'>{title}</h4></div>",
            unsafe_allow_html=True,
        )
        for item in items:
            st.markdown(f"- **{item.text}**" + (f"  \n  <span style='color:{INK_SECONDARY};font-size:0.85em;'>{item.detail}</span>" if item.detail else ""),
                        unsafe_allow_html=True)
        if not items:
            st.caption("Nothing flagged here.")

    q1, q2 = st.columns(2)
    with q1:
        render_quadrant("Strengths", swot.strengths, QUADRANT_COLOR["Strengths"])
    with q2:
        render_quadrant("Weaknesses", swot.weaknesses, QUADRANT_COLOR["Weaknesses"])
    q3, q4 = st.columns(2)
    with q3:
        render_quadrant("Opportunities", swot.opportunities, QUADRANT_COLOR["Opportunities"])
    with q4:
        render_quadrant("Threats", swot.threats, QUADRANT_COLOR["Threats"])

# ---------------------------------------------------------------------------
# Financial Risk deep-dive tab
# ---------------------------------------------------------------------------
with tab_risk:
    st.subheader(f"Overall financial risk: {risk.overall_score}/100 — {risk.overall_level}"
                 if risk.overall_score is not None else "Overall financial risk: insufficient data")

    cats = [c for c, s in risk.category_scores.items() if s is not None]
    scores = [risk.category_scores[c] for c in cats]
    colors = [LEVEL_COLOR[_level_from_score(s)] for s in scores]

    if cats:
        fig2 = go.Figure(go.Bar(
            x=scores, y=cats, orientation="h", marker_color=colors,
            text=[f"{s:.0f}" for s in scores], textposition="outside",
            hovertemplate="%{y}: %{x:.0f}/100<extra></extra>",
        ))
        fig2.update_layout(
            title="Risk score by category (0 = low risk, 100 = high risk)",
            font=PLOTLY_FONT, plot_bgcolor=SURFACE, paper_bgcolor=SURFACE,
            xaxis=dict(range=[0, 105], showgrid=True, gridcolor=GRID, title="Risk score"),
            yaxis=dict(showgrid=False, autorange="reversed"),
            margin=dict(l=10, r=10, t=40, b=10), height=320, showlegend=False,
        )
        st.plotly_chart(fig2, width='stretch')
    else:
        st.info("Not enough data was available to compute category risk scores.")

    st.markdown("#### Factor-level detail")
    by_cat: dict[str, list] = {}
    for f in risk.factors:
        by_cat.setdefault(f.category, []).append(f)

    for cat, items in by_cat.items():
        st.markdown(f"**{cat}**")
        rows = []
        for f in items:
            rows.append({
                "Metric": f.name, "Value": f.value_display, "Risk Level": f.level,
                "Score": f"{f.score:.0f}" if f.score is not None else "n/a",
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, hide_index=True, width='stretch')
        for f in items:
            st.caption(f"**{f.name}** — {f.explanation}")

    if risk.data_gaps:
        st.warning("Missing from Yahoo Finance for this ticker: " + ", ".join(risk.data_gaps))

# ---------------------------------------------------------------------------
# Market Restrictions deep-dive tab
# ---------------------------------------------------------------------------
with tab_restrictions:
    st.subheader(f"Sector regulatory intensity: {restrictions.regulatory_intensity}")
    st.write(restrictions.regulatory_note)
    if restrictions.sector:
        st.caption(f"Sector: {restrictions.sector}  ·  Industry: {restrictions.industry or 'n/a'}")

    st.markdown("#### Recent news signal scan")
    if restrictions.unscanned_reason:
        st.info(restrictions.unscanned_reason)
    elif not restrictions.news_flags:
        st.success("No regulatory, legal, trade, or antitrust keywords were found in recent headlines for this ticker.")
    else:
        if restrictions.flag_counts:
            fig3 = go.Figure(go.Bar(
                x=list(restrictions.flag_counts.values()), y=list(restrictions.flag_counts.keys()),
                orientation="h", marker_color=SERIES_ORANGE,
                hovertemplate="%{y}: %{x} headline(s)<extra></extra>",
            ))
            fig3.update_layout(
                title="Flagged headlines by category", font=PLOTLY_FONT,
                plot_bgcolor=SURFACE, paper_bgcolor=SURFACE,
                xaxis=dict(showgrid=True, gridcolor=GRID, dtick=1, title="Headline count"),
                yaxis=dict(showgrid=False, autorange="reversed"),
                margin=dict(l=10, r=10, t=40, b=10), height=280, showlegend=False,
            )
            st.plotly_chart(fig3, width='stretch')

        for flag in restrictions.news_flags:
            when = ""
            if flag.published:
                try:
                    if isinstance(flag.published, (int, float)):
                        when = dt.datetime.fromtimestamp(flag.published).strftime("%Y-%m-%d")
                    else:
                        when = str(flag.published)[:10]
                except Exception:
                    when = ""
            line = f"**[{flag.category}]** {flag.title}"
            if flag.publisher or when:
                line += f"  \n<span style='color:{INK_SECONDARY};font-size:0.85em;'>{flag.publisher or ''} {when}</span>"
            if flag.link:
                st.markdown(f"{line}\n\n[Read article]({flag.link})", unsafe_allow_html=True)
            else:
                st.markdown(line, unsafe_allow_html=True)
            st.markdown("---")

    st.markdown("#### Ownership & governance")
    if restrictions.ownership_notes:
        for note in restrictions.ownership_notes:
            st.write(f"- {note}")
    else:
        st.caption("No ownership concentration notes available.")

    st.markdown("#### Analyst / market sentiment")
    if restrictions.sentiment_notes:
        for note in restrictions.sentiment_notes:
            st.write(f"- {note}")
    else:
        st.caption("No analyst sentiment data available.")

# ---------------------------------------------------------------------------
# Export tab
# ---------------------------------------------------------------------------
with tab_export:
    st.write("Download this analysis as a Markdown report.")

    def build_markdown_report() -> str:
        lines = [f"# SWOT Analysis: {name} ({company.ticker})",
                 f"_Generated {company.fetched_at.strftime('%Y-%m-%d %H:%M:%S')} · data from Yahoo Finance, delayed ~15-20 min_",
                 ""]
        lines.append(f"**Sector:** {company.sector or 'n/a'}  \n**Industry:** {company.industry or 'n/a'}  \n"
                      f"**Price:** ${company.current_price:,.2f}" if company.current_price else "**Price:** n/a")
        lines.append("")
        lines.append(f"## Overall Financial Risk: {risk.overall_score}/100 ({risk.overall_level})" if risk.overall_score is not None
                      else "## Overall Financial Risk: insufficient data")
        lines.append("")
        for quadrant, items in [("Strengths", swot.strengths), ("Weaknesses", swot.weaknesses),
                                 ("Opportunities", swot.opportunities), ("Threats", swot.threats)]:
            lines.append(f"## {quadrant}")
            for it in items:
                lines.append(f"- **{it.text}**" + (f" — {it.detail}" if it.detail else ""))
            lines.append("")
        lines.append("## Financial Risk Detail")
        for f in risk.factors:
            lines.append(f"- **{f.name}** ({f.category}): {f.value_display} — {f.level} risk. {f.explanation}")
        lines.append("")
        lines.append("## Market Restrictions Detail")
        lines.append(f"- Sector regulatory intensity: {restrictions.regulatory_intensity} — {restrictions.regulatory_note}")
        for flag in restrictions.news_flags:
            lines.append(f"- [{flag.category}] {flag.title} ({flag.publisher or 'unknown source'})")
        lines.append("")
        lines.append("---")
        lines.append("_This report is generated from automated data and heuristics. It is a research aid, "
                      "not financial or legal advice._")
        return "\n".join(lines)

    report_md = build_markdown_report()
    st.download_button(
        "Download SWOT report (.md)", data=report_md,
        file_name=f"{company.ticker}_swot_report.md", mime="text/markdown", width='stretch',
    )
    with st.expander("Preview report"):
        st.markdown(report_md)
