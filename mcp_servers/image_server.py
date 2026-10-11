"""
Image Generation MCP Server
Generates social media graphics using:
  1. Gemini 3.1 Flash Image (highest quality, ~$0.067/image) — default
  2. Google Stitch (if STITCH_API_KEY is set) — UI design generation
  3. Pollinations.ai (free, no key required) — fallback

Usage:
  python image_server.py
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv
import httpx
from mcp.server.fastmcp import FastMCP

load_dotenv(Path.home() / "social-agent" / ".env")
load_dotenv(Path.home() / ".social-agent" / ".env", override=False)

server = FastMCP("images")

DATA_DIR = Path(os.getenv("OLE_DATA_DIR", str(Path(__file__).parent.parent)))
ASSETS_DIR = DATA_DIR / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR = DATA_DIR

STITCH_API_KEY = os.getenv("STITCH_API_KEY", "")
STITCH_PROJECT_ID = os.getenv("STITCH_PROJECT_ID", "")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"

BRAND_COLORS = {
    "primary": "#4285F4",
    "red": "#EA4335",
    "green": "#34A853",
    "yellow": "#FBBC05",
    "navy": "#202124",
}

CAMPAIGN_VISUALS = {
    "crisis_78": {
        "subject": "business owner looking at phone with worried expression, social media graphs declining",
        "mood": "urgent, dramatic, wake-up call",
        "style": "cinematic photography",
    },
    "tax_credit": {
        "subject": "Barbados government building with digital transformation elements floating, tax documents with checkmarks",
        "mood": "optimistic, opportunity, professional",
        "style": "corporate photography with infographic overlays",
    },
    "website_speed": {
        "subject": "abstract speed visualization with light trails, loading bars comparing speeds",
        "mood": "fast, clean, confident",
        "style": "motion design style, geometric",
    },
    "ai_agents": {
        "subject": "futuristic AI network nodes connected by glowing blue lines, robot handshake with human",
        "mood": "innovative, futuristic, efficient",
        "style": "tech illustration, neon accents",
    },
    "brand_identity": {
        "subject": "professional brand style guide spread showing logos, colors, typography, business cards",
        "mood": "polished, professional, premium",
        "style": "flat lay photography, clean",
    },
}

# Topic-to-visual mapping for dynamic prompt generation
TOPIC_VISUAL_KEYWORDS = {
    "website": ["website mockup on laptop screen", "loading speed gauge", "mobile responsive design", "web analytics dashboard"],
    "speed": ["light trails", "speedometer", "fast motion blur", "loading bar completion"],
    "loading": ["progress bar", "clock ticking", "lightning bolt", "instant display"],
    "ai": ["neural network visualization", "robot and human collaboration", "futuristic interface", "data streams flowing"],
    "agent": ["digital assistant", "automation workflow", "24/7 operation", "chat interface"],
    "chatbot": ["conversation bubbles", "customer service interface", "message notifications", "automated replies"],
    "social media": ["phone with social feeds", "engagement metrics", "content calendar", "influencer aesthetic"],
    "marketing": ["growth charts", "funnel visualization", "target audience", "conversion arrows"],
    "data": ["analytics dashboard", "data visualization", "charts and graphs", "insights discovery"],
    "brand": ["logo design process", "color palette", "brand guidelines", "visual identity"],
    "barbados": ["tropical business setting", "caribbean office", "island skyline", "local business storefront"],
    "tax": ["government documents", "financial savings", "tax forms with checkmarks", "filing system"],
    "credit": ["money saving", "financial growth", "investment return", "budget allocation"],
    "website speed": ["browser loading animation", "server rack", "CDN network", "optimization process"],
    "digital transformation": ["modern office technology", "cloud computing", "digital workflow", "innovation"],
    "online presence": ["search results", "google business profile", "online directory", "digital footprint"],
    "lead generation": ["funnel visualization", "contact form", "landing page", "conversion funnel"],
    "content": ["content calendar", "blog writing", "video production", "social scheduling"],
    "analytics": ["dashboard with charts", "KPI metrics", "performance graphs", "data insights"],
    "automation": ["workflow diagram", "robotic process", "scheduled tasks", "system integration"],
    "SEO": ["search engine results", "keyword research", "google ranking", "organic traffic"],
    "advertising": ["ad campaign setup", "budget allocation", "impression metrics", "targeting"],
    "email": ["inbox notifications", "email template", "newsletter design", "open rate metrics"],
    "video": ["video production", "camera equipment", "editing timeline", "thumbnail design"],
    "mobile": ["smartphone app", "responsive design", "mobile optimization", "touch interface"],
    "cloud": ["cloud servers", "data center", "cloud storage", "SaaS application"],
    "security": ["shield protection", "lock icon", "encrypted data", "firewall"],
    "ecommerce": ["online store", "shopping cart", "product listing", "checkout process"],
    "customer": ["customer journey", "satisfaction survey", "feedback loop", "retention metrics"],
    "growth": ["upward trend", "exponential curve", "market expansion", "revenue increase"],
    "ROI": ["return on investment", "profit margin", "financial growth", "success metrics"],
    "audit": ["website analysis", "performance report", "technical review", "optimization checklist"],
    "assessment": ["evaluation form", "scoring system", "improvement areas", "action plan"],
}


def _generate_topic_visual(topic: str) -> dict:
    """Generate a dynamic visual description based on the post topic.
    
    Returns dict with subject, mood, style tailored to the topic.
    """
    topic_lower = topic.lower()
    
    # Find matching visual keywords
    matched_keywords = []
    for keyword, visuals in TOPIC_VISUAL_KEYWORDS.items():
        if keyword in topic_lower:
            matched_keywords.extend(visuals)
    
    # If no specific match, use generic business/tech visuals
    if not matched_keywords:
        matched_keywords = [
            "modern business professionals collaborating",
            "digital technology interface",
            "growth and innovation concept",
            "professional workspace with screens"
        ]
    
    # Pick 2-3 most relevant visuals (avoid too many)
    import random
    selected_visuals = random.sample(matched_keywords[:6], min(3, len(matched_keywords)))
    
    # Determine mood based on topic sentiment
    if any(w in topic_lower for w in ["crisis", "problem", "losing", "failing", "stuck"]):
        mood = "urgent, attention-grabbing, call to action"
    elif any(w in topic_lower for w in ["growth", "success", "increase", "improve", "boost"]):
        mood = "optimistic, upward trajectory, success-oriented"
    elif any(w in topic_lower for w in ["ai", "automation", "future", "innovative"]):
        mood = "futuristic, innovative, cutting-edge"
    elif any(w in topic_lower for w in ["barbados", "local", "island", "caribbean"]):
        mood = "tropical professional, local business pride, community"
    else:
        mood = "professional, confident, authoritative"
    
    # Determine style
    if any(w in topic_lower for w in ["ai", "tech", "digital", "automation", "cloud"]):
        style = "modern tech illustration with clean lines"
    elif any(w in topic_lower for w in ["data", "analytics", "metrics", "roi"]):
        style = "data visualization style with infographic elements"
    elif any(w in topic_lower for w in ["brand", "design", "creative", "content"]):
        style = "creative agency aesthetic with bold typography"
    else:
        style = "professional corporate photography with modern elements"
    
    return {
        "subject": ", ".join(selected_visuals),
        "mood": mood,
        "style": style,
    }


def _social_prompt(campaign_id: str, post_text: str) -> str:
    """Generate a topic-relevant image prompt.
    
    If post_text is provided, generates dynamic visuals based on the topic.
    Falls back to campaign-specific visuals if available.
    """
    # If we have post content, generate dynamic topic-relevant visuals
    if post_text and len(post_text) > 20:
        visual = _generate_topic_visual(post_text)
    elif campaign_id and campaign_id in CAMPAIGN_VISUALS:
        visual = CAMPAIGN_VISUALS[campaign_id]
    else:
        visual = CAMPAIGN_VISUALS["brand_identity"]
    
    return (
        f"Professional LinkedIn social media post graphic.\n"
        f"Style: {visual['style']}.\n"
        f"Visual elements: {visual['subject']}.\n"
        f"Mood: {visual['mood']}.\n"
        f"Color palette: Dark navy background (#202124), with accent colors bright blue (#4285F4), green (#34A853), red (#EA4335).\n"
        f"Layout: Clean, modern design with the visual elements as the focal point. "
        f"Leave space on left side for text overlay (headline area).\n"
        f"Requirements:\n"
        f"- Must look like a premium social media graphic, NOT a website screenshot\n"
        f"- NO UI elements, buttons, or app interfaces\n"
        f"- NO text or words in the image (text goes in post, not image)\n"
        f"- Professional lighting, 8k quality, highly detailed\n"
        f"- Suitable for LinkedIn professional audience\n"
        f"- The image should visually represent the topic, not just show a generic brand"
    )


def _detect_campaign(post_content: str) -> str:
    """Map post text to a campaign id."""
    post_lower = (post_content or "").lower()
    if "78.7" in post_lower or "crisis" in post_lower:
        return "crisis_78"
    if "tax" in post_lower or "credit" in post_lower or "government" in post_lower:
        return "tax_credit"
    if "speed" in post_lower or "0.4" in post_lower or "second" in post_lower or "load" in post_lower:
        return "website_speed"
    if "ai" in post_lower or "agent" in post_lower or "24/7" in post_lower or "ollie" in post_lower:
        return "ai_agents"
    if "brand" in post_lower or "identity" in post_lower or "first impression" in post_lower:
        return "brand_identity"
    return "brand_identity"


IMAGE_PROMPT_SYSTEM = """You are the art director for Online Everywhere (OLE), a data-driven AI marketing agency in Barbados serving SMEs.

