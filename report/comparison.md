---
title: Skill variant comparison — antirez/smallchat
date: 2026-08-11
target: antirez/smallchat (706 LOC, C)
models: [gpt-oss-120b, glm5.2, mistral-small-4-119b]
previous_run: 2026-08-06
---

# Skill Variant Comparison

Three LLM models reviewed the same codebase (antirez/smallchat, 706 LOC) using
three language-agnostic skill variants generated from the same extracted patterns.
Each model received its matching skill file and soul file. This document
synthesizes where they agree, where they diverge, and what that says about the
skill + model combination.

This run uses skill and soul files regenerated on 2026-08-11 after prompt
improvements (forbidden-terms list, translation table, sanitizer post-processor,
code-fence stripper). The previous run (2026-08-06) used the pre-improvement
files. Where the two runs diverge, this document notes the shift.

## Headline numbers

| Metric | gpt-oss-120b | glm5.2 | mistral-small-4-119b |
|--------|-------------|--------|----------------------|
| Findings (total) | 9 | 16 | 25 |
| CRITICAL | 1 | 2 | 0 |
| HIGH | 6 | 3 | 0 |
| MEDIUM | 1 | 5 | 0 |
| LOW | 1 | 6 | 25 |
| Report words | 667 | 2,840 | 2,194 |
| Verdict | FAIL | FAIL | Does not pass |

All three models reach the same verdict: the code does not pass Torvalds' review.
But the severity distribution has shifted dramatically from the previous run.

### Shift from previous run (2026-08-06)

| Metric | gpt-oss-120b | glm5.2 | mistral-small-4-119b |
|--------|-------------|--------|----------------------|
| Findings (prev) | 21 | 15 | 12 |
| Findings (now) | 9 | 16 | 25 |
| CRITICAL (prev) | 2 | 2 | 3 |
| CRITICAL (now) | 1 | 2 | 0 |
| Words (prev) | 4,076 | 3,449 | 2,426 |
| Words (now) | 667 | 2,840 | 2,194 |

gpt-oss-120b shrank from 21 findings to 9 and from 4,076 words to 667 — it
became far more concise but lost coverage on several bugs it previously caught.
glm5.2 stayed roughly stable (15 → 16 findings, 3,449 → 2,840 words) and is the
only model that maintained its bug-finding quality. mistral inverted: previously
12 findings with 3 CRITICAL and the highest signal-to-noise ratio; now 25
findings, all LOW, zero CRITICAL, and several false positives.

## Consensus findings (all three agree)

The consensus core has thinned. In the previous run, seven findings were
unanimous. Now only two are.

### 1. Unchecked `write()` returns — severity varies (all three agree)

All three models flag that `write()` return values are discarded in
`sendMsgToAllClientsBut`, the client send path, and `inputBufferShow`. Severity
diverges sharply: gpt-oss-120b rates it HIGH, glm5.2 MEDIUM, mistral LOW. The
fix is the same everywhere: check the return and handle short writes.

### 2. No handling of partial reads / message framing — gpt-oss + mistral

`read()` may return a partial message; the code assumes a full line and forwards
it directly. gpt-oss-120b flags this MEDIUM, mistral LOW. glm5.2 does not flag
it explicitly but covers the broader error-handling theme.

## Key divergence: glm5.2 is the only model finding the CRITICAL bugs

In the previous run, the headline divergence was that only mistral found the
un-NUL-terminated nickname. In this run, the situation has reversed completely.

### Bugs only glm5.2 found

glm5.2 is the sole model that found four of the five most consequential bugs in
the codebase — bugs that all three models (including glm5.2) found in the
previous run:

1. **SIGPIPE kills the server** (CRITICAL) — `write()` to a dead socket raises
   `SIGPIPE`; no `signal(SIGPIPE, SIG_IGN)` anywhere. A client disconnecting
   kills the server. Previously unanimous CRITICAL; now only glm5.2 flags it.

2. **`acceptClient()` return unchecked → `createClient(-1)`** (CRITICAL) —
   `accept()` failure passes `-1` to `createClient`, which writes to
   `Chat->clients[-1]` — out-of-bounds memory corruption. Previously unanimous
   CRITICAL; now only glm5.2 flags it.

