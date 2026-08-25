---
title: Model Comparison — SmallChat Review
date: 2026-08-25
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
| gpt-oss-120b | 9 | 1 | 0 | Skill reduces coverage |
| glm5.2 | 17 | 1 | 1 | Skill adds value |
| mistral | 10 | 3 | 2 | Skill reduces coverage |

The skill adds the most value for mistral, which gained 2 critical finding(s) exclusive to the with-skill review.

3 models reviewed the same C codebase (antirez/smallchat, ~706 LOC) using the same language-agnostic Linus Torvalds skill. This document cross-references their findings at the issue level — not just counts — to measure consensus, accuracy, and severity calibration.

## Metrics Summary

| Metric | gpt-oss-120b | glm5.2 | mistral |
|--------|:---:|:---:|:---:|
| Findings | 9 | 17 | 10 |
| Critical | 1 | 1 | 3 |
| High | 2 | 6 | 4 |
| Medium | 2 | 8 | 2 |
| Low | 4 | 2 | 1 |
| Words | 700 | 2825 | 1531 |

**Key insight:** Finding count is a poor quality signal. The consensus matrix below shows which models caught which bugs — and that is where the real signal lives.

---

## Finding Consensus Matrix

Every finding from all three reviews, mapped to the underlying issue. ✓ = found, ✗ = missed. Severity shown in parentheses.

### chatlib.c

| # | Issue | gpt-oss-120b | glm5.2 | mistral | Consensus |
|---|:---:|:---:|:---:|:---:|
| 1 | TCPConnect leaks the addrinfo list on the non-bloc... | ✗ | ✓ (HIGH) | ✗ | glm5.2 only |
| 2 | Comment documents retry-on-connect-failure; code b... | ✗ | ✓ (HIGH) | ✗ | glm5.2 only |
| 3 | chatMalloc and chatRealloc abort the process on ou... | ✗ | ✓ (MEDIUM) | ✗ | glm5.2 only |

### chatlib.h

| # | Issue | gpt-oss-120b | glm5.2 | mistral | Consensus |
|---|:---:|:---:|:---:|:---:|
| 4 | TCPConnect special-cases a nonblock flag that crea... | ✗ | ✓ (HIGH) | ✗ | glm5.2 only |

### smallchat-client.c

| # | Issue | gpt-oss-120b | glm5.2 | mistral | Consensus |
|---|:---:|:---:|:---:|:---:|
| 5 | select() treats EINTR as fatal, crashing the clien... | ✗ | ✓ (HIGH) | ✗ | glm5.2 only |
| 6 | read() on stdin does not check for EOF or error, c... | ✗ | ✓ (MEDIUM) | ✗ | glm5.2 only |
| 7 | setRawMode() return value ignored — failure silent... | ✗ | ✓ (MEDIUM) | ✗ | glm5.2 only |
| 8 | write() to the server ignores short writes and err... | ✗ | ✓ (MEDIUM) | ✗ | glm5.2 only |
| 9 | Buffer-full silently drops input; on a full buffer... | ✗ | ✓ (MEDIUM) | ✗ | glm5.2 only |
| 10 | Comment contradicts code in the raw-mode disable p... | ✗ | ✓ (LOW) | ✗ | glm5.2 only |
| 11 | Finding: Stale comment in client code | ✗ | ✗ | ✓ (LOW) | mistral only |

### smallchat-server.c

