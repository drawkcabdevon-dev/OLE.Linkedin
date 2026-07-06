"""
LinkedIn MCP Server
Provides tools: create_post, search_content, get_profile, send_connection_request

Usage:
  python linkedin_server.py

Requires:
  pip install mcp httpx python-dotenv
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("linkedin-mcp")

load_dotenv(Path.home() / "social-agent" / ".env")
# Also check ~/.social-agent/.env
load_dotenv(Path.home() / ".social-agent" / ".env", override=False)

DATA_DIR = Path(os.getenv("OLE_DATA_DIR", str(Path.home() / "Desktop" / "developer worspace " / "onlineeverywhere_-ai-marketing-suite" / "social-agent")))
ASSETS_DIR = DATA_DIR / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# ── API Client ──────────────────────────────────────────────────────

HEADERS = {
    "X-Restli-Protocol-Version": "2.0.0",
    "LinkedIn-Version": "202503",
}

class LinkedInClient:
    BASE = "https://api.linkedin.com/v2"

    def __init__(self, access_token: str):
        self._headers = {**HEADERS, "Authorization": f"Bearer {access_token}"}
        self._client = httpx.Client(headers=self._headers, timeout=30)

    def close(self) -> None:
        self._client.close()

    def _get(self, path: str, params: dict | None = None) -> dict:
        r = self._client.get(f"{self.BASE}{path}", params=params)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, body: dict) -> dict:
        r = self._client.post(f"{self.BASE}{path}", json=body)
        r.raise_for_status()
        return r.json()

    def me(self) -> dict:
        """Return authenticated user's profile via OpenID Connect."""
        r = self._client.get(f"{self.BASE}/userinfo")
        r.raise_for_status()
        data = r.json()
        return {
            "id": data.get("sub", ""),
            "localizedFirstName": data.get("given_name", ""),
            "localizedLastName": data.get("family_name", ""),
            "headline": "",
        }

    def get_profile_picture(self) -> str:
        """Fetch profile picture using the /me endpoint (still works for picture)."""
        try:
            r = self._client.get(f"{self.BASE}/me?projection=(profilePicture)")
            if r.status_code == 200:
                data = r.json()
                return data.get("profilePicture", {}).get(
                    "displayImage~", {}
                ).get("elements", [{}])[-1].get("identifiers", [{}])[0].get("identifier", "")
        except Exception:
            pass
        return ""

    def create_ugc_post(self, author: str, text: str, visibility: str = "PUBLIC") -> dict:
        """Create a text post on LinkedIn. Author is a full URN (person or organization)."""
        body = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": visibility,
            },
        }
        return self._post("/ugcPosts", body)

    def search_posts(self, keyword: str, count: int = 10) -> list[dict]:
        """Search recent posts by keyword. Uses optional search API."""
        params = {"q": "all", "keywords": keyword, "count": min(count, 50)}
        try:
            data = self._get("/search?q=posts", params)
            return data.get("elements", [])
        except httpx.HTTPStatusError as e:
            logger.warning(f"Search not available: {e}")
            return []

    def get_network_stats(self) -> dict:
        """Get connection count and network stats."""
        try:
            return self._get(f"/me/networkSizes/urn:li:organization:0")
        except httpx.HTTPStatusError:
            return {"connections": 0}

    def send_message(self, recipient_urn: str, text: str) -> dict:
        """Send a LinkedIn message to a user."""
        body = {
            "recipients": [recipient_urn],
            "body": text,
        }
        return self._post("/messaging/conversations", body)

    def list_organizations(self) -> list[dict]:
        """Return organizations the user can post as."""
        r = self._client.get(f"{self.BASE}/organizationalEntityAcls?q=roleAssignee")
        r.raise_for_status()
        elements = r.json().get("elements", [])
        orgs = []
        for e in elements:
            org_urn = e.get("organizationalTarget", "")
            role = e.get("role", "")
            org_id = org_urn.split(":")[-1] if ":" in org_urn else ""
            # Fetch org name
            try:
                r2 = self._client.get(f"{self.BASE}/organizations/{org_id}")
                name = r2.json().get("localizedName", "Unknown")
            except Exception:
                name = "Unknown"
            orgs.append({"id": org_id, "urn": org_urn, "name": name, "role": role})
        return orgs


DEFAULT_ORG_ID = os.getenv("LINKEDIN_ORG_ID", "125564340").strip()


def resolve_author(author_override: str | None = None) -> str:
    """Return the author URN — either org or personal."""
    if author_override:
        return f"urn:li:organization:{author_override}"
    if DEFAULT_ORG_ID:
        return f"urn:li:organization:{DEFAULT_ORG_ID}"
    return f"urn:li:person:{get_author_id()}"


