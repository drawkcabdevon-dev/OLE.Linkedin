"""
Telegram Bot for Online Everywhere LinkedIn Agent.

Commands:
  /start         — Welcome & instructions
  /help          — List all commands
  /draft <topic> — Draft a LinkedIn post about <topic>
  /post <text>   — Post <text> to LinkedIn
  /post_image    — Reply to an image with a caption to post it
  /status        — System health check
  /authorize     — Link this chat to the agent

Run:
  TELEGRAM_BOT_TOKEN=xxx python telegram_bot.py
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path.home() / "social-agent" / ".env")
load_dotenv(Path.home() / ".social-agent" / ".env", override=False)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("telegram-bot")

AUTHORIZED_CHATS_FILE = Path.home() / "social-agent" / "authorized_chats.json"

# ── Authorized chat management ──────────────────────────────────────

def load_authorized_chats() -> set[int]:
    if AUTHORIZED_CHATS_FILE.exists():
        return set(json.loads(AUTHORIZED_CHATS_FILE.read_text()))
    return set()

def save_authorized_chats(chats: set[int]):
    AUTHORIZED_CHATS_FILE.write_text(json.dumps(list(chats)))

def is_authorized(chat_id: int) -> bool:
    return chat_id in load_authorized_chats()

# ── LinkedIn posting (direct, no MCP) ───────────────────────────────

def post_to_linkedin(text: str, image_path: str | None = None) -> dict:
    """Post directly via linkedin_server module."""
    sys.path.insert(0, str(Path.home() / "social-agent" / "mcp_servers"))
    from linkedin_server import create_post, post_image, post_multi_image
    if image_path:
        p = Path(image_path)
        if p.suffix.lower() in (".pdf",):
            # Not supported via telegram bot yet
            return {"status": "error", "detail": "PDF post not supported via Telegram"}
        return json.loads(post_image(text, str(p)))
    return json.loads(create_post(text))

def draft_content(topic: str) -> dict:
    """Generate a LinkedIn post draft using Gemini."""
    sys.path.insert(0, str(Path.home() / "social-agent" / "mcp_servers"))
    from content_server import draft_post
    return json.loads(draft_post(topic))

def research_trends() -> dict:
    """Get trending searches."""
    sys.path.insert(0, str(Path.home() / "social-agent" / "mcp_servers"))
    from research_server import trending_searches
    try:
        result = json.loads(trending_searches())
        return result
    except Exception as e:
        return {"status": "error", "detail": str(e)}

def research_topic(topic: str) -> dict:
    """Full research: trends + related queries + content ideas."""
    sys.path.insert(0, str(Path.home() / "social-agent" / "mcp_servers"))
    from research_server import analyze_topic
    try:
        result = json.loads(analyze_topic(topic))
        return result
    except Exception as e:
        return {"status": "error", "detail": str(e)}

def health_check() -> dict:
    """Check that all services are reachable."""
    result = {"status": "ok", "services": {}}
    # Check LinkedIn token
    sys.path.insert(0, str(Path.home() / "social-agent" / "mcp_servers"))
    from linkedin_server import whoami
    try:
        profile = json.loads(whoami())
        result["services"]["linkedin"] = "ok" if "name" in profile else "error"
    except Exception as e:
        result["services"]["linkedin"] = f"error: {e}"
    return result

# ── Bot ─────────────────────────────────────────────────────────────

def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set. Set it in .env")
        sys.exit(1)

    from telegram import Update
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

    allowed_users = set()

    async def require_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        chat_id = update.effective_chat.id if update.effective_chat else 0
        user = update.effective_user
        username = user.username if user else "unknown"

        if is_authorized(chat_id) or chat_id in allowed_users:
            return True

        await update.message.reply_text(
            f"Unauthorized. This bot is private.\n"
            f"Chat ID: {chat_id} | User: @{username}\n"
            "An admin needs to run /authorize from this chat."
        )
        return False

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (
            "Online Everywhere LinkedIn Agent\n\n"
            "I manage LinkedIn content for Online Everywhere.\n"
            "Authenticate with /authorize first.\n\n"
            "Commands:\n"
            "/draft <topic>   - Draft a post\n"
            "/trends          - Trending searches right now\n"
            "/research <topic>- Deep research on a topic\n"
            "/post <text>     - Post to LinkedIn\n"
            "/status          - Health check\n"
            "/help            - Full command list"
        )
        await update.message.reply_text(text)

    async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (
            "/authorize          - Authorize this chat\n"
            "/draft <topic>      - Draft a LinkedIn post\n"
            "/trends             - Today's trending searches\n"
            "/research <topic>   - Deep research + content ideas\n"
            "/post <text>        - Post to LinkedIn\n"
            "/post_image <text>  - Reply to an image with caption to post\n"
            "/status             - Health check\n"
            "/help               - This message"
        )
        await update.message.reply_text(text)

    async def authorize(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        user = update.effective_user
        username = user.username if user else "unknown"

        chats = load_authorized_chats()
        chats.add(chat_id)
        save_authorized_chats(chats)
        allowed_users.add(chat_id)

        await update.message.reply_text(
            f"Chat authorized. @{username} (ID: {chat_id}) can now use the agent."
        )
        logger.info(f"Authorized chat {chat_id} (@{username})")

    async def draft(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await require_auth(update, context):
            return
        topic = " ".join(context.args) if context.args else "digital marketing for Barbados SMEs"
        await update.message.reply_text(f"Drafting post about: {topic}...")
        try:
            result = draft_content(topic)
            if result.get("status") == "drafted":
                post_text = result.get("post", "")
                await update.message.reply_text(f"Draft:\n\n{post_text[:3000]}")
            else:
                await update.message.reply_text(f"Error: {result.get('detail', str(result))}")
        except Exception as e:
            await update.message.reply_text(f"Error drafting: {e}")

    async def post_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await require_auth(update, context):
            return
        text = " ".join(context.args) if context.args else ""
        if not text:
            await update.message.reply_text("Usage: /post <text>")
            return
        await update.message.reply_text("Posting to LinkedIn...")
        try:
            result = post_to_linkedin(text)
            if result.get("status") == "posted":
                post_id = result.get("id", "")
                await update.message.reply_text(f"Posted: https://linkedin.com/feed/update/{post_id}")
            else:
                await update.message.reply_text(f"Error: {result.get('detail', str(result))}")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    async def post_image_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await require_auth(update, context):
            return
        caption = " ".join(context.args) if context.args else "Check this out!"
        if not update.message.reply_to_message or not update.message.reply_to_message.photo:
            await update.message.reply_text("Reply to an image with /post_image <caption>")
            return
        photos = update.message.reply_to_message.photo
        file = await photos[-1].get_file()
        img_path = f"/tmp/telegram_post_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        await file.download_to_drive(img_path)

        await update.message.reply_text("Posting image to LinkedIn...")
        try:
            result = post_to_linkedin(caption, img_path)
            if result.get("status") == "posted":
                post_id = result.get("id", "")
                await update.message.reply_text(f"Posted: https://linkedin.com/feed/update/{post_id}")
            else:
                await update.message.reply_text(f"Error: {result.get('detail', str(result))}")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    async def trends_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await require_auth(update, context):
            return
        await update.message.reply_text("Fetching trending searches...")
        try:
            result = research_trends()
            if result.get("status") == "ok":
                trends = result.get("trends", [])
                if trends:
                    lines = ["**Trending Searches Now:**\n"]
                    for i, t in enumerate(trends[:10], 1):
                        lines.append(f"{i}. {t}")
                    await update.message.reply_text("\n".join(lines))
                else:
                    await update.message.reply_text("No trends found.")
                if "barbados_trends" in result:
                    bb = result["barbados_trends"]
                    if bb:
                        await update.message.reply_text(f"**Barbados:**\n" + "\n".join(f"- {b}" for b in bb[:10]))
            else:
                await update.message.reply_text(f"Error: {result.get('detail', str(result))}")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    async def research_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await require_auth(update, context):
            return
        topic = " ".join(context.args) if context.args else ""
        if not topic:
            await update.message.reply_text("Usage: /research <topic> (e.g. /research AI marketing)")
            return
        await update.message.reply_text(f"Researching: {topic}...")
        try:
            result = research_topic(topic)
            if result.get("status") == "ok":
                msg = f"**Research: {topic}**\n\n"
                msg += f"Interest Score: {result.get('interest_score', 'N/A')}/100\n"
                msg += f"Peak Interest: {result.get('peak_interest', 'N/A')}\n\n"
                top = result.get("top_related", [])
                if top:
                    msg += "**Related Searches:**\n" + "\n".join(f"- {q}" for q in top[:8]) + "\n\n"
                rising = result.get("rising_related", [])
                if rising:
                    msg += "**Rising Queries:**\n"
                    for r in rising[:5]:
                        q = r["query"] if isinstance(r, dict) else r
                        msg += f"- {q}\n"
                    msg += "\n"
                ideas = result.get("post_ideas", "")
                if ideas:
                    msg += f"**Content Ideas:**\n{ideas[:2000]}"
                await update.message.reply_text(msg[:4000])
            else:
                await update.message.reply_text(f"Error: {result.get('detail', str(result))}")
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await require_auth(update, context):
            return
        await update.message.reply_text("Checking system health...")
        try:
            hc = health_check()
            text = f"System Status: {hc['status']}\n"
            for svc, st in hc.get("services", {}).items():
                text += f"  {svc}: {st}\n"
            await update.message.reply_text(text)
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("authorize", authorize))
    app.add_handler(CommandHandler("draft", draft))
    app.add_handler(CommandHandler("trends", trends_cmd))
    app.add_handler(CommandHandler("research", research_cmd))
    app.add_handler(CommandHandler("post", post_cmd))
    app.add_handler(CommandHandler("post_image", post_image_cmd))
    app.add_handler(CommandHandler("status", status_cmd))

    logger.info("Bot started, polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
