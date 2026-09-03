---
title: Model Comparison — SmallChat Review
date: 2026-09-03
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
| gpt-oss-120b | 6 | 1 | 1 | Skill adds value |
| glm5.2 | 11 | 0 | 0 | Skill reduces coverage |
| mistral | 22 | 13 | 12 | Skill adds value |

The skill adds the most value for mistral, which gained 12 critical finding(s) exclusive to the with-skill review.

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
| Findings | 6 | 11 | 22 |
| Critical | 1 | 0 | 13 |
| High | 3 | 9 | 3 |
| Medium | 0 | 1 | 3 |
| Low | 2 | 1 | 3 |
| Words | 757 | 1377 | 2254 |

**Key insight:** Finding count is a poor quality signal. The consensus matrix below shows which models caught which bugs — and that is where the real signal lives.

---

## Finding Consensus Matrix

Every finding from all three reviews, mapped to the underlying issue. ✓ = found, ✗ = missed. Severity shown in parentheses.

### chatlib.c

| # | Issue | gpt-oss-120b | glm5.2 | mistral | Consensus |
|---|:---:|:---:|:---:|:---:|
| 1 | Magic backlog value in `listen()` | ✓ (LOW) | ✗ | ✗ | gpt-oss-120b only |
| 2 | Missing `const` qualifier on address parameter | ✓ (LOW) | ✗ | ✗ | gpt-oss-120b only |
| 3 | Memory leak in TCPConnect on non-blocking EINPROGR... | ✗ | ✓ (HIGH) | ✗ | glm5.2 only |
| 4 | TCPConnect does not try alternative addresses on c... | ✗ | ✓ (HIGH) | ✗ | glm5.2 only |
| 5 | Missing cleanup in `acceptClient` | ✗ | ✗ | ✓ (CRITICAL) | mistral only |
| 6 | Inconsistent error handling in `chatMalloc` | ✗ | ✗ | ✓ (HIGH) | mistral only |
| 7 | Magic constant in `createTCPServer` | ✗ | ✗ | ✓ (HIGH) | mistral only |
| 8 | Comment style in `chatlib.c` | ✗ | ✗ | ✓ (LOW) | mistral only |

### chatlib.h

| # | Issue | gpt-oss-120b | glm5.2 | mistral | Consensus |
|---|:---:|:---:|:---:|:---:|
| 9 | Missing `const` qualifier on `TCPConnect` address ... | ✗ | ✓ (MEDIUM) | ✓ (LOW) | 2/3 |
| 10 | Inconsistent naming convention across public API | ✗ | ✓ (LOW) | ✗ | glm5.2 only |
| 11 | Missing `.PHONY` declaration for phony targets | ✗ | ✓ (HIGH) | ✗ | glm5.2 only |
| 12 | Missing header file dependencies in build rules | ✗ | ✓ (HIGH) | ✗ | glm5.2 only |

### smallchat-client.c

| # | Issue | gpt-oss-120b | glm5.2 | mistral | Consensus |
|---|:---:|:---:|:---:|:---:|
| 13 | Potential buffer overflow when appending newline t... | ✓ (HIGH) | ✗ | ✓ (CRITICAL) | 2/3 |
| 14 | — `select()` EINTR treated as fatal exit | ✗ | ✓ (HIGH) | ✓ (MEDIUM) | 2/3 |
| 15 | — `read()` EINTR on socket causes false disconnect... | ✗ | ✓ (HIGH) | ✗ | glm5.2 only |
| 16 | — Unchecked `inputBufferAppend()` return silently ... | ✗ | ✓ (HIGH) | ✗ | glm5.2 only |
| 17 | — stdin EOF causes 100% CPU busy loop | ✗ | ✓ (HIGH) | ✗ | glm5.2 only |
| 18 | — Unchecked `write()` to socket silently loses mes... | ✗ | ✓ (HIGH) | ✗ | glm5.2 only |
| 19 | Unchecked `tcsetattr` in `setRawMode` | ✗ | ✗ | ✓ (CRITICAL) | mistral only |
| 20 | Missing cleanup in `disableRawModeAtExit` | ✗ | ✗ | ✓ (CRITICAL) | mistral only |

