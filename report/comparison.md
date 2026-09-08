---
title: Model Comparison — SmallChat Review
date: 2026-09-07
codebase: antirez/smallchat
models: gpt-oss-120b, glm5.2, mistral, qwen3.8-27b
skill: linus-torvalds-skill (language-agnostic)
method: static review, skill triggers applied per source file
---

# Model Comparison — SmallChat Review

## Stakeholder Scorecard

Quick summary for non-technical readers:

| Model | Total Findings | Critical Findings | Skill-Only Critical | Verdict |
|-------|---------------|-------------------|---------------------|---------|
| gpt-oss-120b | 0 | 0 | 0 | No change |
| glm5.2 | 7 | 2 | 0 | Skill reduces coverage |
| mistral | 22 | 9 | 9 | Skill adds value |
| qwen3.8-27b | 13 | 3 | 3 | Skill adds value |

The skill adds the most value for mistral, which gained 9 critical finding(s) exclusive to the with-skill review.

## Skill Generation Per Model

Skills are NOT identical — each variant is distilled from the same 350 patterns but with model-specific prompt calibration, token budgets, and execution mode.

| Model | Skill file | Distill mode | Token budget | Wall-clock timeout | Severity calibration |
|-------|------------|--------------|--------------|-------------------|---------------------|
| gpt-oss-120b | `linus-torvalds-skill/SKILL.md` | two-stage (14 categories + synthesis) | 16000 | 120s (profile.default) | balanced |
| glm5.2 | `linus-torvalds-skill/SKILL-GLM.md` | single-call (profile.default) | 16000 | 600s / 1800s (profile.slow) | downgrade ONLY style/docs borderline, never correctness/error-handling |
| mistral-small-4-119b | `linus-torvalds-skill/SKILL-Mistral.md` | two-stage | 16000 | 120s (profile.default) | under-rates → upgrade borderline |
| qwen3.8-27b | `linus-torvalds-skill/SKILL-Qwen.md` | single-call (profile.reasoning) | 16000 | 600s / 2400s (profile.slow) | none measured |

**Source:** `src/torvalds_skill/profiles.py` for per-model `max_tokens`, `timeout`, and `distill_mode` settings. Regenerate per `docs/CONTRIBUTING.md`.

This explains why glm5.2 previously lost 3 criticals (over-filtering style) and why trigger coverage differs across models.

4 models reviewed the same C codebase (antirez/smallchat, ~706 LOC) using the same language-agnostic Linus Torvalds skill. This document cross-references their findings at the issue level — not just counts — to measure consensus, accuracy, and severity calibration.

## Metrics Summary

| Metric | gpt-oss-120b | glm5.2 | mistral | qwen3.8-27b |
|--------|:---:|:---:|:---:|:---:|
| Findings | 0 | 7 | 22 | 13 |
| Critical | 0 | 2 | 9 | 3 |
| High | 0 | 4 | 12 | 6 |
| Medium | 0 | 0 | 1 | 2 |
| Low | 0 | 1 | 0 | 2 |
| Words | 3 | 1455 | 3572 | 6657 |

**Key insight:** Finding count is a poor quality signal. The consensus matrix below shows which models caught which bugs — and that is where the real signal lives.

---

## Finding Consensus Matrix

Every finding from all three reviews, mapped to the underlying issue. ✓ = found, ✗ = missed. Severity shown in parentheses.

### chatlib.c

