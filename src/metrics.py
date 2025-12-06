"""
Prometheus metrics collection for production monitoring.
Provides comprehensive metrics for observability and alerting.
"""

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from functools import wraps
import time

# Request metrics
request_count = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint']
)

# Conversion metrics
conversion_count = Counter(
    'document_conversions_total',
    'Total document conversions',
    ['file_type', 'output_format']
)

conversion_duration = Histogram(
    'document_conversion_duration_seconds',
    'Document conversion latency',
    ['file_type']
)

conversion_size = Histogram(
    'document_conversion_size_bytes',
    'Document size in bytes',
    ['file_type']
)

# Error metrics
error_count = Counter(
    'errors_total',
    'Total errors',
    ['error_type']
)

# Security metrics
rate_limit_hits = Counter(
    'rate_limit_hits_total',
    'Total rate limit hits',
    ['endpoint']
)

blocked_requests = Counter(
    'blocked_requests_total',
    'Total blocked requests',
    ['reason']
)

# System metrics
active_conversions = Gauge(
    'active_conversions',
    'Number of active conversions'
)

# RAG pipeline metrics
rag_chunk_count = Counter(
    'rag_chunks_generated_total',
    'Total RAG chunks generated'
)

rag_embedding_duration = Histogram(
    'rag_embedding_duration_seconds',
    'RAG embedding generation latency'
)


def track_request(f):
    """
    Decorator to track HTTP request metrics.
    
    Usage:
        @track_request
        def my_route():
            ...
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        status = 200
        
        try:
            response = f(*args, **kwargs)
            
            # Extract status code
            if isinstance(response, tuple):
                status = response[1] if len(response) > 1 else 200
            elif hasattr(response, 'status_code'):
                status = response.status_code
            
            return response
        except Exception as e:
            status = 500
            error_count.labels(error_type=type(e).__name__).inc()
            raise
        finally:
            # Record metrics
            duration = time.time() - start_time
            
            # Get endpoint name from function
            endpoint = f.__name__
            method = 'GET'  # Default, can be enhanced
            
            request_count.labels(method=method, endpoint=endpoint, status=status).inc()
            request_duration.labels(method=method, endpoint=endpoint).observe(duration)
    
    return wrapper


def track_conversion(file_type: str, file_size: int, output_format: str = 'markdown'):
    """
    Track conversion metrics.
    
    Args:
        file_type: File extension (e.g., 'pdf', 'docx')
        file_size: File size in bytes
        output_format: Output format ('markdown' or 'text')
    """
    conversion_count.labels(file_type=file_type, output_format=output_format).inc()
    conversion_size.labels(file_type=file_type).observe(file_size)


def track_conversion_duration(file_type: str, duration: float):
    """
    Track conversion duration.
    
    Args:
        file_type: File extension
        duration: Duration in seconds
    """
    conversion_duration.labels(file_type=file_type).observe(duration)


def track_error(error_type: str):
    """
    Track error occurrence.
    
    Args:
        error_type: Type of error (e.g., 'ValidationError', 'ConversionError')
    """
    error_count.labels(error_type=error_type).inc()


def track_rate_limit(endpoint: str):
    """
    Track rate limit hit.
    
    Args:
        endpoint: Endpoint that was rate limited
    """
    rate_limit_hits.labels(endpoint=endpoint).inc()


def track_blocked_request(reason: str):
    """
    Track blocked request.
    
    Args:
        reason: Reason for blocking (e.g., 'abuse', 'invalid_file')
    """
    blocked_requests.labels(reason=reason).inc()


def track_rag_chunks(count: int):
    """
    Track RAG chunk generation.
    
    Args:
        count: Number of chunks generated
    """
    rag_chunk_count.inc(count)


def track_rag_embedding_duration(duration: float):
    """
    Track RAG embedding generation duration.
    
    Args:
        duration: Duration in seconds
    """
    rag_embedding_duration.observe(duration)


def get_metrics():
    """
    Get Prometheus metrics in text format.
    
    Returns:
        tuple: (metrics_text, content_type)
    """
    return generate_latest(), CONTENT_TYPE_LATEST
