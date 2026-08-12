---
title: "Code Review: antirez/smallchat"
reviewer: "Linus Torvalds reviewer skill (GLM5.2 soul)"
date: 2026-08-12
codebase: "/tmp/smallchat"
files_reviewed: ["smallchat-server.c", "smallchat-client.c", "chatlib.c", "chatlib.h", "Makefile"]
loc: 706
skill: "linus-torvalds-skill/SKILL-GLM.md v1.0.0"
soul: "soul/soul-glm.md v2.0"
verdict: "FAIL"
---

# Review: antirez/smallchat

A minimal TCP chat server. ~700 lines of C. The kind of program that should be
simple enough to get right. It doesn't. There are two memory-corruption bugs in
the server's hot path, a signal will kill the whole server dead, and the client
dies from SIGPIPE on a normal disconnect. The data structure design is fine —
indexing clients by fd is the right call — but the code around it has holes you
could drive a truck through.

Let's go file by file.

---

## smallchat-server.c

### [CRITICAL] Unchecked `acceptClient` return feeds -1 into `createClient`, corrupting memory

- **Type:** invariant-false
- **Trigger:** 6.2 — Missing cleanup on error paths (error return not checked; the error path does not exist)
- **Location:** smallchat-server.c:188-189
- **Issue:** `acceptClient()` can return -1 on any non-EINTR accept failure (EMFILE, ENFILE, ECONNABORTED,ENOMEM — all routine under load). The return value is never checked:

  ```c
  int fd = acceptClient(Chat->serversock);
  struct client *c = createClient(fd);
  ```

  `createClient(-1)` runs to completion. `socketSetNonBlockNoDelay(-1)` fails
  harmlessly, but then `c->fd = -1` and the code executes:

  ```c
  assert(Chat->clients[c->fd] == NULL);   // reads Chat->clients[-1] — OOB read
  Chat->clients[c->fd] = c;               // writes Chat->clients[-1] — OOB write
  ```

  `Chat->clients` is an array of 1000 pointers. Index -1 writes one pointer's
  width before the array — into `numclients` or `maxclient` or whatever the
  compiler laid down before it. That is heap corruption. With `-DNDEBUG` the
  assert vanishes and the OOB write is unconditional. Without it, the assert
  reads OOB before crashing.

  This fires under perfectly normal conditions: hit the fd limit, get a
  transient ECONNABORTED, run out of memory. The server then corrupts its own
  state and limps on or dies.

- **Fix:** Check the return before calling `createClient`:

  ```c
  int fd = acceptClient(Chat->serversock);
  if (fd == -1) continue;   /* or log and continue */
  struct client *c = createClient(fd);
  ```

  One line. This is complete and utter shit. You do not feed an error sentinel
  into an array index. Ever.

### [HIGH] `createClient` does not null-terminate `c->nick` — reads uninitialized heap memory

- **Type:** invariant-false
- **Trigger:** 8.5 — Exposing stale or freed data to external callers (uninitialized heap bytes are displayed to all connected clients)
- **Location:** smallchat-server.c:83-84
- **Issue:** `snprintf` returns the string length without the null terminator. The code allocates `nicklen+1` bytes but copies only `nicklen`:

  ```c
  int nicklen = snprintf(nick,sizeof(nick),"user:%d",fd);
  ...
  c->nick = chatMalloc(nicklen+1);
  memcpy(c->nick,nick,nicklen);      // no null terminator written
  ```

  `chatMalloc` calls `malloc`, not `calloc` — the +1 byte is uninitialized heap
  garbage. `c->nick` is then used as a C string in two places:

  - Line 215: `printf("Disconnected client fd=%d, nick=%s\n", j, Chat->clients[j]->nick);`
  - Line 256: `snprintf(msg, sizeof(msg), "%s> %s", c->nick, readbuf);`

  Both read past the intended nick into whatever the allocator left there. The
  second one broadcasts that garbage to every connected client. That is an
  information leak — you are showing users bytes from freed or uninitialized heap.

  The `/nick` command path four lines down gets this right:

  ```c
  memcpy(c->nick,arg,nicklen+1);    // includes the null — correct
  ```

  So the code knows the correct pattern. It just doesn't use it in `createClient`.