| # | Issue | gpt-oss-120b | glm5.2 | mistral | qwen3.8-27b | Consensus |
|---|:---:|:---:|:---:|:---:|:---:|
| 1 | Memory leak in TCPConnect on EINPROGRESS return pa... | ✗ | ✓ (HIGH) | ✓ (HIGH) | ✗ | — |
| 2 | Memory leak in TCPConnect on EINPROGRESS return pa... | ✗ | ✓ (HIGH) | ✗ | ✓ (HIGH) | — |
| 3 | Fatal exit on out-of-memory in chatMalloc and chat... | ✗ | ✓ (HIGH) | ✓ (CRITICAL) | ✗ | — |
| 4 | Finding: Unchecked error in createTCPServer | ✗ | ✗ | ✓ (HIGH) | ✗ | mistral only |
| 5 | Finding: Missing error handling in acceptClient | ✗ | ✗ | ✓ (HIGH) | ✗ | mistral only |
| 6 | Terminal raw mode is not restored on Ctrl-C | ✗ | ✗ | ✗ | ✓ (HIGH) | qwen3.8-27b only |
| 7 | Finding: Silent crash on malloc failure in chatMal... | ✗ | ✗ | ✓ (CRITICAL) | ✓ (HIGH) | — |

### chatlib.h

| # | Issue | gpt-oss-120b | glm5.2 | mistral | qwen3.8-27b | Consensus |
|---|:---:|:---:|:---:|:---:|:---:|
| 8 | Non-const `addr` parameter permits modification of... | ✗ | ✓ (HIGH) | ✓ (HIGH) | ✗ | — |
| 9 | Non-const `addr` parameter permits modification of... | ✗ | ✓ (HIGH) | ✗ | ✓ (MEDIUM) | — |
| 10 | Missing header file prerequisites | ✗ | ✓ (LOW) | ✓ (HIGH) | ✗ | — |
| 11 | Missing header file prerequisites | ✗ | ✓ (LOW) | ✗ | ✓ (LOW) | — |
| 12 | Missing CFLAGS for hardening and diagnostics | ✗ | ✗ | ✓ (HIGH) | ✓ (MEDIUM) | — |
| 13 | Missing `.PHONY` declarations for non-file targets | ✗ | ✗ | ✓ (MEDIUM) | ✓ (LOW) | — |
| 14 | chatMalloc/chatRealloc abort the process on alloca... | ✗ | ✗ | ✗ | ✓ (HIGH) | qwen3.8-27b only |

### smallchat-client.c

| # | Issue | gpt-oss-120b | glm5.2 | mistral | qwen3.8-27b | Consensus |
|---|:---:|:---:|:---:|:---:|:---:|
| 15 | Finding: Unchecked error return in critical path | ✗ | ✗ | ✓ (CRITICAL) | ✗ | mistral only |
| 16 | Finding: Silent corruption of terminal state | ✗ | ✗ | ✓ (CRITICAL) | ✗ | mistral only |
| 17 | Finding: Resource leak on error | ✗ | ✗ | ✓ (HIGH) | ✗ | mistral only |
| 18 | Unchecked FD_SET can write out of bounds | ✗ | ✗ | ✗ | ✓ (CRITICAL) | qwen3.8-27b only |

### smallchat-server.c

