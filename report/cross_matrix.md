# Cross-Model Evaluation Matrix

Diagonal data from `data/eval_results.jsonl`, cross-data from `data/eval_results_cross.jsonl`.

Dataset: 45 diff scenarios = 25 buggy, 15 clean (no findings expected), 5 refuse-to-conclude (correct answer is uncertainty).

Judge: GLM5.2, a fixed external model applied at generation time (`--judge-model`). It also reviews here, so judge scores may carry self-preference.

> **Evaluation provenance:** the reviewer prompt carried only the code under review, never the ground-truth bug list (enforced by regression tests in [tests/test_eval.py](tests/test_eval.py)). Every number below therefore measures detection, not transcription.

## About this report

This report answers: **which model+skill combination detects bugs best?** It is a cross-model evaluation on 45 synthetic diffs.

Three roles are at play:

1. **Reviewer model** — the model that reads the code and produces findings. It determines *which* bugs are found and drives the true-positive count.
2. **Skill** — the prompt/skill applied to the reviewer. It influences precision (false-positive rate) but rarely changes which bugs are detected.
3. **Judge model** — scores the *quality* of each review on four axes (accuracy, prioritization, justification, actionability). The judge does **not** affect the Detection Score, true positives, recall, or precision. It can be disabled with `--no-judge`.

A pairing is written `A × B`: reviewer model `A` reads the code using the skill written by `B`. `A × A` is the native pairing. For baseline-vs-skill analysis (does the skill help or hurt each model?), see [report/comparison.md](report/comparison.md).

## Verdict

A **pairing** is one reviewer model plus one skill, written `A × B`: reviewer `A` reads the code using the skill written by `B`. `A × A` is the **native** pairing, where a model uses its own skill.

**Most bugs found**

- `mistral-small-4-119b` × `mistral-small-4-119b` — **18 of 25** real bugs. 45 findings: 18 matched a real bug, 1 was a duplicate, 26 matched nothing.

**Cleanest review (Detection Score)**

Detection Score weighs bugs found against findings that were not bugs, so a review that buries real bugs in noise scores lower than its bug count suggests.

- Highest: `mistral-small-4-119b` × `mistral-small-4-119b` *(native)* — 0.51, from 45 findings: 18 matched a real bug, 1 was a duplicate, 26 matched nothing.

**Best-written review (judge score)**

A separate judge model (GLM5.2) rates the write-up for clarity, prioritisation, justification and actionability. It never checks whether a finding is a real bug, so a well-argued review of nothing scores well.

- Highest: `glm5.2` × `gpt-oss-120b` — 1.7/2, while finding 2 of 25 real bugs.

**Most serious bugs**

Serious bugs are the ones marked `reject`-severity: a reviewer would block a merge over them.

- Tied at **2** bugs across 1 pairing — `mistral-small-4-119b` × {`mistral-small-4-119b`}.

**Across the whole matrix**

- Best reviewer, counting every bug it found with any of its skills: `mistral-small-4-119b` — **21 of 25** (84%). This rewards breadth, so a noisy reviewer can win here.
- Best skill, counting every bug any reviewer found while using it: `qwen3.8-27b` — **21 of 25** (84%).
- Consensus over 4 models: 2 bugs found by all of them (easy to spot), 7 by exactly one (contestable), 0 by none.

**Native skill or a borrowed one**

Delta = the model's own skill minus the average of its three borrowed skills. Negative means borrowing another model's skill scored better.

- Own skill wins for 3 of 4 models, a borrowed skill for 0.
- Best skill per model: 2 of 4 models do best with their own skill, 2 with a borrowed one.

**How much to trust this:** 25 bugs is a small sample: one extra bug moves Detection Score by about 0.04, so gaps under ~0.05 are ties.

Baseline-vs-skill (does a skill help or hurt a model at all?) is in [report/comparison.md](report/comparison.md). The two reports use different datasets, so do not compare numbers across them.


---

## Overview Matrix

Rows = skill applied to the reviewer; columns = reviewer model. Each cell shows Detection Score (DS). `*(native)*` marks diagonal pairings (model == skill). The highest DS in the matrix is shown in **bold** with a ★.

**Note**: n=45 scenarios (25 buggy), 1 run per cell; intra-skill Detection Score differences of ~0.03 are not significant.

| Skill \\ Model | glm5.2 | gpt-oss-120b | mistral-small-4-119b | qwen3.8-27b |
|---|---|---|---|---|
| **glm5.2** | DS=0.08 *(native)* | DS=0.08 | DS=0.49 | DS=0.18 |
| **gpt-oss-120b** | DS=0.05 | DS=0.17 *(native)* | DS=0.49 | DS=0.23 |
| **mistral-small-4-119b** | DS=0.05 | DS=0.22 | **DS=0.51 *(native)* ★** | — |
| **qwen3.8-27b** | DS=0.08 | DS=0.20 | DS=0.40 | DS=0.28 *(native)* |
| **No skill (baseline)** | DS=0.16 | DS=0.19 | DS=0.49 | DS=0.28 |


### Judge Score Matrix (J, 0-2 scale)

Rows = skill applied, columns = reviewer model. Judge scores only (J, 0–2 scale). The highest J in the matrix is shown in **bold** with a ★. Note: J does not affect DS.

| Skill \\ Model | glm5.2 | gpt-oss-120b | mistral-small-4-119b | qwen3.8-27b |
|---|---|---|---|---|
| **glm5.2** | J=1.4/2 *(native)* | J=1.0/2 | J=0.9/2 | J=1.2/2 |
| **gpt-oss-120b** | **J=1.7/2 ★** | J=1.0/2 *(native)* | J=0.7/2 | J=1.3/2 |
| **mistral-small-4-119b** | J=1.4/2 | J=0.9/2 | J=0.8/2 *(native)* | — |
| **qwen3.8-27b** | J=1.5/2 | J=1.1/2 | J=0.9/2 | J=1.5/2 *(native)* |
| **No skill (baseline)** | J=1.6/2 | J=0.9/2 | J=1.1/2 | J=1.6/2 |


*DS = Detection Score (precision-weighted recall). J = Judge Score (0–3 quality rating by GLM5.2). Cells use `reviewer × skill` notation. Bold ★ marks the best Detection Score.*

## Precision Matrix

