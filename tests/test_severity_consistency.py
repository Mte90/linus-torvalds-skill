"""Test validate_severity_consistency function with realistic calibration data."""

import pytest

from src.torvalds_skill.distill_data import validate_severity_consistency


def test_no_spurious_warnings_with_matching_distribution():
    """Test that no warnings are emitted when skill text proportions match global distribution."""
    # Build minimal calibration dict matching real structure from data/calibration.json
    calibration = {
        "corpus_stats": {
            "severity_distribution": {
                "reject": {"count": 9110, "percentage": 23.8},
                "request-changes": {"count": 16162, "percentage": 42.2},
                "nitpick": {"count": 2614, "percentage": 6.8},
                "approve": {"count": 2689, "percentage": 7.0},
                "discussion": {"count": 7728, "percentage": 20.2},
            }
        },
        "severity_by_category": {
            "correctness": {
                "reject_rate": 25.0,
                "nitpick_rate": 7.0,
                "request_changes_rate": 40.0,
            }
        },
    }

    # Create skill text with severity mentions matching the global distribution
    # Total mentions = 100 for easy math:
    # - reject: 24 mentions (~23.8%)
    # - request-changes: 42 mentions (~42.2%)
    # - nitpick: 7 mentions (~6.8%)
    skill_text = (
        "critical blocker breaking must-fix " * 6  # 24 reject mentions
        + "revision improve refactor rework " * 10
        + "revision improve "  # 42 request-changes
        + "nit cosmetic style minor nit cosmetic style"  # 7 nitpick mentions
    )

    warnings = validate_severity_consistency(skill_text, calibration)

    # Should have NO spurious warnings when proportions match
    reject_warnings = [w for w in warnings if "reject" in w.lower()]
    nitpick_warnings = [w for w in warnings if "nitpick" in w.lower()]
    request_changes_warnings = [w for w in warnings if "request" in w.lower()]

    assert len(reject_warnings) == 0, f"Unexpected reject warning: {reject_warnings}"
    assert len(nitpick_warnings) == 0, f"Unexpected nitpick warning: {nitpick_warnings}"
    assert len(request_changes_warnings) == 0, (
        f"Unexpected request-changes warning: {request_changes_warnings}"
    )


def test_warning_emitted_for_overrepresented_severity():
    """Test that a warning IS emitted when a severity is genuinely over-represented (>2x)."""
    calibration = {
        "corpus_stats": {
            "severity_distribution": {
                "reject": {"count": 9110, "percentage": 23.8},
                "request-changes": {"count": 16162, "percentage": 42.2},
                "nitpick": {"count": 2614, "percentage": 6.8},
                "approve": {"count": 2689, "percentage": 7.0},
                "discussion": {"count": 7728, "percentage": 20.2},
            }
        },
        "severity_by_category": {
            "correctness": {
                "reject_rate": 25.0,
                "nitpick_rate": 7.0,
                "request_changes_rate": 40.0,
            }
        },
    }

    # Create skill text with reject over-represented (>2x the expected 23.8%)
    # 80 reject mentions vs 10 request-changes vs 10 nitpick = 100 total
    # reject = 80% (expected 23.8%) => 3.36x deviation
    skill_text = (
        "critical blocker breaking must-fix " * 20  # 80 reject mentions
        + "revision improve refactor rework " * 2  # 10 request-changes
        + "nit cosmetic style minor nit cosmetic style minor nit cosmetic"  # 10 nitpick
    )

    warnings = validate_severity_consistency(skill_text, calibration)

    # Should have warning for over-represented reject
    reject_warnings = [
        w for w in warnings if "reject" in w.lower() and "over-represented" in w.lower()
    ]
    assert len(reject_warnings) == 1, (
        f"Expected 1 reject over-representation warning, got: {reject_warnings}"
    )
    # ~3.36x deviation
    assert "3.3" in reject_warnings[0] or "3.4" in reject_warnings[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
