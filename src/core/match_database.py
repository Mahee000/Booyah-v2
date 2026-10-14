import os
import sqlite3
import time
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(WORKSPACE_DIR, "data")
CAPTURES_DIR = os.path.join(DATA_DIR, "captures")
DB_PATH = os.path.join(DATA_DIR, "match_history.db")

class MatchDatabase:
    """
    Local SQLite Match Analytics & Capture Store:
    - Stores match results, timestamps, OCR signatures, and saved capture paths.
    - Matches legacy Booyah database schema.
    """
    _instance = None

    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(CAPTURES_DIR, exist_ok=True)
        self._init_db()

    @classmethod
    def get(cls) -> "MatchDatabase":
        if cls._instance is None:
            cls._instance = MatchDatabase()
        return cls._instance

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS matches (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        node_id TEXT,
                        alias TEXT,
                        mode TEXT,
                        state TEXT,
                        ocr_text TEXT,
                        capture_path TEXT,
                        timestamp INTEGER,
                        winners TEXT
                    );
                """)
                # Handle existing database migration if column doesn't exist
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(matches);")
                columns = [c[1] for c in cursor.fetchall()]
                if "winners" not in columns:
                    conn.execute("ALTER TABLE matches ADD COLUMN winners TEXT;")
                conn.commit()
        except Exception as e:
            logger.error(f"Error initializing match database: {e}")

    def save_match(self, node_id: str, alias: str, mode: str, state: str, ocr_text: str, capture_path: str, timestamp_ms: Optional[int] = None, winners: Optional[str] = None) -> int:
        ts = timestamp_ms or int(time.time() * 1000)
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO matches (node_id, alias, mode, state, ocr_text, capture_path, timestamp, winners)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (node_id, alias, mode, state, ocr_text, capture_path, ts, winners or ""))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error saving match: {e}")
            return -1

    def get_matches(self, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, node_id, alias, mode, state, ocr_text, capture_path, timestamp, winners
                    FROM matches
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))
                rows = cursor.fetchall()
                results = []
                for r in rows:
                    results.append({
                        "id": r["id"],
                        "node_id": r["node_id"],
                        "alias": r["alias"],
                        "mode": r["mode"],
                        "state": r["state"],
                        "ocr_text": r["ocr_text"],
                        "capture_path": r["capture_path"],
                        "timestamp": r["timestamp"],
                        "winners": r["winners"] if "winners" in r.keys() else ""
                    })
                return results
        except Exception as e:
            logger.error(f"Error fetching matches: {e}")
            return []

    def delete_match(self, match_id: int) -> bool:
        """Deletes a match record and removes its physical image file if it exists."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT capture_path FROM matches WHERE id = ?", (match_id,))
                row = cursor.fetchone()
                if row and row["capture_path"] and os.path.exists(row["capture_path"]):
                    try:
                        os.remove(row["capture_path"])
                    except Exception:
                        pass
                cursor.execute("DELETE FROM matches WHERE id = ?", (match_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error deleting match {match_id}: {e}")
            return False

    def clear_all_matches(self) -> bool:
        """Clears all records in matches table."""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM matches")
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error clearing matches: {e}")
            return False

    def get_captures_dir(self) -> str:
        return CAPTURES_DIR
