"""
gemini_analyzer.py
Uploads videos to the Gemini File API and performs:
  1. Triage pass - high-level event index with timestamps
  2. Deep-dive QA - answer specific temporal questions
Every answer from Gemini is required to include timestamps.
"""

from __future__ import annotations

import os
import time
import json
import re
import subprocess
import shutil
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

try:
    from google import genai
    from google.genai import types
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False


TRIAGE_PROMPT = """
You are a precise video analysis AI. Analyze this video and create a comprehensive
event timeline.

CRITICAL RULES:
1. Every event MUST include an exact timestamp in [MM:SS] format (e.g., [01:23])
2. Be specific about WHAT object/person and WHERE in the frame
3. Note the ORDER of events (first, then, after, before)
4. Identify any people, vehicles, or objects entering/exiting
5. Flag any sudden changes, alarms, stops, or anomalies

Output a JSON array with this structure:
[
  {
    "event_type": "person_enters" | "vehicle_arrives" | "object_stationary" |
                  "alarm_detected" | "motion_detected" | "scene_change" |
                  "machine_stops" | "zone_crossing" | "other",
    "timestamp_str": "MM:SS",
    "description": "Detailed description of what happened",
    "entities": ["person in blue jacket", "delivery truck"],
    "location": "left side of frame / restricted area / entrance",
    "confidence": 0.9
  }
]

Analyze the FULL video from start to end. Include ALL significant events.
"""

TEMPORAL_QA_PROMPT = """
You are a temporal video analysis AI. Answer questions about WHEN things happen,
in what ORDER, and for HOW LONG.

Here is a timeline of detected events for context:
{timeline}

Now answer this question about the video:
{question}

CRITICAL RULES:
1. EVERY claim must include a timestamp in [MM:SS] format
2. If asked about order, list events chronologically with timestamps
3. If asked about counting, give the count AND timestamp of each occurrence
4. If asked about duration, give start time, end time, and duration
5. If asked "what happened before/after X", find X's timestamp and look around it
6. Be specific and precise - no vague answers

Format your answer as clear, readable text with timestamps inline.
"""

DIRECT_VIDEO_QA_PROMPT = """
You are a temporal video analysis AI. Watch this video carefully and answer:

{question}

CRITICAL RULES:
1. EVERY claim must include a timestamp in [MM:SS] format
2. Be specific about what you see and when
3. If counting events, list each one with its timestamp
4. If describing order, use chronological timestamps

Format your answer as clear, readable text with timestamps inline.
"""


def compress_video(input_path: str, max_size_mb: int = 20) -> str:
    """Compress video to under max_size_mb using ffmpeg if available."""
    file_size_mb = os.path.getsize(input_path) / (1024 * 1024)
    if file_size_mb <= max_size_mb:
        return input_path

    # Check if ffmpeg is available
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("[COMPRESS] ffmpeg not found, uploading original file")
        return input_path

    out_path = str(Path(input_path).with_suffix(".compressed.mp4"))
    print(f"[COMPRESS] Video is {file_size_mb:.0f}MB, compressing to ~{max_size_mb}MB...")

    try:
        # Calculate target bitrate
        import cv2
        cap = cv2.VideoCapture(input_path)
        duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / max(cap.get(cv2.CAP_PROP_FPS), 1)
        cap.release()
        target_bitrate = int((max_size_mb * 8 * 1024) / max(duration, 1))

        subprocess.run(
            [ffmpeg, "-i", input_path, "-b:v", f"{target_bitrate}k",
             "-vf", "scale=-2:480", "-an", "-y", out_path],
            capture_output=True, timeout=120,
        )
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            new_size = os.path.getsize(out_path) / (1024 * 1024)
            print(f"[COMPRESS] Done: {new_size:.1f}MB")
            return out_path
    except Exception as e:
        print(f"[COMPRESS] Failed: {e}, using original")

    return input_path


