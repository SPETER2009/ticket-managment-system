"""
routes.py — FastAPI REST API for the Video Temporal AI system.

Endpoints:
  POST /analyze          → Upload video + run full pipeline
  POST /ask              → Ask a question about an already-analyzed video
  GET  /timeline/{job_id} → Get the full event timeline
  GET  /health           → Health check
"""

import os
import uuid
import json
import asyncio
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import aiofiles

# Internal modules
from core.video_processor import VideoProcessor
from core.object_tracker import ObjectTracker
from core.event_indexer import EventIndexer
from core.gemini_analyzer import GeminiVideoAnalyzer
from core.temporal_engine import TemporalEngine

app = FastAPI(
    title="Video Temporal AI API",
    description="Watches videos and answers temporal questions with timestamps.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory job store (for demo; use Redis/DB in production) ────────────────
_jobs: dict[str, dict] = {}
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./temp_uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ── Request / Response models ─────────────────────────────────────────────────

class QuestionRequest(BaseModel):
    job_id: str
    question: str
    use_pro_model: bool = False


class AnalysisResponse(BaseModel):
    job_id: str
    status: str
    message: str


# ── Background pipeline ───────────────────────────────────────────────────────

async def run_pipeline(job_id: str, video_path: str):
    """Full pipeline: track → index → triage — runs in background."""
    try:
        _jobs[job_id]["status"] = "tracking"

        # Step 1: Object tracking
        tracker = ObjectTracker()
        tracker_summary = await asyncio.to_thread(
            tracker.track_video, video_path, 2.0
        )

        # Step 2: Event indexing
        indexer = EventIndexer()
        proc = VideoProcessor(video_path)
        scene_changes = await asyncio.to_thread(
            proc.detect_scene_changes
        )
        indexer.build_from_tracker(tracker)
        indexer.add_scene_changes(scene_changes)

        # Step 3: Gemini triage
        _jobs[job_id]["status"] = "analyzing"
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            analyzer = GeminiVideoAnalyzer(api_key=api_key)
            gemini_events = await asyncio.to_thread(
                analyzer.build_event_index, video_path
            )
            indexer.merge_gemini_events(gemini_events)

        # Store results
        _jobs[job_id].update({
            "status": "ready",
            "video_path": video_path,
            "tracker_summary": tracker_summary,
            "event_timeline": json.loads(indexer.to_json()),
            "indexer": indexer,   # keep in-memory for QA
            "tracker": tracker,
        })

    except Exception as e:
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["error"] = str(e)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """Upload a video and start the analysis pipeline."""
    job_id = str(uuid.uuid4())[:8]
    video_path = UPLOAD_DIR / f"{job_id}_{file.filename}"

    # Save uploaded file
    async with aiofiles.open(video_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    _jobs[job_id] = {"status": "queued", "filename": file.filename}
    background_tasks.add_task(run_pipeline, job_id, str(video_path))

    return AnalysisResponse(
        job_id=job_id,
        status="queued",
        message=f"Analysis started. Poll GET /status/{job_id} for updates.",
    )


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(404, f"Job {job_id!r} not found")
    job = _jobs[job_id]
    return {
        "job_id": job_id,
        "status": job.get("status"),
        "error": job.get("error"),
        "events_count": len(job.get("event_timeline", [])),
    }


@app.get("/timeline/{job_id}")
async def get_timeline(job_id: str):
    if job_id not in _jobs or _jobs[job_id]["status"] != "ready":
        raise HTTPException(400, "Job not ready or not found")
    return {"job_id": job_id, "timeline": _jobs[job_id]["event_timeline"]}


@app.post("/ask")
async def ask_question(req: QuestionRequest):
    """Answer a temporal question about an analyzed video."""
    job_id = req.job_id
    if job_id not in _jobs or _jobs[job_id]["status"] != "ready":
        raise HTTPException(400, "Job not ready. Run /analyze first.")

    job = _jobs[job_id]
    indexer: EventIndexer = job["indexer"]
    video_path: str = job["video_path"]

    # Rule-based answer from event index
    engine = TemporalEngine(indexer)

    # Gemini deep-dive answer
    api_key = os.getenv("GEMINI_API_KEY")
    gemini_result = None
    if api_key:
        analyzer = GeminiVideoAnalyzer(api_key=api_key)
        timeline_str = engine.get_timeline_for_prompt()
        gemini_result = await asyncio.to_thread(
            analyzer.answer_question,
            video_path,
            req.question,
            timeline_str,
            req.use_pro_model,
        )

    final_answer = engine.answer(req.question, gemini_answer=gemini_result)
    return JSONResponse(content=final_answer.to_dict())
