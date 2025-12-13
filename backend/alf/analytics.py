"""
Analytics module for tracking queries and usage.
Uses SQLite for simple, file-based storage.
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json


class Analytics:
    """Simple analytics tracking using SQLite."""

    def __init__(self, db_path: str = None):
        """Initialize analytics with SQLite database."""
        if db_path is None:
            db_path = Path(__file__).parent / "data" / "analytics.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _init_db(self):
        """Initialize database tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Queries table - logs every question asked
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                session_id TEXT,
                question TEXT NOT NULL,
                response_time_ms INTEGER,
                citations_count INTEGER,
                top_citation TEXT,
                ip_address TEXT
            )
        """)

        # Sessions table - tracks unique sessions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                query_count INTEGER DEFAULT 0,
                user_agent TEXT,
                ip_address TEXT
            )
        """)

        # Page views table - basic traffic tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS page_views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                session_id TEXT,
                page TEXT,
                ip_address TEXT
            )
        """)

        conn.commit()
        conn.close()

    def log_query(
        self,
        question: str,
        session_id: Optional[str] = None,
        response_time_ms: Optional[int] = None,
        citations_count: Optional[int] = None,
        top_citation: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        """Log a query to the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO queries (session_id, question, response_time_ms, citations_count, top_citation, ip_address)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (session_id, question, response_time_ms, citations_count, top_citation, ip_address))

        # Update session if exists
        if session_id:
            cursor.execute("""
                INSERT INTO sessions (session_id, query_count, ip_address)
                VALUES (?, 1, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    last_seen = CURRENT_TIMESTAMP,
                    query_count = query_count + 1
            """, (session_id, ip_address))

        conn.commit()
        conn.close()

    def log_page_view(
        self,
        session_id: Optional[str] = None,
        page: str = "/",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log a page view."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO page_views (session_id, page, ip_address)
            VALUES (?, ?, ?)
        """, (session_id, page, ip_address))

        # Update or create session
        if session_id:
            cursor.execute("""
                INSERT INTO sessions (session_id, ip_address, user_agent)
                VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    last_seen = CURRENT_TIMESTAMP,
                    user_agent = COALESCE(?, user_agent)
            """, (session_id, ip_address, user_agent, user_agent))

        conn.commit()
        conn.close()

    def get_recent_queries(self, limit: int = 100, days: int = 30) -> List[Dict]:
        """Get recent queries."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                id,
                datetime(timestamp, 'localtime') as timestamp,
                session_id,
                question,
                response_time_ms,
                citations_count,
                top_citation
            FROM queries
            WHERE timestamp >= datetime('now', ?)
            ORDER BY timestamp DESC
            LIMIT ?
        """, (f'-{days} days', limit))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_popular_queries(self, limit: int = 20, days: int = 30) -> List[Dict]:
        """Get most common query patterns."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Simple grouping by similar questions (lowercase, trimmed)
        cursor.execute("""
            SELECT
                LOWER(TRIM(question)) as query,
                COUNT(*) as count,
                MAX(timestamp) as last_asked
            FROM queries
            WHERE timestamp >= datetime('now', ?)
            GROUP BY LOWER(TRIM(question))
            ORDER BY count DESC
            LIMIT ?
        """, (f'-{days} days', limit))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_stats(self, days: int = 30) -> Dict:
        """Get summary statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        since = f'-{days} days'

        # Total queries
        cursor.execute("""
            SELECT COUNT(*) FROM queries WHERE timestamp >= datetime('now', ?)
        """, (since,))
        total_queries = cursor.fetchone()[0]

        # Unique sessions
        cursor.execute("""
            SELECT COUNT(DISTINCT session_id) FROM queries
            WHERE timestamp >= datetime('now', ?) AND session_id IS NOT NULL
        """, (since,))
        unique_sessions = cursor.fetchone()[0]

        # Average response time
        cursor.execute("""
            SELECT AVG(response_time_ms) FROM queries
            WHERE timestamp >= datetime('now', ?) AND response_time_ms IS NOT NULL
        """, (since,))
        avg_response_time = cursor.fetchone()[0]

        # Queries per day
        cursor.execute("""
            SELECT
                DATE(timestamp) as date,
                COUNT(*) as count
            FROM queries
            WHERE timestamp >= datetime('now', ?)
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
        """, (since,))
        queries_by_day = [{"date": row[0], "count": row[1]} for row in cursor.fetchall()]

        # Top cited regulations
        cursor.execute("""
            SELECT top_citation, COUNT(*) as count
            FROM queries
            WHERE timestamp >= datetime('now', ?) AND top_citation IS NOT NULL
            GROUP BY top_citation
            ORDER BY count DESC
            LIMIT 10
        """, (since,))
        top_citations = [{"citation": row[0], "count": row[1]} for row in cursor.fetchall()]

        # Total page views
        cursor.execute("""
            SELECT COUNT(*) FROM page_views WHERE timestamp >= datetime('now', ?)
        """, (since,))
        total_page_views = cursor.fetchone()[0]

        conn.close()

        return {
            "period_days": days,
            "total_queries": total_queries,
            "unique_sessions": unique_sessions,
            "avg_response_time_ms": round(avg_response_time) if avg_response_time else None,
            "total_page_views": total_page_views,
            "queries_by_day": queries_by_day,
            "top_citations": top_citations
        }


    def get_sessions(self, limit: int = 100, days: int = 30) -> List[Dict]:
        """Get recent sessions with IP addresses."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                session_id,
                datetime(first_seen, 'localtime') as first_seen,
                datetime(last_seen, 'localtime') as last_seen,
                query_count,
                user_agent,
                ip_address
            FROM sessions
            WHERE first_seen >= datetime('now', ?)
            ORDER BY last_seen DESC
            LIMIT ?
        """, (f'-{days} days', limit))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_unique_ips(self, days: int = 30) -> Dict:
        """Get count of unique IP addresses."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        since = f'-{days} days'

        # Unique IPs from sessions
        cursor.execute("""
            SELECT COUNT(DISTINCT ip_address)
            FROM sessions
            WHERE first_seen >= datetime('now', ?) AND ip_address IS NOT NULL
        """, (since,))
        unique_ips = cursor.fetchone()[0]

        # IP breakdown
        cursor.execute("""
            SELECT
                ip_address,
                COUNT(*) as session_count,
                SUM(query_count) as total_queries
            FROM sessions
            WHERE first_seen >= datetime('now', ?) AND ip_address IS NOT NULL
            GROUP BY ip_address
            ORDER BY total_queries DESC
        """, (since,))
        ip_breakdown = [{"ip": row[0], "sessions": row[1], "queries": row[2]} for row in cursor.fetchall()]

        conn.close()

        return {
            "unique_ips": unique_ips,
            "ip_breakdown": ip_breakdown
        }


# Global analytics instance
analytics = Analytics()
