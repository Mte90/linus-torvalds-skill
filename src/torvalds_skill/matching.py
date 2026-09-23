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
