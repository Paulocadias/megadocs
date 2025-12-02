import os
import time
import uuid
import re
import hashlib
import threading
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from functools import wraps
from flask import request, jsonify, session

from config import Config
from stats import stats

logger = logging.getLogger(__name__)

# =============================================================================
# SECURITY STATE (In-memory - use Redis in production)
# =============================================================================

request_counts = defaultdict(list)  # IP -> [timestamps]
blocked_ips = {}  # IP -> unblock_time
failed_attempts = defaultdict(int)  # IP -> count
request_fingerprints = defaultdict(list)  # For detecting automated attacks

# Concurrency control
active_conversions = 0
conversion_lock = threading.Lock()

# =============================================================================
# SECURITY UTILITIES
# =============================================================================

def check_capacity():
    """Check if system has capacity for new conversion. Returns (allowed, active_count)."""
    with conversion_lock:
        if active_conversions >= Config.MAX_CONCURRENT_CONVERSIONS:
            return False, active_conversions
        return True, active_conversions


def acquire_conversion_slot():
    """Try to acquire a conversion slot. Returns True if successful."""
    global active_conversions
    with conversion_lock:
        if active_conversions >= Config.MAX_CONCURRENT_CONVERSIONS:
            return False
        active_conversions += 1
        return True


def release_conversion_slot():
    """Release a conversion slot."""
    global active_conversions
    with conversion_lock:
        active_conversions = max(0, active_conversions - 1)


def get_active_conversions():
    """Get current number of active conversions."""
    with conversion_lock:
        return active_conversions


def generate_request_id():
    """Generate unique request ID for tracking."""
    return str(uuid.uuid4())[:8].upper()


def get_client_ip():
    """Get real client IP, handling proxies."""
    # Check common proxy headers
    if request.headers.get("X-Forwarded-For"):
        # Take first IP (original client)
        ip = request.headers.get("X-Forwarded-For").split(",")[0].strip()
    elif request.headers.get("X-Real-IP"):
        ip = request.headers.get("X-Real-IP")
    elif request.headers.get("CF-Connecting-IP"):  # Cloudflare
        ip = request.headers.get("CF-Connecting-IP")
    else:
        ip = request.remote_addr or "unknown"

    # Basic IP validation
    if not re.match(r'^[\d.:a-fA-F]+$', ip):
        return "invalid"
    return ip


def get_request_fingerprint():
    """Generate fingerprint for detecting automated requests."""
    components = [
        request.headers.get("User-Agent", ""),
        request.headers.get("Accept-Language", ""),
        request.headers.get("Accept-Encoding", ""),
    ]
    return hashlib.md5("|".join(components).encode(), usedforsecurity=False).hexdigest()[:16]


def is_ip_blocked(ip):
    """Check if IP is currently blocked."""
    if ip in blocked_ips:
        if datetime.now() < blocked_ips[ip]:
            return True
        else:
            # Unblock expired
            del blocked_ips[ip]
    return False


def block_ip(ip, duration_seconds=None):
    """Block an IP address."""
    duration = duration_seconds or Config.ABUSE_BLOCK_DURATION
    blocked_ips[ip] = datetime.now() + timedelta(seconds=duration)
    logger.warning(f"Blocked IP {ip} for {duration} seconds", extra={'request_id': 'SECURITY'})


def check_rate_limit(ip, rate_limit=None):
    """Check and enforce rate limit. Returns (allowed, remaining, reset_time)."""
    current_time = time.time()
    limit = rate_limit or Config.RATE_LIMIT_REQUESTS

    # Clean old requests
    request_counts[ip] = [
        t for t in request_counts[ip]
        if current_time - t < Config.RATE_LIMIT_WINDOW
    ]

    remaining = limit - len(request_counts[ip])
    reset_time = int(Config.RATE_LIMIT_WINDOW - (current_time - request_counts[ip][0])) if request_counts[ip] else Config.RATE_LIMIT_WINDOW

    if remaining <= 0:
        return False, 0, reset_time

    # Record request
    request_counts[ip].append(current_time)
    return True, remaining - 1, reset_time


def validate_api_key(raw_key: str):
    """
    Validate API key and return key info if valid.
    Returns (is_valid, key_info) tuple.
    """
    if not raw_key:
        return False, None

    try:
        from api_keys import api_keys
        key_info = api_keys.validate_key(raw_key)
        if key_info:
            return True, key_info
    except Exception as e:
        logger.warning(f"API key validation error: {e}", extra={'request_id': 'SECURITY'})

    return False, None


