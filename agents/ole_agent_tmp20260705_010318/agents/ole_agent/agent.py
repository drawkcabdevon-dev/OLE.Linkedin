"""
OLE Content Agent definition.

Root agent with tools for drafting, research, trends, and chat.
Deployed to Vertex AI Agent Engine via `adk deploy agent_engine`.
"""

import json
import os
from datetime import datetime

import httpx
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

OLE_SYSTEM_PROMPT = (
    "You are the LinkedIn voice of Online Everywhere, a 'Data-Driven Marketing, Accelerated by AI' agency "
    "based in Barbados. Your AI engine is 'Ollie'. Target audience: Barbados SMEs with ghost websites, data blindness, and slow UX.\n\n"
    "VOICE RULES:\n"
    "- Confident but not arrogant. Plain English, zero jargon.\n"
    "- Lead with a quantified claim (78.7%, 0.4s, $0/mo, 4.8x ROAS, 75% credit)\n"
    "- Identify a specific pain point the audience feels daily\n"
    "- End with a clear single CTA (book audit, download guide, free assessment)\n"
    "- Short paragraphs (1-3 lines). Punchy sentences.\n"
    "- Urgency without pressure\n\n"
    "CONTENT TYPES:\n"
    "- Informational / thought leadership (40%)\n"
    "- Lead magnets (30%)\n"
    "- Case stories / social proof (20%)\n"
    "- Engagement (10%)\n\n"
    "Primary keyword: 'Digital Marketing in Barbados'."
)


def _call_gemini(system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": 1024},
    }
    r = httpx.post(f"{GEMINI_URL}?key={GOOGLE_API_KEY}", json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"No candidates returned: {data}")
    return candidates[0]["content"]["parts"][0]["text"]


# ── Content Tools ──────────────────────────────────────────────────

def draft_post(topic: str, campaign: str = "", tone: str = "informational") -> str:
    """Draft a LinkedIn post using Gemini with OLE brand voice.

    Args:
        topic: What the post should be about.
        campaign: Campaign theme — crisis_78, tax_credit, website_speed, ai_agents, brand_identity.
        tone: Content type — informational, lead_magnet, case_story, engagement.
    """
    campaign_context = {
        "crisis_78": "Hook: 78.7% of Barbados businesses only exist on social media. Angle: fear of loss, algorithm dependency.",
        "tax_credit": "Hook: Government will pay for your digital upgrade. Angle: free money, limited window, urgency.",
        "website_speed": "Hook: 0.4 second load times, $0/month. Angle: technical superiority, ownership.",
        "ai_agents": "Hook: Marketing runs 24/7 while you sleep. Angle: innovation, efficiency, competitive advantage.",
        "brand_identity": "Hook: First impressions in 0.05 seconds. Angle: professionalism, unified presence.",
    }.get(campaign, "")

    user_prompt = (
        f"Draft a LinkedIn post about: {topic}\n"
        f"Content type: {tone}\n"
        f"{'Campaign context: ' + campaign_context if campaign_context else ''}\n\n"
        "Write the full post ready to publish (max 3000 chars). Include a lead magnet CTA driving to onlineverywhere.com."
    )
    return _call_gemini(OLE_SYSTEM_PROMPT, user_prompt)


def rewrite_post(post_content: str, style: str = "more_conversational") -> str:
    """Rewrite an existing post in a different style.

    Args:
        post_content: The existing post text.
        style: Target style — more_conversational, more_urgent, shorter, longer, more_professional.
    """
    user_prompt = (
        f"Rewrite this LinkedIn post to make it {style.replace('_', ' ')}:\n\n---\n{post_content}\n---\n\n"
        "Keep the same core message and CTA. Output only the rewritten post."
    )
    return _call_gemini(OLE_SYSTEM_PROMPT, user_prompt, temperature=0.8)


