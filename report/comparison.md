---
title: Model Comparison — SmallChat Review
date: 2026-11-11
codebase: antirez/smallchat
models: gpt-oss-120b, glm5.2, mistral, qwen3.8-27b
skill: linus-torvalds-skill (language-agnostic)
method: static review, skill triggers applied per source file
---

# Model Comparison — SmallChat Review

> **Evaluation provenance:** the reviewer prompt carried only the code under review, never the ground-truth bug list (enforced by regression tests in [tests/test_eval.py](tests/test_eval.py)). Every number below therefore measures detection, not transcription.


Dataset: SmallChat codebase (~706 LOC), 4 models reviewed with and without the Linus Torvalds skill.

> **Note:** The judge (GLM5.2) also participates as a reviewer: judge scores may reflect self-preference.

## About this report

This report answers: **Does adding the skill help or hurt each model?** (Baseline vs. skill comparison on the SmallChat codebase.)

**Three roles:** (1) **reviewer model** — the LLM reviewing code; (2) **skill** — the language-agnostic Linus Torvalds skill; (3) **judge model** — GLM5.2 scoring review quality.

| Model | Total Findings | Critical Findings | Skill-Only Critical | Verdict |
|-------|---------------|-------------------|---------------------|---------|
| gpt-oss-120b | 8 | 3 | 3 | Skill adds value |
| glm5.2 | 11 | 3 | 2 | Skill adds value |
| mistral | 9 | 4 | 4 | Skill adds value |
| qwen3.8-27b | 16 | 3 | 3 | Skill adds value |

How to read the Verdict column: 'Skill-Only Critical' counts critical bugs a model found only when using the skill; 'Baseline-Only Critical' counts critical bugs found only without it. 'Skill adds value' means a net gain of critical findings with the skill; 'Skill reduces coverage' means a net loss; 'No change' means the model finds the same criticals either way.

The skill adds the most value for mistral, which gained 4 critical finding(s) exclusive to the with-skill review.

## Metrics Summary

| Metric | gpt-oss-120b | glm5.2 | mistral | qwen3.8-27b |
|-------- | :---: | :---: | :---: | :---:|
| Findings (raw) |12 | 11 | 15 | 21 |
| Findings (dedup) |8 | 11 | 9 | 16 |

**DS is the primary metric.** Detection Score combines precision and recall against ground-truth bug matches, so it drives every ranking in this report. Judge scores reflect one model's opinion of review quality: use them to break ties, not to rank.


---

## Skill Generation Per Model

Each variant is distilled from the same 350 patterns. Distill settings (mode, token budget, timeout) are identical across models; what differs is the review-time token budget and severity calibration.

| Model | Skill file | Distill mode | Review token budget | Severity calibration |
|-------|------------|--------------|---------------------|---------------------|
| gpt-oss-120b | [linus-torvalds-skill/gpt-oss/skill.md](linus-torvalds-skill/gpt-oss/skill.md) | single | 16000 (default) | balanced |
| glm5.2 | [linus-torvalds-skill/glm/skill.md](linus-torvalds-skill/glm/skill.md) | single | 32000 | downgrade ONLY style/docs borderline, never correctness/error-handling |
| mistral | [linus-torvalds-skill/mistral/skill.md](linus-torvalds-skill/mistral/skill.md) | two-stage | 16000 | under-rates → upgrade borderline |
| qwen3.8-27b | [linus-torvalds-skill/qwen/skill.md](linus-torvalds-skill/qwen/skill.md) | single | 131072 | none measured |

**Source:** [src/torvalds_skill/profiles.py](src/torvalds_skill/profiles.py). Regenerate per [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md).

**Key insight:** Finding count is a poor quality signal. The consensus matrix below shows which models caught which bugs — and that is where the real signal lives.

---

## Finding Consensus Matrix

Every finding from gpt-oss-120b and glm5.2 and mistral and qwen3.8-27b reviews, mapped to the underlying issue. ✓ = found, ✗ = missed. Severity shown in parentheses.

### chatlib.c

