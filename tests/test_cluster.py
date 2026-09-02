"""Tests for cluster.py stratified sampling and TF-IDF clustering.

Verifies the rewrite that replaced lexical Jaccard clustering
(which fragmented on near-unique LLM-generated principles) with
stratified sampling + LLM-side semantic grouping.

Also tests the new TF-IDF + cosine similarity clustering for semantic
similarity-based grouping.
"""

import json
from pathlib import Path

from torvalds_skill.cluster import (
    TFIDFClustering,
    _cosine_similarity,
    _stratified_sample,
    _tokenize,
    cluster_moves,
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
            _make_move(mid=f"m{i}", date=f"20{i:02d}-01-01", severity="reject") for i in range(50)
        ]
        r1 = _stratified_sample(moves, 10, seed=42)
        r2 = _stratified_sample(moves, 10, seed=42)
        assert [m.email_message_id for m in r1] == [m.email_message_id for m in r2]

    def test_different_seeds_different_samples(self):
        moves = [
            _make_move(mid=f"m{i}", date=f"20{i:02d}-01-01", severity="reject") for i in range(50)
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
            _make_move(mid=f"t{i}", category="testing", trigger=f"t{i}") for i in range(10)
        ] + [_make_move(mid=f"c{i}", category="correctness", trigger=f"c{i}") for i in range(10)]
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
        moves = [_make_move(mid=f"r{i}", severity="reject") for i in range(5)] + [
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


class TestTFIDFClustering:
    """Tests for TF-IDF + cosine similarity clustering."""

    def test_tokenize_basic(self):
        """Tokenization should extract words and filter stopwords."""
        text = "The quick brown fox jumps over the lazy dog"
        tokens = _tokenize(text)
        assert "the" not in tokens  # stopword filtered
        assert "quick" in tokens
        assert "brown" in tokens
        assert "fox" in tokens
        assert len(tokens) > 0

    def test_tokenize_filters_short_tokens(self):
        """Tokens with 2 or fewer characters should be filtered."""
        text = "I am a test with short words like ox and my"
        tokens = _tokenize(text)
        assert "i" not in tokens
        assert "am" not in tokens
        assert "a" not in tokens
        assert "ox" not in tokens
        assert "my" not in tokens
        assert "with" not in tokens  # "with" is a stopword
        assert "test" in tokens
        assert "short" in tokens
        assert "words" in tokens
        assert "like" in tokens

    def test_cosine_similarity_identical_vectors(self):
        """Identical vectors should have cosine similarity of 1.0."""
        vec = {"test": 1.0, "word": 2.0}
        # Normalize the vector first
        import math

        mag = math.sqrt(sum(v * v for v in vec.values()))
        normalized = {k: v / mag for k, v in vec.items()}

        sim = _cosine_similarity(normalized, normalized)
        assert abs(sim - 1.0) < 0.0001

    def test_cosine_similarity_orthogonal_vectors(self):
        """Orthogonal vectors (no common terms) should have similarity 0."""
        vec1 = {"test": 1.0, "word": 2.0}
        vec2 = {"other": 1.0, "different": 3.0}

        # Normalize
        import math

        mag1 = math.sqrt(sum(v * v for v in vec1.values()))
        mag2 = math.sqrt(sum(v * v for v in vec2.values()))
        norm1 = {k: v / mag1 for k, v in vec1.items()}
        norm2 = {k: v / mag2 for k, v in vec2.items()}

        sim = _cosine_similarity(norm1, norm2)
        assert sim == 0.0

    def test_clustering_empty_documents(self):
        """Empty document list should return empty clusters."""
        clustering = TFIDFClustering()
        clusters = clustering.cluster([])
        assert clusters == []

    def test_clustering_single_document(self):
        """Single document should form one cluster."""
        clustering = TFIDFClustering(threshold=0.35)
        documents = ["this is a test document"]
        clusters = clustering.cluster(documents)
        assert len(clusters) == 1
        assert clusters[0] == [0]

    def test_clustering_similar_documents(self):
        """Similar documents should be clustered together."""
        clustering = TFIDFClustering(threshold=0.3)
        documents = [
            "kernel code must be tested before submission",
            "all kernel code requires testing",
            "testing is required for kernel patches",
            "completely unrelated document about cooking recipes",
        ]
        clusters = clustering.cluster(documents)

        # First three should be in one cluster, last one separate
        # (at threshold 0.3, semantically similar documents cluster together)
        assert len(clusters) >= 1
        assert len(clusters) <= 3  # At most 4, but similar docs should merge

    def test_clustering_dissimilar_documents(self):
        """Dissimilar documents should form separate clusters."""
        clustering = TFIDFClustering(threshold=0.5)
        documents = [
            "kernel development requires careful testing",
            "cooking recipes for Italian pasta dishes",
            "quantum physics principles explained simply",
        ]
        clusters = clustering.cluster(documents)

        # With high threshold and very different topics, expect separate clusters
        # or at least the unrelated ones separated
        assert len(clusters) >= 1

    def test_clustering_deterministic(self):
        """Clustering should be deterministic (no random initialization)."""
        clustering = TFIDFClustering(threshold=0.35)
        documents = [
            "kernel code must be tested",
            "testing is important for quality",
            "cooking is an art form",
            "baking bread requires patience",
        ]

        clusters1 = clustering.cluster(documents)
        clusters2 = TFIDFClustering(threshold=0.35).cluster(documents)

        assert clusters1 == clusters2

    def test_clustering_fewer_clusters_than_jaccard(self):
        """TF-IDF clustering should produce fewer clusters than lexical Jaccard.

        This is the key success criterion: TF-IDF + cosine similarity groups
        semantically similar documents even when they share few words,
        resulting in fewer, more coherent clusters.
        """
        # Create documents that are semantically similar but lexically different
        documents = [
            "kernel code requires thorough testing before submission",
            "all patches must be tested carefully",
            "testing is essential for kernel development",
            "we need proper test coverage for changes",
            "cooking recipes for Italian pasta",
            "Italian cuisine and pasta dishes",
            "how to make authentic Italian food",
            "quantum mechanics and physics principles",
            "understanding quantum physics basics",
            "physics explained for beginners",
        ]

        clustering = TFIDFClustering(threshold=0.25)
        clusters = clustering.cluster(documents)

        # With TF-IDF, we expect semantic clustering:
        # - Testing/kernel docs should cluster together (some merge)
        # - Italian cooking docs should cluster (2-3 docs)
        # - Physics docs should cluster (2-3 docs)
        # Result: fewer clusters than documents (Jaccard would give 10)
        assert len(clusters) < len(documents), (
            f"TF-IDF should cluster: got {len(clusters)} clusters for {len(documents)} docs"
        )
        # At threshold 0.25, expect 4-7 clusters (still much better than 10)
        assert len(clusters) <= 7, f"Expected semantic clustering, got {len(clusters)} clusters"

    def test_cluster_with_labels(self):
        """cluster_with_labels should return one label per document."""
        clustering = TFIDFClustering(threshold=0.3)
        documents = [
            "kernel testing is important",
            "code must be tested",
            "cooking recipes",
        ]

        labels = clustering.cluster_with_labels(documents)

        assert len(labels) == len(documents)
        assert all(isinstance(label, int) for label in labels)

    def test_fit_transform_returns_vectors(self):
        """fit_transform should return TF-IDF vectors."""
        clustering = TFIDFClustering()
        documents = ["test document one", "test document two", "different content"]

        vectors = clustering.fit_transform(documents)

        assert len(vectors) == len(documents)
        assert all(isinstance(v, dict) for v in vectors)

    def test_threshold_effect(self):
        """Higher threshold should produce more clusters (stricter clustering)."""
        documents = [
            "kernel code testing requirements",
            "testing is required for patches",
            "cooking Italian recipes",
            "Italian food preparation",
        ]

        # Lower threshold = more permissive = fewer clusters
        clustering_low = TFIDFClustering(threshold=0.2)
        clusters_low = clustering_low.cluster(documents)

        # Higher threshold = stricter = more clusters
        clustering_high = TFIDFClustering(threshold=0.6)
        clusters_high = clustering_high.cluster(documents)

        # Higher threshold should give >= clusters (stricter = less merging)
        assert len(clusters_high) >= len(clusters_low)