| # | Issue | gpt-oss-120b | glm5.2 | mistral | Consensus |
|---|:---:|:---:|:---:|:---:|
| 12 | exit(1) on select() EINTR — recoverable signal int... | ✗ | ✓ (HIGH) | ✓ (MEDIUM) | 2/3 |
| 13 | MAX_CLIENTS name contradicts its actual purpose | ✗ | ✓ (LOW) | ✓ (HIGH) | 2/3 |
| 14 | No bounds check on fd before array indexing — out-... | ✗ | ✓ (CRITICAL) | ✗ | glm5.2 only |
| 15 | write() return values discarded — silent message l... | ✗ | ✓ (MEDIUM) | ✗ | glm5.2 only |
| 16 | socketSetNonBlockNoDelay failure ignored — socket ... | ✗ | ✓ (MEDIUM) | ✗ | glm5.2 only |
| 17 | Finding: Buffer overflow risk in client nickname h... | ✗ | ✗ | ✓ (CRITICAL) | mistral only |
| 18 | Finding: Race condition in client list management | ✗ | ✗ | ✓ (CRITICAL) | mistral only |
| 19 | Finding: Memory leak in client nickname handling | ✗ | ✗ | ✓ (CRITICAL) | mistral only |
| 20 | Finding: No input validation in nickname command | ✗ | ✗ | ✓ (HIGH) | mistral only |
| 21 | Finding: No error handling for socket operations | ✗ | ✗ | ✓ (HIGH) | mistral only |
| 22 | Finding: No bounds checking in message relay | ✗ | ✗ | ✓ (HIGH) | mistral only |
| 23 | Finding: Magic number for max clients | ✗ | ✗ | ✓ (MEDIUM) | mistral only |

### unspecified

