---
model: glm5.2
skill: linus-torvalds-skill/SKILL-GLM.md
soul: soul/soul-glm.md
target: antirez/smallchat
date: 2026-08-06
---

# Code Review: antirez/smallchat

A 278-line chat server, a 261-line client, a 153-line library, a 14-line
header, and a Makefile. The author calls it "the most simple chat system
ever possible." That's fine as a goal. Simplicity is a feature. But simple
code still has to be *correct* code. A teaching example that crashes on the
single most common event in a chat server — a client disconnecting — does
not teach the right lesson.

The skill defines a **Bug** as "a condition that causes incorrect behavior,
crashes, data corruption, or security vulnerabilities." This codebase has
two of those that will fire under normal operation, not edge cases. They
are not subtle. They are the kind of thing where the fix is one line and
the absence of that line is negligence.

The precedence hierarchy is **correctness > performance > complexity >
style > API stability**. Everything below follows that order.

---

## smallchat-server.c

### [CRITICAL] SIGPIPE kills the server when any client disconnects
- **Type:** invariant-false
- **Trigger:** 5.1 — Turning a recoverable condition into a fatal error
- **Location:** smallchat-server.c:143 (`sendMsgToAllClientsBut`), :194, :248 — every `write()` call
- **Issue:** The server uses `write()` to send messages to clients. When a client disconnects abruptly (network drop, killed process, TCP RST), the next `write()` to that client's socket generates `SIGPIPE`. The default disposition of `SIGPIPE` is to terminate the process. No `signal(SIGPIPE, SIG_IGN)` is installed anywhere. No `send()` with `MSG_NOSIGNAL` is used.

  This is not a race condition. It is deterministic. Client A sends a message. Client B has sent a RST. `select()` reports both as readable. The server processes them in fd order. If B's fd is higher than A's, the server reads A's message, calls `sendMsgToAllClientsBut`, and `write()`s to B's dead socket. `SIGPIPE`. Server is dead.

  The skill says: "anybody who makes a hard error out of something that is recoverable is a total moron." A client disconnecting is the most recoverable condition in a chat server. It is the *normal* operation. Killing the server for it is inexcusable.

- **Fix:** Add `signal(SIGPIPE, SIG_IGN);` at the start of `initChat()`. One line. Or replace every `write()` to a socket with `send(fd, buf, len, MSG_NOSIGNAL)`. The first option is simpler and correct.

### [CRITICAL] `acceptClient()` return value not checked — `createClient(-1)` corrupts memory
- **Type:** invariant-false
- **Trigger:** 2.6 — Corrupting existing state during an operation
- **Location:** smallchat-server.c:188-189
- **Issue:** `acceptClient()` can return `-1` on any `accept()` failure (`EMFILE`, `ENFILE`, `ENOBUFS`, `ECONNABORTED`). The return value is passed directly to `createClient(fd)` with no check.

  `createClient(-1)` does the following:
  1. `socketSetNonBlockNoDelay(-1)` — fails, return ignored (line 81)
  2. `c->fd = -1`
  3. `assert(Chat->clients[-1] == NULL)` — out-of-bounds read (line 85). On 64-bit, `clients[-1]` overlaps `Chat->maxclient`. The assert reads `maxclient` reinterpreted as a pointer.
  4. `Chat->clients[-1] = c` — **out-of-bounds write** (line 86). This overwrites `Chat->maxclient` (and padding) with a heap pointer. `maxclient` becomes a value like `0x55555555a010`.
  5. The main loop's `for (int j = 0; j <= Chat->maxclient; j++)` now iterates billions of times, accessing `Chat->clients[j]` far out of bounds. Segfault.

  The skill defines state corruption as "among the most dangerous bugs because it may not manifest immediately but causes cascading failures later." This one manifests immediately — the server crashes on the next loop iteration. But the root cause (no return value check) is the bug. The crash is the symptom.

  `acceptClient` in `chatlib.c:114` correctly retries on `EINTR` and returns `-1` on other errors. The caller just doesn't check. That's the defect.

- **Fix:** After `int fd = acceptClient(Chat->serversock);`, add `if (fd == -1) continue;`. Skip the iteration if accept failed. Do not call `createClient` with an invalid fd. This is not optional.

