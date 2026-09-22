"""
Design Asset Pipeline MCP Server
Generates scripts for HyperFrames, Seedance 2.0, and Higgsfield AI.
Saves design briefs and tracks asset generation in SQLite DB.

Usage:
  python design_server.py

Requires:
  pip install mcp
"""

import json
import os
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv(Path.home() / "social-agent" / ".env")
load_dotenv(Path.home() / ".social-agent" / ".env", override=False)

server = FastMCP("design")

DATA_DIR = Path(os.getenv("OLE_DATA_DIR", str(Path(__file__).parent.parent)))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "data.db"

ASSETS_DIR = DATA_DIR / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

BRAND = {
    "colors": {
        "primary": "#4285F4",
        "red": "#EA4335",
        "yellow": "#FBBC05",
        "green": "#34A853",
        "navy": "#202124",
        "navy_muted": "#5F6368",
    },
    "fonts": {"headlines": "Plus Jakarta Sans", "body": "Inter"},
    "tagline": "Data-Driven Marketing, Accelerated by AI.",
    "ai_engine": "Ollie",
}

CAMPAIGN_ASSETS = {
    "crisis_78": {
        "stat": "78.7%",
        "subtitle": "of Barbados businesses\nonly exist on social media",
        "visual": "bar chart with single red bar at 78.7%, grey remainder at 21.3%",
        "mood": "urgent, alarming, wake-up call",
    },
    "tax_credit": {
        "stat": "75%",
        "subtitle": "Government-funded\ndigital upgrade",
        "visual": "Barbados map with dollar-sign nodes, progress bar showing limited time",
        "mood": "urgent, opportunity, limited window",
    },
    "website_speed": {
        "stat": "0.4s",
        "subtitle": "Load time.\n$0/month.\n100% yours.",
        "visual": "speedometer at 0.4, vs competitors at 3-6s, broken template icons fading",
        "mood": "confident, superior, clean",
    },
    "ai_agents": {
        "stat": "24/7",
        "subtitle": "Your marketing\never sleeps",
        "visual": "glowing AI nodes connected in a network, Ollie logo pulsing, clock face with no hands",
        "mood": "futuristic, efficient, tireless",
    },
    "brand_identity": {
        "stat": "0.05s",
        "subtitle": "First impressions\nhappen fast",
        "visual": "before/after split: scattered brand chaos → unified cohesive identity",
        "mood": "professional, polished, trustworthy",
    },
}


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS design_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id TEXT NOT NULL,
            tool TEXT NOT NULL,
            post_content TEXT,
            script_content TEXT NOT NULL,
            output_path TEXT,
            status TEXT DEFAULT 'generated',
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


init_db()


def _campaign_from_post(post_content: str) -> str:
    post_lower = post_content.lower()
    if "78.7" in post_lower or "crisis" in post_lower:
        return "crisis_78"
    if "tax" in post_lower or "credit" in post_lower or "government" in post_lower:
        return "tax_credit"
    if "speed" in post_lower or "0.4" in post_lower or "second" in post_lower:
        return "website_speed"
    if "ai" in post_lower or "agent" in post_lower or "24/7" in post_lower or "ollie" in post_lower:
        return "ai_agents"
    if "brand" in post_lower or "identity" in post_lower or "first impression" in post_lower:
        return "brand_identity"
    return "brand_identity"


