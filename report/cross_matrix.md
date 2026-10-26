# Cross-Model Evaluation Matrix

Codebase data from `data/eval_results_codebase.jsonl` (full SmallChat review, 43 ground-truth bugs).

*Judge model: GLM5.2 (fixed external judge, scored via `--judge-model` at generation time).

> **Evaluation provenance:** the reviewer prompt carried only the code under review, never the ground-truth bug list (enforced by regression tests in `tests/test_eval.py`). Every number below therefore measures detection, not transcription. Judge: GLM5.2, a fixed external model scored at generation time via `--judge-model`.

Dataset: 43 ground-truth bugs from `benchmark.jsonl`.

> **Note:** The judge (GLM5.2) also participates in the evaluation as a reviewer: judge scores may reflect self-preference.

## Question & Answer

**Question this report answers:** Which model+skill combination detects bugs best? (Cross-model evaluation on the real SmallChat codebase, 43 ground-truth bugs.)

**Headline answer:** The reviewing model — not the attached skill — drives how many bugs are found. Swapping skills rarely changes a model's true-positive count; the skill mainly affects precision (false positives), which is what moves the Detection Score. See the Overview Matrix below for specifics.

**Overview matrix:** The table below shows Detection Score (DS) and Judge score (J) for each model+skill pairing. Native pairings (model == skill) are marked.

> **Anti-contradiction note:** This report answers a different question than `report/comparison.md`. This report asks 'Which model+skill combination detects bugs best?' on the real SmallChat codebase. The comparison.md asks 'Does adding the skill help or hurt each model?' on the same codebase. Both reports now use the same codebase; apparent disagreement reflects different metrics, not different data.



## Evidence

## Verdict

**Best pairing**: `gpt-oss-120b` reviewing with `mistral-small-4-119b` skill found **5 bugs** across 43 ground-truth bugs.

**Best Detection Score**: `gpt-oss-120b` on `mistral-small-4-119b` (DS=0.20).

**Best Judge Score**: `gpt-oss-120b` on `qwen3.8-27b` (J=2.0/2).

**Best reviewer model**: `gpt-oss-120b` found **5** bugs (12% coverage) across all skills.

**Best skill**: `mistral-small-4-119b` found **5** bugs (12% coverage) across all models.

**Consensus**: 0 bug(s) found by every model (across all skill pairings), 5 by only one model, 37 missed by all. This measures inter-model agreement, not skill-on vs skill-off.

**Native pairing advantage**: glm5.2: no difference; gpt-oss-120b: cross helps; mistral-small-4-119b: no difference; qwen3.8-27b: cross helps.

**Best skill per model**: 2 model(s) perform best with their native skill, 2 with a cross-skill. See the *Best Skill per Model* table below for specifics.

See `report/comparison.md` for the baseline-vs-skill analysis (whether adding any skill helps or hurts each model). Note: both reports use the same codebase.

In plain terms: the reviewing model — not the attached skill — drives how many bugs are found. Swapping skills rarely changes a model's true-positive count; the skill mainly affects precision (false positives), which is what moves the Detection Score. Start from the Overview Matrix, then use the ranking tables for specifics.

**Baseline comparison**: gpt-oss-120b: no baseline data; mistral-small-4-119b: skill hurts DS (0.00 vs 0.05); qwen3.8-27b: skill improves DS (0.08 vs 0.04).



## Metrics Glossary

Definitions of every metric used in this report. Read this before the matrices.

- **Detection Score (DS)**: Harmonic mean of precision and recall. Measures how well findings balance correctness (precision) against completeness (recall). Range 0–1; higher is better.

- **Precision**: Of all findings reported, the fraction that matched a ground-truth bug. Low precision means many false positives.

- **Recall**: Matched findings divided by the number of buggy ground-truth bugs (43 ground-truth bugs). Low recall means missed bugs.

- **Refusal Rate (R)**: Fraction of reviews where the model refused to review. In this dataset R=0 for all pairings, so it is omitted from the tables.

- **Judge Score (J)**: Mean of four sub-scores (accuracy, prioritization, justification, actionability) on a 0–2 scale. Reflects review quality as scored by the judge model. **Note**: The judge (GLM5.2) also participates in the evaluation as a reviewer: judge scores may reflect self-preference.

- **Native**: Diagonal pairing where the model reviews the codebase using its own skill (model == skill).

- **Exclusive**: Bugs found by this model/skill and no other model/skill. A high exclusive count means the pairing contributes unique value.

- **Match (TP)**: A finding that matches a ground-truth bug within the ±5 line tolerance.

- **Duplicate**: A finding that matches a ground-truth bug already matched by an earlier finding in the same cell.

- **Non-TP findings**: Total distinct findings minus true positives (= Duplicates + Unmatched).
- **Duplicates**: A second finding matching a ground-truth bug already claimed by an earlier finding in the same cell. Harmless for Detection Score (deduplicated) but it signals verbosity, not extra detection.

