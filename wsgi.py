"""Production WSGI entrypoint.

Run with a real WSGI server, e.g.:

    SECRET_KEY=... FLASK_ENV=production gunicorn wsgi:app

Importing this module builds the application (and seeds the database on first
run). app.py deliberately does NOT build the app at import time so that
importing the factory for tests has no side effects.
"""
from app import create_app

app = create_app()
