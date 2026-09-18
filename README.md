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

---

## Phase 2: YouTube Discovery & Trend Intelligence

Phase 2 introduces metadata-only YouTube discovery, multi-layer deduplication, rights safety gates, and deterministic popularity scoring (`trend_v1`).

### 1. Configuration & YouTube Data API Requirements

In your `.env` file:
```env
YOUTUBE_API_KEY="your-youtube-data-api-v3-key"
DISCOVERY_MAX_RESULTS=25
DISCOVERY_MAX_QUERIES_PER_RUN=5
```
- **Official API Only**: Uses YouTube Data API v3 (`search` and `videos` endpoints). Scraping or unofficial access is strictly prohibited.
- **Metadata-Only**: No media binaries or streams are acquired during discovery.
- **Quota & Error Behavior**:
  - `quotaExceeded` / `dailyLimitExceeded` → mapped to HTTP 429 (`EXTERNAL_SERVICE_ERROR`)
  - Connection timeouts → mapped to HTTP 504 (retryable)
  - Invalid keys / bad requests → mapped to HTTP 400
  - All logs and error messages strictly scrub credentials and API keys (`***REDACTED***`).

### 2. Multi-Level Deduplication

Repeated discovery of the same YouTube video ID never creates duplicate `sources` records:
1. **Application-Level Check**: Pre-lookup via `SourceRepository.get_by_external_id(session, external_id, platform="youtube")`.
2. **Database Uniqueness Protection**: Relational unique constraint on `sources.external_id` enforced by MySQL 8 and handled via transactional savepoints (`begin_nested()`).

### 3. Rights Safety

Discovered YouTube content is **never** automatically cleared for editorial reuse or publishing:
- Discovered sources are strictly initialized with `workflow_state = DISCOVERED` and `rights_status = REVIEW_REQUIRED`.
- Zero permission, license, fair use, or commercial rights are inferred.

### 4. Deterministic Trend Scoring (`trend_v1`)

Trend prioritization uses explainable mathematical signals without machine learning models or virality predictions:
- **View Velocity**: $\text{views} / \text{age\_hours}$ (hourly momentum)
- **Engagement Rate**: $(\text{likes} + 2 \times \text{comments}) / \max(1, \text{views})$ clamped to 0.25
- **Recency Decay**: $1 / (1 + \text{age\_hours} / 720)$ (smooth 30-day half-life)
- **Composite Score**: $\log_{10}(\max(1, \text{velocity} + 1)) \times 20 \times (1 + 5 \times \text{engagement}) \times \text{recency}$, clamped to $[0.0, 100.0]$.
- **Trend History**: Observation snapshots are persisted in `trend_scores`. Repeated discovery with identical engagement metrics skips redundant trend rows, preserving meaningful time-series trend progression when metrics update.

### 5. API Endpoints

- `POST /api/v1/discovery/youtube`
  - Request body: `topics`, optional `keywords`, `channels`, `min_views`, `published_after_days`, `published_after`, `published_before`, `max_results`, `idempotency_key`.
  - Returns: `job_id`, `status`, `discovered_count`, `new_sources_count`, `existing_sources_count`, `sources`.
- `GET /api/v1/jobs/{job_id}`
  - Retrieves execution state, duration, retry count, error diagnostics, and result metadata for an idempotent job.

### 6. Testing Approach

The automated test suite runs completely decoupled from live external APIs:
- HTTP requests are mocked with synthetic responses in adapter tests.
- MySQL 8 integration tests verify real relational constraints, transactions, and repository queries against the dedicated test database (`podcastpulse_test`).
- No real YouTube API key is required to execute or pass the test suite.

---

## Phase 3: Content Rights Engine

Phase 3 introduces the deterministic, evidence-based **Content Rights Engine** that evaluates reuse rights, gates downstream workflow processing, stores auditable clearance records, and enforces zero-risk copyright policies.

### 1. Deterministic Rights Decision Rules

Content clearance decisions are purely deterministic rules executed in the pure domain layer (`app/domain/rights_rules.py`):

| Source Class | Supported Licenses | Default Decision | Conditions / Evidence Required |
|---|---|---|---|
| `USER_OWNED` | `OWNED` | `APPROVED` | Original creator material. Optional affidavit reference recorded. |
| `COMMERCIAL_LICENSE` | `COMMERCIAL` | `REVIEW_REQUIRED` (unverified) / `APPROVED` (cleared) / `BLOCKED` | Requires invoice/contract reference. Blocked if `commercial_use=False` or `modification_allowed=False`. |
| `CREATIVE_COMMONS` | `CC0` | `APPROVED` | Public domain dedication. Unrestricted reuse. |
| `CREATIVE_COMMONS` | `CC_BY` | `CONDITIONAL` | Requires creator attribution condition. |
| `CREATIVE_COMMONS` | `CC_BY_SA` | `CONDITIONAL` | Requires creator attribution and share-alike conditions. |
| `CREATIVE_COMMONS` | `CC_BY_NC` | `BLOCKED` | Non-commercial restriction blocks commercial short adaptation. |
| `CREATIVE_COMMONS` | `CC_BY_ND` | `BLOCKED` | No-derivatives restriction blocks short adaptation/clipping. |
| `PERMISSION_BASED` | Any | `REVIEW_REQUIRED` (incomplete) / `APPROVED` / `CONDITIONAL` | Requires documented agreement reference AND authorized human reviewer. |
| `UNKNOWN` | `STANDARD_YOUTUBE`, `UNKNOWN` | `REVIEW_REQUIRED` | Hard Rule: Public availability on YouTube never grants reuse rights. |

### 2. Hard Safety Gates & Workflow Enforcement

- **Strict Gating**: Sources with `rights_status != APPROVED` (e.g. `BLOCKED`, `REVIEW_REQUIRED`, `CONDITIONAL`) cannot transition to `TRANSCRIBING`.
- **Canonical Transitions**: Discovery sources start in `DISCOVERED`. Upon rights evaluation, sources transition canonically through `RIGHTS_PENDING` to `RIGHTS_APPROVED` or `RIGHTS_BLOCKED`.
- **Re-evaluation**: Previously blocked sources can transition back to `RIGHTS_PENDING` upon submission of new legal evidence or contracts.
- **Anti-Hallucination Guarantee**: AI models are never permitted to declare legal copyright clearance. Evaluation logic is 100% deterministic code.

### 3. Immutable Audit Logging & Secret Scrubbing

- Every rights evaluation automatically logs an immutable `AuditEvent` (`RIGHTS_EVALUATION_{STATUS}`) recording:
  - Source ID, license type, source class, decision status, reason
  - Structured conditions (e.g. `attribution_required`, `share_alike_required`)
  - Ruleset version and evidence reference
- Sensitive parameters, authorization tokens, passwords, and API keys are automatically redacted (`***REDACTED***`) before persistence.

### 4. API Endpoints

- `POST /api/v1/sources/{source_id}/rights`
  - Submits license evidence, evaluates clearance deterministically, updates source state, and records audit trail.
  - Returns: `source_id`, `rights_status`, `workflow_state`, `source_class`, `license_type`, `attribution_required`, `conditions`, `decision_reason`, `verified_at`, `reviewer`, `ruleset_version`.
- `GET /api/v1/sources/{source_id}/rights`
  - Fetches the current rights evaluation record and structured conditions for a source.


