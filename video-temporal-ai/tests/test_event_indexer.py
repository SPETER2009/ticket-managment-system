"""
tests/test_event_indexer.py
Tests for EventIndexer zone crossing, event building, and timeline queries.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.event_indexer import EventIndexer, Zone, Event
from core.video_processor import seconds_to_timestamp


# ── Zone Tests ────────────────────────────────────────────────────────────────

def test_zone_contains_center():
    zone = Zone("test", 0.5, 0.5, 1.0, 1.0)
    assert zone.contains_bbox([0.6, 0.6, 0.9, 0.9])   # center (0.75, 0.75) → inside
    assert not zone.contains_bbox([0.0, 0.0, 0.3, 0.3])  # center (0.15, 0.15) → outside

def test_zone_boundary():
    zone = Zone("boundary", 0.0, 0.0, 0.5, 0.5)
    # Center exactly on boundary → inside
    assert zone.contains_bbox([0.0, 0.0, 1.0, 1.0])  # center (0.5, 0.5)


# ── EventIndexer Basics ───────────────────────────────────────────────────────

def test_indexer_empty():
    idx = EventIndexer()
    assert len(idx) == 0

def test_indexer_sorts_by_timestamp():
    idx = EventIndexer()
    idx.events = [
        Event("b", 20.0, seconds_to_timestamp(20.0)),
        Event("a", 5.0, seconds_to_timestamp(5.0)),
        Event("c", 10.0, seconds_to_timestamp(10.0)),
    ]
    idx._sort()
    assert [e.timestamp_sec for e in idx.events] == [5.0, 10.0, 20.0]


# ── Gemini Event Merge ────────────────────────────────────────────────────────

def test_merge_gemini_events():
    idx = EventIndexer()
    idx.merge_gemini_events([
        {"event_type": "alarm_detected", "timestamp_str": "01:30",
         "description": "Alarm sounded", "confidence": 0.9}
    ])
    assert len(idx) == 1
    e = idx.events[0]
    assert e.event_type == "alarm_detected"
    assert e.source == "gemini"
    assert e.timestamp_sec == pytest.approx(90.0)

def test_merge_gemini_handles_hh_mm_ss():
    idx = EventIndexer()
    idx.merge_gemini_events([
        {"event_type": "test", "timestamp_str": "00:01:30.000"}
    ])
    assert idx.events[0].timestamp_sec == pytest.approx(90.0)


# ── Query Methods ──────────────────────────────────────────────────────────────

def test_get_events_in_window():
    idx = EventIndexer()
    idx.events = [
        Event("a", 10.0, seconds_to_timestamp(10.0)),
        Event("b", 50.0, seconds_to_timestamp(50.0)),
        Event("c", 90.0, seconds_to_timestamp(90.0)),
    ]
    result = idx.get_events_in_window(20.0, 80.0)
    assert len(result) == 1
    assert result[0].event_type == "b"

def test_get_events_by_type():
    idx = EventIndexer()
    idx.events = [
        Event("alarm_detected", 10.0, seconds_to_timestamp(10.0)),
        Event("zone_crossing", 20.0, seconds_to_timestamp(20.0)),
        Event("alarm_detected", 30.0, seconds_to_timestamp(30.0)),
    ]
    alarms = idx.get_events_by_type("alarm_detected")
    assert len(alarms) == 2

def test_count_events():
    idx = EventIndexer()
    idx.events = [Event("scene_change", i * 10.0, seconds_to_timestamp(i * 10.0))
                  for i in range(5)]
    assert idx.count_events("scene_change") == 5

def test_nearest_before():
    idx = EventIndexer()
    idx.events = [
        Event("a", 10.0, seconds_to_timestamp(10.0)),
        Event("b", 20.0, seconds_to_timestamp(20.0)),
        Event("alarm", 30.0, seconds_to_timestamp(30.0)),
    ]
    result = idx.get_nearest_event_before(30.0)
    assert result is not None
    assert result.event_type == "b"

def test_nearest_after():
    idx = EventIndexer()
    idx.events = [
        Event("alarm", 30.0, seconds_to_timestamp(30.0)),
        Event("c", 40.0, seconds_to_timestamp(40.0)),
        Event("d", 50.0, seconds_to_timestamp(50.0)),
    ]
    result = idx.get_nearest_event_after(30.0)
    assert result is not None
    assert result.event_type == "c"

def test_get_events_in_zone():
    idx = EventIndexer()
    idx.events = [
        Event("zone_crossing", 10.0, seconds_to_timestamp(10.0), zone="restricted_area"),
        Event("zone_crossing", 20.0, seconds_to_timestamp(20.0), zone="entrance"),
        Event("zone_crossing", 30.0, seconds_to_timestamp(30.0), zone="restricted_area"),
    ]
    restricted = idx.get_events_in_zone("restricted_area")
    assert len(restricted) == 2

def test_to_json():
    idx = EventIndexer()
    idx.events = [Event("test", 10.0, seconds_to_timestamp(10.0))]
    import json
    data = json.loads(idx.to_json())
    assert isinstance(data, list)
    assert data[0]["event_type"] == "test"
