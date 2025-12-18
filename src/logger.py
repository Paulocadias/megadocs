"""
Structured JSON logging configuration for production observability.
Provides consistent log format with request ID correlation.
"""

import logging
import sys
import os
from pythonjsonlogger import jsonlogger
from flask import request, has_request_context
from datetime import datetime

class RequestFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter to include request context."""
    
    def add_fields(self, log_record, record, message_dict):
        super(RequestFormatter, self).add_fields(log_record, record, message_dict)
        
        # Add timestamp
        if not log_record.get('timestamp'):
            now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            log_record['timestamp'] = now
            
        # Add log level
        if log_record.get('level'):
            log_record['level'] = log_record['level'].upper()
        else:
            log_record['level'] = record.levelname
            
        # Add request context if available
        if has_request_context():
            log_record['request_id'] = request.headers.get('X-Request-ID', 'unknown')
            log_record['ip'] = request.headers.get('X-Forwarded-For', request.remote_addr)
            log_record['method'] = request.method
            log_record['path'] = request.path
            log_record['user_agent'] = request.user_agent.string
            
        # Add source location
        log_record['source'] = f"{record.filename}:{record.lineno}"


def setup_logger(app):
    """
    Configure application logger with JSON formatting.
    
    Args:
        app: Flask application instance
    """
    # Remove default handlers
    app.logger.handlers.clear()
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    
    # Configure JSON formatting
    formatter = RequestFormatter(
        '%(timestamp)s %(level)s %(name)s %(message)s'
    )
    handler.setFormatter(formatter)
    
    # Add handler to app logger
    app.logger.addHandler(handler)
    
    # Set log level based on environment
    log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    app.logger.setLevel(log_level)
    
    # Also configure root logger for other libraries
    logging.getLogger().handlers.clear()
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(log_level)
    
    app.logger.info("Structured logging initialized", extra={'version': '2.0.0'})