def _hyperframes_html(campaign_id: str, post_content: str) -> str:
    asset = CAMPAIGN_ASSETS.get(campaign_id, CAMPAIGN_ASSETS["brand_identity"])
    c = BRAND["colors"]

    return f"""<!DOCTYPE html>
<html>
<head>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Plus+Jakarta+Sans:wght@700;800&display=swap');
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: {c['navy']}; display: flex; align-items: center; justify-content: center; min-height: 1080px; font-family: 'Inter', sans-serif; }}
  .slide {{ width: 1920px; height: 1080px; background: linear-gradient(135deg, {c['navy']} 0%, #1a1a2e 100%); display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 80px; position: relative; overflow: hidden; }}
  .stat {{ font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 800; font-size: 180px; color: {c['primary']}; opacity: 0; animation: fadeUp 0.8s ease forwards; }}
  .subtitle {{ font-size: 48px; font-weight: 700; color: #fff; text-align: center; line-height: 1.3; margin-top: 24px; white-space: pre-line; opacity: 0; animation: fadeUp 0.8s ease 0.3s forwards; }}
  .tagline {{ font-size: 24px; color: {c['navy_muted']}; margin-top: 48px; letter-spacing: 2px; text-transform: uppercase; opacity: 0; animation: fadeUp 0.8s ease 0.6s forwards; }}
  .accent {{ position: absolute; bottom: 0; left: 0; right: 0; height: 6px; background: linear-gradient(90deg, {c['primary']}, {c['green']}, {c['yellow']}, {c['red']}); }}
  .logo {{ position: absolute; top: 40px; left: 40px; font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 700; font-size: 20px; color: {c['navy_muted']}; letter-spacing: 3px; opacity: 0; animation: fadeUp 0.8s ease 0.1s forwards; }}
  @keyframes fadeUp {{ from {{ opacity: 0; transform: translateY(40px); }} to {{ opacity: 1; transform: translateY(0); }} }}
  .pulse {{ position: absolute; width: 600px; height: 600px; border-radius: 50%; background: radial-gradient(circle, {c['primary']}08 0%, transparent 70%); animation: pulse 4s ease-in-out infinite; top: 50%; left: 50%; transform: translate(-50%, -50%); }}
  @keyframes pulse {{ 0%, 100% {{ transform: translate(-50%, -50%) scale(1); opacity: 0.5; }} 50% {{ transform: translate(-50%, -50%) scale(1.2); opacity: 0.8; }} }}
</style>
</head>
<body>
<div class="slide">
  <div class="pulse"></div>
  <div class="logo">ONLINE EVERYWHERE</div>
  <div class="stat">{asset['stat']}</div>
  <div class="subtitle">{asset['subtitle']}</div>
  <div class="tagline">Data-Driven Marketing, Accelerated by AI.</div>
  <div class="accent"></div>
</div>
</body>
</html>"""


def _seedance_prompt(campaign_id: str, post_content: str) -> dict:
    asset = CAMPAIGN_ASSETS.get(campaign_id, CAMPAIGN_ASSETS["brand_identity"])
    return {
        "tool": "seedance_2.0",
        "prompt": f"Professional cinematic motion graphics, {asset['mood']} mood. "
                  f"{asset['visual']}. "
                  f"Dark navy background with blue and green gradient accents. "
                  f"Text overlay shows '{asset['stat']}' in bold blue, "
                  f"with subtitle '{asset['subtitle'].replace(chr(10), ' ')}' below. "
                  f"Modern, clean, tech-forward aesthetic. 10 seconds. 1920x1080.",
        "negative_prompt": "blurry, low quality, text artifacts, distortion, jittery",
        "duration": 10,
        "resolution": "1920x1080",
        "style": "motion_graphics",
        "brand_colors": list(BRAND["colors"].values()),
    }


def _higgsfield_script(campaign_id: str, post_content: str) -> dict:
    asset = CAMPAIGN_ASSETS.get(campaign_id, CAMPAIGN_ASSETS["brand_identity"])
    return {
        "tool": "higgsfield",
        "scene": asset["visual"],
        "camera": "slow push-in on center, cinematic depth of field",
        "mood": asset["mood"],
        "duration": 8,
        "style": "cinematic_marketing",
        "text_overlay": f"{asset['stat']} — {asset['subtitle'].replace(chr(10), ' ')}",
        "brand_colors": list(BRAND["colors"].values()),
    }


def _save_asset(campaign_id: str, tool: str, post_content: str, script_content: str) -> dict:
    conn = get_db()
    conn.execute(
        "INSERT INTO design_assets (campaign_id, tool, post_content, script_content) VALUES (?, ?, ?, ?)",
        (campaign_id, tool, post_content, script_content),
    )
    conn.commit()
    aid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return {"status": "generated", "id": aid, "campaign_id": campaign_id, "tool": tool}


# ── MCP Tools ─────────────────────────────────────────────────────

@server.tool()
def generate_hyperframes(campaign_id: str = "", post_content: str = "", output_name: str = "") -> str:
    """Generate a HyperFrames HTML composition for OLE brand motion graphics.

    Args:
        campaign_id: One of crisis_78, tax_credit, website_speed, ai_agents, brand_identity (auto-detected from post if empty).
        post_content: The LinkedIn post text (used for campaign detection and context).
        output_name: Custom filename (without extension). Auto-generated if empty.
    """
    if not campaign_id:
        campaign_id = _campaign_from_post(post_content)
    if not output_name:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"hf_{campaign_id}_{ts}"

    html = _hyperframes_html(campaign_id, post_content)
    out_path = ASSETS_DIR / f"{output_name}.html"
    out_path.write_text(html)

    result = _save_asset(campaign_id, "hyperframes", post_content, html)
    result["output_path"] = str(out_path)
    return json.dumps(result, indent=2)


