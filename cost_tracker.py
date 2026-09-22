"""
Cost Tracker — logs API usage (tokens, calls, estimated costs) to SQLite.
Provides daily summaries and total spend visibility.
"""

import os
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(os.getenv("OLE_DATA_DIR", str(Path(__file__).parent)))
DB_PATH = DATA_DIR / "data.db"

# Pricing per 1K tokens (as of 2026)
PRICING = {
    "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
    "nvidia/nemotron-3-ultra-550b": {"input": 0.0, "output": 0.0},  # free tier
    "nvidia/flux.1-schnell": {"input": 0.0, "output": 0.0},  # free tier
    "pollinations": {"input": 0.0, "output": 0.0},  # free
    "stitch": {"input": 0.0, "output": 0.0},  # free
}


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_cost_table():
    """Create the cost tracking table if it doesn't exist."""
    conn = _get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service TEXT NOT NULL,
            model TEXT,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            estimated_cost_usd REAL DEFAULT 0.0,
            endpoint TEXT,
            status TEXT DEFAULT 'ok',
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_api_usage_service ON api_usage(service)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_api_usage_date ON api_usage(created_at)
    """)
    conn.commit()
    conn.close()


def log_api_call(
    service: str,
    model: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
    endpoint: str = "",
    status: str = "ok",
    metadata: dict | None = None,
):
    """Log an API call with token usage and estimated cost."""
    # Calculate estimated cost
    pricing = PRICING.get(model, PRICING.get(service, {"input": 0, "output": 0}))
    cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1000.0

    conn = _get_db()
    conn.execute(
        """INSERT INTO api_usage (service, model, input_tokens, output_tokens,
           estimated_cost_usd, endpoint, status, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            service,
            model,
            input_tokens,
            output_tokens,
            cost,
            endpoint,
            status,
            json.dumps(metadata) if metadata else None,
        ),
    )
    conn.commit()
    conn.close()
    return cost


def get_daily_summary(days: int = 7) -> list[dict]:
    """Get daily cost summaries for the last N days."""
    conn = _get_db()
    rows = conn.execute(
        """SELECT
            DATE(created_at) as day,
            service,
            COUNT(*) as calls,
            SUM(input_tokens) as total_input,
            SUM(output_tokens) as total_output,
            SUM(estimated_cost_usd) as total_cost
        FROM api_usage
        WHERE created_at >= DATE('now', ?)
        GROUP BY day, service
        ORDER BY day DESC, service""",
        (f"-{days} days",),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_total_spend() -> dict:
    """Get total spend across all time."""
    conn = _get_db()
    row = conn.execute(
        """SELECT
            COUNT(*) as total_calls,
            SUM(input_tokens) as total_input_tokens,
            SUM(output_tokens) as total_output_tokens,
            SUM(estimated_cost_usd) as total_cost_usd
        FROM api_usage"""
    ).fetchone()
    conn.close()
    return dict(row) if row else {"total_calls": 0, "total_input_tokens": 0, "total_output_tokens": 0, "total_cost_usd": 0}


def get_spend_by_service() -> list[dict]:
    """Get spend broken down by service."""
    conn = _get_db()
    rows = conn.execute(
        """SELECT
            service,
            COUNT(*) as calls,
            SUM(input_tokens) as total_input,
            SUM(output_tokens) as total_output,
            SUM(estimated_cost_usd) as total_cost
        FROM api_usage
        GROUP BY service
        ORDER BY total_cost DESC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# Initialize on import
init_cost_table()
