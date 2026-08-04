"""Tests for cluster.py stratified sampling.

Verifies the rewrite that replaced lexical Jaccard clustering
(which fragmented on near-unique LLM-generated principles) with
stratified sampling + LLM-side semantic grouping.
"""

import json
from pathlib import Path

import pytest

from torvalds_skill.cluster import (
    _stratified_sample,
    cluster_moves,
    SAMPLES_PER_CATEGORY,
    SUBSTANTIVE_FRACTION,
)
from torvalds_skill.models import ReviewMove


def _make_move(
    mid: str = "m1@x",
    date: str = "2020-01-01",
    trigger: str = "untested code",
    principle: str = "require tests",
    response: str = "add tests",
    severity: str = "reject",
    category: str = "testing",
) -> ReviewMove:
    return ReviewMove(
        email_message_id=mid,
        email_date=date,
        trigger=trigger,
        principle=principle,
        response=response,
        severity=severity,
        category=category,
    )


def _write_moves_jsonl(path: Path, moves: list[ReviewMove]) -> None:
    """Write moves in the nested JSONL format iter_moves expects."""
    by_email: dict[str, dict] = {}
    for m in moves:
        if m.email_message_id not in by_email:
            by_email[m.email_message_id] = {
                "email_message_id": m.email_message_id,
                "email_date": m.email_date,
                "moves": [],
            }
        by_email[m.email_message_id]["moves"].append(
            {
                "trigger": m.trigger,
                "principle": m.principle,
                "response": m.response,
                "severity": m.severity,
                "category": m.category,
            }
        )
    with open(path, "w", encoding="utf-8") as f:
        for entry in by_email.values():
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


class TestStratifiedSample:
    def test_returns_all_when_fewer_than_n(self):
        moves = [_make_move(mid=f"m{i}") for i in range(3)]
        result = _stratified_sample(moves, 10)
        assert len(result) == 3

    def test_returns_exactly_n(self):
        moves = [_make_move(mid=f"m{i}", date=f"202{i}0-01-01") for i in range(50)]
        result = _stratified_sample(moves, 10)
        assert len(result) == 10

    def test_deterministic_with_seed(self):
        moves = [
            _make_move(mid=f"m{i}", date=f"20{i:02d}-01-01", severity="reject")
            for i in range(50)
        ]
        r1 = _stratified_sample(moves, 10, seed=42)
        r2 = _stratified_sample(moves, 10, seed=42)
        assert [m.email_message_id for m in r1] == [m.email_message_id for m in r2]

    def test_different_seeds_different_samples(self):
        moves = [
            _make_move(mid=f"m{i}", date=f"20{i:02d}-01-01", severity="reject")
            for i in range(50)
        ]
        r1 = _stratified_sample(moves, 10, seed=42)
        r2 = _stratified_sample(moves, 10, seed=99)
        # extremely unlikely to be identical with 50 entries, seed differing
        assert [m.email_message_id for m in r1] != [m.email_message_id for m in r2]

    def test_buckets_covered(self):
        """Stratification should cover multiple year+severity buckets."""
        moves = []
        for year in range(2010, 2020):
            for sev in ("reject", "approve"):
                moves.append(
                    _make_move(
                        mid=f"m{year}{sev}",
                        date=f"{year}-06-01",
                        severity=sev,
                    )
                )
        result = _stratified_sample(moves, 10, seed=42)
        years = {m.email_date[:4] for m in result}
        severities = {m.severity for m in result}
        assert len(years) > 1, "should sample across years"
        assert len(severities) > 1, "should sample across severities"