### [HIGH] No bounds check on file descriptor before array access
- **Type:** invariant-false
- **Trigger:** 2.6 — Corrupting existing state during an operation
- **Location:** smallchat-server.c:85-88 (`createClient`)
- **Issue:** `Chat->clients` is declared as `struct client *clients[MAX_CLIENTS]` with `MAX_CLIENTS 1000`. The array is indexed by file descriptor: `Chat->clients[c->fd] = c`. There is no check that `c->fd < MAX_CLIENTS`.

  File descriptors are not bounded by `MAX_CLIENTS`. On a default Linux system, `RLIMIT_NOFILE` soft limit is 1024. Fds 1000–1023 are valid and would write past the end of the array. If the soft limit is raised (common for servers: `ulimit -n 65536`), fds can go much higher. Each out-of-bounds write corrupts whatever follows the `clients` array in the `chatState` struct — or past the end of the heap allocation.

  The comment on line 45 says `// This is actually the higher file descriptor.` That's wrong. It's the array size. The highest file descriptor is whatever the OS assigns, and `createClient` trusts it blindly.

  Additionally, `FD_SET(j, &readfds)` in the main loop (line 166) uses `j` as an fd. `FD_SET` with `fd >= FD_SETSIZE` (typically 1024) corrupts the `fd_set` on the stack. So even if `MAX_CLIENTS` were raised to match `FD_SETSIZE`, the `select()` call would corrupt memory at `fd >= 1024`.

- **Fix:** In `createClient`, before `Chat->clients[c->fd] = c`, check `if (c->fd >= MAX_CLIENTS) { close(c->fd); free(c->nick); free(c); return NULL; }`. Also check the return of `createClient` in the caller. And document that `MAX_CLIENTS` must not exceed `FD_SETSIZE`.

### [MEDIUM] `assert()` used for error handling — fatal for a recoverable condition
- **Type:** invariant-false
- **Trigger:** 2.1 — Fatal assertion/panic used for a recoverable condition
- **Location:** smallchat-server.c:85
- **Issue:** `assert(Chat->clients[c->fd] == NULL);` — If the slot is occupied (which shouldn't happen in normal operation, but *can* happen if `acceptClient` returns a reused fd that wasn't properly cleaned up), the assert kills the server.

  Two problems:
  1. Asserts are compiled out with `-DNDEBUG`. Release builds silently skip the check and overwrite the slot, leaking the old client. The comment says "This should be available" — but if it isn't, the assert is either a crash (debug) or silent corruption (release). Neither is acceptable.
  2. Even with asserts enabled, crashing the server because a slot is occupied is a fatal response to a recoverable condition. Log it, skip the client, return `NULL`. Don't kill the server.

  The skill says: "There is *no* excuse for killing the kernel for things like this." This isn't the kernel, but the principle is the same: a slot collision is a data consistency issue, not a reason to terminate.

- **Fix:** Replace the assert with an `if` check. If the slot is occupied, log a warning, close the new fd, and return `NULL`. Have the caller check the return.

### [MEDIUM] `socketSetNonBlockNoDelay()` return value ignored
- **Type:** invariant-false
- **Trigger:** 5.3 — Not cleaning up resources on error paths
- **Location:** smallchat-server.c:81 (`createClient`)
- **Issue:** `socketSetNonBlockNoDelay(fd); // Pretend this will not fail.` — The comment acknowledges the problem and dismisses it. If `fcntl(F_SETFL)` fails, the socket remains in blocking mode. The entire `select()` loop assumes non-blocking sockets. A blocking `read()` on a client socket would hang the server indefinitely, freezing all clients.

  "Pretend this will not fail" is not a design decision. It's a prayer. `fcntl` can fail (`EBADF`, `EINVAL`, `EPERM`). If it does, the server hangs on the next read from that client. That's not "simple" — that's broken.

- **Fix:** Check the return. If `socketSetNonBlockNoDelay(fd) == -1`, close the fd, free the client, return `NULL`. Let the caller handle it.

### [LOW] `select()` returns `-1` on `EINTR`, server exits
- **Type:** invariant-false
- **Trigger:** 5.1 — Turning a recoverable condition into a fatal error
- **Location:** smallchat-server.c:179-182
- **Issue:** `select()` can return `-1` with `errno == EINTR` when interrupted by a signal that has a handler installed. The code calls `exit(1)` on any `select()` error, including `EINTR`.

  Currently no signal handlers are installed, so `EINTR` won't trigger in normal operation (signals with `SIG_IGN` or default-ignore disposition don't cause `EINTR`). But this is still wrong. The day someone adds a `SIGCHLD` handler or a `SIGALRM` timer — both reasonable for a server — `select()` returns `EINTR` and the server dies.

- **Fix:** After `if (retval == -1)`, check `if (errno == EINTR) continue;` before the `exit(1)`.