- **No skill (baseline)**: Model ran without any skill attached (skill=="none"). Used as a reference to measure whether adding a skill helps or hurts. Baseline participates only in model-level comparisons; excluded from skill rankings.


---

## Overview Matrix

Each cell shows: Detection Score (DS), and mean Judge score (0–2 scale).

*(native)* indicates diagonal pairing (model == skill).

**Note**: n=43 ground-truth bugs, 1 run per cell; intra-skill Detection Score differences of ~0.03 are not significant.

| Skill \\ Model | glm5.2 | gpt-oss-120b | mistral-small-4-119b | qwen3.8-27b |
|---|---|---|---|---|
| **glm5.2** | DS=0.00 J=1.2/2 *(native)* | DS=0.05 J=1.0/2 | DS=0.00 J=0.5/2 | DS=0.08 J=1.6/2 |
| **gpt-oss-120b** | DS=0.00 J=1.6/2 | DS=0.00 J=1.2/2 *(native)* | DS=0.00 J=0.0/2 | DS=0.00 J=0.0/2 |
| **mistral-small-4-119b** | DS=0.00 J=2.0/2 | DS=0.20 J=1.0/2 | DS=0.00 J=1.8/2 *(native)* | DS=0.00 J=1.8/2 |
| **qwen3.8-27b** | DS=0.00 J=1.3/2 | DS=0.00 J=2.0/2 | DS=0.00 J=0.5/2 | DS=0.00 J=1.8/2 *(native)* |
| **No skill (baseline)** | DS=0.00 J=2.0/2 | DS=0.00 J=1.8/2 | DS=0.05 J=2.0/2 | DS=0.04 J=1.8/2 |


## Precision Matrix

Rows = skill applied, columns = reviewing model. Fraction of reported findings that matched a real bug — higher is better; low values flag noisy reviewers.

| Skill \\ Model | glm5.2 | gpt-oss-120b | mistral-small-4-119b | qwen3.8-27b |
|---|---|---|---|---|
| glm5.2 | 0.00 | 1.00 | 0.00 | 0.25 |
| gpt-oss-120b | 0.00 | 0.00 | 0.00 | 0.00 |
| mistral-small-4-119b | 0.00 | 0.62 | 0.00 | 0.00 |
| qwen3.8-27b | 0.00 | 0.00 | 0.00 | 0.00 |
| No skill (baseline) | 0.00 | 0.00 | 1.00 | 0.11 |


## Recall Matrix

Rows = skill applied, columns = reviewing model. Matched findings per ground-truth bug (43 ground-truth bugs) — higher is better.

| Skill \\ Model | glm5.2 | gpt-oss-120b | mistral-small-4-119b | qwen3.8-27b |
|---|---|---|---|---|
| glm5.2 | 0.00 | 0.02 | 0.00 | 0.05 |
| gpt-oss-120b | 0.00 | 0.00 | 0.00 | 0.00 |
| mistral-small-4-119b | 0.00 | 0.12 | 0.00 | 0.00 |
| qwen3.8-27b | 0.00 | 0.00 | 0.00 | 0.00 |
| No skill (baseline) | 0.00 | 0.00 | 0.02 | 0.02 |


## Native Pairing Ranking (model == skill)

Diagonal cells only — each model using its own skill.

| Model | Detection Score | Bugs Found | Judge Score |
|-------|-----------------|------------|-------------|
| glm5.2 | 0.00 | 0/43 | 1.2/2 |
| gpt-oss-120b | 0.00 | 0/43 | 1.2/2 |
| mistral-small-4-119b | 0.00 | 0/43 | 1.8/2 |
| qwen3.8-27b | 0.00 | 0/43 | 1.8/2 |

## Best Pairing by Metric

The best pairing(s) for each headline metric (ties shown).

- **Best Detection Score**: gpt-oss-120b on mistral-small-4-119b (DS=0.20)

- **Best Judge Score** (tie): gpt-oss-120b on qwen3.8-27b, glm5.2 on mistral-small-4-119b (J=2.0/2)


---

## Marginal Analysis

Row means (per reviewing model across skills) and column means (per skill across models).

**Best Model**: gpt-oss-120b (row-mean DS=0.06, judge=1.3)

**Best Skill**: mistral-small-4-119b (column-mean DS=0.05, judge=1.6)


### Model Rankings (by row-mean Detection Score)

| Rank | Model | Detection Score | Judge Mean | Rarity Score |
|------|-------|-----------------|------------|--------------|
| 1 | gpt-oss-120b | 0.06 | 1.3 | 0.10 |
| 2 | qwen3.8-27b | 0.02 | 1.3 | 0.03 |
| 3 | glm5.2 | 0.00 | 1.5 | 0.00 |
| 4 | mistral-small-4-119b | 0.00 | 0.7 | 0.00 |

### Skill Rankings (by column-mean Detection Score)

