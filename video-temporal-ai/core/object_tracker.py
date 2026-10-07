"""
object_tracker.py
_________________
YOLOv8 + ByteTrack object detection and tracking.

Each detected object receives a persistent track_id that survives occlusion
and re-entry into frame _ critical for answering "the same person who..." 
type questions.

Output: structured TrackedObject records with entry/exit timestamps.
"""

import os
from dataclasses import dataclass, field
from typing import Optional, Any
from pathlib import Path

# Lazy imports so the module can be imported without crashing
try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None   # type: ignore
    np = None    # type: ignore

try:
    from ultralytics import YOLO
    _YOLO_AVAILABLE = True
except Exception:
    _YOLO_AVAILABLE = False
    YOLO = None

from core.video_processor import VideoProcessor, seconds_to_timestamp


# __ Data classes ______________________________________________________________

@dataclass
class Detection:
    track_id: int
    label: str           # e.g. "person", "truck", "car"
    confidence: float
    bbox: list[float]    # [x1, y1, x2, y2] normalized 0-1
    timestamp_sec: float
    timestamp_str: str
    frame_index: int


@dataclass
class TrackedObject:
    track_id: int
    label: str
    first_seen_sec: float
    first_seen_str: str
    last_seen_sec: float
    last_seen_str: str
    total_visible_frames: int = 0
    detections: list[Detection] = field(default_factory=list, repr=False)

    # Re-identification support
    disappeared_intervals: list[tuple[float, float]] = field(default_factory=list)

    @property
    def duration_sec(self) -> float:
        return self.last_seen_sec - self.first_seen_sec

    @property
    def display_name(self) -> str:
        return f"{self.label.capitalize()}-{self.track_id}"

    def to_dict(self) -> dict:
        return {
            "track_id": self.track_id,
            "label": self.label,
            "display_name": self.display_name,
            "first_seen": self.first_seen_str,
            "first_seen_sec": round(self.first_seen_sec, 2),
            "last_seen": self.last_seen_str,
            "last_seen_sec": round(self.last_seen_sec, 2),
            "duration_sec": round(self.duration_sec, 2),
            "total_visible_frames": self.total_visible_frames,
            "disappeared_intervals": [
                {"from": seconds_to_timestamp(s), "to": seconds_to_timestamp(e)}
                for s, e in self.disappeared_intervals
            ],
        }


# __ Tracker ____________________________________________________________________

