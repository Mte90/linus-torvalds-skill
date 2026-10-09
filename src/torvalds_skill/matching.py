"""Shared finding-to-ground-truth-bug matching.

Single source of truth for both report pipelines:
- report/build_comparison.py (comparison.md)
- scripts/run_eval.py and scripts/render_cross.py (cross_matrix.md)
"""

ALIAS_MAP: dict[str, str] = {
    "server.c": "smallchat-server.c",
    "client.c": "smallchat-client.c",
}

LINE_TOLERANCE = 5


def resume_key(record: dict) -> tuple[object, ...]:
    """Identity of an evaluation record for de-duplicating appended results.

    The eval pipeline is append-only and crash-safe, and it deliberately
    re-runs records poisoned by a judge failure. Because the replacement is
    appended rather than written in place, the file can end up holding several
    records with the same key: a poisoned one and its re-run. Readers must
    therefore keep the last record per key, matching how the resume index itself
    resolves collisions.

    Records without a ``rep`` field are treated as repetition 0, so files written
    before repetitions existed still de-duplicate correctly.
    """
    return (
        record.get("diff_id"),
        record.get("model"),
        record.get("skill") or record.get("model"),
        record.get("rep", 0),
    )


def dedupe_records(records: list[dict]) -> list[dict]:
    """Drop superseded evaluation records, keeping the last one written per key.

    Only records carrying a ``diff_id`` are candidates: ground-truth diff files
    use ``id`` instead and have no model, so keying them here would collapse the
    whole dataset into one record. Those pass through untouched, in order.
    """
    latest: dict[tuple[object, ...], dict] = {}
    for record in records:
        if "diff_id" in record:
            latest[resume_key(record)] = record

    if len(latest) == sum(1 for r in records if "diff_id" in r):
        return list(records)

    merged: list[dict] = []
    kept = iter(latest.values())
    for record in records:
        if "diff_id" in record:
            try:
                merged.append(next(kept))
            except StopIteration:
                break
        else:
            merged.append(record)
    return merged


def finding_identity(finding: dict, diff_id: str | None) -> tuple[object, ...]:
    """Identity of a finding for deduplication across evaluation repetitions.

    ``--repetitions`` re-runs the same diff, so an identical finding recurs once
    per repetition. Precision, Detection Score and the severity/category rankings
    must measure distinct findings, not how many times a diff was re-run, so both
    report pipelines deduplicate on this key.

    Args:
        finding: Finding dict from an evaluation record.
        diff_id: Ground-truth diff the finding matched, or None when unmatched.

    Returns:
        Hashable tuple identifying the finding across repetitions.
    """
    text = (finding.get("issue") or finding.get("title") or "").strip().lower()
    return (
        diff_id,
        normalize_filename(finding.get("file", "")),
        finding.get("line"),
        text,
    )


def normalize_filename(name: str) -> str:
    """Normalize a file path to its canonical lowercase basename."""
    name = name.strip().lower().split("/")[-1]
    return ALIAS_MAP.get(name, name)


def match_finding_to_bug(finding: dict, bugs: list[dict], diff_file: str = "") -> dict | None:
    """Match a finding to a ground-truth bug using file identity and line tolerance.

    Bugs inherit their file from the parent diff record (they carry only
    line/category/severity/description), so the caller passes the diff's file.

    Args:
        finding: Finding dict with 'file' and 'line' keys.
        bugs: List of bug dicts with 'line' keys.
        diff_file: File path from the parent diff record.

    Returns:
        Matching bug dict if found (same file, line within LINE_TOLERANCE), None otherwise.
    """
    finding_file = finding.get("file", "")
    finding_line = finding.get("line")

    if finding_line is None or not finding_file or not diff_file:
        return None

    if normalize_filename(finding_file) != normalize_filename(diff_file):
        return None

    for bug in bugs:
        bug_line = bug.get("line")

        if bug_line is None:
            continue

        if abs(finding_line - bug_line) <= LINE_TOLERANCE:
            return bug

    return None
