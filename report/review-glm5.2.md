---
reviewer: linus-torvalds-skill (GLM5.2 soul)
skill: linus-torvalds-skill/SKILL-GLM.md v1.0.0
soul: soul/soul-glm.md v2.0
codebase: antirez/smallchat
files_reviewed: 5
total_loc: 706
date: 2026-08-11
verdict: FAIL
---

# Code Review: antirez/smallchat

A minimal TCP chat server. ~706 lines across five files. The code is clean, readable, and well-structured for what it is — the `freeClient` maxclient rescan is correct, the select loop is organized, and the networking is cleanly separated into `chatlib`. The data design (clients indexed by fd in a flat array) is simple and appropriate for the scope.

That's where the compliments end. The server has two bugs that kill it under completely normal operation, a memory-corruption path on accept failure, and a missing null terminator that leaks heap data to other clients. None of these are subtle. They are the kind of bugs you get when you write networking code without ever running it under load or disconnecting a client. This is untested code, and it shows.

Precedence applied throughout: **Correctness > Performance > Complexity > Style > API-stability.** Every finding below is a correctness or safety defect. No style nits dressed up as findings.

---

## smallchat-server.c

### [CRITICAL] No SIGPIPE handling — server dies on client disconnect
- **Type:** invariant-false
- **Trigger:** 3.1 — Turning a recoverable condition into a fatal error
- **Location:** smallchat-server.c:143 (`sendMsgToAllClientsBut`), no `signal(SIGPIPE, SIG_IGN)` anywhere
- **Issue:** `write(Chat->clients[j]->fd, s, len)` at line 143 is a plain `write()` to a socket. When a client disconnects and the kernel delivers RST, the next `write()` to that socket raises `SIGPIPE`. There is no `signal(SIGPIPE, SIG_IGN)` in `initChat()` or `main()`, no `MSG_NOSIGNAL` flag, no `SO_NOSIGPIPE` setsockopt. The default `SIGPIPE` disposition terminates the process. A client closing its connection is the most normal event in a chat server's life. The server dies on it. This is complete and utter shit.
- **Fix:** Add `signal(SIGPIPE, SIG_IGN);` at the top of `main()` (or `initChat`). Alternatively, use `send(fd, s, len, MSG_NOSIGNAL)` in `sendMsgToAllClientsBut`. Do both — defense in depth costs nothing here.

### [CRITICAL] `acceptClient()` return value unchecked — `createClient(-1)` corrupts memory
- **Type:** invariant-false
- **Trigger:** 2.6 — Corrupting existing state during an operation
- **Location:** smallchat-server.c:188-189
- **Issue:** `acceptClient()` returns `-1` on error (chatlib.c:125). In `main()`:
  ```c
  int fd = acceptClient(Chat->serversock);
  struct client *c = createClient(fd);
  ```
  There is no check. When `accept()` fails (`EMFILE`, `ENFILE`, `ECONNABORTED` — all normal under load), `fd` is `-1` and `createClient(-1)` runs. It executes `Chat->clients[c->fd] = c` → `Chat->clients[-1] = c` — a write to memory *before* the array. That is undefined behavior and memory corruption of whatever sits below `Chat->clients` in the struct (likely `maxclient` or `numclients`). The `assert` at line 85 reads `clients[-1]` first, which is itself an out-of-bounds read. In a release build the assert is gone and the corrupting write proceeds directly.
- **Fix:** Check the return before creating a client:
  ```c
  int fd = acceptClient(Chat->serversock);
  if (fd == -1) continue;  /* or log and continue */
  struct client *c = createClient(fd);
  ```

### [HIGH] Missing null terminator on nick in `createClient` — heap over-read, data leak
- **Type:** invariant-false
- **Trigger:** 7.5 — Exposing stale or freed data to external callers
- **Location:** smallchat-server.c:83-84
- **Issue:** `createClient` builds the initial nick:
  ```c
  int nicklen = snprintf(nick, sizeof(nick), "user:%d", fd);
  ...
  c->nick = chatMalloc(nicklen + 1);
  memcpy(c->nick, nick, nicklen);       /* copies nicklen bytes, NOT nicklen+1 */
  ```
  `snprintf` returns the string length *excluding* the null terminator. `memcpy` copies `nicklen` bytes. The allocated `nicklen+1`th byte is uninitialized heap memory. `c->nick` is not a valid C string. Compare with the `/nick` command path at lines 243-244, which correctly copies `nicklen+1`:
  ```c
  c->nick = chatMalloc(nicklen + 1);
  memcpy(c->nick, arg, nicklen + 1);   /* correct — includes null */
  ```
  The inconsistency confirms this is a bug, not a design choice. The unterminated nick is then passed to `printf("%s", ...)` at line 215 and `snprintf("%s> %s", c->nick, ...)` at line 256 — both read past the allocation until they hit a null byte. The formatted message is sent to every other client via `sendMsgToAllClientsBut`. Uninitialized heap data from the server's allocator leaks to connected clients. That is an information leak.
