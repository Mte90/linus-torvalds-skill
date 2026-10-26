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

**Best pairing**: `mistral-small-4-119b` reviewing with `glm5.2` skill found **8 bugs** across 43 ground-truth bugs.

**Best Detection Score**: `gpt-oss-120b` on `qwen3.8-27b` (DS=0.24).

**Best Judge Score**: `qwen3.8-27b` on `qwen3.8-27b` *(native)* (J=2.0/2).

**Best critical-bug pairing** (tie): `mistral-small-4-119b` on `mistral-small-4-119b`, `mistral-small-4-119b` on `glm5.2`, `mistral-small-4-119b` on `qwen3.8-27b`, `gpt-oss-120b` on `gpt-oss-120b`, `gpt-oss-120b` on `glm5.2`, `gpt-oss-120b` on `qwen3.8-27b` found **2** `reject`-severity bugs.

**Best reviewer model**: `mistral-small-4-119b` found **14** bugs (33% coverage) across all skills.

**Best skill**: `qwen3.8-27b` found **11** bugs (26% coverage) across all models.

**Consensus**: 2 bug(s) found by every model (across all skill pairings), 11 by only one model, 25 missed by all. This measures inter-model agreement, not skill-on vs skill-off.

**Native pairing advantage**: glm5.2: cross helps; gpt-oss-120b: cross helps; mistral-small-4-119b: cross helps; qwen3.8-27b: cross helps.

**Best skill per model**: 0 model(s) perform best with their native skill, 4 with a cross-skill. See the *Best Skill per Model* table below for specifics.

See `report/comparison.md` for the baseline-vs-skill analysis (whether adding any skill helps or hurts each model). Note: both reports use the same codebase.

In plain terms: the reviewing model — not the attached skill — drives how many bugs are found. Swapping skills rarely changes a model's true-positive count; the skill mainly affects precision (false positives), which is what moves the Detection Score. Start from the Overview Matrix, then use the ranking tables for specifics.

**Baseline comparison**: glm5.2: skill improves DS (0.11 vs 0.08); gpt-oss-120b: skill improves DS (0.24 vs 0.16); mistral-small-4-119b: skill improves DS (0.21 vs 0.06); qwen3.8-27b: skill improves DS (0.14 vs 0.14).



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

- **Unlocatable finding**: A finding that cites no line number. It cannot be matched against a ground-truth bug and therefore counts as a false positive. The reviewer sees the source with absolute line numbers in the left margin, so an absent line means the claim was not anchored to the code.

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
| **glm5.2** | DS=0.07 J=1.8/2 *(native)* | DS=0.20 J=1.4/2 | DS=0.21 J=1.1/2 | DS=0.08 J=1.5/2 |
| **gpt-oss-120b** | DS=0.11 J=1.9/2 | DS=0.08 J=1.4/2 *(native)* | DS=0.12 J=0.9/2 | DS=0.14 J=1.7/2 |
| **mistral-small-4-119b** | DS=0.08 J=1.8/2 | DS=0.16 J=1.1/2 | DS=0.16 J=0.9/2 *(native)* | DS=0.08 J=1.7/2 |
| **qwen3.8-27b** | DS=0.08 J=1.8/2 | DS=0.24 J=1.6/2 | DS=0.20 J=1.3/2 | DS=0.08 J=2.0/2 *(native)* |
| **No skill (baseline)** | DS=0.08 J=1.8/2 | DS=0.16 J=1.4/2 | DS=0.06 J=1.1/2 | DS=0.14 J=1.3/2 |


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

- **Best Detection Score**: gpt-oss-120b on qwen3.8-27b (DS=0.24)

- **Best Judge Score**: qwen3.8-27b on qwen3.8-27b *(native)* (J=2.0/2)


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

### Bugs Found per Model (union across all skills)

| Model | Total Found | Coverage | Exclusive |
|-------|-------------|----------|-----------|
| mistral-small-4-119b | 14 | 33% | 9 |
| gpt-oss-120b | 9 | 21% | 2 |
| qwen3.8-27b | 4 | 9% | 0 |
| glm5.2 | 3 | 7% | 0 |

### Bugs Found per Skill (union across all models)

