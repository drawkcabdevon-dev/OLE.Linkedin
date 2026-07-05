"""
Research MCP Server
Fetches Google Trends data, analyzes with Gemini, generates content ideas.
Tools for trending topics, keyword research, and content opportunity spotting.

Usage:
  python research_server.py

Requires:
  pip install mcp pytrends pandas
"""

import json
import os
import logging
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from gemini_client import generate_content as _gemini

load_dotenv(Path.home() / "social-agent" / ".env")
load_dotenv(Path.home() / ".social-agent" / ".env", override=False)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("research-mcp")

server = FastMCP("research")


def call_gemini(prompt: str, temperature: float = 0.5) -> str:
    """Call Vertex AI Gemini (project billing, no free-tier quota)."""
    try:
        return _gemini("You are a marketing research analyst.", prompt, temperature=temperature)
    except Exception as e:
        return f"Error: {e}"


def get_trendreq() -> object:
    """Return a TrendReq client with common params."""
    from pytrends.request import TrendReq
    tr = TrendReq(hl="en-US", tz=300)
    return tr


@server.tool()
def trending_searches(region: str = "barbados") -> str:
    """Get current trending searches from Google Trends.

    Args:
        region: Region code (e.g. 'barbados', 'united_states', 'worldwide').
    """
    try:
        tr = get_trendreq()
        if region == "worldwide":
            df = tr.trending_searches(pn="united_states")
        else:
            df = tr.trending_searches(pn=region)
        trends = df[0].tolist()[:20]
        return json.dumps({"status": "ok", "trends": trends, "region": region}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "detail": str(e)})


@server.tool()
def interest_over_time(keywords: list[str], timeframe: str = "now 7-d") -> str:
    """Interest over time for keywords.

    Args:
        keywords: List of 1-5 search terms.
        timeframe: 'now 7-d', 'now 1-d', 'today 1-m', 'today 3-m', 'today 12-m'.
    """
    try:
        tr = get_trendreq()
        tr.build_payload([k.lower() for k in keywords], cat=0, timeframe=timeframe, geo="", gprop="")
        df = tr.interest_over_time()
        if df.empty:
            return json.dumps({"status": "ok", "data": [], "note": "No data for these keywords in this timeframe"})
        result = {}
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in df.columns:
                values = df[kw_lower].tolist()
                avg = round(sum(values) / len(values), 1) if values else 0
                result[kw] = {"average_interest": avg, "peak": max(values) if values else 0, "data_points": len(values)}
        return json.dumps({"status": "ok", "data": result, "timeframe": timeframe}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "detail": str(e)})


@server.tool()
def related_queries(keyword: str, timeframe: str = "now 7-d") -> str:
    """Get related queries and rising topics for a keyword.

    Args:
        keyword: Search term to analyze.
        timeframe: 'now 7-d', 'today 1-m', 'today 3-m', 'today 12-m'.
    """
    try:
        tr = get_trendreq()
        tr.build_payload([keyword.lower()], cat=0, timeframe=timeframe, geo="", gprop="")
        related = tr.related_queries()
        if keyword.lower() not in related:
            return json.dumps({"status": "ok", "data": {"top": [], "rising": []}, "note": "No related queries"})

        rq = related[keyword.lower()]
        result = {}
        if rq["top"] is not None and not rq["top"].empty:
            result["top"] = rq["top"].head(10).to_dict("records")
        else:
            result["top"] = []
        if rq["rising"] is not None and not rq["rising"].empty:
            result["rising"] = rq["rising"].head(10).to_dict("records")
        else:
            result["rising"] = []

        return json.dumps({"status": "ok", "keyword": keyword, "data": result, "timeframe": timeframe}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "detail": str(e)})


