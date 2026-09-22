# Cross-Model Evaluation Matrix

Diagonal data from `data/eval_results.jsonl`, cross-data from `data/eval_results_cross.jsonl`.

*Judge model: GLM5.2 (fixed external judge, applied via `--rescore-all`).*

## Verdict

**Best pairing**: `qwen3.8-27b` reviewing with `qwen3.8-27b` skill found **25 bugs** out of 45 ground-truth bugs.

**Best Detection Score**: `qwen3.8-27b` on `gpt-oss-120b` (DS=0.55).

**Best Judge Score**: `glm5.2` on `gpt-oss-120b` (J=1.6/2).

**Best critical-bug pairing**: `gpt-oss-120b` on `glm5.2` found **4** `reject`-severity bugs.

**Best reviewer model**: `gpt-oss-120b` found **25** bugs (56% coverage) across all skills.

**Best skill**: `gpt-oss-120b` found **25** bugs (56% coverage) across all models.

**Consensus**: 17 bug(s) found by every model (across all skill pairings), 0 by only one model, 20 missed by all. This measures inter-model agreement, not skill-on vs skill-off.

**Native pairing advantage**: glm5.2: no difference; gpt-oss-120b: native helps; mistral-small-4-119b: no difference; qwen3.8-27b: no difference.

**Best skill per model**: 1 model(s) perform best with their native skill, 3 with a cross-skill. See the *Best Skill per Model* table below for specifics.

See `report/comparison.md` for the baseline-vs-skill analysis (whether adding any skill helps or hurts each model).



## Metrics Glossary

- **Detection Score (DS)**: Harmonic mean of precision and recall. Measures how well findings balance correctness (precision) against completeness (recall). Range 0–1; higher is better.

- **Precision**: Of all findings reported, the fraction that matched a ground-truth bug. Low precision means many false positives.

- **Recall**: Of all ground-truth bugs, the fraction that were found. Low recall means missed bugs.

- **Refusal Rate (R)**: Fraction of diffs where the model refused to review. In this dataset R=0 for all pairings, so it is omitted from the tables.

- **Judge Score (J)**: Mean of four sub-scores (accuracy, prioritization, justification, actionability) on a 0–2 scale. Reflects review quality as scored by the judge model.

- **Native**: Diagonal pairing where the model reviews a diff using its own skill (model == skill).

- **Exclusive**: Bugs found by this model/skill and no other model/skill. A high exclusive count means the pairing contributes unique value.


---

## Overview Matrix

Each cell shows: Detection Score (DS), and mean Judge score (0–2 scale).

*(native)* indicates diagonal pairing (model == skill).

| Skill \\ Model | glm5.2 | gpt-oss-120b | mistral-small-4-119b | qwen3.8-27b |
|---|---|---|---|---|
| **glm5.2** | DS=0.22 J=1.2/2 *(native)* | DS=0.36 J=1.1/2 | DS=0.49 J=0.9/2 | DS=0.55 J=1.1/2 |
| **gpt-oss-120b** | DS=0.24 J=1.6/2 | DS=0.41 J=1.2/2 *(native)* | DS=0.49 J=1.0/2 | DS=0.55 J=1.0/2 |
| **mistral-small-4-119b** | DS=0.24 J=1.1/2 | DS=0.35 J=1.2/2 | DS=0.49 J=1.1/2 *(native)* | DS=0.52 J=1.1/2 |
| **qwen3.8-27b** | DS=0.19 J=1.2/2 | DS=0.38 J=1.1/2 | DS=0.47 J=1.1/2 | DS=0.54 J=1.0/2 *(native)* |


## Precision Matrix

| Skill \\ Model |glm5.2 |gpt-oss-120b |mistral-small-4-119b |qwen3.8-27b |
|---|---|---|---|---|
| glm5.2 | 0.20 | 0.31 | 0.49 | 0.54 |
| gpt-oss-120b | 0.24 | 0.40 | 0.49 | 0.54 |
| mistral-small-4-119b | 0.24 | 0.33 | 0.49 | 0.49 |
| qwen3.8-27b | 0.18 | 0.35 | 0.47 | 0.52 |


## Recall Matrix

