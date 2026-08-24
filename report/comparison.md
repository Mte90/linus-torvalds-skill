---
title: Model Comparison — SmallChat Review
date: 2026-08-24
codebase: antirez/smallchat
models: gpt-oss-120b, glm5.2, mistral-small-4-119b
skill: linus-torvalds-skill (language-agnostic)
method: static review, skill triggers applied per source file
---

# Model Comparison — SmallChat Review

Three models reviewed the same C codebase (antirez/smallchat, ~706 LOC) using the same language-agnostic Linus Torvalds skill. This document cross-references their findings at the issue level — not just counts — to measure consensus, accuracy, and severity calibration.

## Metrics Summary

| Metric | gpt-oss-120b | glm5.2 | mistral |
|--------|:------------:|:------:|:-------:|
| Findings | 14 | 24 | 16 |
| Critical | 1 | 2 | 3 |
| High | 6 | 6 | 3 |
| Medium | 3 | 9 | 4 |
| Low | 4 | 7 | 6 |
| Words | 1136 | 4226 | 2968 |

**Key insight:** Finding count is a poor quality signal. The consensus matrix below shows which models caught which bugs — and that is where the real signal lives.

---

## Finding Consensus Matrix

Every finding from all three reviews, mapped to the underlying issue. ✓ = found, ✗ = missed. Severity shown in parentheses.

### chatlib.c

| # | Issue | gpt-oss | glm5.2 | mistral | Consensus |
|---|-------|:-------:|:------:|:-------:|:---------:|
| 1 | Memory leak in TCPConnect on non-blocking connect ... | ✗ | ✓ (HIGH) | ✗ | glm5.2 only |
| 2 | exit() on OOM removes caller control in a support ... | ✗ | ✓ (MEDIUM) | ✗ | glm5.2 only |
| 3 | Missing const on TCPConnect addr parameter | ✗ | ✓ (LOW) | ✗ | glm5.2 only |

### chatlib.h

| # | Issue | gpt-oss | glm5.2 | mistral | Consensus |
|---|-------|:-------:|:------:|:-------:|:---------:|
| 4 | Missing `const` qualifier on read-only string para... | ✗ | ✓ (MEDIUM) | ✗ | glm5.2 only |
| 5 | Return values and error semantics are undocumented | ✗ | ✓ (MEDIUM) | ✗ | glm5.2 only |
| 6 | Inconsistent function naming convention | ✗ | ✓ (LOW) | ✗ | glm5.2 only |
| 7 | Inconsistent parameter naming: snake_case mixed wi... | ✗ | ✓ (LOW) | ✗ | glm5.2 only |

### smallchat-client.c

| # | Issue | gpt-oss | glm5.2 | mistral | Consensus |
|---|-------|:-------:|:------:|:-------:|:---------:|
| 8 | select() exits on EINTR — suspend/resume kills the... | ✗ | ✓ (HIGH) | ✗ | glm5.2 only |
| 9 | read() from server treats EINTR as "Connection los... | ✗ | ✓ (HIGH) | ✗ | glm5.2 only |
| 10 | setRawMode overwrites real errno with ENOTTY | ✗ | ✓ (MEDIUM) | ✗ | glm5.2 only |
| 11 | read() from stdin ignores error return | ✗ | ✓ (MEDIUM) | ✗ | glm5.2 only |
| 12 | close(s) and return 0 are dead code | ✗ | ✓ (LOW) | ✗ | glm5.2 only |
| 13 | Magic number 127 for backspace | ✗ | ✓ (LOW) | ✗ | glm5.2 only |

### smallchat-server.c