3. **`select()` exits on `EINTR`** (HIGH) — `select() == -1` calls `exit(1)`
   with no `errno == EINTR` check. Any delivered signal kills the server.
   Previously unanimous MEDIUM; now only glm5.2 flags it (upgraded to HIGH).

4. **No bounds check on `fd` vs `MAX_CLIENTS`** (HIGH) — `clients[fd]` indexed
   without validating `fd < MAX_CLIENTS`; `FD_SET(j, &readfds)` with
   `j >= FD_SETSIZE` corrupts the `fd_set`. Previously unanimous HIGH; now only
   glm5.2 flags it.

5. **`TCPConnect` leaks `addrinfo` on `EINPROGRESS`** (MEDIUM) — early return
   skips `freeaddrinfo(servinfo)`. Previously unanimous; now only glm5.2 flags it.

### The nickname NUL terminator — reversal

The most consequential divergence from the previous run: the un-NUL-terminated
nickname bug.

```c
int nicklen = snprintf(nick, sizeof(nick), "user:%d", fd);
c->nick = chatMalloc(nicklen + 1);
memcpy(c->nick, nick, nicklen);   // copies nicklen bytes — NO NUL
```

`snprintf` returns the length excluding the terminator. `memcpy` copies `nicklen`
bytes. The allocated `nicklen+1`th byte is uninitialized heap memory. `c->nick`
is not a valid C string. Every `printf("%s", c->nick)`, every relay reads past
the allocation until it hits a zero byte. Heap over-read on every connection.
The `/nick` command path four screens down does it correctly (`nicklen + 1`),
confirming this is a copy-paste bug, not a design choice.

In the previous run, only mistral found this (CRITICAL). In this run:
- **gpt-oss-120b**: found it, rated CRITICAL. The headline finding of its review.
- **glm5.2**: found it, rated HIGH, with the most detailed analysis (cross-references
  the correct `/nick` path, traces the data flow to `sendMsgToAllClientsBut`,
  identifies it as an information leak to other clients).
- **mistral**: did NOT find it. Did not flag it at all.

This is a complete reversal. The model that previously uniquely caught this bug
now misses it, while the two that previously missed it now catch it.

## Findings unique to one model

### gpt-oss-120b only
- **Missing NUL terminator on nick** (CRITICAL) — the headline finding. gpt-oss
  found it this run; missed it last run.
- `setRawMode()` return discarded (HIGH) — previously unanimous MEDIUM; now only
  gpt-oss flags it.
- Magic number for input buffer size `IB_MAX 128` (LOW).

### glm5.2 only
- **SIGPIPE kills server** (CRITICAL) — previously unanimous; now glm5.2 alone.
- **`acceptClient(-1)` memory corruption** (CRITICAL) — previously unanimous; now
  glm5.2 alone.
- **`select()` EINTR → exit** (HIGH) — previously unanimous; now glm5.2 alone.
- **No fd bounds check** (HIGH) — previously unanimous; now glm5.2 alone.
- **`assert()` for recoverable condition** (MEDIUM) — `assert` compiled out in
  release; recoverable condition turned fatal in debug.
- **No test suite** (MEDIUM) — "zero tests. The code compiles. That is all that
  was verified."
- **`TCPConnect` addrinfo leak** (MEDIUM) — previously unanimous; now glm5.2 alone.
- **`socketSetNonBlockNoDelay` return ignored** (MEDIUM) — blocking socket can
  hang the event loop.
- `MAX_CLIENTS` comment contradicts name (LOW).
- Dead code in client — unreachable `close(s); return 0;` (LOW).
- `read()` from stdin does not handle `EINTR` (LOW).
- `chatMalloc`/`chatRealloc` OOM abort — acceptable, noted with tradeoff (LOW).
- Makefile `.PHONY` missing (LOW).
- Makefile `CFLAGS` ordering — flags after sources (LOW).