### smallchat-server.c

| # | Issue | gpt-oss-120b | glm5.2 | mistral | Consensus |
|---|:---:|:---:|:---:|:---:|
| 21 | Out‑of‑bounds client array indexing | ✓ (CRITICAL) | ✗ | ✗ | gpt-oss-120b only |
| 22 | Missing NUL‑terminator for generated nicknames | ✓ (HIGH) | ✗ | ✓ (CRITICAL) | 2/3 |
| 23 | Improper handling of read errors (EINTR) as discon... | ✓ (HIGH) | ✗ | ✓ (MEDIUM) | 2/3 |
| 24 | Memory leak in client nickname allocation | ✗ | ✗ | ✓ (CRITICAL) | mistral only |
| 25 | Race condition in client list update | ✗ | ✗ | ✓ (CRITICAL) | mistral only |
| 26 | Buffer overflow in nickname handling | ✗ | ✗ | ✓ (CRITICAL) | mistral only |
| 27 | Unchecked read/write in client loop | ✗ | ✗ | ✓ (CRITICAL) | mistral only |
| 28 | Missing cleanup in client loop | ✗ | ✗ | ✓ (CRITICAL) | mistral only |
| 29 | Unsafe use of global `Chat` state | ✗ | ✗ | ✓ (CRITICAL) | mistral only |
| 30 | Missing input validation in `/nick` command | ✗ | ✗ | ✓ (CRITICAL) | mistral only |
| 31 | Unsafe use of `select` with uninitialized `tv` | ✗ | ✗ | ✓ (CRITICAL) | mistral only |
| 32 | Unsafe use of `strchr` without bounds check | ✗ | ✗ | ✓ (HIGH) | mistral only |
| 33 | Magic constant in `SERVER_PORT` | ✗ | ✗ | ✓ (MEDIUM) | mistral only |

### unspecified

| # | Issue | gpt-oss-120b | glm5.2 | mistral | Consensus |
|---|:---:|:---:|:---:|:---:|
| 34 | Missing `Makefile` cleanup rule | ✗ | ✗ | ✓ (LOW) | mistral only |

---

## Severity Disagreement Table

Cases where 2+ models found the same issue but assigned different severities:

| Issue | gpt-oss-120b | glm5.2 | mistral |
|-------|:---:|:---:|:---:|
| Missing `const` qualifier on `TCPConnect... | — | MEDIUM | LOW |
| Potential buffer overflow when appending... | HIGH | — | CRITICAL |
| — `select()` EINTR treated as fatal exit | — | HIGH | MEDIUM |
| Missing NUL‑terminator for generated nic... | HIGH | — | CRITICAL |
| Improper handling of read errors (EINTR)... | HIGH | — | MEDIUM |

---

## Trigger Coverage Comparison

Which skill triggers fired in each review:

| Trigger theme | gpt-oss-120b | glm5.2 | mistral |
|---------------|:---:|:---:|:---:|
| (unmatched) | ✗ | ✓ (2) | ✗ |
| (unmatched) — resource leak on... | ✗ | ✓ (1) | ✗ |
| Breaking existing working setu... | ✗ | ✓ (2) | ✗ |
| Comment that does not match th... | ✗ | ✓ (1) | ✗ |
| Concurrency safety | ✗ | ✗ | ✓ (1) |
| Eliminate hard-coded magic val... | ✗ | ✗ | ✓ (3) |
| Error handling that masks the ... | ✗ | ✓ (1) | ✗ |
| Fatal assertion or crash used ... | ✗ | ✓ (2) | ✗ |
| Function requires caller to pe... | ✗ | ✓ (1) | ✗ |
| Inconsistent naming across sim... | ✗ | ✓ (1) | ✗ |
| Memory-safety and ownership | ✗ | ✗ | ✓ (11) |
| Security-first review | ✗ | ✗ | ✓ (1) |
| Trust at scale must be structu... | ✗ | ✗ | ✓ (1) |
| Use assertions for invariants,... | ✗ | ✗ | ✓ (1) |
| Use clear and consistent names | ✗ | ✗ | ✓ (1) |
| style | ✗ | ✗ | ✓ (3) |
| “Hard‑coded magic numbers, arc... | ✓ (1) | ✗ | ✗ |
| “Missing validation of inputs ... | ✓ (1) | ✗ | ✗ |
| “Missing validation of inputs ... | ✓ (1) | ✗ | ✗ |
| “Missing validation of inputs,... | ✓ (1) | ✗ | ✗ |
| “Naming conventions must serve... | ✓ (1) | ✗ | ✗ |
| “Unnecessary complexity that c... | ✓ (1) | ✗ | ✗ |

---

## With-Skill vs Baseline Comparison

For each model, comparing findings with the skill vs without (baseline):

| Model | Baseline Total | With-Skill Total | Baseline CRITICAL | With-Skill CRITICAL | Critical Overlap | Skill-Only CRITICAL | Baseline-Only CRITICAL | Skill Added Value |
|-------|----------------|------------------|-------------------|---------------------|------------------|---------------------|------------------------|-------------------|
| gpt-oss-120b | 14 | 6 | 1 | 1 | 0 | 1 | 1 | neutral (0 net: 1 found, 1 lost) |
| glm5.2 | 27 | 11 | 4 | 0 | 0 | 0 | 4 | no (-4 net critical: 0 found, 4 lost) |
| mistral | 15 | 22 | 1 | 13 | 1 | 12 | 0 | yes (+12 net critical: 12 found, 0 lost) |

---

## Per-Model Bug Comparison (Baseline vs With-Skill)

Bug-by-bug comparison for each model: which bugs were found by both, only baseline, or only skill.

### gpt-oss-120b

**Same bugs (found in both):**

| Issue | File | Baseline | Skill | Severity changed? |
|-------|------|----------|-------|-------------------|
| Out‑of‑bounds client array indexing | smallchat-server.c | HIGH | CRITICAL | YES: HIGH→CRITICAL |
| Missing NUL‑terminator for generated nicknames | smallchat-server.c | CRITICAL | HIGH | YES: CRITICAL→HIGH |
| Magic backlog value in `listen()` | chatlib.c | LOW | LOW | no |

**Baseline-only (skill missed):**

| Issue | File | Severity | Trigger coverage |
|-------|------|----------|------------------|
| Unchecked partial writes | smallchat-server.c | MEDIUM | unmatched |
| No validation of `/nick` argument length | smallchat-server.c | MEDIUM | unmatched |
| Ignored error from `socketSetNonBlockNoDelay` | smallchat-server.c | LOW | unmatched |
| Misuse of `snprintf` return value for nickname generation | smallchat-server.c | LOW | unmatched |
| Missing handling of input buffer overflow | smallchat-client.c | HIGH | unmatched |
| Terminal may remain in raw mode after abnormal termination | smallchat-client.c | MEDIUM | unmatched |
| Unchecked partial writes to the server socket | smallchat-client.c | MEDIUM | unmatched |
| Lack of argument validation | smallchat-client.c | LOW | unmatched |
| Ignored error from `setRawMode` call | smallchat-client.c | LOW | unmatched |
| Ignored errors from `socketSetNonBlockNoDelay` | chatlib.c | LOW | unmatched |
| Ignored return values from `setsockopt` | chatlib.c | LOW | unmatched |

**Skill-only (skill added):**

| Issue | File | Severity | Trigger |
|-------|------|----------|---------|
| Improper handling of read errors (EINTR) as disconnects | smallchat-server.c | HIGH | “Missing validation of inputs … leads to... |
| Potential buffer overflow when appending newline to nickname... | smallchat-client.c | HIGH | “Missing validation of inputs … leads to... |
| Missing `const` qualifier on address parameter | chatlib.c | LOW | “Naming conventions must serve a clear p... |

### glm5.2

**Same bugs (found in both):**

| Issue | File | Baseline | Skill | Severity changed? |
|-------|------|----------|-------|-------------------|
| Missing `const` qualifier on `TCPConnect` address parameter | chatlib.h | LOW | MEDIUM | YES: LOW→MEDIUM |
| Inconsistent naming convention across public API | chatlib.h | LOW | LOW | no |
| Missing `.PHONY` declaration for phony targets | chatlib.h | LOW | HIGH | YES: LOW→HIGH |
| Missing header file dependencies in build rules | chatlib.h | LOW | HIGH | YES: LOW→HIGH |

**Baseline-only (skill missed):**

| Issue | File | Severity | Trigger coverage |
|-------|------|----------|------------------|
| Unchecked `acceptClient()` return value leads to out-of-boun... | smallchat-server.c | CRITICAL | unmatched |
| No bounds check on file descriptor before indexing `clients[... | smallchat-server.c | CRITICAL | unmatched |
| No `SIGPIPE` handler — server killed when writing to a close... | smallchat-server.c | CRITICAL | unmatched |
| Nickname not null-terminated in `createClient()` | smallchat-server.c | CRITICAL | unmatched |
| `select()` returning `-1` on `EINTR` causes server exit | smallchat-server.c | HIGH | unmatched |
| `read()` on non-blocking socket does not handle `EAGAIN`/`EW... | smallchat-server.c | HIGH | unmatched |
| No input sanitization — messages relayed verbatim to all cli... | smallchat-server.c | HIGH | unmatched |
| `write()` return values are universally ignored | smallchat-server.c | MEDIUM | unmatched |
| No nickname length validation — unbounded allocation | smallchat-server.c | MEDIUM | unmatched |
| `socketSetNonBlockNoDelay()` return value ignored in `create... | smallchat-server.c | MEDIUM | unmatched |
| `MAX_CLIENTS` comment is misleading | smallchat-server.c | LOW | unmatched |
| Partial reads produce fragmented messages | smallchat-server.c | LOW | unmatched |
| `Ctrl+C` (`SIGINT`) leaves terminal in raw mode | smallchat-client.c | HIGH | unmatched |
| No `SIGPIPE` handling — client killed if server closes conne... | smallchat-client.c | HIGH | unmatched |
| `write()` return values not checked | smallchat-client.c | MEDIUM | unmatched |
| `stdin` `EOF` not handled — client runs forever with no inpu... | smallchat-client.c | MEDIUM | unmatched |
| `\e` escape sequence is a non-standard GCC extension | smallchat-client.c | LOW | unmatched |
| Backspace only handles key code 127 | smallchat-client.c | LOW | unmatched |
| `atoi()` does not validate port argument | smallchat-client.c | LOW | unmatched |
| Memory leak in `TCPConnect()` on `EINPROGRESS` | chatlib.c | MEDIUM | unmatched |
| `TCPConnect()` breaks out of address iteration on nonblock s... | chatlib.c | MEDIUM | unmatched |
| No IPv6 support in `createTCPServer()` | chatlib.c | LOW | unmatched |
| `chatRealloc()` leaks original pointer on failure | chatlib.c | LOW | unmatched |

**Skill-only (skill added):**

| Issue | File | Severity | Trigger |
|-------|------|----------|---------|
| — `select()` EINTR treated as fatal exit | smallchat-client.c | HIGH | Fatal assertion or crash used for a reco... |
| — `read()` EINTR on socket causes false disconnection | smallchat-client.c | HIGH | Fatal assertion or crash used for a reco... |
| — Unchecked `inputBufferAppend()` return silently drops newl... | smallchat-client.c | HIGH | Error handling that masks the root cause |
| — stdin EOF causes 100% CPU busy loop | smallchat-client.c | HIGH | (unmatched) |
| — Unchecked `write()` to socket silently loses message data | smallchat-client.c | HIGH | (unmatched) |
| Memory leak in TCPConnect on non-blocking EINPROGRESS return | chatlib.c | HIGH | (unmatched) — resource leak on early ret... |
| TCPConnect does not try alternative addresses on connect fai... | chatlib.c | HIGH | Comment that does not match the actual b... |

### mistral

**Same bugs (found in both):**

| Issue | File | Baseline | Skill | Severity changed? |
|-------|------|----------|-------|-------------------|
| Buffer overflow in nickname handling | smallchat-server.c | MEDIUM | CRITICAL | YES: MEDIUM→CRITICAL |
| Unsafe use of `select` with uninitialized `tv` | smallchat-server.c | LOW | CRITICAL | YES: LOW→CRITICAL |
| Missing cleanup in `acceptClient` | chatlib.c | MEDIUM | CRITICAL | YES: MEDIUM→CRITICAL |
| Inconsistent error handling in `chatMalloc` | chatlib.c | HIGH | HIGH | no |
| Magic constant in `createTCPServer` | chatlib.c | MEDIUM | HIGH | YES: MEDIUM→HIGH |
| Inconsistent use of `assert` | smallchat-server.c | HIGH | MEDIUM | YES: HIGH→MEDIUM |
| Formatting nit in `chatlib.h` | chatlib.h | LOW | LOW | no |
| Missing input validation in `/nick` command | smallchat-server.c | CRITICAL | CRITICAL | no |

**Baseline-only (skill missed):**

| Issue | File | Severity | Trigger coverage |
|-------|------|----------|------------------|
| Finding: Potential buffer overflow in message handling | smallchat-server.c | HIGH | unmatched |
| Finding: Hardcoded limits | smallchat-server.c | MEDIUM | unmatched |
| Finding: Terminal mode not restored on crash | smallchat-client.c | HIGH | unmatched |
| Finding: No input validation | smallchat-client.c | MEDIUM | unmatched |
| Finding: No port range validation | chatlib.c | LOW | unmatched |
| Finding: No compiler warnings for all issues | chatlib.h | LOW | unmatched |
| Finding: No optimization level specified | chatlib.h | LOW | unmatched |

**Skill-only (skill added):**

| Issue | File | Severity | Trigger |
|-------|------|----------|---------|
| Memory leak in client nickname allocation | smallchat-server.c | CRITICAL | Memory-safety and ownership |
| Race condition in client list update | smallchat-server.c | CRITICAL | Concurrency safety |
| Unchecked read/write in client loop | smallchat-server.c | CRITICAL | Memory-safety and ownership |
| Missing cleanup in client loop | smallchat-server.c | CRITICAL | Memory-safety and ownership |
| Hard-coded magic value in client table size | smallchat-server.c | CRITICAL | Eliminate hard-coded magic values |
| Unsafe use of global `Chat` state | smallchat-server.c | CRITICAL | Trust at scale must be structured |
| Buffer overflow in `inputBufferFeedChar` | smallchat-client.c | CRITICAL | Memory-safety and ownership |
| Unchecked `tcsetattr` in `setRawMode` | smallchat-client.c | CRITICAL | Memory-safety and ownership |
| Missing cleanup in `disableRawModeAtExit` | smallchat-client.c | CRITICAL | Memory-safety and ownership |
| Unsafe use of `strchr` without bounds check | smallchat-server.c | HIGH | Memory-safety and ownership |
| Magic constant in `SERVER_PORT` | smallchat-server.c | MEDIUM | Eliminate hard-coded magic values |
| Unclear naming in `inputBufferClear` | smallchat-client.c | MEDIUM | Use clear and consistent names |
| Comment style in `chatlib.c` | chatlib.c | LOW | style |
| Missing `Makefile` cleanup rule | — | LOW | style |

---

## Focus Metrics

Core-vs-trivia breakdown: % of findings that are CORE (correctness/memory-safety/error-handling) vs TRIVIA (style/build/docs).

| Model | With-Skill CORE% | Baseline-Only CORE% | Focus Status |
|-------|:----------------:|:-------------------:|:-------------|
| gpt-oss-120b | 83.3% | 100.0% | ✅ focused |
| glm5.2 | 100.0% | 100.0% | ✅ focused |
| mistral | 86.4% | 100.0% | ✅ focused |

**Gate rules:** `FOCUS DRIFT` when with-skill CORE% < 50%; `CRITICAL FOCUS FAILURE` when baseline-only contains any CRITICAL while skill-only is majority trivia. **Note:** `unmatched` means no trigger-text overlap, not 'outside the skill's domain'.

---

## Qualitative Analysis

### Consensus-Based Accuracy

Findings confirmed by 2+ models are treated as real bugs. Findings reported by only one model are unverified (could be real or false positive).

| Model | Total Findings | Confirmed (2+ models) | Unverified (1 model only) | Consensus Rate |
|-------|:--------------:|:---------------------:|:--------------------------:|:--------------:|
| gpt-oss-120b | 6 | 3 | 3 | 50% |
| glm5.2 | 11 | 2 | 9 | 18% |
| mistral | 22 | 5 | 17 | 23% |

### Severity Calibration

Cases where 2+ models found the same issue but assigned different severities:

| Issue | gpt-oss-120b | glm5.2 | mistral |
|-------|:---:|:---:|:---:|
| Missing `const` qualifier on `TCPConnect... | — | MEDIUM | LOW |
| Potential buffer overflow when appending... | HIGH | — | CRITICAL |
| — `select()` EINTR treated as fatal exit | — | HIGH | MEDIUM |
| Missing NUL‑terminator for generated nic... | HIGH | — | CRITICAL |
| Improper handling of read errors (EINTR)... | HIGH | — | MEDIUM |

Total severity disagreements: 5. Lower is better — it means the model's severity assessment aligns with the consensus.

### Unique Findings (Single-Model Discoveries)

Findings reported by only one model. These represent either unique insight or false positives:

| Model | Unique Findings |
|-------|:--------------:|
| gpt-oss-120b | 3 |
| glm5.2 | 9 |
| mistral | 17 |

A high unique count with a low consensus rate suggests false positives. A high unique count with a high consensus rate suggests the model found real bugs others missed.

### With-Skill vs Baseline: Skill Impact

How the skill changed each model's review:

**gpt-oss-120b:** Baseline 14 findings (1 CRITICAL) → With-skill 6 findings (1 CRITICAL). Skill found 1 critical bug(s) the baseline missed; baseline found 1 critical bug(s) the skill missed.

**glm5.2:** Baseline 27 findings (4 CRITICAL) → With-skill 11 findings (0 CRITICAL). Skill found 0 critical bug(s) the baseline missed; baseline found 4 critical bug(s) the skill missed.

**mistral:** Baseline 15 findings (1 CRITICAL) → With-skill 22 findings (13 CRITICAL). Skill found 12 critical bug(s) the baseline missed; baseline found 0 critical bug(s) the skill missed.

#### Skill Tradeoff Analysis

The skill narrows reviewer focus toward memory-safety and correctness (Linus's priorities). This filters noise but can also suppress valid findings. Net critical impact per model:

| Model | Skill-Only CRITICAL | Baseline-Only CRITICAL | Net Critical Impact | Total Finding Delta |
|-------|:-------------------:|:----------------------:|:-------------------:|:-------------------:|
| gpt-oss-120b | 1 | 1 | 0 | -8 |
| glm5.2 | 0 | 4 | -4 | -16 |
| mistral | 12 | 0 | +12 | +7 |

**Interpretation:** A positive net critical impact means the skill found real bugs the baseline missed. A negative value means the skill suppressed critical findings the baseline caught — a coverage gap. A large negative total finding delta with neutral critical impact means the skill filtered noise without losing signal.

**Per-model read:**
- **gpt-oss-120b:** Neutral on criticals. The skill filtered noise (cut 8 findings) without losing critical coverage.
- **glm5.2:** Net negative on critical coverage. The skill cut 16 findings and suppressed 4 critical(s) the baseline caught, while only adding 0 new critical. The skill narrowed focus too aggressively — the 4 lost critical(s) are a real coverage gap worth investigating.
- **mistral:** Net positive. The skill added findings and added 12 critical bug(s) the baseline missed.

### Trigger Coverage Analysis

Which skill triggers each model fired:

**gpt-oss-120b:** 6 distinct triggers fired, 6 total trigger firings.
  Top triggers: “Hard‑coded magic numbers, architecture‑specific hacks, or ad‑hoc special‑case branches …” (1x), “Missing validation of inputs, allocation failures, or reference‑count checks before use.” (1x), “Missing validation of inputs … leads to crashes or subtle race conditions.” (1x)

**glm5.2:** 8 distinct triggers fired, 11 total trigger firings.
  Top triggers: Fatal assertion or crash used for a recoverable condition (2x), (unmatched) (2x), Breaking existing working setups (2x)

**mistral:** 8 distinct triggers fired, 22 total trigger firings.
  Top triggers: Memory-safety and ownership (11x), Eliminate hard-coded magic values (3x), style (3x)

### Verdict

Based on consensus-confirmed CRITICAL findings, net critical impact (skill-only minus baseline-only), and severity calibration:

| Model | Confirmed CRITICAL | Skill-Only CRITICAL | Baseline-Only CRITICAL | Net Critical | Severity Disagreements | Score |
|-------|:------------------:|:-------------------:|:----------------------:|:-------------:|:----------------------:|:-----:|
| gpt-oss-120b | 0 | 1 | 1 | 0 | 3 | -3 |
| glm5.2 | 0 | 0 | 4 | -4 | 2 | -6 |
| mistral | 2 | 12 | 0 | +12 | 5 | 9 |

**Scoring:** `confirmed_critical + skill_only_critical - baseline_only_critical - severity_disagreements`. All terms are CRITICAL-only for unit consistency. The baseline-only penalty makes coverage gaps visible: a model that suppresses real bugs the baseline caught scores lower, even if it found other bugs the baseline missed.

**Honest read:** 
mistral wins clearly with score 9. 
gpt-oss-120b follows at -3.
 The skill helps differently per model — see the per-model read above for the tradeoff details.

---

## Ground-Truth Benchmark

Comparison against the ground-truth benchmark dataset (43 records in `data/benchmark.jsonl`).

Metrics computed by matching model findings to benchmark records by file and line number (±10 lines tolerance).

### Per-Model Benchmark Metrics

| Model | Precision | Recall | F1 | Hits | Misses | Severity Match Rate |
|-------|-----------|--------|------|------|--------|---------------------|
| gpt-oss-120b | 83.3% | 11.6% | 20.4% | 5 | 38 | 60.0% |
| glm5.2 | 9.1% | 2.3% | 3.7% | 1 | 42 | 100.0% |
| mistral | 36.4% | 18.6% | 24.6% | 8 | 35 | 37.5% |

### Missed Benchmark Findings

Benchmark records not found by any model (skill or baseline). These represent gaps in review coverage:

**Makefile:**

- SC-033 (severity: nitpick, trigger: Missing reference-count on shared object...)
- SC-034 (severity: nitpick, trigger: Commit message missing rationale...)
- SC-035 (severity: nitpick, trigger: Out-of-tree code dictating core changes...)

**chat-common.c:**

- SC-043 (severity: request-changes, trigger: Premature abstraction or helper function for single-use logi...)

**chatlib.c:**

- SC-019 (severity: request-changes, trigger: Error-handling & return conventions - missing error handling...)
- SC-020 (severity: request-changes, trigger: Error-handling & return conventions - missing error handling...)
- SC-021 (severity: nitpick, trigger: Premature abstraction or helper function for single-use logi...)
- SC-022 (severity: request-changes, trigger: Breaking documented behavior or public interface without mig...)
- SC-023 (severity: nitpick, trigger: Returning a pointer to a stack-allocated buffer...)
- SC-028 (severity: nitpick, trigger: Comment that does not match code...)

**chatlib.h:**

- SC-029 (severity: nitpick, trigger: Unbounded format-string or buffer-size mismatch...)
- SC-030 (severity: nitpick, trigger: Missing reference-count on shared object...)
- SC-036 (severity: nitpick, trigger: Out-of-tree code dictating core changes...)

**inputbuffer.c:**

- SC-039 (severity: request-changes, trigger: Error-handling & return conventions - missing error handling...)
- SC-040 (severity: nitpick, trigger: Overly complex control flow...)

**smallchat-client.c:**

- SC-014 (severity: request-changes, trigger: Error-handling & return conventions - missing error handling...)
- SC-015 (severity: request-changes, trigger: Error-handling & return conventions - missing error handling...)
- SC-016 (severity: request-changes, trigger: Error-handling & return conventions - missing error handling...)
- SC-017 (severity: nitpick, trigger: Special-case handling for rare or edge cases...)
- SC-018 (severity: nitpick, trigger: Inaccurate or misleading comments...)
- SC-026 (severity: request-changes, trigger: Unsynchronized access to shared mutable state...)
- SC-027 (severity: nitpick, trigger: Mixed error-code conventions...)
- SC-032 (severity: nitpick, trigger: Skipping input validation on a boundary crossing...)
- SC-037 (severity: nitpick, trigger: Obscure or non-descriptive naming...)

**smallchat-server.c:**

- SC-001 (severity: reject, trigger: Fatal assertion used for a recoverable error...)
- SC-002 (severity: reject, trigger: Unbounded format-string or buffer-size mismatch (applied to ...)
- SC-003 (severity: request-changes, trigger: Error-handling & return conventions - missing error handling...)
- SC-004 (severity: request-changes, trigger: Error-handling & return conventions - missing error handling...)
- SC-005 (severity: request-changes, trigger: Unbounded format-string or buffer-size mismatch (string hand...)
- SC-006 (severity: request-changes, trigger: Error-handling & return conventions - missing error handling...)
- SC-007 (severity: nitpick, trigger: Hard-coded magic constants without documentation...)
- SC-008 (severity: reject, trigger: Security is ordinary bug-fixing...)
- SC-009 (severity: reject, trigger: A fatal assertion, panic, or abort is used for a condition t...)
- SC-010 (severity: reject, trigger: Code allocates memory but later cannot determine how it was ...)
- SC-011 (severity: request-changes, trigger: A patch adds support for sizes, ranges, options, or architec...)
- SC-012 (severity: request-changes, trigger: Code uses an algorithm or data structure whose cost grows in...)
- SC-013 (severity: nitpick, trigger: An error message that misdescribes the actual condition...)
- SC-024 (severity: reject, trigger: Unsynchronized access to shared mutable state...)
- SC-025 (severity: request-changes, trigger: Error-handling & return conventions - missing error handling...)
- SC-031 (severity: request-changes, trigger: Duplicating logic instead of factoring into shared helper...)
- SC-038 (severity: nitpick, trigger: Inaccurate or misleading comments...)

**terminal.c:**

- SC-041 (severity: request-changes, trigger: Special-case handling for rare or edge cases...)
- SC-042 (severity: nitpick, trigger: Hard-coded magic constants without documentation...)

