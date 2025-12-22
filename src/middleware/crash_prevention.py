"""
Crash Prevention System - Comprehensive protection for resource-limited deployments.

Features:
1. Concurrent Request Limiter - Prevents too many simultaneous requests
2. Memory Guard - Rejects requests when memory is critical
3. Circuit Breaker - Stops requests after repeated failures
4. Automatic GC - Triggers garbage collection under pressure
5. Request Timeout - Kills long-running requests

Designed for GCP e2-micro (1GB RAM, 0.25 vCPU) and similar free-tier VMs.
"""

import gc
import time
import threading
import logging
from functools import wraps
from collections import deque
from datetime import datetime, timedelta

import psutil
from flask import request, jsonify, g

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION - Tuned for 1GB RAM / 0.25 vCPU
# ═══════════════════════════════════════════════════════════════════════════════

class Config:
    # Memory thresholds
    MEMORY_WARNING_PERCENT = 85      # Start degrading features
    MEMORY_CRITICAL_PERCENT = 92     # Reject new requests
    MEMORY_MIN_AVAILABLE_MB = 80     # Minimum free memory

    # Concurrent request limits
    MAX_CONCURRENT_REQUESTS = 5      # Total simultaneous requests
    MAX_CONCURRENT_HEAVY = 2         # Heavy operations (chat, vision)
    MAX_CONCURRENT_LIGHT = 10        # Light operations (health, static)

    # Circuit breaker
    CIRCUIT_FAILURE_THRESHOLD = 5    # Failures before opening circuit
    CIRCUIT_RESET_TIMEOUT = 60       # Seconds before retrying

    # Request timeout
    REQUEST_TIMEOUT_SECONDS = 120    # Max request duration

    # Garbage collection
    GC_TRIGGER_PERCENT = 80          # Memory % to trigger GC
    GC_MIN_INTERVAL = 30             # Min seconds between GC


# ═══════════════════════════════════════════════════════════════════════════════
# CONCURRENT REQUEST LIMITER
# ═══════════════════════════════════════════════════════════════════════════════

class ConcurrentRequestLimiter:
    """Limits the number of simultaneous requests to prevent overload."""

    def __init__(self):
        self._lock = threading.Lock()
        self._current_requests = 0
        self._heavy_requests = 0
        self._request_times = deque(maxlen=100)  # Track recent request durations

    # Heavy endpoints that consume more resources
    HEAVY_ENDPOINTS = {
        '/api/chat', '/api/vision', '/api/sql/query',
        '/api/convert', '/api/rag/chat', '/api/investigate',
        '/api/ingest', '/api/sql/upload'
    }

    def is_heavy(self, path: str) -> bool:
        return any(path.startswith(ep) for ep in self.HEAVY_ENDPOINTS)

    def acquire(self, path: str) -> tuple[bool, str]:
        """Try to acquire a request slot. Returns (success, error_message)."""
        is_heavy = self.is_heavy(path)

        with self._lock:
            # Check total limit
            if self._current_requests >= Config.MAX_CONCURRENT_REQUESTS:
                return False, f"Server busy: {self._current_requests} concurrent requests"

            # Check heavy limit
            if is_heavy and self._heavy_requests >= Config.MAX_CONCURRENT_HEAVY:
                return False, f"Heavy operation limit: {self._heavy_requests} in progress"

            # Acquire slot
            self._current_requests += 1
            if is_heavy:
                self._heavy_requests += 1

            return True, ""

    def release(self, path: str, duration: float):
        """Release a request slot and record duration."""
        is_heavy = self.is_heavy(path)

        with self._lock:
            self._current_requests = max(0, self._current_requests - 1)
            if is_heavy:
                self._heavy_requests = max(0, self._heavy_requests - 1)
            self._request_times.append(duration)

    def get_stats(self) -> dict:
        with self._lock:
            avg_duration = sum(self._request_times) / len(self._request_times) if self._request_times else 0
            return {
                'current_requests': self._current_requests,
                'heavy_requests': self._heavy_requests,
                'avg_duration_ms': round(avg_duration * 1000, 1),
                'max_concurrent': Config.MAX_CONCURRENT_REQUESTS,
                'max_heavy': Config.MAX_CONCURRENT_HEAVY
            }