### [LOW] One-second `select()` timeout with an empty handler
- **Type:** guideline
- **Trigger:** Anti-pattern 1 — Over-engineering for theoretical needs (Trigger 3.3 adjacent)
- **Location:** smallchat-server.c:171-175
- **Issue:** The `select()` timeout is set to 1 second. The timeout branch (line 271-275) is empty: "We don't do anything right now." The timeout serves no current purpose. It wakes the server up every second for nothing.

  This is speculative code for "future" use. The skill's Anti-pattern 1 says: "Speculative generality adds complexity and bugs without solving real problems. When the real need arrives, the speculative abstraction is usually wrong anyway." If you need periodic wakeups later, add them then. For now, use `NULL` timeout (block until activity) and remove the empty branch.

- **Fix:** Set the `select()` timeout to `NULL` and remove the empty `else` branch. Or leave it if you genuinely plan to use it soon — but document why.

---

## smallchat-client.c

### [MEDIUM] `write()` to server can trigger `SIGPIPE`, killing the client ungracefully
- **Type:** invariant-false
- **Trigger:** 5.1 — Turning a recoverable condition into a fatal error
- **Location:** smallchat-client.c:248 (`write(s, ib.buf, ib.len)`)
- **Issue:** When the server closes the connection, the client's `write()` to the socket can generate `SIGPIPE`. No `SIG_IGN` is installed. The client dies from `SIGPIPE` instead of detecting the disconnect via `read()` and printing "Connection lost."

  The window is narrow — `select()` reports the server socket as readable on disconnect, and the client detects it before the next `write()` in most cases. But if the user types a character between the server's close and the client's next `select()` return, the `write()` hits a dead socket and `SIGPIPE` kills the process.

  For a client, this is less catastrophic than for the server. But dying from `SIGPIPE` instead of a clean error message is wrong. The user sees no output, no error — the terminal just stops working.

- **Fix:** `signal(SIGPIPE, SIG_IGN);` at the start of `main()`. Then handle `write()` returning `-1` with `errno == EPIPE` as a connection-lost condition.

### [MEDIUM] `setRawMode()` return value not checked
- **Type:** invariant-false
- **Trigger:** 5.3 — Not cleaning up resources on error paths
- **Location:** smallchat-client.c:204
- **Issue:** `setRawMode(fileno(stdin),1);` — return value ignored. If `setRawMode` fails (not a TTY, `tcgetattr` fails), the client continues without raw mode. Terminal behavior is wrong: line buffering is on, characters aren't echoed individually, backspace doesn't work as expected. The user gets a broken experience with no error message.

  `setRawMode` returns `-1` on failure. The function even sets `errno = ENOTTY`. But the caller doesn't check.

- **Fix:** `if (setRawMode(fileno(stdin), 1) == -1) { perror("setRawMode"); exit(1); }`

### [LOW] `assert.h` included but `assert` never used
- **Type:** guideline
- **Trigger:** N/A (code cleanliness — no dead includes)
- **Location:** smallchat-client.c:34
- **Issue:** `#include <assert.h>` is present but no `assert()` call appears in the client. Unused include. Minor, but it's the kind of thing that accumulates.

- **Fix:** Remove `#include <assert.h>` from `smallchat-client.c`.

---

## chatlib.c

### [HIGH] Memory leak — `freeaddrinfo()` not called on `EINPROGRESS` return
- **Type:** invariant-false
- **Trigger:** 5.3 — Not cleaning up resources on error paths
- **Location:** chatlib.c:94
- **Issue:** In `TCPConnect`, when `connect()` returns `-1` with `errno == EINPROGRESS` and `nonblock` is set, the function returns `s` directly:
  ```c
  if (errno == EINPROGRESS && nonblock) return s;
  ```
  This skips `freeaddrinfo(servinfo)` on line 107. The `addrinfo` linked list allocated by `getaddrinfo()` is leaked.

  The skill says: "Resource leaks accumulate and eventually cause system failure." This leak happens every time a non-blocking connect is attempted. No current caller uses `nonblock=1` (the client passes `0`), so this is latent. But it's a bug in the library — the day someone uses the non-blocking path, it leaks on every call.

- **Fix:** Before `return s` on line 94, call `freeaddrinfo(servinfo)`.