Rows = skill applied, columns = reviewing model. Fraction of reported findings that matched a real bug — higher is better; low values flag noisy reviewers.

| Skill \\ Model | glm5.2 | gpt-oss-120b | mistral-small-4-119b | qwen3.8-27b |
|---|---|---|---|---|
| glm5.2 | 0.06 | 0.06 | 0.38 | 0.21 |
| gpt-oss-120b | 0.04 | 0.13 | 0.38 | 0.28 |
| mistral-small-4-119b | 0.04 | 0.16 | 0.40 | — |
| qwen3.8-27b | 0.09 | 0.16 | 0.31 | 0.19 |
| No skill (baseline) | 0.10 | 0.14 | 0.38 | 0.22 |


## Recall Matrix

Rows = skill applied, columns = reviewing model. Matched findings per buggy diff scenario (25 ground-truth bugs) — higher is better.

| Skill \\ Model | glm5.2 | gpt-oss-120b | mistral-small-4-119b | qwen3.8-27b |
|---|---|---|---|---|
| glm5.2 | 0.12 | 0.12 | 0.68 | 0.16 |
| gpt-oss-120b | 0.08 | 0.24 | 0.68 | 0.20 |
| mistral-small-4-119b | 0.08 | 0.32 | 0.72 | — |
| qwen3.8-27b | 0.08 | 0.28 | 0.56 | 0.52 |
| No skill (baseline) | 0.36 | 0.28 | 0.68 | 0.40 |


## Native Pairing Ranking (model == skill)

Diagonal cells only — each model using its own skill.

| Model | Detection Score | Bugs Found | Judge Score |
|-------|-----------------|------------|-------------|
| mistral-small-4-119b | 0.51 | 18/25 | 0.8/2 |
| qwen3.8-27b | 0.28 | 13/25 | 1.5/2 |
| gpt-oss-120b | 0.17 | 6/25 | 1.0/2 |
| glm5.2 | 0.08 | 3/25 | 1.4/2 |

## Best Pairing by Metric

The best pairing(s) for each headline metric (ties shown).

- **Best Detection Score**: mistral-small-4-119b × mistral-small-4-119b *(native)* (DS=0.51)

- **Best Judge Score**: glm5.2 × gpt-oss-120b (J=1.7/2)


---

## Marginal Analysis

Row means (per reviewing model across skills) and column means (per skill across models).

**Best Model**: mistral-small-4-119b (row-mean DS=0.47, judge=0.8)

**Best Skill**: mistral-small-4-119b (column-mean DS=0.26, judge=1.1)


### Model Rankings (by row-mean Detection Score)

| Rank | Model | Detection Score | Judge Mean | Rarity Score |
|------|-------|-----------------|------------|--------------|
| 1 | mistral-small-4-119b | 0.47 | 0.8 | 0.47 |
| 2 | qwen3.8-27b | 0.23 | 1.3 | 0.28 |
| 3 | gpt-oss-120b | 0.17 | 1.0 | 0.19 |
| 4 | glm5.2 | 0.07 | 1.5 | 0.07 |

### Skill Rankings (by column-mean Detection Score)

| Rank | Skill | Detection Score | Judge Mean | Rarity Score |
|------|-------|-----------------|------------|--------------|
| 1 | mistral-small-4-119b | 0.26 | 1.1 | 0.40 |
| 2 | qwen3.8-27b | 0.24 | 1.3 | 0.44 |
| 3 | gpt-oss-120b | 0.24 | 1.2 | 0.42 |
| 4 | glm5.2 | 0.21 | 1.1 | 0.42 |

---

## Bug Discovery Ranking

How many ground-truth bugs each pairing, model, and skill actually found, broken down by severity and category. Raw counts — no precision penalty.

Ground-truth bugs: **25**

### Bugs Found per Pairing (findings classified)

| Model | Skill | TP | Duplicates | Unmatched | Total findings |
|-------|-------|----|------------|-----------|----------------|
| mistral-small-4-119b | mistral-small-4-119b *(native)* | 18 | 1 | 26 | 45 |
| mistral-small-4-119b | glm5.2 | 17 | 2 | 26 | 45 |
| mistral-small-4-119b | gpt-oss-120b | 17 | 2 | 26 | 45 |
| mistral-small-4-119b | qwen3.8-27b | 14 | 1 | 30 | 45 |
| qwen3.8-27b | qwen3.8-27b *(native)* | 13 | 8 | 47 | 68 |
| gpt-oss-120b | mistral-small-4-119b | 8 | 0 | 41 | 49 |
| gpt-oss-120b | qwen3.8-27b | 7 | 0 | 38 | 45 |
| gpt-oss-120b | gpt-oss-120b *(native)* | 6 | 1 | 38 | 45 |
| qwen3.8-27b | gpt-oss-120b | 5 | 1 | 12 | 18 |
| qwen3.8-27b | glm5.2 | 4 | 1 | 14 | 19 |
| glm5.2 | glm5.2 *(native)* | 3 | 0 | 49 | 52 |
| gpt-oss-120b | glm5.2 | 3 | 0 | 44 | 47 |
| glm5.2 | mistral-small-4-119b | 2 | 0 | 46 | 48 |
| glm5.2 | gpt-oss-120b | 2 | 0 | 46 | 48 |
| glm5.2 | qwen3.8-27b | 2 | 0 | 21 | 23 |

### Bugs Found per Model and per Skill

| Group | Name | Total Found | Coverage | Exclusive |
|-------|------|-------------|----------|-----------|
| Model | mistral-small-4-119b | 21 | 84% | 5 |
| Model | qwen3.8-27b | 15 | 60% | 2 |
| Model | gpt-oss-120b | 12 | 48% | 0 |
| Model | glm5.2 | 5 | 20% | 0 |
| Skill | qwen3.8-27b | 21 | 84% | 2 |
| Skill | gpt-oss-120b | 20 | 80% | 0 |
| Skill | glm5.2 | 20 | 80% | 0 |
| Skill | mistral-small-4-119b | 20 | 80% | 0 |

### Bugs Found by Only One Model

| Bug ID | Found Only By |
|--------|---------------|
| DIFF-001 | qwen3.8-27b |
| DIFF-034 | mistral-small-4-119b |
| DIFF-035 | mistral-small-4-119b |
| DIFF-036 | mistral-small-4-119b |
| DIFF-038 | qwen3.8-27b |
| DIFF-043 | mistral-small-4-119b |
| DIFF-045 | mistral-small-4-119b |

