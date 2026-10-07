"""
app.py — Streamlit UI for Video Temporal AI
============================================
Upload a video → type a question → get a timestamped answer.
"""

import os
import sys
import json
import time
import tempfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Load .env BEFORE anything else
load_dotenv(override=True)

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="🎬 Video Temporal AI",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Add project root to path ──────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from core.video_processor import VideoProcessor
from core.event_indexer import EventIndexer
from core.gemini_analyzer import GeminiVideoAnalyzer
from core.temporal_engine import TemporalEngine

# ── Load API Key & Config ──────────────────────────────────────────────────────
API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

# ── Sidebar Settings ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuration")
    user_api_key = st.text_input("Gemini API Key", value=API_KEY, type="password", help="Get free key at ai.google.dev")
    if user_api_key:
        API_KEY = user_api_key

    model_options = [
        "gemini-3.5-flash",
        "gemini-3.6-flash",
        "gemini-3.7-flash",
        "gemini-3-flash-preview",
        "gemini-3.1-pro-preview",
    ]
    default_idx = model_options.index(DEFAULT_MODEL) if DEFAULT_MODEL in model_options else 0
    GEMINI_MODEL = st.selectbox("Gemini Model", model_options, index=default_idx)

    st.divider()
    st.caption("Model fallback is enabled automatically if high demand occurs.")

