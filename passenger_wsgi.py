"""Passenger WSGI entry point for DreamHost deployment."""

import sys
import os

# Add the src directory to Python path
INTERP = os.path.expanduser("~/paulocadias.com/venv/bin/python3")
if sys.executable != INTERP:
    os.execl(INTERP, INTERP, *sys.argv)

# Add src to path
sys.path.insert(0, os.path.expanduser("~/paulocadias.com/src"))

# Load environment variables from .env if exists
from dotenv import load_dotenv
load_dotenv(os.path.expanduser("~/paulocadias.com/.env"))

# Import the Flask app
from app import app as application
