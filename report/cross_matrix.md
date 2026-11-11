# Cross-Model Evaluation Matrix

Source: full SmallChat review ([data/eval_results_codebase.jsonl](data/eval_results_codebase.jsonl)) scored against 43 ground-truth bugs from [benchmark.jsonl](data/benchmark.jsonl).

Judge: GLM5.2, a fixed external model applied at generation time (`--judge-model`). It also reviews here, so judge scores may carry self-preference.

> **Evaluation provenance:** the reviewer prompt carried only the code under review, never the ground-truth bug list (enforced by regression tests in [tests/test_eval.py](tests/test_eval.py)). Every number below therefore measures detection, not transcription.

## About this report

This report answers: **which model+skill combination detects bugs best?** It is a cross-model evaluation on the real SmallChat codebase (43 ground-truth bugs).

Three roles are at play:

1. **Reviewer model** — the model that reads the code and produces findings. It determines *which* bugs are found and drives the true-positive count.
2. **Skill** — the prompt/skill applied to the reviewer. It influences precision (false-positive rate) but rarely changes which bugs are detected.
3. **Judge model** — scores the *quality* of each review on four axes (accuracy, prioritization, justification, actionability). The judge does **not** affect the Detection Score, true positives, recall, or precision. It can be disabled with `--no-judge`.

A pairing is written `A × B`: reviewer model `A` reads the code using the skill written by `B`. `A × A` is the native pairing. For baseline-vs-skill analysis (does the skill help or hurt each model?), see [report/comparison.md](report/comparison.md).

## Verdict

A **pairing** is one reviewer model plus one skill, written `A × B`: reviewer `A` reads the code using the skill written by `B`. `A × A` is the **native** pairing, where a model uses its own skill.

**Most bugs found**

- `mistral-small-4-119b` × `glm5.2` — **8 of 43** real bugs. 32 findings: 8 matched a real bug, 5 were a duplicate, 19 matched nothing.

**Cleanest review (Detection Score)**

Detection Score weighs bugs found against findings that were not bugs, so a review that buries real bugs in noise scores lower than its bug count suggests.

- Highest: `gpt-oss-120b` × `qwen3.8-27b` — 0.24, from 8 findings: 6 matched a real bug, 1 was a duplicate, 1 matched nothing.
- The bug-count leader lands lower (32 findings: 8 matched a real bug, 5 were a duplicate, 19 matched nothing) because those extra findings are mostly not bugs.

**Best-written review (judge score)**

A separate judge model (GLM5.2) rates the write-up for clarity, prioritisation, justification and actionability. It never checks whether a finding is a real bug, so a well-argued review of nothing scores well.

- Highest: `qwen3.8-27b` × `qwen3.8-27b` *(native)* — 2.0/2, while finding 2 of 43 real bugs.

**Most serious bugs**

Serious bugs are the ones marked `reject`-severity: a reviewer would block a merge over them.

- Tied at **2** bugs across 6 pairings — `mistral-small-4-119b` × {`mistral-small-4-119b`, `glm5.2`, `qwen3.8-27b`}; `gpt-oss-120b` × {`gpt-oss-120b`, `glm5.2`, `qwen3.8-27b`}.

**Across the whole matrix**

- Best reviewer, counting every bug it found with any of its skills: `mistral-small-4-119b` — **14 of 43** (33%). This rewards breadth, so a noisy reviewer can win here.
- Best skill, counting every bug any reviewer found while using it: `qwen3.8-27b` — **11 of 43** (26%).
- Consensus over 4 models: 2 bugs found by all of them (easy to spot), 11 by exactly one (contestable), 25 by none.

**Native skill or a borrowed one**

Delta = the model's own skill minus the average of its three borrowed skills. Negative means borrowing another model's skill scored better.

- Borrowed skills beat the native one for all 4 models. Widest gap: `gpt-oss-120b` — own skill 0.08 vs borrowed 0.20.
- Best skill per model: 0 of 4 models do best with their own skill, 4 with a borrowed one.

**How much to trust this:** 43 bugs is a small sample: one extra bug moves Detection Score by about 0.02, so gaps under ~0.05 are ties.

Baseline-vs-skill (does a skill help or hurt a model at all?) is in [report/comparison.md](report/comparison.md). Both reports use the same codebase.


---

## Overview Matrix

Rows = skill applied to the reviewer; columns = reviewer model. Each cell shows Detection Score (DS). `*(native)*` marks diagonal pairings (model == skill). The highest DS in the matrix is shown in **bold** with a ★.

**Note**: n=43 ground-truth bugs, 1 run per cell; intra-skill Detection Score differences of ~0.03 are not significant.

