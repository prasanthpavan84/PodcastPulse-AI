# PodcastPulse AI

PodcastPulse AI is a local-first, editorial AI agent platform designed to discover high-interest podcast/video discussions, analyze popularity and semantic opportunities, transform permitted source material into original short-form content, and prepare approved vertical Shorts (9:16) for YouTube publishing.

## Architectural Layers

1. **Intelligence Layer**: Provider interfaces for LLM inference (Ollama), Whisper transcription, embeddings, and ranking models.
2. **Domain & Business Layer**: Canonical workflow state machine, deterministic rights rules engine, idempotency gates, and human approval verification.
3. **Execution & Infrastructure Layer**: MySQL 8 relational database (SQLAlchemy 2, Alembic), local filesystem storage, FFmpeg rendering adapter, TTS adapter, and YouTube API client.

## Quick Start (Phase 0/1)

### 1. Environment Setup

Ensure Python 3.11+, uv, and MySQL 8 are installed.

```powershell
# Create venv and install dependencies
uv venv .venv
uv pip install -e ".[dev]"
```

### 2. Database Configuration

Copy `.env.example` to `.env` and configure your MySQL 8 credentials:

```powershell
cp .env.example .env
```

Run database migrations:

```powershell
uv run alembic upgrade head
```

### 3. Run Verification & Tests

```powershell
# Unit and integration tests
uv run pytest -v

# Lint check
uv run ruff check .
```

### 4. Run API and Streamlit

```powershell
# FastAPI
uv run uvicorn app.api.main:app --host 127.0.0.1 --port 8000

# Streamlit UI
uv run streamlit run app/ui/streamlit_app.py --server.headless true
```