| Skill | Total Found | Coverage | Exclusive |
|-------|-------------|----------|-----------|
| qwen3.8-27b | 11 | 26% | 2 |
| glm5.2 | 10 | 23% | 3 |
| mistral-small-4-119b | 9 | 21% | 1 |
| gpt-oss-120b | 7 | 16% | 0 |

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

### Bugs Found by Severity (union across all pairings)

| Severity | Total Bugs Found |
|----------|------------------|
| reject | 22 |
| request-changes | 12 |
| nitpick | 26 |

### Severity Breakdown per Model

| Model |reject|request-changes|nitpick| Total |
|-------|------|------|------|-------|
| glm5.2 | 4 | 0 | 5 | 9 |
| gpt-oss-120b | 7 | 3 | 7 | 17 |
| mistral-small-4-119b | 7 | 8 | 9 | 24 |
| qwen3.8-27b | 4 | 1 | 5 | 10 |

### Severity Breakdown per Skill

| Skill |reject|request-changes|nitpick| Total |
|-------|------|------|------|-------|
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

### Bugs Found by Category (union across all pairings)

| Category | Total Bugs Found |
|----------|------------------|
| memory-safety | 16 |
| documentation | 15 |
| error-handling | 9 |
| correctness | 7 |
| abstraction | 6 |
| process | 5 |
| concurrency | 2 |

### Category Breakdown per Model

| Model |abstraction|concurrency|correctness|documentation|error-handling|memory-safety|process| Total |
|-------|------|------|------|------|------|------|------|-------|
| glm5.2 | 0 | 0 | 0 | 4 | 0 | 4 | 1 | 9 |
| gpt-oss-120b | 2 | 0 | 4 | 2 | 2 | 4 | 3 | 17 |
| mistral-small-4-119b | 4 | 2 | 2 | 5 | 7 | 4 | 0 | 24 |
| qwen3.8-27b | 0 | 0 | 1 | 4 | 0 | 4 | 1 | 10 |

### Category Breakdown per Skill

| Skill |abstraction|concurrency|correctness|documentation|error-handling|memory-safety|process| Total |
|-------|------|------|------|------|------|------|------|-------|
| glm5.2 | 1 | 1 | 2 | 6 | 2 | 4 | 1 | 17 |
| gpt-oss-120b | 1 | 0 | 2 | 3 | 1 | 4 | 2 | 13 |
| mistral-small-4-119b | 2 | 1 | 0 | 3 | 2 | 4 | 1 | 13 |
| qwen3.8-27b | 2 | 0 | 3 | 3 | 4 | 4 | 1 | 17 |

---

## New Bug Candidates

Findings that match NO ground-truth bug — candidates for ground-truth expansion (require human triage).