| Skill \\ Model | glm5.2 | gpt-oss-120b | mistral-small-4-119b | qwen3.8-27b |
|---|---|---|---|---|
| **glm5.2** | DS=0.07 *(native)* | DS=0.20 | DS=0.21 | DS=0.08 |
| **gpt-oss-120b** | DS=0.11 | DS=0.08 *(native)* | DS=0.12 | DS=0.14 |
| **mistral-small-4-119b** | DS=0.08 | DS=0.16 | DS=0.16 *(native)* | DS=0.08 |
| **qwen3.8-27b** | DS=0.08 | **DS=0.24 ★** | DS=0.20 | DS=0.08 *(native)* |
| **No skill (baseline)** | DS=0.08 | DS=0.16 | DS=0.06 | DS=0.14 |


### Judge Score Matrix (J, 0-2 scale)

Rows = skill applied, columns = reviewer model. Judge scores only (J, 0–2 scale). The highest J in the matrix is shown in **bold** with a ★. Note: J does not affect DS.

| Skill \\ Model | glm5.2 | gpt-oss-120b | mistral-small-4-119b | qwen3.8-27b |
|---|---|---|---|---|
| **glm5.2** | J=1.8/2 *(native)* | J=1.4/2 | J=1.1/2 | J=1.5/2 |
| **gpt-oss-120b** | J=1.9/2 | J=1.4/2 *(native)* | J=0.9/2 | J=1.7/2 |
| **mistral-small-4-119b** | J=1.8/2 | J=1.1/2 | J=0.9/2 *(native)* | J=1.7/2 |
| **qwen3.8-27b** | J=1.8/2 | J=1.6/2 | J=1.3/2 | **J=2.0/2 *(native)* ★** |
| **No skill (baseline)** | J=1.8/2 | J=1.4/2 | J=1.1/2 | J=1.3/2 |


*DS = Detection Score (precision-weighted recall). J = Judge Score (0–3 quality rating by GLM5.2). Cells use `reviewer × skill` notation. Bold ★ marks the best Detection Score.*

**Unlocatable findings**: 3 finding(s) in this run cite no line number. They cannot be matched against a ground-truth bug and are counted as false positives.

## Precision Matrix

Rows = skill applied, columns = reviewing model. Fraction of reported findings that matched a real bug — higher is better; low values flag noisy reviewers.

| Skill \\ Model | glm5.2 | gpt-oss-120b | mistral-small-4-119b | qwen3.8-27b |
|---|---|---|---|---|
| glm5.2 | 0.18 | 0.71 | 0.25 | 0.40 |
| gpt-oss-120b | 0.25 | 0.40 | 0.17 | 0.31 |
| mistral-small-4-119b | 0.33 | 0.50 | 0.26 | 0.33 |
| qwen3.8-27b | 0.20 | 0.75 | 0.26 | 0.20 |
| No skill (baseline) | 0.25 | 0.57 | 0.10 | 0.29 |


## Recall Matrix

Rows = skill applied, columns = reviewing model. Matched findings per ground-truth bug (43 ground-truth bugs) — higher is better.

| Skill \\ Model | glm5.2 | gpt-oss-120b | mistral-small-4-119b | qwen3.8-27b |
|---|---|---|---|---|
| glm5.2 | 0.05 | 0.12 | 0.19 | 0.05 |
| gpt-oss-120b | 0.07 | 0.05 | 0.09 | 0.09 |
| mistral-small-4-119b | 0.05 | 0.09 | 0.12 | 0.05 |
| qwen3.8-27b | 0.05 | 0.14 | 0.16 | 0.05 |
| No skill (baseline) | 0.05 | 0.09 | 0.05 | 0.09 |


## Native Pairing Ranking (model == skill)

Diagonal cells only — each model using its own skill.

| Model | Detection Score | Bugs Found | Judge Score |
|-------|-----------------|------------|-------------|
| mistral-small-4-119b | 0.16 | 5/43 | 0.9/2 |
| gpt-oss-120b | 0.08 | 2/43 | 1.4/2 |
| qwen3.8-27b | 0.08 | 2/43 | 2.0/2 |
| glm5.2 | 0.07 | 2/43 | 1.8/2 |

## Best Pairing by Metric

The best pairing(s) for each headline metric (ties shown).

- **Best Detection Score**: gpt-oss-120b × qwen3.8-27b (DS=0.24)

- **Best Judge Score**: qwen3.8-27b × qwen3.8-27b *(native)* (J=2.0/2)


---

## Marginal Analysis

Row means (per reviewing model across skills) and column means (per skill across models).

**Best Model**: mistral-small-4-119b (row-mean DS=0.17, judge=1.0)

**Best Skill**: qwen3.8-27b (column-mean DS=0.15, judge=1.7)


### Model Rankings (by row-mean Detection Score)

| Rank | Model | Detection Score | Judge Mean | Rarity Score |
|------|-------|-----------------|------------|--------------|
| 1 | mistral-small-4-119b | 0.17 | 1.0 | 0.26 |
| 2 | gpt-oss-120b | 0.17 | 1.4 | 0.11 |
| 3 | qwen3.8-27b | 0.10 | 1.7 | 0.03 |
| 4 | glm5.2 | 0.09 | 1.8 | 0.02 |

