"""
Flask application for document to Markdown conversion.
Refactored into modular components.
"""

__version__ = "2.0.0"

import os
import logging
from flask import Flask
from config import Config

from logger import setup_logger
from middleware.resource_guard import resource_guard

def create_app():
    """Application factory."""
    app = Flask(__name__, template_folder="templates", static_folder="../static")
    app.config.from_object(Config)

    # Initialize structured logging
    setup_logger(app)

    # Register resource guard middleware (prevents crashes on low memory)
    @app.before_request
    def check_resources():
        return resource_guard()

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
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug_mode, host="127.0.0.1", port=8080)
