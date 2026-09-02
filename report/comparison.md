---
title: Model Comparison — SmallChat Review
date: 2026-09-02
codebase: antirez/smallchat
models: gpt-oss-120b, glm5.2, mistral
skill: linus-torvalds-skill (language-agnostic)
method: static review, skill triggers applied per source file
---

# Model Comparison — SmallChat Review

## Stakeholder Scorecard

Quick summary for non-technical readers:

| Model | Total Findings | Critical Findings | Skill-Only Critical | Verdict |
|-------|---------------|-------------------|---------------------|---------|
| gpt-oss-120b | 11 | 6 | 5 | Skill adds value |
| glm5.2 | 21 | 4 | 3 | Skill adds value |
| mistral | 10 | 3 | 2 | Skill adds value |

The skill adds the most value for gpt-oss-120b, which gained 5 critical finding(s) exclusive to the with-skill review.

## Skill Generation Per Model

Skills are NOT identical — each variant is distilled from the same 350 patterns but with model-specific prompt calibration, token budgets, and execution mode.

| Model | Skill file | Distill mode | Token budget | Wall-clock timeout | Severity bias note |
|-------|------------|--------------|--------------|-------------------|-------------------|
| gpt-oss-120b | `linus-torvalds-skill/SKILL.md` | two-stage (14 categories + synthesis) | 16000 | 120s (WALL_CLOCK_DEFAULT) | balanced |
| glm5.2 | `linus-torvalds-skill/SKILL-GLM.md` | single-call | 16000 (GLM_MAX_TOKENS) | 600s / 1800s (WALL_CLOCK_GLM) | downgrade ONLY style/docs borderline, never correctness/error-handling (see `MODEL_SEVERITY_BIAS` in `distill.py`) |
| mistral-small-4-119b | `linus-torvalds-skill/SKILL-Mistral.md` | two-stage | 16000 | 120s | under-rates → upgrade borderline |

**Source:** `src/torvalds_skill/distill.py:MODEL_SEVERITY_BIAS`, `src/torvalds_skill/config.py:_MODEL_TIMEOUTS` and `GLM_MAX_TOKENS`. Regenerate per `docs/CONTRIBUTING.md`.

This explains why glm5.2 previously lost 3 criticals (over-filtering style) and why trigger coverage differs across models.

3 models reviewed the same C codebase (antirez/smallchat, ~706 LOC) using the same language-agnostic Linus Torvalds skill. This document cross-references their findings at the issue level — not just counts — to measure consensus, accuracy, and severity calibration.

## Metrics Summary

| Metric | gpt-oss-120b | glm5.2 | mistral |
|--------|:---:|:---:|:---:|
| Findings | 11 | 21 | 10 |
| Critical | 6 | 4 | 3 |
| High | 2 | 5 | 2 |
| Medium | 2 | 5 | 2 |
| Low | 1 | 7 | 3 |
| Words | 1027 | 2893 | 1001 |

**Key insight:** Finding count is a poor quality signal. The consensus matrix below shows which models caught which bugs — and that is where the real signal lives.

---

## Finding Consensus Matrix

Every finding from all three reviews, mapped to the underlying issue. ✓ = found, ✗ = missed. Severity shown in parentheses.

### chatlib.c

