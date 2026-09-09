---
title: Model Comparison — SmallChat Review
date: 2026-09-09
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
| gpt-oss-120b | 15 | 4 | 4 | Skill adds value |
| glm5.2 | 7 | 2 | 0 | Skill reduces coverage |
| mistral | 22 | 9 | 9 | Skill adds value |
| qwen3.8-27b | 18 | 6 | 4 | Skill adds value |

The skill adds the most value for mistral, which gained 9 critical finding(s) exclusive to the with-skill review.

## Skill Generation Per Model

Skills are NOT identical — each variant is distilled from the same 350 patterns but with model-specific prompt calibration, token budgets, and execution mode.

| Model | Skill file | Distill mode | Token budget | Wall-clock timeout | Severity calibration |
|-------|------------|--------------|--------------|-------------------|---------------------|
| gpt-oss-120b | `linus-torvalds-skill/SKILL.md` | single | 16000 | 600s | balanced |
| glm5.2 | `linus-torvalds-skill/SKILL-GLM.md` | single | 16000 | 600s | downgrade ONLY style/docs borderline, never correctness/error-handling |
| mistral | `linus-torvalds-skill/SKILL-Mistral.md` | single | 16000 | 600s | under-rates → upgrade borderline |
| qwen3.8-27b | `linus-torvalds-skill/SKILL-Qwen.md` | single | 16000 | 600s | none measured |

**Source:** `src/torvalds_skill/profiles.py` for per-model `max_tokens`, `timeout`, and `distill_mode` settings. Regenerate per `docs/CONTRIBUTING.md`.

4 models reviewed the same C codebase (antirez/smallchat, ~706 LOC) using the same language-agnostic Linus Torvalds skill. This document cross-references their findings at the issue level — not just counts — to measure consensus, accuracy, and severity calibration.

## Metrics Summary

| Metric | gpt-oss-120b | glm5.2 | mistral | qwen3.8-27b |
|--------|:---:|:---:|:---:|:---:|
| Findings | N/A | N/A | N/A | N/A |
| Critical | 4 | 2 | 9 | 6 |
| High | 5 | 4 | 12 | 9 |
| Medium | 2 | 0 | 1 | 2 |
| Low | 4 | 1 | 0 | 1 |
| Words | 1341 | 1455 | 3572 | 1594 |

**Key insight:** Finding count is a poor quality signal. The consensus matrix below shows which models caught which bugs — and that is where the real signal lives.

---

## Finding Consensus Matrix

Every finding from all three reviews, mapped to the underlying issue. ✓ = found, ✗ = missed. Severity shown in parentheses.

### chatlib.c

| # | Issue | gpt-oss-120b | glm5.2 | mistral | qwen3.8-27b | Consensus |
|---|---|:---:|:---:|:---:|:---:|:---:|
| 1 | Missing `const` qualifier on `TCPConnect` address... | ✓ (LOW) | ✗ | ✗ | ✗ | gpt-oss-120b only |
| 2 | Magic number used for listen backlog | ✓ (LOW) | ✗ | ✓ (HIGH) | ✗ | — |
| 3 | Memory leak in TCPConnect on EINPROGRESS return... | ✗ | ✓ (HIGH) | ✓ (HIGH) | ✗ | — |
| 4 | Memory leak in TCPConnect on EINPROGRESS return... | ✗ | ✓ (HIGH) | ✗ | ✓ (HIGH) | — |
| 5 | Fatal exit on out-of-memory in chatMalloc and... | ✗ | ✓ (HIGH) | ✓ (CRITICAL) | ✗ | — |
| 6 | Finding: Missing error handling in acceptClient | ✗ | ✗ | ✓ (HIGH) | ✗ | mistral only |
| 7 | Memory leak in TCPConnect on EINPROGRESS return... | ✗ | ✓ (HIGH) | ✗ | ✓ (HIGH) | — |

### chatlib.h

| # | Issue | gpt-oss-120b | glm5.2 | mistral | qwen3.8-27b | Consensus |
|---|---|:---:|:---:|:---:|:---:|:---:|
| 8 | Missing size_t definition | ✓ (MEDIUM) | ✓ (HIGH) | ✓ (HIGH) | ✓ (MEDIUM) | 4/4 |
| 9 | Inconsistent naming convention | ✓ (LOW) | ✓ (LOW) | ✓ (HIGH) | ✓ (LOW) | 4/4 |
| 10 | Missing .PHONY declarations | ✓ (MEDIUM) | ✗ | ✓ (HIGH) | ✓ (MEDIUM) | 3/4 |
| 11 | CFLAGS placed after output file | ✓ (LOW) | ✗ | ✓ (MEDIUM) | ✗ | — |