# ── FastMCP Server ──────────────────────────────────────────────────

server = FastMCP("linkedin")

_client: LinkedInClient | None = None

def get_client() -> LinkedInClient:
    global _client
    if _client is None:
        token = os.getenv("LINKEDIN_ACCESS_TOKEN", "").strip()
        if not token:
            raise RuntimeError("LINKEDIN_ACCESS_TOKEN not set in .env")
        _client = LinkedInClient(token)
    return _client

def get_author_id() -> str:
    cache_path = DATA_DIR / "author_id.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text())["id"]

    client = get_client()
    profile = client.me()
    author_id = profile["id"]
    cache_path.write_text(json.dumps({"id": author_id}))
    return author_id


@server.tool()
def whoami() -> str:
    """Return the authenticated LinkedIn profile info."""
    client = get_client()
    profile = client.me()
    first = profile.get("localizedFirstName", "")
    last = profile.get("localizedLastName", "")
    headline = profile.get("headline", "")
    return json.dumps({"name": f"{first} {last}", "headline": headline}, indent=2)


@server.tool()
def create_post(text: str, visibility: str = "PUBLIC", organization_id: str = "") -> str:
    """Create a LinkedIn text post.
    
    Args:
        text: The post content (up to ~3000 chars).
        visibility: PUBLIC or CONNECTIONS.
        organization_id: Post as org (e.g. 125564340). Defaults to LINKEDIN_ORG_ID env or personal account.
    """
    if visibility not in ("PUBLIC", "CONNECTIONS"):
        return '{"error": "visibility must be PUBLIC or CONNECTIONS"}'

    client = get_client()
    author = resolve_author(organization_id or None)
    try:
        result = client.create_ugc_post(author, text, visibility)
        post_id = result.get("id", "unknown")
        return json.dumps({"status": "posted", "id": post_id, "author": author})
    except httpx.HTTPStatusError as e:
        return json.dumps({"status": "error", "detail": str(e.response.text)})


@server.tool()
def post_image(text: str, image_path: str, visibility: str = "PUBLIC", organization_id: str = "") -> str:
    """Create a LinkedIn post with an image.
    
    Args:
        text: Post caption.
        image_path: Absolute path to local image file.
        visibility: PUBLIC or CONNECTIONS.
        organization_id: Post as org (e.g. 125564340). Defaults to env or personal.
    """
    import base64
    client = get_client()
    author = resolve_author(organization_id or None)
    author_id = author.split(":")[-1]
    owner = author

    # 1. Register image upload
    register_body = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
            "owner": owner,
            "serviceRelationships": [{
                "relationshipType": "OWNER",
                "identifier": "urn:li:userGeneratedContent",
            }],
        }
    }
    try:
        reg = client._post("/assets?action=registerUpload", register_body)
        upload_url = reg["value"]["uploadMechanism"][
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
        ]["uploadUrl"]
        asset_urn = reg["value"]["asset"]
    except (httpx.HTTPStatusError, KeyError) as e:
        return json.dumps({"status": "error", "detail": f"Upload registration failed: {e}"})

    # 2. Upload image binary
    with open(image_path, "rb") as f:
        img_data = f.read()
    binary_headers = {
        **client._headers,
        "Content-Type": "image/jpeg",
        "Authorization": client._headers["Authorization"],
    }
    r = httpx.put(upload_url, headers=binary_headers, content=img_data)
    if r.status_code != 201:
        return json.dumps({"status": "error", "detail": f"Binary upload failed: {r.status_code}"})

    # 3. Create post with image
    body = {
        "author": author,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "IMAGE",
                "media": [{
                    "status": "READY",
                    "description": {"text": text},
                    "media": asset_urn,
                    "title": {"text": text[:200]},
                }],
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": visibility,
        },
    }
    try:
        result = client._post("/ugcPosts", body)
        return json.dumps({"status": "posted", "id": result.get("id", "unknown"), "author": author})
    except httpx.HTTPStatusError as e:
        return json.dumps({"status": "error", "detail": str(e.response.text)})