| # | Issue | gpt-oss-120b | glm5.2 | mistral | Consensus |
|---|:---:|:---:|:---:|:---:|
| 1 | Ignoring possible error from `setsockopt` in `sock... | ✓ (MEDIUM) | ✗ | ✓ (LOW) | 2/3 |
| 2 | TCPConnect breaks on connect failure instead of co... | ✗ | ✓ (HIGH) | ✗ | glm5.2 only |
| 3 | chatMalloc/chatRealloc exit on OOM — recoverable e... | ✗ | ✓ (HIGH) | ✗ | glm5.2 only |
| 4 | acceptClient only handles EINTR — other transient ... | ✗ | ✓ (LOW) | ✗ | glm5.2 only |
| 5 | Style: Redundant casts | ✗ | ✗ | ✓ (LOW) | mistral only |

### chatlib.h

| # | Issue | gpt-oss-120b | glm5.2 | mistral | Consensus |
|---|:---:|:---:|:---:|:---:|
| 6 | Invalid compiler flag `-W` | ✓ (LOW) | ✓ (LOW) | ✗ | 2/3 |
| 7 | No debug symbols — hinders debugging | ✗ | ✓ (LOW) | ✗ | glm5.2 only |

### smallchat-client.c

| # | Issue | gpt-oss-120b | glm5.2 | mistral | Consensus |
|---|:---:|:---:|:---:|:---:|
| 8 | Partial writes are not handled | ✓ (HIGH) | ✗ | ✗ | gpt-oss-120b only |
| 9 | Event‑loop drops simultaneous stdin + socket activ... | ✓ (CRITICAL) | ✗ | ✗ | gpt-oss-120b only |
| 10 | Buffer overflow not reported in `inputBufferFeedCh... | ✓ (CRITICAL) | ✗ | ✗ | gpt-oss-120b only |
| 11 | Ignoring the return value of `write(s, ib.buf, ib.... | ✓ (HIGH) | ✓ (MEDIUM) | ✗ | 2/3 |
| 12 | `setRawMode` return value ignored | ✓ (MEDIUM) | ✗ | ✗ | gpt-oss-120b only |
| 13 | read() from stdin ignores errors | ✗ | ✓ (MEDIUM) | ✗ | glm5.2 only |
| 14 | Dead code after infinite loop | ✗ | ✓ (LOW) | ✗ | glm5.2 only |
| 15 | atoi(argv[2]) has no validation | ✗ | ✓ (LOW) | ✗ | glm5.2 only |
| 16 | Backspace key code 127 is not portable | ✗ | ✓ (LOW) | ✗ | glm5.2 only |

### smallchat-server.c

| # | Issue | gpt-oss-120b | glm5.2 | mistral | Consensus |
|---|:---:|:---:|:---:|:---:|
| 17 | Out‑of‑bounds access of `Chat->clients` array | ✓ (CRITICAL) | ✓ (CRITICAL) | ✓ (LOW) | 3/3 |
| 18 | Nickname strings are not NUL‑terminated | ✓ (CRITICAL) | ✓ (CRITICAL) | ✗ | 2/3 |
| 19 | Use of `assert` aborts the whole program on a reco... | ✓ (CRITICAL) | ✓ (HIGH) | ✗ | 2/3 |
| 20 | Ignoring write errors when broadcasting messages | ✓ (CRITICAL) | ✓ (MEDIUM) | ✓ (CRITICAL) | 3/3 |
| 21 | acceptClient return value unchecked — fd=-1 passed... | ✗ | ✓ (CRITICAL) | ✓ (MEDIUM) | 2/3 |
| 22 | sendMsgToAllClientsBut ignores write() return on n... | ✗ | ✓ (HIGH) | ✓ (CRITICAL) | 2/3 |
| 23 | MAX_CLIENTS comment is misleading | ✗ | ✓ (LOW) | ✓ (MEDIUM) | 2/3 |
| 24 | select() exits on EINTR — recoverable signal inter... | ✗ | ✓ (CRITICAL) | ✗ | glm5.2 only |
| 25 | No connection limit — resource exhaustion and OOB ... | ✗ | ✓ (HIGH) | ✗ | glm5.2 only |
| 26 | socketSetNonBlockNoDelay failure silently ignored ... | ✗ | ✓ (MEDIUM) | ✗ | glm5.2 only |
| 27 | /nick command accepts unvalidated input — format i... | ✗ | ✓ (MEDIUM) | ✗ | glm5.2 only |
| 28 | Unvalidated read() results | ✗ | ✗ | ✓ (CRITICAL) | mistral only |
| 29 | Public interface instability (nickname exposure) | ✗ | ✗ | ✓ (HIGH) | mistral only |
| 30 | Missing fallbacks for fallible allocations | ✗ | ✗ | ✓ (HIGH) | mistral only |

---

## Severity Disagreement Table

Cases where 2+ models found the same issue but assigned different severities:

| Issue | gpt-oss-120b | glm5.2 | mistral |
|-------|:---:|:---:|:---:|
| Ignoring possible error from `setsockopt... | MEDIUM | — | LOW |
| Ignoring the return value of `write(s, i... | HIGH | MEDIUM | — |
| Out‑of‑bounds access of `Chat->clients` ... | CRITICAL | CRITICAL | LOW |
| Use of `assert` aborts the whole program... | CRITICAL | HIGH | — |
| Ignoring write errors when broadcasting ... | CRITICAL | MEDIUM | CRITICAL |
| acceptClient return value unchecked — fd... | — | CRITICAL | MEDIUM |
| sendMsgToAllClientsBut ignores write() r... | — | HIGH | CRITICAL |
| MAX_CLIENTS comment is misleading | — | LOW | MEDIUM |

---

## Trigger Coverage Comparison

Which skill triggers fired in each review:

| Trigger theme | gpt-oss-120b | glm5.2 | mistral |
|---------------|:---:|:---:|:---:|
| (unmatched) | ✗ | ✓ (4) | ✗ |
| All Error‑Handling Paths Must ... | ✓ (3) | ✗ | ✗ |
| Avoid exposing internal detail... | ✗ | ✗ | ✓ (1) |
| Avoid special-case hacks and m... | ✗ | ✗ | ✓ (1) |
| Avoid unnecessary abstractions... | ✗ | ✗ | ✓ (1) |
| Binary Correctness | ✓ (3) | ✗ | ✗ |
| Code that produces incorrect o... | ✗ | ✓ (2) | ✗ |
| Code that produces incorrect o... | ✗ | ✓ (1) | ✗ |
| Comments that do not match the... | ✗ | ✓ (2) | ✗ |
| Dead or redundant code providi... | ✗ | ✓ (1) | ✗ |
| Demand evidence for performanc... | ✗ | ✗ | ✓ (1) |
| Error code returned that calle... | ✗ | ✓ (3) | ✗ |
| Fatal assertion or abort used ... | ✗ | ✓ (3) | ✗ |
| Handle fallible allocations ex... | ✗ | ✗ | ✓ (1) |
| Hot‑Path Code Must Remain Low‑... | ✓ (1) | ✗ | ✗ |
| Never Use Custom Synchronisati... | ✓ (1) | ✗ | ✗ |
| No Unbounded Resource Allocati... | ✓ (1) | ✗ | ✗ |
| No race conditions in resource... | ✗ | ✗ | ✓ (1) |
| Prefer Existing, Well‑Tested A... | ✓ (1) | ✗ | ✗ |
| Prefer Simple, Un‑Clever Code | ✓ (1) | ✗ | ✗ |
| Return value that is ambiguous... | ✗ | ✓ (3) | ✗ |
| Security-critical state not in... | ✗ | ✓ (1) | ✗ |
| Separate core logic from resou... | ✗ | ✗ | ✓ (1) |
| Stack-allocated object referen... | ✗ | ✓ (1) | ✗ |
| Use the simplest solution that... | ✗ | ✗ | ✓ (1) |
| Validate inputs and preserve i... | ✗ | ✗ | ✓ (2) |

---

## With-Skill vs Baseline Comparison

For each model, comparing findings with the skill vs without (baseline):

| Model | Baseline Total | With-Skill Total | Baseline CRITICAL | With-Skill CRITICAL | Critical Overlap | Skill-Only CRITICAL | Baseline-Only CRITICAL | Skill Added Value |
|-------|----------------|------------------|-------------------|---------------------|------------------|---------------------|------------------------|-------------------|
| gpt-oss-120b | 15 | 11 | 1 | 6 | 1 | 5 | 0 | yes (+5 net critical: 5 found, 0 lost) |
| glm5.2 | 26 | 21 | 2 | 4 | 1 | 3 | 1 | yes (+2 net critical: 3 found, 1 lost) |
| mistral | 19 | 10 | 2 | 3 | 1 | 2 | 1 | yes (+1 net critical: 2 found, 1 lost) |

---

## Per-Model Bug Comparison (Baseline vs With-Skill)

Bug-by-bug comparison for each model: which bugs were found by both, only baseline, or only skill.

### gpt-oss-120b

**Same bugs (found in both):**

| Issue | File | Baseline | Skill | Severity changed? |
|-------|------|----------|-------|-------------------|
| Nickname strings are not NUL‑terminated | smallchat-server.c | MEDIUM | CRITICAL | YES: MEDIUM→CRITICAL |
| Use of `assert` aborts the whole program on a recoverable co... | smallchat-server.c | MEDIUM | CRITICAL | YES: MEDIUM→CRITICAL |
| Ignoring the return value of `write(s, ib.buf, ib.len)` | smallchat-client.c | LOW | HIGH | YES: LOW→HIGH |
| `setRawMode` return value ignored | smallchat-client.c | LOW | MEDIUM | YES: LOW→MEDIUM |
| Ignoring possible error from `setsockopt` in `socketSetNonBl... | chatlib.c | LOW | MEDIUM | YES: LOW→MEDIUM |
| Out‑of‑bounds access of `Chat->clients` array | smallchat-server.c | CRITICAL | CRITICAL | no |