def generate_batch_ideas(count: int = 5, theme: str = "digital marketing Barbados SMEs") -> str:
    """Generate a batch of content ideas.

    Args:
        count: How many ideas to generate.
        theme: Topic area to focus on.
    """
    user_prompt = (
        f"Generate {count} LinkedIn post ideas about '{theme}' for a Barbados-based AI marketing agency.\n\n"
        "For each idea:\n"
        "IDEA N:\n"
        "- Headline/Hook: <one line>\n"
        "- Campaign fit: <which campaign theme it maps to>\n"
        "- Lead magnet CTA: <what free offer drives to website>\n\n"
        "Focus on informational/educational content and lead magnets."
    )
    return _call_gemini(OLE_SYSTEM_PROMPT, user_prompt, temperature=0.8)


def generate_carousel_script(topic: str, slide_count: int = 4) -> str:
    """Generate a multi-slide carousel script.

    Args:
        topic: The infographic topic.
        slide_count: Number of slides (3-6).
    """
    user_prompt = (
        f"Create a {slide_count}-slide LinkedIn carousel about: {topic}\n\n"
        "For each slide, provide:\n"
        "SLIDE N:\n"
        "Headline: <short headline for the image>\n"
        "Body: <2-3 lines of body text>\n"
        "Image Prompt: <detailed prompt>"
        "\n\nSlide 1 should be a hook/intro. Last slide should be a CTA for onlineverywhere.com."
    )
    return _call_gemini(OLE_SYSTEM_PROMPT, user_prompt, temperature=0.6)


# ── Research Tools ─────────────────────────────────────────────────

def trending_searches(region: str = "barbados") -> str:
    """Get trending search terms from Google Trends.

    Args:
        region: Geo — barbados, united_states, etc.
    """
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="en-US", tz=300, retries=2, backoff_factor=0.5)
        trends = pytrends.trending_searches(pn=region)
        if trends.empty:
            return json.dumps({"status": "empty", "detail": "No trending data available"})
        items = trends[0].head(10).tolist()
        return json.dumps({"status": "ok", "region": region, "trends": items})
    except Exception as e:
        return json.dumps({"status": "error", "detail": str(e)})


def interest_over_time(keywords: list[str], timeframe: str = "now 7-d") -> str:
    """Get interest score over time for keywords.

    Args:
        keywords: 1-5 search terms.
        timeframe: now 7-d, now 30-d, today 5-y, etc.
    """
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="en-US", tz=300, retries=2, backoff_factor=0.5)
        pytrends.build_payload(keywords, cat=0, timeframe=timeframe, geo="", gprop="")
        data = pytrends.interest_over_time()
        if data.empty:
            return json.dumps({"status": "empty"})
        data = data.drop(columns=["isPartial"])
        latest = data.iloc[-1].to_dict()
        peak = data.max().to_dict()
        return json.dumps({"status": "ok", "latest": latest, "peak": peak})
    except Exception as e:
        return json.dumps({"status": "error", "detail": str(e)})


def related_queries(keyword: str, timeframe: str = "now 7-d") -> str:
    """Get top and rising related searches for a keyword.

    Args:
        keyword: Search term.
        timeframe: now 7-d, now 30-d, today 5-y, etc.
    """
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="en-US", tz=300, retries=2, backoff_factor=0.5)
        pytrends.build_payload([keyword], cat=0, timeframe=timeframe, geo="", gprop="")
        related = pytrends.related_queries()
        result = {}
        for key, df in related.items():
            if df is not None and "top" in key.lower() and not df[key.split("_")[1]].empty:
                result["top"] = df[key.split("_")[1]].head(10).to_dict(orient="records")
            if df is not None and "rising" in key.lower() and not df[key.split("_")[1]].empty:
                result["rising"] = df[key.split("_")[1]].head(10).to_dict(orient="records")
        return json.dumps({"status": "ok", "keyword": keyword, "related": result})
    except Exception as e:
        return json.dumps({"status": "error", "detail": str(e)})