Given a LinkedIn post, produce ONE image-generation prompt.

Think silently first:
1. What is this post's core message — the single idea a reader walks away with?
2. What concrete visual literally embodies THAT idea (a scene, object, or metaphor someone could shoot or render)? It must be specific to this post's argument, not a generic marketing graphic.

Rules for the prompt you return:
- Describe: subject/scene, setting, lighting, composition, style, color.
- Base palette: deep navy background (#202124); accents bright blue (#4285F4), green (#34A853), red (#EA4335), used sparingly.
- Composition: main subject centered or right of center; keep the left third quiet (dark negative space) for a headline overlay.
- NO text, letters, numbers, words, logos, watermarks, UI screenshots, dashboards, or website mockups in the image. If the scene contains a sign, banner, screen, or label, describe it as blank — no lettering of any kind may appear.
- Style: premium modern 3D illustration or cinematic photography — editorial quality, not clip art, not a template.
- Match mood to the post's argument: urgent posts feel tense, opportunity posts feel bright.
- Avoid cliches unless the post is literally about them: puzzle pieces, handshakes over skylines, rockets launching off charts, glowing brains.

Return ONLY the final image prompt — one paragraph, 80-120 words. No preamble."""


def _intent_image_prompt(post_content: str, campaign_id: str = "") -> str | None:
    """Use Gemini text to author an image prompt matched to the post's intent.

    Returns None on any failure so callers can fall back to heuristics.
    """
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from gemini_client import generate_content
        user = f"Campaign: {campaign_id or 'auto'}\n\nPost:\n{(post_content or '')[:1500]}"
        prompt = generate_content(
            IMAGE_PROMPT_SYSTEM, user, temperature=0.8, max_tokens=2048
        )
        prompt = (prompt or "").strip().strip('"').strip()
        return prompt or None
    except Exception as e:
        import logging
        logging.getLogger("image_server").warning(f"Intent prompt authoring failed: {e}")
        return None


def build_image_prompt(post_content: str, campaign_id: str = "") -> str:
    """Build an image prompt that matches the post's intent.

    Primary: Gemini authors a purpose-built prompt from the post's core message.
    Fallback: keyword/campaign heuristics (_social_prompt).
    """
    if not campaign_id:
        campaign_id = _detect_campaign(post_content)
    return _intent_image_prompt(post_content, campaign_id) or _social_prompt(
        campaign_id, post_content
    )


def _save_image(image_data: bytes, filename: str) -> Path:
    out = ASSETS_DIR / filename
    out.write_bytes(image_data)
    return out


def _save_to_db(tool: str, campaign_id: str, prompt: str, image_path: str, post_content: str):
    import sqlite3
    conn = sqlite3.connect(str(DB_DIR / "data.db"))
    conn.execute("""CREATE TABLE IF NOT EXISTS design_assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id TEXT,
        tool TEXT,
        post_content TEXT,
        script_content TEXT,
        output_path TEXT,
        status TEXT DEFAULT 'generated',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute(
        "INSERT INTO design_assets (campaign_id, tool, post_content, script_content, output_path, status) VALUES (?, ?, ?, ?, ?, ?)",
        (campaign_id, tool, post_content, json.dumps({"prompt": prompt}), image_path, "generated"),
    )
    conn.commit()
    conn.close()


def _call_gemini_image(prompt: str, aspect_ratio: str = "1:1") -> bytes | None:
    """Call Gemini 3.1 Flash Image to generate an image. Returns PNG bytes or None."""
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from gemini_client import generate_image
        return generate_image(prompt, aspect_ratio=aspect_ratio)
    except Exception as e:
        import logging
        logging.getLogger("image_server").warning(f"Gemini image error: {e}")
        return None


def _call_stitch_api(prompt: str) -> bytes | None:
    """Call Google Stitch API to generate a design and return its screenshot."""
    stitch_key = STITCH_API_KEY or os.getenv("STITCH_API_KEY", "")
    if not stitch_key:
        return None

    project_id = STITCH_PROJECT_ID or os.getenv("STITCH_PROJECT_ID", "")
    if not project_id:
        return None

    try:
        import subprocess, tempfile, base64, json

        # 1. Generate screen from prompt
        gen_cmd = [
            "npx", "-y", "@_davideast/stitch-mcp", "tool", "generate_screen_from_text",
            "-d", json.dumps({"projectId": project_id, "prompt": prompt, "n": 1})
        ]
        gen_result = subprocess.run(gen_cmd, capture_output=True, text=True, timeout=120)
        gen_data = json.loads(gen_result.stdout)
        screens = gen_data.get("screens", [])
        if not screens:
            return None
        screen_id = screens[0].get("id", "")

        # 2. Get screenshot
        img_cmd = [
            "npx", "-y", "@_davideast/stitch-mcp", "tool", "get_screen_image",
            "-d", json.dumps({"projectId": project_id, "screenId": screen_id})
        ]
        img_result = subprocess.run(img_cmd, capture_output=True, text=True, timeout=60)
        img_data = json.loads(img_result.stdout)
        b64 = img_data.get("screenshotBase64", "")
        if not b64:
            return None
        return base64.b64decode(b64)

    except Exception as e:
        import logging
        logging.getLogger("image_server").warning(f"Stitch API error: {e}")
        return None


def _call_nvidia_image(prompt: str, width: int = 1024, height: int = 1024, model: str = "flux.1-schnell") -> bytes | None:
    """Call NVIDIA NIM image generation API. Returns raw image bytes or None."""
    api_key = NVIDIA_API_KEY or os.getenv("NVIDIA_API_KEY", "")
    if not api_key:
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": f"{width}x{height}",
        "response_format": "b64_json",
    }

    try:
        r = httpx.post(
            f"{NVIDIA_BASE_URL}/images/generations",
            json=payload,
            headers=headers,
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()
        images = data.get("data", [])
        if not images:
            return None
        import base64
        return base64.b64decode(images[0].get("b64_json", ""))
    except Exception as e:
        import logging
        logging.getLogger("image_server").warning(f"NVIDIA image API error: {e}")
        return None


@server.tool()
def nvidia_generate_image(prompt: str, width: int = 1024, height: int = 1024, model: str = "flux.1-schnell") -> str:
    """Generate an image using NVIDIA NIM (high quality, OpenAI-compatible).

    Requires NVIDIA_API_KEY in .env.

    Args:
        prompt: Description of the image to generate.
        width: Image width (default 1024).
        height: Image height (default 1024).
        model: NVIDIA model — 'flux.1-schnell' (fast, free tier),
               'flux.1-dev' (high quality), 'stable-diffusion-3.5-large'.
    """
    api_key = NVIDIA_API_KEY or os.getenv("NVIDIA_API_KEY", "")
    if not api_key:
        return json.dumps({"status": "error", "detail": "NVIDIA_API_KEY not set in .env"})

    image_data = _call_nvidia_image(prompt, width, height, model)
    if image_data is None:
        return json.dumps({"status": "error", "detail": "NVIDIA API returned no image"})

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"nvidia_{ts}.png"
    out_path = _save_image(image_data, filename)

    result = {
        "status": "generated",
        "output_path": str(out_path),
        "size_bytes": len(image_data),
        "width": width,
        "height": height,
        "provider": "nvidia",
        "model": model,
    }
    _save_to_db("nvidia", "custom", prompt, str(out_path), prompt)
    # Log cost (NVIDIA free tier = $0)
    try:
        from cost_tracker import log_api_call
        log_api_call("nvidia", model, 0, 0, "images/generations")
    except Exception:
        pass
    return json.dumps(result, indent=2)


@server.tool()
def stitch_generate_image(prompt: str, width: int = 1200, height: int = 1200) -> str:
    """Generate an image using Google Stitch (replaces Pollinations).
    
    Requires STITCH_API_KEY and STITCH_PROJECT_ID in .env.
    Stitch is a UI design generator — creates app/website screen designs
    from text prompts, returned as screenshot images.
    
    Args:
        prompt: Description of the design to generate.
        width: Image width (default 1200).
        height: Image height (default 1200).
    """
    stitch_key = STITCH_API_KEY or os.getenv("STITCH_API_KEY", "")
    if not stitch_key:
        return json.dumps({"status": "error", "detail": "STITCH_API_KEY not set in .env"})

    project_id = STITCH_PROJECT_ID or os.getenv("STITCH_PROJECT_ID", "")
    if not project_id:
        return json.dumps({"status": "error", "detail": "STITCH_PROJECT_ID not set in .env"})

    try:
        image_data = _call_stitch_api(prompt)
        if image_data is None:
            return json.dumps({"status": "error", "detail": "Stitch API returned no image"})

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"stitch_{ts}.png"
        out_path = _save_image(image_data, filename)

        result = {
            "status": "generated",
            "output_path": str(out_path),
            "size_bytes": len(image_data),
            "width": width,
            "height": height,
            "provider": "stitch",
        }
        _save_to_db("stitch", "custom", prompt, str(out_path), prompt)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "detail": str(e)})


