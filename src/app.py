"""
Flask application for document to Markdown conversion.
Refactored into modular components.
"""

import os
import logging
from flask import Flask
from config import Config

# Configure logging
class RequestIdFilter(logging.Filter):
    """Add request ID to log records."""
    def filter(self, record):
        if not hasattr(record, 'request_id'):
            record.request_id = 'SYSTEM'
        return True

# Set up logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create handler with filter
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
handler.addFilter(RequestIdFilter())
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(levelname)s - [%(request_id)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))
# Remove default handlers to avoid duplicates if necessary, or just add this one
logger.addHandler(handler)
logger.propagate = False

def create_app():
    """Application factory."""
    app = Flask(__name__, template_folder="templates", static_folder="../static")
    app.config.from_object(Config)

    # Register Blueprints
    from routes import bp as main_bp
    app.register_blueprint(main_bp)

    return app

app = create_app()

if __name__ == "__main__":
    print("""
    +==============================================================+
    |           DOCS TO MARKDOWN - AUTOMATION PLATFORM             |
    +==============================================================+
    |  Features:                                                   |
    |  - Batch Processing       - Webhook Integration              |
    |  - CLI Automation         - Secure Conversion                |
    +--------------------------------------------------------------+
    """)
    app.run(debug=True, host="127.0.0.1", port=8080)