- **Fix:** Copy `nicklen+1` to include the null terminator, matching the `/nick` path:

  ```c
  memcpy(c->nick,nick,nicklen+1);
  ```

### [HIGH] `select()` EINTR treated as fatal — any signal kills the server

- **Type:** invariant-false
- **Trigger:** 2.2 — Turning a recoverable condition into a hard error
- **Location:** smallchat-server.c:180-182
- **Issue:** `select` returns -1 on EINTR (interrupted by a signal). This is
  perfectly recoverable — you retry the loop. Instead:

  ```c
  retval = select(maxfd+1, &readfds, NULL, NULL, &tv);
  if (retval == -1) {
      perror("select() error");
      exit(1);
  }
  ```

  Any signal — SIGCHLD, SIGHUP, someone resizing the terminal — kills the chat
  server dead. Every user disconnected. For a long-running server this is not a
  question of "if" but "when."

- **Fix:** Handle EINTR and continue; only exit on real errors:

  ```c
  retval = select(maxfd+1, &readfds, NULL, NULL, &tv);
  if (retval == -1) {
      if (errno == EINTR) continue;
      perror("select() error");
      exit(1);
  }
  ```

### [MEDIUM] `read()` EINTR/EAGAIN disconnects the client

- **Type:** invariant-false
- **Trigger:** 2.2 — Turning a recoverable condition into a hard error
- **Location:** smallchat-server.c:209-216
- **Issue:** Sockets are set non-blocking (line 81). `read` on a non-blocking
  socket can return -1 with EAGAIN, and any `read` can return -1 with EINTR.
  Both are recoverable. The code treats all `nread <= 0` as disconnection:

  ```c
  int nread = read(j,readbuf,sizeof(readbuf)-1);
  if (nread <= 0) {
      ...
      freeClient(Chat->clients[j]);
  }
  ```

  A signal arriving between `select` and `read` kicks the client off. EAGAIN
  under transient kernel pressure kicks the client off. The user did nothing
  wrong and gets disconnected.

- **Fix:** Distinguish recoverable errors from real disconnection:

  ```c
  if (nread == -1 && (errno == EINTR || errno == EAGAIN || errno == EWOULDBLOCK))
      continue;
  if (nread <= 0) {
      freeClient(Chat->clients[j]);
      continue;
  }
  ```

### [MEDIUM] `MAX_CLIENTS` used as both array size and max fd — OOB access when fd >= 1000

- **Type:** invariant-false
- **Trigger:** 8.4 — Freeing an object while live references exist (out-of-bounds access corrupts adjacent state; the array boundary is not enforced)
- **Location:** smallchat-server.c:45, 62, 86, 98, 166
- **Issue:** The comment on line 45 says `MAX_CLIENTS 1000` is "actually the
  higher file descriptor," but it is used as the array size:

  ```c
  #define MAX_CLIENTS 1000 // This is actually the higher file descriptor.
  ...
  struct client *clients[MAX_CLIENTS];   // 1000 slots: indices 0..999
  ```

  File descriptors are process-global, not per-connection. The server socket
  (fd 3), stdin/stdout/stderr (fds 0-2), and every accepted client consume fds.
  After ~997 connections, the next `accept` returns fd >= 1000. Then:

  ```c
  Chat->clients[c->fd] = c;   // fd=1000 → clients[1000] → OOB write
  ```

  This is heap corruption, same class as the `acceptClient` bug. The comment
  admits the confusion but the code doesn't enforce anything.

- **Fix:** Either reject fds >= MAX_CLIENTS in `createClient`, or use a
  dynamically-sized structure. For a teaching example, the simplest fix:

  ```c
  if (fd >= MAX_CLIENTS) {
      close(fd);
      return NULL;
  }
  ```

  And check `createClient`'s return for NULL in `main`.

### [LOW] `assert` used for a runtime condition — crashes the server, vanishes under -DNDEBUG

- **Type:** invariant-false
- **Trigger:** 2.1 — Fatal assertion used for a recoverable error
- **Location:** smallchat-server.c:85
- **Issue:** `assert(Chat->clients[c->fd] == NULL)` crashes the server if the
  slot is occupied. A fd collision (shouldn't happen normally, but the whole
  point of defensive checks is the unexpected) kills every connected user.
  Under `-DNDEBUG` the check vanishes entirely and the overwrite silently leaks
  the old client. `assert` is for invariant violations in debug builds, not for
  runtime error handling in a server.

