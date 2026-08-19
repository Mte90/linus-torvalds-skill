---
title: Skill variant comparison — antirez/smallchat
date: 2026-08-19
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

This run uses skill and soul files regenerated on 2026-08-19 after expanding the
interview corpus from 6 to 67 sources and wiring interview data into both the
soul and skill generation pipelines. The previous run (2026-08-12) used 6
interview sources feeding only the soul pipeline.

## Headline numbers

| Metric | gpt-oss-120b | glm5.2 | mistral-small-4-119b |
|--------|-------------|--------|----------------------|
| Findings (total) | 13 | 18 | 8 |
| CRITICAL | 2 | 2 | 1 |
| HIGH | 8 | 5 | 3 |
| MEDIUM | 0 | 4 | 2 |
| LOW | 3 | 7 | 2 |
| Report words | 855 | 3,069 | 1,527 |
| Verdict | FAIL | FAIL | FAIL |

All three models agree the code fails. No model approves code with known
memory-corruption bugs.

### Shift from previous run (Aug 12 → Aug 19)

| Metric | gpt-oss-120b | glm5.2 | mistral-small-4-119b |
|--------|-------------|--------|----------------------|
| Findings (prev) | 18 | 12 | 15 |
| Findings (now) | 13 | 18 | 8 |
| CRITICAL (prev) | 4 | 1 | 1 |
| CRITICAL (now) | 2 | 2 | 1 |
| Words (prev) | 936 | 2,350 | 1,993 |
| Words (now) | 855 | 3,069 | 1,527 |
| Verdict (prev) | FAIL | FAIL | FAIL |
| Verdict (now) | FAIL | FAIL | FAIL |

The interview corpus expansion (6 → 67 sources) and the wiring of interview data
into the skill pipeline affected the three models differently:

- **glm5.2 grew**: 12 → 18 findings, 1 → 2 CRITICAL. The expanded interview data
  gave the reasoning model more material to work with. It now finds both
  `acceptClient(-1)` memory corruption AND the missing fd bounds check — two
  distinct CRITICAL bugs on the accept path. Word count grew from 2,350 to 3,069.

- **gpt-oss tightened**: 18 → 13 findings, 4 → 2 CRITICAL. The previous run
  double-counted the chatMalloc OOM bug across two files; the new run reports
  each bug once. The two remaining CRITICALs (assert misuse, setRawMode) are
  both real. Precision improved.

- **mistral narrowed**: 15 → 8 findings. The previous run's 9 HIGH count was
  inflated by repeating the "ignored error return" pattern across call sites.
  The new run is more selective but still finds the real bugs. It is the only
  model that flags the `/nick` embedded-null-byte memory safety issue.

## Consensus findings

All three models agree on the core failure: the code has real bugs that must be
fixed before merge. Five findings are shared by at least two models:

1. **`assert` used for runtime validation** (gpt-oss CRITICAL, glm5.2 HIGH) —
   `assert(Chat->clients[c->fd] == NULL)` at server.c:85 aborts the server on a
   recoverable condition. Under `-DNDEBUG` the check vanishes entirely, silently
   corrupting. gpt-oss rates this CRITICAL; glm5.2 rates it HIGH but notes the
   debug-crashes/release-corrupts dual failure mode.

2. **`write()` return values ignored** (gpt-oss HIGH, glm5.2 HIGH) — every
   `write()` to a client socket discards the return. Partial writes silently
   truncate messages; failed writes (EPIPE, ECONNRESET) leave dead clients
   uncleaned. Both models flag this across server.c:143, 194, 248.

3. **`setRawMode` terminal state not restored on error** (gpt-oss CRITICAL,
   mistral HIGH) — `atexit_registered` is set before `tcgetattr` succeeds, so
   cleanup tries to restore a terminal state that was never saved. gpt-oss
   rates this CRITICAL; mistral rates it HIGH and provides a full cleanup-handler
   fix.

4. **`chatMalloc`/`chatRealloc` exit on OOM** (gpt-oss HIGH, glm5.2 MEDIUM) —
   `exit(1)` on out-of-memory takes down every connected client for a single
   failed allocation. gpt-oss rates it HIGH; glm5.2 rates it MEDIUM and calls
   the "recovery is futile" comment "an excuse, not a justification."

5. **`MAX_CLIENTS` hard-coded limit** (gpt-oss HIGH, glm5.2 MEDIUM) — the
   constant caps the server at 1000 clients with no runtime configuration.
   glm5.2 additionally notes the name is misleading: it's used as an array size
   indexed by fd, not a client count.

### Bugs only glm5.2 found

glm5.2 remains the sole model that found the most consequential bug:

1. **`acceptClient()` return unchecked → `createClient(-1)`** (CRITICAL) —
   `accept()` failure passes `-1` to `createClient`, which writes to
   `Chat->clients[-1]` — out-of-bounds memory corruption. Triggered by EMFILE,
   ECONNABORTED, or any transient accept failure under load.