@server.tool()
def stitch_list_projects() -> str:
    """List all accessible Stitch projects."""
    import subprocess, json
    try:
        r = subprocess.run(
            ["npx", "-y", "@_davideast/stitch-mcp", "tool", "list_projects"],
            capture_output=True, text=True, timeout=30
        )
        return r.stdout
    except Exception as e:
        return json.dumps({"status": "error", "detail": str(e)})


@server.tool()
def generate_image(prompt: str, width: int = 1200, height: int = 1200, model: str = "flux") -> str:
    """Generate an image directly from a text prompt using Pollinations.ai (free fallback).

    Prefer generate_social_graphic() — it uses Gemini 3.1 Flash Image first
    (on-brand, higher quality) and only falls back to Stitch/Pollinations.

    Args:
        prompt: Detailed description of the image to generate.
        width: Image width (default 1200).
        height: Image height (default 1200 for square).
        model: Model to use — 'flux' (default, best quality) or 'turbo'.
    """
    encoded = quote(prompt)
    url = f"{POLLINATIONS_BASE}/{encoded}?width={width}&height={height}&model={model}&nologo=true&seed={int(time.time())}"

    try:
        r = httpx.get(url, timeout=60, follow_redirects=True)
        r.raise_for_status()

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"social_{ts}.jpg"
        out_path = _save_image(r.content, filename)

        result = {
            "status": "generated",
            "output_path": str(out_path),
            "size_bytes": len(r.content),
            "width": width,
            "height": height,
            "model": model,
            "provider": "pollinations",
        }
        _save_to_db("pollinations", "custom", prompt, str(out_path), prompt)
        return json.dumps(result, indent=2)
    except httpx.HTTPStatusError as e:
        return json.dumps({"status": "error", "detail": f"API error: {e.response.status_code} - {e.response.text}"})
    except Exception as e:
        return json.dumps({"status": "error", "detail": str(e)})