| Skill \\ Model |glm5.2 |gpt-oss-120b |mistral-small-4-119b |qwen3.8-27b |
|---|---|---|---|---|
| glm5.2 | 0.24 | 0.42 | 0.49 | 0.56 |
| gpt-oss-120b | 0.24 | 0.42 | 0.49 | 0.56 |
| mistral-small-4-119b | 0.24 | 0.38 | 0.49 | 0.56 |
| qwen3.8-27b | 0.20 | 0.40 | 0.47 | 0.56 |


## Judge Accuracy Matrix

| Skill \\ Model |glm5.2 |gpt-oss-120b |mistral-small-4-119b |qwen3.8-27b |
|---|---|---|---|---|
| glm5.2 | 1.3 | 1.1 | 1.0 | 1.2 |
| gpt-oss-120b | 1.7 | 1.3 | 1.2 | 1.2 |
| mistral-small-4-119b | 1.3 | 1.3 | 1.2 | 1.2 |
| qwen3.8-27b | 1.3 | 1.2 | 1.2 | 1.2 |


## Judge Prioritization Matrix

| Skill \\ Model |glm5.2 |gpt-oss-120b |mistral-small-4-119b |qwen3.8-27b |
|---|---|---|---|---|
| glm5.2 | 1.1 | 1.0 | 0.9 | 1.0 |
| gpt-oss-120b | 1.2 | 1.0 | 0.9 | 0.9 |
| mistral-small-4-119b | 1.0 | 1.1 | 1.0 | 0.9 |
| qwen3.8-27b | 1.0 | 1.0 | 1.0 | 1.0 |


## Judge Justification Matrix

| Skill \\ Model |glm5.2 |gpt-oss-120b |mistral-small-4-119b |qwen3.8-27b |
|---|---|---|---|---|
| glm5.2 | 1.2 | 1.2 | 0.9 | 1.1 |
| gpt-oss-120b | 1.7 | 1.3 | 1.1 | 1.1 |
| mistral-small-4-119b | 1.2 | 1.3 | 1.2 | 1.1 |
| qwen3.8-27b | 1.3 | 1.2 | 1.1 | 1.0 |


## Judge Actionability Matrix

| Skill \\ Model |glm5.2 |gpt-oss-120b |mistral-small-4-119b |qwen3.8-27b |
|---|---|---|---|---|
| glm5.2 | 1.1 | 1.2 | 0.9 | 1.0 |
| gpt-oss-120b | 1.6 | 1.2 | 1.0 | 1.0 |
| mistral-small-4-119b | 1.1 | 1.2 | 1.1 | 1.1 |
| qwen3.8-27b | 1.3 | 1.1 | 1.0 | 1.0 |


## Native Pairing Ranking (model == skill)

Diagonal cells only — each model using its own skill.

| Model | Detection Score | Bugs Found | Judge Score |
|-------|-----------------|------------|-------------|
| qwen3.8-27b | 0.54 | 25/45 | 1.0/2 |
| mistral-small-4-119b | 0.49 | 22/45 | 1.1/2 |
| gpt-oss-120b | 0.41 | 19/45 | 1.2/2 |
| glm5.2 | 0.22 | 11/45 | 1.2/2 |

## Best Pairing by Metric

- **Best Detection Score**: qwen3.8-27b on gpt-oss-120b (DS=0.55)

- **Best Judge Score**: glm5.2 on gpt-oss-120b (J=1.6/2)


---

## Marginal Analysis

Row means (per reviewing model across skills) and column means (per skill across models).

**Best Model**: qwen3.8-27b (row-mean DS=0.54, judge=1.1)

**Best Skill**: gpt-oss-120b (column-mean DS=0.42, judge=1.2)


### Model Rankings (by row-mean Detection Score)

| Rank | Model | Detection Score | Judge Mean | Rarity Score |
|------|-------|-----------------|------------|--------------|
| 1 | qwen3.8-27b | 0.54 | 1.1 | 0.15 |
| 2 | mistral-small-4-119b | 0.48 | 1.0 | 0.15 |
| 3 | gpt-oss-120b | 0.37 | 1.1 | 0.15 |
| 4 | glm5.2 | 0.23 | 1.3 | 0.09 |