- **Fix:** `memcpy(c->nick, nick, nicklen + 1);` — copy the null terminator. Or `c->nick[nicklen] = '\0';` after the memcpy.

### [HIGH] No bounds check on fd vs `MAX_CLIENTS` — out-of-bounds array write
- **Type:** invariant-false
- **Trigger:** 2.6 — Corrupting existing state during an operation
- **Location:** smallchat-server.c:45, 86
- **Issue:** `#define MAX_CLIENTS 1000` and `struct client *clients[MAX_CLIENTS]`. The array is indexed by file descriptor: `Chat->clients[c->fd] = c` at line 86. There is no check that `c->fd < MAX_CLIENTS`. If a client connects with fd >= 1000 (possible with a high `ulimit -n` and connection churn, or simply a long-running process with fd recycling gaps), the write is out of bounds. The same fd is used in `FD_SET(j, &readfds)` at line 166 — if `j >= FD_SETSIZE` (typically 1024), `FD_SET` overflows the `fd_set`. Two buffer overflows from one missing check.
- **Fix:** In `createClient`, before `Chat->clients[c->fd] = c`:
  ```c
  if (c->fd >= MAX_CLIENTS) {
      close(c->fd);
      free(c->nick);
      free(c);
      return NULL;
  }
  ```
  And check the return of `createClient` in `main()`. Also rename `MAX_CLIENTS` to `MAX_FD` — it is an fd cap, not a client count.

### [HIGH] `select()` EINTR → `exit(1)` — any signal kills the server
- **Type:** invariant-false
- **Trigger:** 3.1 — Turning a recoverable condition into a fatal error
- **Location:** smallchat-server.c:180-182
- **Issue:**
  ```c
  retval = select(maxfd + 1, &readfds, NULL, NULL, &tv);
  if (retval == -1) {
      perror("select() error");
      exit(1);
  }
  ```
  `select()` returns `-1` with `errno == EINTR` when interrupted by a signal. This is completely normal and recoverable — you retry the loop. `EINTR` is not an error, it is a "try again." Exiting the entire server on a signal delivery is turning a recoverable condition into a fatal one. `acceptClient` in chatlib.c:122-123 correctly retries on `EINTR`; the main loop does not follow its own pattern.
- **Fix:**
  ```c
  if (retval == -1) {
      if (errno == EINTR) continue;
      perror("select() error");
      exit(1);
  }
  ```