@server.tool()
def generate_social_graphic(post_content: str, campaign_id: str = "", width: int = 1200, height: int = 1200) -> str:
    """Generate a social media graphic tailored to a post and campaign.

    The image prompt is authored from the post's core message (Gemini text),
    so the visual matches the post's intent — not a generic brand template.
    Primary render: Gemini 3.1 Flash Image (branded, ~$0.067/image).
    Falls back to Stitch, then Pollinations (free).

    Args:
        post_content: The LinkedIn post text (used for auto-detecting campaign + context).
        campaign_id: Override campaign (crisis_78, tax_credit, website_speed, ai_agents, brand_identity).
        width: Image width (default 1200).
        height: Image height (default 1200).
    """
    if not campaign_id:
        campaign_id = _detect_campaign(post_content)

    prompt = build_image_prompt(post_content, campaign_id)

    # 1. Try Gemini 3.1 Flash Image (highest quality, ~$0.067/image)
    image_data = _call_gemini_image(prompt, aspect_ratio="1:1")
    if image_data:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"social_gemini_{ts}.png"
        out_path = _save_image(image_data, filename)
        result = {
            "status": "generated",
            "output_path": str(out_path),
            "size_bytes": len(image_data),
            "width": width,
            "height": height,
            "provider": "gemini-3.1-flash-image",
            "campaign_id": campaign_id,
        }
        _save_to_db("gemini", campaign_id, prompt, str(out_path), post_content)
        return json.dumps(result, indent=2)

    # 2. Try Stitch (if configured)
    stitch_key = STITCH_API_KEY or os.getenv("STITCH_API_KEY", "")
    stitch_project = STITCH_PROJECT_ID or os.getenv("STITCH_PROJECT_ID", "")
    if stitch_key and stitch_project:
        image_data = _call_stitch_api(prompt)
        if image_data:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"social_stitch_{ts}.png"
            out_path = _save_image(image_data, filename)
            result = {
                "status": "generated",
                "output_path": str(out_path),
                "size_bytes": len(image_data),
                "width": width,
                "height": height,
                "provider": "stitch",
                "campaign_id": campaign_id,
            }
            _save_to_db("stitch", campaign_id, prompt, str(out_path), post_content)
            return json.dumps(result, indent=2)

    # 3. Fallback to Pollinations (free, always works)
    return generate_image(prompt, width, height, model="flux")