@server.tool()
def content_opportunities(keyword: str, timeframe: str = "now 7-d") -> str:
    """Analyze keyword + related queries + Gemini for content ideas.

    Combines Google Trends data with Gemini analysis to find content
    opportunities that can capture search traffic.

    Args:
        keyword: Topic to analyze.
        timeframe: 'now 7-d', 'today 1-m', 'today 3-m', 'today 12-m'.
    """
    # Step 1: Get trends data
    tr = get_trendreq()
    tr.build_payload([keyword.lower()], cat=0, timeframe=timeframe, geo="", gprop="")
    interest = tr.interest_over_time()
    related = tr.related_queries()

    trend_summary = f"Keyword: {keyword}\nTimeframe: {timeframe}\n"
    if not interest.empty:
        vals = interest[keyword.lower()].tolist()
        trend_summary += f"Average interest: {round(sum(vals)/len(vals), 1)}\nPeak: {max(vals)}\n"

    top_queries = []
    rising_queries = []
    if keyword.lower() in related:
        rq = related[keyword.lower()]
        if rq["top"] is not None and not rq["top"].empty:
            top_queries = [r["query"] for _, r in rq["top"].head(10).iterrows()]
            trend_summary += "Top related: " + ", ".join(top_queries[:10]) + "\n"
        if rq["rising"] is not None and not rq["rising"].empty:
            rising_queries = [r["query"] for _, r in rq["rising"].head(10).iterrows()]
            trend_summary += "Rising: " + ", ".join(rising_queries[:10]) + "\n"

    # Step 2: Gemini analysis
    prompt = f"""You are a content strategist for a Barbados digital marketing agency (Online Everywhere).
Analyze this Google Trends data and generate 5 content opportunities that would capture search traffic.

{trend_summary}

For each opportunity, provide:
1. Content angle (LinkedIn post or blog title)
2. The search intent it targets
3. Why it would work for a Barbados audience

Output format (JSON array):
[{{"title": "...", "search_intent": "...", "barbados_angle": "...", "content_type": "linkedin_post|blog"}}]"""

    analysis = call_gemini(prompt, temperature=0.4)

    # Try to parse as JSON, fall back to raw text
    ideas = []
    try:
        parsed = json.loads(analysis)
        if isinstance(parsed, list):
            ideas = parsed
    except json.JSONDecodeError:
        ideas = [{"raw": analysis}]

    return json.dumps({
        "status": "ok",
        "keyword": keyword,
        "timeframe": timeframe,
        "trend_data": {
            "top_queries": top_queries[:10],
            "rising_queries": rising_queries[:10],
        },
        "content_ideas": ideas,
    }, indent=2)


@server.tool()
def analyze_topic(keyword: str) -> str:
    """Full research report: trends + queries + content opportunities in one call.

    Args:
        keyword: Topic to research.
    """
    try:
        tr = get_trendreq()
        tr.build_payload([keyword.lower()], cat=0, timeframe="now 7-d", geo="", gprop="")
        interest = tr.interest_over_time()
        related = tr.related_queries()

        avg_interest = 0
        peak = 0
        if not interest.empty:
            vals = interest[keyword.lower()].tolist()
            avg_interest = round(sum(vals) / len(vals), 1)
            peak = max(vals)

        top_q = []
        rising_q = []
        if keyword.lower() in related:
            rq = related[keyword.lower()]
            if rq["top"] is not None and not rq["top"].empty:
                top_q = [r["query"] for _, r in rq["top"].head(10).iterrows()]
            if rq["rising"] is not None and not rq["rising"].empty:
                rising_q = [{"query": r["query"], "value": r.get("value", "")} for _, r in rq["rising"].head(10).iterrows()]

        prompt = f"""You are a content strategist for Online Everywhere (Barbados digital marketing).
Google Trends data for '{keyword}':
- Interest score (0-100): {avg_interest}
- Peak: {peak}
- Top related searches: {', '.join(top_q[:10])}
- Rising: {json.dumps(rising_q[:10])}

Generate 3 high-impact LinkedIn post concepts targeting Barbados SMEs.
For each: post hook, data point to include, CTA (always drive to onlineeverywhere.com).
Be specific and quantified. No fluff."""

        analysis = call_gemini(prompt, temperature=0.5)

        return json.dumps({
            "status": "ok",
            "keyword": keyword,
            "interest_score": avg_interest,
            "peak_interest": peak,
            "top_related": top_q[:10],
            "rising_related": rising_q[:10],
            "post_ideas": analysis,
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "detail": str(e)})


@server.tool()
def daily_brief() -> str:
    """Generate a daily content brief from today's trending searches + Gemini."""
    try:
        tr = get_trendreq()
        df = tr.trending_searches(pn="united_states")
        us_trends = df[0].tolist()[:10]

        bb_df = tr.trending_searches(pn="barbados")
        bb_trends = bb_df[0].tolist()[:10]
    except Exception:
        us_trends = ["AI", "marketing", "small business"]
        bb_trends = ["Barbados business", "digital marketing Barbados"]

    prompt = f"""Today's trending searches:
US: {', '.join(us_trends)}
Barbados: {', '.join(bb_trends)}

You are a content strategist for Online Everywhere (Barbados marketing agency).
Select 2-3 trends that are relevant for Barbados SMEs and generate:
1. A LinkedIn post concept for each
2. Why a Barbados business owner would care
3. A quantified hook with a stat

Output: concise bullet points, no preamble."""

    analysis = call_gemini(prompt, temperature=0.6)

    return json.dumps({
        "status": "ok",
        "us_trends": us_trends,
        "barbados_trends": bb_trends,
        "content_brief": analysis,
    }, indent=2)


if __name__ == "__main__":
    from mcp.server.fastmcp import FastMCP
    server.run(transport="stdio")
