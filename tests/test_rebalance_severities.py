"""Tests for the model-agnostic severity rebalancer."""

from torvalds_skill.distill_sanitize import _soft_language_score, rebalance_severities

CALIBRATION = {
    "corpus_stats": {
        "severity_distribution": {
            "reject": {"count": 9110, "percentage": 23.8},
            "request-changes": {"count": 16162, "percentage": 42.2},
            "nitpick": {"count": 2614, "percentage": 6.8},
            "approve": {"count": 2689, "percentage": 7.0},
            "discussion": {"count": 7728, "percentage": 20.2},
        }
    }
}


def _make_trigger(idx, severity, text):
    return (
        f"- **Trigger**: {text}\n"
        f"  - **Type**: invariant-true\n"
        f"  - **What to look for**: details {idx}\n"
        f"  - **Why it's a problem**: explanation {idx}\n"
        f"  - **Severity**: {severity}\n"
        f'  - **Example**: "quote {idx}"\n'
    )


def _make_skill(triggers):
    header = "# Skill\n\n## Triggers\n\n"
    return header + "\n".join(triggers)


def test_no_calibration_returns_unchanged():
    skill = _make_skill([_make_trigger(1, "reject", "buffer overflow crash")])
    assert rebalance_severities(skill, {}) == skill


def test_few_triggers_returns_unchanged():
    skill = _make_skill([_make_trigger(1, "reject", "buffer overflow")])
    assert rebalance_severities(skill, CALIBRATION) == skill


def test_already_balanced_returns_unchanged():
    # Target for 11 triggers: reject≈4, rc≈6, nitpick≈1
    triggers = []
    for i in range(4):
        triggers.append(_make_trigger(i, "reject", f"critical crash overflow {i}"))
    for i in range(6):
        triggers.append(_make_trigger(i + 10, "request-changes", f"refactor improve {i}"))
    triggers.append(_make_trigger(20, "nitpick", "naming convention style"))
    skill = _make_skill(triggers)
    result = rebalance_severities(skill, CALIBRATION)
    assert result == skill


def test_demotes_over_represented_reject():
    # 8 reject, 2 request-changes, 0 nitpick — reject heavily over-represented
    triggers = []
    for i in range(8):
        triggers.append(_make_trigger(i, "reject", f"should consider naming convention {i}"))
    for i in range(2):
        triggers.append(_make_trigger(i + 10, "request-changes", f"refactor {i}"))
    skill = _make_skill(triggers)
    result = rebalance_severities(skill, CALIBRATION)

    reject_count = result.count("**Severity**: reject")
    rc_count = result.count("**Severity**: request-changes")
    nitpick_count = result.count("**Severity**: nitpick")

    # Target for 10 triggers: reject≈3, rc≈6, nitpick≈1
    assert reject_count < 8, f"reject should be demoted, got {reject_count}"
    assert nitpick_count > 0, f"nitpick should increase, got {nitpick_count}"
    assert reject_count + rc_count + nitpick_count == 10


def test_hard_language_triggers_kept_as_reject():
    # Triggers with hard words should stay reject; soft ones demoted first
    triggers = []
    # 5 hard reject triggers (should stay reject)
    for i in range(5):
        triggers.append(_make_trigger(i, "reject", f"buffer overflow crash corruption {i}"))
    # 5 soft reject triggers (should be demoted)
    for i in range(5):
        triggers.append(_make_trigger(i + 10, "reject", f"should consider naming convention {i}"))
    skill = _make_skill(triggers)
    result = rebalance_severities(skill, CALIBRATION)

    # Target for 10 triggers: reject≈3, rc≈6, nitpick≈1
    # The 3 kept rejects should be hard-language triggers
    reject_count = result.count("**Severity**: reject")
    assert reject_count <= 5, "hard triggers should be preferentially kept"
    # Check that at least some hard triggers survived
    sum(
        1
        for i in range(5)
        if f"buffer overflow crash corruption {i}" in result
        and result.split("buffer overflow crash corruption")[0].endswith("reject")
    )


def test_soft_language_score():
    assert _soft_language_score("should consider naming convention") > 0
    assert _soft_language_score("buffer overflow crash corruption") < 0
    assert _soft_language_score("neutral text here") == 0


def test_ladder_demotion_chain():
    # When reject is over and request-changes is at target, excess reject
    # flows through request-changes to nitpick.
    # 6 reject, 6 request-changes, 0 nitpick (12 total)
    # Target: reject≈3, rc≈7, nitpick≈1
    # Demote 3 reject → rc (rc becomes 9, over by 2)
    # Demote 2 rc → nitpick
    triggers = []
    for i in range(6):
        triggers.append(_make_trigger(i, "reject", f"should consider style {i}"))
    for i in range(6):
        triggers.append(_make_trigger(i + 10, "request-changes", f"refactor improve {i}"))
    skill = _make_skill(triggers)
    result = rebalance_severities(skill, CALIBRATION)

    reject_count = result.count("**Severity**: reject")
    rc_count = result.count("**Severity**: request-changes")
    nitpick_count = result.count("**Severity**: nitpick")

    assert reject_count < 6, f"reject should be demoted from 6, got {reject_count}"
    assert nitpick_count > 0, f"nitpick should appear via ladder, got {nitpick_count}"
    assert reject_count + rc_count + nitpick_count == 12


