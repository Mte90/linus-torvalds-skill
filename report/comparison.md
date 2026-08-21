---
title: Model Comparison — SmallChat Review
date: 2026-08-21
codebase: antirez/smallchat
models: gpt-oss-120b, glm5.2, mistral-small-4-119b
skill: linus-torvalds-skill (language-agnostic)
method: static review, skill triggers applied per source file
---

# Model Comparison — SmallChat Review

Three models reviewed the same C codebase (antirez/smallchat, ~706 LOC) using the same language-agnostic Linus Torvalds skill and soul. This document cross-references their findings at the issue level — not just counts — to measure consensus, accuracy, and severity calibration.

## Metrics Summary

| Metric | gpt-oss-120b | glm5.2 | mistral |
|--------|:------------:|:------:|:-------:|
| Findings | 14 | 24 | 8 |
| Critical | 2 | 2 | 0 |
| High | 7 | 7 | 2 |
| Medium | 4 | 9 | 3 |
| Low | 1 | 6 | 3 |
| Words | 1254 | 3989 | 2010 |

**Key insight:** Finding count is a poor quality signal. The consensus matrix below shows which models caught which bugs — and that is where the real signal lives.

---

## Finding Consensus Matrix

Every finding from all three reviews, mapped to the underlying issue. ✓ = found, ✗ = missed. Severity shown in parentheses.

### chatlib.c

| # | Issue | gpt-oss | glm5.2 | mistral | Consensus |
|---|-------|:-------:|:------:|:-------:|:---------:|
| 1 | Allocators abort the process on out-of-memory | ✗ | ✓ (HIGH) | ✗ | glm5.2 only |
| 2 | TCPConnect leaks addrinfo on non-blocking connect ... | ✗ | ✓ (MEDIUM) | ✗ | glm5.2 only |

### chatlib.h

