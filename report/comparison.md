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
| gpt-oss-120b | 10 | 2 | 1 | Skill adds value |
| glm5.2 | 17 | 5 | 1 | Skill reduces coverage |
| mistral | 22 | 4 | 3 | Skill adds value |

The skill adds the most value for mistral, which gained 3 critical finding(s) exclusive to the with-skill review.

3 models reviewed the same C codebase (antirez/smallchat, ~706 LOC) using the same language-agnostic Linus Torvalds skill. This document cross-references their findings at the issue level — not just counts — to measure consensus, accuracy, and severity calibration.

## Metrics Summary

| Metric | gpt-oss-120b | glm5.2 | mistral |
|--------|:---:|:---:|:---:|
| Findings | 10 | 17 | 22 |
| Critical | 2 | 5 | 4 |
| High | 2 | 5 | 4 |
| Medium | 3 | 3 | 7 |
| Low | 3 | 4 | 7 |
| Words | 1836 | 2519 | 2426 |

**Key insight:** Finding count is a poor quality signal. The consensus matrix below shows which models caught which bugs — and that is where the real signal lives.

---

## Finding Consensus Matrix

Every finding from all three reviews, mapped to the underlying issue. ✓ = found, ✗ = missed. Severity shown in parentheses.

### chatlib.c

| # | Issue | gpt-oss-120b | glm5.2 | mistral | Consensus |
|---|:---:|:---:|:---:|:---:|
| 1 | Unchecked return value of `write()` to stdout | ✓ (LOW) | ✗ | ✓ (MEDIUM) | 2/3 |
| 2 | Ignored error return from `socketSetNonBlockNoDela... | ✓ (MEDIUM) | ✓ (HIGH) | ✗ | 2/3 |
| 3 | TCPConnect leaks addrinfo on EINPROGRESS return | ✗ | ✓ (HIGH) | ✓ (LOW) | 2/3 |
| 4 | Dead code after while(1) loop | ✗ | ✓ (LOW) | ✗ | glm5.2 only |
| 5 | Finding: Silent swallowing of serious errors | ✗ | ✗ | ✓ (CRITICAL) | mistral only |
| 6 | Finding: Silent swallowing of serious errors | ✗ | ✗ | ✓ (HIGH) | mistral only |
| 7 | Finding: Hard-coded magic constants | ✗ | ✗ | ✓ (MEDIUM) | mistral only |

### chatlib.h

| # | Issue | gpt-oss-120b | glm5.2 | mistral | Consensus |
|---|:---:|:---:|:---:|:---:|
| 8 | Unchecked return value of `setsockopt` in `socketS... | ✓ (LOW) | ✗ | ✗ | gpt-oss-120b only |
| 9 | CFLAGS placed after source files — fragile orderin... | ✗ | ✓ (LOW) | ✓ (MEDIUM) | 2/3 |
| 10 | chatRealloc is declared, exported, and never used ... | ✗ | ✓ (LOW) | ✗ | glm5.2 only |
| 11 | Finding: Missing documentation for public interfac... | ✗ | ✗ | ✓ (LOW) | mistral only |
| 12 | Finding: Hard-coded compiler flags | ✗ | ✗ | ✓ (LOW) | mistral only |
| 13 | Finding: Missing clean target for object files | ✗ | ✗ | ✓ (LOW) | mistral only |
| 14 | CFLAGS placed after source files — fragile orderin... | ✗ | ✓ (LOW) | ✓ (HIGH) | 2/3 |

### smallchat-client.c

| # | Issue | gpt-oss-120b | glm5.2 | mistral | Consensus |
|---|:---:|:---:|:---:|:---:|
| 15 | Unchecked return value of `write()` in sendMsgToAl... | ✓ (LOW) | ✓ (MEDIUM) | ✗ | 2/3 |
| 16 | Input buffer overflow not handled | ✓ (HIGH) | ✗ | ✓ (MEDIUM) | 2/3 |
| 17 | Ignored return value of `setRawMode` | ✓ (MEDIUM) | ✗ | ✓ (CRITICAL) | 2/3 |
| 18 | MAX_CLIENTS comment is factually wrong | ✗ | ✓ (LOW) | ✓ (HIGH) | 2/3 |
| 19 | select() exits on EINTR — client dies on any signa... | ✗ | ✓ (HIGH) | ✗ | glm5.2 only |
| 20 | Finding: Hard-coded magic constants | ✗ | ✗ | ✓ (MEDIUM) | mistral only |
| 21 | Finding: Dead or unnecessary code constructs | ✗ | ✗ | ✓ (LOW) | mistral only |

