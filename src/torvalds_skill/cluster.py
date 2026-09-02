"""
cluster.py — sample review moves by category for the distill LLM.

The original approach used lexical Jaccard clustering on principles. This
failed at scale: principles are LLM-generated freeform sentences, nearly
all unique, so lexical similarity is near zero even for semantically
identical principles ("don't break userspace" vs "we don't break existing
setups" share no words).

The fix: skip lexical clustering. Stratified-sample substantive moves per
category (diverse across year and severity, preferring longer responses
which carry more signal) and send them to the distill LLM, which does
semantic grouping in one pass — far better than Jaccard on freeform text.

Output: patterns.json with:
  - corpus statistics (honest counts)
  - samples_by_category: {cat: [{trigger, principle, response, severity, date}]}
  - the distill LLM finds themes from these raw moves
"""

from __future__ import annotations

import json
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from .audit import log_decision
from .models import CATEGORIES, iter_moves

# Simple stopword list for TF-IDF tokenization
STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "from",
    "as",
    "is",
    "was",
    "are",
    "were",
    "been",
    "be",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "must",
    "shall",
    "can",
    "need",
    "dare",
    "ought",
    "used",
    "i",
    "me",
    "my",
    "myself",
    "we",
    "our",
    "ours",
    "ourselves",
    "you",
    "your",
    "yours",
    "yourself",
    "yourselves",
    "he",
    "him",
    "his",
    "himself",
    "she",
    "her",
    "hers",
    "herself",
    "it",
    "its",
    "itself",
    "they",
    "them",
    "their",
    "theirs",
    "themselves",
    "what",
    "which",
    "who",
    "whom",
    "this",
    "that",
    "these",
    "those",
    "am",
    "any",
    "some",
    "no",
    "not",
    "only",
    "own",
    "same",
    "so",
    "than",
    "too",
    "very",
    "just",
    "also",
    "now",
    "here",
    "there",
    "when",
    "where",
    "why",
    "how",
    "all",
    "each",
    "every",
    "both",
    "few",
    "more",
    "most",
    "other",
    "such",
    "out",
    "up",
    "down",
    "over",
    "under",
    "again",
    "further",
    "then",
    "once",
    "if",
    "because",
    "while",
    "although",
    "though",
    "after",
    "before",
    "above",
    "below",
    "between",
    "into",
    "through",
    "during",
    "without",
    "within",
    "around",
    "against",
    "become",
    "becomes",
    "became",
    "get",
    "gets",
    "got",
    "make",
    "makes",
    "made",
    "take",
    "takes",
    "took",
    "give",
    "gives",
    "gave",
    "find",
    "finds",
    "found",
    "say",
    "says",
    "said",
    "know",
    "knows",
    "knew",
    "known",
    "think",
    "thinks",
    "thought",
    "see",
    "sees",
    "saw",
    "seen",
    "come",
    "comes",
    "came",
    "want",
    "wants",
    "wanted",
    "use",
    "uses",
    "using",
    "try",
    "tries",
    "tried",
    "leave",
    "leaves",
    "left",
    "call",
    "calls",
    "called",
    "keep",
    "keeps",
    "kept",
    "let",
    "begin",
    "begins",
    "began",
    "seem",
    "seems",
    "seemed",
    "help",
    "helps",
    "helped",
    "talk",
    "talks",
    "talked",
    "show",
    "shows",
    "showed",
    "shown",
    "ask",
    "asks",
    "asked",
    "work",
    "works",
    "worked",
    "feel",
    "feels",
    "felt",
    "seek",
    "seeks",
    "sought",
    "tell",
    "tells",
    "told",
    "place",
    "places",
    "placed",
    "consider",
    "considers",
    "considered",
    "allow",
    "allows",
    "allowed",
    "back",
    "clear",
    "clears",
    "clearly",
    "different",
    "differ",
    "differed",
    "differing",
    "several",
    "usual",
    "way",
    "ways",
    "question",
    "questions",
    "asking",
    "answer",
    "answers",
    "problem",
    "problems",
    "solve",
    "solves",
    "solved",
    "needs",
    "needed",
    "still",
    "being",
    "better",
    "best",
    "good",
    "great",
    "new",
    "old",
    "first",
    "last",
    "long",
    "little",
    "large",
    "high",
    "low",
    "right",
    "hard",
    "easy",
    "real",
    "true",
    "false",
    "possible",
    "important",
    "necessary",
    "required",
    "available",
    "common",
    "general",
    "specific",
    "particular",
    "certain",
    "similar",
    "various",
    "many",
    "much",
    "less",
    "least",
    "enough",
    "whole",
    "complete",
    "full",
    "open",
    "closed",
    "free",
    "public",
    "private",
    "personal",
    "social",
    "economic",
    "political",
    "legal",
    "technical",
    "practical",
    "theoretical",
}


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase words, filtering stopwords and short tokens."""
    words = re.findall(r"\b[a-zA-Z]+\b", text.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 2]


def _compute_tf(tokens: list[str]) -> dict[str, float]:
    """Compute term frequency for a document."""
    if not tokens:
        return {}
    tf = Counter(tokens)
    total = len(tokens)
    return {term: count / total for term, count in tf.items()}


def _compute_idf(documents: list[list[str]]) -> dict[str, float]:
    """Compute inverse document frequency across the corpus."""
    n_docs = len(documents)
    doc_freq: dict[str, int] = Counter()

    for doc_tokens in documents:
        unique_terms = set(doc_tokens)
        for term in unique_terms:
            doc_freq[term] += 1

    idf = {}
    for term, df in doc_freq.items():
        idf[term] = math.log(n_docs / (1 + df)) + 1

    return idf


def _tfidf_vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    """Compute TF-IDF vector for a document."""
    tf = _compute_tf(tokens)
    return {term: tf_val * idf.get(term, 0) for term, tf_val in tf.items()}


def _normalize_vector(vec: dict[str, float]) -> dict[str, float]:
    """L2-normalize a vector."""
    magnitude = math.sqrt(sum(v * v for v in vec.values()))
    if magnitude == 0:
        return vec
    return {k: v / magnitude for k, v in vec.items()}


def _cosine_similarity(vec1: dict[str, float], vec2: dict[str, float]) -> float:
    """Compute cosine similarity between two sparse vectors."""
    common_terms = set(vec1.keys()) & set(vec2.keys())
    return sum(vec1[term] * vec2[term] for term in common_terms)


class TFIDFClustering:
    """TF-IDF + cosine similarity clustering for text documents."""

    def __init__(self, threshold: float = 0.35):
        """Initialize clustering with similarity threshold.

        Args:
            threshold: Minimum cosine similarity for clustering (0.0-1.0).
                      Higher values = stricter clustering, more clusters.
                      Typical range: 0.3-0.5 works well for semantic clustering.
        """
        self.threshold = threshold
        self.idf: dict[str, float] = {}
        self.vectors: list[dict[str, float]] = []

    def fit(self, documents: list[str]) -> TFIDFClustering:
        """Fit TF-IDF model on documents.

        Args:
            documents: List of text documents to fit on.

        Returns:
            self for method chaining.
        """
        tokenized_docs = [_tokenize(doc) for doc in documents]
        self.idf = _compute_idf(tokenized_docs)

        self.vectors = []
        for tokens in tokenized_docs:
            vec = _tfidf_vector(tokens, self.idf)
            normalized = _normalize_vector(vec)
            self.vectors.append(normalized)

        return self

    def transform(self, documents: list[str]) -> list[dict[str, float]]:
        """Transform documents to TF-IDF vectors.

        Args:
            documents: List of text documents to transform.

        Returns:
            List of TF-IDF vectors.
        """
        tokenized_docs = [_tokenize(doc) for doc in documents]
        vectors = []
        for tokens in tokenized_docs:
            vec = _tfidf_vector(tokens, self.idf)
            normalized = _normalize_vector(vec)
            vectors.append(normalized)
        return vectors

    def fit_transform(self, documents: list[str]) -> list[dict[str, float]]:
        """Fit and transform in one step."""
        self.fit(documents)
        return self.vectors

    def cluster(self, documents: list[str]) -> list[list[int]]:
        """Cluster documents using single-linkage hierarchical clustering.

        Uses a greedy single-pass algorithm: each document joins the first
        cluster where it meets the similarity threshold with any member.

        Args:
            documents: List of text documents to cluster.

        Returns:
            List of clusters, where each cluster is a list of document indices.
        """
        if not documents:
            return []

        self.fit(documents)

        clusters: list[list[int]] = []
        assigned = [False] * len(documents)

        for i in range(len(documents)):
            if assigned[i]:
                continue

            cluster = [i]
            assigned[i] = True

            for j in range(i + 1, len(documents)):
                if assigned[j]:
                    continue

                for member_idx in cluster:
                    sim = _cosine_similarity(self.vectors[member_idx], self.vectors[j])
                    if sim >= self.threshold:
                        cluster.append(j)
                        assigned[j] = True
                        break

            clusters.append(cluster)

        return clusters

    def cluster_with_labels(self, documents: list[str]) -> list[int]:
        """Cluster documents and return cluster label for each document.

        Args:
            documents: List of text documents to cluster.

        Returns:
            List of cluster indices, one per document.
        """
        clusters = self.cluster(documents)
        labels = [0] * len(documents)
        for cluster_idx, cluster in enumerate(clusters):
            for doc_idx in cluster:
                labels[doc_idx] = cluster_idx
        return labels


# Moves per category in the distill prompt. 25 * 14 categories = 350 moves.
# At ~400 chars/move that's ~140K chars (~35K tokens) — safe context for gpt-oss-120b.
SAMPLES_PER_CATEGORY = 25

# Prefer substantive responses — longer responses carry more reviewing signal.
# Short "Ack"/"NACKed" replies are valid data points for severity stats but
# add little to the distill prompt. We sample from the top half by response length.
SUBSTANTIVE_FRACTION = 0.5


def _year_of(date_str: str) -> str:
    """Extract year from ISO date string for stratification."""
    return date_str[:4] if date_str else "unknown"


def _stratified_sample(moves: list, n: int, seed: int = 42) -> list:
    """Sample n moves with diversity across year and severity.

    Strategy: bucket by (year, severity), distribute n across buckets
    proportionally, pick randomly within each bucket. Falls back to
    random sample if buckets are too few.
    """
    if len(moves) <= n:
        return moves

    rng = random.Random(seed)
    buckets: dict[tuple, list] = defaultdict(list)
    for m in moves:
        buckets[(_year_of(m.email_date), m.severity)].append(m)

    # proportional allocation per bucket, at least 1 if bucket exists
    n_buckets = len(buckets)
    per_bucket = max(1, n // n_buckets)

    sampled = []
    for bucket in buckets.values():
        rng.shuffle(bucket)
        sampled.extend(bucket[:per_bucket])

    # if over-sampled, trim; if under, fill from remainder
    if len(sampled) > n:
        rng.shuffle(sampled)
        sampled = sampled[:n]
    elif len(sampled) < n:
        remaining = [m for m in moves if m not in sampled]
        rng.shuffle(remaining)
        sampled.extend(remaining[: n - len(sampled)])

    return sampled


def cluster_moves(moves_path: Path, output_path: Path, top_n: int = SAMPLES_PER_CATEGORY):
    """Sample moves by category and write patterns.json for distill."""
    moves = list(iter_moves(moves_path))
    total_moves = len(moves)

    # group by category
    by_category: dict[str, list] = defaultdict(list)
    for m in moves:
        by_category[m.category].append(m)

    samples_by_category: dict[str, list] = {}
    for cat in CATEGORIES:
        cat_moves = by_category.get(cat, [])
        if not cat_moves:
            continue

        # prefer substantive (longer) responses — more reviewing signal
        cat_moves.sort(key=lambda m: len(m.response), reverse=True)
        substantive = cat_moves[: max(1, int(len(cat_moves) * SUBSTANTIVE_FRACTION))]

        sampled = _stratified_sample(substantive, top_n, seed=42)

        log_decision(
            "cluster",
            category=cat,
            seed=42,
            bucketing="stratified_by_year_severity",
            sample_count=len(sampled),
            total_category_moves=len(cat_moves),
        )

        samples_by_category[cat] = [
            {
                "trigger": m.trigger,
                "principle": m.principle,
                "response": m.response,
                "severity": m.severity,
                "date": m.email_date,
            }
            for m in sampled
        ]

    output = {
        "total_moves": total_moves,
        "categories": {
            cat: len(by_category.get(cat, [])) for cat in CATEGORIES if by_category.get(cat)
        },
        "severity_distribution": dict(Counter(m.severity for m in moves)),
        "samples_per_category": top_n,
        "samples_by_category": samples_by_category,
    }

    output_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(
        f"sampled {total_moves} moves: {sum(len(v) for v in samples_by_category.values())} samples across {len(samples_by_category)} categories"
    )
    print(f"categories: {output['categories']}")
    print(f"severities: {output['severity_distribution']}")

    return output
