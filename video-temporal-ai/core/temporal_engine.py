"""
temporal_engine.py
__________________
The core reasoning engine that answers temporal questions using the event index.

Handles all query categories:
  _ ORDER    _ "What happened first/after/before X?"
  _ COUNT    _ "How many times did Y occur?"
  _ DURATION _ "How long did Z last? / Find things untouched > 2 min"
  _ CAUSAL   _ "What happened right before/after the alarm?"
  _ CONDITIONAL _ "Who entered after the truck arrived?"

Every answer includes timestamps. No timestamp = query returns incomplete.
"""

from __future__ import annotations

import re
import json
from typing import Optional

from core.event_indexer import EventIndexer, Event
from core.video_processor import seconds_to_timestamp, timestamp_to_seconds
from core.answer_formatter import AnswerFormatter, TemporalAnswer


# __ Query Type Classifier _____________________________________________________

ORDER_KEYWORDS = ["first", "after", "before", "then", "next", "last", "order",
                  "sequence", "happened", "preceded", "followed"]
COUNT_KEYWORDS = ["how many", "count", "times", "frequency", "often", "number of"]
DURATION_KEYWORDS = ["how long", "duration", "minutes", "seconds", "hours",
                     "untouched", "stationary", "still", "stayed", "remained"]
CAUSAL_KEYWORDS = ["before the", "after the", "caused", "triggered", "led to",
                   "right before", "right after", "immediately"]
TRACK_KEYWORDS = ["same person", "same vehicle", "same object", "re-entered",
                  "came back", "returned"]


def classify_query(question: str) -> list[str]:
    """Returns list of detected query types."""
    q = question.lower()
    types_found = []
    if any(k in q for k in COUNT_KEYWORDS):
        types_found.append("count")
    if any(k in q for k in DURATION_KEYWORDS):
        types_found.append("duration")
    if any(k in q for k in CAUSAL_KEYWORDS):
        types_found.append("causal")
    if any(k in q for k in TRACK_KEYWORDS):
        types_found.append("tracking")
    if any(k in q for k in ORDER_KEYWORDS) or not types_found:
        types_found.append("order")
    return types_found


# __ Temporal Engine ___________________________________________________________

