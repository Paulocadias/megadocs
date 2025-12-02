"""
Server-side memory store for RAG pipeline.

Solves the session cookie size limit (~4KB) by storing document content
on the server side instead of in cookies.

For Cloud Run ephemeral deployment:
- Uses in-memory storage (dict)
- Data persists for the lifetime of the container instance
- Automatically cleans up expired sessions

For production with persistence:
- Could be extended to use Redis, Firestore, or GCS
"""
import os
import time
import uuid
import threading
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

# Session expiration time (1 hour)
SESSION_EXPIRY_SECONDS = int(os.environ.get('MEMORY_SESSION_EXPIRY', 3600))

# Maximum items per session
MAX_ITEMS_PER_SESSION = int(os.environ.get('MEMORY_MAX_ITEMS', 10))

# Maximum content size per item (1MB)
MAX_CONTENT_SIZE = int(os.environ.get('MEMORY_MAX_CONTENT_SIZE', 1024 * 1024))


class MemoryStore:
    """
    Server-side memory store for RAG document content.

    Usage:
        store = get_memory_store()

        # Add item
        store.add_item(session_id, filename, content, doc_type, doc_format)

        # Get all items for session
        items = store.get_items(session_id)

        # Clear session
        store.clear_session(session_id)
    """

    def __init__(self):
        """Initialize the memory store."""
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()
        logger.info("MemoryStore initialized (in-memory)")

    def _cleanup_expired(self):
        """Remove expired sessions."""
        current_time = time.time()

        # Only cleanup periodically
        if current_time - self._last_cleanup < self._cleanup_interval:
            return

        self._last_cleanup = current_time
        expired = []

        with self._lock:
            for session_id, data in self._store.items():
                if current_time - data.get('last_access', 0) > SESSION_EXPIRY_SECONDS:
                    expired.append(session_id)

            for session_id in expired:
                del self._store[session_id]
                logger.debug(f"Cleaned up expired session: {session_id[:8]}...")

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")

    def _get_or_create_session(self, session_id: str) -> Dict[str, Any]:
        """Get or create session data structure."""
        if session_id not in self._store:
            self._store[session_id] = {
                'items': [],
                'created_at': time.time(),
                'last_access': time.time()
            }
        else:
            self._store[session_id]['last_access'] = time.time()
        return self._store[session_id]

    def add_item(
        self,
        session_id: str,
        filename: str,
        content: str,
        doc_type: str = 'document',
        doc_format: str = 'markdown',
        image_data_uri: Optional[str] = None
    ) -> bool:
        """
        Add a document to the session memory.

        Args:
            session_id: Unique session identifier
            filename: Original filename
            content: Document content (markdown text)
            doc_type: 'document' or 'image'
            doc_format: Output format ('markdown', 'text', etc.)
            image_data_uri: Optional base64 image data

        Returns:
            True if added successfully, False otherwise
        """
        self._cleanup_expired()

        # Validate content size
        if len(content) > MAX_CONTENT_SIZE:
            logger.warning(f"Content too large: {len(content)} bytes (max: {MAX_CONTENT_SIZE})")
            content = content[:MAX_CONTENT_SIZE]

        with self._lock:
            session_data = self._get_or_create_session(session_id)
            items = session_data['items']

            # Enforce max items limit
            if len(items) >= MAX_ITEMS_PER_SESSION:
                # Remove oldest item
                removed = items.pop(0)
                logger.debug(f"Removed oldest item from session: {removed.get('filename')}")

            # Add new item
            item = {
                'id': str(uuid.uuid4())[:8],
                'filename': filename,
                'content': content,
                'type': doc_type,
                'format': doc_format,
                'added_at': time.time()
            }

            if image_data_uri:
                item['image_data_uri'] = image_data_uri

            items.append(item)
            logger.info(f"Added to memory: {filename} (session: {session_id[:8]}..., total items: {len(items)})")
            return True

    def get_items(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get all items for a session.

        Args:
            session_id: Unique session identifier

        Returns:
            List of memory items (without modifying them)
        """
        self._cleanup_expired()

        with self._lock:
            if session_id not in self._store:
                return []

            self._store[session_id]['last_access'] = time.time()
            return list(self._store[session_id]['items'])

    def get_item_count(self, session_id: str) -> int:
        """Get the number of items in a session."""
        with self._lock:
            if session_id not in self._store:
                return 0
            return len(self._store[session_id]['items'])

    def get_combined_content(self, session_id: str) -> str:
        """
        Get all content combined for RAG context.

        Args:
            session_id: Unique session identifier

        Returns:
            Combined content string with filename headers
        """
        items = self.get_items(session_id)

        if not items:
            return ""

        contexts = []
        for item in items:
            header = f"--- {item['filename']} ({item['type']}) ---"
            contexts.append(f"{header}\n{item['content']}")

        return "\n\n".join(contexts)

    def clear_session(self, session_id: str) -> bool:
        """
        Clear all items from a session.

        Args:
            session_id: Unique session identifier

        Returns:
            True if session existed and was cleared
        """
        with self._lock:
            if session_id in self._store:
                del self._store[session_id]
                logger.info(f"Cleared session: {session_id[:8]}...")
                return True
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get memory store status."""
        with self._lock:
            total_items = sum(len(s['items']) for s in self._store.values())
            total_size = sum(
                len(item.get('content', ''))
                for s in self._store.values()
                for item in s['items']
            )

            return {
                'sessions': len(self._store),
                'total_items': total_items,
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'max_items_per_session': MAX_ITEMS_PER_SESSION,
                'session_expiry_seconds': SESSION_EXPIRY_SECONDS
            }


# Singleton instance
_memory_store: Optional[MemoryStore] = None


def get_memory_store() -> MemoryStore:
    """Get the singleton memory store instance."""
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore()
    return _memory_store
