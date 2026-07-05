"""
Shared Gemini client — calls Vertex AI Gemini endpoint with ADC auth.
Used by content_server, research_server, and telegram_bot.
Avoids free-tier quota issues by using project billing.
Works locally (gcloud ADC) and on Cloud Run (metadata server).
"""

import os
import time

import httpx

try:
    import google.auth
    import google.auth.transport.requests
    google_auth = google.auth
except ImportError:
    google_auth = None

LOCATION = "us-central1"
PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "linkedin-agent-501504")
MODEL = "gemini-2.5-flash"
VERTEX_URL = (
    f"https://{LOCATION}-aiplatform.googleapis.com/v1/projects/{PROJECT}"
    f"/locations/{LOCATION}/publishers/google/models/{MODEL}:generateContent"
)

_token: str = ""
_token_expiry: float = 0


def _get_token() -> str:
    global _token, _token_expiry
    if time.time() < _token_expiry:
        return _token
    if google_auth:
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        _token = credentials.token
    else:
        import subprocess
        result = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True, text=True, timeout=10,
        )
        result.check_returncode()
        _token = result.stdout.strip()
    _token_expiry = time.time() + 1800
    return _token


def generate_content(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> str:
    """Call Vertex AI Gemini. Returns response text. Raises on error."""
    token = _get_token()
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    r = httpx.post(VERTEX_URL, json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"No candidates in response: {data}")
    return candidates[0]["content"]["parts"][0]["text"]
