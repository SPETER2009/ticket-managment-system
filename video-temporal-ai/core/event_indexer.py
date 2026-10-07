"""
event_indexer.py
_________________
Builds a structured, time-ordered event timeline from:
  1. YOLO tracking data (object enters/exits, zone crossing, stationary)
  2. Scene change detection
  3. Gemini-extracted events (merged in later)

The event timeline is the foundation for all temporal queries.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Optional
import numpy as np

from core.video_processor import VideoProcessor, seconds_to_timestamp, timestamp_to_seconds
from core.object_tracker import ObjectTracker, TrackedObject


# __ Event Data Class __________________________________________________________

@dataclass
class Event:
    event_type: str            # e.g. "object_enters", "zone_crossing", "alarm"
    timestamp_sec: float
    timestamp_str: str
    track_id: Optional[int] = None
    label: Optional[str] = None
    display_name: Optional[str] = None
    zone: Optional[str] = None
    duration_sec: Optional[float] = None
    confidence: float = 1.0
    source: str = "tracker"    # "tracker" | "gemini" | "scene"
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d = {k: v for k, v in d.items() if v is not None}
        return d


# __ Zone Definitions __________________________________________________________

@dataclass
class Zone:
    name: str
    x1: float   # normalized 0-1
    y1: float
    x2: float
    y2: float

    def contains_bbox(self, bbox: list[float]) -> bool:
        """Check if bbox center falls within this zone."""
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        return self.x1 <= cx <= self.x2 and self.y1 <= cy <= self.y2


# Default zones (can be overridden by user)
DEFAULT_ZONES = [
    Zone("restricted_area", 0.6, 0.0, 1.0, 0.6),
    Zone("entrance",        0.0, 0.7, 0.3, 1.0),
    Zone("center",          0.3, 0.3, 0.7, 0.7),
]


# __ Event Indexer _____________________________________________________________

class EventIndexer:
    """
    Consumes tracking data and scene info to produce a unified event timeline.
    """

    def __init__(self, zones: Optional[list[Zone]] = None):
        self.zones = zones or DEFAULT_ZONES
        self.events: list[Event] = []

    # __ Build from tracker ____________________________________________________

    def build_from_tracker(self, tracker: ObjectTracker) -> list[Event]:
        """
        Extract events from a completed ObjectTracker run.
        """
        self.events.clear()
        tracks = tracker.get_tracks()
        detections = tracker.get_detections()

        # 1. Object entry / exit events
        for tid, obj in tracks.items():
            self._add_entry_exit_events(obj)

        # 2. Zone crossing events
        self._add_zone_crossing_events(tracks, detections)

        # 3. Stationary events
        stationary = tracker.find_stationary_objects(min_duration_sec=60.0)
        for s in stationary:
            self.events.append(Event(
                event_type="stationary_object",
                timestamp_sec=timestamp_to_seconds(s["start_timestamp"]),
                timestamp_str=s["start_timestamp"],
                track_id=s["track_id"],
                label=s["label"],
                display_name=s["display_name"],
                duration_sec=s["duration_sec"],
                source="tracker",
                metadata={"end_timestamp": s["end_timestamp"]},
            ))

        # 4. Re-appearance events (after occlusion)
        for tid, obj in tracks.items():
            for gap_start, gap_end in obj.disappeared_intervals:
                self.events.append(Event(
                    event_type="object_reappears",
                    timestamp_sec=gap_end,
                    timestamp_str=seconds_to_timestamp(gap_end),
                    track_id=tid,
                    label=obj.label,
                    display_name=obj.display_name,
                    source="tracker",
                    metadata={"disappeared_at": seconds_to_timestamp(gap_start),
                              "gap_sec": round(gap_end - gap_start, 1)},
                ))

        self._sort()
        return self.events

    def _add_entry_exit_events(self, obj: TrackedObject):
        self.events.append(Event(
            event_type="object_enters_frame",
            timestamp_sec=obj.first_seen_sec,
            timestamp_str=obj.first_seen_str,
            track_id=obj.track_id,
            label=obj.label,
            display_name=obj.display_name,
            source="tracker",
        ))
        self.events.append(Event(
            event_type="object_exits_frame",
            timestamp_sec=obj.last_seen_sec,
            timestamp_str=obj.last_seen_str,
            track_id=obj.track_id,
            label=obj.label,
            display_name=obj.display_name,
            source="tracker",
        ))

    def _add_zone_crossing_events(self, tracks, detections):
        # For each track, detect first frame where detection center is inside each zone
        zone_first_entry: dict[tuple[int, str], float] = {}

        for det in sorted(detections, key=lambda d: d.timestamp_sec):
            for zone in self.zones:
                key = (det.track_id, zone.name)
                if key not in zone_first_entry and zone.contains_bbox(det.bbox):
                    zone_first_entry[key] = det.timestamp_sec
                    obj = tracks.get(det.track_id)
                    self.events.append(Event(
                        event_type="zone_crossing",
                        timestamp_sec=det.timestamp_sec,
                        timestamp_str=det.timestamp_str,
                        track_id=det.track_id,
                        label=det.label,
                        display_name=obj.display_name if obj else f"{det.label}-{det.track_id}",
                        zone=zone.name,
                        confidence=det.confidence,
                        source="tracker",
                    ))

    # __ Add scene-change events _______________________________________________

    def add_scene_changes(self, scene_changes: list[dict]):
        for sc in scene_changes:
            self.events.append(Event(
                event_type="scene_change",
                timestamp_sec=sc["timestamp_sec"],
                timestamp_str=sc["timestamp_str"],
                source="scene",
                confidence=min(1.0, sc.get("diff_score", 30) / 100),
                metadata={"diff_score": sc.get("diff_score")},
            ))
        self._sort()

    # __ Merge Gemini events ___________________________________________________

    def merge_gemini_events(self, gemini_events: list[dict]):
        """
        Merge events extracted by Gemini (from gemini_analyzer.py).
        Each item should have: event_type, timestamp_str, [description], etc.
        """
        for ge in gemini_events:
            ts_str = ge.get("timestamp_str", "00:00:00.000")
            try:
                ts_sec = timestamp_to_seconds(ts_str)
            except Exception:
                ts_sec = 0.0
            self.events.append(Event(
                event_type=ge.get("event_type", "gemini_event"),
                timestamp_sec=ts_sec,
                timestamp_str=ts_str,
                label=ge.get("label"),
                display_name=ge.get("display_name"),
                zone=ge.get("zone"),
                confidence=ge.get("confidence", 0.8),
                source="gemini",
                metadata=ge.get("metadata", {"description": ge.get("description", "")}),
            ))
        self._sort()

    # __ Query helpers _________________________________________________________

    def get_events_in_window(
        self, start_sec: float, end_sec: float
    ) -> list[Event]:
        return [e for e in self.events if start_sec <= e.timestamp_sec <= end_sec]

    def get_events_by_type(self, event_type: str) -> list[Event]:
        return [e for e in self.events if e.event_type == event_type]

    def get_events_involving_track(self, track_id: int) -> list[Event]:
        return [e for e in self.events if e.track_id == track_id]

    def get_events_in_zone(self, zone_name: str) -> list[Event]:
        return [e for e in self.events if e.zone == zone_name]

    def get_nearest_event_before(
        self, timestamp_sec: float, event_types: Optional[list[str]] = None
    ) -> Optional[Event]:
        candidates = [
            e for e in self.events
            if e.timestamp_sec < timestamp_sec
            and (event_types is None or e.event_type in event_types)
        ]
        return candidates[-1] if candidates else None

    def get_nearest_event_after(
        self, timestamp_sec: float, event_types: Optional[list[str]] = None
    ) -> Optional[Event]:
        candidates = [
            e for e in self.events
            if e.timestamp_sec > timestamp_sec
            and (event_types is None or e.event_type in event_types)
        ]
        return candidates[0] if candidates else None

    def count_events(self, event_type: str) -> int:
        return len(self.get_events_by_type(event_type))

    def to_json(self) -> str:
        return json.dumps([e.to_dict() for e in self.events], indent=2)

    def _sort(self):
        self.events.sort(key=lambda e: e.timestamp_sec)

    def __len__(self):
        return len(self.events)

    def __repr__(self):
        return f"<EventIndexer events={len(self.events)}>"