### Skill Rankings (by column-mean Detection Score)

| Rank | Skill | Detection Score | Judge Mean | Rarity Score |
|------|-------|-----------------|------------|--------------|
| 1 | gpt-oss-120b | 0.42 | 1.2 | 0.15 |
| 2 | glm5.2 | 0.40 | 1.1 | 0.15 |
| 3 | mistral-small-4-119b | 0.40 | 1.1 | 0.15 |
| 4 | qwen3.8-27b | 0.39 | 1.1 | 0.15 |

---

## Bug Discovery Ranking

Ground-truth bugs: **45**

### Bugs Found per Pairing (True Positives)

| Model | Skill | Bugs Found (TP) | False Positives | Total Findings |
|-------|-------|-----------------|-----------------|----------------|
| qwen3.8-27b | qwen3.8-27b *(native)* | 25 | 23 | 48 |
| qwen3.8-27b | gpt-oss-120b | 25 | 21 | 46 |
| qwen3.8-27b | glm5.2 | 25 | 21 | 46 |
| qwen3.8-27b | mistral-small-4-119b | 25 | 26 | 51 |
| mistral-small-4-119b | mistral-small-4-119b *(native)* | 22 | 23 | 45 |
| mistral-small-4-119b | gpt-oss-120b | 22 | 23 | 45 |
| mistral-small-4-119b | glm5.2 | 22 | 23 | 45 |
| mistral-small-4-119b | qwen3.8-27b | 21 | 24 | 45 |
| gpt-oss-120b | gpt-oss-120b *(native)* | 19 | 29 | 48 |
| gpt-oss-120b | glm5.2 | 19 | 43 | 62 |
| gpt-oss-120b | qwen3.8-27b | 18 | 33 | 51 |
| gpt-oss-120b | mistral-small-4-119b | 17 | 35 | 52 |
| glm5.2 | glm5.2 *(native)* | 11 | 43 | 54 |
| glm5.2 | gpt-oss-120b | 11 | 34 | 45 |
| glm5.2 | mistral-small-4-119b | 11 | 34 | 45 |
| glm5.2 | qwen3.8-27b | 9 | 40 | 49 |

### Bugs Found per Model (union across all skills)

| Model | Total Found | Coverage | Exclusive |
|-------|-------------|----------|-----------|
| gpt-oss-120b | 25 | 56% | 0 |
| mistral-small-4-119b | 25 | 56% | 0 |
| qwen3.8-27b | 25 | 56% | 0 |
| glm5.2 | 17 | 38% | 0 |

### Bugs Found per Skill (union across all models)

| Skill | Total Found | Coverage | Exclusive |
|-------|-------------|----------|-----------|
| gpt-oss-120b | 25 | 56% | 0 |
| glm5.2 | 25 | 56% | 0 |
| mistral-small-4-119b | 25 | 56% | 0 |
| qwen3.8-27b | 25 | 56% | 0 |

### Bugs Found by Only One Model

No bugs found by only one model — every discovered bug was found by at least two models.


### Bugs Found by Severity (union across all pairings)

| Severity | Total Bugs Found |
|----------|------------------|
| reject | 29 |
| request-changes | 103 |
| nitpick | 184 |

### Severity Breakdown per Model

| Model |reject|request-changes|nitpick| Total |
|-------|------|------|------|-------|
| glm5.2 | 3 | 15 | 25 | 43 |
| gpt-oss-120b | 9 | 25 | 48 | 82 |
| mistral-small-4-119b | 8 | 30 | 49 | 87 |
| qwen3.8-27b | 9 | 33 | 62 | 104 |

### Severity Breakdown per Skill

| Skill |reject|request-changes|nitpick| Total |
|-------|------|------|------|-------|
| glm5.2 | 10 | 26 | 46 | 82 |
| gpt-oss-120b | 5 | 28 | 46 | 79 |
| mistral-small-4-119b | 7 | 24 | 49 | 80 |
| qwen3.8-27b | 7 | 25 | 43 | 75 |

### Severity Breakdown per Pairing

Critical (`reject`) bug counts for each (model, skill) cell. Higher is better for critical-bug detection.