| Rank | Skill | Detection Score | Judge Mean | Rarity Score |
|------|-------|-----------------|------------|--------------|
| 1 | mistral-small-4-119b | 0.05 | 1.6 | 0.10 |
| 2 | glm5.2 | 0.03 | 1.1 | 0.06 |
| 3 | qwen3.8-27b | 0.00 | 1.4 | 0.00 |
| 4 | gpt-oss-120b | 0.00 | 0.7 | 0.00 |

---

## Bug Discovery Ranking

How many ground-truth bugs each pairing, model, and skill actually found, broken down by severity and category. Raw counts — no precision penalty.

Ground-truth bugs: **43**

### Bugs Found per Pairing (findings classified)

| Model | Skill | TP | Duplicates | Unmatched | Total findings |
|-------|-------|----|------------|-----------|----------------|
| gpt-oss-120b | mistral-small-4-119b | 5 | 1 | 2 | 8 |
| qwen3.8-27b | glm5.2 | 2 | 0 | 6 | 8 |
| gpt-oss-120b | glm5.2 | 1 | 0 | 0 | 1 |
| gpt-oss-120b | gpt-oss-120b *(native)* | 0 | 0 | 1 | 1 |
| glm5.2 | glm5.2 *(native)* | 0 | 0 | 8 | 8 |
| mistral-small-4-119b | mistral-small-4-119b *(native)* | 0 | 0 | 1 | 1 |
| qwen3.8-27b | qwen3.8-27b *(native)* | 0 | 0 | 1 | 1 |
| gpt-oss-120b | qwen3.8-27b | 0 | 0 | 1 | 1 |
| glm5.2 | gpt-oss-120b | 0 | 0 | 12 | 12 |
| glm5.2 | mistral-small-4-119b | 0 | 0 | 1 | 1 |
| mistral-small-4-119b | gpt-oss-120b | 0 | 0 | 1 | 1 |
| mistral-small-4-119b | glm5.2 | 0 | 0 | 1 | 1 |
| mistral-small-4-119b | qwen3.8-27b | 0 | 0 | 1 | 1 |
| qwen3.8-27b | gpt-oss-120b | 0 | 0 | 1 | 1 |
| qwen3.8-27b | mistral-small-4-119b | 0 | 0 | 1 | 1 |
| glm5.2 | qwen3.8-27b | 0 | 0 | 14 | 14 |

### Bugs Found per Model (union across all skills)

| Model | Total Found | Coverage | Exclusive |
|-------|-------------|----------|-----------|
| gpt-oss-120b | 5 | 12% | 4 |
| qwen3.8-27b | 2 | 5% | 1 |
| glm5.2 | 0 | 0% | 0 |
| mistral-small-4-119b | 0 | 0% | 0 |

### Bugs Found per Skill (union across all models)

| Skill | Total Found | Coverage | Exclusive |
|-------|-------------|----------|-----------|
| mistral-small-4-119b | 5 | 12% | 3 |
| glm5.2 | 3 | 7% | 1 |
| gpt-oss-120b | 0 | 0% | 0 |
| qwen3.8-27b | 0 | 0% | 0 |

### Bugs Found by Only One Model

| Bug ID | Found Only By |
|--------|---------------|
| SC-003 | gpt-oss-120b |
| SC-006 | gpt-oss-120b |
| SC-020 | gpt-oss-120b |
| SC-029 | qwen3.8-27b |
| SC-038 | gpt-oss-120b |

### Bugs Found by Severity (union across all pairings)

| Severity | Total Bugs Found |
|----------|------------------|
| request-changes | 4 |
| nitpick | 4 |

### Severity Breakdown per Model

| Model |reject|request-changes|nitpick| Total |
|-------|------|------|------|-------|
| glm5.2 | 0 | 0 | 0 | 0 |
| gpt-oss-120b | 0 | 4 | 2 | 6 |
| mistral-small-4-119b | 0 | 0 | 0 | 0 |
| qwen3.8-27b | 0 | 0 | 2 | 2 |

### Severity Breakdown per Skill

| Skill |reject|request-changes|nitpick| Total |
|-------|------|------|------|-------|
| glm5.2 | 0 | 1 | 2 | 3 |
| gpt-oss-120b | 0 | 0 | 0 | 0 |
| mistral-small-4-119b | 0 | 3 | 2 | 5 |
| qwen3.8-27b | 0 | 0 | 0 | 0 |

### Severity Breakdown per Pairing

Critical (`reject`) bug counts for each (model, skill) cell. Higher is better for critical-bug detection.

