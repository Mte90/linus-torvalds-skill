---
title: Skill variant comparison — antirez/smallchat
date: 2026-08-06
target: antirez/smallchat (706 LOC, C)
models: [gpt-oss-120b, glm5.2, mistral-small-4-119b]
---

# Skill Variant Comparison

Three LLM models reviewed the same codebase (antirez/smallchat, 706 LOC) using
three language-agnostic skill variants generated from the same extracted patterns.
Each model received its matching skill file and soul file. This document
synthesizes where they agree, where they diverge, and what that says about the
skill + model combination.

## Headline numbers

| Metric | gpt-oss-120b | glm5.2 | mistral-small-4-119b |
|--------|-------------|--------|----------------------|
| Findings (total) | 21 | 15 | 12 |
| CRITICAL | 2 | 2 | 3 |
| HIGH | 1 | 2 | 1 |
| MEDIUM | 9 | 5 | 4 |
| LOW | 9 | 6 | 4 |
| Report words | 4,076 | 3,449 | 2,426 |
| Verdict | Does not pass | Does not pass | Does not pass |

All three models reach the same verdict: the code does not pass Torvalds' review.
The severity distribution and finding counts differ, and one divergence matters.

## Consensus findings (all three agree)

These are the defects every model flagged. They are the high-confidence core of
the review — three independent models applying three skill variants all fired on
the same triggers.

### 1. SIGPIPE kills the server — CRITICAL (unanimous)

`write()` to a dead socket raises `SIGPIPE`; no `signal(SIGPIPE, SIG_IGN)`
anywhere. First ungraceful client disconnect terminates the server. All three
models classify this CRITICAL and cite the same fix: one line,
`signal(SIGPIPE, SIG_IGN)`.

Trigger fired: recoverable condition turned fatal (invariant-false).

### 2. Unchecked `accept()` return → `createClient(-1)` — CRITICAL (unanimous)

`acceptClient()` returns `-1` on `EMFILE`/`ECONNABORTED`; the return is passed
straight to `createClient()`, which indexes `Chat->clients[-1]` — out-of-bounds
read (assert) then write. Fires under load, the worst possible time. All three
flag CRITICAL; fix is `if (fd == -1) continue;`.

Trigger fired: unchecked error return, state corruption (invariant-false).

### 3. No bounds check on `fd` before `clients[fd]` indexing — HIGH (unanimous)

`MAX_CLIENTS 1000` is the array bound but nothing validates `fd < MAX_CLIENTS`.
A high fd (raised `ulimit -n`) writes past the array. `FD_SET(j, &readfds)`
with `j >= FD_SETSIZE` (1024) corrupts the `fd_set`. gpt-oss and glm5.2 rate
HIGH; mistral folds it into the `accept` finding. Same defect, same fix.

### 4. `select()` exits on `EINTR` — MEDIUM (unanimous)

`select() == -1` calls `exit(1)` with no `errno == EINTR` check. A single
delivered signal kills the server (or client — both have the bug). The author
handles `EINTR` correctly in `acceptClient` (chatlib.c:122) but not here.
Inconsistent. Fix: `if (errno == EINTR) continue;`.

### 5. `setRawMode()` return discarded — MEDIUM (unanimous)

`setRawMode()` returns `-1` on non-tty; caller throws it away. Client runs
line-editing machinery on a pipe, writes escape codes into stdout, busy-loops
on EOF. All three flag it. Fix: check the return.

### 6. `TCPConnect` leaks `servinfo` on `EINPROGRESS` — HIGH/MEDIUM (unanimous)

`chatlib.c:94` returns `s` without `freeaddrinfo(servinfo)`. Latent (no current
caller uses `nonblock=1`) but a real leak in the public API contract. Severity
varies (gpt-oss MEDIUM, glm5.2 HIGH, mistral HIGH) — all agree it's a defect.

### 7. `chatRealloc` exported but unused — LOW (unanimous)

Declared in `chatlib.h`, defined in `chatlib.c`, never called. Dead public API
surface. All three recommend removal.

## Key divergence: the un-NUL-terminated nickname

**Only mistral-small-4-119b found this.** gpt-oss-120b and glm5.2 both missed it.

```c
int nicklen = snprintf(nick, sizeof(nick), "user:%d", fd);
c->nick = chatMalloc(nicklen+1);
memcpy(c->nick, nick, nicklen);   // copies nicklen bytes — NO NUL
```

