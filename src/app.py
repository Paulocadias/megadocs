"""
Flask application for document to Markdown conversion.
Refactored into modular components.
"""

__version__ = "3.0.0"

import os
import logging
from flask import Flask, jsonify
from config import Config

from logger import setup_logger
from middleware.crash_prevention import (
    crash_prevention_before,
    crash_prevention_after,
    crash_prevention_teardown,
    get_crash_prevention_stats
)

def create_app():
    """Application factory."""
    app = Flask(__name__, template_folder="templates", static_folder="../static")
    app.config.from_object(Config)

    # Initialize structured logging
    setup_logger(app)

    # Register crash prevention middleware (comprehensive protection)
    app.before_request(crash_prevention_before)
    app.after_request(crash_prevention_after)
    app.teardown_request(crash_prevention_teardown)

    # Crash prevention status endpoint
    @app.route('/api/system/status')
    def system_status():
        """Get system resource status for monitoring."""
        return jsonify(get_crash_prevention_stats())

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
    app.run(debug=debug_mode, host="0.0.0.0", port=8080)
