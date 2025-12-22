"""
Resource Guard Middleware - Prevents crashes from memory exhaustion.

On limited memory VMs (like GCP e2-micro with 1GB RAM), this middleware:
- Monitors available memory before processing requests
- Returns 503 "Server Busy" when memory is critically low
- Protects heavy endpoints (chat, vision, SQL) from crashing the server

Usage:
    from middleware.resource_guard import resource_guard

    @app.before_request
    def check_resources():
        return resource_guard()
"""

import psutil
import logging
from flask import request, jsonify
from functools import wraps

logger = logging.getLogger(__name__)

# Configuration - tuned for GCP e2-micro (1GB RAM, ~130MB typically available)
MEMORY_THRESHOLD_PERCENT = 92  # Return 503 if memory usage > 92%
MEMORY_THRESHOLD_MB = 80       # Return 503 if available memory < 80MB

# Heavy endpoints that need protection
PROTECTED_ENDPOINTS = [
    '/api/chat',
    '/api/vision',
    '/api/sql/query',
    '/api/sql/upload',
    '/api/convert',
    '/api/rag/chat',
]


def get_memory_status():
    """Get current memory usage status."""
    try:
        mem = psutil.virtual_memory()
        return {
            'percent_used': mem.percent,
            'available_mb': mem.available / (1024 * 1024),
            'total_mb': mem.total / (1024 * 1024),
            'is_critical': (
                mem.percent > MEMORY_THRESHOLD_PERCENT or
                mem.available < MEMORY_THRESHOLD_MB * 1024 * 1024
            )
        }
    except Exception as e:
        logger.warning(f"Failed to get memory status: {e}")
        return {'is_critical': False, 'percent_used': 0, 'available_mb': 1000}


def resource_guard():
    """
    Before-request handler that checks resource availability.

    Returns:
        None if resources are OK, or 503 response if server is overloaded
    """
    # Only check protected endpoints
    path = request.path
    is_protected = any(path.startswith(ep) for ep in PROTECTED_ENDPOINTS)

    if not is_protected:
        return None

    mem_status = get_memory_status()

    if mem_status['is_critical']:
        logger.warning(
            f"Resource guard triggered: {mem_status['percent_used']:.1f}% memory used, "
            f"{mem_status['available_mb']:.0f}MB available. Rejecting {path}"
        )
        return jsonify({
            'error': 'Server is busy. Please try again in a moment.',
            'error_type': 'resource_limit',
            'retry_after': 30,
            'details': {
                'memory_percent': round(mem_status['percent_used'], 1),
                'available_mb': round(mem_status['available_mb'], 0)
            }
        }), 503

    return None


def require_resources(f):
    """
    Decorator for individual routes that need resource protection.

    Usage:
        @app.route('/api/heavy-task')
        @require_resources
        def heavy_task():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        mem_status = get_memory_status()

        if mem_status['is_critical']:
            logger.warning(
                f"Resource guard (decorator): {mem_status['percent_used']:.1f}% memory, "
                f"rejecting {request.path}"
            )
            return jsonify({
                'error': 'Server is busy. Please try again in a moment.',
                'error_type': 'resource_limit',
                'retry_after': 30
            }), 503

        return f(*args, **kwargs)
    return decorated_function
