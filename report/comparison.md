---
title: Skill variant comparison — antirez/smallchat
date: 2026-08-12
target: antirez/smallchat (706 LOC, C)
models: [gpt-oss-120b, glm5.2, mistral-small-4-119b]
previous_run: 2026-08-12 (keyword calibration)
---

# Skill Variant Comparison

Three LLM models reviewed the same codebase (antirez/smallchat, 706 LOC) using
three language-agnostic skill variants generated from the same extracted patterns.
Each model received its matching skill file and soul file. This document
synthesizes where they agree, where they diverge, and what that says about the
skill + model combination.

This run uses skill and soul files regenerated on 2026-08-12 after removing the
keyword-based decision rules from the calibration data. The previous run used
keyword rules derived from the corpus, which caused mistral to collapse from 25
findings to 0 (APPROVE) — it treated the keyword checklist as exhaustive and,
finding no C/kernel keyword matches in SmallChat, approved the code outright.
The fix replaces keyword matching with category-based severity calibration
(P(severity | category) only), which is genuinely language-agnostic.

## Headline numbers

| Metric | gpt-oss-120b | glm5.2 | mistral-small-4-119b |
|--------|-------------|--------|----------------------|
| Findings (total) | 18 | 12 | 15 |
| CRITICAL | 4 | 1 | 1 |
| HIGH | 4 | 2 | 9 |
| MEDIUM | 4 | 4 | 0 |
| LOW | 6 | 5 | 5 |
| Report words | 936 | 2,350 | 1,993 |
| Verdict | FAIL | FAIL | FAIL |

All three models now agree the code fails. This is the most important outcome:
no model approves code with known memory-corruption bugs.

### Shift from previous run (keyword calibration → category calibration)

| Metric | gpt-oss-120b | glm5.2 | mistral-small-4-119b |
|--------|-------------|--------|----------------------|
| Findings (prev) | 13 | 20 | 0 |
| Findings (now) | 18 | 12 | 15 |
| CRITICAL (prev) | 2 | 2 | 0 |
| CRITICAL (now) | 4 | 1 | 1 |
| Verdict (prev) | FAIL | FAIL | APPROVE |
| Verdict (now) | FAIL | FAIL | FAIL |

The keyword-rules removal affected the three models differently:

- **mistral recovered**: 0 findings → 15 findings, APPROVE → FAIL. This is the
  primary outcome of the fix. The keyword-based decision tree was causing mistral
  to treat C/kernel tokens (`set_fs`, `size_t`, `mutex`) as an exhaustive
  checklist. When none matched SmallChat, it approved. With category-based
  calibration, mistral now reasons about severity by category (error-handling,
  memory-safety, correctness) and produces real findings.

- **glm5.2 tightened**: 20 → 12 findings. It still found the most consequential
  bug (`acceptClient(-1)` memory corruption) but dropped several lower-signal
  findings from the previous run. The precision improved: every finding now maps
  to a specific code location with a concrete fix.

- **gpt-oss grew**: 13 → 18 findings, 2 → 4 CRITICAL. The growth is mixed —
  two of the four CRITICALs are the same bug (chatMalloc OOM) reported in two
  files. But it also found `setRawMode` terminal state and `setsockopt` errors
  silently ignored, both real issues.

## Consensus findings

All three models now agree on the core failure: the code has real bugs that
must be fixed before merge. Three findings are shared by at least two models:

1. **`write()` return values ignored** (all three) — every `write` to a client
   socket discards the return. gpt-oss rates HIGH, glm5.2 rates LOW, mistral
   rates HIGH. glm5.2 notes it as a documented design choice for a teaching
   example.

2. **Missing null terminator on `c->nick`** (glm5.2 + mistral) — `chatMalloc`
   allocates `nicklen+1` but only `nicklen` bytes are copied. The +1 byte is
   uninitialized heap garbage, broadcast to all clients. glm5.2 rates HIGH,
   mistral rates CRITICAL.

3. **`chatMalloc`/`chatRealloc` OOM abort** (gpt-oss + glm5.2) — `exit(1)` on
   out-of-memory. gpt-oss rates HIGH, glm5.2 rates LOW and calls it "a
   documented design choice."

### Bugs only glm5.2 found

glm5.2 remains the sole model that found the most consequential bug:

1. **`acceptClient()` return unchecked → `createClient(-1)`** (CRITICAL) —
   `accept()` failure passes `-1` to `createClient`, which writes to
   `Chat->clients[-1]` — out-of-bounds memory corruption. Triggered by EMFILE,
   ECONNABORTED, or any transient accept failure under load.

