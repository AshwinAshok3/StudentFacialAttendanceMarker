"""
app.py — Flask application entry point for the Facial Attendance System.

Creates the Flask app, registers routes, serves frontend static files,
initialises the database and recognition model on startup.
"""

import os
import sys

# ---------------------------------------------------------------------------
# Ensure backend/ is on the Python path
# ---------------------------------------------------------------------------
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from flask import Flask, send_from_directory
from flask_cors import CORS

from config import (
    SECRET_KEY, HOST, PORT, DEBUG,
    FRONTEND_DIR, DEFAULT_ADMIN_EMAIL, DEFAULT_ADMIN_PASSWORD
)
from database import init_db, get_user_by_email, add_user, seed_default_courses
from auth import hash_password
from recognition import init_model
from routes import api
from utils import format_system_summary


# ---------------------------------------------------------------------------
# App Factory
# ---------------------------------------------------------------------------

def create_app():
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        static_folder=FRONTEND_DIR,
        static_url_path="",
    )
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024   # 50 MB max request

    # Enable CORS for all routes (needed when frontend served separately)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Register API blueprint
    app.register_blueprint(api)

    # -----------------------------------------------------------------------
    # Static file serving — frontend pages
    # -----------------------------------------------------------------------
    @app.route("/")
    def serve_index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.route("/<path:path>")
    def serve_static(path):
        """Serve any static file from the frontend directory."""
        file_path = os.path.join(FRONTEND_DIR, path)
        if os.path.isfile(file_path):
            return send_from_directory(FRONTEND_DIR, path)
        # Fallback to index.html for SPA-style routing
        return send_from_directory(FRONTEND_DIR, "index.html")

    return app


# ---------------------------------------------------------------------------
# Startup Initialization
# ---------------------------------------------------------------------------

def initialize():
    """Run once at startup: database, admin account, model."""

    # 1. Initialize database schema
    print("[Startup] Initializing database...")
    init_db()

    # 2. Seed default admin account
    if not get_user_by_email(DEFAULT_ADMIN_EMAIL):
        print(f"[Startup] Creating default admin: {DEFAULT_ADMIN_EMAIL}")
        pw_hash = hash_password(DEFAULT_ADMIN_PASSWORD)
        add_user("System Admin", DEFAULT_ADMIN_EMAIL, "Administration",
                 "admin", pw_hash)

    # 3. Seed default courses
    seed_default_courses()

    # 4. Initialize InsightFace model
    print("[Startup] Loading face recognition model...")
    model_ok = init_model()
    if not model_ok:
        print("[Startup] WARNING: Face recognition model not loaded!")
        print("[Startup] Run setup script to download models.")

    # 5. Print system summary
    print(format_system_summary())


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    initialize()
    app = create_app()

    print(f"\n  Server starting at http://localhost:{PORT}")
    print("  Press Ctrl+C to stop.\n")

    app.run(host=HOST, port=PORT, debug=DEBUG, use_reloader=False)
