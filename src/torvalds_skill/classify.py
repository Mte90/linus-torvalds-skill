"""
classify.py — rule-based filter: is this email a code review?

No LLM, no external calls. Pure heuristics on headers and body.

A review is:
  - a reply (In-Reply-To set or subject starts with Re:)
  - NOT a release announcement
  - NOT a pure merge/pull confirmation
  - substantive (body > 100 chars after cleaning)
  - NOT a pure ack/nak with no explanation
"""

from __future__ import annotations

import re

from .models import EmailRecord

# subjects that are NOT reviews
ANNOUNCE_RE = re.compile(
    r"^(Linux\s+\d|git\s+pull|pull\s+request|merge\s+(branch|tag))",
    re.IGNORECASE,
)

# pull requests Torvalds sends himself — administrative, not reviews
# no ^ anchor: must catch "Re: [GIT PULL]" replies too
GIT_PULL_RE = re.compile(r"\[GIT\s+PULL\]", re.IGNORECASE)

# RFC discussions — not code reviews
RFC_RE = re.compile(r"\[RFC\]", re.IGNORECASE)

# Pure patch submissions (not reviews of others' code)
# Match both "[PATCH" and "Re: [PATCH" subjects
PATCH_ONLY_RE = re.compile(r"^\s*(Re:\s*)*\[PATCH", re.IGNORECASE)

# pure acks with no substance
PURE_ACK_RE = re.compile(
    r"^(Acked-by|Nacked-by|Signed-off-by|Applied\.?\s*$|"
    r"Pulled\.?\s*$|Merged\.?\s*$)",
    re.IGNORECASE,
)

# very short bodies that are just sign-offs
SIGNOFF_ONLY_RE = re.compile(
    r"^(Acked-by|Nacked-by|Signed-off-by|Reviewed-by|Tested-by|"
    r"Reported-by|Suggested-by|Co-developed-by):.*$",
    re.IGNORECASE,
)

MIN_BODY_LEN = 100


def is_review(email: EmailRecord) -> bool:
    """Return True if this email is likely a code review by Torvalds."""
    subject = email.subject.strip()

    # must be a reply
    is_reply = (
        email.in_reply_to is not None
        or subject.lower().startswith("re:")
    )
    if not is_reply:
        # Torvalds sometimes starts threads with review feedback
        # accept if subject references a patch and body is substantial
        if not re.search(r"\bpatch\b", subject, re.IGNORECASE):
            return False

    # exclude announcements
    if ANNOUNCE_RE.match(subject):
        return False

    # exclude [GIT PULL] requests
    if GIT_PULL_RE.search(subject):
        return False

    # exclude RFC discussions — not code reviews
    if RFC_RE.search(subject):
        return False

    # exclude pure patch submissions (not reviews of others' code)
    if PATCH_ONLY_RE.match(subject):
        return False

    body = email.body.strip()

    # too short to be substantive
    if len(body) < MIN_BODY_LEN:
        return False

    # pure ack/sign-off with nothing else
    lines = [l.strip() for l in body.splitlines() if l.strip()]
    non_signoff = [
        l for l in lines
        if not SIGNOFF_ONLY_RE.match(l)
    ]
    if not non_signoff:
        return False

    # check the body has some technical substance
    # (code references, function names, explanations)
    # rather than being a one-liner + signoff
    substantive_lines = [
        l for l in non_signoff
        if len(l) > 30  # real sentences, not just "Agreed."
    ]
    if len(substantive_lines) < 1:
        return False

    return True


def classify_corpus(emails):
    """Yield (email, label) tuples. label: 'review' | 'other'."""
    for email in emails:
        label = "review" if is_review(email) else "other"
        yield email, label
