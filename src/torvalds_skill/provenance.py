"""Single source of truth for evaluation-data provenance statements.

Both report generators must declare which reviewer-prompt version produced the
numbers they render. Hardcoding that text per generator lets the two reports
drift apart and lets a report claim clean data while it was rendered from a
contaminated run, so the text lives here and the caller states the provenance.
"""

from typing import Literal

EvalProvenance = Literal["decontaminated", "pre-decontamination"]

_BANNERS: dict[EvalProvenance, str] = {
    "decontaminated": (
        "> **Evaluation provenance:** the reviewer prompt carried only the "
        "code under review, never the ground-truth bug list"
        " (enforced by regression tests in `tests/test_eval.py`). "
        "Every number below therefore measures detection, not transcription. Judge: GLM5.2, "
        "a fixed external model scored at generation time via `--judge-model`."
    ),
    "pre-decontamination": (
        "> **WARNING: pre-decontamination data.** The reviewer prompt for this eval run included "
        "the ground-truth bug list (removed afterwards), so every number below measures "
        "answer-key transcription fidelity, not detection ability. A decontaminated re-run is pending."
    ),
}

_LIMITATIONS: dict[EvalProvenance, str] = {
    "decontaminated": (
        "- **Prompt provenance**: reviewers never saw the ground-truth bug list, so these "
        "numbers measure detection against the ground-truth bug list."
    ),
    "pre-decontamination": (
        "- **Pre-decontamination status**: the reviewer prompt initially included ground truth "
        "(subsequently removed); calibration/generalization numbers measure transcription "
        "fidelity, not detection."
    ),
}


def _lookup(table: dict[EvalProvenance, str], provenance: str, kind: str) -> str:
    if provenance not in table:
        raise ValueError(
            f"Unknown evaluation provenance {provenance!r} for {kind}; "
            f"expected one of {sorted(table)}"
        )
    return table[provenance]


def banner(provenance: str) -> str:
    """Return the report-header banner stating which prompt version produced the data."""
    return _lookup(_BANNERS, provenance, "banner")


def limitation(provenance: str) -> str:
    """Return the Limitations-section bullet stating which prompt version produced the data."""
    return _lookup(_LIMITATIONS, provenance, "limitation")
