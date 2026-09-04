"""CLI wiring tests: flags must reach the stage functions unchanged."""

from unittest.mock import patch

from torvalds_skill.cli import stage_distill


def _run_stage_distill(tmp_path, **kwargs):
    patterns = tmp_path / "patterns.json"
    patterns.write_text("[]")
    with (
        patch("torvalds_skill.cli.PATTERNS", patterns),
        patch("torvalds_skill.cli.distill_skill") as mock_distill,
    ):
        stage_distill(top_n=40, **kwargs)
    return mock_distill


def test_stage_distill_passes_distill_mode(tmp_path):
    """--distill-mode value must reach distill_skill (regression: TypeError)."""
    mock_distill = _run_stage_distill(tmp_path, model="glm5.2", distill_mode="two-stage")
    assert mock_distill.call_count == 1
    assert mock_distill.call_args.kwargs["distill_mode"] == "two-stage"


def test_stage_distill_mode_defaults_to_none(tmp_path):
    """No flag → distill_mode None so the profile decides."""
    mock_distill = _run_stage_distill(tmp_path, model="gpt-oss-120b")
    assert mock_distill.call_args.kwargs["distill_mode"] is None


def test_stage_distill_passes_single_call_flag(tmp_path):
    """Legacy --single-call flag still plumbed through."""
    mock_distill = _run_stage_distill(tmp_path, model="glm5.2", single_call=True)
    assert mock_distill.call_args.kwargs["single_call"] is True
