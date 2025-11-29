"""
Application configuration.
"""
import os


class Config:
    """Flask application configuration."""

    # Flask settings
    SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(32).hex())
    
    # Security settings
    SESSION_COOKIE_SECURE = True  # Require HTTPS
    SESSION_COOKIE_HTTPONLY = True  # Prevent XSS access to cookies
    SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF protection

    # File upload settings
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_FILE_SIZE", 50 * 1024 * 1024))  # 50MB default

    ALLOWED_EXTENSIONS = {
        ".pdf", ".docx", ".doc", ".txt",
        ".xlsx", ".xls", ".csv",
        ".pptx", ".ppt",
        ".jpg", ".jpeg", ".png", ".gif", ".bmp",
        ".html", ".htm", ".json", ".xml",
        ".epub", ".zip"
    }

    # Rate limiting
    RATE_LIMIT_REQUESTS = int(os.environ.get("RATE_LIMIT_REQUESTS", 20))
    RATE_LIMIT_WINDOW = int(os.environ.get("RATE_LIMIT_WINDOW", 60))  # seconds

    # Abuse prevention
    ABUSE_THRESHOLD = int(os.environ.get("ABUSE_THRESHOLD", 100))
    ABUSE_BLOCK_DURATION = int(os.environ.get("ABUSE_BLOCK_DURATION", 3600))  # 1 hour

    # Concurrency control
    MAX_CONCURRENT_CONVERSIONS = int(os.environ.get("MAX_CONCURRENT", 10))

    # Admin authentication
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")  # CHANGE IN PRODUCTION!

    # Magic bytes for file validation
    MAGIC_BYTES = {
        b'\x25\x50\x44\x46': {'.pdf'},                          # PDF
        b'\x50\x4b\x03\x04': {'.docx', '.xlsx', '.pptx', '.zip', '.epub'},  # ZIP-based formats
        b'\xd0\xcf\x11\xe0': {'.doc', '.xls', '.ppt'},          # MS Office legacy
        b'\xff\xd8\xff': {'.jpg', '.jpeg'},                     # JPEG
        b'\x89\x50\x4e\x47': {'.png'},                          # PNG
        b'\x47\x49\x46\x38': {'.gif'},                          # GIF
        b'\x42\x4d': {'.bmp'},                                  # BMP
        b'<!DOCTYPE': {'.html', '.htm'},                        # HTML
        b'<html': {'.html', '.htm'},                            # HTML
        b'<?xml': {'.xml'},                                     # XML
        b'{': {'.json'},                                        # JSON
        b'[': {'.json'},                                        # JSON array
    }