### smallchat-server.c

| # | Issue | gpt-oss-120b | glm5.2 | mistral | Consensus |
|---|:---:|:---:|:---:|:---:|
| 22 | Fatal assertion used for a recoverable error | ✓ (CRITICAL) | ✓ (CRITICAL) | ✓ (CRITICAL) | 3/3 |
| 23 | Out‑of‑bounds indexing of the client table | ✓ (CRITICAL) | ✓ (CRITICAL) | ✓ (CRITICAL) | 3/3 |
| 24 | Nick string not NUL‑terminated | ✓ (HIGH) | ✓ (HIGH) | ✓ (HIGH) | 3/3 |
| 25 | Ignored error return from socketSetNonBlockNoDelay | ✓ (MEDIUM) | ✓ (CRITICAL) | ✗ | 2/3 |
| 26 | No SIGPIPE handling — server crashes on write to c... | ✗ | ✓ (CRITICAL) | ✓ (HIGH) | 2/3 |
| 27 | snprintf failure produces negative length cast to ... | ✗ | ✓ (CRITICAL) | ✓ (MEDIUM) | 2/3 |
| 28 | select() exits on EINTR — server dies on any caugh... | ✗ | ✓ (HIGH) | ✓ (MEDIUM) | 2/3 |
| 29 | write() return values ignored — silent data loss o... | ✗ | ✓ (MEDIUM) | ✗ | glm5.2 only |
| 30 | No nickname length validation — unbounded allocati... | ✗ | ✓ (MEDIUM) | ✗ | glm5.2 only |
| 31 | Finding: Obscure or non-descriptive naming | ✗ | ✗ | ✓ (LOW) | mistral only |
| 32 | Finding: Overly complex control flow | ✗ | ✗ | ✓ (LOW) | mistral only |
| 33 | Finding: Special-case handling for rare or edge ca... | ✗ | ✓ (CRITICAL) | ✓ (MEDIUM) | 2/3 |

---

## Severity Disagreement Table

Cases where 2+ models found the same issue but assigned different severities:

| Issue | gpt-oss-120b | glm5.2 | mistral |
|-------|:---:|:---:|:---:|
| Unchecked return value of `write()` to s... | LOW | — | MEDIUM |
| Ignored error return from `socketSetNonB... | MEDIUM | HIGH | — |
| TCPConnect leaks addrinfo on EINPROGRESS... | — | HIGH | LOW |
| CFLAGS placed after source files — fragi... | — | LOW | MEDIUM |
| Unchecked return value of `write()` in s... | LOW | MEDIUM | — |
| Input buffer overflow not handled | HIGH | — | MEDIUM |
| Ignored return value of `setRawMode` | MEDIUM | — | CRITICAL |
| MAX_CLIENTS comment is factually wrong | — | LOW | HIGH |
| Ignored error return from socketSetNonBl... | MEDIUM | CRITICAL | — |
| No SIGPIPE handling — server crashes on ... | — | CRITICAL | HIGH |
| snprintf failure produces negative lengt... | — | CRITICAL | MEDIUM |
| select() exits on EINTR — server dies on... | — | HIGH | MEDIUM |
| CFLAGS placed after source files — fragi... | — | LOW | HIGH |
| Finding: Special-case handling for rare ... | — | CRITICAL | MEDIUM |

---

## Trigger Coverage Comparison

Which skill triggers fired in each review:

| Trigger theme | gpt-oss-120b | glm5.2 | mistral |
|---------------|:---:|:---:|:---:|
| *Fatal assertion used for a re... | ✓ (1) | ✗ | ✗ |
| *Mixed error‑code conventions* | ✓ (2) | ✗ | ✗ |
| *Mixed error‑code conventions*... | ✓ (1) | ✗ | ✗ |
| *Performance‑sensitive hot pat... | ✓ (2) | ✗ | ✗ |
| *Performance‑sensitive hot pat... | ✓ (1) | ✗ | ✗ |
| *Unbounded format‑string or bu... | ✓ (1) | ✗ | ✗ |
| *Unbounded format‑string or bu... | ✓ (1) | ✗ | ✗ |
| *Unbounded format‑string or bu... | ✓ (1) | ✗ | ✗ |
| A comment that describes behav... | ✗ | ✓ (2) | ✗ |
| A fatal assertion, panic, or a... | ✗ | ✓ (1) | ✗ |
| A function's return value conv... | ✗ | ✓ (1) | ✗ |
| A name (function, variable, ty... | ✗ | ✓ (1) | ✗ |
| A patch papers over a problem ... | ✗ | ✓ (1) | ✗ |
| A resource is freed while it m... | ✗ | ✓ (1) | ✗ |
| An API design makes the correc... | ✗ | ✓ (2) | ✗ |
| Code contains dead code paths,... | ✗ | ✓ (2) | ✗ |
| Code uses an algorithm or data... | ✗ | ✓ (1) | ✗ |
| Dead or unnecessary code const... | ✗ | ✗ | ✓ (2) |
| Error-handling code suppresses... | ✗ | ✓ (2) | ✗ |
| Exposing internal structures a... | ✗ | ✗ | ✓ (1) |
| Fatal assertion/panic used for... | ✗ | ✗ | ✓ (1) |
| Hard-coded magic constants or ... | ✗ | ✗ | ✓ (4) |
| Inconsistent error code conven... | ✗ | ✗ | ✓ (2) |
| Inconsistent naming convention... | ✗ | ✗ | ✓ (1) |
| Interfaces that return mislead... | ✗ | ✓ (2) | ✗ |
| Internal memory contents (stac... | ✗ | ✓ (1) | ✗ |
| Manual memory allocation/deall... | ✗ | ✗ | ✓ (2) |
| Manual resource cleanup instea... | ✗ | ✗ | ✓ (1) |
| Missing comments explaining lo... | ✗ | ✗ | ✓ (1) |
| Obscure or non-descriptive nam... | ✗ | ✗ | ✓ (1) |
| Overly complex control flow | ✗ | ✗ | ✓ (1) |
| Silent swallowing of serious e... | ✗ | ✗ | ✓ (4) |
| Special-case handling for rare... | ✗ | ✗ | ✓ (1) |

---

## With-Skill vs Baseline Comparison

For each model, comparing findings with the skill vs without (baseline):

| Model | Baseline Total | With-Skill Total | Baseline CRITICAL | With-Skill CRITICAL | Critical Overlap | Skill-Only CRITICAL | Baseline-Only CRITICAL | Skill Added Value |
|-------|----------------|------------------|-------------------|---------------------|------------------|---------------------|------------------------|-------------------|
| gpt-oss-120b | 12 | 10 | 1 | 2 | 1 | 1 | 0 | yes (+1 net critical: 1 found, 0 lost) |
| glm5.2 | 30 | 17 | 6 | 5 | 4 | 1 | 2 | no (-1 net critical: 1 found, 2 lost) |
| mistral | 10 | 22 | 1 | 4 | 1 | 3 | 0 | yes (+3 net critical: 3 found, 0 lost) |

---

## Qualitative Analysis

### Consensus-Based Accuracy

Findings confirmed by 2+ models are treated as real bugs. Findings reported by only one model are unverified (could be real or false positive).

| Model | Total Findings | Confirmed (2+ models) | Unverified (1 model only) | Consensus Rate |
|-------|:--------------:|:---------------------:|:--------------------------:|:--------------:|
| gpt-oss-120b | 10 | 9 | 1 | 90% |
| glm5.2 | 19 | 14 | 5 | 74% |
| mistral | 24 | 14 | 10 | 58% |

### Severity Calibration

Cases where 2+ models found the same issue but assigned different severities:

| Issue | gpt-oss-120b | glm5.2 | mistral |
|-------|:---:|:---:|:---:|
| Unchecked return value of `write()` to s... | LOW | — | MEDIUM |
| Ignored error return from `socketSetNonB... | MEDIUM | HIGH | — |
| TCPConnect leaks addrinfo on EINPROGRESS... | — | HIGH | LOW |
| CFLAGS placed after source files — fragi... | — | LOW | MEDIUM |
| Unchecked return value of `write()` in s... | LOW | MEDIUM | — |
| Input buffer overflow not handled | HIGH | — | MEDIUM |
| Ignored return value of `setRawMode` | MEDIUM | — | CRITICAL |
| MAX_CLIENTS comment is factually wrong | — | LOW | HIGH |
| Ignored error return from socketSetNonBl... | MEDIUM | CRITICAL | — |
| No SIGPIPE handling — server crashes on ... | — | CRITICAL | HIGH |
| snprintf failure produces negative lengt... | — | CRITICAL | MEDIUM |
| select() exits on EINTR — server dies on... | — | HIGH | MEDIUM |
| CFLAGS placed after source files — fragi... | — | LOW | HIGH |
| Finding: Special-case handling for rare ... | — | CRITICAL | MEDIUM |

Total severity disagreements: 14. Lower is better — it means the model's severity assessment aligns with the consensus.