| # | Issue | gpt-oss | glm5.2 | mistral | Consensus |
|---|-------|:-------:|:------:|:-------:|:---------:|
| 3 | Header not self-contained — `size_t` used without ... | ✓ (MEDIUM) | ✓ (MEDIUM) | ✗ | 2/3 |
| 4 | `TCPConnect` parameter `addr` should be `const cha... | ✗ | ✓ (MEDIUM) | ✗ | glm5.2 only |
| 5 | `nonblock` boolean flag should be a discriminated ... | ✗ | ✓ (LOW) | ✗ | glm5.2 only |
| 6 | Inconsistent naming convention across the API surf... | ✗ | ✓ (LOW) | ✗ | glm5.2 only |
| 7 | Style Issues | ✗ | ✗ | ✓ (LOW) | mistral only |

### smallchat-client.c

| # | Issue | gpt-oss | glm5.2 | mistral | Consensus |
|---|-------|:-------:|:------:|:-------:|:---------:|
| 8 | select() exits on EINTR instead of retrying | ✗ | ✓ (HIGH) | ✗ | glm5.2 only |
| 9 | stdin read() return value unchecked; EOF causes bu... | ✗ | ✓ (HIGH) | ✗ | glm5.2 only |
| 10 | setRawMode() return value ignored | ✓ (MEDIUM) | ✓ (MEDIUM) | ✗ | 2/3 |
| 11 | write() to server socket unchecked; user messages ... | ✗ | ✓ (MEDIUM) | ✗ | glm5.2 only |
| 12 | Dead code after infinite loop | ✗ | ✓ (LOW) | ✓ (LOW) | 2/3 |
| 13 | Misleading comment contradicts the code | ✗ | ✓ (LOW) | ✓ (MEDIUM) | 2/3 |
| 14 | errno overwritten with ENOTTY regardless of actual... | ✗ | ✓ (LOW) | ✗ | glm5.2 only |
| 15 | Missing error handling for write calls | ✓ (MEDIUM) | ✗ | ✗ | gpt-oss only |
| 16 | Magic Constants and Hardcoded Values | ✗ | ✗ | ✓ (HIGH) | mistral only |
| 17 | Special Case Handling in inputBufferFeedChar | ✗ | ✗ | ✓ (HIGH) | mistral only |
| 18 | Fragile Functions Without Input Validation | ✗ | ✗ | ✓ (MEDIUM) | mistral only |
| 19 | Inconsistent Error Handling | ✗ | ✗ | ✓ (MEDIUM) | mistral only |
| 20 | Misleading Comments | ✗ | ✗ | ✓ (LOW) | mistral only |

### smallchat-server.c

| # | Issue | gpt-oss | glm5.2 | mistral | Consensus |
|---|-------|:-------:|:------:|:-------:|:---------:|
| 21 | No bounds check on file descriptor before array ac... | ✓ (CRITICAL) | ✓ (CRITICAL) | ✗ | 2/3 |
| 22 | assert() used for runtime condition — disappears i... | ✓ (HIGH) | ✓ (CRITICAL) | ✗ | 2/3 |
| 23 | read() treats EAGAIN as disconnection on non-block... | ✓ (HIGH) | ✓ (HIGH) | ✗ | 2/3 |
| 24 | select() error causes server exit — EINTR is recov... | ✗ | ✓ (HIGH) | ✗ | glm5.2 only |
| 25 | socketSetNonBlockNoDelay return value ignored — se... | ✓ (HIGH) | ✓ (HIGH) | ✗ | 2/3 |
| 26 | select()/FD_SET vulnerable to FD_SETSIZE overflow | ✗ | ✓ (MEDIUM) | ✗ | glm5.2 only |
| 27 | write() return values ignored — messages silently ... | ✗ | ✓ (MEDIUM) | ✗ | glm5.2 only |
| 28 | Misleading comment on MAX_CLIENTS | ✓ (MEDIUM) | ✓ (MEDIUM) | ✗ | 2/3 |
| 29 | maxclient recalculation is a special case created ... | ✗ | ✓ (LOW) | ✗ | glm5.2 only |
| 30 | Missing NUL-termination of generated nickname | ✓ (HIGH) | ✗ | ✗ | gpt-oss only |
| 31 | No validation of user-provided nickname length | ✓ (HIGH) | ✗ | ✗ | gpt-oss only |
| 32 | Potential out-of-bounds access of `Chat->clients` ... | ✓ (HIGH) | ✗ | ✗ | gpt-oss only |

### unspecified

| # | Issue | gpt-oss | glm5.2 | mistral | Consensus |
|---|-------|:-------:|:------:|:-------:|:---------:|
| 33 | Missing header dependency: `chatlib.h` not tracked... | ✓ (CRITICAL) | ✓ (HIGH) | ✗ | 2/3 |
| 34 | Phony targets `all` and `clean` not declared with ... | ✓ (LOW) | ✓ (MEDIUM) | ✗ | 2/3 |
| 35 | No allocation-failure checks for `chatMalloc` | ✓ (HIGH) | ✗ | ✗ | gpt-oss only |

---

## Severity Disagreement Table

Cases where 2+ models found the same issue but assigned different severities:

| Issue | gpt-oss | glm5.2 | mistral |
|-------|:-------:|:------:|:-------:|
| Misleading comment contradicts the code | — | LOW | MEDIUM |
| assert() used for runtime condition — di... | HIGH | CRITICAL | — |
| Missing header dependency: `chatlib.h` n... | CRITICAL | HIGH | — |
| Phony targets `all` and `clean` not decl... | LOW | MEDIUM | — |

---

## Trigger Coverage Comparison

Which skill triggers fired in each review:

| Trigger theme | gpt-oss | glm5.2 | mistral |
|---------------|:-------:|:------:|:-------:|
| "Code is binary — it works or ... | ✗ | ✓ (1) | ✗ |
| 7.2 | ✓ (2) | ✗ | ✗ |
| Code contains a conditional br... | ✗ | ✓ (1) | ✗ |
| Code either works or it doesn'... | ✗ | ✓ (1) | ✗ |
| Comment that does not match th... | ✗ | ✓ (2) | ✗ |
| Dead or unused code paths reta... | ✗ | ✓ (1) | ✗ |
| Enforce consistent naming, ind... | ✗ | ✓ (1) | ✗ |
| Error handling path that masks... | ✗ | ✓ (1) | ✗ |
| Error handling path that masks... | ✗ | ✓ (1) | ✗ |
| Error handling that aborts or ... | ✗ | ✓ (3) | ✗ |
| Error or diagnostic message th... | ✗ | ✓ (1) | ✗ |
| Every allocated resource must ... | ✗ | ✓ (1) | ✗ |
| Fatal assertion or crash used ... | ✗ | ✓ (1) | ✗ |
| Fatal assertion or crash used ... | ✗ | ✓ (1) | ✗ |
| Function returns a value that ... | ✗ | ✓ (2) | ✗ |
| Internal implementation detail... | ✗ | ✓ (1) | ✗ |
| Prefer discriminated types ove... | ✗ | ✓ (1) | ✗ |
| Shared mutable data accessed w... | ✗ | ✓ (1) | ✗ |
| Silent error swallowing (anti-... | ✗ | ✓ (2) | ✗ |
| Silent error swallowing (anti-... | ✗ | ✓ (1) | ✗ |
| Trigger 1.3 – hard-coded magic... | ✓ (2) | ✗ | ✗ |
| Trigger 2.2 | ✓ (1) | ✗ | ✗ |
| Trigger 7.2 – operation withou... | ✓ (6) | ✗ | ✗ |
| Trigger 7.4 – fatal assertions... | ✓ (1) | ✗ | ✗ |
| non‑file targets without .PHON... | ✓ (1) | ✗ | ✗ |
| unnecessary duplicate compiler... | ✓ (1) | ✗ | ✗ |

---

## With-Skill vs Baseline Comparison

For each model, comparing findings with the skill vs without (baseline):

| Model | Baseline Total | With-Skill Total | Baseline CRITICAL | With-Skill CRITICAL | Critical Overlap | Skill-Only CRITICAL | Baseline-Only CRITICAL | Skill Added Value |
|-------|----------------|------------------|-------------------|---------------------|------------------|---------------------|------------------------|-------------------|
| gpt-oss-120b | 0 | 14 | 0 | 2 | 0 | 1 | 0 | yes (+1 net critical: 1 found, 0 lost) |
| glm5.2 | 25 | 24 | 2 | 2 | 1 | 0 | 1 | no (-1 net critical: 0 found, 1 lost) |
| mistral | 21 | 8 | 1 | 0 | 0 | 0 | 1 | no (-1 net critical: 0 found, 1 lost) |

---

## Qualitative Analysis

### Consensus-Based Accuracy

Findings confirmed by 2+ models are treated as real bugs. Findings reported by only one model are unverified (could be real or false positive).

| Model | Total Findings | Confirmed (2+ models) | Unverified (1 model only) | Consensus Rate |
|-------|:--------------:|:---------------------:|:--------------------------:|:--------------:|
| gpt-oss-120b | 14 | 9 | 5 | 64% |
| glm5.2 | 24 | 11 | 13 | 46% |
| mistral | 8 | 2 | 6 | 25% |

### Severity Calibration

Cases where 2+ models found the same issue but assigned different severities:

| Issue | gpt-oss | glm5.2 | mistral |
|-------|:-------:|:------:|:-------:|
| Misleading comment contradicts the code | — | LOW | MEDIUM |
| assert() used for runtime condition — di... | HIGH | CRITICAL | — |
| Missing header dependency: `chatlib.h` n... | CRITICAL | HIGH | — |
| Phony targets `all` and `clean` not decl... | LOW | MEDIUM | — |

Total severity disagreements: 4. Lower is better — it means the model's severity assessment aligns with the consensus.

### Unique Findings (Single-Model Discoveries)

Findings reported by only one model. These represent either unique insight or false positives:

| Model | Unique Findings |
|-------|:--------------:|
| gpt-oss-120b | 5 |
| glm5.2 | 13 |
| mistral | 6 |

A high unique count with a low consensus rate suggests false positives. A high unique count with a high consensus rate suggests the model found real bugs others missed.

### With-Skill vs Baseline: Skill Impact

How the skill changed each model's review:

**gpt-oss-120b:** Baseline 0 findings (0 CRITICAL) → With-skill 14 findings (2 CRITICAL). Skill found 1 critical bug(s) the baseline missed; baseline found 0 critical bug(s) the skill missed.

**glm5.2:** Baseline 25 findings (2 CRITICAL) → With-skill 24 findings (2 CRITICAL). Skill found 0 critical bug(s) the baseline missed; baseline found 1 critical bug(s) the skill missed.

**mistral:** Baseline 21 findings (1 CRITICAL) → With-skill 8 findings (0 CRITICAL). Skill found 0 critical bug(s) the baseline missed; baseline found 1 critical bug(s) the skill missed.

#### Skill Tradeoff Analysis

The skill narrows reviewer focus toward memory-safety and correctness (Linus's priorities). This filters noise but can also suppress valid findings. Net critical impact per model:

| Model | Skill-Only CRITICAL | Baseline-Only CRITICAL | Net Critical Impact | Total Finding Delta |
|-------|:-------------------:|:----------------------:|:-------------------:|:-------------------:|
| gpt-oss-120b | 1 | 0 | +1 | +14 |
| glm5.2 | 0 | 1 | -1 | -1 |
| mistral | 0 | 1 | -1 | -13 |

**Interpretation:** A positive net critical impact means the skill found real bugs the baseline missed. A negative value means the skill suppressed critical findings the baseline caught — a coverage gap. A large negative total finding delta with neutral critical impact means the skill filtered noise without losing signal.

**Per-model read:**
- **gpt-oss-120b:** Clear win. Baseline found nothing; skill added 1 critical bug(s). The skill unlocked review capability this model didn't have without it.
- **glm5.2:** Net negative on critical coverage. The skill cut 1 findings and suppressed 1 critical(s) the baseline caught, while only adding 0 new critical. The skill narrowed focus too aggressively — the 1 lost critical(s) are a real coverage gap worth investigating.
- **mistral:** Net negative on critical coverage. The skill cut 13 findings and suppressed 1 critical(s) the baseline caught, while only adding 0 new critical. The skill narrowed focus too aggressively — the 1 lost critical(s) are a real coverage gap worth investigating.

### Trigger Coverage Analysis

Which skill triggers each model fired:

**gpt-oss-120b:** 7 distinct triggers fired, 14 total trigger firings.
  Top triggers: Trigger 7.2 – operation without first checking that the target object is in a permissible state (6x), Trigger 1.3 – hard-coded magic numbers, fixed physical addresses, or platform-specific constants (2x), 7.2 (2x)

**glm5.2:** 19 distinct triggers fired, 24 total trigger firings.
  Top triggers: Error handling that aborts or traps on a recoverable condition instead of returning an error (3x), Comment that does not match the code's actual behavior (2x), Silent error swallowing (anti-pattern) (2x)

**mistral:** 0 distinct triggers fired, 0 total trigger firings.

### Verdict

Based on consensus-confirmed findings, net critical impact (skill-only minus baseline-only), and severity calibration:

| Model | Confirmed | Skill-Only CRITICAL | Baseline-Only CRITICAL | Net Critical | Severity Disagreements | Score |
|-------|:---------:|:-------------------:|:----------------------:|:-------------:|:----------------------:|:-----:|
| gpt-oss-120b | 9 | 1 | 0 | +1 | 3 | 7 |
| glm5.2 | 11 | 0 | 1 | -1 | 4 | 6 |
| mistral | 2 | 0 | 1 | -1 | 1 | 0 |

**Scoring:** `confirmed + skill_only_critical - baseline_only_critical - severity_disagreements`. The baseline-only penalty makes coverage gaps visible: a model that suppresses real bugs the baseline caught scores lower, even if it found other bugs the baseline missed.

**Honest read:** 
gpt-oss-120b wins clearly with score 7. 
glm5.2 follows at 6.
 The skill helps differently per model — see the per-model read above for the tradeoff details.
