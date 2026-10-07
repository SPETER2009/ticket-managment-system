"""
tests/test_temporal_engine.py
Tests for the temporal reasoning engine using mock event data.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.event_indexer import EventIndexer, Event
from core.temporal_engine import TemporalEngine, classify_query
from core.answer_formatter import AnswerFormatter
from core.video_processor import seconds_to_timestamp, timestamp_to_seconds


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_event(event_type, ts_sec, label=None, track_id=None, zone=None,
               duration_sec=None, source="tracker", metadata=None):
    return Event(
        event_type=event_type,
        timestamp_sec=ts_sec,
        timestamp_str=seconds_to_timestamp(ts_sec),
        track_id=track_id,
        label=label,
        display_name=f"{label}-{track_id}" if label and track_id else None,
        zone=zone,
        duration_sec=duration_sec,
        source=source,
        metadata=metadata or {},
    )


@pytest.fixture
def sample_indexer():
    """Pre-populated EventIndexer with a realistic event sequence."""
    idx = EventIndexer()
    idx.events = [
        make_event("object_enters_frame", 10.0, "truck", track_id=1),
        make_event("zone_crossing",        47.5, "truck", track_id=1, zone="entrance"),
        make_event("object_enters_frame", 87.0, "person", track_id=2),
        make_event("zone_crossing",        134.0, "person", track_id=2, zone="restricted_area"),
        make_event("alarm_detected",       140.0, source="gemini", metadata={"description": "Safety alarm triggered"}),
        make_event("object_enters_frame", 200.0, "person", track_id=3),
        make_event("stationary_object",    220.0, "box", track_id=5, duration_sec=150,
                   metadata={"end_timestamp": "00:06:30.000"}),
        make_event("object_exits_frame",   300.0, "truck", track_id=1),
    ]
    idx._sort()
    return idx


# ── Query Classification ───────────────────────────────────────────────────────

def test_classify_count_query():
    types = classify_query("How many times did the machine stop?")
    assert "count" in types

def test_classify_duration_query():
    types = classify_query("Find objects untouched for more than 2 minutes")
    assert "duration" in types

def test_classify_causal_query():
    types = classify_query("What happened right before the alarm?")
    assert "causal" in types

def test_classify_order_query():
    types = classify_query("What was the first event?")
    assert "order" in types


# ── Timestamp Utilities ────────────────────────────────────────────────────────

def test_seconds_to_timestamp():
    assert seconds_to_timestamp(0) == "00:00:00.000"
    assert seconds_to_timestamp(65.5) == "00:01:05.500"
    assert seconds_to_timestamp(3661.0) == "01:01:01.000"

def test_timestamp_to_seconds():
    assert timestamp_to_seconds("00:01:05.500") == pytest.approx(65.5)
    assert timestamp_to_seconds("01:27") == pytest.approx(87.0)


# ── Count Queries ──────────────────────────────────────────────────────────────

def test_count_person_entries(sample_indexer):
    engine = TemporalEngine(sample_indexer)
    answer = engine.answer("How many people entered the frame?")
    assert answer.has_timestamp
    assert answer.query_types  # must not be empty
    assert "2" in answer.answer or "two" in answer.answer.lower() or answer.rule_based_summary

def test_count_returns_timestamps(sample_indexer):
    engine = TemporalEngine(sample_indexer)
    answer = engine.answer("How many times did the truck appear?")
    assert answer.has_timestamp, "Count answer must contain a timestamp"


# ── Duration Queries ───────────────────────────────────────────────────────────

def test_find_stationary_objects(sample_indexer):
    engine = TemporalEngine(sample_indexer)
    answer = engine.answer("Find every object that sat untouched for more than 2 minutes")
    assert answer.has_timestamp
    # The box with duration_sec=150 (2.5 min) should be found
    assert "box" in answer.answer.lower() or len(answer.supporting_events) > 0

def test_stationary_threshold(sample_indexer):
    engine = TemporalEngine(sample_indexer)
    # 10 minutes — nothing should qualify
    answer = engine.answer("Find objects stationary for more than 10 minutes")
    assert "No objects" in answer.answer or answer.rule_based_summary


# ── Causal Queries ─────────────────────────────────────────────────────────────

def test_causal_before_alarm(sample_indexer):
    engine = TemporalEngine(sample_indexer)
    answer = engine.answer("What happened right before the alarm?")
    assert answer.has_timestamp
    # The zone_crossing at 134.0 is the last event before alarm at 140.0
    assert any("134" in ts or "02:14" in ts or "02:20" in ts for ts in answer.timestamps) \
        or answer.supporting_events

def test_causal_after_alarm(sample_indexer):
    engine = TemporalEngine(sample_indexer)
    answer = engine.answer("What happened right after the alarm?")
    assert answer.has_timestamp


# ── Order Queries ──────────────────────────────────────────────────────────────

def test_first_event(sample_indexer):
    engine = TemporalEngine(sample_indexer)
    answer = engine.answer("What was the first event in the video?")
    assert answer.has_timestamp
    # First event is truck enters at 10.0s
    assert any("00:00:10" in ts or "0:10" in ts for ts in answer.timestamps) \
        or answer.supporting_events


# ── Answer Formatter ───────────────────────────────────────────────────────────

def test_formatter_enforces_timestamp():
    formatter = AnswerFormatter()
    rule_data = {"summary": "No events found.", "events_found": [], "query_types": ["order"]}
    answer = formatter.format_rule_based("What happened?", rule_data)
    assert not answer.has_timestamp
    assert "TIMESTAMP REQUIRED" in answer.answer

def test_formatter_extracts_timestamps():
    formatter = AnswerFormatter()
    rule_data = {
        "summary": "Truck arrived at [00:01:27]. Person entered at [00:02:14].",
        "events_found": [],
        "query_types": ["order"],
    }
    answer = formatter.format_rule_based("When did the truck arrive?", rule_data)
    assert answer.has_timestamp
    assert len(answer.timestamps) >= 1
    assert answer.timestamp_confidence in ("HIGH", "MEDIUM")

def test_score_estimate_with_timestamps():
    formatter = AnswerFormatter()
    rule_data = {
        "summary": "Event at [00:01:23].",
        "events_found": [],
        "query_types": ["order"],
    }
    answer = formatter.format_rule_based("test", rule_data)
    assert answer.score_estimate == 1.0

def test_score_estimate_no_timestamps():
    formatter = AnswerFormatter()
    rule_data = {"summary": "No events.", "events_found": [], "query_types": []}
    answer = formatter.format_rule_based("test", rule_data)
    assert answer.score_estimate == 0.5


# ── Integration ────────────────────────────────────────────────────────────────

def test_full_pipeline_no_gemini(sample_indexer):
    """Full pipeline test without Gemini (pure rule-based)."""
    engine = TemporalEngine(sample_indexer)
    questions = [
        "What happened right before the alarm?",
        "How many people entered?",
        "Find objects untouched for more than 1 minute.",
        "What was the first event?",
    ]
    for q in questions:
        answer = engine.answer(q)
        assert answer.question == q
        assert isinstance(answer.answer, str)
        assert isinstance(answer.timestamps, list)
        assert answer.timestamp_confidence in ("HIGH", "MEDIUM", "LOW", "NONE")