### [MEDIUM] `assert()` for a recoverable condition — and compiled out in release
- **Type:** invariant-false
- **Trigger:** 2.1 — Fatal assertion or crash for a recoverable condition
- **Location:** smallchat-server.c:85
- **Issue:** `assert(Chat->clients[c->fd] == NULL);` guards the slot assignment. Two problems. First, if the slot is occupied, that is a logic error (a previous client wasn't freed) — recoverable: free the old client or reject the new connection. Aborting the whole server is killing the kernel for a recoverable condition. Second, `assert` is a no-op when `NDEBUG` is defined (any `-O2 -DNDEBUG` release build). So in debug, the server aborts; in release, the protection vanishes entirely and the old client pointer is silently overwritten, leaking the old client. Neither behavior is correct.
- **Fix:** Replace the assert with a real check:
  ```c
  if (Chat->clients[c->fd] != NULL) {
      freeClient(Chat->clients[c->fd]);
  }
  Chat->clients[c->fd] = c;
  ```

### [MEDIUM] `socketSetNonBlockNoDelay` return ignored — blocking socket can hang the server
- **Type:** invariant-false
- **Trigger:** 3.1 — Turning a recoverable condition into a fatal error
- **Location:** smallchat-server.c:81
- **Issue:** `socketSetNonBlockNoDelay(fd); // Pretend this will not fail.` The comment admits the return is discarded. `socketSetNonBlockNoDelay` returns `-1` on `fcntl` failure (chatlib.c:29-30). If it fails, the socket stays in blocking mode. The server's `sendMsgToAllClientsBut` calls `write()` without checking writability — it relies on the socket being non-blocking so a full kernel buffer returns `EAGAIN` instead of blocking. With a blocking socket and a full send buffer (a slow client), `write()` blocks the entire event loop. Every client stalls. The "pretend this will not fail" comment is a workaround for a condition that is recoverable: report the error, close the socket, reject the client.
- **Fix:** Check the return:
  ```c
  if (socketSetNonBlockNoDelay(fd) == -1) {
      close(fd);
      free(c->nick);
      free(c);
      return NULL;
  }
  ```

### [MEDIUM] No test suite — code is entirely untested
- **Type:** invariant-false
- **Trigger:** 9.1 — Submitting untested code
- **Location:** repository root (no test files exist)
- **Issue:** There are zero tests. No unit tests, no integration tests, no test harness. The SIGPIPE bug, the `acceptClient(-1)` corruption, and the missing null terminator would all have been caught by a basic integration test that connects a client, sends a message, and disconnects. The code compiles. That is all that was verified. "It compiles for me, but that's all I actually checked" is not a testing strategy.
- **Fix:** Add at minimum: a test that starts the server, connects two clients, sends a message, and disconnects one — verifying the server survives. Add a test for `createClient` with fd=-1 and fd>=MAX_CLIENTS. The bugs found in this review are the evidence that untested code is almost certainly wrong.

### [LOW] `MAX_CLIENTS` comment contradicts the name
- **Type:** invariant-false
- **Trigger:** 10.1 — Comments that contradict the code
- **Location:** smallchat-server.c:45
- **Issue:** `#define MAX_CLIENTS 1000 // This is actually the higher file descriptor.` The name says "max clients" (a count). The comment says "actually the higher file descriptor" (an fd cap). It is neither — it is the array bound, used to size `clients[]` and implicitly the max allowed fd. A reader who trusts the name will reason about client counts; a reader who trusts the comment will reason about fd limits. Both are wrong. The constant does triple duty (array size, fd cap, implicit client limit) and the comment does not clarify which.
- **Fix:** Rename to `MAX_FD`, size the array to `MAX_FD + 1`, and document: `/* Sockets with fd > MAX_FD are rejected. Array is indexed by fd. */`

---

## smallchat-client.c

### [MEDIUM] `write()` to server return ignored — messages silently truncated
- **Type:** invariant-false
- **Trigger:** 3.2 — Not cleaning up resources on an error path
- **Location:** smallchat-client.c:248
- **Issue:** `write(s, ib.buf, ib.len);` sends the completed line to the server. The return value is discarded. A partial write (kernel buffer full, large message) means the message is silently truncated — the server receives half a line. The client never retries the remainder. For a chat client, this means messages can vanish with no indication to the user. The client also has no `SIGPIPE` handling: if the server closes the connection, this `write()` raises `SIGPIPE` and kills the client before the `read()` path at line 230 can print "Connection lost."
- **Fix:** Check the return and loop on partial writes, or at minimum use `send(s, ib.buf, ib.len, MSG_NOSIGNAL)` and log short writes. Add `signal(SIGPIPE, SIG_IGN)` in `main()`.

### [LOW] Dead code — `close(s); return 0;` is unreachable
- **Type:** guideline
- **Trigger:** 4.4 — Unnecessary abstraction that doesn't improve readability or safety (dead code adds no value)
- **Location:** smallchat-client.c:259-260
- **Issue:** The `while(1)` loop exits only via `exit(1)` at line 223 (select error) and line 232 (connection lost). Lines 259-260 (`close(s); return 0;`) are never reached. Dead code misleads readers into thinking there is a clean shutdown path. There is not.
- **Fix:** Delete lines 259-260, or make the loop condition explicit (`while (running)`).

### [LOW] `read()` from stdin does not handle `EINTR`
- **Type:** guideline
- **Trigger:** 3.6 — Error handling code that is itself wrong or adds no value
- **Location:** smallchat-client.c:239
- **Issue:** `ssize_t count = read(stdin_fd, buf, sizeof(buf));` — if `read` returns `-1` (`EINTR` from a signal during raw-mode read), the subsequent `for (int j = 0; j < count; j++)` does not execute (`0 < -1` is false), so the keystroke batch is silently dropped. Not dangerous, but the error is not distinguished from a zero-length read. The server-side `read` at line 209 has the same pattern but treats `nread <= 0` as disconnection — acceptable there since a server can't easily distinguish, but the client could.
- **Fix:** `if (count == -1 && errno == EINTR) continue;` before the loop.

---

## chatlib.c

### [MEDIUM] `TCPConnect` leaks `addrinfo` on `EINPROGRESS` return
- **Type:** invariant-false
- **Trigger:** 7.6 — Unbounded resource growth or leaks
- **Location:** chatlib.c:94
- **Issue:**
  ```c
  if (errno == EINPROGRESS && nonblock) return s;
  ```
  This returns the socket `s` immediately without calling `freeaddrinfo(servinfo)` at line 107. The `addrinfo` linked list allocated by `getaddrinfo` at line 75 is leaked. Every non-blocking connect attempt that hits `EINPROGRESS` leaks the full resolved address list. The success path (line 103-104, `retval = s; break;`) and the error path (line 97-98, `close(s); break;`) both reach `freeaddrinfo` at line 107 — only the `EINPROGRESS` early return skips it. No current caller uses `nonblock=1` (the client passes `0`), so this is a latent leak, but it is a real bug in the function's contract.
- **Fix:** Call `freeaddrinfo(servinfo)` before the early return:
  ```c
  if (errno == EINPROGRESS && nonblock) {
      freeaddrinfo(servinfo);
      return s;
  }
  ```

### [LOW] `chatMalloc`/`chatRealloc` abort on OOM — acceptable, but note the tradeoff
- **Type:** guideline
- **Trigger:** 3.1 — Turning a recoverable condition into a fatal error (borderline)
- **Location:** chatlib.c:136-153
- **Issue:** Both allocators call `exit(1)` on `malloc` failure. The comment at lines 132-135 justifies this: "in most programs designed to run for a long time, that are not libraries, trying to recover from out of memory is often futile." This is a defensible design choice for a standalone server — OOM recovery in a simple C program is usually more dangerous than crashing. I am noting it, not rejecting it. The one caveat: `chatRealloc` at line 147 does `ptr = realloc(ptr, size);` — if `realloc` fails, the original `ptr` is *not* freed, but the function exits, so the leak is moot. Fine.
- **Fix:** None required. The design is intentional and documented. If the codebase ever grows, revisit whether OOM should be recoverable for specific allocation sites.

---

## chatlib.h

Clean. Five declarations matching their implementations. No issues on any trigger. The header correctly guards with `#ifndef CHATLIB_H`, declares only what is needed, and exposes no internal helpers. This is what a small header should look like.

---

## Makefile

### [LOW] No `.PHONY` targets — `make clean` breaks if a file named `clean` exists
- **Type:** guideline
- **Trigger:** 10.5 — Magic numbers without explanation (related: build conventions without explicit declaration)
- **Location:** Makefile:1, 10
- **Issue:** `all` and `clean` are not declared `.PHONY`. If a file named `clean` or `all` ever appears in the directory (a build artifact, a downloaded file), `make clean` will report "clean is up to date" and do nothing. Standard make hygiene.
- **Fix:** Add `.PHONY: all clean` after line 1.

### [LOW] `CFLAGS` placed after source files in the link line
- **Type:** guideline
- **Trigger:** 4.6 — Preserving legacy ordering without justification
- **Location:** Makefile:5, 8
- **Issue:** `$(CC) smallchat-server.c chatlib.c -o smallchat-server $(CFLAGS)` — flags come after the sources. Convention is `$(CC) $(CFLAGS) sources -o target $(LDFLAGS) $(LDLIBS)`. With only `-O2 -Wall -W -std=c99` this works, but the moment a library flag (`-l...`) is added to `CFLAGS`, the ordering will break on linkers that require libs after objects. This is preserving an ordering that will bite later.
- **Fix:** `$(CC) $(CFLAGS) smallchat-server.c chatlib.c -o smallchat-server`

---

## Summary

**Verdict: FAIL.**

The code does not pass. Two CRITICAL bugs mean the server dies under completely normal operation — a client disconnecting kills it (SIGPIPE), and an `accept()` failure corrupts memory (unchecked `-1` fd). These are not edge cases. They are the first things that happen when you run a chat server with real clients.

The missing null terminator on the initial nick is a heap over-read that leaks uninitialized memory to other connected clients. The `MAX_CLIENTS` bounds gap is a buffer overflow waiting for a high-fd environment. The `select()` EINTR exit kills the server on any signal. None of these are subtle. They are the predictable consequences of shipping code with no tests.

**Findings by severity:**

| Severity | Count | Findings |
|----------|-------|----------|
| CRITICAL | 2 | SIGPIPE kills server; `acceptClient(-1)` memory corruption |
| HIGH | 3 | Missing null terminator on nick (heap over-read / data leak); no fd bounds check (OOB write); `select()` EINTR → exit |
| MEDIUM | 5 | `assert` for recoverable condition; ignored `socketSetNonBlockNoDelay` return; no test suite; client `write()` return ignored; `TCPConnect` addrinfo leak |
| LOW | 6 | `MAX_CLIENTS` comment contradicts name; dead code in client; stdin `EINTR` not handled; `chatMalloc` OOM abort (acceptable, noted); Makefile `.PHONY`; Makefile flag ordering |

**What is done right:** The data design (flat array indexed by fd) is appropriate and simple. `freeClient`'s maxclient rescan is correct. The select loop structure is clean. `chatlib` is a reasonable separation of networking from logic. `acceptClient` correctly retries on `EINTR`. The code is readable. The problem is not the structure or the style — it is that the code was never run hard enough to find the bugs that live in it.

**The non-negotiable violations:** Correctness (the server crashes and corrupts memory under normal load). The skill's #1 rule — "wrong code that ships is worse than no code" — is violated. Fix the two CRITICAL bugs and the null terminator, add a test that connects and disconnects a client, then resubmit.