class ObjectTracker:
    """
    Runs YOLOv8 detection with ByteTrack on a video, producing:
      - frame-level detections (list[Detection])
      - per-object track summaries (dict[track_id _ TrackedObject])
    """

    COCO_CLASSES = {
        0: "person", 1: "bicycle", 2: "car", 3: "motorcycle",
        4: "airplane", 5: "bus", 6: "train", 7: "truck",
        8: "boat", 14: "bird", 15: "cat", 16: "dog",
        24: "backpack", 26: "handbag", 28: "suitcase",
        39: "bottle", 56: "chair", 57: "couch", 58: "potted plant",
        59: "bed", 60: "dining table", 62: "tv", 63: "laptop",
        67: "cell phone", 72: "refrigerator", 73: "book",
        74: "clock", 76: "scissors",
    }

    def __init__(
        self,
        model_name: str = "yolov8n.pt",
        confidence: float = 0.35,
        classes_of_interest: Optional[list[int]] = None,
    ):
        if not _YOLO_AVAILABLE:
            raise RuntimeError(
                "ultralytics not installed. Run: pip install ultralytics"
            )
        self.model = YOLO(model_name)
        self.confidence = confidence
        # None _ detect all classes; list _ filter to these COCO class IDs
        self.classes_of_interest = classes_of_interest
        self._tracks: dict[int, TrackedObject] = {}
        self._all_detections: list[Detection] = []

    # __ Main entry point ______________________________________________________

    def track_video(
        self,
        video_path: str,
        sample_fps: float = 2.0,
        progress_callback=None,
    ) -> dict:
        """
        Run tracking on a video file.
        Returns summary dict with all tracked objects and detections.
        """
        proc = VideoProcessor(video_path)
        meta = proc.get_metadata()
        self._tracks.clear()
        self._all_detections.clear()

        frame_buffer = []
        timestamp_buffer = []

        # Collect sampled frames first, then run batch inference
        for fi in proc.iter_frames(sample_fps=sample_fps):
            frame_buffer.append(fi.frame)
            timestamp_buffer.append((fi.timestamp_sec, fi.timestamp_str, fi.frame_index))

        total = len(frame_buffer)
        for i, (frame, ts_info) in enumerate(zip(frame_buffer, timestamp_buffer)):
            ts_sec, ts_str, frame_idx = ts_info
            self._process_frame(frame, ts_sec, ts_str, frame_idx)
            if progress_callback:
                progress_callback(i + 1, total)

        self._finalize_tracks()
        return self.get_summary()

    # __ Frame processing ______________________________________________________

    def _process_frame(
        self,
        frame: Any,
        ts_sec: float,
        ts_str: str,
        frame_idx: int,
    ):
        """Run YOLO+ByteTrack on one frame, update track records."""
        kwargs = {
            "source": frame,
            "conf": self.confidence,
            "tracker": "bytetrack.yaml",
            "persist": True,
            "verbose": False,
        }
        if self.classes_of_interest:
            kwargs["classes"] = self.classes_of_interest

        results = self.model.track(**kwargs)
        if not results or results[0].boxes is None:
            return

        boxes = results[0].boxes
        h, w = frame.shape[:2]

        if boxes.id is None:
            return  # No tracks assigned yet

        for box, track_id, cls_id, conf in zip(
            boxes.xyxy.cpu().numpy(),
            boxes.id.cpu().numpy().astype(int),
            boxes.cls.cpu().numpy().astype(int),
            boxes.conf.cpu().numpy(),
        ):
            label = self.model.names.get(cls_id, str(cls_id))
            x1, y1, x2, y2 = box
            bbox_norm = [
                round(x1 / w, 4), round(y1 / h, 4),
                round(x2 / w, 4), round(y2 / h, 4),
            ]

            det = Detection(
                track_id=int(track_id),
                label=label,
                confidence=round(float(conf), 3),
                bbox=bbox_norm,
                timestamp_sec=ts_sec,
                timestamp_str=ts_str,
                frame_index=frame_idx,
            )
            self._all_detections.append(det)

            # Update or create TrackedObject
            if track_id not in self._tracks:
                self._tracks[track_id] = TrackedObject(
                    track_id=int(track_id),
                    label=label,
                    first_seen_sec=ts_sec,
                    first_seen_str=ts_str,
                    last_seen_sec=ts_sec,
                    last_seen_str=ts_str,
                )
            else:
                obj = self._tracks[track_id]
                prev_last = obj.last_seen_sec
                # If gap > 3s between detections, record as disappearance
                if ts_sec - prev_last > 3.0:
                    obj.disappeared_intervals.append((prev_last, ts_sec))
                obj.last_seen_sec = ts_sec
                obj.last_seen_str = ts_str

            self._tracks[track_id].total_visible_frames += 1
            self._tracks[track_id].detections.append(det)

    def _finalize_tracks(self):
        """Post-process: label tracks that were stationary, etc."""
        pass  # Extended in event_indexer.py

    # __ Accessors _____________________________________________________________

    def get_summary(self) -> dict:
        return {
            "total_objects_tracked": len(self._tracks),
            "tracked_objects": [t.to_dict() for t in self._tracks.values()],
            "total_detections": len(self._all_detections),
        }

    def get_tracks(self) -> dict[int, TrackedObject]:
        return self._tracks

    def get_detections(self) -> list[Detection]:
        return self._all_detections

    # __ Stationary Detection __________________________________________________

    def find_stationary_objects(
        self,
        min_duration_sec: float = 120.0,
        movement_threshold: float = 0.03,  # normalized bbox center movement
    ) -> list[dict]:
        """
        Find TrackedObjects that barely moved for >= min_duration_sec.
        Returns list of stationary event dicts with timestamps.
        """
        stationary = []
        for tid, obj in self._tracks.items():
            if obj.duration_sec < min_duration_sec:
                continue
            if len(obj.detections) < 3:
                continue

            # Compute center movement across all detections
            centers = [
                ((d.bbox[0] + d.bbox[2]) / 2, (d.bbox[1] + d.bbox[3]) / 2)
                for d in obj.detections
            ]
            max_displacement = max(
                ((c[0] - centers[0][0]) ** 2 + (c[1] - centers[0][1]) ** 2) ** 0.5
                for c in centers
            )
            if max_displacement < movement_threshold:
                stationary.append({
                    "event": "stationary_object",
                    "track_id": tid,
                    "label": obj.label,
                    "display_name": obj.display_name,
                    "start_timestamp": obj.first_seen_str,
                    "end_timestamp": obj.last_seen_str,
                    "duration_sec": round(obj.duration_sec, 1),
                    "max_displacement": round(max_displacement, 4),
                })
        return stationary