`snprintf` returns the count excluding the terminator. `chatMalloc` wraps `malloc`
(not `calloc`), so byte `nicklen` is uninitialized heap garbage. `c->nick` is
not a C string from this point. Every `printf("%s", c->nick)`, every `strcmp`,
every relay reads past the allocation until it hits a zero byte. **Heap over-read
on every connection.**

The `/nick` path four screens down does it correctly:
```c
memcpy(c->nick, arg, nicklen+1);   // +1, copies the NUL
```

One path copies `nicklen`, the other copies `nicklen+1`. Copy-paste error. Mistral
caught the asymmetry; the other two did not.

This is the most consequential divergence in the three reviews. It means:
- mistral found a CRITICAL correctness bug that fires on **every** connection,
  not just edge cases.
- gpt-oss-120b and glm5.2, reviewing the same 278-line file with the same
  skill, both missed it.

Why mistral caught it and the others didn't is worth noting: mistral's skill
variant (`SKILL-Mistral.md`) may phrase the "unsafe memory access" trigger more
broadly, or the model may simply be more attuned to `snprintf` return semantics.
Either way, this is a real bug that two of three reviews would have let through.

## Findings unique to one model

### gpt-oss-120b only
- `_POSIX_C_SOURCE` defined only in `chatlib.c` → implicit declarations in server
  and client TUs under `-std=c99` (MEDIUM). Correct and subtle — a portability
  bug masked by glibc leniency.
- Makefile: `CFLAGS` placed after source files (MEDIUM).
- Client `IB_MAX` off-by-one drops trailing newline at 128 chars (LOW).
- `atoi(argv[2])` for port, no validation (LOW).
- Magic number `127` for DEL key (LOW).
- `createTCPServer` binds `INADDR_ANY` with no bind-address option (LOW).

### glm5.2 only
- Comment contradicts code: says "retry on connect failure", code `break`s (MEDIUM).
  Real bug: `getaddrinfo` returning IPv4+IPv6 won't fall back to IPv6 on connect
  failure. The comment lies about the behavior.
- `chatlib.h` not self-contained: uses `size_t` without `<stddef.h>` (LOW).
- `assert.h` included but unused in `smallchat-client.c` (LOW).
- 1-second `select()` timeout with empty handler — speculative code (LOW).

### mistral only
- **Un-NUL-terminated nickname** (CRITICAL) — the headline divergence above.
- Client `read()` errors swallowed and used as loop bound: `count = -1` flows into
  `j < count`, loop skipped by signed-comparison accident (MEDIUM).

## Skill quality observations

### Trigger labeling
All three models applied trigger labels (invariant-true, invariant-false,
precedence, guideline) and respected the precedence hierarchy
(correctness > performance > complexity > style > API stability). The skill
prompt's labeling requirement is working across all three model variants.

### Voice and tone
All three adopted Torvalds' voice from their respective soul files: direct,
blunt, profane on the negligent bugs. gpt-oss-120b is the most profuse with
profanity ("a goddamn chat server", "total moron", "STUPID"). glm5.2 is blunt
but slightly more measured. mistral is the most economical — fewer words,
sharper cuts. All three reserve profanity for the CRITICAL findings, matching
the soul's rule that profanity is for dangerous/negligent defects.

### Coverage vs. precision tradeoff
- **gpt-oss-120b**: highest finding count (21), broadest coverage, caught the
  subtle `_POSIX_C_SOURCE` portability issue. Missed the nickname NUL bug.
  Most verbose report (4,076 words).
- **glm5.2**: middle count (15), caught the comment/code contradiction and
  header self-containment. Missed the nickname NUL bug. Good balance of
  coverage and precision.
- **mistral**: lowest count (12), but found the unique CRITICAL (nickname NUL)
  and the read-error-as-loop-bound bug. Most economical report (2,426 words).
  Highest signal-to-noise ratio.

## Recommendation

For a codebase of this size (<1000 LOC), all three skill variants produce a
usable review. The divergence on the nickname bug shows that no single model is
sufficient for a correctness review — a multi-model pass catches what any one
misses.

If running one model only:
- **mistral** gives the highest signal-to-noise and found the most consequential
  unique bug, but at the cost of missing the portability and build-system issues.
- **gpt-oss-120b** gives the broadest coverage and catches build/portability
  issues, but missed a heap over-read.
- **glm5.2** is the middle ground: solid coverage, good precision, but no unique
  CRITICAL findings.

For production review, run at least two models and union the findings. The
nickname bug is the proof: mistral caught what the other two missed, but mistral
missed what gpt-oss caught.