### Unique Findings (Single-Model Discoveries)

Findings reported by only one model. These represent either unique insight or false positives:

| Model | Unique Findings |
|-------|:--------------:|
| gpt-oss-120b | 1 |
| glm5.2 | 5 |
| mistral | 10 |

A high unique count with a low consensus rate suggests false positives. A high unique count with a high consensus rate suggests the model found real bugs others missed.

### With-Skill vs Baseline: Skill Impact

How the skill changed each model's review:

**gpt-oss-120b:** Baseline 12 findings (1 CRITICAL) → With-skill 10 findings (2 CRITICAL). Skill found 1 critical bug(s) the baseline missed; baseline found 0 critical bug(s) the skill missed.

**glm5.2:** Baseline 30 findings (6 CRITICAL) → With-skill 17 findings (5 CRITICAL). Skill found 1 critical bug(s) the baseline missed; baseline found 2 critical bug(s) the skill missed.

**mistral:** Baseline 10 findings (1 CRITICAL) → With-skill 22 findings (4 CRITICAL). Skill found 3 critical bug(s) the baseline missed; baseline found 0 critical bug(s) the skill missed.

#### Skill Tradeoff Analysis

The skill narrows reviewer focus toward memory-safety and correctness (Linus's priorities). This filters noise but can also suppress valid findings. Net critical impact per model:

| Model | Skill-Only CRITICAL | Baseline-Only CRITICAL | Net Critical Impact | Total Finding Delta |
|-------|:-------------------:|:----------------------:|:-------------------:|:-------------------:|
| gpt-oss-120b | 1 | 0 | +1 | -2 |
| glm5.2 | 1 | 2 | -1 | -13 |
| mistral | 3 | 0 | +3 | +12 |

**Interpretation:** A positive net critical impact means the skill found real bugs the baseline missed. A negative value means the skill suppressed critical findings the baseline caught — a coverage gap. A large negative total finding delta with neutral critical impact means the skill filtered noise without losing signal.

**Per-model read:**
- **gpt-oss-120b:** Net positive. The skill cut 2 findings and added 1 critical bug(s) the baseline missed.
- **glm5.2:** Net negative on critical coverage. The skill cut 13 findings and suppressed 2 critical(s) the baseline caught, while only adding 1 new critical. The skill narrowed focus too aggressively — the 2 lost critical(s) are a real coverage gap worth investigating.
- **mistral:** Net positive. The skill added findings and added 3 critical bug(s) the baseline missed.

### Trigger Coverage Analysis

Which skill triggers each model fired:

**gpt-oss-120b:** 8 distinct triggers fired, 10 total trigger firings.
  Top triggers: *Mixed error‑code conventions* (2x), *Performance‑sensitive hot path* (error masking) (2x), *Fatal assertion used for a recoverable error* (1x)

**glm5.2:** 12 distinct triggers fired, 17 total trigger firings.
  Top triggers: An API design makes the correct usage path difficult and the incorrect usage path easy. (2x), Interfaces that return misleading or fabricated data, or functions that are fragile against unexpected inputs from callers. (2x), Error-handling code suppresses the symptom of an underlying bug, or is itself fragile enough to fail under the same conditions that triggered the original error. (2x)

**mistral:** 13 distinct triggers fired, 22 total trigger firings.
  Top triggers: Silent swallowing of serious errors (4x), Hard-coded magic constants or hardware-specific hacks (4x), Manual memory allocation/deallocation without clear ownership (2x)

### Verdict

Based on consensus-confirmed CRITICAL findings, net critical impact (skill-only minus baseline-only), and severity calibration:

| Model | Confirmed CRITICAL | Skill-Only CRITICAL | Baseline-Only CRITICAL | Net Critical | Severity Disagreements | Score |
|-------|:------------------:|:-------------------:|:----------------------:|:-------------:|:----------------------:|:-----:|
| gpt-oss-120b | 2 | 1 | 0 | +1 | 6 | -3 |
| glm5.2 | 6 | 1 | 2 | -1 | 11 | -6 |
| mistral | 3 | 3 | 0 | +3 | 11 | -5 |

**Scoring:** `confirmed_critical + skill_only_critical - baseline_only_critical - severity_disagreements`. All terms are CRITICAL-only for unit consistency. The baseline-only penalty makes coverage gaps visible: a model that suppresses real bugs the baseline caught scores lower, even if it found other bugs the baseline missed.

**Honest read:** 
gpt-oss-120b wins clearly with score -3. 
mistral follows at -5.
 The skill helps differently per model — see the per-model read above for the tradeoff details.
