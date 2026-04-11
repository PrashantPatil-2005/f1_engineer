"""
F1 AI Race Engineer — Central Configuration

All modules import from here. Environment variables are loaded from .env,
with sensible defaults for local development.

Uses Google AI Studio (Gemini) — free API key from https://aistudio.google.com/apikey
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ──────────────────────────────────────────────
# Load .env from project root
# ──────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# ──────────────────────────────────────────────
# Google AI Studio (Gemini)
# ──────────────────────────────────────────────
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "3072"))  # gemini-embedding-001 output dim

# ──────────────────────────────────────────────
# Data directories (relative to project root)
# ──────────────────────────────────────────────
DATA_DIR = _PROJECT_ROOT / "data"
FASTF1_CACHE_DIR = DATA_DIR / "cache"
PROCESSED_DIR = DATA_DIR / "processed"
FAISS_DIR = DATA_DIR / "faiss"
METRICS_DIR = DATA_DIR / "metrics"

# Create directories if they don't exist
for _dir in [FASTF1_CACHE_DIR, PROCESSED_DIR, FAISS_DIR, METRICS_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────
# Retrieval settings
# ──────────────────────────────────────────────
TOP_K = 8                    # Number of chunks to retrieve
MAX_CONTEXT_TOKENS = 3000    # Hard token budget for retrieved context

# ──────────────────────────────────────────────
# LLM settings
# ──────────────────────────────────────────────
LLM_TEMPERATURE = 0.3        # Low = factual, high = creative
LLM_MAX_TOKENS = 2048        # Max response tokens

# ──────────────────────────────────────────────
# Flask
# ──────────────────────────────────────────────
FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"

# ──────────────────────────────────────────────
# FastF1
# ──────────────────────────────────────────────
SUPPORTED_YEARS = list(range(2018, 2025))  # 2018–2024 inclusive

SESSION_TYPES = {
    "R": "Race",
    "Q": "Qualifying",
    "S": "Sprint",
    "FP1": "Practice 1",
    "FP2": "Practice 2",
    "FP3": "Practice 3",
}

# ──────────────────────────────────────────────
# Validation
# ──────────────────────────────────────────────
def validate():
    """Check that critical config is present. Call on startup."""
    errors = []
    if not GOOGLE_API_KEY:
        errors.append("GOOGLE_API_KEY is not set. Get one free at https://aistudio.google.com/apikey and add it to .env")
    if errors:
        raise EnvironmentError(
            "Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
        )
