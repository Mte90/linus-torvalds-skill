from torvalds_skill.matching import LINE_TOLERANCE, match_finding_to_bug, normalize_filename


def _bug(line, severity="reject", category="logic"):
    return {"line": line, "severity": severity, "category": category, "description": "bug"}


class TestNormalizeFilename:
    def test_strips_directory(self):
        assert normalize_filename("src/auth/handlers.py") == "handlers.py"

    def test_lowercases(self):
        assert normalize_filename("Auth.PY") == "auth.py"

    def test_alias_short_forms(self):
        assert normalize_filename("server.c") == "smallchat-server.c"
        assert normalize_filename("client.c") == "smallchat-client.c"

    def test_canonical_names_unchanged(self):
        assert normalize_filename("smallchat-server.c") == "smallchat-server.c"


class TestMatchFindingToBug:
    def test_same_file_within_tolerance_matches(self):
        bugs = [_bug(100)]
        finding = {"file": "a/auth.py", "line": 104}
        assert match_finding_to_bug(finding, bugs, "auth.py") == bugs[0]

    def test_boundary_five_matches_six_does_not(self):
        bugs = [_bug(100)]
        assert match_finding_to_bug({"file": "auth.py", "line": 105}, bugs, "auth.py") == bugs[0]
        assert match_finding_to_bug({"file": "auth.py", "line": 106}, bugs, "auth.py") is None

    def test_different_file_never_matches(self):
        bugs = [_bug(100)]
        assert match_finding_to_bug({"file": "other.py", "line": 100}, bugs, "auth.py") is None

    def test_null_finding_line_never_matches(self):
        bugs = [_bug(100)]
        assert match_finding_to_bug({"file": "auth.py", "line": None}, bugs, "auth.py") is None

    def test_empty_finding_file_never_matches(self):
        bugs = [_bug(100)]
        assert match_finding_to_bug({"file": "", "line": 100}, bugs, "auth.py") is None

    def test_null_bug_lines_skipped(self):
        bugs = [{"line": None}, _bug(100)]
        assert match_finding_to_bug({"file": "auth.py", "line": 100}, bugs, "auth.py") == bugs[1]

    def test_alias_match(self):
        bugs = [_bug(50)]
        assert (
            match_finding_to_bug({"file": "server.c", "line": 52}, bugs, "smallchat-server.c")
            == bugs[0]
        )

    def test_returns_first_matching_bug(self):
        bugs = [_bug(98), _bug(101)]
        assert match_finding_to_bug({"file": "auth.py", "line": 99}, bugs, "auth.py") == bugs[0]

    def test_tolerance_constant(self):
        assert LINE_TOLERANCE == 5