class TemporalEngine:
    """
    Answers temporal questions using the EventIndexer + AnswerFormatter.
    Works standalone (from tracker data) or combined with Gemini answers.
    """

    def __init__(self, indexer: EventIndexer):
        self.indexer = indexer
        self.formatter = AnswerFormatter()

    # __ Main Entry Point ______________________________________________________

    def answer(
        self,
        question: str,
        gemini_answer: Optional[dict] = None,
    ) -> TemporalAnswer:
        """
        Answer a temporal question. Combines rule-based reasoning from the
        event index with (optional) Gemini's natural language answer.
        """
        query_types = classify_query(question)
        rule_based = self._rule_based_answer(question, query_types)

        if gemini_answer:
            return self.formatter.merge(
                question=question,
                rule_based=rule_based,
                gemini_answer=gemini_answer,
            )
        else:
            return self.formatter.format_rule_based(question, rule_based)

    # __ Rule-based reasoning __________________________________________________

    def _rule_based_answer(self, question: str, query_types: list[str]) -> dict:
        q = question.lower()
        result = {"query_types": query_types, "events_found": [], "summary": ""}

        if "count" in query_types:
            result.update(self._handle_count_query(q))

        if "duration" in query_types or ("stationary" in q or "untouched" in q):
            result.update(self._handle_duration_query(q))

        if "causal" in query_types:
            result.update(self._handle_causal_query(q))

        if "order" in query_types:
            result.update(self._handle_order_query(q))

        return result

    # __ Count queries _________________________________________________________

    def _handle_count_query(self, question: str) -> dict:
        """How many times did X happen?"""
        events = self.indexer.events
        label_match = self._extract_object_label(question)
        event_type_match = self._extract_event_type(question)

        if label_match:
            relevant = [
                e for e in events
                if e.label and label_match in e.label.lower()
                and e.event_type == "object_enters_frame"
            ]
        elif event_type_match:
            relevant = [e for e in events if event_type_match in e.event_type]
        else:
            relevant = []

        occurrences = [
            {"timestamp": e.timestamp_str, "event": e.event_type,
             "detail": e.display_name or e.label}
            for e in relevant
        ]
        return {
            "count": len(relevant),
            "occurrences": occurrences,
            "events_found": relevant,
            "summary": (
                f"Found {len(relevant)} occurrence(s)"
                + (f" of '{label_match}'" if label_match else "")
                + "."
            ),
        }

    # __ Duration queries ______________________________________________________

    def _handle_duration_query(self, question: str) -> dict:
        """How long did X stay? / Find objects untouched > 2 min."""
        # Extract minimum duration from question (e.g., "2 minutes", "30 seconds")
        min_dur = self._extract_min_duration(question) or 120.0  # default 2 min

        stationary_events = self.indexer.get_events_by_type("stationary_object")
        # Also filter by label if mentioned
        label = self._extract_object_label(question)
        if label:
            stationary_events = [
                e for e in stationary_events
                if e.label and label in e.label.lower()
            ]
        # Filter by duration
        qualifying = [
            e for e in stationary_events
            if (e.duration_sec or 0) >= min_dur
        ]

        results = []
        for e in qualifying:
            end_ts = e.metadata.get("end_timestamp", "unknown")
            results.append({
                "display_name": e.display_name or e.label,
                "start_timestamp": e.timestamp_str,
                "end_timestamp": end_ts,
                "duration_sec": e.duration_sec,
            })

        summary = (
            f"Found {len(qualifying)} object(s) stationary for _{min_dur/60:.1f} minute(s)."
            if qualifying else
            f"No objects found stationary for _{min_dur/60:.1f} minute(s)."
        )

        return {
            "stationary_objects": results,
            "events_found": qualifying,
            "summary": summary,
        }

    # __ Causal queries ________________________________________________________

    def _handle_causal_query(self, question: str) -> dict:
        """What happened right before/after X?"""
        q = question.lower()
        is_before = "before" in q
        is_after = "after" in q

        # Extract reference event from question
        reference_event = self._find_reference_event(question)
        if not reference_event:
            return {"summary": "Could not identify the reference event in the question.",
                    "events_found": []}

        ref_sec = reference_event.timestamp_sec
        if is_before:
            neighbor = self.indexer.get_nearest_event_before(ref_sec)
        else:
            neighbor = self.indexer.get_nearest_event_after(ref_sec)

        if not neighbor:
            return {
                "reference_event": reference_event.to_dict(),
                "events_found": [reference_event],
                "summary": f"Reference event at [{reference_event.timestamp_str}]. No adjacent event found.",
            }

        direction = "before" if is_before else "after"
        time_diff = abs(neighbor.timestamp_sec - ref_sec)
        return {
            "reference_event": reference_event.to_dict(),
            "adjacent_event": neighbor.to_dict(),
            "time_difference_sec": round(time_diff, 1),
            "events_found": [reference_event, neighbor],
            "summary": (
                f"The event {direction} [{reference_event.timestamp_str}] is: "
                f"'{neighbor.event_type}' at [{neighbor.timestamp_str}] "
                f"({time_diff:.1f}s apart)."
            ),
        }

    # __ Order queries _________________________________________________________

    def _handle_order_query(self, question: str) -> dict:
        """What happened first/next/last?"""
        q = question.lower()
        label = self._extract_object_label(question)
        events = self.indexer.events

        if label:
            events = [e for e in events if e.label and label in e.label.lower()]

        if not events:
            return {"events_found": [], "summary": "No relevant events found in the timeline."}

        ordered = sorted(events, key=lambda e: e.timestamp_sec)
        timeline_str = " _ ".join(
            f"[{e.timestamp_str}] {e.event_type} ({e.display_name or ''})"
            for e in ordered[:10]  # top 10
        )
        return {
            "first_event": ordered[0].to_dict() if ordered else None,
            "last_event": ordered[-1].to_dict() if ordered else None,
            "timeline": [e.to_dict() for e in ordered[:15]],
            "events_found": ordered[:15],
            "summary": f"Timeline: {timeline_str}",
        }

    # __ Utility Helpers _______________________________________________________

    def _extract_object_label(self, question: str) -> Optional[str]:
        """Extract the object/person label from the question."""
        q = question.lower()
        # Order matters: try specific labels first to avoid substring false positives
        # Use word-boundary matching to prevent "man" matching "many"
        # Note: 'object' is deliberately excluded as it's too generic
        for label in ["truck", "car", "vehicle", "bicycle", "motorcycle",
                      "person", "people", "woman", "man",
                      "machine", "box", "package", "bag"]:
            if re.search(r'\b' + label + r'\b', q):
                if label == "people":
                    return "person"
                return label
        return None

    def _extract_event_type(self, question: str) -> Optional[str]:
        q = question.lower()
        if "stop" in q or "stopped" in q:
            return "machine_stops"
        if "alarm" in q:
            return "alarm_detected"
        if "enter" in q or "entered" in q:
            return "object_enters_frame"
        if "exit" in q or "left" in q:
            return "object_exits_frame"
        return None

    def _extract_min_duration(self, question: str) -> Optional[float]:
        """Extract minimum duration in seconds from question text."""
        # Match patterns like "2 minutes", "30 seconds", "1.5 hours"
        match = re.search(r"(\d+(?:\.\d+)?)\s*(minute|second|hour)s?", question.lower())
        if not match:
            return None
        val = float(match.group(1))
        unit = match.group(2)
        if unit == "minute":
            return val * 60
        if unit == "hour":
            return val * 3600
        return val  # seconds

    def _find_reference_event(self, question: str) -> Optional[Event]:
        """Find the event referenced in the question (e.g., 'the alarm', 'the truck')."""
        q = question.lower()
        # Look for alarm
        if "alarm" in q:
            candidates = self.indexer.get_events_by_type("alarm_detected")
            if candidates:
                return candidates[0]
        # Look for truck/vehicle
        if "truck" in q or "vehicle" in q:
            candidates = [
                e for e in self.indexer.events
                if e.label in ("truck", "car", "vehicle", "bus")
            ]
            if candidates:
                return candidates[0]
        # Look for machine stop
        if "machine" in q and ("stop" in q or "stopped" in q):
            candidates = self.indexer.get_events_by_type("machine_stops")
            if candidates:
                return candidates[0]
        # Fallback: look for any gemini_event or scene_change
        for e in self.indexer.events:
            if e.source == "gemini":
                return e
        return None

    # __ Timeline Export _______________________________________________________

    def get_timeline_for_prompt(self, max_events: int = 50) -> str:
        """Get a compact timeline string suitable for embedding in a Gemini prompt."""
        events = self.indexer.events[:max_events]
        lines = [
            f"[{e.timestamp_str}] {e.event_type}"
            + (f" _ {e.display_name}" if e.display_name else "")
            + (f" in {e.zone}" if e.zone else "")
            + (f" (duration: {e.duration_sec:.0f}s)" if e.duration_sec else "")
            for e in events
        ]
        return "\n".join(lines)