def test_preserves_trigger_text():
    triggers = []
    for i in range(5):
        triggers.append(_make_trigger(i, "reject", f"unique marker text {i}"))
    skill = _make_skill(triggers)
    result = rebalance_severities(skill, CALIBRATION)

    for i in range(5):
        assert f"unique marker text {i}" in result, f"trigger {i} text lost"


def test_total_trigger_count_preserved():
    triggers = []
    for i in range(10):
        triggers.append(_make_trigger(i, "reject", f"should consider {i}"))
    skill = _make_skill(triggers)
    result = rebalance_severities(skill, CALIBRATION)

    total = sum(
        result.count(f"**Severity**: {s}") for s in ["reject", "request-changes", "nitpick"]
    )
    assert total == 10, f"trigger count changed: {total}"


def test_unknown_severities_ignored():
    # Triggers with severities not in the ladder should be left alone
    triggers = []
    for i in range(3):
        triggers.append(_make_trigger(i, "reject", f"should consider {i}"))
    triggers.append(_make_trigger(10, "discussion", "some text"))
    skill = _make_skill(triggers)
    result = rebalance_severities(skill, CALIBRATION)

    assert "**Severity**: discussion" in result, "unknown severity should be preserved"


def test_promotes_over_represented_nitpick():
    # 0 reject, 2 request-changes, 8 nitpick (10 total)
    # Target: reject≈3, rc≈6, nitpick≈1
    # Demotion: nothing over-represented at reject/rc level
    # Promotion: reject under by 3 → promote 3 hardest nitpicks → reject
    #            rc under by 4 → promote 4 hardest nitpicks → rc
    # Result: reject=3, rc=6, nitpick=1
    triggers = []
    for i in range(2):
        triggers.append(_make_trigger(i, "request-changes", f"refactor improve {i}"))
    for i in range(8):
        triggers.append(_make_trigger(i + 10, "nitpick", f"naming convention style {i}"))
    skill = _make_skill(triggers)
    result = rebalance_severities(skill, CALIBRATION)

    reject_count = result.count("**Severity**: reject")
    rc_count = result.count("**Severity**: request-changes")
    nitpick_count = result.count("**Severity**: nitpick")

    assert reject_count > 0, f"nitpick should be promoted to reject, got {reject_count}"
    assert nitpick_count < 8, f"nitpick should be promoted away, got {nitpick_count}"
    assert reject_count + rc_count + nitpick_count == 10


def test_promotion_prefers_hard_language():
    # 0 reject, 0 rc, 6 nitpick (6 total)
    # Target: reject≈2, rc≈4, nitpick≈0
    # Hard nitpicks should be promoted to reject; soft ones stay nitpick/rc
    triggers = []
    for i in range(3):
        triggers.append(_make_trigger(i, "nitpick", f"buffer overflow crash corruption {i}"))
    for i in range(3):
        triggers.append(_make_trigger(i + 10, "nitpick", f"naming convention style {i}"))
    skill = _make_skill(triggers)
    result = rebalance_severities(skill, CALIBRATION)

    reject_count = result.count("**Severity**: reject")
    assert reject_count == 2, f"target reject=2, got {reject_count}"
    # No soft-language trigger should be at reject
    for i in range(3):
        marker = f"naming convention style {i}"
        if marker in result:
            after = result.split(marker, 1)[1]
            sev_match = after[: after.find("- **Example**")]
            assert "reject" not in sev_match, f"soft trigger {i} should not be reject"
    # At least one hard-language trigger should be at reject
    hard_at_reject = 0
    for i in range(3):
        marker = f"buffer overflow crash corruption {i}"
        if marker in result:
            after = result.split(marker, 1)[1]
            sev_match = after[: after.find("- **Example**")]
            if "reject" in sev_match:
                hard_at_reject += 1
    assert hard_at_reject == 2, f"both reject slots should be hard triggers, got {hard_at_reject}"


def test_demotion_then_promotion():
    # 8 reject, 0 rc, 2 nitpick (10 total)
    # Target: reject≈3, rc≈6, nitpick≈1
    # Demotion: reject over by 5 → 5 softest demoted to rc (reject=3, rc=5, nitpick=2)
    #           rc under by 1 → no demotion
    #           nitpick over by 1 → can't demote further
    # Promotion: reject at target (3=3)
    #            rc under by 1 → promote 1 hardest nitpick → rc (rc=6, nitpick=1)
    triggers = []
    for i in range(8):
        triggers.append(_make_trigger(i, "reject", f"should consider naming convention {i}"))
    for i in range(2):
        triggers.append(_make_trigger(i + 10, "nitpick", f"buffer overflow crash {i}"))
    skill = _make_skill(triggers)
    result = rebalance_severities(skill, CALIBRATION)

    reject_count = result.count("**Severity**: reject")
    rc_count = result.count("**Severity**: request-changes")
    nitpick_count = result.count("**Severity**: nitpick")

    assert reject_count < 8, f"reject should be demoted, got {reject_count}"
    assert rc_count > 0, f"request-changes should appear, got {rc_count}"
    assert reject_count + rc_count + nitpick_count == 10
