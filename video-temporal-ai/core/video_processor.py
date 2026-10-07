"""
video_processor.py
__________________
Handles video ingestion, frame extraction, and metadata.
Every frame is mapped to an exact timestamp (HH:MM:SS.mmm).
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Iterator, Optional, Any

try:
    import cv2
    import numpy as np
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False
    cv2 = None  # type: ignore
    np = None   # type: ignore


@dataclass
class FrameInfo:
    frame_index: int
    timestamp_sec: float
    timestamp_str: str          # "HH:MM:SS.mmm"
    width: int
    height: int
    frame: Optional[Any] = field(default=None, repr=False)


@dataclass
class VideoMetadata:
    path: str
    duration_sec: float
    fps: float
    total_frames: int
    width: int
    height: int
    size_bytes: int

    def to_dict(self):
        return asdict(self)


def seconds_to_timestamp(sec: float) -> str:
    """Convert float seconds _ 'HH:MM:SS.mmm' string."""
    hrs = int(sec // 3600)
    mins = int((sec % 3600) // 60)
    secs = sec % 60
    return f"{hrs:02d}:{mins:02d}:{secs:06.3f}"


def timestamp_to_seconds(ts: str) -> float:
    """Convert 'HH:MM:SS.mmm' or 'MM:SS' _ float seconds."""
    parts = ts.strip().split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(parts[0])


class VideoProcessor:
    """
    Loads a video file, exposes metadata, and yields frames with timestamps.
    """

    def __init__(self, video_path: str):
        self.video_path = str(video_path)
        if not os.path.exists(self.video_path):
            raise FileNotFoundError(f"Video not found: {self.video_path}")
        self._cap = None
        self._metadata: Optional[VideoMetadata] = None

    # __ Metadata ______________________________________________________________

    def get_metadata(self) -> VideoMetadata:
        if self._metadata:
            return self._metadata
        cap = cv2.VideoCapture(self.video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        self._metadata = VideoMetadata(
            path=self.video_path,
            duration_sec=total / fps if fps else 0,
            fps=fps,
            total_frames=total,
            width=w,
            height=h,
            size_bytes=os.path.getsize(self.video_path),
        )
        return self._metadata

    # __ Frame Iteration _______________________________________________________

    def iter_frames(
        self,
        sample_fps: float = 1.0,
        start_sec: float = 0.0,
        end_sec: Optional[float] = None,
    ) -> Iterator[FrameInfo]:
        """
        Yield FrameInfo objects at `sample_fps` rate.
        E.g. sample_fps=1 _ one frame per second.
        """
        meta = self.get_metadata()
        cap = cv2.VideoCapture(self.video_path)
        native_fps = meta.fps
        interval = int(native_fps / sample_fps) if sample_fps < native_fps else 1
        end_sec = end_sec or meta.duration_sec

        frame_idx = 0
        cap.set(cv2.CAP_PROP_POS_MSEC, start_sec * 1000)

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            pos_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
            pos_sec = pos_ms / 1000.0
            if pos_sec > end_sec:
                break
            if frame_idx % interval == 0:
                yield FrameInfo(
                    frame_index=frame_idx,
                    timestamp_sec=pos_sec,
                    timestamp_str=seconds_to_timestamp(pos_sec),
                    width=frame.shape[1],
                    height=frame.shape[0],
                    frame=frame,
                )
            frame_idx += 1
        cap.release()

    def extract_frame_at(self, timestamp_sec: float) -> Optional[Any]:
        """Extract a single frame at the given timestamp."""
        cap = cv2.VideoCapture(self.video_path)
        cap.set(cv2.CAP_PROP_POS_MSEC, timestamp_sec * 1000)
        ret, frame = cap.read()
        cap.release()
        return frame if ret else None

    # __ Scene Change Detection _________________________________________________

    def detect_scene_changes(
        self, threshold: float = 30.0, sample_fps: float = 2.0
    ) -> list[dict]:
        """
        Detect abrupt scene changes using frame difference.
        Returns list of {'timestamp_str': ..., 'timestamp_sec': ..., 'diff_score': ...}
        """
        scenes = []
        prev_gray = None
        for fi in self.iter_frames(sample_fps=sample_fps):
            gray = cv2.cvtColor(fi.frame, cv2.COLOR_BGR2GRAY)
            if prev_gray is not None:
                diff = cv2.absdiff(gray, prev_gray)
                score = float(diff.mean())
                if score > threshold:
                    scenes.append({
                        "timestamp_str": fi.timestamp_str,
                        "timestamp_sec": fi.timestamp_sec,
                        "diff_score": round(score, 2),
                        "event": "scene_change",
                    })
            prev_gray = gray
        return scenes

    # __ Frame Export __________________________________________________________

    def save_keyframes(
        self,
        output_dir: str,
        sample_fps: float = 1.0,
    ) -> list[str]:
        """Save sampled frames as JPEG files; return list of file paths."""
        os.makedirs(output_dir, exist_ok=True)
        paths = []
        for fi in self.iter_frames(sample_fps=sample_fps):
            fname = os.path.join(
                output_dir,
                f"frame_{fi.frame_index:06d}_{fi.timestamp_str.replace(':', '-')}.jpg",
            )
            cv2.imwrite(fname, fi.frame)
            paths.append(fname)
        return paths

    def __repr__(self):
        m = self.get_metadata()
        return (
            f"<VideoProcessor path='{Path(self.video_path).name}' "
            f"duration={m.duration_sec:.1f}s fps={m.fps:.1f}>"
        )
