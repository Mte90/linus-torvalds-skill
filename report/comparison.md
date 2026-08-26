---
title: Model Comparison — SmallChat Review
date: 2026-08-26
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
| gpt-oss-120b | 10 | 2 | 1 | Skill reduces coverage |
| glm5.2 | 9 | 4 | 4 | Skill adds value |
| mistral | 18 | 4 | 2 | Skill reduces coverage |

The skill adds the most value for glm5.2, which gained 4 critical finding(s) exclusive to the with-skill review.

3 models reviewed the same C codebase (antirez/smallchat, ~706 LOC) using the same language-agnostic Linus Torvalds skill. This document cross-references their findings at the issue level — not just counts — to measure consensus, accuracy, and severity calibration.

## Metrics Summary

| Metric | gpt-oss-120b | glm5.2 | mistral |
|--------|:---:|:---:|:---:|
| Findings | 10 | 9 | 18 |
| Critical | 2 | 4 | 4 |
| High | 7 | 2 | 7 |
| Medium | 1 | 3 | 5 |
| Low | 0 | 0 | 2 |
| Words | 1048 | 2795 | 1418 |

**Key insight:** Finding count is a poor quality signal. The consensus matrix below shows which models caught which bugs — and that is where the real signal lives.

---

## Finding Consensus Matrix

Every finding from all three reviews, mapped to the underlying issue. ✓ = found, ✗ = missed. Severity shown in parentheses.

### chatlib.c

