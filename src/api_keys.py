"""
API Key management module.
Handles creation, validation, and usage tracking of API keys.
"""

import secrets
import hashlib
from datetime import datetime
from threading import Lock

from stats import _db_connection, _lock


class APIKeyManager:
    """Manages API keys for authenticated access."""

    def __init__(self):
        self._cache = {}  # key_hash -> {rate_limit, is_active}
        self._cache_lock = Lock()

    def generate_key(self, name: str, email: str, rate_limit: int = 100) -> str:
        """
        Generate a new API key.
        Returns the raw API key (only shown once).
        """
        # Generate a secure random key
        raw_key = f"mdc_{secrets.token_urlsafe(32)}"
        key_hash = self._hash_key(raw_key)

        with _lock:
            with _db_connection() as conn:
                conn.execute(
                    '''INSERT INTO api_keys (key_hash, name, email, rate_limit)
                       VALUES (?, ?, ?, ?)''',
                    (key_hash, name, email, rate_limit)
                )

        return raw_key

    def validate_key(self, raw_key: str) -> dict | None:
        """
        Validate an API key and return its info if valid.
        Returns None if key is invalid or inactive.
        """
        if not raw_key or not raw_key.startswith('mdc_'):
            return None

        key_hash = self._hash_key(raw_key)

        # Check cache first
        with self._cache_lock:
            if key_hash in self._cache:
                cached = self._cache[key_hash]
                if cached.get('is_active'):
                    return cached

        # Query database
        with _db_connection() as conn:
            row = conn.execute(
                '''SELECT id, name, email, rate_limit, is_active, total_requests
                   FROM api_keys WHERE key_hash = ?''',
                (key_hash,)
            ).fetchone()

            if row and row['is_active']:
                result = {
                    'id': row['id'],
                    'name': row['name'],
                    'email': row['email'],
                    'rate_limit': row['rate_limit'],
                    'is_active': bool(row['is_active']),
                    'total_requests': row['total_requests']
                }

                # Update cache
                with self._cache_lock:
                    self._cache[key_hash] = result

                return result

        return None

    def record_usage(self, raw_key: str):
        """Record API key usage."""
        if not raw_key:
            return

        key_hash = self._hash_key(raw_key)

        with _lock:
            with _db_connection() as conn:
                conn.execute(
                    '''UPDATE api_keys
                       SET last_used_at = ?, total_requests = total_requests + 1
                       WHERE key_hash = ?''',
                    (datetime.now().isoformat(), key_hash)
                )

    def deactivate_key(self, key_id: int):
        """Deactivate an API key."""
        with _lock:
            with _db_connection() as conn:
                conn.execute(
                    'UPDATE api_keys SET is_active = 0 WHERE id = ?',
                    (key_id,)
                )

        # Clear cache
        self._clear_cache()

    def activate_key(self, key_id: int):
        """Reactivate an API key."""
        with _lock:
            with _db_connection() as conn:
                conn.execute(
                    'UPDATE api_keys SET is_active = 1 WHERE id = ?',
                    (key_id,)
                )

        self._clear_cache()

    def update_rate_limit(self, key_id: int, new_limit: int):
        """Update rate limit for an API key."""
        with _lock:
            with _db_connection() as conn:
                conn.execute(
                    'UPDATE api_keys SET rate_limit = ? WHERE id = ?',
                    (new_limit, key_id)
                )

        self._clear_cache()

    def list_keys(self) -> list:
        """List all API keys (for admin dashboard)."""
        with _db_connection() as conn:
            rows = conn.execute(
                '''SELECT id, name, email, rate_limit, is_active,
                          created_at, last_used_at, total_requests
                   FROM api_keys ORDER BY created_at DESC'''
            ).fetchall()
            return [dict(row) for row in rows]

    def get_key_stats(self, key_id: int) -> dict | None:
        """Get detailed stats for a specific API key."""
        with _db_connection() as conn:
            row = conn.execute(
                '''SELECT id, name, email, rate_limit, is_active,
                          created_at, last_used_at, total_requests
                   FROM api_keys WHERE id = ?''',
                (key_id,)
            ).fetchone()
            return dict(row) if row else None

    def _hash_key(self, raw_key: str) -> str:
        """Hash an API key for storage."""
        return hashlib.sha256(raw_key.encode()).hexdigest()

    def _clear_cache(self):
        """Clear the validation cache."""
        with self._cache_lock:
            self._cache.clear()


# Global API key manager instance
api_keys = APIKeyManager()
