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
# Google AI Studio (Gemini) — commented out, migrated to Groq
# ──────────────────────────────────────────────
# GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
# GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
# EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
# EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "3072"))

# ──────────────────────────────────────────────
# Groq LLM
# ──────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# ──────────────────────────────────────────────
# Local Embeddings (sentence-transformers, runs on CPU, no API cost)
# ──────────────────────────────────────────────
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIMENSIONS = 384  # all-MiniLM-L6-v2 fixed output dims — do not change

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
# MCP Server
# ──────────────────────────────────────────────
MCP_SERVER_SCRIPT = _PROJECT_ROOT / "mcp_server" / "server.py"

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
    # if not GOOGLE_API_KEY:
    #     errors.append("GOOGLE_API_KEY is not set. Get one free at https://aistudio.google.com/apikey and add it to .env")
    if not GROQ_API_KEY:
        errors.append("GROQ_API_KEY is not set.")
    if errors:
        raise OSError(
            "Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
        )
