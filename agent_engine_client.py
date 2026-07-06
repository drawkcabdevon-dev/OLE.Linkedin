"""
Agent Engine client — calls the deployed ADK agent from the Telegram bot.
Uses Vertex AI REST API directly (avoid SDK version mismatches).
"""

import json
import os
import subprocess
import logging

import httpx

logger = logging.getLogger("agent_engine_client")

ENGINE_RESOURCE = os.getenv(
    "AGENT_ENGINE_RESOURCE",
    "",
)

LOCATION = "us-central1"


def _get_token() -> str | None:
    """Get an access token from gcloud or ADC."""
    try:
        result = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:
        logger.warning(f"Failed to get access token: {e}")
    return None


def _query(input_text: str) -> dict | None:
    """Send a query to the Agent Engine via REST API."""
    if not ENGINE_RESOURCE:
        logger.warning("AGENT_ENGINE_RESOURCE not set")
        return None

    token = _get_token()
    if not token:
        logger.warning("No access token available")
        return None

    url = f"https://{LOCATION}-aiplatform.googleapis.com/v1/{ENGINE_RESOURCE}:query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = {
        "input": {
            "messages": [
                {"role": "user", "content": input_text},
            ]
        }
    }

    try:
        r = httpx.post(url, json=body, headers=headers, timeout=60)
        r.raise_for_status()
        data = r.json()
        return data
    except httpx.HTTPStatusError as e:
        logger.warning(f"Agent Engine HTTP {e.response.status_code}: {e.response.text[:500]}")
        return None
    except Exception as e:
        logger.warning(f"Agent Engine error: {e}")
        return None


def _extract_content(response: dict | None) -> str | None:
    """Extract text content from an Agent Engine response."""
    if response is None:
        return None
    candidates = response.get("candidates", [])
    if not candidates:
        return None
    parts = candidates[0].get("content", {}).get("parts", [])
    texts = [p.get("text", "") for p in parts if p.get("text")]
    return " ".join(texts) if texts else None


def draft_post(topic: str, campaign: str = "", tone: str = "informational") -> dict:
    prompt = f"Draft a LinkedIn post about: {topic}. Campaign: {campaign}. Tone: {tone}."
    resp = _query(prompt)
    content = _extract_content(resp)
    if content:
        return {"status": "drafted", "content": content, "model": "gemini-2.5-flash"}
    return {"status": "unavailable", "detail": "Agent Engine returned no content"}


def generate_batch_ideas(count: int = 5, theme: str = "digital marketing Barbados SMEs") -> dict:
    resp = _query(f"Generate {count} LinkedIn post ideas about '{theme}'.")
    content = _extract_content(resp)
    if content:
        return {"status": "generated", "ideas": content}
    return {"status": "unavailable", "detail": "Agent Engine returned no content"}


def rewrite_post(post_content: str, style: str = "more_conversational") -> dict:
    resp = _query(f"Rewrite this post to be {style.replace('_', ' ')}:\n\n{post_content}")
    content = _extract_content(resp)
    if content:
        return {"status": "rewritten", "content": content, "style": style}
    return {"status": "unavailable", "detail": "Agent Engine returned no content"}


def trending_searches(region: str = "barbados") -> dict:
    resp = _query(f"Get trending searches for {region}.")
    content = _extract_content(resp)
    if content:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"status": "ok", "trends": content.split("\n")}
    return {"status": "unavailable", "detail": "Agent Engine returned no content"}


def daily_brief() -> dict:
    resp = _query("Generate today's daily content brief with trends.")
    content = _extract_content(resp)
    if content:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"status": "ok", "content_brief": content}
    return {"status": "unavailable", "detail": "Agent Engine returned no content"}


def chat_reply(user_message: str) -> str | None:
    resp = _query(user_message)
    return _extract_content(resp)


def analyze_topic(keyword: str) -> dict:
    resp = _query(f"Research topic: {keyword}. Provide full analysis with content ideas.")
    content = _extract_content(resp)
    if content:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"status": "ok", "analysis": content}
    return {"status": "unavailable", "detail": "Agent Engine returned no content"}


def content_opportunities(keyword: str) -> dict:
    resp = _query(f"Find content opportunities for keyword: {keyword}.")
    content = _extract_content(resp)
    if content:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {"status": "ok", "analysis": content}
    return {"status": "unavailable", "detail": "Agent Engine returned no content"}


def mirror_competitor(topic: str, angle: str = "") -> dict:
    prompt = f"Create a counter-position post about '{topic}'"
    if angle:
        prompt += f" with angle: {angle}"
    resp = _query(prompt)
    content = _extract_content(resp)
    if content:
        return {"status": "drafted", "content": content}
    return {"status": "unavailable", "detail": "Agent Engine returned no content"}
