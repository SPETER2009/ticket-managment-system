"""
answer_formatter.py
____________________
Enforces the hackathon rule: EVERY answer must have a timestamp.
Merges rule-based tracker answers with Gemini natural language answers.
Outputs structured TemporalAnswer objects.
"""

from __future__ import annotations

import re
import json
from dataclasses import dataclass, field
from typing import Optional


# __ Output Data Class _________________________________________________________

@dataclass
class TemporalAnswer:
    question: str
    answer: str                     # Final human-readable answer
    timestamps: list[str]           # All timestamps mentioned in the answer
    timestamp_confidence: str       # "HIGH" | "MEDIUM" | "LOW" | "NONE"
    has_timestamp: bool             # Rule enforcement flag
    supporting_events: list[dict] = field(default_factory=list)
    rule_based_summary: str = ""
    gemini_answer: str = ""
    query_types: list[str] = field(default_factory=list)
    score_estimate: float = 1.0     # Estimated point score (0_1)

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "answer": self.answer,
            "timestamps": self.timestamps,
            "timestamp_confidence": self.timestamp_confidence,
            "has_timestamp": self.has_timestamp,
            "supporting_events": self.supporting_events[:10],
            "rule_based_summary": self.rule_based_summary,
            "query_types": self.query_types,
            "score_estimate": self.score_estimate,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


# __ Formatter _________________________________________________________________

class AnswerFormatter:
    """
    Ensures every answer includes timestamps.
    Merges rule-based (fast, precise timestamps) + Gemini (rich language) answers.
    """

    TIMESTAMP_PATTERN = re.compile(
        r"\[?(\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?)\]?"
    )
    NO_TIMESTAMP_SUFFIX = (
        "\n\n__ [TIMESTAMP REQUIRED] The system could not extract a precise timestamp "
        "for this answer. The event likely exists but the exact time is uncertain."
    )

    # __ Format from rule-based only ___________________________________________

    def format_rule_based(self, question: str, rule_data: dict) -> TemporalAnswer:
        summary = rule_data.get("summary", "No answer found in tracker data.")
        events = rule_data.get("events_found", [])
        event_dicts = [
            e.to_dict() if hasattr(e, "to_dict") else e
            for e in events
        ]

        timestamps = self._extract_timestamps(summary)
        for e in event_dicts:
            if "timestamp_str" in e:
                timestamps.append(e["timestamp_str"])
        timestamps = list(dict.fromkeys(timestamps))  # deduplicate, preserve order

        has_ts = len(timestamps) > 0
        answer = summary
        if not has_ts:
            answer += self.NO_TIMESTAMP_SUFFIX

        return TemporalAnswer(
            question=question,
            answer=answer,
            timestamps=timestamps,
            timestamp_confidence=self._rate_confidence(timestamps, summary),
            has_timestamp=has_ts,
            supporting_events=event_dicts,
            rule_based_summary=summary,
            query_types=rule_data.get("query_types", []),
            score_estimate=1.0 if has_ts else 0.5,
        )

    # __ Merge rule-based + Gemini ______________________________________________

    def merge(
        self,
        question: str,
        rule_based: dict,
        gemini_answer: dict,
    ) -> TemporalAnswer:
        """
        Combine rule-based event index with Gemini's natural language answer.
        Strategy: Use Gemini's richer answer but inject tracker timestamps for accuracy.
        """
        gemini_text = gemini_answer.get("answer", "")
        gemini_timestamps = gemini_answer.get("timestamps_found", [])
        rule_summary = rule_based.get("summary", "")
        events = rule_based.get("events_found", [])
        event_dicts = [
            e.to_dict() if hasattr(e, "to_dict") else e
            for e in events
        ]

        # Collect all timestamps from both sources
        rule_timestamps = self._extract_timestamps(rule_summary)
        for e in event_dicts:
            if "timestamp_str" in e:
                rule_timestamps.append(e["timestamp_str"])

        all_timestamps = list(dict.fromkeys(gemini_timestamps + rule_timestamps))

        # Build combined answer: Gemini answer is primary, rule-based adds evidence
        combined = gemini_text
        if rule_summary and rule_summary != "No relevant events found in the timeline.":
            combined += f"\n\n**_ Tracker Evidence:** {rule_summary}"

        # Enforce timestamp rule
        has_ts = len(all_timestamps) > 0
        if not has_ts:
            combined += self.NO_TIMESTAMP_SUFFIX

        confidence = gemini_answer.get("timestamp_confidence", "MEDIUM")
        if all_timestamps and confidence == "NONE":
            confidence = "MEDIUM"

        return TemporalAnswer(
            question=question,
            answer=combined,
            timestamps=all_timestamps,
            timestamp_confidence=confidence,
            has_timestamp=has_ts,
            supporting_events=event_dicts,
            rule_based_summary=rule_summary,
            gemini_answer=gemini_text,
            query_types=rule_based.get("query_types", []),
            score_estimate=1.0 if (has_ts and confidence in ("HIGH", "MEDIUM")) else 0.5,
        )

    # __ Helpers _______________________________________________________________

    def _extract_timestamps(self, text: str) -> list[str]:
        return self.TIMESTAMP_PATTERN.findall(text)

    def _rate_confidence(self, timestamps: list[str], text: str) -> str:
        if not timestamps:
            return "NONE"
        hedging = ["approximately", "around", "about", "roughly", "unclear", "possibly"]
        if any(h in text.lower() for h in hedging):
            return "MEDIUM"
        return "HIGH" if len(timestamps) >= 1 else "LOW"