### Bugs Found by Severity (distinct from ground truth)

| Severity | Ground Truth |
|----------|--------------|
| reject | 2 |
| request-changes | 8 |
| nitpick | 15 |

### Severity Breakdown per Model and per Skill

| Group | Name | reject | request-changes | nitpick | Total |
|-------|------|-------|-------|-------|-------|-------|
| glm5.2 | 0 | 2 | 7 | 9 |
| gpt-oss-120b | 3 | 11 | 10 | 24 |
| mistral-small-4-119b | 5 | 28 | 33 | 66 |
| qwen3.8-27b | 3 | 8 | 11 | 22 |
| Group | Name | reject | request-changes | nitpick | Total |
|-------|------|-------|-------|-------|-------|-------|
| glm5.2 | 2 | 10 | 15 | 27 |
| gpt-oss-120b | 3 | 12 | 15 | 30 |
| mistral-small-4-119b | 3 | 13 | 12 | 28 |
| qwen3.8-27b | 3 | 14 | 19 | 36 |

### Severity Breakdown per Pairing

Critical (`reject`) bug counts for each (model, skill) cell. Higher is better for critical-bug detection.

| Model | Skill | reject | total |
|-------|-------|--------|-------|
| mistral-small-4-119b *(native)* | mistral-small-4-119b | 2 | 18 |
| mistral-small-4-119b | glm5.2 | 1 | 17 |
| mistral-small-4-119b | gpt-oss-120b | 1 | 17 |
| mistral-small-4-119b | qwen3.8-27b | 1 | 14 |
| qwen3.8-27b *(native)* | qwen3.8-27b | 1 | 13 |
| gpt-oss-120b | mistral-small-4-119b | 1 | 8 |
| gpt-oss-120b | qwen3.8-27b | 1 | 7 |
| gpt-oss-120b *(native)* | gpt-oss-120b | 1 | 6 |
| qwen3.8-27b | gpt-oss-120b | 1 | 5 |
| qwen3.8-27b | glm5.2 | 1 | 4 |
| glm5.2 *(native)* | glm5.2 | 0 | 3 |
| gpt-oss-120b | glm5.2 | 0 | 3 |
| glm5.2 | mistral-small-4-119b | 0 | 2 |
| glm5.2 | gpt-oss-120b | 0 | 2 |
| glm5.2 | qwen3.8-27b | 0 | 2 |

### Bugs Found by Category (distinct from ground truth)

| Category | Ground Truth |
|----------|--------------|
| correctness | 5 |
| style | 4 |
| abstraction | 3 |
| error-handling | 3 |
| api-stability | 2 |
| complexity | 2 |
| memory-safety | 2 |
| concurrency | 1 |
| documentation | 1 |
| performance | 1 |
| process | 1 |

### Category Breakdown per Model and per Skill

| Group | Name | abstraction | api-stability | complexity | concurrency | correctness | documentation | error-handling | memory-safety | performance | process | style | Total |
|-------|------|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|
| glm5.2 | 3 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 4 | 9 |
| gpt-oss-120b | 3 | 6 | 2 | 1 | 4 | 0 | 3 | 1 | 0 | 0 | 4 | 24 |
| mistral-small-4-119b | 10 | 8 | 4 | 4 | 5 | 3 | 12 | 8 | 2 | 2 | 8 | 66 |
| qwen3.8-27b | 3 | 4 | 1 | 0 | 6 | 1 | 2 | 1 | 0 | 0 | 4 | 22 |
| Group | Name | abstraction | api-stability | complexity | concurrency | correctness | documentation | error-handling | memory-safety | performance | process | style | Total |
|-------|------|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|
| glm5.2 | 5 | 4 | 1 | 1 | 2 | 1 | 4 | 2 | 1 | 0 | 6 | 27 |
| gpt-oss-120b | 5 | 5 | 1 | 1 | 4 | 0 | 4 | 3 | 1 | 1 | 5 | 30 |
| mistral-small-4-119b | 4 | 4 | 2 | 2 | 5 | 1 | 4 | 2 | 0 | 1 | 3 | 28 |
| qwen3.8-27b | 5 | 6 | 3 | 1 | 4 | 2 | 6 | 3 | 0 | 0 | 6 | 36 |

---

## New Bug Candidates

Findings that match NO ground-truth bug — candidates for ground-truth expansion (require human triage).