def content_opportunities(keyword: str, timeframe: str = "now 7-d") -> str:
    """Analyze a keyword for content opportunities using trends + Gemini.

    Args:
        keyword: Search term to research.
        timeframe: now 7-d, now 30-d, today 5-y, etc.
    """
    try:
        trend_data = json.loads(related_queries(keyword, timeframe))
        user_prompt = (
            f"Analyze this keyword for content opportunities: '{keyword}'\n\n"
            f"Related search data: {json.dumps(trend_data.get('related', {}), indent=2)}\n\n"
            "Provide:\n"
            "1. What this trend means for Barbados SMEs\n"
            "2. 3 content angles we can use\n"
            "3. Suggested headlines\n"
            "4. Which OLE campaign fits best\n"
        )
        analysis = _call_gemini(OLE_SYSTEM_PROMPT, user_prompt, temperature=0.7)
        return json.dumps({"status": "ok", "keyword": keyword, "analysis": analysis})
    except Exception as e:
        return json.dumps({"status": "error", "detail": str(e)})


def analyze_topic(keyword: str) -> str:
    """Full research report on a topic: trends + Gemini analysis + post ideas.

    Args:
        keyword: Topic to research.
    """
    try:
        trend_info = json.loads(interest_over_time([keyword], "now 30-d"))
        query_info = json.loads(related_queries(keyword, "now 30-d"))
        user_prompt = (
            f"Research topic: '{keyword}'\n\n"
            f"Trend data: {json.dumps(trend_info, indent=2)}\n"
            f"Related queries: {json.dumps(query_info, indent=2)}\n\n"
            "Provide:\n"
            "1. What this topic means for Barbados businesses\n"
            "2. Content strategy: 3 LinkedIn post ideas\n"
            "3. Suggested hooks and CTAs\n"
            "4. Related keywords to target\n"
        )
        analysis = _call_gemini(OLE_SYSTEM_PROMPT, user_prompt, temperature=0.7)
        return json.dumps({"status": "ok", "keyword": keyword, "analysis": analysis})
    except Exception as e:
        return json.dumps({"status": "error", "detail": str(e)})


def daily_brief() -> str:
    """Today's trending searches + content brief with ideas."""
    try:
        us_data = json.loads(trending_searches("united_states"))
        bb_data = json.loads(trending_searches("barbados"))
        us_trends = us_data.get("trends", [])
        bb_trends = bb_data.get("trends", [])
        us_text = "\n".join(f"- {t}" for t in us_trends[:5]) if us_trends else "No US trends"
        bb_text = "\n".join(f"- {t}" for t in bb_trends[:5]) if bb_trends else "No Barbados trends"
        user_prompt = (
            f"Today's trending topics:\n\nUS:\n{us_text}\n\nBarbados:\n{bb_text}\n\n"
            "Create a daily content brief with:\n"
            "1. The most relevant trend for SME marketing\n"
            "2. A LinkedIn post hook based on the trend\n"
            "3. Suggested CTA\n"
        )
        brief = _call_gemini(OLE_SYSTEM_PROMPT, user_prompt, temperature=0.7)
        return json.dumps({
            "status": "ok",
            "us_trends": us_trends,
            "barbados_trends": bb_trends,
            "content_brief": brief,
        })
    except Exception as e:
        return json.dumps({"status": "error", "detail": str(e)})


def chat_reply(user_message: str) -> str:
    """Respond to a free-form chat message as the OLE assistant.

    Args:
        user_message: The user's chat text.
    """
    system = OLE_SYSTEM_PROMPT + (
        "\n\nYou are also a helpful assistant for the Online Everywhere team. "
        "Answer questions about the business, suggest content ideas, "
        "and be conversational. Keep responses concise and friendly."
    )
    user_prompt = f"User: {user_message}\n\nResponse:"
    return _call_gemini(system, user_prompt, temperature=0.7)


# ── Root Agent ─────────────────────────────────────────────────────

agent = LlmAgent(
    name="ole_content_agent",
    model="gemini-2.5-flash",
    instruction=OLE_SYSTEM_PROMPT,
    tools=[
        FunctionTool(draft_post),
        FunctionTool(rewrite_post),
        FunctionTool(generate_batch_ideas),
        FunctionTool(generate_carousel_script),
        FunctionTool(trending_searches),
        FunctionTool(interest_over_time),
        FunctionTool(related_queries),
        FunctionTool(content_opportunities),
        FunctionTool(analyze_topic),
        FunctionTool(daily_brief),
        FunctionTool(chat_reply),
    ],
)
