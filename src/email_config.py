# Email Configuration - Brevo Free SMTP (300 emails/day)
# Uses environment variables for security - DO NOT commit credentials to GitHub!

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env with override to ensure file values take precedence
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path, override=True)

CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "")  # Set via environment variable
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp-relay.brevo.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")  # Set via environment variable
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")  # Set via environment variable
SMTP_SENDER = os.environ.get("SMTP_SENDER", CONTACT_EMAIL)  # Verified sender email in Brevo

# For local development, create a .env file (NOT committed to git):
# CONTACT_EMAIL=your-email@example.com
# SMTP_SERVER=smtp-relay.brevo.com
# SMTP_PORT=587
# SMTP_USERNAME=your-brevo-login@example.com
# SMTP_PASSWORD=xsmtpsib-your-key-here

# For GCP deployment, set these as environment variables in your app.yaml or Cloud Run