### mistral only
- 25 LOW findings, no CRITICAL or HIGH. Several are false positives or
  self-contradictory:
  - "No handling for `free()` failure" — `free()` returns `void`; the fix says
    "Remove the check for free() return value — it is not necessary," contradicting
    the finding.
  - "No handling for `bind()` failure" — the code does check `bind()` return and
    exits on failure. False positive.
  - "No handling for `$(CC)` failure in build rules" — `make` exits on non-zero
    return by default. The fix (`|| exit 1`) is redundant.
  - "No handling for `setsockopt()` failure in `createTCPServer()`" — the code
    checks and exits. False positive.
- The review's own summary says "LOW: 14" but there are 25 `[LOW]` headers. The
  model miscounted its own findings.
- The verdict says "does not pass" but also "these issues are not blockers" —
  internally contradictory.

## Skill quality observations

### Trigger labeling
All three models applied trigger labels (invariant-true, invariant-false,
guideline) and cited specific trigger numbers. glm5.2's labeling is the most
precise — every finding maps to a numbered trigger with the theme name. gpt-oss
labels are correct but less specific. mistral labels are present but often
mismatched: several findings are labelled "invariant-true" with trigger 7.3
("does not clean up resources on error paths") for issues that are really about
unchecked returns, not resource cleanup.

### Voice and tone
glm5.2 has the strongest Torvalds voice: "This is complete and utter shit,"
"This is untested code, and it shows," "the predictable consequences of
shipping code with no tests." Profanity is reserved for CRITICAL findings on
negligent bugs, matching the soul's directive. gpt-oss is direct but more
measured — no profanity this run (previously it was the most profuse). mistral's
voice is flat and formulaic — the closing quote attempts Torvalds' tone but the
body reads like a checklist.

### Coverage vs. precision tradeoff
- **glm5.2**: 16 findings, 2 CRITICAL, 3 HIGH. Found every consequential bug in
  the codebase. Highest signal-to-noise ratio. The only model that found bugs
  no other model found at CRITICAL severity. 2,840 words — thorough but not
  bloated.
- **gpt-oss-120b**: 9 findings, 1 CRITICAL. Found the nickname bug (which glm5.2
  also found) but missed SIGPIPE, `acceptClient(-1)`, `select()` EINTR, fd
  bounds, and the addrinfo leak — all of which it caught in the previous run.
  667 words — very concise, but the brevity came at the cost of missing
  correctness bugs.
- **mistral**: 25 findings, 0 CRITICAL, 0 HIGH. Highest count, lowest signal.
  Several false positives. Missed every CRITICAL bug. The review that previously
  had the highest signal-to-noise ratio now has the lowest. 2,194 words — much
  of it spent on low-value findings like "magic value `-O2` lacks justification."

### Regression from previous run
The skill regeneration affected the three models very differently:
- **glm5.2** improved or maintained quality on every dimension. It is now the
  clear standout.
- **gpt-oss-120b** became more concise (4,076 → 667 words) but lost coverage on
  critical bugs it previously caught. The conciseness may be a side effect of the
  tightened prompt — the model may be interpreting the "no useless commentary"
  directive too aggressively and skipping findings.
- **mistral** collapsed. The model that previously produced the sharpest, most
  economical review now produces volume over signal. The 25 LOW findings suggest
  the model is pattern-matching on the trigger list rather than reasoning about
  severity. The skill prompt changes may have pushed mistral toward breadth over
  depth.

## Recommendation

For a codebase of this size (<1000 LOC), glm5.2 is now the strongest single-model
reviewer. It found every CRITICAL bug, maintained the Torvalds voice, and
produced the most precise trigger labeling. If running one model only, use glm5.2.

For production review, run at least two models and union the findings. gpt-oss
caught the nickname bug with the right severity (CRITICAL) where glm5.2 rated it
HIGH — the severity calibration differs even when both find the same bug. But
glm5.2 caught four CRITICAL/HIGH bugs that gpt-oss missed entirely.

The previous run's recommendation (mistral for signal-to-noise, gpt-oss for
breadth, glm5.2 as middle ground) no longer holds. The regenerated skill files
shifted the models' behavior: glm5.2 improved, gpt-oss narrowed, and mistral
collapsed. This suggests the skill prompt changes interact differently with
different models — a finding worth tracking as the skill evolves further.
