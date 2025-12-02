"""
Statistics and monitoring module for document converter.
Uses SQLite for persistent storage.
"""

import sqlite3
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from contextlib import contextmanager

# Database file path
DB_PATH = Path(__file__).parent.parent / "data" / "stats.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Thread lock for database operations
_lock = Lock()


def _get_connection():
    """Get a database connection."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def _db_connection():
    """Context manager for database connections."""
    conn = _get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _init_db():
    """Initialize the database schema."""
    with _db_connection() as conn:
        cursor = conn.cursor()

        # Conversions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                ip_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Errors table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                error_type TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Security events table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS security_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                ip_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Service info table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS service_info (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')

        # Contact requests table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contact_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                company TEXT,
                use_case TEXT NOT NULL,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Capacity exceeded events table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS capacity_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_hash TEXT NOT NULL,
                active_count INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Document analysis table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analyze_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # RAG chunking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chunk_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_hash TEXT NOT NULL,
                chunks_generated INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Document comparison table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS compare_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # API keys table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_hash TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                rate_limit INTEGER DEFAULT 100,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP,
                total_requests INTEGER DEFAULT 0
            )
        ''')

        # Set service start time if not exists
        cursor.execute('''
            INSERT OR IGNORE INTO service_info (key, value)
            VALUES ('started_at', ?)
        ''', (datetime.now().isoformat(),))

        # Create indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversions_created ON conversions(created_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_conversions_type ON conversions(file_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_security_created ON security_events(created_at)')

        # Migration: Add error_type and error_message columns if they don't exist
        try:
            cursor.execute('SELECT error_type FROM errors LIMIT 1')
        except sqlite3.OperationalError:
            cursor.execute('ALTER TABLE errors ADD COLUMN error_type TEXT')
            cursor.execute('ALTER TABLE errors ADD COLUMN error_message TEXT')


# Initialize database on module load
_init_db()


class Statistics:
    """Statistics manager using SQLite."""

    def __init__(self):
        pass

    def record_conversion(self, file_type: str, file_size: int, ip: str):
        """Record a successful conversion."""
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
        with _lock:
            with _db_connection() as conn:
                conn.execute(
                    'INSERT INTO conversions (file_type, file_size, ip_hash) VALUES (?, ?, ?)',
                    (file_type, file_size, ip_hash)
                )

    def record_error(self, error_type: str = "unknown", error_message: str = None):
        """Record a conversion error with details.

        Args:
            error_type: Category of error (e.g., 'conversion', 'analysis', 'chunking')
            error_message: Detailed error message (truncated to 500 chars)
        """
        # Truncate message to prevent DB bloat
        if error_message and len(error_message) > 500:
            error_message = error_message[:497] + "..."
        with _lock:
            with _db_connection() as conn:
                conn.execute(
                    'INSERT INTO errors (error_type, error_message) VALUES (?, ?)',
                    (error_type, error_message)
                )

    def record_rate_limit(self, ip: str):
        """Record a rate limit hit."""
        self._add_security_event("rate_limit", ip)

    def record_blocked(self, ip: str, reason: str):
        """Record a blocked request."""
        self._add_security_event(f"blocked:{reason}", ip)

    def _add_security_event(self, event_type: str, ip: str):
        """Add a security event to the log."""
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:8]
        with _lock:
            with _db_connection() as conn:
                conn.execute(
                    'INSERT INTO security_events (event_type, ip_hash) VALUES (?, ?)',
                    (event_type, ip_hash)
                )

    def record_contact_request(self, name: str, email: str, company: str, use_case: str, message: str):
        """Record a contact form submission."""
        with _lock:
            with _db_connection() as conn:
                conn.execute(
                    '''INSERT INTO contact_requests (name, email, company, use_case, message)
                       VALUES (?, ?, ?, ?, ?)''',
                    (name, email, company, use_case, message)
                )

    def record_capacity_exceeded(self, ip: str, active_count: int):
        """Record when system is over capacity."""
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
        with _lock:
            with _db_connection() as conn:
                conn.execute(
                    'INSERT INTO capacity_events (ip_hash, active_count) VALUES (?, ?)',
                    (ip_hash, active_count)
                )

    def record_analyze(self, ip: str):
        """Record a document analysis request."""
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
        with _lock:
            with _db_connection() as conn:
                conn.execute(
                    'INSERT INTO analyze_requests (ip_hash) VALUES (?)',
                    (ip_hash,)
                )

    def record_chunk(self, ip: str, chunks_generated: int):
        """Record a RAG chunking request."""
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
        with _lock:
            with _db_connection() as conn:
                conn.execute(
                    'INSERT INTO chunk_requests (ip_hash, chunks_generated) VALUES (?, ?)',
                    (ip_hash, chunks_generated)
                )

    def record_compare(self, ip: str):
        """Record a document comparison request."""
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
        with _lock:
            with _db_connection() as conn:
                conn.execute(
                    'INSERT INTO compare_requests (ip_hash) VALUES (?)',
                    (ip_hash,)
                )

    def get_summary(self):
        """Get statistics summary for dashboard."""
        with _db_connection() as conn:
            cursor = conn.cursor()

            # Total conversions
            total = cursor.execute('SELECT COUNT(*) FROM conversions').fetchone()[0]

            # Today's conversions
            today = datetime.now().strftime("%Y-%m-%d")
            today_count = cursor.execute(
                'SELECT COUNT(*) FROM conversions WHERE DATE(created_at) = ?', (today,)
            ).fetchone()[0]

            # This week's conversions
            week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            week_count = cursor.execute(
                'SELECT COUNT(*) FROM conversions WHERE DATE(created_at) >= ?', (week_ago,)
            ).fetchone()[0]

            # Total bytes processed
            total_bytes = cursor.execute(
                'SELECT COALESCE(SUM(file_size), 0) FROM conversions'
            ).fetchone()[0]

            # Format bytes
            if total_bytes >= 1024 * 1024 * 1024:
                bytes_formatted = f"{total_bytes / (1024**3):.2f} GB"
            elif total_bytes >= 1024 * 1024:
                bytes_formatted = f"{total_bytes / (1024**2):.2f} MB"
            else:
                bytes_formatted = f"{total_bytes / 1024:.2f} KB"

            # Unique users
            unique_users = cursor.execute(
                'SELECT COUNT(DISTINCT ip_hash) FROM conversions'
            ).fetchone()[0]

            # Errors
            errors = cursor.execute('SELECT COUNT(*) FROM errors').fetchone()[0]
            error_rate = f"{(errors / max(total, 1) * 100):.1f}%"

            # Rate limit hits
            rate_limits = cursor.execute(
                "SELECT COUNT(*) FROM security_events WHERE event_type = 'rate_limit'"
            ).fetchone()[0]

            # Blocked requests
            blocked = cursor.execute(
                "SELECT COUNT(*) FROM security_events WHERE event_type LIKE 'blocked:%'"
            ).fetchone()[0]

            # Conversions by type
            type_rows = cursor.execute(
                'SELECT file_type, COUNT(*) as cnt FROM conversions GROUP BY file_type ORDER BY cnt DESC'
            ).fetchall()
            conversions_by_type = {row['file_type']: row['cnt'] for row in type_rows}

            # Conversions by day (last 7 days)
            day_rows = cursor.execute('''
                SELECT DATE(created_at) as day, COUNT(*) as cnt
                FROM conversions
                WHERE DATE(created_at) >= ?
                GROUP BY DATE(created_at)
                ORDER BY day
            ''', (week_ago,)).fetchall()
            conversions_by_day = {row['day']: row['cnt'] for row in day_rows}

            # Conversions by hour
            hour_rows = cursor.execute('''
                SELECT strftime('%H', created_at) as hour, COUNT(*) as cnt
                FROM conversions
                GROUP BY strftime('%H', created_at)
            ''').fetchall()
            conversions_by_hour = {row['hour']: row['cnt'] for row in hour_rows}

            # Last conversion
            last = cursor.execute(
                'SELECT created_at FROM conversions ORDER BY id DESC LIMIT 1'
            ).fetchone()
            last_conversion = last['created_at'] if last else None

            # Service start time
            started = cursor.execute(
                "SELECT value FROM service_info WHERE key = 'started_at'"
            ).fetchone()
            uptime_since = started['value'] if started else None

            # Recent security events
            events = cursor.execute('''
                SELECT event_type as type, ip_hash, created_at as timestamp
                FROM security_events
                ORDER BY id DESC LIMIT 10
            ''').fetchall()
            recent_security_events = [
                {"type": e['type'], "ip_hash": e['ip_hash'], "timestamp": e['timestamp']}
                for e in events
            ]

            # Contact requests count
            contact_count = cursor.execute('SELECT COUNT(*) FROM contact_requests').fetchone()[0]

            # Capacity exceeded count
            try:
                capacity_exceeded = cursor.execute('SELECT COUNT(*) FROM capacity_events').fetchone()[0]
            except Exception:
                capacity_exceeded = 0

            # Analyze requests count
            try:
                analyze_count = cursor.execute('SELECT COUNT(*) FROM analyze_requests').fetchone()[0]
            except Exception:
                analyze_count = 0

            # Chunk requests count and total chunks
            try:
                chunk_count = cursor.execute('SELECT COUNT(*) FROM chunk_requests').fetchone()[0]
                total_chunks = cursor.execute(
                    'SELECT COALESCE(SUM(chunks_generated), 0) FROM chunk_requests'
                ).fetchone()[0]
            except Exception:
                chunk_count = 0
                total_chunks = 0

            # Compare requests count
            try:
                compare_count = cursor.execute('SELECT COUNT(*) FROM compare_requests').fetchone()[0]
            except Exception:
                compare_count = 0

            # Recent errors with details
            try:
                error_rows = cursor.execute('''
                    SELECT id, error_type, error_message, created_at
                    FROM errors
                    ORDER BY id DESC LIMIT 10
                ''').fetchall()
                recent_errors = [
                    {
                        "id": e['id'],
                        "type": e['error_type'] or "unknown",
                        "message": e['error_message'],
                        "timestamp": e['created_at']
                    }
                    for e in error_rows
                ]
                # Errors by type
                error_type_rows = cursor.execute('''
                    SELECT COALESCE(error_type, 'unknown') as etype, COUNT(*) as cnt
                    FROM errors
                    GROUP BY error_type
                    ORDER BY cnt DESC
                ''').fetchall()
                errors_by_type = {row['etype']: row['cnt'] for row in error_type_rows}
            except Exception:
                recent_errors = []
                errors_by_type = {}

            return {
                "total_conversions": total,
                "today_conversions": today_count,
                "week_conversions": week_count,
                "total_data_processed": bytes_formatted,
                "total_bytes": total_bytes,
                "unique_users": unique_users,
                "errors": errors,
                "error_rate": error_rate,
                "rate_limit_hits": rate_limits,
                "blocked_requests": blocked,
                "capacity_exceeded": capacity_exceeded,
                "conversions_by_type": conversions_by_type,
                "conversions_by_day": conversions_by_day,
                "conversions_by_hour": conversions_by_hour,
                "last_conversion": last_conversion,
                "uptime_since": uptime_since,
                "recent_security_events": recent_security_events,
                "contact_requests": contact_count,
                "analyze_requests": analyze_count,
                "chunk_requests": chunk_count,
                "total_chunks_generated": total_chunks,
                "compare_requests": compare_count,
                "recent_errors": recent_errors,
                "errors_by_type": errors_by_type
            }

    def get_api_stats(self):
        """Get API-friendly statistics."""
        summary = self.get_summary()
        
        # Calculate uptime in seconds
        uptime_seconds = 0
        if summary["uptime_since"]:
            try:
                start_time = datetime.fromisoformat(summary["uptime_since"])
                uptime_delta = datetime.now() - start_time
                uptime_seconds = int(uptime_delta.total_seconds())
            except (ValueError, TypeError):
                uptime_seconds = 0
        
        return {
            "success": True,
            "status": "operational",
            "statistics": {
                "conversions": {
                    "total": summary["total_conversions"],
                    "today": summary["today_conversions"],
                    "this_week": summary["week_conversions"],
                    "conversions_by_day": summary["conversions_by_day"]
                },
                "data_processed": {
                    "formatted": summary["total_data_processed"],
                    "bytes": summary["total_bytes"]
                },
                "users": {
                    "unique": summary["unique_users"]
                },
                "reliability": {
                    "errors": summary["errors"],
                    "error_rate": summary["error_rate"],
                    "errors_by_type": summary.get("errors_by_type", {}),
                    "rate_limits": summary["rate_limit_hits"],
                    "blocked": summary["blocked_requests"],
                    "capacity_exceeded": summary["capacity_exceeded"]
                },
                "popular_formats": summary["conversions_by_type"],
                "ai_features": {
                    "analyze_requests": summary.get("analyze_requests", 0),
                    "chunk_requests": summary.get("chunk_requests", 0),
                    "total_chunks_generated": summary.get("total_chunks_generated", 0),
                    "compare_requests": summary.get("compare_requests", 0)
                },
                "contact_requests": summary.get("contact_requests", 0)
            },
            "last_conversion": summary["last_conversion"],
            "service_started": summary["uptime_since"],
            "uptime_seconds": uptime_seconds,
            "recent_security_events": summary["recent_security_events"],
            "recent_errors": summary.get("recent_errors", [])
        }

    def get_contact_requests(self):
        """Get all contact requests for admin view."""
        with _db_connection() as conn:
            rows = conn.execute(
                'SELECT * FROM contact_requests ORDER BY created_at DESC'
            ).fetchall()
            return [dict(row) for row in rows]


# Global statistics instance
stats = Statistics()
