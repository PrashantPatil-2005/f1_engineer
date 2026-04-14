"""
F1 AI Race Engineer — Flask App Factory

Creates and configures the Flask application with CORS.
Serves the React frontend in production mode.

Usage:
    python -m app.server
"""

import logging
from pathlib import Path

from flask import Flask, send_from_directory
from flask_cors import CORS

from config import config

# ──────────────────────────────────────────────
# Configure logging
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Path to built frontend (production) at repo root
_FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


def create_app() -> Flask:
    """
    Flask application factory.

    Sets up CORS, registers blueprints, validates config.
    In production, serves the React frontend from frontend/dist/.
    """
    app = Flask(__name__)

    # ── CORS — allow frontend (React dev server) ──
    CORS(app, resources={
        r"/api/*": {
            "origins": ["http://localhost:5173", "http://localhost:3000", "*"],
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type"],
        }
    })

    # ── Validate config on startup ──
    try:
        config.validate()
        logger.info("Configuration validated successfully.")
    except OSError as e:
        logger.error(f"Configuration error: {e}")
        # Don't crash — allow health endpoint to report the error
        app.config["CONFIG_ERROR"] = str(e)

    # ── Register blueprints ──
    from app.routes import api_bp
    app.register_blueprint(api_bp, url_prefix="/api")

    # ── Serve React frontend in production ──
    if _FRONTEND_DIST.exists():
        logger.info(f"Serving frontend from {_FRONTEND_DIST}")

        @app.route("/", defaults={"path": ""})
        @app.route("/<path:path>")
        def serve_frontend(path):
            """Serve React SPA — fall back to index.html for client-side routing."""
            file_path = _FRONTEND_DIST / path
            if path and file_path.exists():
                return send_from_directory(str(_FRONTEND_DIST), path)
            return send_from_directory(str(_FRONTEND_DIST), "index.html")
    else:
        logger.info("No frontend/dist found — API-only mode (use Vite dev server)")

    logger.info(
        f"F1 AI Race Engineer started on {config.FLASK_HOST}:{config.FLASK_PORT}"
    )

    return app


# ──────────────────────────────────────────────
# Run directly: python -m app.server
# ──────────────────────────────────────────────
if __name__ == "__main__":
    app = create_app()
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG,
    )