| # | Issue | gpt-oss | glm5.2 | mistral | Consensus |
|---|-------|:-------:|:------:|:-------:|:---------:|
| 14 | No bounds check on file descriptor before array an... | ✗ | ✓ (CRITICAL) | ✓ (CRITICAL) | 2/3 |
| 15 | acceptClient() return value not checked before use | ✗ | ✓ (CRITICAL) | ✓ (MEDIUM) | 2/3 |
| 16 | Fatal assertion used for a recoverable condition | ✗ | ✓ (HIGH) | ✓ (HIGH) | 2/3 |
| 17 | exit(1) on select() failure kills the server on an... | ✗ | ✓ (HIGH) | ✓ (LOW) | 2/3 |
| 18 | read() EINTR treated as client disconnect | ✗ | ✓ (MEDIUM) | ✓ (LOW) | 2/3 |
| 19 | write() return values silently discarded | ✗ | ✓ (MEDIUM) | ✓ (MEDIUM) | 2/3 |
| 20 | socketSetNonBlockNoDelay() failure ignored — "Pret... | ✗ | ✓ (MEDIUM) | ✓ (MEDIUM) | 2/3 |
| 21 | snprintf return value used as memcpy length withou... | ✗ | ✓ (LOW) | ✓ (LOW) | 2/3 |
| 22 | Buffer Overflow in Nickname Handling | ✗ | ✗ | ✓ (CRITICAL) | mistral only |
| 23 | Command Injection via Malformed Input | ✗ | ✗ | ✓ (CRITICAL) | mistral only |
| 24 | Memory Leak in `/nick` Command Handler | ✗ | ✗ | ✓ (HIGH) | mistral only |
| 25 | File Descriptor Exhaustion via Unbounded Clients | ✗ | ✗ | ✓ (HIGH) | mistral only |
| 26 | Missing Error Handling in `write()` Calls | ✗ | ✗ | ✓ (MEDIUM) | mistral only |
| 27 | Magic Number: `MAX_CLIENTS = 1000` | ✗ | ✗ | ✓ (LOW) | mistral only |
| 28 | Missing Logging for Client Disconnections | ✗ | ✗ | ✓ (LOW) | mistral only |
| 29 | Missing Timeout Handling in `select()` | ✗ | ✗ | ✓ (LOW) | mistral only |

### unspecified

