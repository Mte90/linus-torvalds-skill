"""Shared severity vocabulary for ground truth and model findings."""

MODEL_SEVERITIES: list[str] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

GROUND_TRUTH_SEVERITIES: list[str] = ["reject", "request-changes", "nitpick"]

SEVERITY_MAP: dict[str, str] = {
    "reject": "CRITICAL",
    "request-changes": "HIGH",
    "nitpick": "MEDIUM",
}


def map_severity(severity: str) -> str:
    """Map a ground-truth severity to the model vocabulary; unknown values pass through."""
    return SEVERITY_MAP.get(severity, severity)
