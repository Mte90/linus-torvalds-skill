"""Tests for the skip list logic in cli.py.

The skip list persists message_ids of emails that returned 0 moves
(announcements, git-pulls, short acks). Future runs with --resume
skip them, saving API calls on emails known to produce no signal.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from torvalds_skill import cli


class TestLoadSkipList:
    def test_returns_empty_set_when_file_missing(self, tmp_path):
        with patch.object(cli, "SKIP_LIST", tmp_path / "nonexistent.json"):
            result = cli._load_skip_list()
        assert result == set()

    def test_loads_line_delimited_json(self, tmp_path):
        skip_file = tmp_path / "skip_list.json"
        skip_file.write_text(
            json.dumps("id1@x") + "\n" + json.dumps("id2@x") + "\n",
            encoding="utf-8",
        )
        with patch.object(cli, "SKIP_LIST", skip_file):
            result = cli._load_skip_list()
        assert result == {"id1@x", "id2@x"}

    def test_skips_blank_lines(self, tmp_path):
        skip_file = tmp_path / "skip_list.json"
        skip_file.write_text(
            json.dumps("id1@x") + "\n\n" + json.dumps("id2@x") + "\n",
            encoding="utf-8",
        )
        with patch.object(cli, "SKIP_LIST", skip_file):
            result = cli._load_skip_list()
        assert result == {"id1@x", "id2@x"}

    def test_handles_corrupt_file_gracefully(self, tmp_path):
        skip_file = tmp_path / "skip_list.json"
        skip_file.write_text("not json at all\n", encoding="utf-8")
        with patch.object(cli, "SKIP_LIST", skip_file):
            result = cli._load_skip_list()
        assert result == set()

    def test_handles_partial_corrupt_file(self, tmp_path):
        """Valid lines before corrupt one should load; corrupt raises and stops."""
        skip_file = tmp_path / "skip_list.json"
        skip_file.write_text(
            json.dumps("good@x") + "\n" + "BROKEN\n",
            encoding="utf-8",
        )
        with patch.object(cli, "SKIP_LIST", skip_file):
            result = cli._load_skip_list()
        # json.JSONDecodeError on "BROKEN" triggers except, returns ids so far
        assert "good@x" in result


class TestSaveSkipId:
    def test_appends_to_file(self, tmp_path):
        skip_file = tmp_path / "skip_list.json"
        skip_file.write_text(json.dumps("existing@x") + "\n", encoding="utf-8")

        with patch.object(cli, "SKIP_LIST", skip_file):
            cli._save_skip_id("new@x")

        lines = skip_file.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0]) == "existing@x"
        assert json.loads(lines[1]) == "new@x"

    def test_creates_file_if_missing(self, tmp_path):
        skip_file = tmp_path / "skip_list.json"
        with patch.object(cli, "SKIP_LIST", skip_file):
            cli._save_skip_id("first@x")
        lines = skip_file.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0]) == "first@x"

    def test_line_delimited_for_crash_safety(self, tmp_path):
        """Each write is a complete JSON line — no partial state on crash."""
        skip_file = tmp_path / "skip_list.json"
        with patch.object(cli, "SKIP_LIST", skip_file):
            cli._save_skip_id("a@x")
            cli._save_skip_id("b@x")

        content = skip_file.read_text(encoding="utf-8")
        for line in content.splitlines():
            # each line must be valid JSON (crash-safe: no partial writes)
            json.loads(line)


class TestSkipListRoundTrip:
    def test_save_then_load(self, tmp_path):
        skip_file = tmp_path / "skip_list.json"
        ids = [f"id{i}@x" for i in range(100)]

        with patch.object(cli, "SKIP_LIST", skip_file):
            for mid in ids:
                cli._save_skip_id(mid)
            loaded = cli._load_skip_list()

        assert loaded == set(ids)
        assert len(loaded) == 100

    def test_no_duplicates_after_repeated_saves(self, tmp_path):
        skip_file = tmp_path / "skip_list.json"
        with patch.object(cli, "SKIP_LIST", skip_file):
            cli._save_skip_id("dup@x")
            cli._save_skip_id("dup@x")
            loaded = cli._load_skip_list()

        # set semantics: one entry despite two writes
        assert loaded == {"dup@x"}