| # | Issue | gpt-oss | glm5.2 | mistral | Consensus |
|---|-------|:-------:|:------:|:-------:|:---------:|
| 30 | Header file not listed as a build prerequisite — s... | ✓ (LOW) | ✓ (HIGH) | ✗ | 2/3 |
| 31 | Phony targets not declared `.PHONY` | ✗ | ✓ (MEDIUM) | ✗ | glm5.2 only |
| 32 | Duplicated compile rules | ✗ | ✓ (LOW) | ✗ | glm5.2 only |
| 33 | `assert` used for runtime validation | ✓ (CRITICAL) | ✗ | ✗ | gpt-oss only |
| 34 | unchecked return values (`write`, `socketSetNonBlo... | ✓ (HIGH) | ✗ | ✗ | gpt-oss only |
| 35 | missing validation of `SERVER_PORT` | ✓ (HIGH) | ✗ | ✗ | gpt-oss only |
| 36 | magic numbers (`MAX_CLIENTS`, listen backlog 511) | ✓ (MEDIUM) | ✗ | ✗ | gpt-oss only |
| 37 | partial‑read handling comment (no actual buffering... | ✓ (MEDIUM) | ✗ | ✗ | gpt-oss only |
| 38 | clever‑trick (`write` without error check) | ✓ (LOW) | ✗ | ✗ | gpt-oss only |
| 39 | unchecked return of `setRawMode` | ✓ (HIGH) | ✗ | ✗ | gpt-oss only |
| 40 | missing validation of command‑line arguments (port... | ✓ (HIGH) | ✗ | ✗ | gpt-oss only |
| 41 | magic buffer sizes (`256`, `128`) | ✓ (MEDIUM) | ✗ | ✗ | gpt-oss only |
| 42 | clever‑trick (`goto fatal` pattern) | ✓ (LOW) | ✗ | ✗ | gpt-oss only |
| 43 | unchecked return of `socketSetNonBlockNoDelay` | ✓ (HIGH) | ✗ | ✗ | gpt-oss only |
| 44 | missing validation of `port` argument in `createTC... | ✓ (HIGH) | ✗ | ✗ | gpt-oss only |
| 45 | clever‑trick (`goto fatal` in `TCPConnect`) | ✓ (LOW) | ✗ | ✗ | gpt-oss only |

---

## Severity Disagreement Table

Cases where 2+ models found the same issue but assigned different severities:

| Issue | gpt-oss | glm5.2 | mistral |
|-------|:-------:|:------:|:-------:|
| acceptClient() return value not checked ... | — | CRITICAL | MEDIUM |
| exit(1) on select() failure kills the se... | — | HIGH | LOW |
| read() EINTR treated as client disconnec... | — | MEDIUM | LOW |
| Header file not listed as a build prereq... | LOW | HIGH | — |

---

## Trigger Coverage Comparison

Which skill triggers fired in each review:

| Trigger theme | gpt-oss | glm5.2 | mistral |
|---------------|:-------:|:------:|:-------:|
| 13.4 | ✓ (4) | ✗ | ✗ |
| 5.1 – hidden special‑case bran... | ✓ (1) | ✗ | ✗ |
| 5.4 – unnecessary configuratio... | ✓ (2) | ✗ | ✗ |
| 7.2 – missing input validation | ✓ (3) | ✗ | ✗ |
| 8.1 – fatal abort on recoverab... | ✓ (1) | ✗ | ✗ |
| 8.2 – silent failure handling | ✓ (3) | ✗ | ✗ |
| Code acquires the same lock re... | ✗ | ✗ | ✓ (1) |
| Code adds new configuration op... | ✗ | ✗ | ✓ (1) |
| Code adds new configuration op... | ✗ | ✗ | ✓ (1) |
| Code is assumed to be free of ... | ✗ | ✗ | ✓ (2) |
| Code is modified to improve co... | ✗ | ✗ | ✓ (1) |
| Code performs operations in a ... | ✗ | ✗ | ✓ (1) |
| Code performs operations witho... | ✗ | ✗ | ✓ (3) |
| Correctness invariant — "code ... | ✗ | ✓ (1) | ✗ |
| Correctness invariant — the bu... | ✗ | ✓ (1) | ✗ |
| Dead or unused code paths reta... | ✗ | ✓ (1) | ✗ |
| Duplicated logic that should b... | ✗ | ✓ (1) | ✗ |
| Error handling that masks the ... | ✗ | ✓ (5) | ✗ |
| Error handling that masks the ... | ✗ | ✓ (1) | ✗ |
| Error handling that masks the ... | ✗ | ✓ (1) | ✗ |
| Error return value that is ind... | ✗ | ✓ (1) | ✗ |
| Fatal assertion or abort used ... | ✗ | ✓ (3) | ✗ |
| Fatal assertion or abort used ... | ✗ | ✓ (1) | ✗ |
| General code-review judgment (... | ✗ | ✓ (1) | ✗ |
| Hard-coded constants or hardwa... | ✗ | ✓ (1) | ✗ |
| Inconsistent naming across sim... | ✗ | ✓ (2) | ✗ |
| Introducing memory structures ... | ✗ | ✗ | ✓ (1) |
| Losing track of how memory was... | ✗ | ✗ | ✓ (1) |
| Manual deallocation commented ... | ✗ | ✗ | ✓ (3) |
| Memory Safety — shared object ... | ✗ | ✓ (1) | ✗ |
| Missing documentation for non-... | ✗ | ✓ (1) | ✗ |
| Missing validation of input or... | ✗ | ✗ | ✓ (1) |
| Names that don't describe what... | ✗ | ✓ (1) | ✗ |
| Resource management — early re... | ✗ | ✓ (1) | ✗ |

---

## With-Skill vs Baseline Comparison

For each model, comparing findings with the skill vs without (baseline):

| Model | Baseline Total | With-Skill Total | Baseline CRITICAL | With-Skill CRITICAL | Critical Overlap | Skill-Only CRITICAL | Baseline-Only CRITICAL | Skill Added Value |
|-------|----------------|------------------|-------------------|---------------------|------------------|---------------------|------------------------|-------------------|
| gpt-oss-120b | 11 | 14 | 1 | 1 | 0 | 0 | 1 | no (-1 net critical: 0 found, 1 lost) |
| glm5.2 | 22 | 24 | 3 | 2 | 2 | 0 | 1 | no (-1 net critical: 0 found, 1 lost) |
| mistral | 14 | 16 | 3 | 3 | 1 | 2 | 2 | neutral (0 net: 2 found, 2 lost) |

---

## Qualitative Analysis

### Consensus-Based Accuracy

Findings confirmed by 2+ models are treated as real bugs. Findings reported by only one model are unverified (could be real or false positive).

| Model | Total Findings | Confirmed (2+ models) | Unverified (1 model only) | Consensus Rate |
|-------|:--------------:|:---------------------:|:--------------------------:|:--------------:|
| gpt-oss-120b | 14 | 1 | 13 | 7% |
| glm5.2 | 24 | 9 | 15 | 38% |
| mistral | 16 | 8 | 8 | 50% |

### Severity Calibration

Cases where 2+ models found the same issue but assigned different severities:

| Issue | gpt-oss | glm5.2 | mistral |
|-------|:-------:|:------:|:-------:|
| acceptClient() return value not checked ... | — | CRITICAL | MEDIUM |
| exit(1) on select() failure kills the se... | — | HIGH | LOW |
| read() EINTR treated as client disconnec... | — | MEDIUM | LOW |
| Header file not listed as a build prereq... | LOW | HIGH | — |

Total severity disagreements: 4. Lower is better — it means the model's severity assessment aligns with the consensus.

### Unique Findings (Single-Model Discoveries)

Findings reported by only one model. These represent either unique insight or false positives:

| Model | Unique Findings |
|-------|:--------------:|
| gpt-oss-120b | 13 |
| glm5.2 | 15 |
| mistral | 8 |

A high unique count with a low consensus rate suggests false positives. A high unique count with a high consensus rate suggests the model found real bugs others missed.

### With-Skill vs Baseline: Skill Impact

How the skill changed each model's review:

**gpt-oss-120b:** Baseline 11 findings (1 CRITICAL) → With-skill 14 findings (1 CRITICAL). Skill found 0 critical bug(s) the baseline missed; baseline found 1 critical bug(s) the skill missed.

**glm5.2:** Baseline 22 findings (3 CRITICAL) → With-skill 24 findings (2 CRITICAL). Skill found 0 critical bug(s) the baseline missed; baseline found 1 critical bug(s) the skill missed.

**mistral:** Baseline 14 findings (3 CRITICAL) → With-skill 16 findings (3 CRITICAL). Skill found 2 critical bug(s) the baseline missed; baseline found 2 critical bug(s) the skill missed.

#### Skill Tradeoff Analysis

The skill narrows reviewer focus toward memory-safety and correctness (Linus's priorities). This filters noise but can also suppress valid findings. Net critical impact per model:

| Model | Skill-Only CRITICAL | Baseline-Only CRITICAL | Net Critical Impact | Total Finding Delta |
|-------|:-------------------:|:----------------------:|:-------------------:|:-------------------:|
| gpt-oss-120b | 0 | 1 | -1 | +3 |
| glm5.2 | 0 | 1 | -1 | +2 |
| mistral | 2 | 2 | 0 | +2 |

**Interpretation:** A positive net critical impact means the skill found real bugs the baseline missed. A negative value means the skill suppressed critical findings the baseline caught — a coverage gap. A large negative total finding delta with neutral critical impact means the skill filtered noise without losing signal.

**Per-model read:**
- **gpt-oss-120b:** Net negative on critical coverage. The skill changed finding count and suppressed 1 critical(s) the baseline caught, while only adding 0 new critical. The skill narrowed focus too aggressively — the 1 lost critical(s) are a real coverage gap worth investigating.
- **glm5.2:** Net negative on critical coverage. The skill changed finding count and suppressed 1 critical(s) the baseline caught, while only adding 0 new critical. The skill narrowed focus too aggressively — the 1 lost critical(s) are a real coverage gap worth investigating.
- **mistral:** Neutral. No net change in critical coverage.

### Trigger Coverage Analysis

Which skill triggers each model fired:

**gpt-oss-120b:** 6 distinct triggers fired, 14 total trigger firings.
  Top triggers: 13.4 (4x), 8.2 – silent failure handling (3x), 7.2 – missing input validation (3x)

**glm5.2:** 17 distinct triggers fired, 24 total trigger firings.
  Top triggers: Error handling that masks the root cause (5x), Fatal assertion or abort used for a recoverable condition (3x), Inconsistent naming across similar entities (2x)

**mistral:** 11 distinct triggers fired, 16 total trigger firings.
  Top triggers: Manual deallocation commented out or omitted, risking leaks or crashes (3x), Code performs operations without checking for validity (3x), Code is assumed to be free of security vulnerabilities without explicit justification (2x)

### Verdict

Based on consensus-confirmed findings, net critical impact (skill-only minus baseline-only), and severity calibration:

| Model | Confirmed | Skill-Only CRITICAL | Baseline-Only CRITICAL | Net Critical | Severity Disagreements | Score |
|-------|:---------:|:-------------------:|:----------------------:|:-------------:|:----------------------:|:-----:|
| gpt-oss-120b | 1 | 0 | 1 | -1 | 1 | -1 |
| glm5.2 | 9 | 0 | 1 | -1 | 4 | 4 |
| mistral | 8 | 2 | 2 | 0 | 3 | 5 |

**Scoring:** `confirmed + skill_only_critical - baseline_only_critical - severity_disagreements`. The baseline-only penalty makes coverage gaps visible: a model that suppresses real bugs the baseline caught scores lower, even if it found other bugs the baseline missed.

**Honest read:** 
mistral wins clearly with score 5. 
glm5.2 follows at 4.
 The skill helps differently per model — see the per-model read above for the tradeoff details.