@server.tool()
def generate_carousel_images(prompts: list[str], model: str = "flux") -> str:
    """Generate multiple images for a LinkedIn carousel post.

    Each prompt produces one image slide. Use with content_server's
    generate_carousel_script() to get the prompts, then feed them here.

    Args:
        prompts: List of image prompts, one per carousel slide.
        model: 'flux' (default) or 'turbo'.
    """
    slides = []
    for i, prompt in enumerate(prompts):
        encoded = quote(prompt)
        url = f"{POLLINATIONS_BASE}/{encoded}?width=1080&height=1080&model={model}&nologo=true&seed={int(time.time())}"

        try:
            r = httpx.get(url, timeout=60, follow_redirects=True)
            r.raise_for_status()

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"carousel_{ts}_slide{i+1}.jpg"
            out_path = _save_image(r.content, filename)

            slides.append({
                "slide": i + 1,
                "output_path": str(out_path),
                "size_bytes": len(r.content),
            })
        except Exception as e:
            slides.append({"slide": i + 1, "error": str(e)})

    result = {
        "status": "generated",
        "slide_count": len(prompts),
        "slides": slides,
    }
    _save_to_db("pollinations", "carousel", json.dumps(prompts), json.dumps(result), str(result))
    return json.dumps(result, indent=2)


@server.tool()
def list_generated_images(limit: int = 20) -> str:
    """List recently generated images.
    
    Args:
        limit: Max results (default 20).
    """
    import sqlite3
    conn = sqlite3.connect(str(DB_DIR / "data.db"))
    rows = conn.execute(
        "SELECT * FROM design_assets WHERE tool = 'pollinations' ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return json.dumps([dict(r) for r in rows], indent=2, default=str)


def main():
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