| # | Issue | gpt-oss-120b | glm5.2 | mistral | Consensus |
|---|:---:|:---:|:---:|:---:|
| 24 | Missing null‑termination for client nickname | ✓ (CRITICAL) | ✗ | ✗ | gpt-oss-120b only |
| 25 | Unchecked `write` in `sendMsgToAllClientsBut` | ✓ (HIGH) | ✗ | ✗ | gpt-oss-120b only |
| 26 | No buffering for partial client messages | ✓ (MEDIUM) | ✗ | ✗ | gpt-oss-120b only |
| 27 | Magic number `MAX_CLIENTS` | ✓ (LOW) | ✗ | ✗ | gpt-oss-120b only |
| 28 | Unchecked `write` to server socket | ✓ (HIGH) | ✗ | ✗ | gpt-oss-120b only |
| 29 | No handling of partial reads from server | ✓ (MEDIUM) | ✗ | ✗ | gpt-oss-120b only |
| 30 | Fixed input buffer size (`IB_MAX 128`) | ✓ (LOW) | ✗ | ✗ | gpt-oss-120b only |
| 31 | Ignored error from `setsockopt` in `socketSetNonBl... | ✓ (LOW) | ✗ | ✗ | gpt-oss-120b only |
| 32 | No `SO_REUSEPORT` in `createTCPServer` | ✓ (LOW) | ✗ | ✗ | gpt-oss-120b only |
| 33 | Missing header file dependencies produce silently ... | ✗ | ✓ (HIGH) | ✗ | glm5.2 only |
| 34 | Phony targets not declared with .PHONY | ✗ | ✓ (MEDIUM) | ✗ | glm5.2 only |

---

## Severity Disagreement Table

Cases where 2+ models found the same issue but assigned different severities:

| Issue | gpt-oss-120b | glm5.2 | mistral |
|-------|:---:|:---:|:---:|
| exit(1) on select() EINTR — recoverable ... | — | HIGH | MEDIUM |
| MAX_CLIENTS name contradicts its actual ... | — | LOW | HIGH |

---

## Trigger Coverage Comparison

Which skill triggers fired in each review:

| Trigger theme | gpt-oss-120b | glm5.2 | mistral |
|---------------|:---:|:---:|:---:|
| Code that aborts or traps on r... | ✗ | ✗ | ✓ (1) |
| Code that may double-free or f... | ✗ | ✗ | ✓ (1) |
| Code that performs non-atomic ... | ✗ | ✗ | ✓ (2) |
| Code that sets a timeout for s... | ✗ | ✗ | ✓ (1) |
| Code that uses magic numbers w... | ✗ | ✗ | ✓ (1) |
| Code that uses unsafe APIs (e.... | ✗ | ✗ | ✓ (1) |
| Comment or documentation does ... | ✗ | ✓ (3) | ✗ |
| Comments reference outdated or... | ✗ | ✗ | ✓ (1) |
| Fatal crash or abort used for ... | ✗ | ✓ (4) | ✗ |
| Function returns a value that ... | ✗ | ✓ (7) | ✗ |
| Functions that assume callers ... | ✗ | ✗ | ✓ (1) |
| General‑guideline – Add config... | ✓ (2) | ✗ | ✗ |
| General‑guideline – Add config... | ✓ (1) | ✗ | ✗ |
| Invariant‑false – Excessive st... | ✓ (1) | ✗ | ✗ |
| Invariant‑false – Fatal aborts... | ✓ (1) | ✗ | ✗ |
| Invariant‑false – Fatal aborts... | ✓ (2) | ✗ | ✗ |
| Invariant‑false – Inconsistent... | ✓ (1) | ✗ | ✗ |
| Invariant‑true – Fatal aborts ... | ✓ (1) | ✗ | ✗ |
| Misleading or false informatio... | ✗ | ✓ (1) | ✗ |
| Public interfaces leak interna... | ✗ | ✗ | ✓ (1) |
| Resource released while it may... | ✗ | ✓ (1) | ✗ |
| Single API function special-ca... | ✗ | ✓ (1) | ✗ |

---

## With-Skill vs Baseline Comparison

For each model, comparing findings with the skill vs without (baseline):

| Model | Baseline Total | With-Skill Total | Baseline CRITICAL | With-Skill CRITICAL | Critical Overlap | Skill-Only CRITICAL | Baseline-Only CRITICAL | Skill Added Value |
|-------|----------------|------------------|-------------------|---------------------|------------------|---------------------|------------------------|-------------------|
| gpt-oss-120b | 19 | 9 | 2 | 1 | 0 | 0 | 2 | no (-2 net critical: 0 found, 2 lost) |
| glm5.2 | 34 | 17 | 1 | 1 | 0 | 1 | 1 | neutral (0 net: 1 found, 1 lost) |
| mistral | 15 | 10 | 3 | 3 | 0 | 2 | 3 | no (-1 net critical: 2 found, 3 lost) |

---

## Qualitative Analysis

### Consensus-Based Accuracy

Findings confirmed by 2+ models are treated as real bugs. Findings reported by only one model are unverified (could be real or false positive).

| Model | Total Findings | Confirmed (2+ models) | Unverified (1 model only) | Consensus Rate |
|-------|:--------------:|:---------------------:|:--------------------------:|:--------------:|
| gpt-oss-120b | 9 | 0 | 9 | 0% |
| glm5.2 | 17 | 2 | 15 | 12% |
| mistral | 10 | 2 | 8 | 20% |

### Severity Calibration

Cases where 2+ models found the same issue but assigned different severities:

| Issue | gpt-oss-120b | glm5.2 | mistral |
|-------|:---:|:---:|:---:|
| exit(1) on select() EINTR — recoverable ... | — | HIGH | MEDIUM |
| MAX_CLIENTS name contradicts its actual ... | — | LOW | HIGH |

Total severity disagreements: 2. Lower is better — it means the model's severity assessment aligns with the consensus.

### Unique Findings (Single-Model Discoveries)

Findings reported by only one model. These represent either unique insight or false positives:

| Model | Unique Findings |
|-------|:--------------:|
| gpt-oss-120b | 9 |
| glm5.2 | 15 |
| mistral | 8 |

A high unique count with a low consensus rate suggests false positives. A high unique count with a high consensus rate suggests the model found real bugs others missed.

### With-Skill vs Baseline: Skill Impact

How the skill changed each model's review:

**gpt-oss-120b:** Baseline 19 findings (2 CRITICAL) → With-skill 9 findings (1 CRITICAL). Skill found 0 critical bug(s) the baseline missed; baseline found 2 critical bug(s) the skill missed.

**glm5.2:** Baseline 34 findings (1 CRITICAL) → With-skill 17 findings (1 CRITICAL). Skill found 1 critical bug(s) the baseline missed; baseline found 1 critical bug(s) the skill missed.

**mistral:** Baseline 15 findings (3 CRITICAL) → With-skill 10 findings (3 CRITICAL). Skill found 2 critical bug(s) the baseline missed; baseline found 3 critical bug(s) the skill missed.

#### Skill Tradeoff Analysis

The skill narrows reviewer focus toward memory-safety and correctness (Linus's priorities). This filters noise but can also suppress valid findings. Net critical impact per model:

| Model | Skill-Only CRITICAL | Baseline-Only CRITICAL | Net Critical Impact | Total Finding Delta |
|-------|:-------------------:|:----------------------:|:-------------------:|:-------------------:|
| gpt-oss-120b | 0 | 2 | -2 | -10 |
| glm5.2 | 1 | 1 | 0 | -17 |
| mistral | 2 | 3 | -1 | -5 |

**Interpretation:** A positive net critical impact means the skill found real bugs the baseline missed. A negative value means the skill suppressed critical findings the baseline caught — a coverage gap. A large negative total finding delta with neutral critical impact means the skill filtered noise without losing signal.

**Per-model read:**
- **gpt-oss-120b:** Net negative on critical coverage. The skill cut 10 findings and suppressed 2 critical(s) the baseline caught, while only adding 0 new critical. The skill narrowed focus too aggressively — the 2 lost critical(s) are a real coverage gap worth investigating.
- **glm5.2:** Neutral on criticals. The skill filtered noise (cut 17 findings) without losing critical coverage.
- **mistral:** Net negative on critical coverage. The skill cut 5 findings and suppressed 3 critical(s) the baseline caught, while only adding 2 new critical. The skill narrowed focus too aggressively — the 3 lost critical(s) are a real coverage gap worth investigating.

### Trigger Coverage Analysis

Which skill triggers each model fired:

**gpt-oss-120b:** 7 distinct triggers fired, 9 total trigger firings.
  Top triggers: Invariant‑false – Fatal aborts for recoverable conditions (2x), General‑guideline – Add configuration knobs only when there is documented demand (2x), Invariant‑true – Fatal aborts for recoverable conditions (used here to flag a correctness‑critical undefined behaviour) (1x)

**glm5.2:** 6 distinct triggers fired, 17 total trigger firings.
  Top triggers: Function returns a value that is indistinguishable from a successful return (7x), Fatal crash or abort used for a recoverable error condition (4x), Comment or documentation does not match actual code behavior (3x)

**mistral:** 9 distinct triggers fired, 10 total trigger firings.
  Top triggers: Code that performs non-atomic operations on shared data without synchronization (2x), Code that uses unsafe APIs (e.g., `strlcpy()`) in hardening code (1x), Code that may double-free or free resources still in use (1x)

### Verdict

Based on consensus-confirmed CRITICAL findings, net critical impact (skill-only minus baseline-only), and severity calibration:

| Model | Confirmed CRITICAL | Skill-Only CRITICAL | Baseline-Only CRITICAL | Net Critical | Severity Disagreements | Score |
|-------|:------------------:|:-------------------:|:----------------------:|:-------------:|:----------------------:|:-----:|
| gpt-oss-120b | 0 | 0 | 2 | -2 | 0 | -2 |
| glm5.2 | 0 | 1 | 1 | 0 | 2 | -2 |
| mistral | 0 | 2 | 3 | -1 | 2 | -3 |

**Scoring:** `confirmed_critical + skill_only_critical - baseline_only_critical - severity_disagreements`. All terms are CRITICAL-only for unit consistency. The baseline-only penalty makes coverage gaps visible: a model that suppresses real bugs the baseline caught scores lower, even if it found other bugs the baseline missed.

**Honest read:** 
gpt-oss-120b, glm5.2 tie for the top score (-2). The skill helps differently per model — see the per-model read above for the tradeoff details.