### Skill Rankings (by column-mean Detection Score)

| Rank | Skill | Detection Score | Judge Mean | Rarity Score |
|------|-------|-----------------|------------|--------------|
| 1 | qwen3.8-27b | 0.15 | 1.7 | 0.18 |
| 2 | glm5.2 | 0.14 | 1.4 | 0.16 |
| 3 | mistral-small-4-119b | 0.12 | 1.4 | 0.14 |
| 4 | gpt-oss-120b | 0.11 | 1.5 | 0.09 |

---

## Bug Discovery Ranking

How many ground-truth bugs each pairing, model, and skill actually found, broken down by severity and category. Raw counts — no precision penalty.

Ground-truth bugs: **43**

### Bugs Found per Pairing (findings classified)

| Model | Skill | TP | Duplicates | Unmatched | Total findings |
|-------|-------|----|------------|-----------|----------------|
| mistral-small-4-119b | glm5.2 | 8 | 5 | 19 | 32 |
| mistral-small-4-119b | qwen3.8-27b | 7 | 3 | 17 | 27 |
| gpt-oss-120b | qwen3.8-27b | 6 | 1 | 1 | 8 |
| mistral-small-4-119b | mistral-small-4-119b *(native)* | 5 | 1 | 13 | 19 |
| gpt-oss-120b | glm5.2 | 5 | 0 | 2 | 7 |
| mistral-small-4-119b | gpt-oss-120b | 4 | 5 | 15 | 24 |
| gpt-oss-120b | mistral-small-4-119b | 4 | 0 | 4 | 8 |
| qwen3.8-27b | gpt-oss-120b | 4 | 2 | 7 | 13 |
| glm5.2 | gpt-oss-120b | 3 | 4 | 5 | 12 |
| glm5.2 | glm5.2 *(native)* | 2 | 2 | 7 | 11 |
| glm5.2 | mistral-small-4-119b | 2 | 1 | 3 | 6 |
| glm5.2 | qwen3.8-27b | 2 | 3 | 5 | 10 |
| gpt-oss-120b | gpt-oss-120b *(native)* | 2 | 0 | 3 | 5 |
| qwen3.8-27b | qwen3.8-27b *(native)* | 2 | 1 | 7 | 10 |
| qwen3.8-27b | glm5.2 | 2 | 1 | 2 | 5 |
| qwen3.8-27b | mistral-small-4-119b | 2 | 2 | 2 | 6 |

### Bugs Found per Model and per Skill

| Group | Name | Total Found | Coverage | Exclusive |
|-------|------|-------------|----------|-----------|
| Model | mistral-small-4-119b | 14 | 33% | 9 |
| Model | gpt-oss-120b | 9 | 21% | 2 |
| Model | qwen3.8-27b | 4 | 9% | 0 |
| Model | glm5.2 | 3 | 7% | 0 |
| Skill | qwen3.8-27b | 11 | 26% | 2 |
| Skill | glm5.2 | 10 | 23% | 3 |
| Skill | mistral-small-4-119b | 9 | 21% | 1 |
| Skill | gpt-oss-120b | 7 | 16% | 0 |

### Bugs Found by Only One Model

| Bug ID | Found Only By |
|--------|---------------|
| SC-001 | gpt-oss-120b |
| SC-006 | mistral-small-4-119b |
| SC-009 | mistral-small-4-119b |
| SC-012 | mistral-small-4-119b |
| SC-016 | mistral-small-4-119b |
| SC-021 | mistral-small-4-119b |
| SC-023 | mistral-small-4-119b |
| SC-024 | mistral-small-4-119b |
| SC-027 | mistral-small-4-119b |
| SC-029 | gpt-oss-120b |
| SC-031 | mistral-small-4-119b |

### Bugs Found by Severity (distinct from ground truth)

| Severity | Ground Truth |
|----------|--------------|
| reject | 6 |
| request-changes | 18 |
| nitpick | 19 |

### Severity Breakdown per Model and per Skill

| Group | Name | reject | request-changes | nitpick | Total |
|-------|------|-------|-------|-------|-------|-------|
| glm5.2 | 4 | 0 | 5 | 9 |
| gpt-oss-120b | 7 | 3 | 7 | 17 |
| mistral-small-4-119b | 7 | 8 | 9 | 24 |
| qwen3.8-27b | 4 | 1 | 5 | 10 |
| Group | Name | reject | request-changes | nitpick | Total |
|-------|------|-------|-------|-------|-------|-------|
| glm5.2 | 6 | 4 | 7 | 17 |
| gpt-oss-120b | 5 | 2 | 6 | 13 |
| mistral-small-4-119b | 5 | 2 | 6 | 13 |
| qwen3.8-27b | 6 | 4 | 7 | 17 |

