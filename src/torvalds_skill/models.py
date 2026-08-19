"""
models.py — dataclasses shared across pipeline stages.

EmailRecord: one parsed email from the corpus.
ReviewMove: one actionable reviewing principle extracted from an email.
Pattern: a recurring trigger→principle cluster across many emails.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

SEVERITIES = ("reject", "request-changes", "nitpick", "approve", "discussion")

CATEGORIES = (
    "api-stability",
    "performance",
    "correctness",
    "complexity",
    "style",
    "process",
    "error-handling",
    "concurrency",
    "memory-safety",
    "abstraction",
    "testing",
    "documentation",
    "other",
    "security",
)


@dataclass(frozen=True)
class EmailRecord:
    message_id: str
    from_name: str
    from_email: str
    date: str
    subject: str
    in_reply_to: str | None
    body: str
    to: str = ""
    cc: str = ""

    @classmethod
    def from_jsonl_line(cls, line: str) -> EmailRecord:
        d = json.loads(line)
        return cls(**d)


@dataclass(frozen=True)
class ReviewMove:
    email_message_id: str
    email_date: str
    trigger: str
    principle: str
    response: str
    severity: str
    category: str


@dataclass
class Pattern:
    category: str
    principle: str
    count: int
    example_triggers: list[str] = field(default_factory=list)
    example_responses: list[str] = field(default_factory=list)
    severities: dict[str, int] = field(default_factory=dict)


def iter_corpus(jsonl_path: Path):
    """Yield EmailRecord objects from corpus.jsonl."""
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield EmailRecord.from_jsonl_line(line)


def iter_moves(jsonl_path: Path):
    """Yield ReviewMove objects from a moves jsonl file."""
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            for move in d.get("moves", []):
                yield ReviewMove(
                    email_message_id=d["email_message_id"],
                    email_date=d["email_date"],
                    trigger=move["trigger"],
                    principle=move["principle"],
                    response=move["response"],
                    severity=move["severity"],
                    category=move["category"],
                )