- **Fix:** Replace with a real check that handles the condition:

  ```c
  if (Chat->clients[c->fd] != NULL) freeClient(Chat->clients[c->fd]);
  Chat->clients[c->fd] = c;
  ```

### [LOW] `write()` return values ignored — messages silently dropped

- **Type:** guideline
- **Trigger:** 6.5 — Unnecessary error handling that adds no value (inverse: missing handling where it matters)
- **Location:** smallchat-server.c:143, 194, 248
- **Issue:** Every `write` to a client socket ignores the return value. Partial
  writes silently truncate messages. The comment at line 140 acknowledges this
  ("If the content does not fit, we don't care"), and for a teaching example
  that is a defensible choice. But it means messages vanish with no signal to
  the sender or receiver. In production this would be a correctness bug; here it
  is a documented limitation.

- **Fix:** None required for a teaching example. For anything real: buffer
  pending writes per-client and retry on the next `select` iteration.

---

## smallchat-client.c

### [MEDIUM] No SIGPIPE handling — client dies when writing to a closed socket

- **Type:** invariant-false
- **Trigger:** 2.2 — Turning a recoverable condition into a hard error
- **Location:** smallchat-client.c:214-256 (main loop, no `signal(SIGPIPE, ...)` anywhere)
- **Issue:** When the server closes the connection, the client's next `write(s,
  ib.buf, ib.len)` (line 248) raises SIGPIPE. The default action is to
  terminate the process. The client has a `read` path that detects disconnect
  (line 230), but there is a race: the user types a line, the client writes to
  the socket, the server already closed — SIGPIPE kills the client before it
  ever reads the close. The user sees "Connection lost" sometimes; other times
  the client just vanishes with no message.

  This is a one-line fix that is missing entirely.

- **Fix:** Ignore SIGPIPE at startup:

  ```c
  signal(SIGPIPE, SIG_IGN);
  ```

  Or use `send(s, buf, len, MSG_NOSIGNAL)` instead of `write`. The `signal`
  approach is simpler and matches the program's style.

### [LOW] `read()` return value not checked for -1 on stdin path

- **Type:** guideline
- **Trigger:** 6.5 — Unnecessary error handling that adds no value (inverse: missing check)
- **Location:** smallchat-client.c:239
- **Issue:** `ssize_t count = read(stdin_fd,buf,sizeof(buf));` — if `read`
  returns -1 (EINTR), `count` is -1. The loop `for (int j = 0; j < count; j++)`
  does not execute (0 < -1 is false), so no crash, but the error is silently
  swallowed. On a signal during stdin read, the keystroke is lost with no
  indication.

- **Fix:** Check for -1 and continue:

  ```c
  if (count == -1) {
      if (errno == EINTR) continue;
      perror("read");
      exit(1);
  }
  ```

---

## chatlib.c

### [MEDIUM] `TCPConnect` leaks `servinfo` on EINPROGRESS return path

- **Type:** invariant-true
- **Trigger:** 6.2 — Missing cleanup on error paths (resource leak on early return)
- **Location:** chatlib.c:94
- **Issue:** On the non-blocking connect path, EINPROGRESS is a valid
  in-progress connection. The function returns the socket `s` — but skips
  `freeaddrinfo(servinfo)`:

  ```c
  if (errno == EINPROGRESS && nonblock) return s;   // servinfo leaked
  ```

  Every non-blocking connect attempt leaks the `addrinfo` linked list. This is
  a real leak, not theoretical — `getaddrinfo` allocates on the heap.

- **Fix:** Free before returning:

  ```c
  if (errno == EINPROGRESS && nonblock) {
      freeaddrinfo(servinfo);
      return s;
  }
  ```

### [LOW] `chatMalloc`/`chatRealloc` call `exit(1)` on OOM

- **Type:** guideline
- **Trigger:** 2.3 — Fail-fast mechanisms in production code paths
- **Location:** chatlib.c:136-153
- **Issue:** Exiting on OOM is a documented design choice ("trying to recover
  from out of memory is often futile"). The comment argues the case and for a
  700-line teaching program this is a reasonable simplification. For anything
  production-grade, OOM on a per-allocation basis is recoverable — refuse the
  new connection, log, keep serving existing clients. But the code is honest
  about the tradeoff, and the soul says: if the code is honest about its
  limitations, that counts for something.

- **Fix:** None required for a teaching example. For production: return NULL
  and let callers handle it.

---

## chatlib.h

Clean. Declares the public API: `createTCPServer`, `socketSetNonBlockNoDelay`,
`acceptClient`, `TCPConnect`, `chatMalloc`, `chatRealloc`. No issues.

One observation: `chatRealloc` is declared and defined but never called by
either the server or the client. It is dead surface in the library. Not a bug —
it is a library function that exists for completeness. If this were a kernel
API, I would say "new interface without real-world users" (Trigger 10.5). For
a teaching library, it is fine.

---

## Makefile

### [LOW] No header dependency tracking — stale builds after editing `chatlib.h`

- **Type:** guideline
- **Trigger:** 10.1 — Non-bisectable change (stale binaries make bisects unreliable)
- **Location:** Makefile:4-8
- **Issue:** The rules depend on `.c` files but not on `chatlib.h`:

  ```makefile
  smallchat-server: smallchat-server.c chatlib.c
  	$(CC) smallchat-server.c chatlib.c -o smallchat-server $(CFLAGS)
  ```

  Edit `chatlib.h` (change a signature, add a parameter) and run `make` — it
  says "up to date." You get a stale binary that doesn't reflect the header
  change. This causes confusing build failures and unreliable bisects.

- **Fix:** Add header dependencies, or use a compiler-generated dependency file:

  ```makefile
  smallchat-server: smallchat-server.c chatlib.c chatlib.h
  smallchat-client: smallchat-client.c chatlib.c chatlib.h
  ```

  Or for automatic dependency tracking:

  ```makefile
  CFLAGS=-O2 -Wall -W -std=c99 -MMD -MP
  -include *.d
  ```

### [LOW] `clean` is not declared `.PHONY`

- **Type:** guideline
- **Trigger:** 12.2 — Cosmetic (no functional benefit, but correct Makefile hygiene)
- **Location:** Makefile:10
- **Issue:** If a file named `clean` ever exists in the directory, `make clean`
  will refuse to run. Standard hygiene: declare phony targets.

- **Fix:** Add `.PHONY: clean` before the target.

---

## Summary

**Verdict: FAIL.**

The code does not pass. Two memory-corruption bugs in the server's connection
path make it unsafe under normal operating conditions. The `acceptClient`
unchecked return is the worst — feeding -1 into an array index is the kind of
mistake that should not survive a first read. The missing null terminator on
`c->nick` broadcasts uninitialized heap bytes to every connected client. A
single signal kills the server. The client dies from SIGPIPE on a normal
disconnect.

The good: the data structure design is right. Indexing clients by fd is the
correct approach — "bad programmers worry about the code, good programmers
worry about data structures and their relationships," and the data structure
here is sound. `acceptClient` handles EINTR correctly. `createTCPServer` cleans
up on error. The code is honest in its comments about what it does and does
not handle. For a teaching example, the simplicity is appropriate. But simple
is not an excuse for memory corruption.

### Findings by severity

| Severity | Count | Findings |
|----------|-------|----------|
| CRITICAL | 1 | Unchecked `acceptClient` return → OOB write |
| HIGH | 2 | Missing null terminator on `c->nick`; `select` EINTR kills server |
| MEDIUM | 4 | `read` EINTR disconnects client; `MAX_CLIENTS` OOB; SIGPIPE kills client; `TCPConnect` leaks `servinfo` |
| LOW | 5 | `assert` for runtime condition; `write` returns ignored; stdin `read` unchecked; OOM `exit`; Makefile header deps / `.PHONY` |

**Total: 12 findings. 3 are memory-safety bugs. The code does not pass.**

The fixes are small — most are one to three lines. The `acceptClient` check is
one line. The null terminator is one byte. The EINTR retry is one `continue`.
The SIGPIPE ignore is one `signal` call. None of this requires redesign. The
data structures are right; the error handling around them is not.