| # | Issue | gpt-oss-120b | glm5.2 | mistral | qwen3.8-27b | Consensus |
|---|:---:|:---:|:---:|:---:|:---:|
| 19 | Unchecked `acceptClient` return value causes out-o... | ✗ | ✓ (CRITICAL) | ✓ (CRITICAL) | ✗ | — |
| 20 | Unchecked `acceptClient` return value causes out-o... | ✗ | ✓ (CRITICAL) | ✗ | ✓ (CRITICAL) | — |
| 21 | No bounds check on file descriptor before indexing... | ✗ | ✓ (CRITICAL) | ✓ (HIGH) | ✗ | — |
| 22 | `snprintf` return value used as `memcpy` length wi... | ✗ | ✓ (HIGH) | ✗ | ✓ (HIGH) | — |
| 23 | Resource Leak in `createClient` | ✗ | ✗ | ✓ (CRITICAL) | ✗ | mistral only |
| 24 | Buffer Overflow in `sendMsgToAllClientsBut` | ✗ | ✗ | ✓ (CRITICAL) | ✗ | mistral only |
| 25 | Unchecked `read` in Main Loop | ✗ | ✗ | ✓ (CRITICAL) | ✗ | mistral only |
| 26 | Missing Error Handling in `initChat` | ✗ | ✗ | ✓ (CRITICAL) | ✗ | mistral only |
| 27 | Silent Corruption in Nickname Handling | ✗ | ✗ | ✓ (CRITICAL) | ✗ | mistral only |
| 28 | Missing Client Input Validation | ✗ | ✗ | ✓ (HIGH) | ✗ | mistral only |
| 29 | Missing Logging for Critical Errors | ✗ | ✗ | ✓ (HIGH) | ✗ | mistral only |
| 30 | Missing Message Framing | ✗ | ✗ | ✓ (HIGH) | ✗ | mistral only |
| 31 | Missing Non-Blocking I/O for Client Sockets | ✗ | ✗ | ✓ (HIGH) | ✗ | mistral only |
| 32 | Ignored write() return values allow SIGPIPE crash ... | ✗ | ✗ | ✗ | ✓ (CRITICAL) | qwen3.8-27b only |
| 33 | assert() used for a runtime state check | ✗ | ✗ | ✗ | ✓ (HIGH) | qwen3.8-27b only |
| 34 | select() fd_set usage does not validate FD_SETSIZE... | ✗ | ✗ | ✗ | ✓ (HIGH) | qwen3.8-27b only |
| 35 | Unchecked `acceptClient` return value causes out-o... | ✗ | ✓ (CRITICAL) | ✗ | ✓ (CRITICAL) | — |

---

## Severity Disagreement Table

Cases where 2+ models found the same issue but assigned different severities:

| Issue | gpt-oss-120b | glm5.2 | mistral | qwen3.8-27b |
|-------|:---:|:---:|:---:|:---:|
| Fatal exit on out-of-memory in chatMallo... | — | HIGH | CRITICAL | — |
| Non-const `addr` parameter permits modif... | — | HIGH | — | MEDIUM |
| Missing header file prerequisites | — | LOW | HIGH | — |
| Missing CFLAGS for hardening and diagnos... | — | — | HIGH | MEDIUM |
| Missing `.PHONY` declarations for non-fi... | — | — | MEDIUM | LOW |
| No bounds check on file descriptor befor... | — | CRITICAL | HIGH | — |
| Finding: Silent crash on malloc failure ... | — | — | CRITICAL | HIGH |

---

## Trigger Coverage Comparison

Which skill triggers fired in each review:

| Trigger theme | gpt-oss-120b | glm5.2 | mistral | qwen3.8-27b |
|---------------|:---:|:---:|:---:|:---:|
| (the trigger from the skill th... | ✗ | ✗ | ✗ | ✓ (1) |
| (unmatched — build correctness... | ✗ | ✓ (1) | ✗ | ✗ |
| (unmatched) | ✗ | ✗ | ✗ | ✓ (4) |
| Code provides false or mislead... | ✗ | ✓ (1) | ✗ | ✗ |
| Crash or panic in a path that ... | ✗ | ✗ | ✓ (3) | ✗ |
| Data race with observable side... | ✗ | ✗ | ✓ (2) | ✗ |
| Fatal abort used for resource ... | ✗ | ✓ (1) | ✗ | ✗ |
| Interface design that makes co... | ✗ | ✓ (1) | ✗ | ✗ |
| Memory safety — out-of-bounds ... | ✗ | ✓ (1) | ✗ | ✗ |
| Memory safety — out-of-bounds ... | ✗ | ✓ (1) | ✗ | ✗ |
| Missing `.PHONY` declarations ... | ✗ | ✗ | ✓ (1) | ✗ |
| Missing compiler flags for sec... | ✗ | ✗ | ✓ (1) | ✗ |
| Never-Block on Build Trivia: s... | ✗ | ✗ | ✗ | ✓ (1) |
| Operation produces wrong resul... | ✗ | ✗ | ✓ (3) | ✗ |
| Public API that exposes intern... | ✗ | ✗ | ✓ (1) | ✗ |
| Resource leak in a critical pa... | ✗ | ✗ | ✓ (1) | ✗ |
| Resource leak — function retur... | ✗ | ✓ (1) | ✗ | ✗ |
| Silent corruption of data or s... | ✗ | ✗ | ✓ (5) | ✗ |
| Theme 11 – Memory-Safety and O... | ✗ | ✗ | ✗ | ✓ (1) |
| Theme 11 – Memory-Safety and O... | ✗ | ✗ | ✗ | ✓ (1) |
| Theme 11 – Memory-Safety and O... | ✗ | ✗ | ✗ | ✓ (1) |
| Theme 2 – Fatal Assertions for... | ✗ | ✗ | ✗ | ✓ (1) |
| Theme 2 – Fatal Assertions for... | ✗ | ✗ | ✗ | ✓ (1) |
| Theme 5 – Consistent Error-Cod... | ✗ | ✗ | ✗ | ✓ (1) |
| Unchecked error return in a cr... | ✗ | ✗ | ✓ (5) | ✗ |

---

## With-Skill vs Baseline Comparison

For each model, comparing findings with the skill vs without (baseline):

| Model | Baseline Total | With-Skill Total | Baseline CRITICAL | With-Skill CRITICAL | Critical Overlap | Skill-Only CRITICAL | Baseline-Only CRITICAL | Skill Added Value |
|-------|----------------|------------------|-------------------|---------------------|------------------|---------------------|------------------------|-------------------|
| gpt-oss-120b | 0 | 0 | 0 | 0 | 0 | 0 | 0 | neutral (0 net: 0 found, 0 lost) |
| glm5.2 | 12 | 7 | 4 | 2 | 2 | 0 | 2 | no (-2 net critical: 0 found, 2 lost) |
| mistral | 15 | 22 | 0 | 9 | 0 | 9 | 0 | yes (+9 net critical: 9 found, 0 lost) |
| qwen3.8-27b | 1 | 13 | 1 | 3 | 0 | 3 | 1 | yes (+2 net critical: 3 found, 1 lost) |

---

## Per-Model Bug Comparison (Baseline vs With-Skill)

Bug-by-bug comparison for each model: which bugs were found by both, only baseline, or only skill.

### gpt-oss-120b

**Same bugs (found in both):**

*None.*

**Baseline-only (skill missed):**

*None.*

**Skill-only (skill added):**

*None.*

### glm5.2

**Same bugs (found in both):**

| Issue | File | Baseline | Skill | Severity changed? |
|-------|------|----------|-------|-------------------|
| Unchecked `acceptClient` return value causes out-of-bounds a... | smallchat-server.c | CRITICAL | CRITICAL | no |
| No bounds check on file descriptor before indexing `clients[... | smallchat-server.c | CRITICAL | CRITICAL | no |
| Non-const `addr` parameter permits modification of caller's ... | chatlib.h | LOW | HIGH | YES: LOW→HIGH |
| Missing header file prerequisites | chatlib.h | LOW | LOW | no |

**Baseline-only (skill missed):**

| Issue | File | Severity | Trigger coverage |
|-------|------|----------|------------------|
| Missing null terminator on client nickname in `createClient` | smallchat-server.c | CRITICAL | Missing docstring or header comment for exported s... |
| No bounds check on file descriptor against `MAX_CLIENTS` in ... | smallchat-server.c | CRITICAL | Removal of a safety check for speed. |
| `select()` exits the server on EINTR | smallchat-server.c | HIGH | unmatched |
| `FD_SET` called without `FD_SETSIZE` bounds check | smallchat-server.c | HIGH | Removal of a safety check for speed. |
| No SIGPIPE handling — client killed on write to closed socke... | smallchat-client.c | HIGH | Missing error-handling after a call that can fail. |
| `select()` exits the client on EINTR | smallchat-client.c | HIGH | unmatched |
| `TCPConnect` leaks `addrinfo` on EINPROGRESS early return | chatlib.c | MEDIUM | Functions that sometimes block and sometimes retur... |
| `acceptClient` populates `sockaddr_in` but never uses it | chatlib.c | LOW | unmatched |

**Skill-only (skill added):**

| Issue | File | Severity | Trigger |
|-------|------|----------|---------|
| `snprintf` return value used as `memcpy` length without trun... | smallchat-server.c | HIGH | Memory safety — out-of-bounds read from ... |
| Memory leak in TCPConnect on EINPROGRESS return path | chatlib.c | HIGH | Resource leak — function returns without... |
| Fatal exit on out-of-memory in chatMalloc and chatRealloc | chatlib.c | HIGH | Fatal abort used for resource exhaustion... |

### mistral

**Same bugs (found in both):**

| Issue | File | Baseline | Skill | Severity changed? |
|-------|------|----------|-------|-------------------|
| Buffer Overflow in `sendMsgToAllClientsBut` | smallchat-server.c | HIGH | CRITICAL | YES: HIGH→CRITICAL |
| Missing Client Input Validation | smallchat-server.c | HIGH | HIGH | no |

**Baseline-only (skill missed):**

| Issue | File | Severity | Trigger coverage |
|-------|------|----------|------------------|
| Memory Leak in Client Disconnection | smallchat-server.c | HIGH | Reads/writes to the same variable from multiple th... |
| Resource Leak in Error Paths | chatlib.c | HIGH | Allocation → immediate use without error check. |
| Unchecked System Call | smallchat-server.c | HIGH | No sanitisation before file write, network send, o... |
| Uninitialized Memory Access | smallchat-server.c | HIGH | Reads/writes to the same variable from multiple th... |
| Race Condition in Client Management | smallchat-server.c | HIGH | unmatched |
| Missing Input Validation | smallchat-server.c | HIGH | Missing docstring or header comment for exported s... |
| Unchecked read() in Client | smallchat-client.c | HIGH | unmatched |
| Buffer Overflow in Client Input | smallchat-client.c | HIGH | Calls to a panic-style routine on invalid input. |
| Missing Cleanup in Client | smallchat-client.c | HIGH | Missing docstring or header comment for exported s... |
| Inefficient Client Nickname Handling | smallchat-server.c | HIGH | Missing error-handling after a call that can fail. |
| Missing Error Handling in TCPConnect() | chatlib.c | MEDIUM | Missing error-handling after a call that can fail. |
| Magic Numbers | smallchat-server.c | MEDIUM | unmatched |
| Redundant Code in freeClient() | smallchat-server.c | LOW | Code that treats a hash as proof of authenticity. |

**Skill-only (skill added):**

| Issue | File | Severity | Trigger |
|-------|------|----------|---------|
| Resource Leak in `createClient` | smallchat-server.c | CRITICAL | Unchecked error return in a critical pat... |
| Unchecked `read` in Main Loop | smallchat-server.c | CRITICAL | Unchecked error return in a critical pat... |
| Missing Error Handling in `initChat` | smallchat-server.c | CRITICAL | Crash or panic in a path that should han... |
| Race Condition in `freeClient` | smallchat-server.c | CRITICAL | Data race with observable side effects |
| Silent Corruption in Nickname Handling | smallchat-server.c | CRITICAL | Silent corruption of data or state |
| Missing Logging for Critical Errors | smallchat-server.c | HIGH | Silent corruption of data or state |
| Missing Thread Safety in Global State | smallchat-server.c | HIGH | Data race with observable side effects |
| Missing Message Framing | smallchat-server.c | HIGH | Operation produces wrong results for val... |
| Missing Non-Blocking I/O for Client Sockets | smallchat-server.c | HIGH | Crash or panic in a path that should han... |
| Finding: Unchecked error return in critical path | smallchat-client.c | CRITICAL | Unchecked error return in a critical pat... |
| Finding: Silent corruption of terminal state | smallchat-client.c | CRITICAL | Silent corruption of data or state |
| Finding: Resource leak on error | smallchat-client.c | HIGH | Resource leak in a critical path |
| Finding: Silent crash on malloc failure in chatMalloc/chatRe... | chatlib.c | CRITICAL | Silent corruption of data or state |
| Finding: Resource leak in TCPConnect on partial failure | chatlib.c | HIGH | Silent corruption of data or state |
| Finding: Unchecked error in createTCPServer | chatlib.c | HIGH | Unchecked error return in a critical pat... |
| Finding: Missing error handling in acceptClient | chatlib.c | HIGH | Crash or panic in a path that should han... |
| Missing error handling for system calls | chatlib.h | HIGH | Unchecked error return in a critical pat... |
| Leaky interface exposing internal state | chatlib.h | HIGH | Public API that exposes internal impleme... |
| Missing CFLAGS for hardening and diagnostics | chatlib.h | HIGH | Missing compiler flags for security and ... |
| Missing `.PHONY` declarations for non-file targets | chatlib.h | MEDIUM | Missing `.PHONY` declarations for non-fi... |

### qwen3.8-27b

**Same bugs (found in both):**

| Issue | File | Baseline | Skill | Severity changed? |
|-------|------|----------|-------|-------------------|
| select() fd_set usage does not validate FD_SETSIZE limits | smallchat-server.c | CRITICAL | HIGH | YES: CRITICAL→HIGH |

**Baseline-only (skill missed):**

*None.*

**Skill-only (skill added):**

| Issue | File | Severity | Trigger |
|-------|------|----------|---------|
| Out-of-bounds client array access from unvalidated file desc... | smallchat-server.c | CRITICAL | Theme 11 – Memory-Safety and Ownership |
| Ignored write() return values allow SIGPIPE crash and silent... | smallchat-server.c | CRITICAL | Theme 2 – Fatal Assertions for Recoverab... |
| Transient non-blocking read errors are treated as client dis... | smallchat-server.c | HIGH | Theme 5 – Consistent Error-Code Conventi... |
| assert() used for a runtime state check | smallchat-server.c | HIGH | Theme 2 – Fatal Assertions for Recoverab... |
| Unchecked FD_SET can write out of bounds | smallchat-client.c | CRITICAL | Theme 11 – Memory-Safety and Ownership (... |
| Terminal raw mode is not restored on Ctrl-C | chatlib.c | HIGH | — |
| TCPConnect leaks addrinfo on EINPROGRESS | chatlib.c | HIGH | Theme 11 – Memory-Safety and Ownership: ... |
| chatMalloc/chatRealloc abort the process on allocation failu... | chatlib.h | HIGH | (the trigger from the skill that fired) |
| Missing `<stddef.h>` for `size_t` | chatlib.h | MEDIUM | (unmatched) |
| `TCPConnect` should take `const char *addr` | chatlib.h | LOW | (unmatched) |
| Missing header dependency can leave stale binaries | chatlib.h | MEDIUM | (unmatched) |
| CFLAGS assignment overrides environment-provided flags | chatlib.h | LOW | Never-Block on Build Trivia: simple `CFL... |

---

## Focus Metrics

Core-vs-trivia breakdown: % of findings that are CORE (correctness/memory-safety/error-handling) vs TRIVIA (style/build/docs).

| Model | With-Skill CORE% | Baseline-Only CORE% | Focus Status |
|-------|:----------------:|:-------------------:|:-------------|
| gpt-oss-120b | 0.0% | 0.0% | ⚠️ FOCUS DRIFT |
| glm5.2 | 100.0% | 100.0% | ✅ focused |
| mistral | 100.0% | 100.0% | ✅ focused |
| qwen3.8-27b | 92.3% | 0.0% | ✅ focused |

**Gate rules:** `FOCUS DRIFT` when with-skill CORE% < 50%; `CRITICAL FOCUS FAILURE` when baseline-only contains any CRITICAL while skill-only is majority trivia. **Note:** `unmatched` means no trigger-text overlap, not 'outside the skill's domain'.

---

## Qualitative Analysis

### Consensus-Based Accuracy

Findings confirmed by 2+ models are treated as real bugs. Findings reported by only one model are unverified (could be real or false positive).

| Model | Total Findings | Confirmed (2+ models) | Unverified (1 model only) | Consensus Rate |
|-------|:--------------:|:---------------------:|:--------------------------:|:--------------:|
| gpt-oss-120b | 0 | 0 | 0 | N/A |
| glm5.2 | 12 | 12 | 0 | 100% |
| mistral | 23 | 9 | 14 | 39% |
| qwen3.8-27b | 15 | 9 | 6 | 60% |

### Severity Calibration

Cases where 2+ models found the same issue but assigned different severities:

| Issue | gpt-oss-120b | glm5.2 | mistral | qwen3.8-27b |
|-------|:---:|:---:|:---:|:---:|
| Fatal exit on out-of-memory in chatMallo... | — | HIGH | CRITICAL | — |
| Non-const `addr` parameter permits modif... | — | HIGH | — | MEDIUM |
| Missing header file prerequisites | — | LOW | HIGH | — |
| Missing CFLAGS for hardening and diagnos... | — | — | HIGH | MEDIUM |
| Missing `.PHONY` declarations for non-fi... | — | — | MEDIUM | LOW |
| No bounds check on file descriptor befor... | — | CRITICAL | HIGH | — |
| Finding: Silent crash on malloc failure ... | — | — | CRITICAL | HIGH |

Total severity disagreements: 7. Lower is better — it means the model's severity assessment aligns with the consensus.

### Unique Findings (Single-Model Discoveries)

Findings reported by only one model. These represent either unique insight or false positives:

| Model | Unique Findings |
|-------|:--------------:|
| gpt-oss-120b | 0 |
| glm5.2 | 0 |
| mistral | 14 |
| qwen3.8-27b | 6 |

A high unique count with a low consensus rate suggests false positives. A high unique count with a high consensus rate suggests the model found real bugs others missed.

### With-Skill vs Baseline: Skill Impact

How the skill changed each model's review:

**gpt-oss-120b:** Baseline 0 findings (0 CRITICAL) → With-skill 0 findings (0 CRITICAL). Skill found 0 critical bug(s) the baseline missed; baseline found 0 critical bug(s) the skill missed.

**glm5.2:** Baseline 12 findings (4 CRITICAL) → With-skill 7 findings (2 CRITICAL). Skill found 0 critical bug(s) the baseline missed; baseline found 2 critical bug(s) the skill missed.

**mistral:** Baseline 15 findings (0 CRITICAL) → With-skill 22 findings (9 CRITICAL). Skill found 9 critical bug(s) the baseline missed; baseline found 0 critical bug(s) the skill missed.

**qwen3.8-27b:** Baseline 1 findings (1 CRITICAL) → With-skill 13 findings (3 CRITICAL). Skill found 3 critical bug(s) the baseline missed; baseline found 1 critical bug(s) the skill missed.

#### Skill Tradeoff Analysis

The skill narrows reviewer focus toward memory-safety and correctness (Linus's priorities). This filters noise but can also suppress valid findings. Net critical impact per model:

| Model | Skill-Only CRITICAL | Baseline-Only CRITICAL | Net Critical Impact | Total Finding Delta |
|-------|:-------------------:|:----------------------:|:-------------------:|:-------------------:|
| gpt-oss-120b | 0 | 0 | 0 | 0 |
| glm5.2 | 0 | 2 | -2 | -5 |
| mistral | 9 | 0 | +9 | +7 |
| qwen3.8-27b | 3 | 1 | +2 | +12 |

**Interpretation:** A positive net critical impact means the skill found real bugs the baseline missed. A negative value means the skill suppressed critical findings the baseline caught — a coverage gap. A large negative total finding delta with neutral critical impact means the skill filtered noise without losing signal.

**Per-model read:**
- **gpt-oss-120b:** Neutral. No net change in critical coverage.
- **glm5.2:** Net negative on critical coverage. The skill cut 5 findings and suppressed 2 critical(s) the baseline caught, while only adding 0 new critical. The skill narrowed focus too aggressively — the 2 lost critical(s) are a real coverage gap worth investigating.
- **mistral:** Net positive. The skill added findings and added 9 critical bug(s) the baseline missed.
- **qwen3.8-27b:** Net positive. The skill added findings and added 2 critical bug(s) the baseline missed.

### Trigger Coverage Analysis

Which skill triggers each model fired:

**gpt-oss-120b:** 0 distinct triggers fired, 0 total trigger firings.

**glm5.2:** 7 distinct triggers fired, 7 total trigger firings.
  Top triggers: Code provides false or misleading information through any user-visible interface / memory safety — reference to invalid index (1x), Memory safety — out-of-bounds access; large stack allocations / buffer overflow (1x), Memory safety — out-of-bounds read from stack buffer (1x)

**mistral:** 9 distinct triggers fired, 22 total trigger firings.
  Top triggers: Unchecked error return in a critical path (5x), Silent corruption of data or state (5x), Operation produces wrong results for valid inputs (3x)

**qwen3.8-27b:** 9 distinct triggers fired, 12 total trigger firings.
  Top triggers: (unmatched) (4x), Theme 11 – Memory-Safety and Ownership (1x), Theme 2 – Fatal Assertions for Recoverable Errors (recoverable I/O errors must be handled, not ignored) (1x)

### Verdict

Based on consensus-confirmed CRITICAL findings, net critical impact (skill-only minus baseline-only), and severity calibration:

| Model | Confirmed CRITICAL | Skill-Only CRITICAL | Baseline-Only CRITICAL | Net Critical | Severity Disagreements | Score |
|-------|:------------------:|:-------------------:|:----------------------:|:-------------:|:----------------------:|:-----:|
| gpt-oss-120b | 0 | 0 | 0 | 0 | 0 | 0 |
| glm5.2 | 4 | 0 | 2 | -2 | 4 | -2 |
| mistral | 3 | 9 | 0 | +9 | 6 | 6 |
| qwen3.8-27b | 2 | 3 | 1 | +2 | 4 | 0 |

**Scoring:** `confirmed_critical + skill_only_critical - baseline_only_critical - severity_disagreements`. All terms are CRITICAL-only for unit consistency. The baseline-only penalty makes coverage gaps visible: a model that suppresses real bugs the baseline caught scores lower, even if it found other bugs the baseline missed.

**Honest read:** 
mistral wins clearly with score 6. 
gpt-oss-120b follows at 0.
 The skill helps differently per model — see the per-model read above for the tradeoff details.

---

## Ground-Truth Benchmark

Comparison against the ground-truth benchmark dataset (43 records in `data/benchmark.jsonl`).

Metrics computed by matching model findings to benchmark records by file and line number (±10 lines tolerance).

### Per-Model Benchmark Metrics

| Model | Precision | Recall | F1 | Hits | Misses | Severity Match Rate |
|-------|-----------|--------|------|------|--------|---------------------|
| gpt-oss-120b | 0.0% | 0.0% | 0.0% | 0 | 43 | 0.0% |
| glm5.2 | 42.9% | 7.0% | 12.0% | 3 | 40 | 0.0% |
| mistral | 22.7% | 11.6% | 15.4% | 5 | 38 | 20.0% |
| qwen3.8-27b | 23.1% | 7.0% | 10.7% | 3 | 40 | 66.7% |

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