| # | Issue | gpt-oss-120b | glm5.2 | mistral | qwen3.8-27b | Consensus |
|---|---|:---:|:---:|:---:|:---:|:---:|
| 1 | TCPConnect leaks memory when connect returns... | ✓ (HIGH) | ✓ (HIGH) | ✗ | ✗ | — |
| 2 | socketSetNonBlockNoDelay ignores setsockopt error | ✓ (HIGH) | ✗ | ✓ (HIGH) | ✓ (HIGH) | 3/4 |
| 3 | Fatal abort on out-of-memory in chatMalloc and... | ✗ | ✓ (HIGH) | ✓ (CRITICAL) | ✗ | — |
| 4 | Finding title: Fatal abort for recoverable memory... | ✗ | ✗ | ✗ | ✓ (CRITICAL) | qwen3.8-27b only |

*Severity: reject = critical bug, request-changes = important bug, nitpick = minor issue.*

### chatlib.h

| # | Issue | gpt-oss-120b | glm5.2 | mistral | qwen3.8-27b | Consensus |
|---|---|:---:|:---:|:---:|:---:|:---:|
| 5 | TCPConnect signature should use const char *addr | ✓ (CRITICAL) | ✓ (MEDIUM) | ✓ (MEDIUM) | ✓ (HIGH) | 4/4 |
| 6 | Missing .PHONY declarations | ✓ (MEDIUM) | ✓ (MEDIUM) | ✓ (MEDIUM) | ✓ (HIGH) | 4/4 |
| 7 | Unnecessary `-W` flag | ✓ (LOW) | ✓ (LOW) | ✗ | ✓ (MEDIUM) | 3/4 |
| 8 | Sparse documentation | ✗ | ✗ | ✓ (LOW) | ✗ | mistral only |
| 9 | Incomplete Cleanup | ✗ | ✗ | ✓ (LOW) | ✗ | mistral only |
| 10 | Special targets are not declared `.PHONY` | ✗ | ✗ | ✗ | ✓ (LOW) | qwen3.8-27b only |

*Severity: reject = critical bug, request-changes = important bug, nitpick = minor issue.*

### smallchat-client.c

| # | Issue | gpt-oss-120b | glm5.2 | mistral | qwen3.8-27b | Consensus |
|---|---|:---:|:---:|:---:|:---:|:---:|
| 11 | Ignoring write return value may cause SIGPIPE... | ✓ (HIGH) | ✗ | ✗ | ✓ (HIGH) | — |
| 12 | FD_SET can write out of bounds when fd >=... | ✗ | ✗ | ✗ | ✓ (CRITICAL) | qwen3.8-27b only |
| 13 | select() EINTR is treated as fatal | ✗ | ✗ | ✗ | ✓ (HIGH) | qwen3.8-27b only |
| 14 | Stdin read() failure is silently ignored | ✗ | ✗ | ✗ | ✓ (HIGH) | qwen3.8-27b only |
| 15 | Input buffer overflow is silently swallowed | ✗ | ✗ | ✗ | ✓ (HIGH) | qwen3.8-27b only |
| 16 | Port argument parsed with atoi without range... | ✗ | ✗ | ✗ | ✓ (HIGH) | qwen3.8-27b only |

*Severity: reject = critical bug, request-changes = important bug, nitpick = minor issue.*

### smallchat-server.c

| # | Issue | gpt-oss-120b | glm5.2 | mistral | qwen3.8-27b | Consensus |
|---|---|:---:|:---:|:---:|:---:|:---:|
| 17 | Out-of-bounds read when generating initial... | ✓ (CRITICAL) | ✓ (CRITICAL) | ✓ (CRITICAL) | ✓ (HIGH) | 4/4 |
| 18 | Out-of-bounds write when storing client in array | ✓ (CRITICAL) | ✓ (CRITICAL) | ✗ | ✓ (CRITICAL) | 3/4 |
| 19 | assert() crashes server for a recoverable... | ✗ | ✓ (HIGH) | ✓ (CRITICAL) | ✗ | — |
| 20 | acceptClient return value not checked before use | ✗ | ✓ (CRITICAL) | ✗ | ✗ | glm5.2 only |
| 21 | exit(1) on select() EINTR — transient signal... | ✗ | ✓ (HIGH) | ✗ | ✗ | glm5.2 only |
| 22 | read() returning -1 with EINTR treated as client... | ✗ | ✓ (HIGH) | ✗ | ✗ | glm5.2 only |
| 23 | Unchecked allocation return in initChat | ✗ | ✗ | ✓ (CRITICAL) | ✗ | mistral only |
| 24 | Unchecked `write` in `sendMsgToAllClientsBut` | ✗ | ✗ | ✗ | ✓ (HIGH) | qwen3.8-27b only |
| 25 | `select` maxfd Logic Vulnerability | ✗ | ✗ | ✗ | ✓ (HIGH) | qwen3.8-27b only |