@server.tool()
def post_multi_image(text: str, image_paths: list[str], visibility: str = "PUBLIC", organization_id: str = "") -> str:
    """Post multiple images as a scrollable gallery (organic multi-image post).

    Args:
        text: Post caption.
        image_paths: List of absolute paths to image files (2-9 recommended).
        visibility: PUBLIC or CONNECTIONS.
        organization_id: Post as org (e.g. 125564340). Defaults to env or personal.
    """
    if visibility not in ("PUBLIC", "CONNECTIONS"):
        return '{"error": "visibility must be PUBLIC or CONNECTIONS"}'
    if len(image_paths) < 2:
        return '{"error": "Need at least 2 images for multi-image post"}'

    client = get_client()
    author = resolve_author(organization_id or None)
    owner = author

    media_items = []
    for i, img_path in enumerate(image_paths[:9]):  # Max 9 images
        register_body = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": owner,
                "serviceRelationships": [{
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent",
                }],
            }
        }
        try:
            reg = client._post("/assets?action=registerUpload", register_body)
            upload_url = reg["value"]["uploadMechanism"][
                "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
            ]["uploadUrl"]
            asset_urn = reg["value"]["asset"]
        except (httpx.HTTPStatusError, KeyError) as e:
            return json.dumps({"status": "error", "detail": f"Upload registration failed for image {i+1}: {e}"})

        with open(img_path, "rb") as f:
            img_data = f.read()
        binary_headers = {
            **client._headers,
            "Content-Type": "image/jpeg",
            "Authorization": client._headers["Authorization"],
        }
        r = httpx.put(upload_url, headers=binary_headers, content=img_data)
        if r.status_code != 201:
            return json.dumps({"status": "error", "detail": f"Binary upload failed for image {i+1}: {r.status_code}"})

        media_items.append({
            "status": "READY",
            "description": {"text": text[:100]},
            "media": asset_urn,
            "title": {"text": f"{text[:80]} — Image {i+1}"},
        })

    body = {
        "author": author,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "IMAGE",
                "media": media_items,
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": visibility,
        },
    }
    try:
        result = client._post("/ugcPosts", body)
        return json.dumps({
            "status": "posted",
            "id": result.get("id", "unknown"),
            "author": author,
            "image_count": len(media_items),
        })
    except httpx.HTTPStatusError as e:
        return json.dumps({"status": "error", "detail": str(e.response.text)})


@server.tool()
def create_carousel_post(text: str, image_paths: list[str], visibility: str = "PUBLIC", organization_id: str = "") -> str:
    """Create a LinkedIn carousel post with multiple scrollable images.

    Args:
        text: Post caption.
        image_paths: List of absolute paths to image files (3-5 recommended).
        visibility: PUBLIC or CONNECTIONS.
        organization_id: Post as org (e.g. 125564340). Defaults to env or personal.
    """
    if visibility not in ("PUBLIC", "CONNECTIONS"):
        return '{"error": "visibility must be PUBLIC or CONNECTIONS"}'
    if len(image_paths) < 2:
        return '{"error": "Need at least 2 images for a carousel"}'

    client = get_client()
    author = resolve_author(organization_id or None)
    owner = author

    media_items = []
    for i, img_path in enumerate(image_paths):
        # Register upload
        register_body = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": owner,
                "serviceRelationships": [{
                    "relationshipType": "OWNER",
                    "identifier": "urn:li:userGeneratedContent",
                }],
            }
        }
        try:
            reg = client._post("/assets?action=registerUpload", register_body)
            upload_url = reg["value"]["uploadMechanism"][
                "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
            ]["uploadUrl"]
            asset_urn = reg["value"]["asset"]
        except (httpx.HTTPStatusError, KeyError) as e:
            # Cleanup any already-uploaded assets
            return json.dumps({"status": "error", "detail": f"Upload registration failed for slide {i+1}: {e}"})

        # Upload binary
        with open(img_path, "rb") as f:
            img_data = f.read()
        binary_headers = {
            **client._headers,
            "Content-Type": "image/jpeg",
            "Authorization": client._headers["Authorization"],
        }
        r = httpx.put(upload_url, headers=binary_headers, content=img_data)
        if r.status_code != 201:
            return json.dumps({"status": "error", "detail": f"Binary upload failed for slide {i+1}: {r.status_code}"})

        media_items.append({
            "status": "READY",
            "description": {"text": f"Slide {i+1}"},
            "media": asset_urn,
            "title": {"text": f"{text[:100]} — Slide {i+1}"},
        })

    body = {
        "author": author,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "CAROUSEL",
                "media": media_items,
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": visibility,
        },
    }
    try:
        result = client._post("/ugcPosts", body)
        return json.dumps({
            "status": "posted",
            "id": result.get("id", "unknown"),
            "author": author,
            "slide_count": len(media_items),
        })
    except httpx.HTTPStatusError as e:
        return json.dumps({"status": "error", "detail": str(e.response.text)})