| Diff ID | Model | Skill | File:Line | Severity | Issue |
|---------|-------|-------|-----------|----------|-------|
| SMALLCHAT | glm5.2 | glm5.2 | smallchat-server.c:85 | CRITICAL | `createClient` uses `c->fd` as a direct index into `Chat->clients[MAX_CLIENTS]` (1000 entries) with  |
| SMALLCHAT | glm5.2 | glm5.2 | smallchat-server.c:188 | CRITICAL | `acceptClient` can return -1 (accept failure from EMFILE, ENOMEM, connection reset). The return valu |
| SMALLCHAT | glm5.2 | glm5.2 | smallchat-server.c:143 | CRITICAL | The server calls `write()` on client sockets without ignoring SIGPIPE. When a client disconnects and |
| SMALLCHAT | glm5.2 | glm5.2 | chatlib.c:136 | CRITICAL | `chatMalloc` and `chatRealloc` call `exit(1)` on allocation failure. Resource exhaustion is a recove |
| SMALLCHAT | glm5.2 | glm5.2 | smallchat-server.c:180 | HIGH | When `select()` returns -1, the server immediately exits. But `select()` can return -1 with `errno = |
| SMALLCHAT | glm5.2 | glm5.2 | smallchat-server.c:85 | HIGH | `assert(Chat->clients[c->fd] == NULL)` is used to verify a slot is available. This condition depends |
| SMALLCHAT | glm5.2 | glm5.2 | smallchat-server.c:81 | HIGH | `createClient` sets the socket to non-blocking mode (line 81), but the read loop at line 209 treats  |
| SMALLCHAT | glm5.2 | glm5.2 | smallchat-client.c:248 | HIGH | `write(s, ib.buf, ib.len)` sends user input to the server socket. If the server has closed the conne |
| SMALLCHAT | glm5.2 | glm5.2 | smallchat-client.c:220 | HIGH | Same as the server: `select()` returning -1 with `EINTR` causes the client to exit. The client has a |
| SMALLCHAT | glm5.2 | glm5.2 | smallchat-client.c:204 | HIGH | `setRawMode(fileno(stdin), 1)` is called but the return value is not checked. If `setRawMode` fails  |
| SMALLCHAT | glm5.2 | glm5.2 | chatlib.c:94 | HIGH | In `TCPConnect`, when `connect()` returns -1 with `errno == EINPROGRESS` and `nonblock` is true, the |
| SMALLCHAT | glm5.2 | none | smallchat-server.c:84 | CRITICAL | `memcpy(c->nick,nick,nicklen)` copies `nicklen` bytes but does NOT copy the null terminator. `chatMa |
| SMALLCHAT | glm5.2 | none | smallchat-server.c:85 | CRITICAL | `Chat->clients` is declared as `struct client *clients[MAX_CLIENTS]` with `MAX_CLIENTS=1000`. The fd |
| SMALLCHAT | glm5.2 | none | smallchat-server.c:188 | CRITICAL | `acceptClient` can return -1 on error (e.g., `EMFILE`, `ENOMEM`, `ECONNABORTED`). The return value i |
| SMALLCHAT | glm5.2 | none | smallchat-server.c:143 | HIGH | `write()` to a socket whose peer has closed generates `SIGPIPE`. The default disposition is `SIG_DFL |
| SMALLCHAT | glm5.2 | none | smallchat-server.c:180 | HIGH | `select()` returns -1 with `errno == EINTR` when interrupted by a signal. Both the server and client |
| SMALLCHAT | glm5.2 | none | smallchat-server.c:209 | HIGH | `read()` can return -1 with `errno == EINTR` if a signal is delivered before any data is read. The c |
| SMALLCHAT | glm5.2 | none | chatlib.c:94 | HIGH | When `connect()` returns -1 with `EINPROGRESS` on a non-blocking socket, the function returns `s` im |
| SMALLCHAT | glm5.2 | none | smallchat-server.c:81 | HIGH | `socketSetNonBlockNoDelay(fd)` can fail (e.g., if `fcntl` fails). The return value is ignored with a |
| SMALLCHAT | glm5.2 | gpt-oss-120b | smallchat-server.c:188 | CRITICAL | `acceptClient()` can return `-1` on failure. The return value is never checked before passing it to  |
| SMALLCHAT | glm5.2 | gpt-oss-120b | smallchat-server.c:83 | CRITICAL | `snprintf(nick, sizeof(nick), "user:%d", fd)` returns the string length without the null terminator. |
| SMALLCHAT | glm5.2 | gpt-oss-120b | smallchat-server.c:85 | CRITICAL | `MAX_CLIENTS` is defined as 1000, and `Chat->clients` is an array of 1000 pointers. Clients are stor |
| SMALLCHAT | glm5.2 | gpt-oss-120b | smallchat-server.c:85 | HIGH | `assert(Chat->clients[c->fd] == NULL)` crashes the entire server if a file descriptor slot is alread |
| SMALLCHAT | glm5.2 | gpt-oss-120b | smallchat-server.c:143 | HIGH | The server calls `write()` on client sockets without ignoring SIGPIPE. When a client disconnects abr |
| SMALLCHAT | glm5.2 | gpt-oss-120b | smallchat-server.c:143 | HIGH | All `write()` calls to client sockets discard the return value. On a non-blocking socket (which thes |
| SMALLCHAT | glm5.2 | gpt-oss-120b | smallchat-server.c:166 | HIGH | `FD_SET(j, &readfds)` at line 166 and `select(maxfd+1, ...)` at line 179 use file descriptors as bit |
| SMALLCHAT | glm5.2 | gpt-oss-120b | smallchat-client.c:239 | HIGH | When `read(stdin_fd, buf, sizeof(buf))` returns 0 (EOF — e.g., input redirected from a file, or `Ctr |
| SMALLCHAT | glm5.2 | gpt-oss-120b | smallchat-client.c:239 | HIGH | `ssize_t count = read(stdin_fd, buf, sizeof(buf))` — the return value is never checked for `-1`. If  |
| SMALLCHAT | glm5.2 | gpt-oss-120b | chatlib.c:94 | HIGH | When `connect()` returns `-1` with `errno == EINPROGRESS` on a non-blocking socket, the function exe |
| SMALLCHAT | glm5.2 | gpt-oss-120b | Makefile:5 | LOW | `$(CC) smallchat-server.c chatlib.c -o smallchat-server $(CFLAGS)` places `CFLAGS` after the source  |
| SMALLCHAT | glm5.2 | gpt-oss-120b | Makefile:1 | LOW | The `all` and `clean` targets are not declared `.PHONY`. If a file named `all` or `clean` exists in  |
| SMALLCHAT | glm5.2 | mistral-small-4-119b | smallchat-server.c:85 | CRITICAL | `Chat->clients` is declared as `struct client *clients[MAX_CLIENTS]` with `MAX_CLIENTS=1000`, but th |
| SMALLCHAT | glm5.2 | mistral-small-4-119b | smallchat-server.c:188 | CRITICAL | `acceptClient` can return -1 on error, but the return value is never checked. The result is passed d |
| SMALLCHAT | glm5.2 | mistral-small-4-119b | smallchat-server.c:83 | CRITICAL | In `createClient`, the nickname is allocated as `chatMalloc(nicklen+1)` but only `nicklen` bytes are |
| SMALLCHAT | glm5.2 | mistral-small-4-119b | smallchat-server.c:143 | HIGH | The server calls `write()` on client sockets without installing a SIGPIPE handler (`signal(SIGPIPE,  |
| SMALLCHAT | glm5.2 | mistral-small-4-119b | chatlib.c:94 | HIGH | In `TCPConnect`, when `connect()` returns -1 with `errno == EINPROGRESS` and `nonblock` is set, the  |
| SMALLCHAT | glm5.2 | mistral-small-4-119b | smallchat-client.c:248 | HIGH | The client calls `write(s, ib.buf, ib.len)` on the server socket without handling SIGPIPE. If the se |
| SMALLCHAT | glm5.2 | qwen3.8-27b | smallchat-server.c:86 | CRITICAL | `Chat->clients[c->fd] = c` writes into a fixed-size array of `MAX_CLIENTS` (1000) elements without v |
| SMALLCHAT | glm5.2 | qwen3.8-27b | smallchat-server.c:143 | CRITICAL | The server calls `write()` on client sockets. When a client disconnects, the next `write()` to that  |
| SMALLCHAT | glm5.2 | qwen3.8-27b | smallchat-server.c:85 | HIGH | `assert(Chat->clients[c->fd] == NULL)` crashes the entire server if the slot is already occupied. Th |
| SMALLCHAT | glm5.2 | qwen3.8-27b | smallchat-server.c:209 | HIGH | `read(j, readbuf, sizeof(readbuf)-1)` can return `-1` with `errno == EINTR` if a signal interrupts t |
| SMALLCHAT | glm5.2 | qwen3.8-27b | smallchat-server.c:143 | HIGH | All client sockets are set to non-blocking mode (`socketSetNonBlockNoDelay` on line 81). On a non-bl |
| SMALLCHAT | glm5.2 | qwen3.8-27b | smallchat-server.c:163 | HIGH | `FD_SET(fd, &readfds)` writes into the `fd_set` structure on the stack. On most platforms `fd_set` h |
| SMALLCHAT | glm5.2 | qwen3.8-27b | smallchat-server.c:81 | HIGH | `socketSetNonBlockNoDelay(fd)` can fail (e.g., `fcntl` returns `-1`). The return value is ignored wi |
| SMALLCHAT | glm5.2 | qwen3.8-27b | chatlib.c:94 | HIGH | When `connect()` returns `-1` with `errno == EINPROGRESS` on a non-blocking socket, the function ret |
| SMALLCHAT | glm5.2 | qwen3.8-27b | chatlib.c:136 | HIGH | Both allocators call `exit(1)` when `malloc`/`realloc` returns `NULL`. `chatMalloc` is called from ` |
| SMALLCHAT | mistral-small-4-119b | mistral-small-4-119b | smallchat-server.c:255 | CRITICAL | The `snprintf()` call in `main()` can overflow the `msg` buffer when formatting messages. While the  |
| SMALLCHAT | mistral-small-4-119b | mistral-small-4-119b | smallchat-server.c:81 | CRITICAL | `socketSetNonBlockNoDelay()` is called without checking its return value. If this fails, the client  |
| SMALLCHAT | mistral-small-4-119b | mistral-small-4-119b | smallchat-server.c:58 | CRITICAL | The global `Chat` state is accessed and modified from multiple places without any synchronization. T |
| SMALLCHAT | mistral-small-4-119b | mistral-small-4-119b | smallchat-server.c:216 | CRITICAL | When `read()` returns <= 0, the client is freed but the socket is not properly closed before calling |

### Unmatched Count by Pairing

- mistral-small-4-119b×glm5.2: 32 unmatched
- mistral-small-4-119b×qwen3.8-27b: 27 unmatched
- mistral-small-4-119b×gpt-oss-120b: 24 unmatched
- mistral-small-4-119b×none: 20 unmatched
- mistral-small-4-119b×mistral-small-4-119b: 19 unmatched
- qwen3.8-27b×none: 14 unmatched
- qwen3.8-27b×gpt-oss-120b: 13 unmatched
- glm5.2×gpt-oss-120b: 12 unmatched
- glm5.2×glm5.2: 11 unmatched
- qwen3.8-27b×qwen3.8-27b: 10 unmatched
- glm5.2×qwen3.8-27b: 9 unmatched
- glm5.2×none: 8 unmatched
- gpt-oss-120b×mistral-small-4-119b: 8 unmatched
- gpt-oss-120b×qwen3.8-27b: 8 unmatched
- gpt-oss-120b×none: 7 unmatched
- gpt-oss-120b×glm5.2: 7 unmatched
- glm5.2×mistral-small-4-119b: 6 unmatched
- qwen3.8-27b×mistral-small-4-119b: 6 unmatched
- gpt-oss-120b×gpt-oss-120b: 5 unmatched
- qwen3.8-27b×glm5.2: 5 unmatched

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
| SC-008 | smallchat-server.c | reject | memory-safety | No SIGPIPE handling causes server crash on write to disconnected client | gpt-oss-120b |
| SC-038 | smallchat-server.c | nitpick | documentation | Comment describes behavior that does not match code | gpt-oss-120b |

#### Three Models (3/4)

| Bug ID | File | Severity | Category | Description | Found By |
|--------|------|----------|----------|-------------|-----------|
| SC-033 | Makefile | nitpick | process | No clean rule removes object files, only binaries deleted | glm5.2, gpt-oss-120b, mistral-small-4-119b, qwen3.8-27b |

#### Two Models (2/4)

| Bug ID | File | Severity | Category | Description | Found By |
|--------|------|----------|----------|-------------|-----------|
| SC-020 | chatlib.c | request-changes | error-handling | Ignored return value of setsockopt() for SO_REUSEADDR in createTCPServer | glm5.2, gpt-oss-120b, qwen3.8-27b |
| SC-022 | chatlib.c | request-changes | correctness | TCPConnect breaks out of address iteration loop on EINPROGRESS instead of continuing | glm5.2, gpt-oss-120b, qwen3.8-27b |
| SC-025 | smallchat-server.c | request-changes | error-handling | write() return values ignored on non-blocking sockets in sendMsgToAllClientsBut | glm5.2, gpt-oss-120b, qwen3.8-27b |
| SC-028 | chatlib.c | nitpick | documentation | socketSetNonBlockNoDelay does not preserve other fcntl flags | glm5.2, gpt-oss-120b, qwen3.8-27b |

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

For each model, compare its native skill (model == skill) against the mean of cross-skills (model != skill). Positive delta = native skill helps; negative = cross-skill helps. This measures native-skill advantage, not skill-on vs skill-off — for that comparison see `report/comparison.md`. Note: both reports use the same codebase.

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

**Secondary metric.** Detection Score (above) is the primary metric because it is computed against ground truth and is reproducible from the committed eval data. The LLM-judge scores below are a quality opinion, not a measurement: they come from one model, on a 0-2 scale, with no inter-rater check. Use them to break ties, never to rank.

> **Note**: The judge (GLM5.2) also participates in the evaluation as a reviewer: judge scores may reflect self-preference.


The four sub-scores below feed the Judge Score (J) shown in the matrices above. Each is the mean over evaluated reviews on a 0–2 scale, scored by the judge model; values vary little across pairings, so they are shown as appendix detail.

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