2. **No bounds check on fd before array indexing** (CRITICAL) — `createClient()`
   uses `c->fd` as an index into `Chat->clients[MAX_CLIENTS]` without checking
   `c->fd < MAX_CLIENTS`. Any fd >= 1000 corrupts memory.

glm5.2 also found three bugs no other model caught:

3. **Non-blocking read treated as disconnect on EAGAIN/EINTR** (HIGH) — client
   sockets are non-blocking, but `read() <= 0` is treated as "disconnected."
   EAGAIN and EINTR are recoverable; the code drops healthy clients.

4. **Memory leak on EINPROGRESS path in `TCPConnect`** (HIGH) —
   `freeaddrinfo(servinfo)` is skipped when `connect()` returns EINPROGRESS with
   `nonblock` set. Every non-blocking connect leaks a `struct addrinfo` chain.

5. **`chatRealloc` exported but never called** (MEDIUM) — defined in chatlib.c,
   declared in chatlib.h, zero callers. Unused public export.

### Bugs only gpt-oss found

gpt-oss found two issues neither other model flagged:

1. **`socketSetNonBlockNoDelay` return ignored** (HIGH) — server.c:81 calls it
   with "Pretend this will not fail." The socket may remain in blocking mode on
   error.

2. **`IB_MAX` hard-coded input buffer limit** (HIGH) — client.c:118 limits line
   length to 128 bytes; longer input is silently dropped.

### Bugs only mistral found

Mistral found one bug neither other model flagged:

1. **`/nick` memory safety with embedded null bytes** (CRITICAL) —
   `strlen(arg)` truncates at the first null byte, but `memcpy(c->nick, arg,
   nicklen+1)` copies past it. If `arg` contains embedded nulls, `nicklen` is
   shorter than the actual allocation, and the copy reads uninitialized heap
   memory. gpt-oss and glm5.2 both flag `/nick` for unbounded length (both LOW);
   only mistral identifies the null-byte memory safety issue.

Mistral also raised two process-level findings the other models missed:

2. **Missing error documentation in `chatlib.h`** (MEDIUM) — no function-level
   docs force every caller to rediscover error handling patterns.

3. **Missing `test` target in Makefile** (LOW) — no automated verification.

## Skill quality observations

### Trigger labeling

glm5.2's trigger labeling remains the most precise — every finding maps to a
named trigger with type labels (invariant-false, invariant-true, guideline).
gpt-oss labels triggers by name without the type annotation. Mistral uses
numbered triggers (#21, #3, #20) referencing the skill's trigger catalog — a
different but valid approach.

### Voice and tone

glm5.2 has the strongest Torvalds voice: "You don't crash a server because
accept() failed. You log it and you move on." and "There is *no* excuse for
killing the server for something like this." Direct, technical, profane where
warranted. gpt-oss is measured but forceful. Mistral's voice is the weakest —
correct in structure but reads more like a checklist than a review, with a
generic closing quote attributed to Torvalds rather than an original voice.

### Coverage vs. precision tradeoff

- **glm5.2**: 18 findings, 2 CRITICAL, 5 HIGH. Found both accept-path memory
  corruption bugs that no other model found. Highest precision — every finding
  maps to a specific code location with a concrete fix and code example. 3,069
  words — thorough but not bloated. The clear standout for bug-finding.

- **gpt-oss-120b**: 13 findings, 2 CRITICAL, 8 HIGH. Widest HIGH coverage —
  flags socketSetNonBlockNoDelay and IB_MAX that glm5.2 misses. 855 words —
  the most concise. No code examples in the findings, which limits
  actionability compared to glm5.2.

- **mistral**: 8 findings, 1 CRITICAL, 2 HIGH. Most selective — only flags
  what it considers the highest-impact issues. Found the /nick null-byte bug
  no other model caught. 1,527 words. The model is functional as a reviewer
  but should not be used solo (it missed acceptClient(-1) and the fd bounds
  check).

## Recommendation

For a codebase of this size (<1000 LOC), glm5.2 remains the strongest
single-model reviewer. It found both CRITICAL memory-safety bugs on the accept
path that no other model found, maintained the strongest Torvalds voice, and
produced the most precise trigger labeling with concrete code fixes.

For production review, run at least two models and union the findings. gpt-oss
catches socketSetNonBlockNoDelay and IB_MAX that glm5.2 skips; glm5.2 catches
acceptClient(-1) and the fd bounds check that gpt-oss misses. Together they
cover more ground than either alone.

Mistral is functional as a reviewer — it produces real findings and correctly
fails the code. It should not be used as a sole reviewer (it missed both
accept-path CRITICALs), but it catches the /nick null-byte issue that both other
models miss. As a third model in a union, it adds value.