@server.tool()
def post_document(text: str, pdf_path: str, title: str = "", visibility: str = "PUBLIC", organization_id: str = "") -> str:
    """Post a PDF document (users scroll through pages like a carousel).

    Args:
        text: Post caption.
        pdf_path: Absolute path to the PDF file.
        title: Document title (defaults to post first 100 chars).
        visibility: PUBLIC or CONNECTIONS.
        organization_id: Post as org (e.g. 125564340).
    """
    if visibility not in ("PUBLIC", "CONNECTIONS"):
        return '{"error": "visibility must be PUBLIC or CONNECTIONS"}'

    client = get_client()
    author = resolve_author(organization_id or None)

    # 1. Register document upload
    register_body = {
        "registerUploadRequest": {
            "recipes": ["urn:li:digitalmediaRecipe:feedshare-document"],
            "owner": author,
            "serviceRelationships": [{
                "relationshipType": "OWNER",
                "identifier": "urn:li:userGeneratedContent",
            }],
        }
    }
    try:
        reg = client._post("/assets?action=registerUpload", register_body)
        upload_url = reg["value"]["uploadMechanism"][
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
        ]["uploadUrl"]
        asset_urn = reg["value"]["asset"]
    except (httpx.HTTPStatusError, KeyError) as e:
        return json.dumps({"status": "error", "detail": f"Upload registration failed: {e}"})

    # 2. Upload PDF binary
    with open(pdf_path, "rb") as f:
        pdf_data = f.read()
    binary_headers = {
        **client._headers,
        "Content-Type": "application/pdf",
        "Authorization": client._headers["Authorization"],
    }
    r = httpx.put(upload_url, headers=binary_headers, content=pdf_data)
    if r.status_code != 201:
        return json.dumps({"status": "error", "detail": f"PDF upload failed: {r.status_code}"})

    # 3. Create post with document
    doc_title = title or text[:100]
    body = {
        "author": author,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "DOCUMENT",
                "media": [{
                    "status": "READY",
                    "description": {"text": doc_title},
                    "media": asset_urn,
                    "title": {"text": doc_title},
                }],
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": visibility,
        },
    }
    try:
        result = client._post("/ugcPosts", body)
        return json.dumps({"status": "posted", "id": result.get("id", "unknown"), "author": author})
    except httpx.HTTPStatusError as e:
        return json.dumps({"status": "error", "detail": str(e.response.text)})


@server.tool()
def images_to_pdf(image_paths: list[str], output_path: str = "") -> str:
    """Combine multiple images into a single PDF file for document posting.

    Args:
        image_paths: List of absolute paths to image files.
        output_path: Desired PDF output path (auto-generated if empty).
    """
    from datetime import datetime
    if not output_path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(ASSETS_DIR / f"document_{ts}.pdf")

    try:
        from PIL import Image
        images = [Image.open(p).convert("RGB") for p in image_paths]
        # Fit each page to letter size (8.5x11 inches at 150 DPI = 1275x1650)
        fitted = []
        for img in images:
            # Scale to fit within letter size while maintaining aspect ratio
            img.thumbnail((1275, 1650), Image.LANCZOS)
            # Create white letter-sized canvas
            canvas = Image.new("RGB", (1275, 1650), (255, 255, 255))
            offset = ((1275 - img.width) // 2, (1650 - img.height) // 2)
            canvas.paste(img, offset)
            fitted.append(canvas)

        fitted[0].save(output_path, save_all=True, append_images=fitted[1:], quality=95)
        size = Path(output_path).stat().st_size
        return json.dumps({"status": "created", "output_path": output_path, "size_bytes": size, "pages": len(image_paths)})
    except Exception as e:
        return json.dumps({"status": "error", "detail": str(e)})


@server.tool()
def search_content(keyword: str, count: int = 10) -> str:
    """Search LinkedIn for recent posts matching keyword.
    
    Args:
        keyword: Search term.
        count: Number of results (max 50).
    """
    client = get_client()
    results = client.search_posts(keyword, count)
    return json.dumps({"results": results[:count]}, indent=2, default=str)


@server.tool()
def get_profile() -> str:
    """Get your LinkedIn profile info (name, headline, connections)."""
    client = get_client()
    profile = client.me()
    return json.dumps({
        "name": f'{profile.get("localizedFirstName", "")} {profile.get("localizedLastName", "")}',
        "headline": profile.get("headline", ""),
        "connections": 0,
    }, indent=2)


@server.tool()
def list_organizations() -> str:
    """List organizations you can post as (requires w_organization_social scope)."""
    client = get_client()
    try:
        orgs = client.list_organizations()
        return json.dumps(orgs, indent=2)
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": str(e.response.text)})


# ── Run ─────────────────────────────────────────────────────────────

def main():
    server.run(transport="stdio")

if __name__ == "__main__":
    main()