| Model | Skill | reject | total |
|-------|-------|--------|-------|
| gpt-oss-120b | mistral-small-4-119b | 0 | 5 |
| qwen3.8-27b | glm5.2 | 0 | 2 |
| gpt-oss-120b | glm5.2 | 0 | 1 |
| gpt-oss-120b *(native)* | gpt-oss-120b | 0 | 0 |
| glm5.2 *(native)* | glm5.2 | 0 | 0 |
| mistral-small-4-119b *(native)* | mistral-small-4-119b | 0 | 0 |
| qwen3.8-27b *(native)* | qwen3.8-27b | 0 | 0 |
| gpt-oss-120b | qwen3.8-27b | 0 | 0 |
| glm5.2 | gpt-oss-120b | 0 | 0 |
| glm5.2 | mistral-small-4-119b | 0 | 0 |
| mistral-small-4-119b | gpt-oss-120b | 0 | 0 |
| mistral-small-4-119b | glm5.2 | 0 | 0 |
| mistral-small-4-119b | qwen3.8-27b | 0 | 0 |
| qwen3.8-27b | gpt-oss-120b | 0 | 0 |
| qwen3.8-27b | mistral-small-4-119b | 0 | 0 |
| glm5.2 | qwen3.8-27b | 0 | 0 |

### Bugs Found by Category (union across all pairings)

| Category | Total Bugs Found |
|----------|------------------|
| error-handling | 4 |
| process | 2 |
| abstraction | 1 |
| documentation | 1 |

### Category Breakdown per Model

| Model |abstraction|documentation|error-handling|process| Total |
|-------|------|------|------|------|-------|
| glm5.2 | 0 | 0 | 0 | 0 | 0 |
| gpt-oss-120b | 0 | 1 | 4 | 1 | 6 |
| mistral-small-4-119b | 0 | 0 | 0 | 0 | 0 |
| qwen3.8-27b | 1 | 0 | 0 | 1 | 2 |

### Category Breakdown per Skill

| Skill |abstraction|documentation|error-handling|process| Total |
|-------|------|------|------|------|-------|
| glm5.2 | 1 | 0 | 1 | 1 | 3 |
| gpt-oss-120b | 0 | 0 | 0 | 0 | 0 |
| mistral-small-4-119b | 0 | 1 | 3 | 1 | 5 |
| qwen3.8-27b | 0 | 0 | 0 | 0 | 0 |

---

## New Bug Candidates

Findings that match NO ground-truth bug — candidates for ground-truth expansion (require human triage).