@server.tool()
def generate_seedance_prompt(campaign_id: str = "", post_content: str = "") -> str:
    """Generate a Seedance 2.0-compatible video prompt.

    Args:
        campaign_id: One of crisis_78, tax_credit, website_speed, ai_agents, brand_identity.
        post_content: The LinkedIn post text for context.
    """
    if not campaign_id:
        campaign_id = _campaign_from_post(post_content)
    prompt = _seedance_prompt(campaign_id, post_content)
    prompt_json = json.dumps(prompt, indent=2)

    result = _save_asset(campaign_id, "seedance", post_content, prompt_json)
    result["prompt"] = prompt
    return json.dumps(result, indent=2)


@server.tool()
def generate_higgsfield_script(campaign_id: str = "", post_content: str = "") -> str:
    """Generate a Higgsfield AI video script for cinematic short-form video.

    Args:
        campaign_id: One of crisis_78, tax_credit, website_speed, ai_agents, brand_identity.
        post_content: The LinkedIn post text for context.
    """
    if not campaign_id:
        campaign_id = _campaign_from_post(post_content)
    script = _higgsfield_script(campaign_id, post_content)
    script_json = json.dumps(script, indent=2)

    result = _save_asset(campaign_id, "higgsfield", post_content, script_json)
    result["script"] = script
    return json.dumps(result, indent=2)


@server.tool()
def render_hyperframes(script_path: str, output_path: str = "") -> str:
    """Render a HyperFrames HTML file to MP4 using npx hyperframes render.

    Args:
        script_path: Absolute path to the .html file generated by generate_hyperframes.
        output_path: Desired output .mp4 path. Auto-generated if empty.
    """
    path = Path(script_path)
    if not path.exists():
        return json.dumps({"status": "error", "detail": f"File not found: {script_path}"})
    if not output_path:
        output_path = str(path.with_suffix(".mp4"))

    try:
        result = subprocess.run(
            ["npx", "hyperframes", "render", str(path), "--output", output_path],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            return json.dumps({"status": "rendered", "output": output_path, "log": result.stdout})
        else:
            return json.dumps({"status": "error", "detail": result.stderr, "log": result.stdout})
    except FileNotFoundError:
        return json.dumps({"status": "error", "detail": "npx not found. Install Node.js and run: npm install -g hyperframes"})
    except subprocess.TimeoutExpired:
        return json.dumps({"status": "error", "detail": "Render timed out after 120s"})


@server.tool()
def list_design_assets(campaign_id: str = "", tool: str = "", status: str = "") -> str:
    """List generated design assets, optionally filtered.

    Args:
        campaign_id: Filter by campaign (optional).
        tool: Filter by tool — hyperframes, seedance, higgsfield (optional).
        status: Filter by status (optional).
    """
    conn = get_db()
    query = "SELECT * FROM design_assets WHERE 1=1"
    params = []
    if campaign_id:
        query += " AND campaign_id = ?"
        params.append(campaign_id)
    if tool:
        query += " AND tool = ?"
        params.append(tool)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC LIMIT 50"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return json.dumps([dict(r) for r in rows], indent=2, default=str)


@server.tool()
def design_brief_from_post(post_content: str) -> str:
    """Generate a complete design brief from a LinkedIn post.
    Outputs recommendations for which tool(s) to use and the asset specs.

    Args:
        post_content: The full LinkedIn post text.
    """
    campaign_id = _campaign_from_post(post_content)
    asset = CAMPAIGN_ASSETS.get(campaign_id, CAMPAIGN_ASSETS["brand_identity"])

    hf_html = _hyperframes_html(campaign_id, post_content)
    hf_path = ASSETS_DIR / f"brief_{campaign_id}.html"
    hf_path.write_text(hf_html)

    brief = {
        "campaign_id": campaign_id,
        "detected_from_post": True,
        "asset_spec": asset,
        "tool_recommendations": {
            "hyperframes": {
                "reason": "Best for motion graphics with text overlays and brand animations",
                "html_path": str(hf_path),
                "render_command": f"npx hyperframes render {hf_path} --output {hf_path.with_suffix('.mp4')}",
            },
            "seedance": {
                "reason": "Best for cinematic AI video with quad-modal (text+image+audio+video)",
                "prompt": _seedance_prompt(campaign_id, post_content),
            },
            "higgsfield": {
                "reason": "Best for short-form vertical video with camera control",
                "script": _higgsfield_script(campaign_id, post_content),
            },
        },
        "brand": {
            "colors": BRAND["colors"],
            "fonts": BRAND["fonts"],
            "tagline": BRAND["tagline"],
        },
    }

    result = _save_asset(campaign_id, "design_brief", post_content, json.dumps(brief))
    result["brief"] = brief
    return json.dumps(result, indent=2, default=str)


def main():
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