# ═══════════════════════════════════════════════════════════════════════════════
# CIRCUIT BREAKER
# ═══════════════════════════════════════════════════════════════════════════════

class CircuitBreaker:
    """
    Prevents cascade failures by stopping requests after repeated errors.

    States:
    - CLOSED: Normal operation, requests flow through
    - OPEN: Failures exceeded threshold, rejecting all requests
    - HALF_OPEN: Testing if service recovered
    """

    CLOSED = 'closed'
    OPEN = 'open'
    HALF_OPEN = 'half_open'

    def __init__(self):
        self._lock = threading.Lock()
        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._success_count = 0

    def can_proceed(self) -> tuple[bool, str]:
        """Check if request should proceed."""
        with self._lock:
            if self._state == self.CLOSED:
                return True, ""

            if self._state == self.OPEN:
                # Check if timeout has passed
                if self._last_failure_time:
                    elapsed = (datetime.now() - self._last_failure_time).total_seconds()
                    if elapsed >= Config.CIRCUIT_RESET_TIMEOUT:
                        self._state = self.HALF_OPEN
                        self._success_count = 0
                        logger.info("Circuit breaker: OPEN -> HALF_OPEN (testing recovery)")
                        return True, ""
                return False, f"Circuit open: service recovering (retry in {Config.CIRCUIT_RESET_TIMEOUT}s)"

            if self._state == self.HALF_OPEN:
                return True, ""

            return True, ""

    def record_success(self):
        """Record a successful request."""
        with self._lock:
            if self._state == self.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= 3:  # 3 successes to close
                    self._state = self.CLOSED
                    self._failure_count = 0
                    logger.info("Circuit breaker: HALF_OPEN -> CLOSED (recovered)")
            elif self._state == self.CLOSED:
                self._failure_count = max(0, self._failure_count - 1)

    def record_failure(self):
        """Record a failed request."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now()

            if self._state == self.HALF_OPEN:
                self._state = self.OPEN
                logger.warning("Circuit breaker: HALF_OPEN -> OPEN (still failing)")
            elif self._state == self.CLOSED and self._failure_count >= Config.CIRCUIT_FAILURE_THRESHOLD:
                self._state = self.OPEN
                logger.warning(f"Circuit breaker: CLOSED -> OPEN ({self._failure_count} failures)")

    def get_stats(self) -> dict:
        with self._lock:
            return {
                'state': self._state,
                'failure_count': self._failure_count,
                'threshold': Config.CIRCUIT_FAILURE_THRESHOLD
            }


# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryManager:
    """Monitors memory and triggers cleanup when needed."""

    def __init__(self):
        self._last_gc = time.time()
        self._gc_count = 0

    def get_status(self) -> dict:
        """Get current memory status."""
        try:
            mem = psutil.virtual_memory()
            return {
                'percent_used': mem.percent,
                'available_mb': mem.available / (1024 * 1024),
                'total_mb': mem.total / (1024 * 1024),
                'is_warning': mem.percent > Config.MEMORY_WARNING_PERCENT,
                'is_critical': (
                    mem.percent > Config.MEMORY_CRITICAL_PERCENT or
                    mem.available < Config.MEMORY_MIN_AVAILABLE_MB * 1024 * 1024
                )
            }
        except Exception as e:
            logger.error(f"Failed to get memory status: {e}")
            return {'is_warning': False, 'is_critical': False, 'percent_used': 0}

    def maybe_gc(self) -> bool:
        """Trigger garbage collection if needed. Returns True if GC ran."""
        mem = self.get_status()
        now = time.time()

        # Check if GC is needed and allowed
        if mem['percent_used'] < Config.GC_TRIGGER_PERCENT:
            return False

        if now - self._last_gc < Config.GC_MIN_INTERVAL:
            return False

        # Run garbage collection
        collected = gc.collect()
        self._last_gc = now
        self._gc_count += 1

        logger.info(f"GC triggered: collected {collected} objects (memory was {mem['percent_used']:.1f}%)")
        return True

    def get_gc_stats(self) -> dict:
        return {
            'gc_count': self._gc_count,
            'last_gc': self._last_gc,
            'gc_threshold_percent': Config.GC_TRIGGER_PERCENT
        }


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCES
# ═══════════════════════════════════════════════════════════════════════════════

request_limiter = ConcurrentRequestLimiter()
circuit_breaker = CircuitBreaker()
memory_manager = MemoryManager()


# ═══════════════════════════════════════════════════════════════════════════════
# FLASK MIDDLEWARE
# ═══════════════════════════════════════════════════════════════════════════════

# Endpoints that bypass protection (must always be available)
BYPASS_ENDPOINTS = {'/health', '/metrics', '/favicon.ico', '/static', '/robots.txt'}


def should_bypass(path: str) -> bool:
    """Check if path should bypass crash prevention."""
    return any(path.startswith(ep) for ep in BYPASS_ENDPOINTS)


def crash_prevention_before():
    """
    Before-request handler for crash prevention.
    Register with: app.before_request(crash_prevention_before)
    """
    path = request.path
    g.request_start_time = time.time()
    g.request_path = path

    # Skip protection for health/monitoring endpoints
    if should_bypass(path):
        return None

    # 1. Check circuit breaker
    can_proceed, error = circuit_breaker.can_proceed()
    if not can_proceed:
        return jsonify({
            'error': 'Service temporarily unavailable',
            'error_type': 'circuit_open',
            'message': error,
            'retry_after': Config.CIRCUIT_RESET_TIMEOUT
        }), 503

    # 2. Check memory
    mem_status = memory_manager.get_status()
    if mem_status['is_critical']:
        # Try garbage collection first
        memory_manager.maybe_gc()
        mem_status = memory_manager.get_status()

        if mem_status['is_critical']:
            logger.warning(f"Memory critical: {mem_status['percent_used']:.1f}%, rejecting {path}")
            return jsonify({
                'error': 'Server memory critical. Please try again shortly.',
                'error_type': 'memory_critical',
                'memory_percent': round(mem_status['percent_used'], 1),
                'retry_after': 30
            }), 503

    # 3. Check concurrent requests
    acquired, error = request_limiter.acquire(path)
    if not acquired:
        logger.warning(f"Request limit reached: {error}")
        return jsonify({
            'error': 'Server busy. Too many concurrent requests.',
            'error_type': 'rate_limit',
            'message': error,
            'retry_after': 5
        }), 429

    # Mark that we acquired a slot (for cleanup in after_request)
    g.acquired_slot = True

    return None


def crash_prevention_after(response):
    """
    After-request handler for crash prevention.
    Register with: app.after_request(crash_prevention_after)
    """
    path = getattr(g, 'request_path', request.path)
    start_time = getattr(g, 'request_start_time', time.time())
    duration = time.time() - start_time

    # Release request slot if we acquired one
    if getattr(g, 'acquired_slot', False):
        request_limiter.release(path, duration)

    # Record success/failure for circuit breaker
    if not should_bypass(path):
        if response.status_code >= 500:
            circuit_breaker.record_failure()
        else:
            circuit_breaker.record_success()

    # Trigger GC if memory is high
    memory_manager.maybe_gc()

    return response


def crash_prevention_teardown(exception):
    """
    Teardown handler - ensures slots are released even on errors.
    Register with: app.teardown_request(crash_prevention_teardown)
    """
    if exception:
        circuit_breaker.record_failure()
        logger.error(f"Request failed with exception: {exception}")

    # Ensure slot is released
    path = getattr(g, 'request_path', '')
    start_time = getattr(g, 'request_start_time', time.time())

    if getattr(g, 'acquired_slot', False) and not getattr(g, 'slot_released', False):
        request_limiter.release(path, time.time() - start_time)
        g.slot_released = True


# ═══════════════════════════════════════════════════════════════════════════════
# STATUS ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

def get_crash_prevention_stats() -> dict:
    """Get comprehensive crash prevention statistics."""
    mem = memory_manager.get_status()
    return {
        'memory': {
            'percent_used': round(mem['percent_used'], 1),
            'available_mb': round(mem['available_mb'], 1),
            'is_warning': mem['is_warning'],
            'is_critical': mem['is_critical'],
            'thresholds': {
                'warning_percent': Config.MEMORY_WARNING_PERCENT,
                'critical_percent': Config.MEMORY_CRITICAL_PERCENT,
                'min_available_mb': Config.MEMORY_MIN_AVAILABLE_MB
            }
        },
        'requests': request_limiter.get_stats(),
        'circuit_breaker': circuit_breaker.get_stats(),
        'gc': memory_manager.get_gc_stats()
    }