class TestClusterMoves:
    def test_output_structure(self, tmp_path):
        moves = [_make_move(mid=f"m{i}") for i in range(30)]
        moves_path = tmp_path / "moves.jsonl"
        out_path = tmp_path / "patterns.json"
        _write_moves_jsonl(moves_path, moves)

        result = cluster_moves(moves_path, out_path)

        assert "total_moves" in result
        assert "categories" in result
        assert "severity_distribution" in result
        assert "samples_per_category" in result
        assert "samples_by_category" in result
        assert result["total_moves"] == 30

    def test_writes_valid_json(self, tmp_path):
        moves = [_make_move(mid=f"m{i}") for i in range(5)]
        moves_path = tmp_path / "moves.jsonl"
        out_path = tmp_path / "patterns.json"
        _write_moves_jsonl(moves_path, moves)

        cluster_moves(moves_path, out_path)

        loaded = json.loads(out_path.read_text(encoding="utf-8"))
        assert loaded["total_moves"] == 5

    def test_groups_by_category(self, tmp_path):
        moves = [
            _make_move(mid=f"t{i}", category="testing", trigger=f"t{i}")
            for i in range(10)
        ] + [
            _make_move(mid=f"c{i}", category="correctness", trigger=f"c{i}")
            for i in range(10)
        ]
        moves_path = tmp_path / "moves.jsonl"
        out_path = tmp_path / "patterns.json"
        _write_moves_jsonl(moves_path, moves)

        result = cluster_moves(moves_path, out_path)

        assert "testing" in result["categories"]
        assert "correctness" in result["categories"]
        assert result["categories"]["testing"] == 10
        assert result["categories"]["correctness"] == 10

    def test_substantive_filter(self, tmp_path):
        """Only top SUBSTANTIVE_FRACTION by response length should be eligible."""
        moves = [
            _make_move(
                mid=f"m{i}",
                response="x" * (i + 1),  # varying lengths
            )
            for i in range(20)
        ]
        moves_path = tmp_path / "moves.jsonl"
        out_path = tmp_path / "patterns.json"
        _write_moves_jsonl(moves_path, moves)

        cluster_moves(moves_path, out_path, top_n=15)
        loaded = json.loads(out_path.read_text(encoding="utf-8"))

        # With 20 moves, top 50% = 10 substantive, all sampled (10 < 15)
        sampled = len(loaded["samples_by_category"].get("testing", []))
        assert sampled == 10, f"expected 10 substantive, got {sampled}"

    def test_empty_category_omitted(self, tmp_path):
        moves = [_make_move(mid=f"m{i}", category="testing") for i in range(5)]
        moves_path = tmp_path / "moves.jsonl"
        out_path = tmp_path / "patterns.json"
        _write_moves_jsonl(moves_path, moves)

        result = cluster_moves(moves_path, out_path)

        assert "testing" in result["samples_by_category"]
        assert "correctness" not in result["samples_by_category"]

    def test_samples_have_required_fields(self, tmp_path):
        moves = [_make_move(mid=f"m{i}") for i in range(5)]
        moves_path = tmp_path / "moves.jsonl"
        out_path = tmp_path / "patterns.json"
        _write_moves_jsonl(moves_path, moves)

        cluster_moves(moves_path, out_path)
        loaded = json.loads(out_path.read_text(encoding="utf-8"))

        for sample in loaded["samples_by_category"]["testing"]:
            assert "trigger" in sample
            assert "principle" in sample
            assert "response" in sample
            assert "severity" in sample
            assert "date" in sample

    def test_severity_distribution_counts(self, tmp_path):
        moves = [
            _make_move(mid=f"r{i}", severity="reject") for i in range(5)
        ] + [
            _make_move(mid=f"a{i}", severity="approve") for i in range(3)
        ]
        moves_path = tmp_path / "moves.jsonl"
        out_path = tmp_path / "patterns.json"
        _write_moves_jsonl(moves_path, moves)

        result = cluster_moves(moves_path, out_path)

        assert result["severity_distribution"]["reject"] == 5
        assert result["severity_distribution"]["approve"] == 3

    def test_respects_top_n(self, tmp_path):
        moves = [_make_move(mid=f"m{i}", response="x" * i) for i in range(100)]
        moves_path = tmp_path / "moves.jsonl"
        out_path = tmp_path / "patterns.json"
        _write_moves_jsonl(moves_path, moves)

        cluster_moves(moves_path, out_path, top_n=10)
        loaded = json.loads(out_path.read_text(encoding="utf-8"))

        # 100 moves, top 50% = 50 substantive, sample 10 from those
        assert len(loaded["samples_by_category"]["testing"]) == 10

    def test_single_move_category(self, tmp_path):
        moves = [_make_move(mid="m1", category="testing")]
        moves_path = tmp_path / "moves.jsonl"
        out_path = tmp_path / "patterns.json"
        _write_moves_jsonl(moves_path, moves)

        cluster_moves(moves_path, out_path)
        loaded = json.loads(out_path.read_text(encoding="utf-8"))

        assert len(loaded["samples_by_category"]["testing"]) == 1