### [MEDIUM] Comment contradicts code — says "retry on connect failure", code `break`s
- **Type:** invariant-false
- **Trigger:** 9.1 — Comment that misrepresents code behavior
- **Location:** chatlib.c:79-80 (comment) vs. chatlib.c:98 (code)
- **Issue:** The comment says:
  > "If we fail in the socket() call, or on connect(), we retry with the next entry in servinfo."

  The code does `continue` on `socket()` failure (line 82) — that's a retry. But on `connect()` failure (non-`EINPROGRESS`), it does `close(s); break;` (lines 97-98) — that's *not* a retry. It gives up after the first connect failure.

  The consequence: if `getaddrinfo` returns both an IPv4 and an IPv6 address, and the IPv4 `connect()` fails, the function does not try IPv6. The comment claims it does. The skill says: "Misleading comments cause developers to make wrong assumptions about the code, leading to bugs."

  `socket()` failure retries. `connect()` failure does not. The comment is wrong about `connect()`.

- **Fix:** Either change `break` to `continue` on line 98 (to match the comment and actually try the next address), or fix the comment to say "we retry on socket() failure, but give up on connect() failure." Given that trying the next address is the correct behavior for `getaddrinfo` results, changing `break` to `continue` is the better fix.

### [LOW] `chatMalloc`/`chatRealloc` exit on OOM
- **Type:** invariant-false
- **Trigger:** 5.1 — Turning a recoverable condition into a fatal error
- **Location:** chatlib.c:136-153
- **Issue:** Both functions call `exit(1)` on allocation failure. The skill's Trigger 5.1 says "anybody who makes a hard error out of something that is recoverable is a total moron."

  That said, the comment on lines 132-135 makes a defensible case: "in most programs designed to run for a long time, that are not libraries, trying to recover from out of memory is often futile." For a simple chat server, exiting on OOM is a judgment call, not negligence. OOM recovery in C is genuinely hard, and half-hearted recovery is worse than none.

  This is the one case where I'd let it slide — the author thought about it, documented the reasoning, and made a deliberate choice. But it's still technically a Trigger 5.1 violation, so I'm noting it.

- **Fix:** None required for a teaching example. If this were production code, I'd want graceful degradation (reject new connections, log, continue serving existing clients). For this scope, `exit(1)` is acceptable.

### [LOW] `chatRealloc` declared in public API but never called
- **Type:** guideline
- **Trigger:** 12.4 — Unnecessary API surface or flags that burden many callers
- **Location:** chatlib.c:146-153, chatlib.h:12
- **Issue:** `chatRealloc` is defined in `chatlib.c` and declared in `chatlib.h` (public API), but no code in the project calls it. It's permanent maintenance burden for zero current benefit. The skill says: "Each addition to a shared interface is a burden on every caller."

  `chatRealloc` is also subtly wrong: `ptr = realloc(ptr, size)` leaks the old memory if `realloc` fails (the original `ptr` is still valid but the local variable is overwritten). But since it `exit`s on failure, the leak doesn't matter. Still, if anyone ever calls it and `realloc` fails, the old buffer is leaked before `exit` — a minor issue that's masked by the `exit`.

- **Fix:** Remove `chatRealloc` from both `chatlib.c` and `chatlib.h` unless a caller is planned. Unused public API is debt.

### [LOW] `listen()` backlog of 511 is an unexplained magic number
- **Type:** guideline
- **Trigger:** 9.5 — Magic numbers without explanation
- **Location:** chatlib.c:51 (`listen(s, 511)`)
- **Issue:** The backlog is 511. Why 511? Not 512, not 128, not `SOMAXCONN`? The skill says: "Magic numbers are opaque. Future maintainers cannot tell whether the value is correct, why it was chosen, or whether it can be changed."

  On modern Linux, `/proc/sys/net/core/somaxconn` defaults to 4096. A backlog of 511 is silently capped to `somaxconn` by the kernel. On older systems with `somaxconn=128`, the backlog is 128. So 511 is neither the system default nor a documented choice.

- **Fix:** Use `SOMAXCONN` (which respects the system default), or add a comment explaining why 511 was chosen.

---

## chatlib.h

### [LOW] Header is not self-contained — uses `size_t` without including a defining header
- **Type:** guideline
- **Trigger:** 9.4 — Missing documentation for non-obvious behavior or pitfalls
- **Location:** chatlib.h:11-12
- **Issue:** The header declares `void *chatMalloc(size_t size)` and `void *chatRealloc(void *ptr, size_t size)`, but does not include `<stddef.h>` (which defines `size_t`). It relies on the including file having already included a header that defines `size_t`.

  Currently this works because both `smallchat-server.c` and `smallchat-client.c` include `<stdlib.h>` before `chatlib.h`. But a header that requires its includer to have included other headers first is a pitfall. The first person to include `chatlib.h` without a prior `<stdlib.h>` gets a confusing compile error.

  The skill says: "Undocumented pitfalls trap every new user of the API."