| Diff ID | Model | Skill | File:Line | Severity | Issue |
|---------|-------|-------|-----------|----------|-------|
| SMALLCHAT | gpt-oss-120b | gpt-oss-120b | smallchat-server.c | MEDIUM | The file descriptor (`fd`) is used directly as an index into the fixed‑size `clients` array. On most |
| SMALLCHAT | glm5.2 | glm5.2 | smallchat-server.c | MEDIUM | `acceptClient()` can return `-1` on error. The caller in `main()` passes this directly to `createCli |
| SMALLCHAT | glm5.2 | glm5.2 | smallchat-server.c | MEDIUM | `snprintf` returns the number of characters written, excluding the NUL. The code allocates `nicklen+ |
| SMALLCHAT | glm5.2 | glm5.2 | smallchat-server.c | MEDIUM | ```c |
| SMALLCHAT | glm5.2 | glm5.2 | chatlib.c | MEDIUM | Both allocators call `exit(1)` on `malloc`/`realloc` failure: |
| SMALLCHAT | glm5.2 | glm5.2 | chatlib.c | MEDIUM | When `connect()` fails (non-EINPROGRESS), the code `break`s out of the `addrinfo` loop instead of `c |
| SMALLCHAT | glm5.2 | glm5.2 | smallchat-client.c | MEDIUM | The client calls `write()` in several places without checking the return value: |
| SMALLCHAT | glm5.2 | glm5.2 | chatlib.h | MEDIUM | `TCPConnect(char *addr, int port, int nonblock)` takes `addr` as `char *` but never modifies it. Thi |
| SMALLCHAT | mistral-small-4-119b | mistral-small-4-119b | smallchat-server.c:264 | MEDIUM | When `snprintf()` returns a value larger than the buffer size, the code truncates the message but co |
| SMALLCHAT | qwen3.8-27b | qwen3.8-27b | smallchat-server.c | MEDIUM | `acceptClient()` returns `-1` on failure, but `main()` passes the result directly to `createClient(f |
| SMALLCHAT | gpt-oss-120b | none | smallchat-server.c | MEDIUM | `Chat->clients[c->fd] = c;` indexes the `clients` array with the socket descriptor `fd`. The array s |
| SMALLCHAT | gpt-oss-120b | none | smallchat-server.c | MEDIUM | `nicklen` is the length returned by `snprintf` (without the trailing NUL). Memory is allocated with  |
| SMALLCHAT | gpt-oss-120b | none | smallchat-server.c | MEDIUM | After `int fd = acceptClient(Chat->serversock);` the return value is used unconditionally: `struct c |
| SMALLCHAT | gpt-oss-120b | none | smallchat-server.c | MEDIUM | `write()` is called on sockets without checking the return value or disabling `SIGPIPE`. If a client |
| SMALLCHAT | gpt-oss-120b | none | smallchat-client.c | MEDIUM | The code uses `if (FD_ISSET(s, &readfds)) { … } else if (FD_ISSET(stdin_fd, &readfds)) { … }`. If bo |
| SMALLCHAT | gpt-oss-120b | none | smallchat-client.c | MEDIUM | The client calls `write()` without checking its return value. A short write or an error (e.g., `EPIP |
| SMALLCHAT | gpt-oss-120b | none | chatlib.c | MEDIUM | The call to `setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &yes, sizeof(yes));` discards its return value |
| SMALLCHAT | gpt-oss-120b | none | chatlib.c | MEDIUM | The backlog argument to `listen()` is hard‑coded as `511`. This magic number is undocumented and may |
| SMALLCHAT | mistral-small-4-119b | none | chatlib.c:10 | MEDIUM | - `socketSetNonBlockNoDelay()` does not check the return value of `setsockopt()` for errors. TCP_NOD |
| SMALLCHAT | qwen3.8-27b | none | smallchat-server.c | MEDIUM | `acceptClient()` can return `-1`, and even on success the new fd is not checked against `MAX_CLIENTS |
| SMALLCHAT | qwen3.8-27b | none | smallchat-server.c | MEDIUM | `int nread = read(...); if (nread <= 0) freeClient(...);` frees the client on any error, including ` |
| SMALLCHAT | qwen3.8-27b | none | smallchat-server.c | MEDIUM | `sendMsgToAllClientsBut()`, the welcome message, and the unsupported-command reply call `write()` on |
| SMALLCHAT | qwen3.8-27b | none | smallchat-client.c:73 | MEDIUM | `setRawMode()` calls `tcgetattr(fd,&orig_termios)` every time `enable` is nonzero. If raw mode is al |
| SMALLCHAT | qwen3.8-27b | none | smallchat-client.c:204 | MEDIUM | `setRawMode(fileno(stdin),1)` return value is ignored. If stdin is not a tty or `tcsetattr()` fails, |
| SMALLCHAT | qwen3.8-27b | none | chatlib.c:148 | MEDIUM | `ptr = realloc(ptr,size);` overwrites the original pointer before checking failure. If `realloc()` f |
| SMALLCHAT | qwen3.8-27b | none | chatlib.c | MEDIUM | `char portstr[6]` is only enough for `0..65535`. `snprintf()` will silently truncate other `int` val |
| SMALLCHAT | qwen3.8-27b | none | Makefile | MEDIUM | The compile commands put `$(CFLAGS)` after the sources and `-o`. This is accepted by GCC but is nons |
| SMALLCHAT | qwen3.8-27b | none | Makefile | MEDIUM | `all` and `clean` are not declared `.PHONY`. If files named `all` or `clean` exist, make may skip th |
| SMALLCHAT | gpt-oss-120b | glm5.2 | smallchat-server.c:68 | MEDIUM | `snprintf` may write more than 31 characters into `nick[32]` when the file descriptor is large, caus |
| SMALLCHAT | gpt-oss-120b | mistral-small-4-119b | smallchat-server.c:71 | MEDIUM | The global `clients` array is sized for the highest possible file descriptor, but the code never che |
| SMALLCHAT | gpt-oss-120b | mistral-small-4-119b | smallchat-server.c:74 | MEDIUM | Subsequent uses of `c->nick` (e.g., in `snprintf("%s> %s", c->nick, ...)`) read past the allocated b |
| SMALLCHAT | gpt-oss-120b | mistral-small-4-119b | smallchat-server.c:144 | MEDIUM | `printf` expects a NUL‑terminated string; without it the function will read past the buffer, causing |
| SMALLCHAT | gpt-oss-120b | mistral-small-4-119b | smallchat-server.c:115 | MEDIUM | On accept failure (e.g., EMFILE, ENOMEM) `fd` is ‑1, which then flows into `createClient` and trigge |
| SMALLCHAT | gpt-oss-120b | mistral-small-4-119b | smallchat-client.c:30 | MEDIUM | If `tcsetattr` fails (e.g., not a TTY), the terminal remains in its original mode, and later `disabl |
| SMALLCHAT | gpt-oss-120b | mistral-small-4-119b | smallchat-client.c:78 | MEDIUM | Users typing long lines will see characters disappear without any indication, leading to confusing b |
| SMALLCHAT | gpt-oss-120b | mistral-small-4-119b | chatlib.c:27 | MEDIUM | If `setsockopt` fails, the socket will not have `TCP_NODELAY` set, potentially degrading performance |
| SMALLCHAT | gpt-oss-120b | mistral-small-4-119b | Makefile:2 | MEDIUM | Redundant flags clutter the build command and can cause confusing warning output. |
| SMALLCHAT | gpt-oss-120b | qwen3.8-27b | `smallchat-server.c | MEDIUM | File descriptors can be arbitrarily large (e.g., after opening many files or after `dup()`), so inde |
| SMALLCHAT | glm5.2 | gpt-oss-120b | smallchat-server.c | MEDIUM | `Chat->clients[c->fd] = c` uses the raw file descriptor as an index into a 1000-element array (`MAX_ |
| SMALLCHAT | glm5.2 | gpt-oss-120b | smallchat-server.c | MEDIUM | `int fd = acceptClient(Chat->serversock)` is called, and the return value is passed directly to `cre |
| SMALLCHAT | glm5.2 | gpt-oss-120b | smallchat-server.c | MEDIUM | The server calls `write()` on client sockets without ignoring SIGPIPE. If a client crashes (sends RS |
| SMALLCHAT | glm5.2 | gpt-oss-120b | smallchat-server.c | MEDIUM | `assert(Chat->clients[c->fd] == NULL)` guards a real runtime condition. With `-DNDEBUG` (common in r |
| SMALLCHAT | glm5.2 | gpt-oss-120b | smallchat-server.c | MEDIUM | When `nonblock` is set and `connect()` returns -1 with `errno == EINPROGRESS`, the function does `re |
| SMALLCHAT | glm5.2 | gpt-oss-120b | smallchat-server.c | MEDIUM | When `connect()` fails with an error other than EINPROGRESS, the code does `close(s); break;`. The ` |
| SMALLCHAT | glm5.2 | gpt-oss-120b | smallchat-server.c | MEDIUM | `int nread = read(j, readbuf, sizeof(readbuf)-1);` — if `read()` is interrupted by a signal (EINTR), |
| SMALLCHAT | glm5.2 | gpt-oss-120b | smallchat-server.c | MEDIUM | `retval = select(...)` — if `select()` is interrupted by a signal (EINTR), it returns -1. The code c |
| SMALLCHAT | glm5.2 | gpt-oss-120b | smallchat-server.c | MEDIUM | `socketSetNonBlockNoDelay(fd);` is called with the comment "Pretend this will not fail." The return  |
| SMALLCHAT | glm5.2 | gpt-oss-120b | smallchat-server.c | MEDIUM | `ssize_t count = read(s, buf, sizeof(buf));` — if `read()` returns -1 (EINTR), `count <= 0` is true, |
| SMALLCHAT | glm5.2 | gpt-oss-120b | smallchat-server.c | MEDIUM | The header declares `void *chatMalloc(size_t size)` and `void *chatRealloc(void *ptr, size_t size)`  |
| SMALLCHAT | glm5.2 | mistral-small-4-119b | smallchat-server.c | MEDIUM | The server calls `write()` on TCP sockets without ignoring SIGPIPE. When a client disconnects and th |

### Unmatched Count by Pairing

- glm5.2×qwen3.8-27b: 13 unmatched
- glm5.2×gpt-oss-120b: 11 unmatched
- qwen3.8-27b×none: 9 unmatched
- glm5.2×none: 9 unmatched
- gpt-oss-120b×none: 8 unmatched
- gpt-oss-120b×mistral-small-4-119b: 8 unmatched
- qwen3.8-27b×glm5.2: 8 unmatched
- glm5.2×glm5.2: 7 unmatched
- gpt-oss-120b×gpt-oss-120b: 1 unmatched
- mistral-small-4-119b×mistral-small-4-119b: 1 unmatched
- qwen3.8-27b×qwen3.8-27b: 1 unmatched
- mistral-small-4-119b×none: 1 unmatched
- gpt-oss-120b×glm5.2: 1 unmatched
- gpt-oss-120b×qwen3.8-27b: 1 unmatched
- glm5.2×mistral-small-4-119b: 1 unmatched
- mistral-small-4-119b×gpt-oss-120b: 1 unmatched
- mistral-small-4-119b×glm5.2: 1 unmatched
- mistral-small-4-119b×qwen3.8-27b: 1 unmatched
- qwen3.8-27b×gpt-oss-120b: 1 unmatched
- qwen3.8-27b×mistral-small-4-119b: 1 unmatched

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
| 4/4 models | 0 | 0% |
| 3/4 models | 0 | 0% |
| 2/4 models | 1 | 2% |
| 1/4 models | 5 | 12% |
| 0/4 models (missed) | 37 | 86% |

### Bug Details by Consensus

#### Two Models (2/4)

| Bug ID | File | Severity | Category | Description | Found By |
|--------|------|----------|----------|-------------|-----------|
| SC-033 | Makefile | nitpick | process | No clean rule removes object files, only binaries deleted | qwen3.8-27b |

#### Sole Discovery (1/4 model)

| Bug ID | File | Severity | Category | Description | Found By |
|--------|------|----------|----------|-------------|-----------|
| SC-003 | smallchat-server.c | request-changes | error-handling | Ignored return value of write() in broadcast loop can silently drop messages | gpt-oss-120b |
| SC-006 | smallchat-server.c | request-changes | error-handling | Missing error handling for write() of welcome message | gpt-oss-120b |
| SC-020 | chatlib.c | request-changes | error-handling | Ignored return value of setsockopt() for SO_REUSEADDR in createTCPServer | gpt-oss-120b |
| SC-029 | chatlib.h | nitpick | abstraction | No const correctness on string parameters in header declarations | qwen3.8-27b |
| SC-038 | smallchat-server.c | nitpick | documentation | Comment describes behavior that does not match code | gpt-oss-120b |

#### Missed by All Models (0/4)

| Bug ID | File | Severity | Category | Description |
|--------|------|----------|----------|-------------|
| SC-001 | smallchat-server.c | reject | correctness | assert(Chat->clients[c->fd] == NULL) aborts on recoverable condition when fd slot already occupied |
| SC-002 | smallchat-server.c | reject | memory-safety | Fixed-size client table clients[MAX_CLIENTS] can overflow when fd >= 1000 |
| SC-004 | smallchat-server.c | request-changes | error-handling | Ignored result of socketSetNonBlockNoDelay() breaks event-driven design on failure |
| SC-005 | smallchat-server.c | request-changes | memory-safety | memcpy(c->nick,nick,nicklen) without null termination causes undefined behavior |
| SC-007 | smallchat-server.c | nitpick | complexity | MAX_CLIENTS constant conflates maximum clients with maximum fd without documentation |
| SC-008 | smallchat-server.c | reject | memory-safety | No SIGPIPE handling causes server crash on write to disconnected client |
| SC-009 | smallchat-server.c | reject | correctness | select() exits on EINTR - any signal kills the server instead of retrying |
| SC-010 | smallchat-server.c | reject | memory-safety | acceptClient return value not checked - createClient(-1) corrupts memory on EMFILE |
| SC-011 | smallchat-server.c | request-changes | complexity | select() 1-second timeout is speculative generality with no current purpose |
| SC-012 | smallchat-server.c | request-changes | correctness | No nick length validation allows memory exhaustion DoS via /nick command |
| SC-013 | smallchat-server.c | nitpick | error-handling | /nick with no argument gives misleading 'Unsupported command' error instead of usage message |
| SC-014 | smallchat-client.c | request-changes | error-handling | Ignored return value of write() when sending user input silently drops data |
| SC-015 | smallchat-client.c | request-changes | error-handling | Ignored return value of write() for server welcome messages |
| SC-016 | smallchat-client.c | request-changes | error-handling | No handling of inputBufferAppend() failure falls through and treats character as accepted |
| SC-017 | smallchat-client.c | nitpick | style | Backspace handling limited to DEL (127) does not handle other backspace codes |
| SC-018 | smallchat-client.c | nitpick | documentation | No handling of arrow keys/escape sequences not documented |
| SC-019 | chatlib.c | request-changes | error-handling | Ignored return value of setsockopt() in socketSetNonBlockNoDelay |
| SC-021 | chatlib.c | nitpick | abstraction | TCPConnect non-blocking EINPROGRESS path leaks addrinfo on failure |
| SC-022 | chatlib.c | request-changes | correctness | TCPConnect breaks out of address iteration loop on EINPROGRESS instead of continuing |
| SC-023 | chatlib.c | nitpick | abstraction | chatRealloc leaks original pointer on failure |
| SC-024 | smallchat-server.c | reject | concurrency | freeClient invalidates loop bound mid-iteration in broadcast loop |
| SC-025 | smallchat-server.c | request-changes | error-handling | write() return values ignored on non-blocking sockets in sendMsgToAllClientsBut |
| SC-026 | smallchat-client.c | request-changes | concurrency | Client select() exits on EINTR without retry logic |
| SC-027 | smallchat-client.c | nitpick | error-handling | No SIGPIPE handling in client can cause unexpected termination |
| SC-028 | chatlib.c | nitpick | documentation | socketSetNonBlockNoDelay does not preserve other fcntl flags |
| SC-030 | chatlib.h | nitpick | documentation | No extern C guard for C++ consumers |
| SC-031 | smallchat-server.c | request-changes | abstraction | Magic constant 127 for backspace handling duplicated without named constant |
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

**37 bug(s) missed by every model** — these may require skill refinement or represent subtle defects beyond current detection capability.

**5 bug(s) found by only one model** — these highlight model-specific strengths and potential complementarity.


---

## Native Pairing Advantage

For each model, compare its native skill (model == skill) against the mean of cross-skills (model != skill). Positive delta = native skill helps; negative = cross-skill helps. This measures native-skill advantage, not skill-on vs skill-off — for that comparison see `report/comparison.md`. Note: both reports use the same codebase.

| Model | Native DS | Cross-Skill Mean DS | Delta | Verdict |
|-------|----------|---------------------|-------|---------|
| glm5.2 | 0.00 | 0.00 | +0.00 | no difference |
| gpt-oss-120b | 0.00 | 0.08 | -0.08 | cross helps |
| mistral-small-4-119b | 0.00 | 0.00 | +0.00 | no difference |
| qwen3.8-27b | 0.00 | 0.03 | -0.03 | cross helps |

## Best Skill per Model

For each model, the skill that produces the highest Detection Score. Since true-positive counts are model-driven while the skill mainly affects the false-positive rate, the recommended skill is the one that maximizes DS (i.e., minimizes false positives).

| Model | Best Skill(s) | DS | Recommendation |
|-------|--------------|----|----------------|
| glm5.2 | glm5.2, gpt-oss-120b, mistral-small-4-119b, qwen3.8-27b | 0.00 | native skill (tied) |
| gpt-oss-120b | mistral-small-4-119b | 0.20 | cross-skill `mistral-small-4-119b` |
| mistral-small-4-119b | glm5.2, gpt-oss-120b, mistral-small-4-119b, qwen3.8-27b | 0.00 | native skill (tied) |
| qwen3.8-27b | glm5.2 | 0.08 | cross-skill `glm5.2` |


---

## Judge Score Detail

**Secondary metric.** Detection Score (above) is the primary metric because it is computed against ground truth and is reproducible from the committed eval data. The LLM-judge scores below are a quality opinion, not a measurement: they come from one model, on a 0-2 scale, with no inter-rater check. Use them to break ties, never to rank.

> **Note**: The judge (GLM5.2) also participates in the evaluation as a reviewer: judge scores may reflect self-preference.


The four sub-scores below feed the Judge Score (J) shown in the matrices above. Each is the mean over evaluated reviews on a 0–2 scale, scored by the judge model; values vary little across pairings, so they are shown as appendix detail.

### Judge Accuracy Matrix

| Skill \\ Model | glm5.2 | gpt-oss-120b | mistral-small-4-119b | qwen3.8-27b |
|---|---|---|---|---|
| glm5.2 | 1.0 | 1.0 | 0.0 | 1.4 |
| gpt-oss-120b | 1.5 | 1.0 | 0.0 | 0.0 |
| mistral-small-4-119b | 2.0 | 1.0 | 2.0 | 1.0 |
| qwen3.8-27b | 1.1 | 2.0 | 0.0 | 2.0 |
| No skill (baseline) | 2.0 | 2.0 | 2.0 | 1.8 |


### Judge Prioritization Matrix

| Skill \\ Model | glm5.2 | gpt-oss-120b | mistral-small-4-119b | qwen3.8-27b |
|---|---|---|---|---|
| glm5.2 | 1.4 | 1.0 | 1.0 | 1.5 |
| gpt-oss-120b | 1.7 | 1.0 | 0.0 | 0.0 |
| mistral-small-4-119b | 2.0 | 0.9 | 2.0 | 2.0 |
| qwen3.8-27b | 1.7 | 2.0 | 0.0 | 1.0 |
| No skill (baseline) | 2.0 | 1.6 | 2.0 | 1.4 |


### Judge Justification Matrix

| Skill \\ Model | glm5.2 | gpt-oss-120b | mistral-small-4-119b | qwen3.8-27b |
|---|---|---|---|---|
| glm5.2 | 0.9 | 1.0 | 1.0 | 1.6 |
| gpt-oss-120b | 1.7 | 1.0 | 0.0 | 0.0 |
| mistral-small-4-119b | 2.0 | 1.1 | 2.0 | 2.0 |
| qwen3.8-27b | 0.9 | 2.0 | 1.0 | 2.0 |
| No skill (baseline) | 2.0 | 1.9 | 2.0 | 1.8 |


### Judge Actionability Matrix

| Skill \\ Model | glm5.2 | gpt-oss-120b | mistral-small-4-119b | qwen3.8-27b |
|---|---|---|---|---|
| glm5.2 | 1.6 | 1.0 | 0.0 | 1.9 |
| gpt-oss-120b | 1.8 | 2.0 | 0.0 | 0.0 |
| mistral-small-4-119b | 2.0 | 0.9 | 1.0 | 2.0 |
| qwen3.8-27b | 1.5 | 2.0 | 1.0 | 2.0 |
| No skill (baseline) | 2.0 | 1.9 | 2.0 | 2.0 |


## Limitations

- **n=43 ground-truth bugs**: Evaluation based on the real SmallChat codebase with 43 known bugs.

- **Repetitions**: each model+skill pairing was evaluated 1x per bug.

- **Judge COI**: The judge (GLM5.2) also participates as a reviewer, so judge scores may reflect self-preference.

- **Prompt provenance**: reviewers never saw the ground-truth bug list, so these numbers measure detection against the ground-truth bug list.

- **Denominator choice**: Recall denominator uses only ground-truth bugs; any finding that matches no ground-truth bug counts as a false positive.