**Baseline-only (skill missed):**

| Issue | File | Severity | Skill trigger covers? |
|-------|------|----------|-----------------------|
| Potential SIGPIPE termination on writes | smallchat-server.c | MEDIUM | out of scope |
| Unhandled partial writes | smallchat-server.c | LOW | out of scope |
| No newline handling for long messages | smallchat-server.c | LOW | out of scope |
| No explicit handling of `SIGINT`/graceful shutdown | smallchat-client.c | LOW | out of scope |
| Unhandled SIGPIPE on writes to the server | smallchat-client.c | MEDIUM | out of scope |
| Unchecked partial writes to the server socket | smallchat-client.c | LOW | out of scope |
| Input buffer overflow silently dropped | smallchat-client.c | LOW | out of scope |
| `TCPConnect` aborts address iteration on `socketSetNonBlockN... | chatlib.c | LOW | out of scope |
| Server socket is created blocking | chatlib.c | LOW | out of scope |

**Skill-only (skill added):**

| Issue | File | Severity | Trigger |
|-------|------|----------|---------|
| Ignoring write errors when broadcasting messages | smallchat-server.c | CRITICAL | All Error‑Handling Paths Must Be Reliabl... |
| Partial writes are not handled | smallchat-client.c | HIGH | Hot‑Path Code Must Remain Low‑Overhead (... |
| Event‑loop drops simultaneous stdin + socket activity | smallchat-client.c | CRITICAL | Binary Correctness |
| Buffer overflow not reported in `inputBufferFeedChar` | smallchat-client.c | CRITICAL | Binary Correctness |
| Invalid compiler flag `-W` | chatlib.h | LOW | Prefer Simple, Un‑Clever Code |

### glm5.2

**Same bugs (found in both):**

| Issue | File | Baseline | Skill | Severity changed? |
|-------|------|----------|-------|-------------------|
| Nickname not null-terminated in createClient — heap over-rea... | smallchat-server.c | HIGH | CRITICAL | YES: HIGH→CRITICAL |
| acceptClient return value unchecked — fd=-1 passed to create... | smallchat-server.c | CRITICAL | CRITICAL | no |
| fd used as array index without bounds check — out-of-bounds ... | smallchat-server.c | HIGH | CRITICAL | YES: HIGH→CRITICAL |
| select() exits on EINTR — recoverable signal interruption cr... | smallchat-server.c | HIGH | CRITICAL | YES: HIGH→CRITICAL |
| sendMsgToAllClientsBut ignores write() return on non-blockin... | smallchat-server.c | CRITICAL | HIGH | YES: CRITICAL→HIGH |
| assert in createClient crashes server for recoverable condit... | smallchat-server.c | LOW | HIGH | YES: LOW→HIGH |
| /nick command accepts unvalidated input — format injection a... | smallchat-server.c | MEDIUM | MEDIUM | no |
| MAX_CLIENTS comment is misleading | smallchat-server.c | LOW | LOW | no |
| Dead code after infinite loop | smallchat-client.c | HIGH | LOW | YES: HIGH→LOW |
| Backspace key code 127 is not portable | smallchat-client.c | LOW | LOW | no |
| TCPConnect breaks on connect failure instead of continuing —... | chatlib.c | MEDIUM | HIGH | YES: MEDIUM→HIGH |
| acceptClient only handles EINTR — other transient errors not... | chatlib.c | MEDIUM | LOW | YES: MEDIUM→LOW |
| CFLAGS placed after source files — unconventional and fragil... | chatlib.h | LOW | LOW | no |
| No debug symbols — hinders debugging | chatlib.h | LOW | LOW | no |
| write() return values ignored for welcome and error messages | smallchat-server.c | MEDIUM | MEDIUM | no |

**Baseline-only (skill missed):**

| Issue | File | Severity | Skill trigger covers? |
|-------|------|----------|-----------------------|
| Nickname not validated for length or content | smallchat-server.c | MEDIUM | out of scope |
| `select()` with `fd_set` has an implicit `FD_SETSIZE` limit | smallchat-server.c | LOW | out of scope |
| Busy-loop at 100% CPU when stdin reaches EOF | smallchat-client.c | MEDIUM | out of scope |
| No SIGPIPE handling — client killed when writing to closed s... | smallchat-client.c | MEDIUM | out of scope |
| Mixed `printf()` and `write()` output can cause interleaving | smallchat-client.c | LOW | out of scope |
| No feedback when input buffer is full | smallchat-client.c | LOW | out of scope |
| `acceptClient()` uses `struct sockaddr_in` — cannot accept I... | chatlib.c | LOW | out of scope |
| `socketSetNonBlockNoDelay()` ignores `setsockopt()` failure | chatlib.c | LOW | out of scope |
| No `extern "C"` guard for C++ compatibility | chatlib.h | LOW | out of scope |
| No `const` correctness on string parameters | chatlib.h | LOW | out of scope |
| No `.PHONY` declaration for `all` and `clean` | chatlib.h | LOW | out of scope |

**Skill-only (skill added):**

| Issue | File | Severity | Trigger |
|-------|------|----------|---------|
| No connection limit — resource exhaustion and OOB access | smallchat-server.c | HIGH | Security-critical state not initialized ... |
| socketSetNonBlockNoDelay failure silently ignored — server m... | smallchat-server.c | MEDIUM | Error code returned that callers cannot ... |
| inputBufferAppend return value not checked when appending ne... | smallchat-client.c | MEDIUM | Return value that is ambiguous between s... |
| read() from stdin ignores errors | smallchat-client.c | MEDIUM | Error code returned that callers cannot ... |
| atoi(argv[2]) has no validation | smallchat-client.c | LOW | Error code returned that callers cannot ... |
| chatMalloc/chatRealloc exit on OOM — recoverable error crash... | chatlib.c | HIGH | Fatal assertion or abort used for a reco... |

### mistral

**Same bugs (found in both):**

| Issue | File | Baseline | Skill | Severity changed? |
|-------|------|----------|-------|-------------------|
| Race condition in maxclient update | smallchat-server.c | LOW | CRITICAL | YES: LOW→CRITICAL |
| Unvalidated read() results | smallchat-server.c | LOW | CRITICAL | YES: LOW→CRITICAL |
| Inefficient select() loop | smallchat-server.c | MEDIUM | MEDIUM | no |
| Style: Redundant casts | chatlib.c | MEDIUM | LOW | YES: MEDIUM→LOW |
| Buffer overflow in nickname handling | smallchat-server.c | CRITICAL | CRITICAL | no |

**Baseline-only (skill missed):**

| Issue | File | Severity | Skill trigger covers? |
|-------|------|----------|-----------------------|
| Finding: Missing Error Handling in socketSetNonBlockNoDelay | smallchat-server.c | HIGH | out of scope |
| Finding: Unsafe String Handling | smallchat-server.c | MEDIUM | out of scope |
| Finding: Terminal Raw Mode Not Restored on Crash | smallchat-client.c | CRITICAL | out of scope |
| Finding: Potential Buffer Overflow in Input Handling | smallchat-client.c | HIGH | out of scope |
| Finding: No Timeout Handling in select() | smallchat-client.c | MEDIUM | out of scope |
| Finding: Magic Numbers in Terminal Codes | smallchat-client.c | LOW | out of scope |
| Finding: Potential Resource Leak in TCPConnect | chatlib.c | HIGH | out of scope |
| Finding: No Port Range Validation | chatlib.c | MEDIUM | out of scope |
| Finding: No IPv6 Support | chatlib.c | LOW | out of scope |
| Finding: Inconsistent Error Handling | chatlib.h | LOW | out of scope |
| Finding: Missing Function Prototypes | chatlib.h | LOW | out of scope |
| Finding: No Documentation | chatlib.h | LOW | out of scope |
| Finding: No Compiler Warnings for All Files | chatlib.h | LOW | out of scope |
| Finding: No Debug Symbols or Sanitizers | chatlib.h | LOW | out of scope |

**Skill-only (skill added):**

| Issue | File | Severity | Trigger |
|-------|------|----------|---------|
| Public interface instability (nickname exposure) | smallchat-server.c | HIGH | Avoid exposing internal details in publi... |
| Missing fallbacks for fallible allocations | smallchat-server.c | HIGH | Handle fallible allocations explicitly |
| Unnecessary global state | smallchat-server.c | MEDIUM | Separate core logic from resource manage... |
| Style: Inconsistent error handling | chatlib.c | LOW | Use the simplest solution that works |
| Style: Magic constants | smallchat-server.c | LOW | Avoid special-case hacks and magic const... |

---

## Qualitative Analysis

### Consensus-Based Accuracy

Findings confirmed by 2+ models are treated as real bugs. Findings reported by only one model are unverified (could be real or false positive).

| Model | Total Findings | Confirmed (2+ models) | Unverified (1 model only) | Consensus Rate |
|-------|:--------------:|:---------------------:|:--------------------------:|:--------------:|
| gpt-oss-120b | 11 | 7 | 4 | 64% |
| glm5.2 | 21 | 9 | 12 | 43% |
| mistral | 10 | 6 | 4 | 60% |

### Severity Calibration

Cases where 2+ models found the same issue but assigned different severities:

| Issue | gpt-oss-120b | glm5.2 | mistral |
|-------|:---:|:---:|:---:|
| Ignoring possible error from `setsockopt... | MEDIUM | — | LOW |
| Ignoring the return value of `write(s, i... | HIGH | MEDIUM | — |
| Out‑of‑bounds access of `Chat->clients` ... | CRITICAL | CRITICAL | LOW |
| Use of `assert` aborts the whole program... | CRITICAL | HIGH | — |
| Ignoring write errors when broadcasting ... | CRITICAL | MEDIUM | CRITICAL |
| acceptClient return value unchecked — fd... | — | CRITICAL | MEDIUM |
| sendMsgToAllClientsBut ignores write() r... | — | HIGH | CRITICAL |
| MAX_CLIENTS comment is misleading | — | LOW | MEDIUM |

Total severity disagreements: 8. Lower is better — it means the model's severity assessment aligns with the consensus.

### Unique Findings (Single-Model Discoveries)

Findings reported by only one model. These represent either unique insight or false positives:

| Model | Unique Findings |
|-------|:--------------:|
| gpt-oss-120b | 4 |
| glm5.2 | 12 |
| mistral | 4 |

A high unique count with a low consensus rate suggests false positives. A high unique count with a high consensus rate suggests the model found real bugs others missed.

### With-Skill vs Baseline: Skill Impact

How the skill changed each model's review:

**gpt-oss-120b:** Baseline 15 findings (1 CRITICAL) → With-skill 11 findings (6 CRITICAL). Skill found 5 critical bug(s) the baseline missed; baseline found 0 critical bug(s) the skill missed.

**glm5.2:** Baseline 26 findings (2 CRITICAL) → With-skill 21 findings (4 CRITICAL). Skill found 3 critical bug(s) the baseline missed; baseline found 1 critical bug(s) the skill missed.

**mistral:** Baseline 19 findings (2 CRITICAL) → With-skill 10 findings (3 CRITICAL). Skill found 2 critical bug(s) the baseline missed; baseline found 1 critical bug(s) the skill missed.

#### Skill Tradeoff Analysis

The skill narrows reviewer focus toward memory-safety and correctness (Linus's priorities). This filters noise but can also suppress valid findings. Net critical impact per model:

| Model | Skill-Only CRITICAL | Baseline-Only CRITICAL | Net Critical Impact | Total Finding Delta |
|-------|:-------------------:|:----------------------:|:-------------------:|:-------------------:|
| gpt-oss-120b | 5 | 0 | +5 | -4 |
| glm5.2 | 3 | 1 | +2 | -5 |
| mistral | 2 | 1 | +1 | -9 |

**Interpretation:** A positive net critical impact means the skill found real bugs the baseline missed. A negative value means the skill suppressed critical findings the baseline caught — a coverage gap. A large negative total finding delta with neutral critical impact means the skill filtered noise without losing signal.

**Per-model read:**
- **gpt-oss-120b:** Net positive. The skill cut 4 findings and added 5 critical bug(s) the baseline missed.
- **glm5.2:** Net positive. The skill cut 5 findings and added 2 critical bug(s) the baseline missed.
- **mistral:** Net positive. The skill cut 9 findings and added 1 critical bug(s) the baseline missed.

### Trigger Coverage Analysis

Which skill triggers each model fired:

**gpt-oss-120b:** 7 distinct triggers fired, 11 total trigger firings.
  Top triggers: Binary Correctness (3x), All Error‑Handling Paths Must Be Reliable (3x), No Unbounded Resource Allocation Without Bounds (1x)

**glm5.2:** 10 distinct triggers fired, 21 total trigger firings.
  Top triggers: (unmatched) (4x), Fatal assertion or abort used for a recoverable condition (3x), Return value that is ambiguous between success and error (3x)

**mistral:** 9 distinct triggers fired, 10 total trigger firings.
  Top triggers: Validate inputs and preserve invariants (2x), No race conditions in resource management (1x), Avoid exposing internal details in public interfaces (1x)

### Verdict

Based on consensus-confirmed CRITICAL findings, net critical impact (skill-only minus baseline-only), and severity calibration:

| Model | Confirmed CRITICAL | Skill-Only CRITICAL | Baseline-Only CRITICAL | Net Critical | Severity Disagreements | Score |
|-------|:------------------:|:-------------------:|:----------------------:|:-------------:|:----------------------:|:-----:|
| gpt-oss-120b | 4 | 5 | 0 | +5 | 5 | 4 |
| glm5.2 | 3 | 3 | 1 | +2 | 7 | -2 |
| mistral | 2 | 2 | 1 | +1 | 6 | -3 |

**Scoring:** `confirmed_critical + skill_only_critical - baseline_only_critical - severity_disagreements`. All terms are CRITICAL-only for unit consistency. The baseline-only penalty makes coverage gaps visible: a model that suppresses real bugs the baseline caught scores lower, even if it found other bugs the baseline missed.

**Honest read:** 
gpt-oss-120b wins clearly with score 4. 
glm5.2 follows at -2.
 The skill helps differently per model — see the per-model read above for the tradeoff details.