# ── Session State ─────────────────────────────────────────────────────────────
for key, default in [
    ("pipeline_done", False), ("indexer", None), ("video_path", None),
    ("qa_history", []), ("analyzer", None), ("gemini_events", []),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("🎬 Video Temporal AI")
st.caption("Upload a video → Ask temporal questions → Get answers with timestamps")

# ── Video Upload ───────────────────────────────────────────────────────────────
col_video, col_results = st.columns([1, 1])

with col_video:
    st.subheader("📹 Upload Video")
    uploaded_file = st.file_uploader(
        "Choose a video file",
        type=["mp4", "avi", "mov", "mkv", "webm"],
        label_visibility="collapsed",
    )

    if uploaded_file:
        suffix = Path(uploaded_file.name).suffix
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(uploaded_file.read())
        tmp.close()
        video_path = tmp.name

        st.video(video_path)

        proc = VideoProcessor(video_path)
        meta = proc.get_metadata()

        m1, m2, m3 = st.columns(3)
        m1.metric("Duration", f"{meta.duration_sec:.1f}s")
        m2.metric("FPS", f"{meta.fps:.0f}")
        m3.metric("Size", f"{meta.size_bytes / 1024 / 1024:.1f}MB")

        if st.button("🚀 Analyze Video", type="primary", use_container_width=True):
            if not API_KEY or API_KEY == "api-key":
                st.error("❌ No API key in `.env` file!")
            else:
                progress = st.progress(0, text="Starting...")

                # Step 1: Scene detection
                progress.progress(15, text="🔍 Detecting scene changes...")
                scene_changes = proc.detect_scene_changes()

                # Step 2: Object tracking (optional — skip if ultralytics not installed)
                tracker = None
                try:
                    from core.object_tracker import ObjectTracker
                    progress.progress(30, text="🎯 Running YOLOv8 tracking...")
                    tracker = ObjectTracker(confidence=0.35)
                    tracker.track_video(video_path, sample_fps=1.0)
                except Exception:
                    tracker = None

                # Step 3: Build event index
                progress.progress(50, text="📋 Building event timeline...")
                indexer = EventIndexer()
                if tracker:
                    indexer.build_from_tracker(tracker)
                indexer.add_scene_changes(scene_changes)

                # Step 4: Gemini triage analysis
                progress.progress(60, text="🤖 Uploading to Gemini AI...")
                analyzer = None
                try:
                    analyzer = GeminiVideoAnalyzer(
                        api_key=API_KEY, model=GEMINI_MODEL
                    )
                    gemini_events = analyzer.build_event_index(video_path)
                    indexer.merge_gemini_events(gemini_events)
                    st.session_state.analyzer = analyzer
                    st.session_state.gemini_events = gemini_events
                    progress.progress(100, text="✅ Done!")
                except Exception as e:
                    st.error(f"❌ Gemini analysis failed: {e}")
                    st.session_state.analyzer = None
                    progress.progress(100, text="⚠️ Partial analysis done")

                time.sleep(0.5)
                progress.empty()

                st.session_state.indexer = indexer
                st.session_state.video_path = video_path
                st.session_state.pipeline_done = True
                st.session_state.qa_history = []

                if analyzer:
                    st.success(f"✅ Analysis complete! Found **{len(indexer)}** events.")
                else:
                    st.warning("⚠️ Only scene detection worked. Check your API key.")

with col_results:
    st.subheader("📊 Events Found")
    if st.session_state.indexer and st.session_state.pipeline_done:
        indexer = st.session_state.indexer
        events = indexer.events

        if events:
            for ev in events[:25]:
                icon = {
                    "object_enters_frame": "👤", "object_exits_frame": "🚶",
                    "zone_crossing": "🚨", "stationary_object": "🅿️",
                    "scene_change": "🎬", "alarm_detected": "🔔",
                }.get(ev.event_type, "📌")

                desc = ev.metadata.get("description", "")
                if ev.display_name and not desc:
                    desc = ev.display_name

                st.markdown(f"`{ev.timestamp_str[:8]}` {icon} {desc or ev.event_type}")
        else:
            st.info("No events detected.")
    else:
        st.info("📹 Upload and analyze a video first.")

# ── Q&A Section ────────────────────────────────────────────────────────────────
st.divider()
st.subheader("💬 Ask Questions About the Video")

if not st.session_state.pipeline_done:
    st.info("⬆️ Upload and analyze a video first.")
else:
    # Quick question buttons
    qcol1, qcol2, qcol3, qcol4 = st.columns(4)
    with qcol1:
        if st.button("📝 Describe all events", use_container_width=True):
            st.session_state["_q"] = "Describe everything that happens in this video with timestamps for each event."
    with qcol2:
        if st.button("🔢 Count people", use_container_width=True):
            st.session_state["_q"] = "How many people appear in this video? Give timestamps for each."
    with qcol3:
        if st.button("⏱️ What happened first?", use_container_width=True):
            st.session_state["_q"] = "What was the very first thing that happened in the video? Give the timestamp."
    with qcol4:
        if st.button("🔍 Full timeline", use_container_width=True):
            st.session_state["_q"] = "List every event in chronological order with exact timestamps."

    default_q = st.session_state.get("_q", "")
    question = st.text_input(
        "Or type your own question:",
        value=default_q,
        placeholder="e.g., What happened right before the alarm? / How many times did the person enter?",
    )

    if st.button("🔍 Get Answer", type="primary", use_container_width=True):
        if not question.strip():
            st.warning("Please type a question.")
        else:
            with st.spinner("🤔 Gemini is analyzing the video to answer your question..."):
                # PRIMARY: Ask Gemini directly
                gemini_result = None
                analyzer = st.session_state.analyzer
                if analyzer:
                    try:
                        # Build timeline context from event index
                        indexer = st.session_state.indexer
                        engine = TemporalEngine(indexer)
                        timeline_str = engine.get_timeline_for_prompt()

                        gemini_result = analyzer.answer_question(
                            st.session_state.video_path,
                            question,
                            timeline_str,
                        )
                    except Exception as e:
                        st.error(f"❌ Error getting answer: {e}")

                # Build final answer
                indexer = st.session_state.indexer
                engine = TemporalEngine(indexer)
                final = engine.answer(question, gemini_answer=gemini_result)

            st.session_state.qa_history.append({
                "question": question,
                "gemini_answer": gemini_result.get("answer", "") if gemini_result else "",
                "timestamps": gemini_result.get("timestamps_found", []) if gemini_result else final.timestamps,
                "rule_based": final.answer,
                "full": final.to_dict(),
            })
            if "_q" in st.session_state:
                del st.session_state["_q"]

    # ── Display Answers ───────────────────────────────────────────────────────
    for idx, qa in enumerate(reversed(st.session_state.qa_history)):
        is_latest = (idx == 0)

        with st.expander(f"❓ {qa['question']}", expanded=is_latest):
            # Show Gemini's direct answer (the good one)
            if qa["gemini_answer"]:
                st.markdown(qa["gemini_answer"])
            else:
                st.markdown(qa["rule_based"])
                st.caption("⚠️ This is a rule-based answer. Gemini couldn't process this question.")

            # Show timestamps
            if qa["timestamps"]:
                ts_str = ", ".join([f"`{t}`" for t in qa["timestamps"][:10]])
                st.markdown(f"**⏱️ Timestamps:** {ts_str}")

# ── Footer ─────────────────────────────────────────────────────────────────────
st.divider()
st.caption("Video Temporal AI · Powered by Google Gemini + YOLOv8 · Hackathon 2026")