def validate_file_magic(file_content, extension):
    """Validate file content matches expected type (magic byte validation)."""
    if len(file_content) < 8:
        return False

    # Check magic bytes
    for magic, extensions in Config.MAGIC_BYTES.items():
        if file_content.startswith(magic):
            if extension.lower() in extensions:
                return True
            # Magic doesn't match extension - suspicious
            return False

    # For text-based files without magic bytes, do basic validation
    text_extensions = {'.txt', '.csv', '.json', '.xml'}
    if extension.lower() in text_extensions:
        try:
            # Check if content is valid UTF-8 text
            file_content[:1000].decode('utf-8')
            return True
        except UnicodeDecodeError:
            return False

    # Unknown format - allow but log
    return True


def check_honeypot(form_data):
    """Check honeypot field - bots often fill hidden fields."""
    honeypot_value = form_data.get('website', '')  # Hidden field
    if honeypot_value:
        return True  # Bot detected
    return False


# =============================================================================
# SECURITY DECORATORS
# =============================================================================

def security_check(f):
    """Comprehensive security decorator with API key support."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        request_id = generate_request_id()
        request.request_id = request_id

        ip = get_client_ip()

        # Check if IP is blocked
        if is_ip_blocked(ip):
            logger.warning(f"Blocked IP attempted access: {ip}", extra={'request_id': request_id})
            stats.record_blocked(ip, "ip_blocked")
            return jsonify({
                "error": "Access temporarily blocked due to suspicious activity. Try again later.",
                "request_id": request_id
            }), 403

        # Check for API key authentication
        api_key = request.headers.get('X-API-Key')
        is_authenticated, key_info = validate_api_key(api_key)
        rate_limit = None
        authenticated_as = None

        if is_authenticated and key_info:
            rate_limit = key_info.get('rate_limit', Config.RATE_LIMIT_REQUESTS)
            authenticated_as = key_info.get('name', 'API User')
            request.api_key_info = key_info

            # Track API key usage
            try:
                from api_keys import api_keys
                api_keys.record_usage(api_key)
            except Exception:
                pass

            logger.info(f"API key authenticated: {authenticated_as}", extra={'request_id': request_id})

        # Check rate limit (use API key rate limit if authenticated)
        allowed, remaining, reset_time = check_rate_limit(ip, rate_limit)
        if not allowed:
            failed_attempts[ip] += 1
            if failed_attempts[ip] >= Config.ABUSE_THRESHOLD:
                block_ip(ip)
                stats.record_blocked(ip, "abuse_threshold")
            stats.record_rate_limit(ip)
            logger.warning(f"Rate limit exceeded for {ip}", extra={'request_id': request_id})
            response = jsonify({
                "error": "Queue Full",
                "message": f"Rate limit exceeded. Try again in {reset_time} seconds.",
                "retry_after": reset_time,
                "request_id": request_id
            })
            response.headers["X-RateLimit-Remaining"] = "0"
            response.headers["X-RateLimit-Reset"] = str(reset_time)
            response.headers["X-RateLimit-Limit"] = str(rate_limit or Config.RATE_LIMIT_REQUESTS)
            response.headers["Retry-After"] = str(reset_time)
            return response, 429

        # Check for honeypot (bot detection) - skip for authenticated API requests
        if not is_authenticated and request.method == "POST" and check_honeypot(request.form):
            logger.warning(f"Honeypot triggered from {ip}", extra={'request_id': request_id})
            failed_attempts[ip] += 10  # Heavy penalty for bot behavior
            return jsonify({"error": "Invalid request"}), 400

        # Log request
        auth_info = f" [API: {authenticated_as}]" if authenticated_as else ""
        logger.info(
            f"Request from {ip}{auth_info} - {request.method} {request.path}",
            extra={'request_id': request_id}
        )

        # Execute request
        response = f(*args, **kwargs)

        # Add security headers to response
        if hasattr(response, 'headers'):
            response.headers["X-Request-ID"] = request_id
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Limit"] = str(rate_limit or Config.RATE_LIMIT_REQUESTS)
            if is_authenticated:
                response.headers["X-Authenticated"] = "true"

        return response

    return decorated_function