glm5.2 also found two bugs no other model caught:

2. **`select()` exits on `EINTR`** (HIGH) — any delivered signal kills the
   server. EINTR is the textbook recoverable condition.

3. **`freeaddrinfo()` leaked on `EINPROGRESS` early return** (MEDIUM) — the
   non-blocking connect path skips `freeaddrinfo(servinfo)`. Real resource leak.

### Bugs only mistral found

Mistral found one bug neither other model flagged:

1. **`assert` used for runtime sanity check** (HIGH) — `assert(Chat->clients[c->fd] == NULL)`
   aborts the server if the slot is occupied. Under `-DNDEBUG` the check vanishes
   entirely. glm5.2 mentions this in passing but rates it LOW; mistral correctly
   identifies it as HIGH.

### Bugs only gpt-oss found

gpt-oss found two issues neither other model flagged:

1. **`setsockopt` errors silently ignored** (CRITICAL) — lines 33 and 46 call
   `setsockopt` with "no need to check for errors." gpt-oss rates this CRITICAL,
   which is aggressive — the comment says "best-effort" — but the finding is
   technically correct.

2. **`setRawMode` can leave terminal in broken state** (CRITICAL) —
   `atexit_registered` is set before `tcgetattr` succeeds, so cleanup tries to
   restore a terminal state that was never saved. Real bug, real impact.

## Skill quality observations

### Trigger labeling

glm5.2's trigger labeling remains the most precise — every finding maps to a
numbered trigger with the theme name (e.g., "Trigger 6.2 — Missing cleanup on
error paths"). gpt-oss labels triggers by name without numbers. Mistral labels
triggers by name and includes the trigger description — a significant improvement
from the previous run where it applied no trigger labels at all.

### Voice and tone

glm5.2 has the strongest Torvalds voice: "One line. This is complete and utter
shit. You do not feed an error sentinel into an array index. Ever." Direct,
technical, profane where warranted. gpt-oss is measured but forceful: "This is
bullshit — if you can't handle an error, you shouldn't be calling the function."
Mistral's voice is the weakest — correct in structure but flat in tone, reading
more like a checklist than a review.

### Calibration impact (keyword → category)

The keyword-rules removal had the expected effect on mistral and a neutral
effect on the other two:

- **mistral**: recovered from 0 to 15 findings. The category-based calibration
  gives the model severity guidance without forcing it to match specific tokens.
  This is the correct design — the skill should teach *how to think about
  severity*, not *what keywords to look for*.

- **glm5.2**: tightened from 20 to 12 findings. The previous run's keyword rules
  may have been inflating the count by suggesting patterns to look for. Without
  them, glm5.2 focuses on the bugs it can justify from the code itself.

- **gpt-oss**: grew from 13 to 18 findings. The category-based calibration may
  be giving the model more confidence to flag issues without needing a keyword
  match.

### Coverage vs. precision tradeoff

- **glm5.2**: 12 findings, 1 CRITICAL, 2 HIGH. Found the most consequential bug
  (acceptClient(-1)) that no other model found. Highest precision — every finding
  maps to a specific code location with a concrete fix. 2,350 words — thorough
  but not bloated. The clear standout for bug-finding.

- **gpt-oss-120b**: 18 findings, 4 CRITICAL (2 are duplicates), 4 HIGH. Widest
  coverage but lowest precision — two CRITICALs are the same bug reported twice.
  Found setsockopt and setRawMode bugs that glm5.2 missed. 936 words — concise.

- **mistral**: 15 findings, 1 CRITICAL, 9 HIGH. Dramatic recovery from the
  previous run's 0 findings. The HIGH count is inflated (several are the same
  "ignored error return" pattern applied to different call sites), but the
  findings are real. 1,993 words — thorough. The model is now functional as a
  reviewer.

## Recommendation

For a codebase of this size (<1000 LOC), glm5.2 remains the strongest
single-model reviewer. It found the most consequential bug (acceptClient(-1))
that no other model found, maintained the strongest Torvalds voice, and
produced the most precise trigger labeling.

For production review, run at least two models and union the findings. gpt-oss
catches setsockopt and setRawMode issues that glm5.2 skips; glm5.2 catches
acceptClient(-1) and select() EINTR that gpt-oss misses. Together they cover
more ground than either alone.

Mistral is now functional as a reviewer — it produces real findings and correctly
fails the code. It should not be used as a sole reviewer (it missed
acceptClient(-1) and select() EINTR), but it is no longer dangerous (it no
longer approves code with known bugs). The keyword-rules removal was the correct
fix.