- **Fix:** Add `#include <stddef.h>` to `chatlib.h` after the include guard. A header should compile when included alone.

---

## Makefile

### [MEDIUM] `chatlib.h` is not a build dependency — header changes don't trigger rebuild
- **Type:** invariant-false
- **Trigger:** 8.1 — Non-bisectable change (adjacent — build correctness)
- **Location:** Makefile:4-8
- **Issue:** The rules for `smallchat-server` and `smallchat-client` list only `.c` files as dependencies:
  ```makefile
  smallchat-server: smallchat-server.c chatlib.c
  smallchat-client: smallchat-client.c chatlib.c
  ```
  `chatlib.h` is missing. If `chatlib.h` is modified (e.g., changing a function signature), `make` does not rebuild the targets. The resulting binaries are stale — they use the old header, producing silent ABI mismatches.

  This is a build correctness bug. The skill's Trigger 8.1 is about bisectability — a build that doesn't rebuild on header changes produces binaries that don't match the source, which makes bisecting unreliable because the binary doesn't reflect the source state.

- **Fix:** Add `chatlib.h` as a dependency:
  ```makefile
  smallchat-server: smallchat-server.c chatlib.c chatlib.h
  smallchat-client: smallchat-client.c chatlib.c chatlib.h
  ```

---

## Summary

### Verdict: Does not pass.

Two CRITICAL bugs that fire under normal operation. The server dies when a client disconnects (`SIGPIPE`), and the server corrupts its own state when `accept()` fails (unchecked `-1` return). Neither is an edge case. Both are one-line fixes. Both are the kind of bug that anyone who has written network code in C has been bitten by and learned to prevent.

The `SIGPIPE` bug is the worst. A chat server whose job is to handle client connections, and which dies when a client disconnects, is fundamentally broken. It's the equivalent of a web server that crashes when a browser closes a tab. And the fix is `signal(SIGPIPE, SIG_IGN)` — one line, at the top of `initChat()`. Its absence is not a simplification; it's an omission.

The `acceptClient(-1)` bug is the kind of thing that would make me question whether the code was ever tested under any load at all. `accept()` fails under `EMFILE` (too many open files), `ECONNABORTED` (client disconnected during handshake), `EINTR` (handled, but other errors are not). Each of these is a normal condition for a network server. Passing the unchecked `-1` to `createClient` writes to `Chat->clients[-1]`, which overwrites `maxclient` with a heap pointer, which makes the next `select()` loop iterate billions of times and segfault. The fix is `if (fd == -1) continue;`. One line.

The rest of the codebase is what you'd expect from a minimal teaching example: simple, readable, and correct in the happy path. The data structures are straightforward. The main loop is a clean `select()` fan-out. The client's raw-mode handling is well-commented. The `freeClient` maxclient recalculation is correct. The command parsing is minimal but works. The `snprintf` truncation handling on line 261 is actually good — many people get that wrong.

But the skill's precedence is clear: **correctness > everything else**. Two CRITICAL correctness bugs override any positive qualities. The code does not pass.

### Findings by severity

| Severity | Count |
|----------|-------|
| CRITICAL | 2 |
| HIGH | 2 |
| MEDIUM | 5 |
| LOW | 6 |
| **Total** | **15** |

### Findings by file

| File | CRITICAL | HIGH | MEDIUM | LOW | Total |
|------|----------|------|--------|-----|-------|
| smallchat-server.c | 2 | 1 | 2 | 2 | 7 |
| smallchat-client.c | 0 | 0 | 2 | 1 | 3 |
| chatlib.c | 0 | 1 | 1 | 3 | 5 |
| chatlib.h | 0 | 0 | 0 | 1 | 1 |
| Makefile | 0 | 0 | 1 | 0 | 1 |

### What to fix first

1. `signal(SIGPIPE, SIG_IGN);` in `initChat()`. One line. Fixes the server dying on client disconnect.
2. `if (fd == -1) continue;` after `acceptClient()`. One line. Fixes memory corruption on accept failure.
3. Bounds check `c->fd < MAX_CLIENTS` in `createClient`. Fixes out-of-bounds at high connection counts.
4. Check `socketSetNonBlockNoDelay()` return. Fixes potential server hang on fcntl failure.

Four lines of code fix the two CRITICAL and one HIGH bug. The rest is cleanup.
