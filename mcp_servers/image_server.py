"""
Image Generation MCP Server
Generates social media graphics using Pollinations.ai (free, no key)
or Google Stitch (if STITCH_API_KEY is set).

Usage:
  python image_server.py

Free provider: Pollinations.ai — no API key required
Premium: Google Stitch — set STITCH_API_KEY in .env
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

DATA_DIR = Path(os.getenv("OLE_DATA_DIR", str(Path.home() / "Desktop" / "developer worspace " / "onlineeverywhere_-ai-marketing-suite" / "social-agent")))
ASSETS_DIR = DATA_DIR / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR = DATA_DIR

STITCH_API_KEY = os.getenv("STITCH_API_KEY", "")
STITCH_PROJECT_ID = os.getenv("STITCH_PROJECT_ID", "")

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


def _social_prompt(campaign_id: str, post_text: str) -> str:
    visual = CAMPAIGN_VISUALS.get(campaign_id, CAMPAIGN_VISUALS["brand_identity"])
    return (
        f"Professional LinkedIn social media post graphic. "
        f"{visual['style']} style. "
        f"Subject: {visual['subject']}. "
        f"Mood: {visual['mood']}. "
        f"Color palette: dark navy blue background, bright blue (#4285F4), green (#34A853), red (#EA4335) accents. "
        f"Modern, clean, high-end marketing agency aesthetic. "
        f"Text overlay area on left/center with space for headline. "
        f"Do NOT make it look like a website UI or app interface. "
        f"It should look like a professional social media graphic created by a design agency. "
        f"8k resolution, highly detailed, professional lighting."
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
    """Generate a social media graphic from a text prompt using Pollinations.ai.
    
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
    
    Args:
        post_content: The LinkedIn post text (used for auto-detecting campaign + context).
        campaign_id: Override campaign (crisis_78, tax_credit, website_speed, ai_agents, brand_identity).
        width: Image width (default 1200).
        height: Image height (default 1200).
    """
    if not campaign_id:
        post_lower = post_content.lower()
        if "78.7" in post_lower or "crisis" in post_lower:
            campaign_id = "crisis_78"
        elif "tax" in post_lower or "credit" in post_lower or "government" in post_lower:
            campaign_id = "tax_credit"
        elif "speed" in post_lower or "0.4" in post_lower or "second" in post_lower or "load" in post_lower:
            campaign_id = "website_speed"
        elif "ai" in post_lower or "agent" in post_lower or "24/7" in post_lower or "ollie" in post_lower:
            campaign_id = "ai_agents"
        elif "brand" in post_lower or "identity" in post_lower or "first impression" in post_lower:
            campaign_id = "brand_identity"
        else:
            campaign_id = "brand_identity"

    prompt = _social_prompt(campaign_id, post_content)
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
