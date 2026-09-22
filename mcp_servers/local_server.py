"""
Local Data MCP Server
SQLite-backed storage for drafts, published posts, leads, content calendar.

Usage:
  python local_server.py
"""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv(Path.home() / "social-agent" / ".env")
load_dotenv(Path.home() / ".social-agent" / ".env", override=False)

server = FastMCP("local-data")

DB_DIR = Path(os.getenv("OLE_DATA_DIR", str(Path(__file__).parent.parent)))
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "data.db"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            content TEXT NOT NULL,
            scheduled_at TEXT,
            status TEXT DEFAULT 'draft',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS published (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            external_id TEXT,
            content TEXT NOT NULL,
            url TEXT,
            posted_at TEXT DEFAULT (datetime('now')),
            engagement_data TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            profile_url TEXT,
            name TEXT,
            headline TEXT,
            industry TEXT,
            status TEXT DEFAULT 'new',
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            last_contacted_at TEXT
        );

        CREATE TABLE IF NOT EXISTS content_calendar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            title TEXT,
            content TEXT,
            scheduled_for TEXT NOT NULL,
            status TEXT DEFAULT 'planned',
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


init_db()


# ── Drafts ──────────────────────────────────────────────────────────

@server.tool()
def save_draft(platform: str, content: str, scheduled_at: str | None = None) -> str:
    """Save a content draft.
    
    Args:
        platform: e.g., linkedin, twitter
        content: The draft text
        scheduled_at: Optional ISO datetime for scheduled posting
    """
    conn = get_db()
    conn.execute(
        "INSERT INTO drafts (platform, content, scheduled_at) VALUES (?, ?, ?)",
        (platform, content, scheduled_at),
    )
    conn.commit()
    draft_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return json.dumps({"status": "saved", "id": draft_id})


@server.tool()
def list_drafts(platform: str | None = None, status: str = "draft") -> str:
    """List saved drafts, optionally filtered by platform.
    
    Args:
        platform: Filter by platform (optional)
        status: Filter by status (default: draft)
    """
    conn = get_db()
    if platform:
        rows = conn.execute(
            "SELECT * FROM drafts WHERE platform = ? AND status = ? ORDER BY created_at DESC",
            (platform, status),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM drafts WHERE status = ? ORDER BY created_at DESC",
            (status,),
        ).fetchall()
    conn.close()
    return json.dumps([dict(r) for r in rows], indent=2, default=str)


# ── Published Posts ────────────────────────────────────────────────

@server.tool()
def log_published(platform: str, external_id: str, content: str, url: str = "") -> str:
    """Log a published post to local history.
    
    Args:
        platform: e.g., linkedin
        external_id: The platform's post ID
        content: Full text of the post
        url: Permalink to the post
    """
    conn = get_db()
    conn.execute(
        "INSERT INTO published (platform, external_id, content, url) VALUES (?, ?, ?, ?)",
        (platform, external_id, content, url),
    )
    conn.commit()
    pid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return json.dumps({"status": "logged", "id": pid})


@server.tool()
def list_published(platform: str | None = None, limit: int = 20) -> str:
    """List recently published posts.
    
    Args:
        platform: Filter by platform (optional)
        limit: Max results (default 20)
    """
    conn = get_db()
    if platform:
        rows = conn.execute(
            "SELECT * FROM published WHERE platform = ? ORDER BY posted_at DESC LIMIT ?",
            (platform, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM published ORDER BY posted_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    return json.dumps([dict(r) for r in rows], indent=2, default=str)


# ── Leads ───────────────────────────────────────────────────────────

@server.tool()
def add_lead(platform: str, name: str, profile_url: str = "", headline: str = "", industry: str = "") -> str:
    """Add a lead to track.
    
    Args:
        platform: e.g., linkedin
        name: Full name
        profile_url: URL to profile
        headline: Their headline/title
        industry: Industry
    """
    conn = get_db()
    conn.execute(
        "INSERT INTO leads (platform, name, profile_url, headline, industry) VALUES (?, ?, ?, ?, ?)",
        (platform, name, profile_url, headline, industry),
    )
    conn.commit()
    lid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return json.dumps({"status": "added", "id": lid})


@server.tool()
def list_leads(status: str | None = None) -> str:
    """List tracked leads.
    
    Args:
        status: Filter by status (new, contacted, replied, converted)
    """
    conn = get_db()
    if status:
        rows = conn.execute(
            "SELECT * FROM leads WHERE status = ? ORDER BY created_at DESC",
            (status,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM leads ORDER BY created_at DESC").fetchall()
    conn.close()
    return json.dumps([dict(r) for r in rows], indent=2, default=str)


# ── Content Calendar ───────────────────────────────────────────────

@server.tool()
def schedule_content(platform: str, content: str, scheduled_for: str, title: str = "") -> str:
    """Schedule content for future posting.
    
    Args:
        platform: e.g., linkedin
        content: The post content
        scheduled_for: ISO datetime string
        title: Optional title/label
    """
    conn = get_db()
    conn.execute(
        "INSERT INTO content_calendar (platform, title, content, scheduled_for) VALUES (?, ?, ?, ?)",
        (platform, title, content, scheduled_for),
    )
    conn.commit()
    cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return json.dumps({"status": "scheduled", "id": cid})


@server.tool()
def get_calendar(platform: str | None = None, days: int = 14) -> str:
    """Get upcoming scheduled content.
    
    Args:
        platform: Filter by platform (optional)
        days: How many days ahead (default 14)
    """
    conn = get_db()
    if platform:
        rows = conn.execute(
            """SELECT * FROM content_calendar 
               WHERE platform = ? AND scheduled_for >= datetime('now') 
               AND scheduled_for <= datetime('now', '+' || ? || ' days')
               ORDER BY scheduled_for ASC""",
            (platform, days),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT * FROM content_calendar 
               WHERE scheduled_for >= datetime('now') 
               AND scheduled_for <= datetime('now', '+' || ? || ' days')
               ORDER BY scheduled_for ASC""",
            (days,),
        ).fetchall()
    conn.close()
    return json.dumps([dict(r) for r in rows], indent=2, default=str)


# ── Run ─────────────────────────────────────────────────────────────

def main():
    server.run(transport="stdio")

if __name__ == "__main__":
    main()