### smallchat-client.c

| # | Issue | gpt-oss-120b | glm5.2 | mistral | qwen3.8-27b | Consensus |
|---|---|:---:|:---:|:---:|:---:|:---:|
| 12 | Buffer overflow when appending newline to full... | ✓ (CRITICAL) | ✗ | ✗ | ✓ (HIGH) | — |
| 13 | Ignored return value from setRawMode | ✓ (HIGH) | ✗ | ✓ (HIGH) | ✓ (HIGH) | 3/4 |
| 14 | Finding: Unchecked error return in critical path | ✗ | ✗ | ✓ (CRITICAL) | ✗ | mistral only |
| 15 | Finding: Silent corruption of terminal state | ✗ | ✗ | ✓ (CRITICAL) | ✗ | mistral only |
| 16 | FD_SET used without FD_SETSIZE bounds check | ✗ | ✗ | ✗ | ✓ (CRITICAL) | qwen3.8-27b only |
| 17 | inputBufferAppend() failure is ignored when... | ✗ | ✗ | ✗ | ✓ (HIGH) | qwen3.8-27b only |
| 18 | inputBufferFeedChar() hides append failure | ✗ | ✗ | ✗ | ✓ (HIGH) | qwen3.8-27b only |
| 19 | write() to the server socket is unchecked | ✗ | ✗ | ✗ | ✓ (HIGH) | qwen3.8-27b only |

### smallchat-server.c

| # | Issue | gpt-oss-120b | glm5.2 | mistral | qwen3.8-27b | Consensus |
|---|---|:---:|:---:|:---:|:---:|:---:|
| 20 | Buffer overflow in nickname construction | ✓ (CRITICAL) | ✗ | ✓ (CRITICAL) | ✗ | — |
| 21 | Missing NUL‑terminator for client nickname | ✓ (CRITICAL) | ✗ | ✓ (HIGH) | ✓ (CRITICAL) | 3/4 |
| 22 | Out‑of‑bounds access of `Chat->clients` array | ✓ (CRITICAL) | ✓ (CRITICAL) | ✗ | ✓ (CRITICAL) | 3/4 |
| 23 | Reliance on `assert` for runtime invariant | ✓ (HIGH) | ✗ | ✗ | ✗ | gpt-oss-120b only |
| 24 | Ignoring possible failure of... | ✓ (HIGH) | ✗ | ✗ | ✗ | gpt-oss-120b only |
| 25 | Ignoring write errors in `sendMsgToAllClientsBut` | ✓ (HIGH) | ✓ (CRITICAL) | ✓ (HIGH) | ✓ (CRITICAL) | 4/4 |
| 26 | Treating any `read` error as client disconnect | ✓ (HIGH) | ✓ (HIGH) | ✗ | ✓ (HIGH) | 3/4 |
| 27 | Missing Error Handling in `initChat` | ✗ | ✗ | ✓ (CRITICAL) | ✓ (CRITICAL) | — |
| 28 | Race Condition in `freeClient` | ✗ | ✗ | ✓ (CRITICAL) | ✓ (CRITICAL) | — |
| 29 | Silent Corruption in Nickname Handling | ✗ | ✗ | ✓ (CRITICAL) | ✓ (HIGH) | — |
| 30 | Resource Leak in `createClient` | ✗ | ✗ | ✓ (CRITICAL) | ✗ | mistral only |
| 31 | Unchecked `read` in Main Loop | ✗ | ✗ | ✓ (CRITICAL) | ✗ | mistral only |
| 32 | Missing Logging for Critical Errors | ✗ | ✗ | ✓ (HIGH) | ✗ | mistral only |
| 33 | Missing Message Framing | ✗ | ✗ | ✓ (HIGH) | ✗ | mistral only |
| 34 | Missing Non-Blocking I/O for Client Sockets | ✗ | ✗ | ✓ (HIGH) | ✗ | mistral only |
| 35 | select() EINTR causes process exit | ✗ | ✗ | ✗ | ✓ (HIGH) | qwen3.8-27b only |

---

## Severity Disagreement Table

Cases where 2+ models found the same issue but assigned different severities:

| Issue | gpt-oss-120b | glm5.2 | mistral | qwen3.8-27b |
|-------|:---:|:---:|:---:|:---:|
| Magic number used for listen backlog | LOW | — | HIGH | — |
| Fatal exit on out-of-memory in... | — | HIGH | CRITICAL | — |
| Missing size_t definition | MEDIUM | HIGH | HIGH | MEDIUM |
| Inconsistent naming convention | LOW | LOW | HIGH | LOW |
| Missing .PHONY declarations | MEDIUM | — | HIGH | MEDIUM |
| CFLAGS placed after output file | LOW | — | MEDIUM | — |
| Buffer overflow when appending newline... | CRITICAL | — | — | HIGH |
| Missing NUL‑terminator for client... | CRITICAL | — | HIGH | CRITICAL |
| Ignoring write errors in... | HIGH | CRITICAL | HIGH | CRITICAL |
| Silent Corruption in Nickname Handling | — | — | CRITICAL | HIGH |

---

## Trigger Coverage Comparison

Which skill triggers fired in each review:

| Trigger theme | gpt-oss-120b | glm5.2 | mistral | qwen3.8-27b |
|---------------|:---:|:---:|:---:|:---:|
| (unmatched — build... | ✗ | ✓ (1) | ✗ | ✗ |
| (unmatched) | ✓ (4) | ✗ | ✗ | ✓ (5) |
| Code provides false or... | ✗ | ✓ (1) | ✗ | ✗ |
| Crash or panic in a path that... | ✗ | ✗ | ✓ (3) | ✗ |
| Data race with observable... | ✗ | ✗ | ✓ (2) | ✗ |
| Fatal abort used for resource... | ✗ | ✓ (1) | ✗ | ✗ |
| Fatal assertion (panic/fatal... | ✓ (1) | ✗ | ✗ | ✗ |
| Identifier that does not... | ✓ (1) | ✗ | ✗ | ✗ |
| Interface design that makes... | ✗ | ✓ (1) | ✗ | ✗ |
| Magic numbers & hard‑coded... | ✓ (1) | ✗ | ✗ | ✗ |
| Memory safety — out-of-bounds... | ✗ | ✓ (1) | ✗ | ✗ |
| Memory safety — out-of-bounds... | ✗ | ✓ (1) | ✗ | ✗ |
| Missing `.PHONY` declarations... | ✗ | ✗ | ✓ (1) | ✗ |
| Missing compiler flags for... | ✗ | ✗ | ✓ (1) | ✗ |
| Operation produces wrong... | ✗ | ✗ | ✓ (3) | ✗ |
| Performing an unchecked... | ✓ (4) | ✗ | ✗ | ✗ |
| Public API that exposes... | ✗ | ✗ | ✓ (1) | ✗ |
| Resource leak in a critical... | ✗ | ✗ | ✓ (1) | ✗ |
| Resource leak — function... | ✗ | ✓ (1) | ✗ | ✗ |
| Silent corruption of data or... | ✗ | ✗ | ✓ (5) | ✗ |
| Silently swallowing an error... | ✓ (4) | ✗ | ✗ | ✗ |
| Theme 11 – Memory-Safety and... | ✗ | ✗ | ✗ | ✓ (3) |
| Theme 11 – Memory-Safety and... | ✗ | ✗ | ✗ | ✓ (1) |
| Theme 11 – Memory-Safety and... | ✗ | ✗ | ✗ | ✓ (1) |
| Theme 2 – Fatal Assertions... | ✗ | ✗ | ✗ | ✓ (2) |
| Theme 2 – Fatal Assertions... | ✗ | ✗ | ✗ | ✓ (3) |
| Theme 4 – Security-Critical... | ✗ | ✗ | ✗ | ✓ (1) |
| Theme 5 – Consistent... | ✗ | ✗ | ✗ | ✓ (2) |
| Unchecked error return in a... | ✗ | ✗ | ✓ (5) | ✗ |

---

## With-Skill vs Baseline Comparison

For each model, comparing findings with the skill vs without (baseline):

| Model | Baseline Total | With-Skill Total | Baseline CRITICAL | With-Skill CRITICAL | Critical Overlap | Skill-Only CRITICAL | Baseline-Only CRITICAL | Skill Added Value |
|-------|----------------|------------------|-------------------|---------------------|------------------|---------------------|------------------------|-------------------|
| gpt-oss-120b | 7 | 15 | 0 | 4 | 0 | 4 | 0 | yes (+4 net critical: 4 found, 0 lost) |
| glm5.2 | 12 | 7 | 4 | 2 | 2 | 0 | 2 | no (-2 net critical: 0 found, 2 lost) |
| mistral | 15 | 22 | 0 | 9 | 0 | 9 | 0 | yes (+9 net critical: 9 found, 0 lost) |
| qwen3.8-27b | 11 | 18 | 2 | 6 | 2 | 4 | 0 | yes (+4 net critical: 4 found, 0 lost) |

---

## Per-Model Bug Comparison (Baseline vs With-Skill)

Bug-by-bug comparison for each model: which bugs were found by both, only baseline, or only skill.

### gpt-oss-120b

**Same bugs (found in both):**

| Issue | File | Baseline | Skill | Severity changed? |
|-------|------|----------|-------|-------------------|
| Buffer overflow in nickname construction | smallchat-server.c | HIGH | CRITICAL | YES: HIGH→CRITICAL |
| Out‑of‑bounds access of `Chat->clients` array | smallchat-server.c | HIGH | CRITICAL | YES: HIGH→CRITICAL |
| Magic number used for listen backlog | chatlib.c | LOW | LOW | no |

**Baseline-only (skill missed):**

*Classification: `skill-gap` = CORE finding with matched trigger (skill should catch); `out-of-scope` = TRIVIA finding (intentionally uncovered); `sampling-loss` = CORE finding with no matched trigger (pattern absent from 325-sample cluster).*

| Issue | File | Severity | Classification | Trigger coverage |
|-------|------|----------|----------------|------------------|
| Nickname string not NUL‑terminated | smallchat-server.c | HIGH | sampling-loss | unmatched |
| Non‑blocking read errors treated as disconnects | smallchat-server.c | HIGH | sampling-loss | unmatched |
| SIGPIPE not ignored on writes to server | smallchat-client.c | HIGH | sampling-loss | unmatched |
| Missing error check for `setsockopt` in... | chatlib.c | LOW | sampling-loss | unmatched |

**Skill-only (skill added):**

| Issue | File | Severity | Trigger |
|-------|------|----------|---------|
| Missing NUL‑terminator for client nickname | smallchat-server.c | CRITICAL | Performing an unchecked pointer... |
| Reliance on `assert` for runtime invariant | smallchat-server.c | HIGH | Fatal assertion (panic/fatal assertion)... |
| Ignoring possible failure of `socketSetNonBlockNoDelay` | smallchat-server.c | HIGH | Silently swallowing an error and... |
| Ignoring write errors in `sendMsgToAllClientsBut` | smallchat-server.c | HIGH | Silently swallowing an error and... |
| Treating any `read` error as client disconnect | smallchat-server.c | HIGH | Silently swallowing an error and... |
| Buffer overflow when appending newline to full input buffer | smallchat-client.c | CRITICAL | Performing an unchecked pointer... |
| Ignored return value from setRawMode | smallchat-client.c | HIGH | Silently swallowing an error and... |
| Missing `const` qualifier on `TCPConnect` address parameter | chatlib.c | LOW | (unmatched) |
| Missing size_t definition | chatlib.h | MEDIUM | (unmatched) |
| Inconsistent naming convention | chatlib.h | LOW | Identifier that does not convey its... |
| Missing .PHONY declarations | chatlib.h | MEDIUM | (unmatched) |
| CFLAGS placed after output file | chatlib.h | LOW | (unmatched) |

### glm5.2

**Same bugs (found in both):**

| Issue | File | Baseline | Skill | Severity changed? |
|-------|------|----------|-------|-------------------|
| Unchecked `acceptClient` return value causes out-of-bounds... | smallchat-server.c | CRITICAL | CRITICAL | no |
| No bounds check on file descriptor before indexing... | smallchat-server.c | CRITICAL | CRITICAL | no |
| Non-const `addr` parameter permits modification of caller's... | chatlib.h | LOW | HIGH | YES: LOW→HIGH |
| Missing header file prerequisites | chatlib.h | LOW | LOW | no |

**Baseline-only (skill missed):**

*Classification: `skill-gap` = CORE finding with matched trigger (skill should catch); `out-of-scope` = TRIVIA finding (intentionally uncovered); `sampling-loss` = CORE finding with no matched trigger (pattern absent from 325-sample cluster).*

| Issue | File | Severity | Classification | Trigger coverage |
|-------|------|----------|----------------|------------------|
| Missing null terminator on client nickname in `createClient` | smallchat-server.c | CRITICAL | sampling-loss | unmatched |
| No bounds check on file descriptor against `MAX_CLIENTS` in... | smallchat-server.c | CRITICAL | sampling-loss | unmatched |
| `select()` exits the server on EINTR | smallchat-server.c | HIGH | sampling-loss | unmatched |
| `FD_SET` called without `FD_SETSIZE` bounds check | smallchat-server.c | HIGH | sampling-loss | unmatched |
| No SIGPIPE handling — client killed on write to closed... | smallchat-client.c | HIGH | sampling-loss | unmatched |
| `select()` exits the client on EINTR | smallchat-client.c | HIGH | sampling-loss | unmatched |
| `TCPConnect` leaks `addrinfo` on EINPROGRESS early return | chatlib.c | MEDIUM | sampling-loss | unmatched |
| `acceptClient` populates `sockaddr_in` but never uses it | chatlib.c | LOW | sampling-loss | unmatched |

**Skill-only (skill added):**

| Issue | File | Severity | Trigger |
|-------|------|----------|---------|
| `snprintf` return value used as `memcpy` length without... | smallchat-server.c | HIGH | Memory safety — out-of-bounds read from... |
| Memory leak in TCPConnect on EINPROGRESS return path | chatlib.c | HIGH | Resource leak — function returns... |
| Fatal exit on out-of-memory in chatMalloc and chatRealloc | chatlib.c | HIGH | Fatal abort used for resource... |

### mistral

**Same bugs (found in both):**

| Issue | File | Baseline | Skill | Severity changed? |
|-------|------|----------|-------|-------------------|
| Buffer Overflow in `sendMsgToAllClientsBut` | smallchat-server.c | HIGH | CRITICAL | YES: HIGH→CRITICAL |
| Missing Client Input Validation | smallchat-server.c | HIGH | HIGH | no |

**Baseline-only (skill missed):**

*Classification: `skill-gap` = CORE finding with matched trigger (skill should catch); `out-of-scope` = TRIVIA finding (intentionally uncovered); `sampling-loss` = CORE finding with no matched trigger (pattern absent from 325-sample cluster).*

| Issue | File | Severity | Classification | Trigger coverage |
|-------|------|----------|----------------|------------------|
| Memory Leak in Client Disconnection | smallchat-server.c | HIGH | sampling-loss | unmatched |
| Resource Leak in Error Paths | chatlib.c | HIGH | sampling-loss | unmatched |
| Unchecked System Call | smallchat-server.c | HIGH | skill-gap | Introducing a new public system call or interface... |
| Uninitialized Memory Access | smallchat-server.c | HIGH | sampling-loss | unmatched |
| Race Condition in Client Management | smallchat-server.c | HIGH | sampling-loss | unmatched |
| Missing Input Validation | smallchat-server.c | HIGH | sampling-loss | unmatched |
| Unchecked read() in Client | smallchat-client.c | HIGH | sampling-loss | unmatched |
| Buffer Overflow in Client Input | smallchat-client.c | HIGH | sampling-loss | unmatched |
| Missing Cleanup in Client | smallchat-client.c | HIGH | skill-gap | Missing `err:` cleanup label that would release... |
| Inefficient Client Nickname Handling | smallchat-server.c | HIGH | sampling-loss | unmatched |
| Missing Error Handling in TCPConnect() | chatlib.c | MEDIUM | skill-gap | Test that only covers the happy path, ignoring... |
| Magic Numbers | smallchat-server.c | MEDIUM | sampling-loss | unmatched |
| Redundant Code in freeClient() | smallchat-server.c | LOW | sampling-loss | unmatched |

**Skill-only (skill added):**

| Issue | File | Severity | Trigger |
|-------|------|----------|---------|
| Resource Leak in `createClient` | smallchat-server.c | CRITICAL | Unchecked error return in a critical... |
| Unchecked `read` in Main Loop | smallchat-server.c | CRITICAL | Unchecked error return in a critical... |
| Missing Error Handling in `initChat` | smallchat-server.c | CRITICAL | Crash or panic in a path that should... |
| Race Condition in `freeClient` | smallchat-server.c | CRITICAL | Data race with observable side effects |
| Silent Corruption in Nickname Handling | smallchat-server.c | CRITICAL | Silent corruption of data or state |
| Missing Logging for Critical Errors | smallchat-server.c | HIGH | Silent corruption of data or state |
| Missing Thread Safety in Global State | smallchat-server.c | HIGH | Data race with observable side effects |
| Missing Message Framing | smallchat-server.c | HIGH | Operation produces wrong results for... |
| Missing Non-Blocking I/O for Client Sockets | smallchat-server.c | HIGH | Crash or panic in a path that should... |
| Finding: Unchecked error return in critical path | smallchat-client.c | CRITICAL | Unchecked error return in a critical... |
| Finding: Silent corruption of terminal state | smallchat-client.c | CRITICAL | Silent corruption of data or state |
| Finding: Resource leak on error | smallchat-client.c | HIGH | Resource leak in a critical path |
| Finding: Silent crash on malloc failure in... | chatlib.c | CRITICAL | Silent corruption of data or state |
| Finding: Resource leak in TCPConnect on partial failure | chatlib.c | HIGH | Silent corruption of data or state |
| Finding: Unchecked error in createTCPServer | chatlib.c | HIGH | Unchecked error return in a critical... |
| Finding: Missing error handling in acceptClient | chatlib.c | HIGH | Crash or panic in a path that should... |
| Missing error handling for system calls | chatlib.h | HIGH | Unchecked error return in a critical... |
| Leaky interface exposing internal state | chatlib.h | HIGH | Public API that exposes internal... |
| Missing CFLAGS for hardening and diagnostics | chatlib.h | HIGH | Missing compiler flags for security and... |
| Missing `.PHONY` declarations for non-file targets | chatlib.h | MEDIUM | Missing `.PHONY` declarations for... |

### qwen3.8-27b

**Same bugs (found in both):**

| Issue | File | Baseline | Skill | Severity changed? |
|-------|------|----------|-------|-------------------|
| Initial nick is not NUL-terminated | smallchat-server.c | CRITICAL | CRITICAL | no |
| createClient indexes the clients array with an unvalidated... | smallchat-server.c | HIGH | CRITICAL | YES: HIGH→CRITICAL |
| acceptClient result is not checked before createClient | smallchat-server.c | CRITICAL | CRITICAL | no |
| write() can terminate the server via SIGPIPE and errors are... | smallchat-server.c | HIGH | CRITICAL | YES: HIGH→CRITICAL |
| read() error path disconnects clients on transient errors | smallchat-server.c | HIGH | HIGH | no |
| read() from stdin error and EOF are ignored | smallchat-client.c | HIGH | HIGH | no |
| Missing `<stddef.h>` include for `size_t` | chatlib.h | MEDIUM | MEDIUM | no |
| `TCPConnect` should take `const char*` address | chatlib.h | MEDIUM | LOW | YES: MEDIUM→LOW |
| Missing header dependencies can produce stale binaries | chatlib.h | LOW | MEDIUM | YES: LOW→MEDIUM |

**Baseline-only (skill missed):**

*Classification: `skill-gap` = CORE finding with matched trigger (skill should catch); `out-of-scope` = TRIVIA finding (intentionally uncovered); `sampling-loss` = CORE finding with no matched trigger (pattern absent from 325-sample cluster).*

| Issue | File | Severity | Classification | Trigger coverage |
|-------|------|----------|----------------|------------------|
| getaddrinfo() failure is not reported | chatlib.c | MEDIUM | sampling-loss | unmatched |
| Server socket is IPv4-only while client uses AF_UNSPEC | chatlib.c | MEDIUM | sampling-loss | unmatched |

**Skill-only (skill added):**

| Issue | File | Severity | Trigger |
|-------|------|----------|---------|
| select/fd_set usage lacks FD_SETSIZE and MAX_CLIENTS bounds | smallchat-server.c | CRITICAL | Theme 11 – Memory-Safety and Ownership |
| select() EINTR causes process exit | smallchat-server.c | HIGH | Theme 2 – Fatal Assertions for... |
| snprintf() negative return becomes a huge size_t length | smallchat-server.c | HIGH | Theme 4 – Security-Critical Checks Must... |
| FD_SET used without FD_SETSIZE bounds check | smallchat-client.c | CRITICAL | Theme 11 – Memory-Safety and Ownership... |
| setRawMode() failure is ignored | smallchat-client.c | HIGH | Theme 2 – Fatal Assertions for... |
| inputBufferAppend() failure is ignored when sending a line | smallchat-client.c | HIGH | Theme 5 – Consistent Error-Code... |
| inputBufferFeedChar() hides append failure | smallchat-client.c | HIGH | Theme 5 – Consistent Error-Code... |
| write() to the server socket is unchecked | smallchat-client.c | HIGH | Theme 2 – Fatal Assertions for... |
| TCPConnect leaks getaddrinfo list on nonblocking... | chatlib.c | HIGH | Theme 11 – Memory-Safety and Ownership:... |

---

## Focus Metrics

Core-vs-trivia breakdown: % of findings that are CORE (correctness/memory-safety/error-handling) vs TRIVIA (style/build/docs).

| Model | With-Skill CORE% | Baseline-Only CORE% | Focus Status |
|-------|:----------------:|:-------------------:|:-------------|
| gpt-oss-120b | 100.0% | 100.0% | ✅ focused |
| glm5.2 | 100.0% | 100.0% | ✅ focused |
| mistral | 100.0% | 100.0% | ✅ focused |
| qwen3.8-27b | 100.0% | 100.0% | ✅ focused |

**Gate rules:** `FOCUS DRIFT` when with-skill CORE% < 50%; `CRITICAL FOCUS FAILURE` when baseline-only contains any CRITICAL while skill-only is majority trivia. **Note:** `unmatched` means no trigger-text overlap, not 'outside the skill's domain'.

---

## Qualitative Analysis

### Consensus-Based Accuracy

Findings confirmed by 2+ models are treated as real bugs. Findings reported by only one model are unverified (could be real or false positive).

| Model | Total Findings | Confirmed (2+ models) | Unverified (1 model only) | Consensus Rate |
|-------|:--------------:|:---------------------:|:--------------------------:|:--------------:|
| gpt-oss-120b | 15 | 12 | 3 | 80% |
| glm5.2 | 9 | 9 | 0 | 100% |
| mistral | 22 | 14 | 8 | 64% |
| qwen3.8-27b | 19 | 14 | 5 | 74% |

### Severity Calibration

Cases where 2+ models found the same issue but assigned different severities:

| Issue | gpt-oss-120b | glm5.2 | mistral | qwen3.8-27b |
|-------|:---:|:---:|:---:|:---:|
| Magic number used for listen backlog | LOW | — | HIGH | — |
| Fatal exit on out-of-memory in... | — | HIGH | CRITICAL | — |
| Missing size_t definition | MEDIUM | HIGH | HIGH | MEDIUM |
| Inconsistent naming convention | LOW | LOW | HIGH | LOW |
| Missing .PHONY declarations | MEDIUM | — | HIGH | MEDIUM |
| CFLAGS placed after output file | LOW | — | MEDIUM | — |
| Buffer overflow when appending newline... | CRITICAL | — | — | HIGH |
| Missing NUL‑terminator for client... | CRITICAL | — | HIGH | CRITICAL |
| Ignoring write errors in... | HIGH | CRITICAL | HIGH | CRITICAL |
| Silent Corruption in Nickname Handling | — | — | CRITICAL | HIGH |

Total severity disagreements: 10. Lower is better — it means the model's severity assessment aligns with the consensus.

### Unique Findings (Single-Model Discoveries)

Findings reported by only one model. These represent either unique insight or false positives:

| Model | Unique Findings |
|-------|:--------------:|
| gpt-oss-120b | 3 |
| glm5.2 | 0 |
| mistral | 8 |
| qwen3.8-27b | 5 |

A high unique count with a low consensus rate suggests false positives. A high unique count with a high consensus rate suggests the model found real bugs others missed.

### With-Skill vs Baseline: Skill Impact

How the skill changed each model's review:

**gpt-oss-120b:** Baseline 7 findings (0 CRITICAL) → With-skill 15 findings (4 CRITICAL). Skill found 4 critical bug(s) the baseline missed; baseline found 0 critical bug(s) the skill missed.

**glm5.2:** Baseline 12 findings (4 CRITICAL) → With-skill 7 findings (2 CRITICAL). Skill found 0 critical bug(s) the baseline missed; baseline found 2 critical bug(s) the skill missed.

**mistral:** Baseline 15 findings (0 CRITICAL) → With-skill 22 findings (9 CRITICAL). Skill found 9 critical bug(s) the baseline missed; baseline found 0 critical bug(s) the skill missed.

**qwen3.8-27b:** Baseline 11 findings (2 CRITICAL) → With-skill 18 findings (6 CRITICAL). Skill found 4 critical bug(s) the baseline missed; baseline found 0 critical bug(s) the skill missed.

#### Skill Tradeoff Analysis

The skill narrows reviewer focus toward memory-safety and correctness (Linus's priorities). This filters noise but can also suppress valid findings. Net critical impact per model:

| Model | Skill-Only CRITICAL | Baseline-Only CRITICAL | Net Critical Impact | Total Finding Delta |
|-------|:-------------------:|:----------------------:|:-------------------:|:-------------------:|
| gpt-oss-120b | 4 | 0 | +4 | +8 |
| glm5.2 | 0 | 2 | -2 | -5 |
| mistral | 9 | 0 | +9 | +7 |
| qwen3.8-27b | 4 | 0 | +4 | +7 |

**Interpretation:** A positive net critical impact means the skill found real bugs the baseline missed. A negative value means the skill suppressed critical findings the baseline caught — a coverage gap. A large negative total finding delta with neutral critical impact means the skill filtered noise without losing signal.

**Per-model read:**
- **gpt-oss-120b:** Net positive. The skill added findings and added 4 critical bug(s) the baseline missed.
- **glm5.2:** Net negative on critical coverage. The skill cut 5 findings and suppressed 2 critical(s) the baseline caught, while only adding 0 new critical. The skill narrowed focus too aggressively — the 2 lost critical(s) are a real coverage gap worth investigating.
- **mistral:** Net positive. The skill added findings and added 9 critical bug(s) the baseline missed.
- **qwen3.8-27b:** Net positive. The skill added findings and added 4 critical bug(s) the baseline missed.

### Trigger Coverage Analysis

Which skill triggers each model fired:

**gpt-oss-120b:** 6 distinct triggers fired, 15 total trigger firings.
  Top triggers: Performing an unchecked pointer arithmetic that can walk off the end of a buffer (4x), Silently swallowing an error and continuing execution (4x), (unmatched) (4x)

**glm5.2:** 7 distinct triggers fired, 7 total trigger firings.
  Top triggers: Code provides false or misleading information through any user-visible interface / memory safety — reference to invalid index (1x), Memory safety — out-of-bounds access; large stack allocations / buffer overflow (1x), Memory safety — out-of-bounds read from stack buffer (1x)

**mistral:** 9 distinct triggers fired, 22 total trigger firings.
  Top triggers: Unchecked error return in a critical path (5x), Silent corruption of data or state (5x), Operation produces wrong results for valid inputs (3x)

**qwen3.8-27b:** 8 distinct triggers fired, 18 total trigger firings.
  Top triggers: (unmatched) (5x), Theme 11 – Memory-Safety and Ownership (3x), Theme 2 – Fatal Assertions for Recoverable Errors (suppressing an error return) (3x)

### Verdict

Based on consensus-confirmed CRITICAL findings, net critical impact (skill-only minus baseline-only), and severity calibration:

| Model | Confirmed CRITICAL | Skill-Only CRITICAL | Baseline-Only CRITICAL | Net Critical | Severity Disagreements | Score |
|-------|:------------------:|:-------------------:|:----------------------:|:-------------:|:----------------------:|:-----:|
| gpt-oss-120b | 4 | 4 | 0 | +4 | 8 | 0 |
| glm5.2 | 2 | 0 | 2 | -2 | 4 | -4 |
| mistral | 5 | 9 | 0 | +9 | 9 | 5 |
| qwen3.8-27b | 5 | 4 | 0 | +4 | 7 | 2 |

**Scoring:** `confirmed_critical + skill_only_critical - baseline_only_critical - severity_disagreements`. All terms are CRITICAL-only for unit consistency. The baseline-only penalty makes coverage gaps visible: a model that suppresses real bugs the baseline caught scores lower, even if it found other bugs the baseline missed.

**Honest read:** 
mistral wins clearly with score 5. 
qwen3.8-27b follows at 2.
 The skill helps differently per model — see the per-model read above for the tradeoff details.

---

## Ground-Truth Benchmark

Comparison against the ground-truth benchmark dataset (43 records in `data/benchmark.jsonl`).

Metrics computed by matching model findings to benchmark records by file and line number (±10 lines tolerance).

### Per-Model Benchmark Metrics

| Model | Precision | Recall | F1 | Hits | Misses | Severity Match Rate |
|-------|-----------|--------|------|------|--------|---------------------|
| gpt-oss-120b | 40.0% | 14.0% | 20.7% | 6 | 37 | 33.3% |
| glm5.2 | 42.9% | 7.0% | 12.0% | 3 | 40 | 0.0% |
| mistral | 22.7% | 11.6% | 15.4% | 5 | 38 | 20.0% |
| qwen3.8-27b | 22.2% | 9.3% | 13.1% | 4 | 39 | 50.0% |

> **Note:** The benchmark is derived entirely from model consensus (no external tool or human verification). Precision and recall are therefore relative measures of cross-model agreement, not absolute correctness.