### Severity Breakdown per Pairing

Critical (`reject`) bug counts for each (model, skill) cell. Higher is better for critical-bug detection.

| Model | Skill | reject | total |
|-------|-------|--------|-------|
| mistral-small-4-119b | glm5.2 | 2 | 8 |
| mistral-small-4-119b | qwen3.8-27b | 2 | 7 |
| gpt-oss-120b | qwen3.8-27b | 2 | 6 |
| mistral-small-4-119b *(native)* | mistral-small-4-119b | 2 | 5 |
| gpt-oss-120b | glm5.2 | 2 | 5 |
| gpt-oss-120b *(native)* | gpt-oss-120b | 2 | 2 |
| mistral-small-4-119b | gpt-oss-120b | 1 | 4 |
| gpt-oss-120b | mistral-small-4-119b | 1 | 4 |
| qwen3.8-27b | gpt-oss-120b | 1 | 4 |
| glm5.2 | gpt-oss-120b | 1 | 3 |
| glm5.2 *(native)* | glm5.2 | 1 | 2 |
| glm5.2 | mistral-small-4-119b | 1 | 2 |
| glm5.2 | qwen3.8-27b | 1 | 2 |
| qwen3.8-27b *(native)* | qwen3.8-27b | 1 | 2 |
| qwen3.8-27b | glm5.2 | 1 | 2 |
| qwen3.8-27b | mistral-small-4-119b | 1 | 2 |

### Bugs Found by Category (distinct from ground truth)

| Category | Ground Truth |
|----------|--------------|
| error-handling | 12 |
| abstraction | 6 |
| correctness | 5 |
| documentation | 4 |
| memory-safety | 4 |
| complexity | 3 |
| process | 3 |
| style | 3 |
| concurrency | 2 |
| testing | 1 |

### Category Breakdown per Model and per Skill

| Group | Name | abstraction | complexity | concurrency | correctness | documentation | error-handling | memory-safety | process | style | testing | Total |
|-------|------|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|
| glm5.2 | 0 | 0 | 0 | 0 | 4 | 0 | 4 | 1 | 0 | 0 | 9 |
| gpt-oss-120b | 2 | 0 | 0 | 4 | 2 | 2 | 4 | 3 | 0 | 0 | 17 |
| mistral-small-4-119b | 4 | 0 | 2 | 2 | 5 | 7 | 4 | 0 | 0 | 0 | 24 |
| qwen3.8-27b | 0 | 0 | 0 | 1 | 4 | 0 | 4 | 1 | 0 | 0 | 10 |
| Group | Name | abstraction | complexity | concurrency | correctness | documentation | error-handling | memory-safety | process | style | testing | Total |
|-------|------|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|
| glm5.2 | 1 | 0 | 1 | 2 | 6 | 2 | 4 | 1 | 0 | 0 | 17 |
| gpt-oss-120b | 1 | 0 | 0 | 2 | 3 | 1 | 4 | 2 | 0 | 0 | 13 |
| mistral-small-4-119b | 2 | 0 | 1 | 0 | 3 | 2 | 4 | 1 | 0 | 0 | 13 |
| qwen3.8-27b | 2 | 0 | 0 | 3 | 3 | 4 | 4 | 1 | 0 | 0 | 17 |

---

## New Bug Candidates

Findings that match NO ground-truth bug — candidates for ground-truth expansion (require human triage).

