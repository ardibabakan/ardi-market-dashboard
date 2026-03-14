"""
Supabase client wrapper for Ardi Market Command Center.
All database operations go through this module.
"""
import json
import logging
from datetime import datetime, timezone
from supabase import create_client, Client

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger("ardi.supabase")

_client: Client = None

def get_client() -> Client:
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client

_TABLES_WITH_UPDATED_AT = {"positions"}

def upsert(table: str, data: dict, on_conflict: str = "id"):
    """Insert or update a row."""
    try:
        client = get_client()
        if table in _TABLES_WITH_UPDATED_AT:
            data["updated_at"] = datetime.now(timezone.utc).isoformat()
        result = client.table(table).upsert(data, on_conflict=on_conflict).execute()
        return result.data
    except Exception as e:
        logger.error(f"Supabase upsert to {table} failed: {e}")
        return None

def insert(table: str, data: dict):
    """Insert a new row. Let Supabase handle created_at default."""
    try:
        client = get_client()
        result = client.table(table).insert(data).execute()
        return result.data
    except Exception as e:
        logger.error(f"Supabase insert to {table} failed: {e}")
        return None

def select(table: str, filters: dict = None, order_by: str = None,
           limit: int = None):
    """Query rows from a table."""
    try:
        client = get_client()
        query = client.table(table).select("*")
        if filters:
            for key, value in filters.items():
                query = query.eq(key, value)
        if order_by:
            desc = order_by.startswith("-")
            col = order_by.lstrip("-")
            query = query.order(col, desc=desc)
        if limit:
            query = query.limit(limit)
        result = query.execute()
        return result.data
    except Exception as e:
        logger.error(f"Supabase select from {table} failed: {e}")
        return []

def select_latest(table: str, key_col: str, key_val: str):
    """Get the most recent row matching a key."""
    rows = select(table, {key_col: key_val}, order_by="-created_at", limit=1)
    return rows[0] if rows else None
