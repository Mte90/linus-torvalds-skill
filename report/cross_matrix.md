# Cross-Model Evaluation Matrix

Diagonal data from `data/eval_results.jsonl`, cross-data from `data/eval_results_cross.jsonl`.

*Note: Each model judges its own reviews (self-judge).*

## Overview Matrix

Each cell shows: F1 score, Refusal rate, and mean Judge score (0–2 scale).

*(native)* indicates diagonal pairing (model == skill).

| Skill \\ Model | glm5.2 | gpt-oss-120b | mistral-small-4-119b | qwen3.8-27b |
|---|---|---|---|
| **glm5.2** | F1=0.22 R=0% J=1.0/2 *(native)* | F1=0.36 R=0% J=1.0/2 | F1=0.49 R=0% J=1.1/2 | F1=0.55 R=0% J=0.9/2 |
| **gpt-oss-120b** | F1=0.24 R=0% J=1.5/2 | F1=0.41 R=0% J=1.1/2 *(native)* | F1=0.49 R=0% J=1.4/2 | F1=0.55 R=0% J=0.9/2 |
| **mistral-small-4-119b** | F1=0.24 R=0% J=1.1/2 | F1=0.35 R=0% J=1.1/2 | F1=0.49 R=0% J=1.0/2 *(native)* | F1=0.52 R=0% J=0.9/2 |
| **qwen3.8-27b** | F1=0.19 R=0% J=1.2/2 | F1=0.38 R=0% J=1.0/2 | F1=0.47 R=0% J=1.2/2 | F1=0.54 R=0% J=0.8/2 *(native)* |


## Precision Matrix

| Skill \\ Model |glm5.2 |gpt-oss-120b |mistral-small-4-119b |qwen3.8-27b |
|---|---|---|---|
| glm5.2 | 0.20 | 0.31 | 0.49 | 0.54 |
| gpt-oss-120b | 0.24 | 0.40 | 0.49 | 0.54 |
| mistral-small-4-119b | 0.24 | 0.33 | 0.49 | 0.49 |
| qwen3.8-27b | 0.18 | 0.35 | 0.47 | 0.52 |


## Recall Matrix

| Skill \\ Model |glm5.2 |gpt-oss-120b |mistral-small-4-119b |qwen3.8-27b |
|---|---|---|---|
| glm5.2 | 0.24 | 0.42 | 0.49 | 0.56 |
| gpt-oss-120b | 0.24 | 0.42 | 0.49 | 0.56 |
| mistral-small-4-119b | 0.24 | 0.38 | 0.49 | 0.56 |
| qwen3.8-27b | 0.20 | 0.40 | 0.47 | 0.56 |


## Refusal Rate Matrix

| Skill \\ Model |glm5.2 |gpt-oss-120b |mistral-small-4-119b |qwen3.8-27b |
|---|---|---|---|
| glm5.2 | 0% | 0% | 0% | 0% |
| gpt-oss-120b | 0% | 0% | 0% | 0% |
| mistral-small-4-119b | 0% | 0% | 0% | 0% |
| qwen3.8-27b | 0% | 0% | 0% | 0% |


## Judge Accuracy Matrix

| Skill \\ Model |glm5.2 |gpt-oss-120b |mistral-small-4-119b |qwen3.8-27b |
|---|---|---|---|
| glm5.2 | 0.9 | 0.9 | 1.2 | 0.9 |
| gpt-oss-120b | 1.6 | 1.0 | 1.5 | 0.9 |
| mistral-small-4-119b | 1.3 | 1.1 | 1.0 | 0.9 |
| qwen3.8-27b | 1.4 | 1.1 | 1.3 | 0.7 |


## Judge Prioritization Matrix

| Skill \\ Model |glm5.2 |gpt-oss-120b |mistral-small-4-119b |qwen3.8-27b |
|---|---|---|---|
| glm5.2 | 0.6 | 0.5 | 0.9 | 0.6 |
| gpt-oss-120b | 1.1 | 0.6 | 1.2 | 0.6 |
| mistral-small-4-119b | 0.8 | 0.6 | 0.6 | 0.6 |
| qwen3.8-27b | 0.9 | 0.6 | 1.1 | 0.5 |


## Judge Justification Matrix

| Skill \\ Model |glm5.2 |gpt-oss-120b |mistral-small-4-119b |qwen3.8-27b |
|---|---|---|---|
| glm5.2 | 1.2 | 1.2 | 1.2 | 1.0 |
| gpt-oss-120b | 1.6 | 1.3 | 1.5 | 1.0 |
| mistral-small-4-119b | 1.1 | 1.3 | 1.1 | 1.0 |
| qwen3.8-27b | 1.3 | 1.2 | 1.3 | 1.0 |


## Judge Actionability Matrix

| Skill \\ Model |glm5.2 |gpt-oss-120b |mistral-small-4-119b |qwen3.8-27b |
|---|---|---|---|
| glm5.2 | 1.2 | 1.3 | 1.2 | 1.0 |
| gpt-oss-120b | 1.6 | 1.3 | 1.5 | 1.0 |
| mistral-small-4-119b | 1.1 | 1.4 | 1.3 | 1.0 |
| qwen3.8-27b | 1.3 | 1.3 | 1.3 | 1.0 |


## Best Pairing by Metric

- **Best F1**: qwen3.8-27b on gpt-oss-120b (F1=0.55)

- **Best Refusal Rate**: gpt-oss-120b on gpt-oss-120b *(native)* (R=0%)

- **Best Judge Score**: glm5.2 on gpt-oss-120b (J=1.5/2)


---

## Marginal Analysis

Row means (per reviewing model across skills) and column means (per skill across models).

**Best Model**: qwen3.8-27b (row-mean F1=0.54, judge=0.9, refusal=0%)

**Best Skill**: gpt-oss-120b (column-mean F1=0.42, judge=1.2, refusal=0%)


### Model Rankings (by row-mean F1)

| Rank | Model | F1 | Judge Mean | Refusal Rate |
|------|-------|----|------------|-------------|
| 1 | qwen3.8-27b | 0.54 | 0.9 | 0% |
| 2 | mistral-small-4-119b | 0.48 | 1.2 | 0% |
| 3 | gpt-oss-120b | 0.37 | 1.1 | 0% |
| 4 | glm5.2 | 0.23 | 1.2 | 0% |

### Skill Rankings (by column-mean F1)

| Rank | Skill | F1 | Judge Mean | Refusal Rate |
|------|-------|----|------------|-------------|
| 1 | gpt-oss-120b | 0.42 | 1.2 | 0% |
| 2 | glm5.2 | 0.40 | 1.0 | 0% |
| 3 | mistral-small-4-119b | 0.40 | 1.0 | 0% |
| 4 | qwen3.8-27b | 0.39 | 1.1 | 0% |

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

*Generated from `data/eval_results.jsonl` (diagonal) and `data/eval_results_cross.jsonl` (cross).*

*Each model judges its own reviews (self-judge).*