| File:Line | Severity | Issue | Reported by |
|-----------|----------|-------|-------------|
| smallchat-server.c:188 | CRITICAL | `acceptClient` can return -1 (accept failure from EMFILE, ENOMEM, connection reset). The return valu | 11 cell(s) |
| smallchat-server.c:209 | HIGH | `read(j, readbuf, sizeof(readbuf)-1)` can return `-1` with `errno == EINTR` if a signal interrupts t | 10 cell(s) |
| chatlib.c:94 | HIGH | In `TCPConnect`, when `connect()` returns -1 with `errno == EINPROGRESS` and `nonblock` is true, the | 6 cell(s) |
| smallchat-server.c:255 | CRITICAL | The `snprintf()` call in `main()` can overflow the `msg` buffer when formatting messages. While the | 6 cell(s) |
| smallchat-server.c:240 | HIGH | When setting a new nickname, the code doesn't validate the length of the new nickname. If `arg` is l | 5 cell(s) |
| smallchat-client.c:239 | HIGH | When `read(stdin_fd, buf, sizeof(buf))` returns 0 (EOF — e.g., input redirected from a file, or `Ctr | 4 cell(s) |
| smallchat-server.c:211 | CRITICAL | The code uses `assert(nread <= 0)` implicitly via the condition `if (nread <= 0)` followed by immedi | 4 cell(s) |
| chatlib.c:121 | HIGH | `accept` is not checked for errors. If it fails, the program continues with an invalid socket. | 3 cell(s) |
| chatlib.c:136 | CRITICAL | `chatMalloc` and `chatRealloc` call `exit(1)` on allocation failure. Resource exhaustion is a recove | 3 cell(s) |
| chatlib.c:75 | HIGH | `getaddrinfo` is not checked for errors. If it fails, the program continues with invalid address inf | 3 cell(s) |
| chatlib.c:91 | HIGH | `connect` is not checked for errors. If it fails, the socket is leaked. | 3 cell(s) |
| smallchat-client.c:204 | HIGH | `setRawMode(fileno(stdin), 1)` is called but the return value is not checked. If `setRawMode` fails | 3 cell(s) |
| smallchat-client.c:229 | HIGH | `read(s,buf,sizeof(buf))` is not checked for errors. If the server disconnects, the program may proc | 3 cell(s) |
| smallchat-client.c:244 | HIGH | The client appends a newline character to the input buffer without checking if there's space. If `ib | 3 cell(s) |
| smallchat-client.c:248 | HIGH | `write(s, ib.buf, ib.len)` sends user input to the server socket. If the server has closed the conne | 3 cell(s) |
| smallchat-server.c:180 | HIGH | When `select()` returns -1, the server immediately exits. But `select()` can return -1 with `errno = | 3 cell(s) |
| chatlib.c:147 | HIGH | `realloc` is not checked for errors. If it fails, the program calls `exit(1)` without freeing any re | 2 cell(s) |
| chatlib.c:81 | HIGH | `socket` is not checked for errors in the loop. If it fails, the program continues with an invalid s | 2 cell(s) |
| smallchat-client.c:220 | HIGH | Same as the server: `select()` returning -1 with `EINTR` causes the client to exit. The client has a | 2 cell(s) |
| smallchat-client.c:235 | HIGH | The client writes server messages directly to stdout without checking the return value of `write()`. | 2 cell(s) |
| smallchat-client.c:62 | HIGH | The `tcsetattr()` return value isn't checked in the error path of `setRawMode()`. If terminal restor | 2 cell(s) |
| smallchat-server.c:165 | HIGH | The client list is accessed in the `select()` loop without any synchronization. Multiple threads cou | 2 cell(s) |
| smallchat-server.c:216 | CRITICAL | When `read()` returns <= 0, the client is freed but the socket is not properly closed before calling | 2 cell(s) |
| chatlib.c:120 | HIGH | `accept()` may not complete in one call. The code ignores the return value, which can cause connecti | 1 cell(s) |
| chatlib.c:137 | HIGH | `malloc` is not checked for errors. If it fails, the program calls `exit(1)` without freeing any res | 1 cell(s) |
| chatlib.c:138 | MEDIUM | `if (ptr == NULL) { perror("Out of memory"); exit(1); }` will abort the program if `malloc` fails, w | 1 cell(s) |
| chatlib.c:148 | MEDIUM | `if (ptr == NULL) { perror("Out of memory"); exit(1); }` will abort the program if `realloc` fails, | 1 cell(s) |
| chatlib.c:38 | HIGH | `bind()` and `listen()` may not complete in one call. The code ignores the return values, which can | 1 cell(s) |
| chatlib.c:69 | LOW | `char portstr[6]` assumes a maximum 5-digit port, but `port` is an `int` and is not validated. Out-o | 1 cell(s) |
| chatlib.c:70 | CRITICAL | `snprintf(portstr,sizeof(portstr),"%d",port)` can overflow if `port` is a very large number (e.g., 1 | 1 cell(s) |
| chatlib.c:85 | HIGH | `socketSetNonBlockNoDelay` is not checked for errors. If it fails, the socket may not be in the expe | 1 cell(s) |
| smallchat-client.c:118 | LOW | Magic numbers obscure intent. | 1 cell(s) |
| smallchat-client.c:130 | HIGH | `inputBufferAppend` does not check if `ib->len >= IB_MAX` before appending, yet `inputBufferFeedChar | 1 cell(s) |
| smallchat-client.c:225 | LOW | `char buf[128]` uses a magic size for both server and stdin reads. The intent is unclear and the siz | 1 cell(s) |
| smallchat-client.c:231 | HIGH | When the connection is lost, the client exits without properly closing the socket. | 1 cell(s) |
| smallchat-client.c:259 | LOW | `close(s)` is unreachable because the main loop is `while(1)` and all error paths call `exit(1)`. Th | 1 cell(s) |
| smallchat-client.c:49 | MEDIUM | `setRawMode` uses static variables (`orig_termios`, `atexit_registered`, `rawmode_is_set`) to manage | 1 cell(s) |
| smallchat-server.c:163 | HIGH | `FD_SET(fd, &readfds)` writes into the `fd_set` structure on the stack. On most platforms `fd_set` h | 1 cell(s) |
| smallchat-server.c:166 | HIGH | `FD_SET(j, &readfds)` at line 166 and `select(maxfd+1, ...)` at line 179 use file descriptors as bit | 1 cell(s) |
| smallchat-server.c:179 | LOW | The code uses `select()`, which is limited to `FD_SETSIZE` (typically 1024) file descriptors. `MAX_C | 1 cell(s) |
| smallchat-server.c:194 | HIGH | `write()` can return -1 with `errno == EINTR` due to signals. The code treats this as an error and e | 1 cell(s) |
| smallchat-server.c:234 | CRITICAL | The command processing code modifies the `readbuf` string in-place by inserting null terminators. If | 1 cell(s) |
| smallchat-server.c:241 | HIGH | When changing a nickname, the old nickname memory is freed but if `chatMalloc()` fails for the new n | 1 cell(s) |
| smallchat-server.c:266 | HIGH | If `sendMsgToAllClientsBut()` fails to send to some clients, the message is still processed and the | 1 cell(s) |

### Unmatched Count by Pairing

- mistral-small-4-119b×glm5.2: 19 unmatched
- mistral-small-4-119b×qwen3.8-27b: 17 unmatched
- mistral-small-4-119b×gpt-oss-120b: 15 unmatched
- mistral-small-4-119b×mistral-small-4-119b: 13 unmatched
- glm5.2×glm5.2: 7 unmatched
- qwen3.8-27b×qwen3.8-27b: 7 unmatched
- qwen3.8-27b×gpt-oss-120b: 7 unmatched
- glm5.2×gpt-oss-120b: 5 unmatched
- glm5.2×qwen3.8-27b: 4 unmatched
- gpt-oss-120b×mistral-small-4-119b: 4 unmatched
- glm5.2×mistral-small-4-119b: 3 unmatched
- gpt-oss-120b×gpt-oss-120b: 3 unmatched
- gpt-oss-120b×glm5.2: 2 unmatched
- qwen3.8-27b×glm5.2: 2 unmatched
- qwen3.8-27b×mistral-small-4-119b: 2 unmatched
- gpt-oss-120b×qwen3.8-27b: 1 unmatched

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
| 4/4 models | 2 | 5% |
| 3/4 models | 1 | 2% |
| 2/4 models | 4 | 9% |
| 1/4 models | 11 | 26% |
| 0/4 models (missed) | 25 | 58% |

### Bug Details by Consensus

#### Full Consensus (4/4 models)

| Bug ID | File | Severity | Category | Description | Found By |
|--------|------|----------|----------|-------------|-----------|
| SC-008 | smallchat-server.c | reject | memory-safety | No SIGPIPE handling causes server crash on write to disconnected client | glm5.2, gpt-oss-120b, mistral-small-4-119b, qwen3.8-27b |
| SC-038 | smallchat-server.c | nitpick | documentation | Comment describes behavior that does not match code | glm5.2, gpt-oss-120b, mistral-small-4-119b, qwen3.8-27b |

#### Three Models (3/4)

| Bug ID | File | Severity | Category | Description | Found By |
|--------|------|----------|----------|-------------|-----------|
| SC-033 | Makefile | nitpick | process | No clean rule removes object files, only binaries deleted | glm5.2, gpt-oss-120b, qwen3.8-27b |

#### Two Models (2/4)

| Bug ID | File | Severity | Category | Description | Found By |
|--------|------|----------|----------|-------------|-----------|
| SC-020 | chatlib.c | request-changes | error-handling | Ignored return value of setsockopt() for SO_REUSEADDR in createTCPServer | gpt-oss-120b, mistral-small-4-119b |
| SC-022 | chatlib.c | request-changes | correctness | TCPConnect breaks out of address iteration loop on EINPROGRESS instead of continuing | gpt-oss-120b, qwen3.8-27b |
| SC-025 | smallchat-server.c | request-changes | error-handling | write() return values ignored on non-blocking sockets in sendMsgToAllClientsBut | gpt-oss-120b, mistral-small-4-119b |
| SC-028 | chatlib.c | nitpick | documentation | socketSetNonBlockNoDelay does not preserve other fcntl flags | gpt-oss-120b, mistral-small-4-119b |

#### Sole Discovery (1/4 model)

| Bug ID | File | Severity | Category | Description | Found By |
|--------|------|----------|----------|-------------|-----------|
| SC-001 | smallchat-server.c | reject | correctness | assert(Chat->clients[c->fd] == NULL) aborts on recoverable condition when fd slot already occupied | gpt-oss-120b |
| SC-006 | smallchat-server.c | request-changes | error-handling | Missing error handling for write() of welcome message | mistral-small-4-119b |
| SC-009 | smallchat-server.c | reject | correctness | select() exits on EINTR - any signal kills the server instead of retrying | mistral-small-4-119b |
| SC-012 | smallchat-server.c | request-changes | correctness | No nick length validation allows memory exhaustion DoS via /nick command | mistral-small-4-119b |
| SC-016 | smallchat-client.c | request-changes | error-handling | No handling of inputBufferAppend() failure falls through and treats character as accepted | mistral-small-4-119b |
| SC-021 | chatlib.c | nitpick | abstraction | TCPConnect non-blocking EINPROGRESS path leaks addrinfo on failure | mistral-small-4-119b |
| SC-023 | chatlib.c | nitpick | abstraction | chatRealloc leaks original pointer on failure | mistral-small-4-119b |
| SC-024 | smallchat-server.c | reject | concurrency | freeClient invalidates loop bound mid-iteration in broadcast loop | mistral-small-4-119b |
| SC-027 | smallchat-client.c | nitpick | error-handling | No SIGPIPE handling in client can cause unexpected termination | mistral-small-4-119b |
| SC-029 | chatlib.h | nitpick | abstraction | No const correctness on string parameters in header declarations | gpt-oss-120b |
| SC-031 | smallchat-server.c | request-changes | abstraction | Magic constant 127 for backspace handling duplicated without named constant | mistral-small-4-119b |

#### Missed by All Models (0/4)

| Bug ID | File | Severity | Category | Description |
|--------|------|----------|----------|-------------|
| SC-002 | smallchat-server.c | reject | memory-safety | Fixed-size client table clients[MAX_CLIENTS] can overflow when fd >= 1000 |
| SC-003 | smallchat-server.c | request-changes | error-handling | Ignored return value of write() in broadcast loop can silently drop messages |
| SC-004 | smallchat-server.c | request-changes | error-handling | Ignored result of socketSetNonBlockNoDelay() breaks event-driven design on failure |
| SC-005 | smallchat-server.c | request-changes | memory-safety | memcpy(c->nick,nick,nicklen) without null termination causes undefined behavior |
| SC-007 | smallchat-server.c | nitpick | complexity | MAX_CLIENTS constant conflates maximum clients with maximum fd without documentation |
| SC-010 | smallchat-server.c | reject | memory-safety | acceptClient return value not checked - createClient(-1) corrupts memory on EMFILE |
| SC-011 | smallchat-server.c | request-changes | complexity | select() 1-second timeout is speculative generality with no current purpose |
| SC-013 | smallchat-server.c | nitpick | error-handling | /nick with no argument gives misleading 'Unsupported command' error instead of usage message |
| SC-014 | smallchat-client.c | request-changes | error-handling | Ignored return value of write() when sending user input silently drops data |
| SC-015 | smallchat-client.c | request-changes | error-handling | Ignored return value of write() for server welcome messages |
| SC-017 | smallchat-client.c | nitpick | style | Backspace handling limited to DEL (127) does not handle other backspace codes |
| SC-018 | smallchat-client.c | nitpick | documentation | No handling of arrow keys/escape sequences not documented |
| SC-019 | chatlib.c | request-changes | error-handling | Ignored return value of setsockopt() in socketSetNonBlockNoDelay |
| SC-026 | smallchat-client.c | request-changes | concurrency | Client select() exits on EINTR without retry logic |
| SC-030 | chatlib.h | nitpick | documentation | No extern C guard for C++ consumers |
| SC-032 | smallchat-client.c | nitpick | testing | atoi(argv[2]) with no validation for port number |
| SC-034 | Makefile | nitpick | process | Missing .PHONY declarations for non-file targets |
| SC-035 | Makefile | nitpick | process | No install target or dependency tracking |
| SC-036 | chatlib.h | nitpick | abstraction | Header lacks include guards for C++ compatibility |
| SC-037 | smallchat-client.c | nitpick | style | Variable naming inconsistent with project conventions |
| SC-039 | inputbuffer.c | request-changes | error-handling | inputBufferFeedChar silent failure on buffer full condition |
| SC-040 | inputbuffer.c | nitpick | complexity | Nested if statements in inputBufferAppend could be flattened |
| SC-041 | terminal.c | request-changes | correctness | setRawMode does not restore terminal on error path |
| SC-042 | terminal.c | nitpick | style | Terminal escape codes use magic numbers without named constants |
| SC-043 | chat-common.c | request-changes | abstraction | Shared utility functions duplicated across modules instead of centralized |

**25 bug(s) missed by every model** — these may require skill refinement or represent subtle defects beyond current detection capability.

**2 bug(s) reached full consensus** — found by all four models. These represent the easiest-to-detect defects.

**11 bug(s) found by only one model** — these highlight model-specific strengths and potential complementarity.


---

## Native Pairing Advantage

For each model, compare its native skill (model == skill) against the mean of cross-skills (model != skill). Positive delta = native skill helps; negative = cross-skill helps. This measures native-skill advantage, not skill-on vs skill-off — for that comparison see [report/comparison.md](report/comparison.md).

| Model | Native DS | Cross-Skill Mean DS | Delta | Verdict |
|-------|----------|---------------------|-------|---------|
| glm5.2 | 0.07 | 0.09 | -0.01 | cross helps |
| gpt-oss-120b | 0.08 | 0.20 | -0.11 | cross helps |
| mistral-small-4-119b | 0.16 | 0.18 | -0.02 | cross helps |
| qwen3.8-27b | 0.08 | 0.10 | -0.03 | cross helps |

## Best Skill per Model

For each model, the skill that produces the highest Detection Score. Since true-positive counts are model-driven while the skill mainly affects the false-positive rate, the recommended skill is the one that maximizes DS (i.e., minimizes false positives).

| Model | Best Skill(s) | DS | Recommendation |
|-------|--------------|----|----------------|
| glm5.2 | gpt-oss-120b | 0.11 | cross-skill `gpt-oss-120b` |
| gpt-oss-120b | qwen3.8-27b | 0.24 | cross-skill `qwen3.8-27b` |
| mistral-small-4-119b | glm5.2 | 0.21 | cross-skill `glm5.2` |
| qwen3.8-27b | gpt-oss-120b | 0.14 | cross-skill `gpt-oss-120b` |


---

## Judge Score Detail

**Secondary metric.** The judge does **not** affect the Detection Score (DS), true positives, recall, or precision — all detection metrics are computed by matching findings to ground truth. The judge only provides four quality sub-scores (accuracy, prioritization, justification, actionability) on a 0–2 scale, aggregated into the Judge Score (J) shown in the matrices above. Use J to break ties, never to rank. Disable with `--no-judge`.

> **Conflict of interest**: the judge (GLM5.2) also participates in the evaluation as a reviewer, so its self-scored reviews may reflect self-preference.


Each sub-score is the mean over evaluated reviews on a 0–2 scale; values vary little across pairings, so they are shown as appendix detail.

### Judge Accuracy Matrix

| Skill \\ Model | glm5.2 | gpt-oss-120b | mistral-small-4-119b | qwen3.8-27b |
|---|---|---|---|---|
| glm5.2 | 1.7 | 1.0 | 0.9 | 1.4 |
| gpt-oss-120b | 1.9 | 1.0 | 0.9 | 1.5 |
| mistral-small-4-119b | 1.7 | 0.9 | 0.6 | 1.7 |
| qwen3.8-27b | 1.8 | 1.6 | 1.3 | 2.0 |
| No skill (baseline) | 1.9 | 1.3 | 0.9 | 1.3 |


### Judge Prioritization Matrix

| Skill \\ Model | glm5.2 | gpt-oss-120b | mistral-small-4-119b | qwen3.8-27b |
|---|---|---|---|---|
| glm5.2 | 1.5 | 1.6 | 1.1 | 1.6 |
| gpt-oss-120b | 1.8 | 1.4 | 0.9 | 1.7 |
| mistral-small-4-119b | 1.7 | 1.2 | 0.8 | 1.7 |
| qwen3.8-27b | 1.7 | 1.6 | 1.2 | 1.9 |
| No skill (baseline) | 1.9 | 1.3 | 0.9 | 1.4 |


### Judge Justification Matrix

| Skill \\ Model | glm5.2 | gpt-oss-120b | mistral-small-4-119b | qwen3.8-27b |
|---|---|---|---|---|
| glm5.2 | 2.0 | 1.3 | 1.1 | 1.6 |
| gpt-oss-120b | 2.0 | 1.4 | 0.9 | 1.7 |
| mistral-small-4-119b | 2.0 | 0.9 | 0.9 | 1.7 |
| qwen3.8-27b | 1.8 | 1.6 | 1.2 | 2.0 |
| No skill (baseline) | 1.9 | 1.6 | 1.1 | 1.1 |


### Judge Actionability Matrix

| Skill \\ Model | glm5.2 | gpt-oss-120b | mistral-small-4-119b | qwen3.8-27b |
|---|---|---|---|---|
| glm5.2 | 1.9 | 1.7 | 1.2 | 1.6 |
| gpt-oss-120b | 2.0 | 1.8 | 1.0 | 2.0 |
| mistral-small-4-119b | 2.0 | 1.5 | 1.1 | 1.7 |
| qwen3.8-27b | 1.8 | 1.5 | 1.6 | 2.0 |
| No skill (baseline) | 1.8 | 1.4 | 1.2 | 1.4 |


## Limitations

- **n=43 ground-truth bugs**: Evaluation based on the real SmallChat codebase with 43 known bugs.

- **Repetitions**: each model+skill pairing was evaluated 1x per bug.

- **Judge COI**: The judge (GLM5.2) also participates as a reviewer, so judge scores may reflect self-preference.

- **Prompt provenance**: reviewers never saw the ground-truth bug list, so these numbers measure detection against the ground-truth bug list.

- **Denominator choice**: Recall denominator uses only ground-truth bugs; any finding that matches no ground-truth bug counts as a false positive.


