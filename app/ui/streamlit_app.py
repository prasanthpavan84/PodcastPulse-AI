"""PodcastPulse AI — Streamlit Dashboard Skeleton (Phase 1)."""

import httpx
import streamlit as st

st.set_page_config(
    page_title="PodcastPulse AI Dashboard",
    page_icon="🎙️",
    layout="wide",
)

st.title("🎙️ PodcastPulse AI — Editorial Production Dashboard")
st.caption("Phase 1: Architecture Foundation & System Monitoring")

# Sidebar - System Status
st.sidebar.header("System Health & Status")

api_base_url = st.sidebar.text_input("API Base URL", "http://127.0.0.1:8000")

try:
    with httpx.Client(timeout=2.0) as client:
        health_res = client.get(f"{api_base_url}/api/v1/health")
        if health_res.status_code == 200:
            st.sidebar.success(f"FastAPI: Online (v{health_res.json().get('version', '0.1.0')})")
        else:
            st.sidebar.warning(f"FastAPI: Status {health_res.status_code}")

        ready_res = client.get(f"{api_base_url}/api/v1/ready")
        if ready_res.status_code == 200 and ready_res.json().get("database") == "connected":
            st.sidebar.success("Database: MySQL 8 Connected")
        else:
            st.sidebar.error("Database: Disconnected")
except Exception:
    st.sidebar.warning("FastAPI Server: Offline (Start backend with `uv run uvicorn app.api.main:app`)")

# Main Navigation Tabs
tab_overview, tab_workflow, tab_jobs = st.tabs(
    [
        "Architecture Overview",
        "Canonical Workflow",
        "Job Monitor",
    ]
)

with tab_overview:
    st.subheader("System Architecture Layers")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### 1. Intelligence Layer")
        st.info(
            "• LLM Provider Interface (Ollama)\n"
            "• Whisper Audio Transcription\n"
            "• Semantic Segmentation & Embeddings\n"
            "• Multi-factor Virality Scoring"
        )

    with col2:
        st.markdown("### 2. Domain & Business Layer")
        st.success(
            "• Canonical Workflow State Machine\n"
            "• Deterministic Rights Engine\n"
            "• Idempotency & Retries Policy\n"
            "• Human Approval Publishing Gate"
        )

    with col3:
        st.markdown("### 3. Execution Services")
        st.warning(
            "• MySQL 8 Relational Store\n• Local Filesystem Storage\n• FFmpeg Rendering Engine\n• Local TTS Synthesizer"
        )

with tab_workflow:
    st.subheader("Canonical Content Lifecycle")
    st.markdown("""
    ```text
    DISCOVERED ──> RIGHTS_PENDING ──> RIGHTS_APPROVED ──> TRANSCRIBING ──> TRANSCRIBED
                                           │
                                     RIGHTS_BLOCKED [Hard Gate]
                                           │
    CLIPS_READY <── CLIP_ANALYSIS <────────┘
         │
         └──> SCRIPT_READY ──> VIDEO_RENDERING ──> RENDERED ──> QC_PENDING ──> QC_PASSED
                                                                                  │
    PUBLISHED <── UPLOADING <── READY_TO_PUBLISH <── APPROVED <── REVIEW_PENDING <┘
                                                        │
                                                     REJECTED
    ```
    """)

with tab_jobs:
    st.subheader("Job Execution Engine")
    st.write("Idempotent background job tracking with bounded retries and correlation IDs.")
    st.info("No active background jobs running. Ready for Phase 2 discovery tasks.")
