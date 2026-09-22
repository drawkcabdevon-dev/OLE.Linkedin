"""
Shared Gemini client using the official google-genai SDK.
Used by content_server, research_server, telegram_bot, and image_server.
Handles both text generation and image generation via gemini-2.5-flash-image.
"""

import os
import time
import logging
from pathlib import Path

logger = logging.getLogger("gemini-client")

# ── Cost tracking (best-effort) ──────────────────────────────────

def _log_usage(service: str, model: str, input_tokens: int, output_tokens: int, endpoint: str = ""):
    """Log API usage to cost tracker. Non-blocking — never crashes the caller."""
    try:
        from cost_tracker import log_api_call
        log_api_call(service, model, input_tokens, output_tokens, endpoint)
    except Exception:
        pass

# ── SDK Client (lazy init) ───────────────────────────────────────

_client = None
_IMAGE_CLIENT = None

def _get_client():
    """Get or create the google-genai client. Uses Vertex AI backend."""
    global _client
    if _client is not None:
        return _client
    try:
        from google import genai
        from google.genai.types import HttpOptions

        _client = genai.Client(
            vertexai=True,
            http_options=HttpOptions(api_version="v1")
        )
        logger.info("Gemini client initialized (Vertex AI backend)")
        return _client
    except Exception as e:
        logger.error(f"Failed to initialize Gemini client: {e}")
        raise


def _get_image_client():
    """Get or create the image generation client."""
    global _IMAGE_CLIENT
    if _IMAGE_CLIENT is not None:
        return _IMAGE_CLIENT
    try:
        from google import genai
        from google.genai.types import HttpOptions

        _IMAGE_CLIENT = genai.Client(
            vertexai=True,
            http_options=HttpOptions(api_version="v1")
        )
        logger.info("Image generation client initialized")
        return _IMAGE_CLIENT
    except Exception as e:
        logger.error(f"Failed to initialize image client: {e}")
        raise


# ── Text Generation ──────────────────────────────────────────────

def generate_content(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    max_retries: int = 3,
) -> str:
    """Call Gemini for text generation. Returns response text. Raises on error."""
    from google.genai import types

    client = _get_client()

    last_error = None
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                )
            )
            text = response.text or ""
            # Log usage
            usage = response.usage_metadata
            if usage:
                _log_usage("gemini", "gemini-2.5-flash",
                           getattr(usage, 'prompt_token_count', 0),
                           getattr(usage, 'candidates_token_count', 0),
                           "generate_content")
            return text
        except Exception as e:
            last_error = e
            if "429" in str(e) and attempt < max_retries - 1:
                wait = 2 ** attempt * 5
                logger.warning(f"Gemini 429 (attempt {attempt+1}/{max_retries}), retrying in {wait}s...")
                time.sleep(wait)
                continue
            logger.warning(f"Gemini error: {e}")
            raise

    raise last_error or RuntimeError("Gemini: max retries exceeded")


# ── Image Generation ─────────────────────────────────────────────

def generate_image(
    prompt: str,
    aspect_ratio: str = "1:1",
    max_retries: int = 3,
) -> bytes | None:
    """Generate an image using gemini-2.5-flash-image. Returns PNG bytes or None."""
    from google.genai import types

    client = _get_image_client()

    last_error = None
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash-image",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(
                        aspect_ratio=aspect_ratio,
                    )
                )
            )
            # Extract image from response
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data:
                    img_data = part.inline_data.data
                    # Log usage (1290 tokens per image)
                    _log_usage("gemini", "gemini-2.5-flash-image", 0, 1290, "generate_image")
                    return img_data
            logger.warning("No image in Gemini response")
            return None
        except Exception as e:
            last_error = e
            if "429" in str(e) and attempt < max_retries - 1:
                wait = 2 ** attempt * 5
                logger.warning(f"Gemini Image 429 (attempt {attempt+1}/{max_retries}), retrying in {wait}s...")
                time.sleep(wait)
                continue
            logger.warning(f"Gemini image error: {e}")
            return None

    return None


def generate_post_with_image(
    post_text: str,
    image_prompt: str,
    aspect_ratio: str = "1:1",
) -> tuple[str, bytes | None]:
    """Generate a LinkedIn post AND its image in a single call.
    Returns (post_text, image_bytes or None)."""
    from google.genai import types

    client = _get_image_client()

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=f"Create a LinkedIn post and a matching professional graphic.\n\nPost text:\n{post_text}\n\nImage prompt: {image_prompt}",
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio=aspect_ratio,
                )
            )
        )

        text = ""
        img_data = None
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'text') and part.text:
                text = part.text
            if hasattr(part, 'inline_data') and part.inline_data:
                img_data = part.inline_data.data

        _log_usage("gemini", "gemini-2.5-flash-image", 0, 1290, "generate_post_with_image")
        return text or post_text, img_data
    except Exception as e:
        logger.warning(f"Gemini post+image error: {e}")
        return post_text, None