| Model | Skill | reject | total |
|-------|-------|--------|-------|
| gpt-oss-120b | glm5.2 | 4 | 23 |
| qwen3.8-27b | mistral-small-4-119b | 3 | 28 |
| qwen3.8-27b *(native)* | qwen3.8-27b | 2 | 26 |
| qwen3.8-27b | gpt-oss-120b | 2 | 25 |
| qwen3.8-27b | glm5.2 | 2 | 25 |
| mistral-small-4-119b *(native)* | mistral-small-4-119b | 2 | 22 |
| mistral-small-4-119b | gpt-oss-120b | 2 | 22 |
| mistral-small-4-119b | glm5.2 | 2 | 22 |
| mistral-small-4-119b | qwen3.8-27b | 2 | 21 |
| gpt-oss-120b | mistral-small-4-119b | 2 | 19 |
| gpt-oss-120b | qwen3.8-27b | 2 | 19 |
| glm5.2 *(native)* | glm5.2 | 2 | 12 |
| gpt-oss-120b *(native)* | gpt-oss-120b | 1 | 21 |
| glm5.2 | qwen3.8-27b | 1 | 9 |
| glm5.2 | gpt-oss-120b | 0 | 11 |
| glm5.2 | mistral-small-4-119b | 0 | 11 |

### Bugs Found by Category (union across all pairings)

| Category | Total Bugs Found |
|----------|------------------|
| correctness | 65 |
| style | 57 |
| error-handling | 42 |
| abstraction | 38 |
| api-stability | 30 |
| memory-safety | 23 |
| complexity | 21 |
| documentation | 15 |
| process | 10 |
| concurrency | 8 |
| performance | 7 |

### Category Breakdown per Model

| Model |abstraction|api-stability|complexity|concurrency|correctness|documentation|error-handling|memory-safety|performance|process|style| Total |
|-------|------|------|------|------|------|------|------|------|------|------|------|-------|
| glm5.2 | 4 | 4 | 1 | 0 | 7 | 4 | 10 | 1 | 0 | 0 | 12 | 43 |
| gpt-oss-120b | 11 | 10 | 6 | 1 | 19 | 3 | 8 | 6 | 2 | 2 | 14 | 82 |
| mistral-small-4-119b | 11 | 8 | 6 | 2 | 16 | 4 | 12 | 8 | 1 | 4 | 15 | 87 |
| qwen3.8-27b | 12 | 8 | 8 | 5 | 23 | 4 | 12 | 8 | 4 | 4 | 16 | 104 |

### Category Breakdown per Skill

| Skill |abstraction|api-stability|complexity|concurrency|correctness|documentation|error-handling|memory-safety|performance|process|style| Total |
|-------|------|------|------|------|------|------|------|------|------|------|------|-------|
| glm5.2 | 8 | 7 | 6 | 1 | 19 | 4 | 11 | 6 | 3 | 2 | 15 | 82 |
| gpt-oss-120b | 10 | 7 | 5 | 3 | 17 | 3 | 10 | 6 | 1 | 3 | 14 | 79 |
| mistral-small-4-119b | 12 | 8 | 5 | 2 | 16 | 4 | 10 | 5 | 1 | 3 | 14 | 80 |
| qwen3.8-27b | 8 | 8 | 5 | 2 | 13 | 4 | 11 | 6 | 2 | 2 | 14 | 75 |

---

## New Bug Candidates

Findings that match NO ground-truth bug — candidates for ground-truth expansion (require human triage).