class GeminiVideoAnalyzer:
    """Wraps the Gemini File API for video understanding with temporal reasoning."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-3.5-flash",
        pro_model: str = "gemini-3.1-pro-preview",
    ):
        if not _GENAI_AVAILABLE:
            raise RuntimeError("google-genai not installed. Run: pip install google-genai")
        key = api_key or os.getenv("GEMINI_API_KEY", "")
        if not key or key == "api-key":
            raise ValueError("No Gemini API key provided")

        self.client = genai.Client(api_key=key)

        # Deprecation / migration mapping for legacy or decommissioned model names
        deprecated_map = {
            "gemini-3-pro-preview": "gemini-3.1-pro-preview",
            "gemini-2.5-flash": "gemini-3.5-flash",
            "gemini-2.0-flash": "gemini-3.5-flash",
            "gemini-1.5-flash": "gemini-3.5-flash",
            "gemini-1.5-pro": "gemini-3.1-pro-preview",
        }
        env_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
        primary_model = model or env_model
        primary_model = deprecated_map.get(primary_model, primary_model)

        # Candidate models ordered by speed and availability
        self.models_to_try = [
            primary_model,
            "gemini-3.5-flash",
            "gemini-3.6-flash",
            "gemini-3-flash-preview",
            "gemini-3.7-flash",
            "gemini-3.8-flash",
            "gemini-3.1-pro-preview",
            "gemini-flash-latest",
        ]
        # Remove duplicates while preserving order
        self.models_to_try = list(dict.fromkeys(self.models_to_try))
        self.model = self.models_to_try[0]
        self.pro_model = deprecated_map.get(pro_model, pro_model)
        self._uploaded_file = None
        self._video_path: Optional[str] = None

    def _call_with_retry(self, func, max_retries=4):
        """Call with exponential backoff retry on transient errors."""
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                err = str(e).lower()
                is_transient = any(x in err for x in [
                    "503", "429", "unavailable", "overloaded", "high demand",
                    "10054", "10053", "connection", "forcibly closed",
                    "timeout", "reset", "broken pipe",
                ])
                if is_transient and attempt < max_retries - 1:
                    wait = (2 ** attempt) * 5
                    print(f"[RETRY] Attempt {attempt+1}/{max_retries} failed. Waiting {wait}s...")
                    time.sleep(wait)
                else:
                    raise

    def upload_video(self, video_path: str, force_reupload: bool = False) -> str:
        """Upload video to Gemini File API with compression and retry."""
        if (
            self._uploaded_file is not None
            and self._video_path == video_path
            and not force_reupload
        ):
            return self._uploaded_file.uri

        # Compress large videos
        upload_path = compress_video(video_path)

        print(f"[UPLOAD] Uploading to Gemini: {Path(upload_path).name}")

        def _upload():
            return self.client.files.upload(file=upload_path)

        self._uploaded_file = self._call_with_retry(_upload)
        self._video_path = video_path

        print("[WAIT] Waiting for Gemini to process video...")
        for _ in range(60):  # max 3 min wait
            if self._uploaded_file.state.name != "PROCESSING":
                break
            time.sleep(3)
            self._uploaded_file = self.client.files.get(name=self._uploaded_file.name)

        if self._uploaded_file.state.name != "ACTIVE":
            raise RuntimeError(f"Video processing failed: {self._uploaded_file.state.name}")

        print("[READY] Video ready")
        return self._uploaded_file.uri

    def build_event_index(self, video_path: str) -> list[dict]:
        """Run triage pass to get structured event timeline as JSON."""
        self.upload_video(video_path)

        last_error = None
        for m in self.models_to_try:
            print(f"[TRIAGE] Analyzing with {m}...")
            try:
                def _call():
                    return self.client.models.generate_content(
                        model=m,
                        contents=[self._uploaded_file, TRIAGE_PROMPT],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.2,
                        ),
                    )
                response = self._call_with_retry(_call, max_retries=2)
                text = response.text.strip() if hasattr(response, "text") and response.text else ""
                self.model = m  # stick with working model
                if text.startswith("```"):
                    text = re.sub(r"^```(?:json)?\s*", "", text)
                    text = re.sub(r"\s*```$", "", text)
                try:
                    events = json.loads(text)
                    if isinstance(events, dict) and "events" in events:
                        events = events["events"]
                    return events if isinstance(events, list) else []
                except json.JSONDecodeError:
                    match = re.search(r'\[.*\]', text, re.DOTALL)
                    if match:
                        try:
                            return json.loads(match.group())
                        except json.JSONDecodeError:
                            pass
                    return []
            except Exception as e:
                print(f"[TRIAGE] Model {m} failed: {e}. Trying fallback...")
                last_error = e

        if last_error:
            raise last_error
        return []

    def answer_question(
        self,
        video_path: str,
        question: str,
        event_timeline_json: str = "",
        use_pro: bool = False,
    ) -> dict:
        """Answer a temporal question about the video."""
        self.upload_video(video_path)

        if event_timeline_json:
            prompt = TEMPORAL_QA_PROMPT.format(
                timeline=event_timeline_json, question=question,
            )
        else:
            prompt = DIRECT_VIDEO_QA_PROMPT.format(question=question)

        last_error = None
        for m in self.models_to_try:
            print(f"[QA] Answering with {m}: {question[:80]}...")
            try:
                def _call():
                    return self.client.models.generate_content(
                        model=m,
                        contents=[self._uploaded_file, prompt],
                        config=types.GenerateContentConfig(temperature=0.3),
                    )
                response = self._call_with_retry(_call, max_retries=2)
                answer_text = response.text.strip()
                self.model = m
                timestamps = re.findall(
                    r'\[?(\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?)\]?', answer_text
                )
                return {
                    "answer": answer_text,
                    "timestamps_found": timestamps,
                    "model_used": m,
                    "question": question,
                }
            except Exception as e:
                print(f"[QA] Model {m} failed: {e}. Trying fallback...")
                last_error = e

        if last_error:
            raise last_error
        return {"answer": "", "timestamps_found": [], "model_used": "none", "question": question}

    def cleanup(self):
        """Delete the uploaded file from Gemini servers."""
        if self._uploaded_file:
            try:
                self.client.files.delete(name=self._uploaded_file.name)
            except Exception:
                pass
            self._uploaded_file = None
            self._video_path = None

    def __del__(self):
        self.cleanup()


def extract_timestamps(text: str) -> list[str]:
    """Pull all timestamps from text."""
    return re.findall(r'\[?(\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?)\]?', text)