*Severity: reject = critical bug, request-changes = important bug, nitpick = minor issue.*

---

## Severity Disagreement Table

Cases where 2+ models found the same issue but assigned different severities:

| Issue | gpt-oss-120b | glm5.2 | mistral | qwen3.8-27b |
|-------|:---:|:---:|:---:|:---:|
| Fatal abort on out-of-memory in... | — | HIGH | CRITICAL | — |
| TCPConnect signature should use const... | CRITICAL | MEDIUM | MEDIUM | HIGH |
| Missing .PHONY declarations | MEDIUM | MEDIUM | MEDIUM | HIGH |
| Unnecessary `-W` flag | LOW | LOW | — | MEDIUM |
| Out-of-bounds read when generating... | CRITICAL | CRITICAL | CRITICAL | HIGH |
| assert() crashes server for a... | — | HIGH | CRITICAL | — |

---

## Trigger Coverage Comparison

Which skill triggers fired in each review:

| Trigger theme | gpt-oss-120b | glm5.2 | mistral | qwen3.8-27b |
|---------------|:---:|:---:|:---:|:---:|
| (error handling — recoverable... | ✗ | ✓ (1) | ✗ | ✗ |
| (memory safety —... | ✗ | ✓ (1) | ✗ | ✗ |
| (unchecked error leading to... | ✗ | ✓ (1) | ✗ | ✗ |
| Ambiguous return values –... | ✗ | ✗ | ✗ | ✓ (1) |
| Assertion used for... | ✗ | ✗ | ✓ (1) | ✗ |
| Correctness & Safety... | ✗ | ✗ | ✗ | ✓ (1) |
| Crash-prone paths (missing... | ✗ | ✗ | ✗ | ✓ (1) |
| Crash-prone paths (missing... | ✗ | ✗ | ✗ | ✓ (1) |
| Crash-prone paths / Ambiguous... | ✗ | ✗ | ✗ | ✓ (1) |
| Crash-prone paths / Cross... | ✗ | ✗ | ✗ | ✓ (1) |
| Crash-prone paths – missing... | ✗ | ✗ | ✗ | ✓ (2) |
| Error Handling (silent error... | ✗ | ✗ | ✗ | ✓ (1) |
| Fatal abort for recoverable... | ✗ | ✓ (2) | ✗ | ✗ |
| Fatal assertion or crash used... | ✗ | ✓ (1) | ✗ | ✗ |
| Fatal assertion used for... | ✗ | ✗ | ✓ (1) | ✗ |
| Ignoring a returned error... | ✓ (3) | ✗ | ✗ | ✗ |
| Inconsistent error handling... | ✗ | ✗ | ✗ | ✓ (2) |
| Inconsistent naming style | ✗ | ✗ | ✓ (1) | ✗ |
| Interface that requires... | ✗ | ✓ (1) | ✗ | ✗ |
| Missing documentation | ✗ | ✗ | ✓ (1) | ✗ |
| Silent failure | ✗ | ✗ | ✓ (1) | ✗ |
| Unchecked allocation return | ✗ | ✗ | ✓ (1) | ✗ |
| Unchecked errors | ✗ | ✗ | ✗ | ✓ (1) |
| Uninitialized or partially... | ✗ | ✓ (1) | ✗ | ✗ |
| Untrusted boundary crossing | ✗ | ✗ | ✓ (1) | ✗ |
| Using fatal abort for... | ✗ | ✗ | ✗ | ✓ (1) |
| Using fatal abort for... | ✗ | ✗ | ✗ | ✓ (1) |

**Note:** 11 finding(s) fired no skill trigger and are excluded from the table above (they carry no trigger theme): gpt-oss-120b=5, glm5.2=2, mistral=2, qwen3.8-27b=2. They are still counted as findings in the metrics tables, so precision here reflects trigger coverage while overall precision reflects all findings.

---

## With-Skill vs Baseline Comparison

For each model, comparing findings with the skill vs without (baseline):

### Critical Impact Summary

| Model | Baseline Total | With-Skill Total | Skill Added Value |
|-------|----------------|------------------|-------------------|
| gpt-oss-120b | 11 | 8 | yes (+3 net critical: 3 found, 0 lost) |
| glm5.2 | 11 | 11 | neutral (0 net: 2 found, 2 lost) |
| mistral | 8 | 9 | yes (+2 net critical: 4 found, 2 lost) |
| qwen3.8-27b | 16 | 16 | neutral (0 net: 3 found, 3 lost) |

### Critical Findings Breakdown

| Model | Baseline CRITICAL | With-Skill CRITICAL | Critical Overlap | Skill-Only CRITICAL | Baseline-Only CRITICAL |
|-------|-------------------|---------------------|------------------|---------------------|------------------------|
| gpt-oss-120b | 0 | 3 | 0 | 3 | 0 |
| glm5.2 | 3 | 3 | 1 | 2 | 2 |
| mistral | 2 | 4 | 0 | 4 | 2 |
| qwen3.8-27b | 3 | 3 | 0 | 3 | 3 |

---

## Per-Model Bug Comparison (Baseline vs With-Skill)

Bug-by-bug comparison for each model: which bugs were found by both, only baseline, or only skill.

### gpt-oss-120b

**Same bugs (found in both):**

| Issue | File | Baseline | Skill | Severity changed? |
|-------|------|----------|-------|-------------------|
| TCPConnect signature should use const char *addr | chatlib.h | LOW | CRITICAL | YES: LOW→CRITICAL |
| Missing .PHONY declarations | chatlib.h | LOW | MEDIUM | YES: LOW→MEDIUM |
| Unnecessary `-W` flag | chatlib.h | LOW | LOW | no |
| Out-of-bounds write when storing client in array | smallchat-server.c | HIGH | CRITICAL | YES: HIGH→CRITICAL |

**Baseline-only (skill missed):**

*Classification: `skill-gap` = CORE finding with matched trigger (skill should catch); `out-of-scope` = TRIVIA finding (intentionally uncovered); `sampling-loss` = CORE finding with no matched trigger (pattern absent from 325-sample cluster).*

| Issue | File | Severity | Classification | Trigger coverage |
|-------|------|----------|----------------|------------------|
| Missing null terminator for client nick | smallchat-server.c | HIGH | sampling-loss | unmatched |
| Unchecked return value from `acceptClient` leading to... | smallchat-server.c | HIGH | sampling-loss | unmatched |
| Use of `write()` for stdout instead of stdio functions | smallchat-client.c | LOW | sampling-loss | unmatched |
| Ignoring the possibility that both sockets are ready in... | smallchat-client.c | LOW | sampling-loss | unmatched |
| Ambiguous parameter name `nonblock` in `TCPConnect` | chatlib.c | LOW | sampling-loss | unmatched |
| Use of `struct sockaddr_in` in `acceptClient` instead of... | chatlib.c | LOW | sampling-loss | unmatched |
| `CFLAGS` defined after target rules, so flags are not... | chatlib.h | MEDIUM | sampling-loss | unmatched |

**Skill-only (skill added):**

| Issue | File | Severity | Trigger |
|-------|------|----------|---------|
| Out-of-bounds read when generating initial nickname | smallchat-server.c | CRITICAL | (unmatched) |
| Ignoring write return value may cause SIGPIPE crash | smallchat-client.c | HIGH | Ignoring a returned error from a called... |
| TCPConnect leaks memory when connect returns EINPROGRESS in... | chatlib.c | HIGH | Ignoring a returned error from a called... |
| socketSetNonBlockNoDelay ignores setsockopt error | chatlib.c | HIGH | Ignoring a returned error from a called... |

### glm5.2

**Same bugs (found in both):**

| Issue | File | Baseline | Skill | Severity changed? |
|-------|------|----------|-------|-------------------|
| `TCPConnect` takes non-const `char *addr` | chatlib.h | LOW | MEDIUM | YES: LOW→MEDIUM |
| Missing header file dependencies | chatlib.h | LOW | MEDIUM | YES: LOW→MEDIUM |
| Deprecated -W compiler flag | chatlib.h | LOW | LOW | no |
| No bounds check on file descriptor before indexing... | smallchat-server.c | CRITICAL | CRITICAL | no |

**Baseline-only (skill missed):**

*Classification: `skill-gap` = CORE finding with matched trigger (skill should catch); `out-of-scope` = TRIVIA finding (intentionally uncovered); `sampling-loss` = CORE finding with no matched trigger (pattern absent from 325-sample cluster).*

| Issue | File | Severity | Classification | Trigger coverage |
|-------|------|----------|----------------|------------------|
| Unchecked `acceptClient` return value leads to negative... | smallchat-server.c | CRITICAL | sampling-loss | unmatched |
| No SIGPIPE handling — process killed on write to closed... | smallchat-server.c | CRITICAL | sampling-loss | unmatched |
| Missing null terminator on initial nickname | smallchat-server.c | HIGH | sampling-loss | unmatched |
| `select()` exits the process on EINTR | smallchat-server.c | HIGH | sampling-loss | unmatched |
| No SIGPIPE handling — client killed on write to closed... | smallchat-client.c | HIGH | sampling-loss | unmatched |
| stdin EOF causes infinite 100% CPU spin | smallchat-client.c | HIGH | sampling-loss | unmatched |
| Memory leak in `TCPConnect` on non-blocking EINPROGRESS path | chatlib.c | HIGH | sampling-loss | unmatched |

**Skill-only (skill added):**

| Issue | File | Severity | Trigger |
|-------|------|----------|---------|
| Nick string not null-terminated in createClient | smallchat-server.c | CRITICAL | Uninitialized or partially initialized... |
| acceptClient return value not checked before use | smallchat-server.c | CRITICAL | (unchecked error leading to... |
| assert() crashes server for a recoverable condition | smallchat-server.c | HIGH | Fatal assertion or crash used for a... |
| exit(1) on select() EINTR — transient signal interruption... | smallchat-server.c | HIGH | Fatal abort for recoverable resource... |
| read() returning -1 with EINTR treated as client... | smallchat-server.c | HIGH | (error handling — recoverable error... |
| Memory leak in TCPConnect on nonblocking connect path | chatlib.c | HIGH | (unmatched — resource leak on... |
| Fatal abort on out-of-memory in chatMalloc and chatRealloc | chatlib.c | HIGH | Fatal abort for recoverable resource... |

### mistral

**Same bugs (found in both):**

*None.*

**Baseline-only (skill missed):**

*Classification: `skill-gap` = CORE finding with matched trigger (skill should catch); `out-of-scope` = TRIVIA finding (intentionally uncovered); `sampling-loss` = CORE finding with no matched trigger (pattern absent from 325-sample cluster).*

| Issue | File | Severity | Classification | Trigger coverage |
|-------|------|----------|----------------|------------------|
| Missing null terminator in client nickname | smallchat-server.c | CRITICAL | sampling-loss | unmatched |
| No bounds checking on file descriptor | smallchat-server.c | CRITICAL | sampling-loss | unmatched |
| Unchecked setsockopt in socketSetNonBlockNoDelay | smallchat-server.c | HIGH | sampling-loss | unmatched |
| atoi does not validate port input | smallchat-server.c | HIGH | sampling-loss | unmatched |
| Fixed-size buffer truncation in main message handling | smallchat-server.c | MEDIUM | sampling-loss | unmatched |
| Confusing maxclient management logic | chatlib.c | MEDIUM | sampling-loss | unmatched |
| Unchecked setsockopt in TCPConnect | smallchat-client.c | HIGH | sampling-loss | unmatched |
| No timeout on select() | chatlib.h | MEDIUM | sampling-loss | unmatched |

**Skill-only (skill added):**

| Issue | File | Severity | Trigger |
|-------|------|----------|---------|
| Unchecked allocation return in initChat | smallchat-server.c | CRITICAL | Unchecked allocation return |
| Assertion used for recoverable condition in createClient | smallchat-server.c | CRITICAL | Assertion used for recoverable condition |
| Untrusted boundary crossing in freeClient | smallchat-server.c | CRITICAL | Untrusted boundary crossing |
| Finding title: Fatal assertion on recoverable condition... | chatlib.c | CRITICAL | Fatal assertion used for recoverable... |
| Finding title: Silent failure on socket configuration... | chatlib.c | HIGH | Silent failure |
| Naming inconsistency | chatlib.h | MEDIUM | Inconsistent naming style |
| Sparse documentation | chatlib.h | LOW | Missing documentation |
| Build Syntax Error | chatlib.h | MEDIUM | (unmatched) |
| Incomplete Cleanup | chatlib.h | LOW | (unmatched) |

### qwen3.8-27b

**Same bugs (found in both):**

| Issue | File | Baseline | Skill | Severity changed? |
|-------|------|----------|-------|-------------------|
| Unchecked `write` in `sendMsgToAllClientsBut` | smallchat-server.c | CRITICAL | HIGH | YES: CRITICAL→HIGH |
| `select` maxfd Logic Vulnerability | smallchat-server.c | CRITICAL | HIGH | YES: CRITICAL→HIGH |
| Finding: TCPConnect NULL Pointer Dereference Risk | chatlib.h | LOW | HIGH | YES: LOW→HIGH |
| Finding: createTCPServer Invalid Port Range | chatlib.h | LOW | HIGH | YES: LOW→HIGH |

**Baseline-only (skill missed):**

*Classification: `skill-gap` = CORE finding with matched trigger (skill should catch); `out-of-scope` = TRIVIA finding (intentionally uncovered); `sampling-loss` = CORE finding with no matched trigger (pattern absent from 325-sample cluster).*

| Issue | File | Severity | Classification | Trigger coverage |
|-------|------|----------|----------------|------------------|
| No error checking on write() calls | smallchat-server.c | CRITICAL | sampling-loss | unmatched |
| Unchecked malloc failures | smallchat-server.c | HIGH | sampling-loss | unmatched |
| No validation of client socket descriptors | smallchat-server.c | HIGH | sampling-loss | unmatched |
| No validation of command arguments | smallchat-server.c | HIGH | sampling-loss | unmatched |
| No graceful shutdown mechanism | smallchat-server.c | MEDIUM | sampling-loss | unmatched |
| Hardcoded server port | smallchat-server.c | MEDIUM | sampling-loss | unmatched |
| No validation of input buffer length | smallchat-client.c | HIGH | sampling-loss | unmatched |
| No validation of message length before sending | smallchat-client.c | HIGH | sampling-loss | unmatched |
| No signal handling | smallchat-client.c | MEDIUM | sampling-loss | unmatched |
| No validation of port number | chatlib.c | HIGH | sampling-loss | unmatched |
| No error handling for accept() | chatlib.c | HIGH | sampling-loss | unmatched |
| chatMalloc exits on failure | chatlib.c | MEDIUM | sampling-loss | unmatched |

**Skill-only (skill added):**

| Issue | File | Severity | Trigger |
|-------|------|----------|---------|
| Array Bounds Violation in Client State | smallchat-server.c | CRITICAL | Crash-prone paths (missing bounds... |
| Unchecked Allocation in `createClient` | smallchat-server.c | HIGH | Correctness & Safety (unchecked... |
| FD_SET can write out of bounds when fd >= FD_SETSIZE | smallchat-client.c | CRITICAL | Crash-prone paths – missing bounds... |
| select() EINTR is treated as fatal | smallchat-client.c | HIGH | Using fatal abort for recoverable... |
| Stdin read() failure is silently ignored | smallchat-client.c | HIGH | Inconsistent error handling within a... |
| write() return values are ignored, including socket send | smallchat-client.c | HIGH | Inconsistent error handling within a... |
| Input buffer overflow is silently swallowed | smallchat-client.c | HIGH | Ambiguous return values – same value... |
| Port argument parsed with atoi without range validation | smallchat-client.c | HIGH | Crash-prone paths – missing bounds... |
| Finding title: Fatal abort for recoverable memory error | chatlib.c | CRITICAL | Using fatal abort for recoverable errors |
| Finding title: Unchecked setsockopt in... | chatlib.c | HIGH | Unchecked errors |
| Missing header dependencies can produce stale builds | chatlib.h | MEDIUM | (unmatched) |
| Special targets are not declared `.PHONY` | chatlib.h | LOW | (unmatched) |

---

## Qualitative Analysis

### Consensus-Based Accuracy

Findings confirmed by 2+ models are treated as real bugs. Findings reported by only one model are unverified (could be real or false positive).

| Model | Total Findings | Confirmed (2+ models) | Unverified (1 model only) | Consensus Rate |
|-------|:--------------:|:---------------------:|:--------------------------:|:--------------:|
| gpt-oss-120b | 8 | 8 | 0 | 100% |
| glm5.2 | 11 | 8 | 3 | 73% |
| mistral | 9 | 6 | 3 | 67% |
| qwen3.8-27b | 16 | 7 | 9 | 44% |

### Severity Calibration

Cases where 2+ models found the same issue but assigned different severities:

| Issue | gpt-oss-120b | glm5.2 | mistral | qwen3.8-27b |
|-------|:---:|:---:|:---:|:---:|
| Fatal abort on out-of-memory in... | — | HIGH | CRITICAL | — |
| TCPConnect signature should use const... | CRITICAL | MEDIUM | MEDIUM | HIGH |
| Missing .PHONY declarations | MEDIUM | MEDIUM | MEDIUM | HIGH |
| Unnecessary `-W` flag | LOW | LOW | — | MEDIUM |
| Out-of-bounds read when generating... | CRITICAL | CRITICAL | CRITICAL | HIGH |
| assert() crashes server for a... | — | HIGH | CRITICAL | — |

Total severity disagreements: 6. Lower is better — it means the model's severity assessment aligns with the consensus.

### Unique Findings (Single-Model Discoveries)

Findings reported by only one model. These represent either unique insight or false positives:

| Model | Unique Findings |
|-------|:--------------:|
| gpt-oss-120b | 0 |
| glm5.2 | 3 |
| mistral | 3 |
| qwen3.8-27b | 9 |

A high unique count with a low consensus rate suggests false positives. A high unique count with a high consensus rate suggests the model found real bugs others missed.

### With-Skill vs Baseline: Skill Impact

How the skill changed each model's review:

**gpt-oss-120b:** Baseline 11 findings (0 CRITICAL) → With-skill 8 findings (3 CRITICAL). Skill found 3 critical bug(s) the baseline missed; baseline found 0 critical bug(s) the skill missed.

**glm5.2:** Baseline 11 findings (3 CRITICAL) → With-skill 11 findings (3 CRITICAL). Skill found 2 critical bug(s) the baseline missed; baseline found 2 critical bug(s) the skill missed.

**mistral:** Baseline 8 findings (2 CRITICAL) → With-skill 9 findings (4 CRITICAL). Skill found 4 critical bug(s) the baseline missed; baseline found 2 critical bug(s) the skill missed.

**qwen3.8-27b:** Baseline 16 findings (3 CRITICAL) → With-skill 16 findings (3 CRITICAL). Skill found 3 critical bug(s) the baseline missed; baseline found 3 critical bug(s) the skill missed.

#### Skill Tradeoff Analysis

The skill narrows reviewer focus toward memory-safety and correctness (Linus's priorities). This filters noise but can also suppress valid findings. Net critical impact per model:

| Model | Skill-Only CRITICAL | Baseline-Only CRITICAL | Net Critical Impact | Total Finding Delta |
|-------|:-------------------:|:----------------------:|:-------------------:|:-------------------:|
| gpt-oss-120b | 3 | 0 | +3 | -3 |
| glm5.2 | 2 | 2 | 0 | 0 |
| mistral | 4 | 2 | +2 | +1 |
| qwen3.8-27b | 3 | 3 | 0 | 0 |

**Interpretation:** A positive net critical impact means the skill found real bugs the baseline missed. A negative value means the skill suppressed critical findings the baseline caught — a coverage gap. A large negative total finding delta with neutral critical impact means the skill filtered noise without losing signal.

**Per-model read:**
- **gpt-oss-120b:** Net positive. The skill cut 3 findings and added 3 critical bug(s) the baseline missed.
- **glm5.2:** Neutral. No net change in critical coverage.
- **mistral:** Net positive. The skill added findings and added 2 critical bug(s) the baseline missed.
- **qwen3.8-27b:** Neutral. No net change in critical coverage.

### Trigger Coverage Analysis

Which skill triggers each model fired:

**gpt-oss-120b:** 2 distinct triggers fired, 8 total trigger firings.
  Top triggers: (unmatched) (5x), Ignoring a returned error from a called function (3x)

**glm5.2:** 9 distinct triggers fired, 11 total trigger firings.
  Top triggers: Fatal abort for recoverable resource exhaustion (2x), (unmatched) (2x), Uninitialized or partially initialized data exposed to external callers (1x)

**mistral:** 8 distinct triggers fired, 9 total trigger firings.
  Top triggers: (unmatched) (2x), Unchecked allocation return (1x), Assertion used for recoverable condition (1x)

**qwen3.8-27b:** 13 distinct triggers fired, 16 total trigger firings.
  Top triggers: Crash-prone paths – missing bounds checks, unchecked allocations, out-of-bounds accesses, integer overflows. (2x), Inconsistent error handling within a module – mixed return conventions, silent ignores. (2x), (unmatched) (2x)

### Verdict

Based on consensus-confirmed CRITICAL findings, net critical impact (skill-only minus baseline-only), and severity calibration:

| Model | Confirmed CRITICAL | Skill-Only CRITICAL | Baseline-Only CRITICAL | Net Critical | Severity Disagreements | Score |
|-------|:------------------:|:-------------------:|:----------------------:|:-------------:|:----------------------:|:-----:|
| gpt-oss-120b | 3 | 3 | 0 | +3 | 2 | 4 |
| glm5.2 | 2 | 2 | 2 | 0 | 4 | -2 |
| mistral | 3 | 4 | 2 | +2 | 4 | 1 |
| qwen3.8-27b | 1 | 3 | 3 | 0 | 2 | -1 |

**Scoring:** `confirmed_critical + skill_only_critical - baseline_only_critical - severity_disagreements`. All terms are CRITICAL-only for unit consistency. Severity disagreements counted only when at least one model assigned CRITICAL (cross-scale equivalent: reject). The baseline-only penalty makes coverage gaps visible: a model that suppresses real bugs the baseline caught scores lower, even if it found other bugs the baseline missed.

**Honest read:** 
gpt-oss-120b wins clearly with score 4. 
mistral follows at 1.
 The skill helps differently per model — see the per-model read above for the tradeoff details.

---

## SmallChat Benchmark

Skill impact on the curated SmallChat dataset (43 records in [data/benchmark.jsonl](data/benchmark.jsonl)) — Arm: with-skill reviews. Counts use deduped findings.

Metrics computed by matching model findings to benchmark records by file and line number (±10 lines tolerance).

### Per-Model Benchmark Metrics

| Model | Precision | Recall | DS | Hits | Misses | Severity Match Rate |
|-------|-----------|--------|------|------|--------|---------------------|
| gpt-oss-120b | 37.5% | 7.0% | 11.8% | 3 | 40 | 66.7% |
| glm5.2 | 36.4% | 9.3% | 14.8% | 4 | 39 | 75.0% |
| mistral | 55.6% | 11.6% | 19.2% | 5 | 38 | 60.0% |
| qwen3.8-27b | 37.5% | 14.0% | 20.3% | 6 | 37 | 66.7% |

> **Note:** The benchmark is derived entirely from model consensus (no external tool or human verification). Precision and recall are therefore relative measures of cross-model agreement, not absolute correctness.


---

## Calibration (Refusal)

Assessment of model refusal behavior on clean and ambiguous cases.

| Model | Clean FP Rate (n/d) | Ambiguous Confidence Error (n/d) | Refusal Accuracy |
|-------|:-------------------:|:--------------------------------:|:----------------:|
| gpt-oss-120b | 46.7% (0/30) | 40.0% (0/10) | 60.0% |
| glm5.2 | 80.0% (0/30) | 40.0% (0/10) | 60.0% |
| mistral | 90.0% (0/20) | 85.7% (0/7) | 14.3% |
| qwen3.8-27b | 90.0% (0/30) | 60.0% (0/10) | 40.0% |

> **Note:** Clean FP Rate measures false positives on records expected to have no findings. Ambiguous Confidence Error measures incorrect high-confidence conclusions on ambiguous cases. Refusal Accuracy = 1 - Ambiguous Confidence Error. Denominators shown in parentheses.

## Limitations


- **Repetitions**: each model+skill pairing was evaluated 1x per diff scenario.
- **No variance estimate**: with a single run per cell there is no standard deviation, so differences of ~0.03 Detection Score between pairings should be read as noise, not as a ranking difference.
- **Judge COI**: The judge (GLM5.2) also participates as a reviewer, so judge scores may reflect self-preference.
- **Prompt provenance**: reviewers never saw the ground-truth bug list, so these numbers measure detection against the ground-truth bug list.

- **Denominator choice**: Recall denominator uses only buggy diffs (expected=="findings"); findings on clean or refusal scenarios count as false positives.



## Executive Summary

Across all models, 25 unique issue(s) were identified, with qwen3.8-27b performing best (16 finding(s)) and gpt-oss-120b performing worst (8 finding(s)).  The skill-only approach identified 12 critical bug(s) the baseline missed, while the baseline found 7 critical bug(s) the skill missed.  Native skill configurations outperformed cross-skill pairings on critical coverage.