| Diff ID | Model | Skill | File:Line | Severity | Issue |
|---------|-------|-------|-----------|----------|-------|
| DIFF-001 | gpt-oss-120b | gpt-oss-120b | server.c:16 | MEDIUM | `int max_retries = 3;` is declared but never read or used anywhere in the function. This adds dead c |
| DIFF-002 | gpt-oss-120b | gpt-oss-120b | utils.py:18 | MEDIUM | The signature of `validate_port` was changed from `validate_port(port: int) -> bool` to `validate_po |
| DIFF-004 | gpt-oss-120b | gpt-oss-120b | network.c | MEDIUM | The function never converts the `host` string to an IP address and never stores it in `addr.sin_addr |
| DIFF-007 | gpt-oss-120b | gpt-oss-120b | cache.c | MEDIUM | The function uses the identifier `hash` which is never defined or assigned. This is a compile‑time e |
| DIFF-013 | gpt-oss-120b | gpt-oss-120b | main.c:9 | MEDIUM | The added `int main(int argc, char *argv[]) {` opens a function block but never provides a closing b |
| DIFF-014 | gpt-oss-120b | gpt-oss-120b | utils.py:13 | MEDIUM | The module’s `__all__` list includes `"parse_date"` but no such function or symbol is defined in the |
| DIFF-015 | gpt-oss-120b | gpt-oss-120b | types.rs:7 | MEDIUM | The diff adds an `impl Default for Config {` block but does not provide the required `fn default() - |
| DIFF-018 | gpt-oss-120b | gpt-oss-120b | error.rs | MEDIUM | The diff adds a straightforward `Display` implementation for the existing `Error` enum without intro |
| DIFF-019 | gpt-oss-120b | gpt-oss-120b | network.c | MEDIUM | The diff adds a stray `#endif` with no corresponding `#if`/`#ifdef` directive. This will cause the c |
| DIFF-024 | gpt-oss-120b | gpt-oss-120b | queue.rs | MEDIUM | The `drop` method only calls `self.items.clear()`. When `Queue` is dropped, its field `items` (presu |
| DIFF-025 | gpt-oss-120b | gpt-oss-120b | test.c:7 | MEDIUM | The newly added `static int test_count = 0;` is never read or written anywhere in the file, which wi |
| DIFF-027 | gpt-oss-120b | gpt-oss-120b | legacy.rs:9 | MEDIUM | The `#[deprecated]` attribute is placed without an accompanying item. In Rust an attribute must appl |
| DIFF-035 | gpt-oss-120b | gpt-oss-120b | memory.rs | MEDIUM | The new `allocation_count` field is never updated anywhere in the code. Consequently `allocations()` |
| DIFF-037 | gpt-oss-120b | gpt-oss-120b | stream.py | MEDIUM | The function `stream_map` is annotated as `Iterator` and `Callable` without specifying the element t |
| DIFF-040 | gpt-oss-120b | gpt-oss-120b | async.py | MEDIUM | `session.get(url) as response` is already entered by the outer `async with` statement. Adding a seco |
| DIFF-042 | gpt-oss-120b | gpt-oss-120b | validation.c | MEDIUM | `is_valid_identifier` only checks that the first character is alphabetic (`isalpha(name[0])`). It re |
| DIFF-001 | glm5.2 | glm5.2 | server.c | MEDIUM | `buffer` is declared as `char buffer[1024]` and `read(fd, buffer, sizeof(buffer))` will return at mo |
| DIFF-003 | glm5.2 | glm5.2 | main.rs | MEDIUM | The `#[cfg(debug_assertions)]` guard on `println!("Debug mode enabled")` means the line only compile |
| DIFF-005 | glm5.2 | glm5.2 | parser.py | MEDIUM | `tokenize()` previously returned every token from `text.split()`. The new code silently caps the res |
| DIFF-018 | glm5.2 | glm5.2 | error.rs | MEDIUM | The `Display` implementation delegates to `Debug` formatting via `{:?}`. `Display` is the user-facin |
| DIFF-024 | glm5.2 | glm5.2 | queue.rs | MEDIUM | The `Drop` impl calls `self.items.clear()`, which manually drops every element in the underlying deq |
| DIFF-032 | glm5.2 | glm5.2 | crypto.py | MEDIUM | The new code generates `salt = os.urandom(32)` and feeds it into `pbkdf2_hmac`, but the salt is neve |
| DIFF-033 | glm5.2 | glm5.2 | parallel.rs | MEDIUM | The new `parallel_reduce` function has a full signature and opening brace but no body whatsoever: |
| DIFF-035 | glm5.2 | glm5.2 | memory.rs | MEDIUM | The diff adds an `allocation_count: usize` field to `MemoryPool`, initializes it to `0` in the const |
| DIFF-035 | glm5.2 | glm5.2 | memory.rs:15 | MEDIUM | `allocation_count` is a `usize` field that is written exactly once (to `0` in `new`) and never writt |
| DIFF-038 | glm5.2 | glm5.2 | sync.rs | MEDIUM | The `shared_counter` function creates a local variable `counter` only to return it on the next line. |
| DIFF-045 | glm5.2 | glm5.2 | streams.c | MEDIUM | A new `stream_t` struct is introduced with a raw `char *data` pointer and a `size_t size`, but no co |
| DIFF-012 | mistral-small-4-119b | mistral-small-4-119b | helpers.rs:5 | MEDIUM | The function `normalize_path` blindly converts any path to a string without validating the input. Th |
| DIFF-013 | mistral-small-4-119b | mistral-small-4-119b | main.c:7 | MEDIUM | The `main()` function is declared to return an `int` but has no `return` statement. This invokes und |
| DIFF-015 | mistral-small-4-119b | mistral-small-4-119b | types.rs:8 | MEDIUM | The `impl Default for Config` block is opened but not completed. It lacks the `default()` method imp |
| DIFF-017 | mistral-small-4-119b | mistral-small-4-119b | parser.py | MEDIUM | The added TODO comments ("Add XML parser", "support multiple formats") suggest future work that isn' |
| DIFF-018 | mistral-small-4-119b | mistral-small-4-119b | error.rs:11 | MEDIUM | The `Display` implementation uses `{:?}` (debug formatting) instead of proper user-facing output. Th |
| DIFF-019 | mistral-small-4-119b | mistral-small-4-119b | network.c | MEDIUM | The added comments are redundant and do not provide meaningful information. They state the obvious ( |
| DIFF-020 | mistral-small-4-119b | mistral-small-4-119b | app.py:23 | MEDIUM | The entry point guard uses `if __name__ == "__main__":` which is incorrect Python syntax. The compar |
| DIFF-021 | mistral-small-4-119b | mistral-small-4-119b | async.rs:1 | MEDIUM | The module-level documentation (`//! Async operations\n//! Tokio-based async utilities`) is present  |
| DIFF-023 | mistral-small-4-119b | mistral-small-4-119b | routes.py:6 | MEDIUM | The diff adds comments and a placeholder comment for route handlers but does not include any actual  |
| DIFF-033 | mistral-small-4-119b | mistral-small-4-119b | parallel.rs | MEDIUM | The `parallel_reduce` function is declared but has no implementation body. This is a syntax error th |
| DIFF-035 | mistral-small-4-119b | mistral-small-4-119b | memory.rs:15 | MEDIUM | The new field `allocation_count` is added to `MemoryPool` but never incremented, making it dead code |
| DIFF-039 | mistral-small-4-119b | mistral-small-4-119b | fileio.c:12 | MEDIUM | The original code uses `perror("fopen")` to log the error but then returns `NULL` without surfacing  |
| DIFF-002 | glm5.2 | glm5.2 | utils.py:21 | MEDIUM | The signature `validate_port(port: int, strict: bool = False) -> bool` adds a `strict` parameter tha |
| DIFF-010 | glm5.2 | glm5.2 | db.c | MEDIUM | The new line calls `sqlite3_free(err_msg)` immediately after `sqlite3_exec`, before the error check. |
| DIFF-039 | glm5.2 | glm5.2 | fileio.c | MEDIUM | `fp` is passed by value. Setting `fp = NULL` only nullifies the local copy — the caller's pointer is |
| DIFF-041 | glm5.2 | glm5.2 | iterators.rs | MEDIUM | The closure `|inner| inner.into_iter()` returns `<J as IntoIterator>::IntoIter`. For `flat_map` to i |
| DIFF-042 | glm5.2 | glm5.2 | validation.c | MEDIUM | The new function `is_valid_identifier` checks only `isalpha(name[0])` and returns immediately. It ne |
| DIFF-043 | glm5.2 | glm5.2 | config.py | MEDIUM | `load_config` now opens with `encoding="utf-8-sig"` (strips BOM, expects UTF-8), but `save_config` s |
| DIFF-008 | glm5.2 | glm5.2 | validator.py:21 | MEDIUM | `# TODO: Add more validators` is noise. It communicates nothing actionable — no context, no owner, n |
| DIFF-007 | glm5.2 | glm5.2 | cache.c | MEDIUM | `return cache[hash_key(key)]->value;` dereferences the cache slot unconditionally. When no entry exi |
| DIFF-007 | glm5.2 | glm5.2 | cache.c | MEDIUM | The global `cache[1024]` array is written by `cache_set` and read by `cache_get` with no lock, atomi |
| DIFF-007 | glm5.2 | glm5.2 | cache.c | MEDIUM | `CACHE_TTL` is `#define`d but never referenced. `time_t now = time(NULL);` is computed but never rea |
| DIFF-031 | glm5.2 | glm5.2 | buffer.c:26 | MEDIUM | `buffer_clear` previously set `buf->size = 0` and returned — constant time. The added `memset(buf->d |

### Unmatched Count by Pairing

- gpt-oss-120b×glm5.2: 27 unmatched
- glm5.2×gpt-oss-120b: 27 unmatched
- glm5.2×qwen3.8-27b: 25 unmatched
- glm5.2×glm5.2: 24 unmatched
- gpt-oss-120b×mistral-small-4-119b: 24 unmatched
- gpt-oss-120b×qwen3.8-27b: 22 unmatched
- glm5.2×mistral-small-4-119b: 17 unmatched
- gpt-oss-120b×gpt-oss-120b: 16 unmatched
- mistral-small-4-119b×mistral-small-4-119b: 12 unmatched
- mistral-small-4-119b×gpt-oss-120b: 11 unmatched
- mistral-small-4-119b×qwen3.8-27b: 9 unmatched
- mistral-small-4-119b×glm5.2: 3 unmatched
- qwen3.8-27b×mistral-small-4-119b: 3 unmatched
- qwen3.8-27b×qwen3.8-27b: 2 unmatched
- qwen3.8-27b×gpt-oss-120b: 1 unmatched
- qwen3.8-27b×glm5.2: 1 unmatched

*Note: High unmatched rates may indicate hallucinated findings rather than new bugs.*


---

## Cross-Only Discoveries

Bugs found only when cross-applying skills (not by native pair).

No cross-only discoveries.


---

## Consensus Analysis

For each ground-truth bug, how many of the four reviewing models found it (union across all skills). Full consensus = 4/4.

| Finders | Bugs Found | % of Ground Truth |
|---------|-------------|--------------------|
| 4/4 models | 17 | 38% |
| 3/4 models | 8 | 18% |
| 2/4 models | 0 | 0% |
| 1/4 models | 0 | 0% |
| 0/4 models (missed) | 20 | 44% |

**17 bug(s) reached full consensus** — found by all four models. These represent the easiest-to-detect defects.

**20 bug(s) missed by every model** — these may require skill refinement or represent subtle defects beyond current detection capability.


---

## Native Pairing Advantage

For each model, compare its native skill (model == skill) against the mean of cross-skills (model != skill). Positive delta = native skill helps; negative = cross-skill helps. This measures native-skill advantage, not skill-on vs skill-off — for that comparison see `report/comparison.md`.

| Model | Native DS | Cross-Skill Mean DS | Delta | Verdict |
|-------|----------|---------------------|-------|---------|
| glm5.2 | 0.22 | 0.23 | -0.00 | no difference |
| gpt-oss-120b | 0.41 | 0.36 | +0.05 | native helps |
| mistral-small-4-119b | 0.49 | 0.48 | +0.01 | no difference |
| qwen3.8-27b | 0.54 | 0.54 | -0.00 | no difference |

## Best Skill per Model

For each model, the skill that produces the highest Detection Score. Since true-positive counts are model-driven while the skill mainly affects the false-positive rate, the recommended skill is the one that maximizes DS (i.e., minimizes false positives).

| Model | Best Skill | DS | Recommendation |
|-------|-----------|----|----------------|
| glm5.2 | gpt-oss-120b | 0.24 | cross-skill `gpt-oss-120b` |
| gpt-oss-120b | gpt-oss-120b | 0.41 | native skill |
| mistral-small-4-119b | glm5.2 | 0.49 | cross-skill `glm5.2` |
| qwen3.8-27b | glm5.2 | 0.55 | cross-skill `glm5.2` |