| File:Line | Severity | Issue | Reported by |
|-----------|----------|-------|-------------|
| network.c | MEDIUM | `addr.sin_addr` is never set. The code attempts to `connect()` using a `sockaddr_in` whose address f | 15 cell(s) |
| fileio.c | MEDIUM | `fp` is passed by value. Setting `fp = NULL` after `fclose(fp)` mutates a local copy that is discard | 14 cell(s) |
| sync.rs | MEDIUM | The function will not compile because the error type does not match the actual error produced by `lo | 12 cell(s) |
| config.py | MEDIUM | The module loads arbitrary YAML data and writes it back without any schema validation. Untrusted or | 11 cell(s) |
| parser.py | MEDIUM | The `tokenize()` function previously returned the full list of tokens from the input string. The pat | 11 cell(s) |
| streams.c | MEDIUM | The diff introduces `typedef struct stream { char *data; size_t size; } stream_t;` but no code in th | 11 cell(s) |
| threads.rs | MEDIUM | An additional `}` is inserted after the `for` loop in `join_all`. The function already has its closi | 11 cell(s) |
| cache.c | MEDIUM | `cache_get` indexes into the `cache[]` array and immediately dereferences `->value` without checking | 10 cell(s) |
| db.c | MEDIUM | `sqlite3_free(err_msg);` is called **before** the error message is printed. If `sqlite3_exec` fails, | 9 cell(s) |
| memory.rs | MEDIUM | The new field `allocation_count` is initialized to `0` and a public accessor `allocations()` returns | 9 cell(s) |
| types.rs | MEDIUM | The diff adds an `impl Default for Config {` block but does not provide the required `fn default() - | 9 cell(s) |
| parallel.rs | MEDIUM | A recoverable condition (empty or tiny input) crashes the whole program, violating the “never crash | 8 cell(s) |
| protocol.c | MEDIUM | `free_packet` does not verify that the argument `pkt` is non‑NULL before accessing `pkt->payload`. I | 8 cell(s) |
| queue.rs | MEDIUM | The `Drop` implementation only calls `self.items.clear()`. `VecDeque` (or whatever collection `items | 8 cell(s) |
| buffer.c | MEDIUM | `buf->capacity * 2 + len` is computed in `size_t` without any overflow check. If `capacity` is alrea | 7 cell(s) |
| crypto.py | MEDIUM | The new code does `salt = os.urandom(32)` and then returns only `hashlib.pbkdf2_hmac("sha256", passw | 7 cell(s) |
| server.c | MEDIUM | `buffer` is declared as `char buffer[1024]` and `n` is the return value of `read(fd, buffer, sizeof( | 7 cell(s) |
| utils.py | MEDIUM | A `strict: bool = False` parameter was added to `validate_port`, but the function body was not touch | 7 cell(s) |
| error.rs | MEDIUM | The `Display` impl prints the error with `{:?}`, which yields the `Debug` representation of the enum | 6 cell(s) |
| logging.py | MEDIUM | The new `get_logger(name)` function is a one-line passthrough to `logging.getLogger(name)`. It does | 6 cell(s) |
| main.rs | MEDIUM | The added `println!("Debug mode enabled")` under `#[cfg(debug_assertions)]` means the program's stdo | 6 cell(s) |
| worker.rs:28 | MEDIUM | The added blank line contains trailing spaces, visible in the diff as `+    `. This is unnecessary a | 6 cell(s) |
| async.rs | MEDIUM | The function is named `delayed_call`, which strongly implies that something will be *called* after t | 5 cell(s) |
| helpers.rs:5 | MEDIUM | The function `normalize_path` returns a `String` constructed from `path.to_string_lossy()`, which ma | 5 cell(s) |
| helpers.rs:6 | MEDIUM | The function name and module docs promise path normalization, but the body only converts a `Path` to | 5 cell(s) |
| validation.c | MEDIUM | `name[0]` is of type `char`. On platforms where `char` is signed, any byte with the high bit set (0x | 5 cell(s) |
| app.py:23 | MEDIUM | The `# Entry point` comment and `if __name__ == "__main__":` guard are placed *after* the `main()` c | 4 cell(s) |
| async.py | MEDIUM | `response` is already obtained and managed via `async with session.get(url) as response:`. The inner | 4 cell(s) |
| error.rs:11 | MEDIUM | The `Display` implementation uses `{:?}` (Debug formatting) which produces implementation-dependent | 4 cell(s) |
| fileio.c:13 | MEDIUM | If `open_file(NULL, mode)` is called, `fopen()` fails and `fprintf(stderr, "Failed to open %s: %s\n" | 4 cell(s) |
| helpers.rs | MEDIUM | The public documentation misrepresents the function’s behavior. Callers will expect a true “normaliz | 4 cell(s) |
| helpers.rs:7 | MEDIUM | `to_string_lossy()` silently replaces non-UTF-8 bytes in the path with U+FFFD (the Unicode replaceme | 4 cell(s) |
| lib.rs | MEDIUM | The function `process_data` previously returned `Error::Empty`. Renaming the variant to `Error::Empt | 4 cell(s) |
| main.c:9 | MEDIUM | The added `int main(int argc, char *argv[]) {` opens a function block but never closes it and provid | 4 cell(s) |
| test.c | MEDIUM | Two consecutive comments — `/* Unit tests */` and `/* Test suite for core functionality */` — say es | 4 cell(s) |
| types.rs:8 | MEDIUM | The patch adds an `impl Default for Config` block but provides no implementation body. This will fai | 4 cell(s) |
| unknown_feature.py:4 | MEDIUM | The diff adds an exported function `experimental_function` without justification, documentation, or | 4 cell(s) |
| validator.py | MEDIUM | A new `strict` parameter is added to the public `validate_email` signature, but the function body ne | 4 cell(s) |
| allocator.c | MEDIUM | The diff adds a new public header comment (`/* Custom memory allocator */`, `/* Implements pool-base | 3 cell(s) |
| app.py | MEDIUM | The comment `# Application startup complete` is placed after the `if __name__ == "__main__":` block. | 3 cell(s) |
| async.rs:4 | MEDIUM | The `delayed_call` function awaits a `sleep` without handling potential errors. Tokio's `sleep` can | 3 cell(s) |
| config.py:7 | MEDIUM | `HOST = "localhost"` adds a new public configuration constant to `config` without a visible consumer | 3 cell(s) |
| iterators.rs | MEDIUM | The new `flatten` implementation uses `flat_map` with two consecutive `into_iter()` calls. This is f | 3 cell(s) |
| legacy.rs | MEDIUM | The `#[deprecated]` outer attribute is placed at the very end of the file with no item following it. | 3 cell(s) |
| legacy.rs:9 | MEDIUM | The `#[deprecated]` attribute is inserted on its own line, not attached to any item. Rust treats thi | 3 cell(s) |
| main.c:7 | MEDIUM | The diff adds `int main(int argc, char *argv[]) {` but does not add a function body or closing brace | 3 cell(s) |
| plugin.py:15 | MEDIUM | The `Plugin` abstract base class defines an abstract method `execute()` that must be implemented by | 3 cell(s) |
| routes.py:6 | MEDIUM | The diff adds a comment "# Route handlers below" but provides no actual route handlers or API endpoi | 3 cell(s) |
| server.c:18 | MEDIUM | `int max_retries = 3;` is introduced but never used. It suggests unimplemented retry logic and adds | 3 cell(s) |
| unknown_feature.py | MEDIUM | The diff adds `# Experimental feature` at the top and `# Do not use in production` at the bottom, bu | 3 cell(s) |
| allocator.c:4 | MEDIUM | The diff adds a new public header comment and a `#define POOL_SIZE 4096` in a header file (implied b | 2 cell(s) |
| config.py:5 | MEDIUM | The constant `HOST = "localhost"` is defined as a string literal, which in Python is interned and sa | 2 cell(s) |
| error.rs:14 | MEDIUM | `write!(f, "Error: {:?}", self)` renders every error as a generic `Error:` prefix followed by the en | 2 cell(s) |
| experimental.c | MEDIUM | The function `prototype_function` is defined with external linkage. Compiling this file will add a n | 2 cell(s) |
| experimental.c:1 | MEDIUM | The file starts with a comment `/* Experimental code - subject to change */` but contains no actual | 2 cell(s) |
| ffi.rs | MEDIUM | The added `// C compatibility layer` comment sits after a blank line at the very end of the file, wi | 2 cell(s) |
| ffi.rs:1 | MEDIUM | The new module-level documentation `//! FFI bindings` does not explain why unsafe FFI is needed, wha | 2 cell(s) |
| ffi.rs:7 | MEDIUM | The function `add_one` returns a raw pointer to a stack-allocated integer (`x`), which becomes inval | 2 cell(s) |
| legacy.rs:11 | MEDIUM | The added line `#[deprecated]` is an outer attribute with no following item. Rust requires an item a | 2 cell(s) |
| lib.rs:21 | MEDIUM | `batch_process` is a new public entry point that is a thin wrapper around `process_data`. The diff d | 2 cell(s) |
| logging.py:17 | MEDIUM | The new `get_logger()` function directly calls `logging.getLogger(name)` without any error handling | 2 cell(s) |
| main.c | MEDIUM | The comments `/* Main entry point for the application */` and `/* Handles command-line arguments */` | 2 cell(s) |
| main.c:5 | MEDIUM | The `main()` function is declared to return an `int` but does not have a `return` statement. This ca | 2 cell(s) |
| main.c:6 | MEDIUM | The diff adds a `main` function declaration but provides no body. This will fail to link and produce | 2 cell(s) |
| memory.rs:15 | MEDIUM | The `MemoryPool` struct now includes an `allocation_count` field, but there is no synchronization me | 2 cell(s) |
| network.c:32 | MEDIUM | The patch adds `#endif` with no visible matching `#if`, `#ifdef`, or `#ifndef`. If there is no condi | 2 cell(s) |
| network.c:7 | MEDIUM | The diff adds a stray `#endif` with no corresponding `#if`/`#ifdef` in the file. This will cause a c | 2 cell(s) |
| parser.py:15 | MEDIUM | `parse_json` calls `json.loads`, but the file does not import the `json` module. At runtime this wil | 2 cell(s) |
| queue.rs:15 | MEDIUM | The `Drop` implementation calls `self.items.clear()`, which removes all items from the queue but doe | 2 cell(s) |
| server.c:1 | MEDIUM | The new header comment block and includes are added without an include guard (`#ifndef`/`#define`), | 2 cell(s) |
| server.c:17 | MEDIUM | The variable `max_retries` is declared but never read or used, adding unnecessary clutter and riskin | 2 cell(s) |
| server.c:5 | MEDIUM | Adding `#include <unistd.h>` introduces new system calls (e.g., `read`, `write`, `close`) without an | 2 cell(s) |
| test.c:4 | MEDIUM | The diff adds test scaffolding comments and a counter variable but provides no actual test functions | 2 cell(s) |
| test.c:5 | MEDIUM | The diff adds a new global variable `test_count` with no explanation in commit message or comments. | 2 cell(s) |
| test.c:9 | MEDIUM | The newly added `static int test_count = 0;` is never read or written anywhere in the file. An unuse | 2 cell(s) |
| types.rs:10 | MEDIUM | [REASON] The diff adds `impl Default for Config {` but provides no `fn default()` body and no closin | 2 cell(s) |
| utils.py:21 | MEDIUM | `validate_port(port: int, strict: bool = False)` adds a `strict` parameter, but the implementation i | 2 cell(s) |
| validation.c:22 | MEDIUM | `is_valid_identifier` calls `isalpha` but `<ctype.h>` is not included, causing a compilation error. | 2 cell(s) |
| validation.c:7 | MEDIUM | The original `validate_input()` accepted an empty string (only a NULL pointer was rejected). The pat | 2 cell(s) |
| worker.rs | MEDIUM | Introducing a new public API (`pub fn is_running(&self) -> bool`) expands the public surface area. I | 2 cell(s) |
| `types.rs`, added lines after `pub version | MEDIUM | The diff adds `impl Default for Config {` but provides no method body and no closing brace. The `Def | 1 cell(s) |
| allocator.c:6 | MEDIUM | The diff introduces a `#define POOL_SIZE 4096` at the top of the file, which is a new public symbol | 1 cell(s) |
| allocator.c:9 | MEDIUM | `#define POOL_SIZE 4096` embeds a magic constant directly in the source. The value has no comment ex | 1 cell(s) |
| app.py:25 | MEDIUM | The added `if __name__ == "__main__": main()` makes the module execute `main()`, which calls `app.ru | 1 cell(s) |
| app.py:28 | MEDIUM | The comment `# Application startup complete` appears after `main()`, but `main()` calls `app.run()`, | 1 cell(s) |
| async.py — `fetch_data`, the changed line (`async with aiohttp.ClientSession() as session, session.get(url) as response | MEDIUM | The new line already enters the response lifecycle via `session.get(url) as response` (aiohttp's `_R | 1 cell(s) |
| async.py:18 | MEDIUM | `tasks = [fetch_data(url) for url in urls]` starts every URL at once. A large `urls` list can create | 1 cell(s) |
| async.py:19 | MEDIUM | `asyncio.gather(*tasks)` propagates the first exception but does not define what happens to the othe | 1 cell(s) |
| async.py:20 | MEDIUM | `# TODO: Add timeout handling` acknowledges a known deficiency without fixing it. A TODO is a promis | 1 cell(s) |
| async.py:22 | MEDIUM | The diff adds `# TODO: Add timeout handling` but ships no timeout. `fetch_data()` can block on a slo | 1 cell(s) |
| async.rs:5 | MEDIUM | The `delayed_call` function awaits `sleep(...).await` but does not handle potential errors from the | 1 cell(s) |
| buffer.c:26 | MEDIUM | The new function `buffer_remaining()` returns `buf->capacity - buf->size`, exposing the internal cap | 1 cell(s) |
| config.py:1 | MEDIUM | The diff adds a new configuration variable `HOST = "localhost"` but the commit message (implied by t | 1 cell(s) |
| config.py:26 | MEDIUM | The `save_config` function opens the file without specifying the encoding, which can lead to platfor | 1 cell(s) |
| config.py:6 | MEDIUM | The new `HOST` variable is set to a hard-coded string `"localhost"` with no validation or sanitizati | 1 cell(s) |
| crypto.py:1 | MEDIUM | The new implementation uses `os.urandom(32)` but the module does not import `os`. This will raise a | 1 cell(s) |
| db.c:42 | MEDIUM | `sqlite3_close(db);` can fail, for example if there are outstanding prepared statements or active op | 1 cell(s) |
| experimental.c:5 | MEDIUM | The function `prototype_function()` is declared but has no implementation (just a comment "Implement | 1 cell(s) |
| experimental.c:6 | MEDIUM | The comment block `/* Experimental code - subject to change */` and the appended `/* End of experime | 1 cell(s) |
| ffi.rs:11 | MEDIUM | The diff adds `// C compatibility layer` at the bottom of the file, but line 1 already declares `//! | 1 cell(s) |
| ffi.rs:9 | MEDIUM | The comment `// C compatibility layer` is immediately followed by a stack-allocated variable (`x`) w | 1 cell(s) |
| fileio.c:12 | MEDIUM | The original code uses `perror("fopen")` which prints a generic error message to stderr but does not | 1 cell(s) |
| helpers.rs:2 | MEDIUM | The module comment says “Provides path normalization utilities”, but the only function performs a lo | 1 cell(s) |
| legacy.rs:10 | MEDIUM | The `#[deprecated]` attribute is applied to the `old_style_function` without any message or since ve | 1 cell(s) |
| legacy.rs:12 | MEDIUM | The `#[deprecated]` attribute is placed on its own line without being attached to any item (function | 1 cell(s) |
| legacy.rs:7 | MEDIUM | The line `#[deprecated]` is placed by itself, not attached to any item (function, module, etc.). In | 1 cell(s) |
| legacy.rs:8 | MEDIUM | The `#[deprecated]` attribute is added without any explanation, documentation, or migration guidance | 1 cell(s) |
| lib.rs:20 | MEDIUM | The new function `batch_process` is exported as a public API. Adding a new public symbol expands the | 1 cell(s) |
| logging.py:15 | MEDIUM | The newly added public function `get_logger` has no docstring. Public helpers should document *what* | 1 cell(s) |
| logging.py:18 | MEDIUM | `get_logger()` is a pass-through to `logging.getLogger(name)`. It does not configure logging, valida | 1 cell(s) |
| main.c:2 | MEDIUM | [REASON] The comment says `Handles command-line arguments`, but the added `main()` does not use `arg | 1 cell(s) |
| main.rs:2 | MEDIUM | The code calls `env::args()` without bringing `std::env` into scope. This results in a compilation e | 1 cell(s) |
| network.c:9 | MEDIUM | A stray `#endif` is added without a matching `#if`/`#ifdef`. This makes the file fail to compile, br | 1 cell(s) |
| parser.py:17 | MEDIUM | The `json.loads(text)` call can raise `json.JSONDecodeError` (or other exceptions) for malformed inp | 1 cell(s) |
| parser.py:18 | MEDIUM | The `parse_json` function lacks error handling for malformed JSON input. It directly returns `json.l | 1 cell(s) |
| plugin.py:1 | MEDIUM | The added comment `# Plugin interface` adds zero information. The file is named `plugin.py`, the cla | 1 cell(s) |
| plugin.py:14 | MEDIUM | The diff adds a new abstract base class `Plugin` with an `execute()` method but provides no mechanis | 1 cell(s) |
| protocol.c:33 | MEDIUM | `free_packet()` dereferences `pkt` to read `pkt->payload` before checking whether `pkt` is NULL. `fr | 1 cell(s) |
| queue.rs:14 | MEDIUM | The `Drop` implementation calls `self.items.clear()` which may internally acquire a lock. If the `Qu | 1 cell(s) |
| queue.rs:5 | MEDIUM | The added `impl<T> Drop for Queue<T>` simply calls `self.items.clear()`. When a `Queue` is dropped, | 1 cell(s) |
| routes.py | MEDIUM | The patch adds three comments — `# API route definitions`, `# Flask blueprint for REST endpoints`, a | 1 cell(s) |
| routes.py:5 | MEDIUM | The diff adds a new comment block labeled "# Route handlers below" but does not include any actual r | 1 cell(s) |
| server.c:16 | MEDIUM | The variable serves no purpose; it adds dead code, triggers a compiler warning, and suggests an unfi | 1 cell(s) |
| server.c:19 | MEDIUM | The code checks `if (n <= 0)` but only breaks the loop without handling the error case. When `read() | 1 cell(s) |
| stream.py:1 | MEDIUM | The new module-level docstring `"""Streaming data processing."""` is too vague and does not document | 1 cell(s) |
| threads.rs:20 | MEDIUM | `let _ = handle.join();` discards the `Err` value returned by `JoinHandle::join()`. If a worker thre | 1 cell(s) |
| unknown_feature.py:1 | MEDIUM | The diff introduces a new function `experimental_function` with no justification for why it cannot b | 1 cell(s) |
| unknown_feature.py:5 | MEDIUM | `# Experimental feature` and `# Do not use in production` on line 11 are vague. They do not explain | 1 cell(s) |
| unknown_feature.py:7 | MEDIUM | `experimental_function()` is marked experimental, and the added comment says `# Do not use in produc | 1 cell(s) |
| utils.py — `validate_port` (diff line | MEDIUM | The function signature now accepts a `strict: bool = False` argument, but the body is still just `re | 1 cell(s) |
| utils.py, `validate_port` signature (diff line | MEDIUM | The `strict` parameter is introduced into the public signature of `validate_port`, but the function | 1 cell(s) |
| utils.py:17 | MEDIUM | The file lacks a trailing newline, which violates POSIX and many style guides. While not a correctne | 1 cell(s) |
| utils.py:18 | MEDIUM | `validate_port` now takes an extra `strict` argument. Existing callers that import this function wil | 1 cell(s) |
| utils.py:20 | MEDIUM | `validate_port` previously accepted a single `port` argument. The patch adds a second, optional `str | 1 cell(s) |
| validation.c:6 | MEDIUM | The change adds a check `*input == '\0'` to treat empty strings as invalid input. This modifies the | 1 cell(s) |
| validation.c:8 | MEDIUM | The function `validate_input` now returns `-1` for both a NULL input and an empty string input, but | 1 cell(s) |
| validator.py:10 | MEDIUM | The pattern uses `$`, and in Python `$` matches at the end of the string or before a final newline. | 1 cell(s) |

### Unmatched Count by Pairing

- glm5.2×gpt-oss-120b: 44 unmatched
- qwen3.8-27b×qwen3.8-27b: 42 unmatched
- glm5.2×glm5.2: 40 unmatched
- glm5.2×mistral-small-4-119b: 38 unmatched
- gpt-oss-120b×glm5.2: 34 unmatched
- mistral-small-4-119b×qwen3.8-27b: 30 unmatched
- gpt-oss-120b×qwen3.8-27b: 26 unmatched
- mistral-small-4-119b×glm5.2: 26 unmatched
- mistral-small-4-119b×gpt-oss-120b: 26 unmatched
- mistral-small-4-119b×mistral-small-4-119b: 25 unmatched
- gpt-oss-120b×gpt-oss-120b: 24 unmatched
- gpt-oss-120b×mistral-small-4-119b: 24 unmatched
- glm5.2×qwen3.8-27b: 20 unmatched
- qwen3.8-27b×glm5.2: 11 unmatched
- qwen3.8-27b×gpt-oss-120b: 9 unmatched

*Note: High unmatched rates may indicate hallucinated findings rather than new bugs.*


---

## Cross-Only Discoveries

Bugs found only when cross-applying skills (not by native pair).


### Diff DIFF-034

- Removed blank line before function, inconsistent with PEP 8 — found by gpt-oss-120b×none

- Removed blank line before function, inconsistent with PEP 8 — found by mistral-small-4-119b×none

- Removed blank line before function, inconsistent with PEP 8 — found by mistral-small-4-119b×glm5.2

- Removed blank line before function, inconsistent with PEP 8 — found by mistral-small-4-119b×qwen3.8-27b


### Diff DIFF-035

- allocation_count field added but never incremented — found by mistral-small-4-119b×none

- allocation_count field added but never incremented — found by mistral-small-4-119b×gpt-oss-120b

- allocation_count field added but never incremented — found by mistral-small-4-119b×glm5.2


### Cross-Only Count by Skill

- none: 3 cross-only discoveries
- glm5.2: 2 cross-only discoveries
- qwen3.8-27b: 1 cross-only discoveries
- gpt-oss-120b: 1 cross-only discoveries

---

## Consensus Analysis

For each ground-truth bug, how many of the four reviewing models found it (union across all skills). Full consensus = 4/4.

| Finders | Bugs Found | % of Ground Truth |
|---------|-------------|--------------------|
| 4/4 models | 2 | 8% |
| 3/4 models | 6 | 24% |
| 2/4 models | 10 | 40% |
| 1/4 models | 7 | 28% |
| 0/4 models (missed) | 0 | 0% |

### Bug Details by Consensus

#### Full Consensus (4/4 models)

| Bug ID | File | Severity | Category | Description | Found By |
|--------|------|----------|----------|-------------|-----------|
| DIFF-006 | ? | request-changes | api-stability | Changed error variant name without deprecation warning | glm5.2, gpt-oss-120b, mistral-small-4-119b, qwen3.8-27b |
| DIFF-040 | ? | request-changes | error-handling | Nested context managers may not handle response errors correctly | glm5.2, gpt-oss-120b, mistral-small-4-119b, qwen3.8-27b |

#### Three Models (3/4)

| Bug ID | File | Severity | Category | Description | Found By |
|--------|------|----------|----------|-------------|-----------|
| DIFF-002 | ? | request-changes | api-stability | Added encoding parameter without updating docstring | gpt-oss-120b, mistral-small-4-119b, qwen3.8-27b |
| DIFF-003 | ? | nitpick | style | Debug print statement left in production code | gpt-oss-120b, mistral-small-4-119b, qwen3.8-27b |
| DIFF-007 | ? | reject | correctness | cache_get uses undefined variable 'hash' without recomputing hash_key result | gpt-oss-120b, mistral-small-4-119b, qwen3.8-27b |
| DIFF-008 | ? | nitpick | abstraction | Added unused 'strict' parameter without implementation | gpt-oss-120b, mistral-small-4-119b, qwen3.8-27b |
| DIFF-009 | ? | nitpick | style | Redundant 'id: id' syntax instead of shorthand field initialization | glm5.2, gpt-oss-120b, qwen3.8-27b |
| DIFF-041 | ? | nitpick | abstraction | Missing bounds on T for IntoIterator result type | glm5.2, mistral-small-4-119b, qwen3.8-27b |

#### Two Models (2/4)

| Bug ID | File | Severity | Category | Description | Found By |
|--------|------|----------|----------|-------------|-----------|
| DIFF-004 | ? | request-changes | error-handling | Added error check for socket creation but inconsistent return style | mistral-small-4-119b, qwen3.8-27b |
| DIFF-005 | ? | nitpick | complexity | Magic constant MAX_TOKENS should be documented or made configurable | gpt-oss-120b, mistral-small-4-119b |
| DIFF-010 | ? | request-changes | memory-safety | Moved sqlite3_free before error check, potentially freeing uninitialized memory on first call | mistral-small-4-119b, qwen3.8-27b |
| DIFF-031 | ? | request-changes | correctness | Resize calculation may overflow on large allocations | gpt-oss-120b, mistral-small-4-119b |
| DIFF-032 | ? | reject | memory-safety | Salt generated but not stored with hash, making verification impossible | gpt-oss-120b, mistral-small-4-119b |
| DIFF-033 | ? | request-changes | concurrency | Added Clone bound but parallel_reduce incomplete, missing body | gpt-oss-120b, mistral-small-4-119b |
| DIFF-037 | ? | nitpick | documentation | Added docstring but missing type hints for Iterator generic parameters | mistral-small-4-119b, qwen3.8-27b |
| DIFF-039 | ? | nitpick | correctness | Setting fp to NULL has no effect on caller's pointer | gpt-oss-120b, qwen3.8-27b |
| DIFF-042 | ? | request-changes | correctness | is_valid_identifier doesn't check for valid identifier characters after first | mistral-small-4-119b, qwen3.8-27b |
| DIFF-044 | ? | nitpick | style | Duplicate trait bound F: FnOnce() + Send + 'static on line 12 and 13 | glm5.2, mistral-small-4-119b |

#### Sole Discovery (1/4 model)

| Bug ID | File | Severity | Category | Description | Found By |
|--------|------|----------|----------|-------------|-----------|
| DIFF-001 | ? | nitpick | correctness | Magic number 10000 used without documentation for packet size threshold | qwen3.8-27b |
| DIFF-034 | ? | nitpick | style | Removed blank line before function, inconsistent with PEP 8 | mistral-small-4-119b |
| DIFF-035 | ? | nitpick | performance | allocation_count field added but never incremented | mistral-small-4-119b |
| DIFF-036 | ? | nitpick | error-handling | Using -EINVAL without including errno.h or defining it | mistral-small-4-119b |
| DIFF-038 | ? | nitpick | complexity | Unnecessary intermediate variable 'counter' in shared_counter function | qwen3.8-27b |
| DIFF-043 | ? | nitpick | abstraction | Changed encoding to utf-8-sig without documenting BOM handling | mistral-small-4-119b |
| DIFF-045 | ? | nitpick | process | Added stream_t struct but no constructor or destructor functions | mistral-small-4-119b |

**2 bug(s) reached full consensus** — found by all four models. These represent the easiest-to-detect defects.

**7 bug(s) found by only one model** — these highlight model-specific strengths and potential complementarity.


---

## Native Pairing Advantage

For each model, compare its native skill (model == skill) against the mean of cross-skills (model != skill). Positive delta = native skill helps; negative = cross-skill helps. This measures native-skill advantage, not skill-on vs skill-off — for that comparison see [report/comparison.md](report/comparison.md).

| Model | Native DS | Cross-Skill Mean DS | Delta | Verdict |
|-------|----------|---------------------|-------|---------|
| glm5.2 | 0.08 | 0.06 | +0.01 | native helps |
| gpt-oss-120b | 0.17 | 0.17 | +0.00 | no difference |
| mistral-small-4-119b | 0.51 | 0.46 | +0.06 | native helps |
| qwen3.8-27b | 0.28 | 0.21 | +0.07 | native helps |

## Best Skill per Model

For each model, the skill that produces the highest Detection Score. Since true-positive counts are model-driven while the skill mainly affects the false-positive rate, the recommended skill is the one that maximizes DS (i.e., minimizes false positives).

| Model | Best Skill(s) | DS | Recommendation |
|-------|--------------|----|----------------|
| glm5.2 | qwen3.8-27b | 0.08 | cross-skill `qwen3.8-27b` |
| gpt-oss-120b | mistral-small-4-119b | 0.22 | cross-skill `mistral-small-4-119b` |
| mistral-small-4-119b | mistral-small-4-119b | 0.51 | native skill |
| qwen3.8-27b | qwen3.8-27b | 0.28 | native skill |


---

## Judge Score Detail

**Secondary metric.** The judge does **not** affect the Detection Score (DS), true positives, recall, or precision — all detection metrics are computed by matching findings to ground truth. The judge only provides four quality sub-scores (accuracy, prioritization, justification, actionability) on a 0–2 scale, aggregated into the Judge Score (J) shown in the matrices above. Use J to break ties, never to rank. Disable with `--no-judge`.

> **Conflict of interest**: the judge (GLM5.2) also participates in the evaluation as a reviewer, so its self-scored reviews may reflect self-preference.


Each sub-score is the mean over evaluated diffs on a 0–2 scale; values vary little across pairings, so they are shown as appendix detail.

### Judge Accuracy Matrix

| Skill \\ Model | glm5.2 | gpt-oss-120b | mistral-small-4-119b | qwen3.8-27b |
|---|---|---|---|---|
| glm5.2 | 1.5 | 0.9 | 0.6 | 1.1 |
| gpt-oss-120b | 1.7 | 1.0 | 0.6 | 1.2 |
| mistral-small-4-119b | 1.4 | 1.0 | 0.7 | — |
| qwen3.8-27b | 1.6 | 1.2 | 0.6 | 1.5 |
| No skill (baseline) | 1.7 | 1.0 | 1.1 | 1.5 |


### Judge Prioritization Matrix

| Skill \\ Model | glm5.2 | gpt-oss-120b | mistral-small-4-119b | qwen3.8-27b |
|---|---|---|---|---|
| glm5.2 | 1.1 | 0.9 | 0.8 | 1.1 |
| gpt-oss-120b | 1.2 | 1.0 | 0.7 | 1.1 |
| mistral-small-4-119b | 1.1 | 0.8 | 0.7 | — |
| qwen3.8-27b | 1.2 | 1.0 | 0.8 | 1.3 |
| No skill (baseline) | 1.2 | 0.8 | 0.9 | 1.3 |


### Judge Justification Matrix

| Skill \\ Model | glm5.2 | gpt-oss-120b | mistral-small-4-119b | qwen3.8-27b |
|---|---|---|---|---|
| glm5.2 | 1.6 | 1.2 | 1.0 | 1.3 |
| gpt-oss-120b | 1.9 | 1.0 | 0.7 | 1.4 |
| mistral-small-4-119b | 1.6 | 1.0 | 0.9 | — |
| qwen3.8-27b | 1.7 | 1.2 | 1.0 | 1.6 |
| No skill (baseline) | 1.8 | 0.9 | 1.2 | 1.7 |


### Judge Actionability Matrix

| Skill \\ Model | glm5.2 | gpt-oss-120b | mistral-small-4-119b | qwen3.8-27b |
|---|---|---|---|---|
| glm5.2 | 1.6 | 1.2 | 1.1 | 1.3 |
| gpt-oss-120b | 1.9 | 1.0 | 1.0 | 1.3 |
| mistral-small-4-119b | 1.6 | 1.0 | 1.0 | — |
| qwen3.8-27b | 1.7 | 1.2 | 1.1 | 1.6 |
| No skill (baseline) | 1.8 | 0.9 | 1.2 | 1.8 |


## Limitations

- **n=45 (25 buggy)**: Evaluation based on 45 diff scenarios, of which 25 contain ground-truth bugs.

- **Repetitions**: each model+skill pairing was evaluated 1x per diff scenario.

- **Judge COI**: The judge (GLM5.2) also participates as a reviewer, so judge scores may reflect self-preference.

- **Prompt provenance**: reviewers never saw the ground-truth bug list, so these numbers measure detection against the ground-truth bug list.

- **Denominator choice**: Recall denominator uses only buggy diffs (expected=="findings"); findings on clean or refusal scenarios count as false positives.


