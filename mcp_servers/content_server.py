"""
Content Generation MCP Server
Uses Google Gemini to draft, rewrite, and optimize LinkedIn content.
Also handles Google Imagen image generation when configured.

Usage:
  python content_server.py
"""

import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv(Path.home() / ".social-agent" / ".env")
load_dotenv(Path.home() / "social-agent" / ".env", override=False)

server = FastMCP("content")

DATA_DIR = Path(os.getenv("OLE_DATA_DIR", str(Path.home() / "Desktop" / "developer worspace " / "onlineeverywhere_-ai-marketing-suite" / "social-agent")))
ASSETS_DIR = DATA_DIR / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
STITCH_API_KEY = os.getenv("STITCH_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# ── Calendar & Examples ────────────────────────────────────────────

CALENDAR_FILE = Path(__file__).parent.parent / "events_calendar.json"
EXAMPLES_FILE = Path(__file__).parent.parent / "premium_examples.json"


def _load_calendar() -> dict:
    import json
    try:
        return json.loads(CALENDAR_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"events": []}


def _load_examples() -> list[dict]:
    import json
    try:
        data = json.loads(EXAMPLES_FILE.read_text())
        return data if isinstance(data, list) else data.get("examples", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _upcoming_events(days: int = 30) -> str:
    """Find events in the next N days and format them as context."""
    from datetime import datetime, timedelta, timezone
    cal = _load_calendar()
    now = datetime.now(timezone.utc)
    window = now + timedelta(days=days)
    upcoming = []
    for ev in cal.get("events", []):
        try:
            dt = datetime.strptime(ev["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if now <= dt <= window:
                upcoming.append(ev)
        except (ValueError, KeyError):
            continue
    if not upcoming:
        return ""
    lines = ["UPCOMING EVENTS & HOLIDAYS (use these for context when relevant):"]
    for ev in upcoming:
        lines.append(f"- {ev['date']}: {ev['name']} ({ev['scope']}) — tone: {ev['tone']}")
        lines.append(f"  Hook idea: {ev.get('content_hook', '')}")
    return "\n".join(lines)


def _premium_reference_context() -> str:
    """Return premium examples as reference for quality."""
    examples = _load_examples()
    if not examples:
        return ""
    lines = ["\nPREMIUM QUALITY REFERENCES (match this tone, structure, and style):"]
    for i, ex in enumerate(examples[:3], 1):
        content = ex.get("content", "")[:500]
        lines.append(f"\nREFERENCE POST {i}:")
        lines.append(content)
        if ex.get("notes"):
            lines.append(f"Notes: {ex['notes']}")
    return "\n".join(lines)

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
    "- Informational / thought leadership (40%) — educate on digital trends, AI, Barbados market\n"
    "- Lead magnets (30%) — drive to website for free audits, assessments, guides\n"
    "- Case stories / social proof (20%) — client results, before/after\n"
    "- Engagement (10%) — polls, questions, comments\n\n"
    "Always include a lead magnet or CTA that drives traffic to onlineverywhere.com.\n"
    "Primary keyword to weave in naturally: 'Digital Marketing in Barbados'."
)


def _call_gemini(system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": 1024,
        },
    }
    r = httpx.post(f"{GEMINI_URL}?key={GOOGLE_API_KEY}", json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"No candidates returned: {data}")
    return candidates[0]["content"]["parts"][0]["text"]


@server.tool()
def draft_post(topic: str, campaign: str = "", tone: str = "informational") -> str:
    """Draft a LinkedIn post using Gemini with OLE brand voice.

    Factors in upcoming events, seasonal context, and premium quality references.

    Args:
        topic: What the post should be about (e.g. 'website speed for Barbados SMEs', 'AI agents for booking systems').
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

    event_context = _upcoming_events(14)
    premium_context = _premium_reference_context()

    user_prompt = (
        f"Draft a LinkedIn post about: {topic}\n"
        f"Content type: {tone}\n"
        f"{'Campaign context: ' + campaign_context if campaign_context else ''}\n\n"
        f"{event_context}\n\n"
        f"{premium_context}\n\n"
        "Write the full post ready to publish (max 3000 chars). "
        "Match the tone to the topic and any nearby event — use the event's suggested tone if applicable. "
        "Include a lead magnet CTA driving to onlineverywhere.com."
    )
    try:
        result = _call_gemini(OLE_SYSTEM_PROMPT, user_prompt)
        return json.dumps({"status": "drafted", "content": result, "model": GEMINI_MODEL}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "detail": str(e)})


@server.tool()
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
    try:
        result = _call_gemini(OLE_SYSTEM_PROMPT, user_prompt, temperature=0.8)
        return json.dumps({"status": "rewritten", "content": result, "style": style}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "detail": str(e)})


@server.tool()
def generate_carousel_script(topic: str, slide_count: int = 4) -> str:
    """Generate a multi-slide carousel script. Each slide is an image + caption.

    Args:
        topic: The infographic topic (e.g. '3 signs your website is leaking revenue').
        slide_count: Number of slides (3-6 recommended for LinkedIn).
    """
    user_prompt = (
        f"Create a {slide_count}-slide LinkedIn carousel about: {topic}\n\n"
        "For each slide, provide:\n"
        "SLIDE N:\n"
        "Headline: <short headline for the image>\n"
        "Body: <2-3 lines of body text>\n"
        "Image Prompt: <detailed prompt to generate this slide's image, including OLE brand colors navy #202124, blue #4285F4, green #34A853>\n\n"
        "Slide 1 should be a hook/intro. Last slide should be a CTA for onlineverywhere.com.\n"
        "The carousel should tell a complete narrative when scrolled through."
    )
    try:
        result = _call_gemini(OLE_SYSTEM_PROMPT, user_prompt, temperature=0.6)
        return json.dumps({"status": "generated", "slides": result, "slide_count": slide_count}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "detail": str(e)})


@server.tool()
def generate_imagen_image(prompt: str) -> str:
    """Generate an image using Google Imagen (requires Vertex AI access).

    Note: Imagen requires a Google Cloud project with Vertex AI enabled.
    Falls back if not configured.

    Args:
        prompt: Detailed image description.
    """
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    if not project_id or GOOGLE_API_KEY.startswith("AIza"):
        return json.dumps({
            "status": "unavailable",
            "detail": "Imagen requires a Google Cloud project with Vertex AI. "
                      "Set GOOGLE_CLOUD_PROJECT in .env or use the images MCP server (Pollinations.ai) instead.",
        })

    url = (
        f"https://us-central1-aiplatform.googleapis.com/v1/"
        f"projects/{project_id}/locations/us-central1/"
        f"publishers/google/models/imagen-3.0-generate-001:predict"
    )
    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {"sampleCount": 1, "aspectRatio": "1:1"},
    }
    try:
        r = httpx.post(f"{url}?key={GOOGLE_API_KEY}", json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        img_data = data["predictions"][0]["bytesBase64Encoded"]
        import base64
        from datetime import datetime
        img_bytes = base64.b64decode(img_data)
        out = ASSETS_DIR / f"imagen_{datetime.now():%Y%m%d_%H%M%S}.jpg"
        out.write_bytes(img_bytes)
        return json.dumps({"status": "generated", "output_path": str(out)})
    except Exception as e:
        return json.dumps({"status": "error", "detail": str(e)})


@server.tool()
def generate_batch_ideas(count: int = 5, theme: str = "digital marketing Barbados SMEs") -> str:
    """Generate a batch of content ideas for future posts.

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
    try:
        result = _call_gemini(OLE_SYSTEM_PROMPT, user_prompt, temperature=0.8)
        return json.dumps({"status": "generated", "ideas": result}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "detail": str(e)})


@server.tool()
def add_premium_example(content: str, notes: str = "", source_url: str = "") -> str:
    """Save a post as a premium quality reference for future drafts.

    The bot will reference these when generating new content to match the quality bar.

    Args:
        content: The full post text to use as a quality reference.
        notes: Optional notes on why this post is high quality (e.g. 'great hook', 'strong CTA').
        source_url: Optional URL to the original post.
    """
    import json, datetime
    examples = _load_examples()
    entry = {
        "content": content,
        "notes": notes,
        "source_url": source_url,
        "added_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    examples.append(entry)
    EXAMPLES_FILE.write_text(json.dumps(examples, indent=2))
    return json.dumps({
        "status": "saved",
        "total_examples": len(examples),
        "entry": entry,
    }, indent=2)


@server.tool()
def list_premium_examples(limit: int = 10) -> str:
    """List saved premium quality reference posts.

    Args:
        limit: Max examples to return (default 10).
    """
    import json
    examples = _load_examples()
    return json.dumps(
        [{"index": i, "preview": e["content"][:200], "notes": e.get("notes", ""), "added_at": e.get("added_at", "")}
         for i, e in enumerate(examples[-limit:])],
        indent=2, default=str
    )


@server.tool()
def delete_premium_example(index: int) -> str:
    """Delete a saved premium example by its index.

    Args:
        index: The index of the example to delete (from list_premium_examples).
    """
    import json
    examples = _load_examples()
    if 0 <= index < len(examples):
        removed = examples.pop(index)
        EXAMPLES_FILE.write_text(json.dumps(examples, indent=2))
        return json.dumps({"status": "deleted", "removed": removed.get("content", "")[:100]}, indent=2)
    return json.dumps({"status": "error", "detail": f"Index {index} out of range (0-{len(examples)-1})"})


def main():
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
