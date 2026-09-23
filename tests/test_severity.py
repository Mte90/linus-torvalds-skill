from torvalds_skill.severity import (
    GROUND_TRUTH_SEVERITIES,
    MODEL_SEVERITIES,
    SEVERITY_MAP,
    map_severity,
)


def test_ground_truth_order():
    assert GROUND_TRUTH_SEVERITIES == ["reject", "request-changes", "nitpick"]


def test_model_order():
    assert MODEL_SEVERITIES == ["CRITICAL", "HIGH", "MEDIUM", "LOW"]


def test_severity_map_covers_ground_truth():
    for sev in GROUND_TRUTH_SEVERITIES:
        assert sev in SEVERITY_MAP


def test_map_severity_known_values():
    assert map_severity("reject") == "CRITICAL"
    assert map_severity("request-changes") == "HIGH"
    assert map_severity("nitpick") == "MEDIUM"


def test_map_severity_unknown_passthrough():
    assert map_severity("HIGH") == "HIGH"