| # | Issue | gpt-oss-120b | glm5.2 | mistral | Consensus |
|---|:---:|:---:|:---:|:---:|
| 1 | Ignored return value of `setsockopt()` in `socketS... | ✓ (HIGH) | ✗ | ✓ (LOW) | 2/3 |
| 2 | Finding: Inconsistent error handling conventions | ✗ | ✗ | ✓ (HIGH) | mistral only |
| 3 | Finding: Premature abstraction | ✗ | ✗ | ✓ (MEDIUM) | mistral only |

### smallchat-client.c

| # | Issue | gpt-oss-120b | glm5.2 | mistral | Consensus |
|---|:---:|:---:|:---:|:---:|
| 4 | Ignored return value of `write()` when sending use... | ✓ (HIGH) | ✗ | ✗ | gpt-oss-120b only |
| 5 | No handling of `inputBufferAppend()` failure | ✓ (HIGH) | ✗ | ✗ | gpt-oss-120b only |
| 6 | /nick with no argument gives misleading "Unsupport... | ✗ | ✓ (MEDIUM) | ✗ | glm5.2 only |
| 7 | Finding: Lack of input validation | ✗ | ✗ | ✓ (HIGH) | mistral only |
| 8 | Finding: Resource leak in client cleanup | ✗ | ✗ | ✓ (HIGH) | mistral only |

### smallchat-server.c

| # | Issue | gpt-oss-120b | glm5.2 | mistral | Consensus |
|---|:---:|:---:|:---:|:---:|
| 9 | Fatal assertion on recoverable condition | ✓ (CRITICAL) | ✓ (HIGH) | ✓ (CRITICAL) | 3/3 |
| 10 | Fixed‑size client table can overflow | ✓ (CRITICAL) | ✗ | ✗ | gpt-oss-120b only |
| 11 | Ignored return value of `write()` in broadcast loo... | ✓ (HIGH) | ✓ (CRITICAL) | ✗ | 2/3 |
| 12 | Ignored result of `socketSetNonBlockNoDelay()` in ... | ✓ (HIGH) | ✗ | ✗ | gpt-oss-120b only |
| 13 | Nick string not NUL‑terminated | ✓ (HIGH) | ✗ | ✗ | gpt-oss-120b only |
| 14 | Missing error handling for writes to client socket... | ✓ (HIGH) | ✓ (CRITICAL) | ✓ (CRITICAL) | 3/3 |
| 15 | Magic constant `MAX_CLIENTS` | ✓ (MEDIUM) | ✗ | ✗ | gpt-oss-120b only |
| 16 | No bounds check on fd against MAX_CLIENTS — buffer... | ✗ | ✓ (CRITICAL) | ✓ (HIGH) | 2/3 |
| 17 | select() exits on EINTR — any signal kills the ser... | ✗ | ✓ (CRITICAL) | ✗ | glm5.2 only |
| 18 | write() return values ignored on non-blocking sock... | ✗ | ✓ (HIGH) | ✗ | glm5.2 only |
| 19 | select() 1-second timeout is speculative generalit... | ✗ | ✓ (MEDIUM) | ✗ | glm5.2 only |
| 20 | No nick length validation — memory exhaustion DoS | ✗ | ✓ (MEDIUM) | ✗ | glm5.2 only |
| 21 | Finding: Unsafe boundary crossing without validati... | ✗ | ✗ | ✓ (CRITICAL) | mistral only |
| 22 | Finding: Memory leak in client creation | ✗ | ✗ | ✓ (CRITICAL) | mistral only |
| 23 | Finding: Breaking documented behavior without migr... | ✗ | ✗ | ✓ (HIGH) | mistral only |
| 24 | Finding: Race condition in client cleanup | ✗ | ✗ | ✓ (HIGH) | mistral only |
| 25 | Finding: Undocumented workarounds | ✗ | ✗ | ✓ (HIGH) | mistral only |
| 26 | Finding: Special-case handling for rare or edge ca... | ✗ | ✗ | ✓ (MEDIUM) | mistral only |
| 27 | Finding: Duplicated logic | ✗ | ✗ | ✓ (MEDIUM) | mistral only |
| 28 | Finding: Inaccurate comments | ✗ | ✗ | ✓ (MEDIUM) | mistral only |
| 29 | Finding: Overly complex control flow | ✗ | ✗ | ✓ (MEDIUM) | mistral only |
| 30 | Finding: Dead or unnecessary code constructs | ✗ | ✗ | ✓ (LOW) | mistral only |

---

## Severity Disagreement Table

Cases where 2+ models found the same issue but assigned different severities:

| Issue | gpt-oss-120b | glm5.2 | mistral |
|-------|:---:|:---:|:---:|
| Ignored return value of `setsockopt()` i... | HIGH | — | LOW |
| Fatal assertion on recoverable condition | CRITICAL | HIGH | CRITICAL |
| Ignored return value of `write()` in bro... | HIGH | CRITICAL | — |
| Missing error handling for writes to cli... | HIGH | CRITICAL | CRITICAL |
| No bounds check on fd against MAX_CLIENT... | — | CRITICAL | HIGH |

---

## Trigger Coverage Comparison

Which skill triggers fired in each review:

| Trigger theme | gpt-oss-120b | glm5.2 | mistral |
|---------------|:---:|:---:|:---:|
| A fatal assertion, panic, or a... | ✗ | ✓ (2) | ✗ |
| A patch adds support for sizes... | ✗ | ✓ (1) | ✗ |
| A resource is freed while it m... | ✗ | ✓ (1) | ✗ |
| An error message that misdescr... | ✗ | ✓ (1) | ✗ |
| Breaking documented behavior o... | ✗ | ✗ | ✓ (1) |
| Code allocates memory but late... | ✗ | ✓ (1) | ✗ |
| Code uses an algorithm or data... | ✗ | ✓ (1) | ✗ |
| Dead or unnecessary code const... | ✗ | ✗ | ✓ (1) |
| Duplicating logic instead of f... | ✗ | ✗ | ✓ (1) |
| Error‑handling & return conven... | ✓ (6) | ✗ | ✗ |
| Fatal assertion used for a rec... | ✓ (1) | ✗ | ✗ |
| Fatal assertion/panic used for... | ✗ | ✗ | ✓ (1) |
| Hard-coded magic constants or ... | ✗ | ✗ | ✓ (1) |
| Hard-coded magic constants or ... | ✗ | ✗ | ✓ (1) |
| Hard‑coded magic constants wit... | ✓ (1) | ✗ | ✗ |
| Inaccurate or misleading comme... | ✗ | ✗ | ✓ (1) |
| Interfaces that return mislead... | ✗ | ✓ (1) | ✗ |
| Manual memory allocation/deall... | ✗ | ✗ | ✓ (1) |
| Manual resource cleanup instea... | ✗ | ✗ | ✓ (1) |
| Not validating boundary-crossi... | ✗ | ✗ | ✓ (1) |
| Obscure or non-descriptive nam... | ✗ | ✗ | ✓ (1) |
| Overly complex control flow | ✗ | ✗ | ✓ (1) |
| Premature abstraction or helpe... | ✗ | ✗ | ✓ (1) |
| Returning magic error codes in... | ✗ | ✗ | ✓ (1) |
| Security is ordinary bug-fixin... | ✗ | ✓ (1) | ✗ |
| Silent swallowing of serious e... | ✗ | ✗ | ✓ (1) |
| Special-case handling for rare... | ✗ | ✗ | ✓ (1) |
| Unbounded format‑string or buf... | ✓ (1) | ✗ | ✗ |
| Unbounded format‑string or buf... | ✓ (1) | ✗ | ✗ |
| Unsafe or untrusted boundary c... | ✗ | ✗ | ✓ (1) |
| Unsynchronized access to share... | ✗ | ✗ | ✓ (1) |

---

## With-Skill vs Baseline Comparison

For each model, comparing findings with the skill vs without (baseline):

| Model | Baseline Total | With-Skill Total | Baseline CRITICAL | With-Skill CRITICAL | Critical Overlap | Skill-Only CRITICAL | Baseline-Only CRITICAL | Skill Added Value |
|-------|----------------|------------------|-------------------|---------------------|------------------|---------------------|------------------------|-------------------|
| gpt-oss-120b | 20 | 10 | 4 | 2 | 1 | 1 | 3 | no (-2 net critical: 1 found, 3 lost) |
| glm5.2 | 35 | 9 | 2 | 4 | 0 | 4 | 2 | yes (+2 net critical: 4 found, 2 lost) |
| mistral | 19 | 18 | 7 | 4 | 2 | 2 | 5 | no (-3 net critical: 2 found, 5 lost) |

---

## Per-Model Bug Comparison (Baseline vs With-Skill)

Bug-by-bug comparison for each model: which bugs were found by both, only baseline, or only skill.

### gpt-oss-120b

**Same bugs (found in both):**

| Issue | File | Baseline | Skill | Severity changed? |
|-------|------|----------|-------|-------------------|
| Fatal assertion on recoverable condition | smallchat-server.c | CRITICAL | CRITICAL | no |
| Fixed‑size client table can overflow | smallchat-server.c | MEDIUM | CRITICAL | YES: MEDIUM→CRITICAL |
| Ignored result of `socketSetNonBlockNoDelay()` in `createCli... | smallchat-server.c | CRITICAL | HIGH | YES: CRITICAL→HIGH |
| Nick string not NUL‑terminated | smallchat-server.c | LOW | HIGH | YES: LOW→HIGH |
| Missing error handling for writes to client sockets (welcome... | smallchat-server.c | HIGH | HIGH | no |
| Ignored return value of `write()` when sending user input | smallchat-client.c | CRITICAL | HIGH | YES: CRITICAL→HIGH |
| No handling of `inputBufferAppend()` failure | smallchat-client.c | MEDIUM | HIGH | YES: MEDIUM→HIGH |
| Ignored return value of `setsockopt()` in `socketSetNonBlock... | chatlib.c | MEDIUM | HIGH | YES: MEDIUM→HIGH |

**Baseline-only (skill missed):**

| Issue | File | Severity | Skill trigger covers? |
|-------|------|----------|-----------------------|
| Unchecked `write()` may raise `SIGPIPE` and terminate the se... | smallchat-server.c | CRITICAL | out of scope |
| Ignoring return values of `write()` and `socketSetNonBlockNo... | smallchat-server.c | HIGH | out of scope |
| Partial writes are ignored | smallchat-server.c | MEDIUM | out of scope |
| Lack of error handling for `acceptClient()` | smallchat-server.c | LOW | Mixed error‑code conventions |
| Non‑blocking read errors are not handled | smallchat-client.c | HIGH | out of scope |
| Input buffer overflow handling is silent | smallchat-client.c | MEDIUM | Returning a pointer to a stack‑allocated buffer |
| No validation of command‑line arguments | smallchat-client.c | LOW | Skipping input validation on a boundary crossing |
| `make` does not enable `-Wextra` or `-pedantic` | chatlib.c | LOW | Comment that does not match code |
| `TCPConnect()` breaks out of the address‑iteration loop on `... | chatlib.c | MEDIUM | Out‑of‑tree code dictating core changes |
| No `#pragma` or attribute to silence unused‑parameter warnin... | chatlib.c | LOW | out of scope |
| Header lacks include guards for C++ compatibility | chatlib.h | LOW | out of scope |
| No `clean` rule removes object files; only binaries are dele... | chatlib.h | LOW | Missing reference‑count on shared object |

**Skill-only (skill added):**

| Issue | File | Severity | Trigger |
|-------|------|----------|---------|
| Ignored return value of `write()` in broadcast loop | smallchat-server.c | HIGH | Error‑handling & return conventions – mi... |
| Magic constant `MAX_CLIENTS` | smallchat-server.c | MEDIUM | Hard‑coded magic constants without docum... |

### glm5.2

**Same bugs (found in both):**

| Issue | File | Baseline | Skill | Severity changed? |
|-------|------|----------|-------|-------------------|
| select() exits on EINTR — any signal kills the server | smallchat-server.c | HIGH | CRITICAL | YES: HIGH→CRITICAL |

**Baseline-only (skill missed):**

| Issue | File | Severity | Skill trigger covers? |
|-------|------|----------|-----------------------|
| Out-of-bounds write when client fd >= MAX_CLIENTS | smallchat-server.c | CRITICAL | Out‑of‑tree code dictating core changes |
| `acceptClient` return value unchecked before `createClient` | smallchat-server.c | CRITICAL | Special‑case handling for a single value |
| Missing NUL terminator on initial nickname | smallchat-server.c | HIGH | Commit message missing rationale |
| No SIGPIPE handling — server dies on client disconnect | smallchat-server.c | HIGH | Special‑case handling for a single value |
| FD_SET / FD_SETSIZE overflow | smallchat-server.c | MEDIUM | out of scope |
| `write()` return values ignored in fan-out | smallchat-server.c | MEDIUM | Out‑of‑tree code dictating core changes |
| No validation/length cap on `/nick` argument | smallchat-server.c | MEDIUM | Skipping input validation on a boundary crossing |
| `freeClient` invalidates loop bound mid-iteration | smallchat-server.c | MEDIUM | Calling a virtual function inside a tight inner lo... |
| `socketSetNonBlockNoDelay` failure ignored | smallchat-server.c | LOW | out of scope |
| Hardcoded server port | smallchat-server.c | LOW | out of scope |
| `/nick` with no argument reports "Unsupported command" | smallchat-server.c | LOW | out of scope |
| `assert` in `createClient` compiled out in release | smallchat-server.c | LOW | Out‑of‑tree code dictating core changes |
| Client `select()` exits on EINTR | smallchat-client.c | HIGH | out of scope |
| No SIGPIPE handling in client | smallchat-client.c | HIGH | Special‑case handling for a single value |
| `inputBufferAppend` after `IB_GOTLINE` silently drops newlin... | smallchat-client.c | MEDIUM | Returning a pointer to a stack‑allocated buffer |
| `read()` from server not checked for partial/short reads on ... | smallchat-client.c | MEDIUM | out of scope |
| Terminal injection from server-relayed messages | smallchat-client.c | MEDIUM | out of scope |
| `setRawMode` static state is not fd-aware | smallchat-client.c | MEDIUM | out of scope |
| Backspace handling limited to DEL (127) | smallchat-client.c | LOW | Special‑case handling for a single value |
| No handling of arrow keys / escape sequences | smallchat-client.c | LOW | Special‑case handling for a single value |
| `close(s)` after `while(1)` is unreachable | smallchat-client.c | LOW | out of scope |
| `atoi(argv[2])` with no validation | smallchat-client.c | LOW | Skipping input validation on a boundary crossing |
| Sender sees both "you> " echo and server broadcast | smallchat-client.c | LOW | out of scope |
| `TCPConnect` leaks `addrinfo` on non-blocking EINPROGRESS | chatlib.c | MEDIUM | out of scope |
| `TCPConnect` non-blocking `connect` failure aborts remaining... | chatlib.c | MEDIUM | out of scope |
| `acceptClient` ignores peer address it collects | chatlib.c | MEDIUM | out of scope |
| `createTCPServer` is IPv4-only | chatlib.c | LOW | Introducing a new abstraction that is used only on... |
| `socketSetNonBlockNoDelay` does not preserve other `fcntl` f... | chatlib.c | LOW | Comment that does not match code |
| `chatRealloc` leaks original pointer on failure (moot due to... | chatlib.c | LOW | Returning a pointer to a stack‑allocated buffer |
| No `const` correctness on string parameters | chatlib.h | LOW | Unbounded format‑string or buffer‑size mismatch |
| No `extern "C"` guard for C++ consumers | chatlib.h | LOW | out of scope |
| `CFLAGS` placed after source files | chatlib.h | LOW | out of scope |
| Missing `.PHONY` declarations | chatlib.h | LOW | Commit message missing rationale |
| No `install` target, no dependency tracking | chatlib.h | LOW | out of scope |

**Skill-only (skill added):**

| Issue | File | Severity | Trigger |
|-------|------|----------|---------|
| No SIGPIPE handling — server crashes when writing to a disco... | smallchat-server.c | CRITICAL | Security is ordinary bug-fixing — "secur... |
| No bounds check on fd against MAX_CLIENTS — buffer overflow | smallchat-server.c | CRITICAL | A resource is freed while it may still b... |
| acceptClient return value not checked — createClient(-1) cor... | smallchat-server.c | CRITICAL | Code allocates memory but later cannot d... |
| assert in createClient for a recoverable condition — server ... | smallchat-server.c | HIGH | A fatal assertion, panic, or abort is us... |
| write() return values ignored on non-blocking sockets — mess... | smallchat-server.c | HIGH | Interfaces that return misleading or fab... |
| select() 1-second timeout is speculative generality — serves... | smallchat-server.c | MEDIUM | A patch adds support for sizes, ranges, ... |
| No nick length validation — memory exhaustion DoS | smallchat-server.c | MEDIUM | Code uses an algorithm or data structure... |
| /nick with no argument gives misleading "Unsupported command... | smallchat-client.c | MEDIUM | An error message that misdescribes the a... |

### mistral

**Same bugs (found in both):**

| Issue | File | Baseline | Skill | Severity changed? |
|-------|------|----------|-------|-------------------|
| Finding: Fatal assertion used for recoverable condition | smallchat-server.c | HIGH | CRITICAL | YES: HIGH→CRITICAL |
| Finding: Silent swallowing of serious errors | smallchat-server.c | CRITICAL | CRITICAL | no |
| Finding: Unsafe boundary crossing without validation | smallchat-server.c | CRITICAL | CRITICAL | no |
| Finding: Undocumented workarounds | smallchat-server.c | HIGH | HIGH | no |

**Baseline-only (skill missed):**

| Issue | File | Severity | Skill trigger covers? |
|-------|------|----------|-----------------------|
| Missing Error Handling in `socketSetNonBlockNoDelay()` | smallchat-server.c | MEDIUM | Mixed error‑code conventions |
| Hardcoded Limits | smallchat-server.c | MEDIUM | out of scope |
| Unused Variable | smallchat-client.c | LOW | out of scope |
| Terminal Escape Injection | smallchat-client.c | CRITICAL | out of scope |
| Buffer Overflow in `inputBufferFeedChar()` | smallchat-client.c | CRITICAL | Returning a pointer to a stack‑allocated buffer |
| Resource Leak in `setRawMode()` | smallchat-client.c | HIGH | out of scope |
| No Timeout for Server Reads | smallchat-client.c | MEDIUM | out of scope |
| Uninitialized `readbuf` in `main()` | chatlib.c | LOW | out of scope |
| Missing Error Handling in `TCPConnect()` | chatlib.c | CRITICAL | Mixed error‑code conventions |
| Race Condition in `acceptClient()` | chatlib.c | CRITICAL | out of scope |
| No IPv6 Support | chatlib.c | MEDIUM | out of scope |
| Unused Variable | chatlib.h | LOW | out of scope |
| Missing Documentation | chatlib.h | LOW | Commit message missing rationale |
| No Compiler Warnings for Implicit Functions | chatlib.h | CRITICAL | Reading a shared flag without atomic/implicit lang... |
| No Debug Symbols | chatlib.h | LOW | out of scope |

**Skill-only (skill added):**

| Issue | File | Severity | Trigger |
|-------|------|----------|---------|
| Finding: Memory leak in client creation | smallchat-server.c | CRITICAL | Manual memory allocation/deallocation wi... |
| Finding: Breaking documented behavior without migration path | smallchat-server.c | HIGH | Breaking documented behavior or public i... |
| Finding: Inconsistent error handling conventions | chatlib.c | HIGH | Returning magic error codes instead of t... |
| Finding: Potential buffer overflow in message handling | smallchat-server.c | HIGH | Hard-coded magic constants or unsafe sta... |
| Finding: Race condition in client cleanup | smallchat-server.c | HIGH | Unsynchronized access to shared mutable ... |
| Finding: Lack of input validation | smallchat-client.c | HIGH | Not validating boundary-crossing returns... |
| Finding: Resource leak in client cleanup | smallchat-client.c | HIGH | Manual resource cleanup instead of RAII/... |
| Finding: Special-case handling for rare or edge cases | smallchat-server.c | MEDIUM | Special-case handling for rare or edge c... |
| Finding: Duplicated logic | smallchat-server.c | MEDIUM | Duplicating logic instead of factoring i... |
| Finding: Premature abstraction | chatlib.c | MEDIUM | Premature abstraction or helper function... |
| Finding: Inaccurate comments | smallchat-server.c | MEDIUM | Inaccurate or misleading comments |
| Finding: Overly complex control flow | smallchat-server.c | MEDIUM | Overly complex control flow |
| Finding: Obscure or non-descriptive naming | chatlib.c | LOW | Obscure or non-descriptive naming |
| Finding: Dead or unnecessary code constructs | smallchat-server.c | LOW | Dead or unnecessary code constructs |

---

## Qualitative Analysis

### Consensus-Based Accuracy

Findings confirmed by 2+ models are treated as real bugs. Findings reported by only one model are unverified (could be real or false positive).

| Model | Total Findings | Confirmed (2+ models) | Unverified (1 model only) | Consensus Rate |
|-------|:--------------:|:---------------------:|:--------------------------:|:--------------:|
| gpt-oss-120b | 10 | 4 | 6 | 40% |
| glm5.2 | 9 | 4 | 5 | 44% |
| mistral | 18 | 4 | 14 | 22% |

### Severity Calibration

Cases where 2+ models found the same issue but assigned different severities:

| Issue | gpt-oss-120b | glm5.2 | mistral |
|-------|:---:|:---:|:---:|
| Ignored return value of `setsockopt()` i... | HIGH | — | LOW |
| Fatal assertion on recoverable condition | CRITICAL | HIGH | CRITICAL |
| Ignored return value of `write()` in bro... | HIGH | CRITICAL | — |
| Missing error handling for writes to cli... | HIGH | CRITICAL | CRITICAL |
| No bounds check on fd against MAX_CLIENT... | — | CRITICAL | HIGH |

Total severity disagreements: 5. Lower is better — it means the model's severity assessment aligns with the consensus.

### Unique Findings (Single-Model Discoveries)

Findings reported by only one model. These represent either unique insight or false positives:

| Model | Unique Findings |
|-------|:--------------:|
| gpt-oss-120b | 6 |
| glm5.2 | 5 |
| mistral | 14 |

A high unique count with a low consensus rate suggests false positives. A high unique count with a high consensus rate suggests the model found real bugs others missed.

### With-Skill vs Baseline: Skill Impact

How the skill changed each model's review:

**gpt-oss-120b:** Baseline 20 findings (4 CRITICAL) → With-skill 10 findings (2 CRITICAL). Skill found 1 critical bug(s) the baseline missed; baseline found 3 critical bug(s) the skill missed.

**glm5.2:** Baseline 35 findings (2 CRITICAL) → With-skill 9 findings (4 CRITICAL). Skill found 4 critical bug(s) the baseline missed; baseline found 2 critical bug(s) the skill missed.

**mistral:** Baseline 19 findings (7 CRITICAL) → With-skill 18 findings (4 CRITICAL). Skill found 2 critical bug(s) the baseline missed; baseline found 5 critical bug(s) the skill missed.

#### Skill Tradeoff Analysis

The skill narrows reviewer focus toward memory-safety and correctness (Linus's priorities). This filters noise but can also suppress valid findings. Net critical impact per model:

| Model | Skill-Only CRITICAL | Baseline-Only CRITICAL | Net Critical Impact | Total Finding Delta |
|-------|:-------------------:|:----------------------:|:-------------------:|:-------------------:|
| gpt-oss-120b | 1 | 3 | -2 | -10 |
| glm5.2 | 4 | 2 | +2 | -26 |
| mistral | 2 | 5 | -3 | -1 |

**Interpretation:** A positive net critical impact means the skill found real bugs the baseline missed. A negative value means the skill suppressed critical findings the baseline caught — a coverage gap. A large negative total finding delta with neutral critical impact means the skill filtered noise without losing signal.

**Per-model read:**
- **gpt-oss-120b:** Net negative on critical coverage. The skill cut 10 findings and suppressed 3 critical(s) the baseline caught, while only adding 1 new critical. The skill narrowed focus too aggressively — the 3 lost critical(s) are a real coverage gap worth investigating.
- **glm5.2:** Net positive. The skill cut 26 findings and added 2 critical bug(s) the baseline missed.
- **mistral:** Net negative on critical coverage. The skill cut 1 findings and suppressed 5 critical(s) the baseline caught, while only adding 2 new critical. The skill narrowed focus too aggressively — the 5 lost critical(s) are a real coverage gap worth investigating.

### Trigger Coverage Analysis

Which skill triggers each model fired:

**gpt-oss-120b:** 5 distinct triggers fired, 10 total trigger firings.
  Top triggers: Error‑handling & return conventions – missing error handling (6x), Fatal assertion used for a recoverable error (1x), Unbounded format‑string or buffer‑size mismatch (applied to array bounds) (1x)

**glm5.2:** 8 distinct triggers fired, 9 total trigger firings.
  Top triggers: A fatal assertion, panic, or abort is used for a condition that could be handled gracefully by returning an error or falling back to a safe path (2x), Security is ordinary bug-fixing — "security is bugs" (1x), A resource is freed while it may still be referenced as part of a data structure, or a code path exists that may free the same resource twice (memory safety) (1x)

**mistral:** 18 distinct triggers fired, 18 total trigger firings.
  Top triggers: Fatal assertion/panic used for a recoverable condition (1x), Silent swallowing of serious errors (1x), Unsafe or untrusted boundary crossing without validation (1x)

### Verdict

Based on consensus-confirmed CRITICAL findings, net critical impact (skill-only minus baseline-only), and severity calibration:

| Model | Confirmed CRITICAL | Skill-Only CRITICAL | Baseline-Only CRITICAL | Net Critical | Severity Disagreements | Score |
|-------|:------------------:|:-------------------:|:----------------------:|:-------------:|:----------------------:|:-----:|
| gpt-oss-120b | 1 | 1 | 3 | -2 | 4 | -5 |
| glm5.2 | 3 | 4 | 2 | +2 | 4 | 1 |
| mistral | 2 | 2 | 5 | -3 | 4 | -5 |

**Scoring:** `confirmed_critical + skill_only_critical - baseline_only_critical - severity_disagreements`. All terms are CRITICAL-only for unit consistency. The baseline-only penalty makes coverage gaps visible: a model that suppresses real bugs the baseline caught scores lower, even if it found other bugs the baseline missed.

**Honest read:** 
glm5.2 wins clearly with score 1. 
gpt-oss-120b follows at -5.
 The skill helps differently per model — see the per-model read above for the tradeoff details.
