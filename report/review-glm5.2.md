---
title: "Torvalds-Method Review: antirez/smallchat"
reviewer: "torvalds-skill (GLM5.2 soul + skill-glm.md)"
date: "2026-08-19"
codebase: "/tmp/smallchat (~706 LOC)"
skill: "linus-torvalds-skill/skill-glm.md"
soul: "soul/soul-glm.md"
verdict: "FAIL — must not ship"
files_reviewed: 5
findings:
  critical: 2
  high: 3
  medium: 3
  low: 3
---

# Review: antirez/smallchat

So let me get this straight. A chat server whose entire job is to accept connections and relay messages, and it doesn't check the return value of `accept()`, doesn't bounds-check the file descriptor before using it as an array index, and crashes on an assert for a condition it could handle by returning an error. This is ~700 lines of C and it still manages to have memory corruption on the happy path. No. Just no.

The data model — clients indexed by fd in a fixed array — is fine for a teaching example. The problem is that the code around it doesn't defend the model's invariants. An array indexed by fd only works if you check that fd is in bounds. You don't. That's not a style issue. That's a correctness bug that corrupts memory.

Below, file by file.

---

## smallchat-server.c

### [CRITICAL] accept() return value not checked before use as array index
- **Type:** invariant-false
- **Trigger:** Code that corrupts existing state / Fatal assertion or crash for a recoverable condition
- **Location:** smallchat-server.c:188-189
- **Issue:** `acceptClient()` can return -1 on failure. The return value is passed directly to `createClient(fd)` with zero validation. Inside `createClient`, `fd` becomes the index into `Chat->clients[MAX_CLIENTS]`. When `fd` is -1, `Chat->clients[-1]` is an out-of-bounds read (the assert at line 85) followed by an out-of-bounds write (line 86). That is memory corruption on a failed accept, which is a routine, recoverable condition. You don't crash a server because accept() failed. You log it and you move on.
- **Fix:** Check the return value of `acceptClient()` before calling `createClient()`. If it returns -1, log the error and continue the event loop. Do not pass -1 to any function that uses it as an array index. Ever.

```c
int fd = acceptClient(Chat->serversock);
if (fd == -1) {
    perror("accept() error");
    continue;
}
struct client *c = createClient(fd);
```

### [CRITICAL] No bounds check on fd before array indexing
- **Type:** invariant-false
- **Trigger:** Code that corrupts existing state
- **Location:** smallchat-server.c:85-86, 88
- **Issue:** `createClient()` uses `c->fd` as an index into `Chat->clients[MAX_CLIENTS]` (1000 entries) without checking `c->fd < MAX_CLIENTS`. If a client's fd is >= 1000 — which is entirely possible if the process has inherited file descriptors or has many open connections — `Chat->clients[c->fd]` is an out-of-bounds access. The assert at line 85 reads garbage, and the assignment at line 86 writes a pointer past the end of the array. This is a buffer overflow. The `MAX_CLIENTS` constant doesn't enforce anything; it's just an array size. There is no guard.
- **Fix:** In `createClient()`, check `fd >= 0 && fd < MAX_CLIENTS` before any array access. If out of range, close the socket and return NULL. The caller must handle NULL.

```c
struct client *createClient(int fd) {
    if (fd < 0 || fd >= MAX_CLIENTS) {
        close(fd);
        return NULL;
    }
    /* ... rest of function ... */
}
```

### [HIGH] Fatal assert for a recoverable condition
- **Type:** invariant-false
- **Trigger:** Fatal assertion or crash for a recoverable condition
- **Location:** smallchat-server.c:85
- **Issue:** `assert(Chat->clients[c->fd] == NULL)` crashes the server if the slot is already occupied. A slot collision is a recoverable condition — the server could log it, close the new connection, and continue. Instead, it aborts. And in a release build (NDEBUG defined), the assert is compiled out entirely, so the code silently overwrites the existing client pointer, leaking the old client and creating a dangling pointer. So in debug it crashes, in release it corrupts. Both outcomes are wrong. There is *no* excuse for killing the server for something like this.
- **Fix:** Replace the assert with a runtime check that returns an error or closes the new connection. The caller handles the failure.

```c
if (Chat->clients[c->fd] != NULL) {
    /* Slot collision — shouldn't happen, but handle it. */
    fprintf(stderr, "fd %d already has a client\n", fd);
    close(fd);
    free(c->nick);
    free(c);
    return NULL;
}
```

### [HIGH] Non-blocking socket read treated as disconnect on EAGAIN/EINTR
- **Type:** invariant-false
- **Trigger:** Recoverable condition turned into a fatal error
- **Location:** smallchat-server.c:209-216
- **Issue:** Client sockets are set non-blocking in `createClient()` (line 81: `socketSetNonBlockNoDelay(fd)`). In the main loop, `read()` returning `<= 0` is treated as "client disconnected." But `read()` on a non-blocking socket can return -1 with `errno == EAGAIN` (no data available yet) or `errno == EINTR` (interrupted by a signal). Both are recoverable — the client is still connected. The code disconnects a healthy client on a signal-interrupted read. The socket is non-blocking, so EAGAIN is a real possibility after select reports readability in edge cases (urgent data, partial reads). Treating it as a disconnect is wrong.
- **Fix:** Check `errno` when `read()` returns -1. Retry on EINTR, continue on EAGAIN, disconnect only on EOF (0) or a real error.

```c
int nread = read(j, readbuf, sizeof(readbuf)-1);
if (nread == 0) {
    /* Client disconnected. */
    freeClient(Chat->clients[j]);
} else if (nread == -1) {
    if (errno == EINTR || errno == EAGAIN) continue; /* Not a disconnect. */
    /* Real error — disconnect. */
    freeClient(Chat->clients[j]);
} else {
    /* Process data. */
}
```

### [HIGH] write() return values silently ignored — messages dropped
- **Type:** invariant-false
- **Trigger:** Success return value used to indicate failure
- **Location:** smallchat-server.c:143, 194, 248
- **Issue:** Every `write()` call in the server ignores the return value. `sendMsgToAllClientsBut()` (line 143) calls `write()` and discards the result. If the write is partial (kernel buffer full), the message is silently truncated. If the write fails entirely (EPIPE, ECONNRESET), the message is silently dropped and the dead client is not cleaned up until the next `read()` returns 0. The comment at lines 140-142 says "If the content does not fit, we don't care." For a chat server whose entire purpose is to relay messages, silently dropping them is a functional defect, not a design choice. The welcome message (line 194) and error message (line 248) have the same problem.
- **Fix:** For a teaching example, at minimum check for -1 and mark the client for disconnection on EPIPE/ECONNRESET. For partial writes, either buffer (which the comment says it avoids) or accept the loss but log it. Do not silently swallow write failures on a server whose job is writing.

### [MEDIUM] MAX_CLIENTS name contradicts its actual meaning
- **Type:** invariant-false
- **Trigger:** Comment that contradicts the code
- **Location:** smallchat-server.c:45
- **Issue:** `#define MAX_CLIENTS 1000` with the comment `// This is actually the higher file descriptor.` The name says "maximum number of clients." The comment says "actually the highest file descriptor." The code uses it as the array size for `clients[]`, indexed by fd. These are three different things. A reader seeing `MAX_CLIENTS` assumes it limits the client count, not the fd range. This is exactly the kind of misleading name that leads to the bounds-check bug above — nobody thinks to check `fd < MAX_CLIENTS` because the name implies a count, not a bound.
- **Fix:** Rename to `MAX_FD` or `CLIENT_SLOTS` to match what it actually is — the array size and maximum fd index.

### [LOW] /nick command accepts unbounded nick length
- **Type:** guideline
- **Trigger:** Configuration value that can cause stack overflow or resource exhaustion
- **Location:** smallchat-server.c:240-244
- **Issue:** The `/nick` command copies the argument with no length limit: `int nicklen = strlen(arg); c->nick = chatMalloc(nicklen+1);`. A client can set a nick of arbitrary length, causing an unbounded allocation. The nick is then used in `snprintf(msg, sizeof(msg), "%s> %s", c->nick, readbuf)` where `msg` is 256 bytes — a long nick truncates the actual message content to nothing. No crash, but the server is trivially DOSable by setting a 1MB nick.
- **Fix:** Cap nick length at a reasonable value (e.g., 32 bytes, matching the initial nick buffer) and reject longer nicks.

### [LOW] select() has no FD_SETSIZE guard
- **Type:** guideline
- **Trigger:** Configuration value that can cause stack overflow or resource exhaustion
- **Location:** smallchat-server.c:166, 179
- **Issue:** `FD_SET(j, &readfds)` where `j` can be up to `maxclient` (up to 999). `FD_SETSIZE` is typically 1024 on Linux, so 999 < 1024 is safe today. But there is no check that `j < FD_SETSIZE` before the `FD_SET` call. If the process ever gets an fd >= 1024 (inherited descriptors, high ulimit), `FD_SET` writes past the `readfds` stack buffer. The code relies on an implicit assumption that `MAX_CLIENTS < FD_SETSIZE`, which is true by accident, not by design.
- **Fix:** Add a compile-time or runtime check: `_Static_assert(MAX_CLIENTS <= FD_SETSIZE, ...)` or check `fd < FD_SETSIZE` before `FD_SET`.

---

## smallchat-client.c

### [HIGH] Client exits on signal-interrupted read from server
- **Type:** invariant-false
- **Trigger:** Recoverable condition turned into a fatal error
- **Location:** smallchat-client.c:229-233
- **Issue:** `read(s, buf, sizeof(buf))` returns -1 on EINTR (signal interrupted the read). The code treats `count <= 0` as "Connection lost" and exits. EINTR does not mean the connection is lost — it means a signal arrived during the read. The client should retry, not exit. This is the same class of bug as the server's read handling. A single signal during a read kills the client session.
- **Fix:** Check `errno` on read failure. Retry on EINTR, continue on EAGAIN (if non-blocking), exit only on EOF or a real connection error.

```c
ssize_t count = read(s, buf, sizeof(buf));
if (count == 0) {
    printf("Connection lost\n");
    exit(1);
} else if (count == -1) {
    if (errno == EINTR) continue;
    perror("read");
    exit(1);
}
```

### [MEDIUM] stdin read error silently swallowed
- **Type:** guideline
- **Trigger:** Error path that does not clean up resources
- **Location:** smallchat-client.c:239-254
- **Issue:** `read(stdin_fd, buf, sizeof(buf))` can return -1 on EINTR. The code does `for (int j = 0; j < count; j++)` — since `count` is -1 (signed ssize_t) and `j` is int, `0 < -1` is false, so the loop body is skipped. The error is silently swallowed. The keystroke is lost. This is "safe by accident" — it doesn't crash, but it doesn't handle the error either. It just drops input on the floor.
- **Fix:** Check for -1 and `continue` on EINTR. Don't rely on signed comparison to skip the loop body.

### [LOW] Port argument parsed with atoi, no validation
- **Type:** guideline
- **Trigger:** Interface with surprising or non-intuitive semantics
- **Location:** smallchat-client.c:195
- **Issue:** `TCPConnect(argv[1], atoi(argv[2]), 0)` — `atoi("abc")` returns 0, `atoi("99999")` returns 99999 (out of port range), `atoi("-1")` returns -1. No validation. The user gets a silent connection failure or an attempt to connect to port 0. `strtol` with range checking would catch these.
- **Fix:** Use `strtol` with validation, or at minimum check the port is in range 1-65535.

### [LOW] inputBufferHide takes unused parameter
- **Type:** guideline
- **Trigger:** Unnecessary parameter or code path that serves only one rare case
- **Location:** smallchat-client.c:167-171
- **Issue:** `inputBufferHide(struct InputBuffer *ib)` takes `ib` but doesn't use it — the first line is `(void)ib;`. The comment says "Not used var, but is conceptually part of the API." If it's not used, it's not part of the API. It's a dead parameter that every caller has to pass for no reason. This is the kind of "conceptually part of the API" thinking that leads to interfaces nobody can use correctly.
- **Fix:** Remove the parameter, or make `inputBufferHide` actually use it (e.g., to clear the buffer's display state).

---

## chatlib.c

### [HIGH] Memory leak on EINPROGRESS path in TCPConnect
- **Type:** invariant-false
- **Trigger:** Error path that does not clean up resources
- **Location:** chatlib.c:94
- **Issue:** When `connect()` returns -1 with `errno == EINPROGRESS` and `nonblock` is set, the function returns `s` immediately — without calling `freeaddrinfo(servinfo)`. The `servinfo` linked list allocated by `getaddrinfo()` at line 75 is leaked. Every non-blocking connect attempt that returns EINPROGRESS leaks a `struct addrinfo` chain. This is a resource leak on a code path that is explicitly designed to be taken (non-blocking connect is the whole point of the `nonblock` parameter).
- **Fix:** Call `freeaddrinfo(servinfo)` before returning `s` on the EINPROGRESS path.

```c
if (errno == EINPROGRESS && nonblock) {
    freeaddrinfo(servinfo);
    return s;
}
```

### [MEDIUM] chatMalloc/chatRealloc exit the process on OOM
- **Type:** invariant-false
- **Trigger:** Recoverable condition turned into a fatal error
- **Location:** chatlib.c:136-153
- **Issue:** Both allocators call `exit(1)` on `malloc` failure. The comment at lines 132-135 argues this is a deliberate design choice: "trying to recover from out of memory is often futile." For a teaching example, fine. For a server that is supposed to run for a long time, this is wrong. A single failed allocation for a new client's nick takes down every connected client. OOM is recoverable — close the new connection, log the error, keep serving existing clients. The comment is an excuse, not a justification. "Anybody who makes a hard error out of something that is recoverable is a total moron."
- **Fix:** Return NULL on failure. Callers check the return value and handle it. For the server, a failed allocation for a new client means closing that connection, not killing the process.

### [MEDIUM] chatRealloc exported but never called
- **Type:** guideline
- **Trigger:** Public interface exported but unused
- **Location:** chatlib.c:146-153, chatlib.h:12
- **Issue:** `chatRealloc()` is defined in chatlib.c and declared in chatlib.h, but has zero callers in the entire codebase. It's a public export that nobody uses. Every public symbol is a maintenance burden. Unused exports should be removed or kept private until needed.
- **Fix:** Remove `chatRealloc` from both chatlib.c and chatlib.h. Add it back when something actually calls it.

### [LOW] acceptClient loops indefinitely on EINTR storm
- **Type:** guideline
- **Trigger:** Blocking synchronization in a performance-critical path
- **Location:** chatlib.c:117-128
- **Issue:** The `while(1)` loop in `acceptClient()` retries on EINTR with no limit. If signals arrive in a tight loop (signal storm), this function never returns. In practice, this is unlikely for a simple chat server, but the pattern is fragile — a `while(1)` with only `continue` on EINTR and no iteration limit is a potential livelock.
- **Fix:** Either accept the livelock risk for a teaching example (and document it), or add a retry limit. For production code, a bounded retry or returning -1 with EINTR to the caller is safer.

---

## chatlib.h

### [LOW] Header does not guard against FD_SETSIZE mismatch
- **Type:** guideline
- **Trigger:** Interface with surprising or non-intuitive semantics
- **Location:** chatlib.h:1-14
- **Issue:** The header declares networking functions but doesn't document the implicit contract that `MAX_CLIENTS <= FD_SETSIZE` must hold in the server. The server's `select()` usage depends on this invariant, but it's not enforced or documented anywhere. A user who changes `MAX_CLIENTS` to 2000 gets silent stack corruption with no compile-time error.
- **Fix:** Add a `_Static_assert` in the server, or document the constraint in the header. This is a guideline, not a crash today — but it's a trap for the next person who edits the constant.

---

## Makefile

### [LOW] CFLAGS defined after targets, no .PHONY
- **Type:** guideline
- **Trigger:** Stale comment that no longer reflects current behavior
- **Location:** Makefile:1-2, 10
- **Issue:** `CFLAGS` is defined after the `all` target. This works in Make (variables are expanded at use time), but it's unconventional and confusing — a reader scanning the top of the file doesn't see the build flags. `all` and `clean` are not declared `.PHONY`, so if someone creates a file named `all` or `clean` in the directory, `make all` stops working. The `-W` flag is the old form of `-Wextra` and is less readable.
- **Fix:** Move `CFLAGS` above the `all` target. Add `.PHONY: all clean`. Use `-Wextra` instead of `-W`.

```makefile
CFLAGS = -O2 -Wall -Wextra -std=c99
.PHONY: all clean

all: smallchat-server smallchat-client
```

---

## Summary

**Verdict: FAIL — must not ship.**

The code has two CRITICAL memory-safety bugs on the connection-accept path. `acceptClient()` returning -1 is passed to `createClient()` which uses it as an array index, causing out-of-bounds access at `Chat->clients[-1]`. Separately, no bounds check on `fd` before indexing into `Chat->clients[MAX_CLIENTS]` means any fd >= 1000 corrupts memory. Both are on the happy path — they fire on routine accept failure and high-fd connections, not on exotic edge cases.

The assert at line 85 is the kind of thing I have no patience for. It crashes the server in debug and silently corrupts in release. There is *no* excuse for killing the server for a condition that can be handled by closing the connection and logging an error.

The non-blocking socket + `read() <= 0` disconnect pattern is a real bug, not a style issue. EINTR and EAGAIN are not disconnects. Treating them as such drops healthy clients.

The `TCPConnect` memory leak on EINPROGRESS is a straightforward resource leak on a code path that is explicitly designed to be taken.

### Findings by severity

| Severity | Count | Files |
|----------|-------|-------|
| CRITICAL | 2 | smallchat-server.c (accept unchecked, no fd bounds check) |
| HIGH | 3 | smallchat-server.c (assert crash, read-as-disconnect, write ignored), smallchat-client.c (read-as-disconnect) |
| MEDIUM | 3 | smallchat-server.c (MAX_CLIENTS naming), chatlib.c (exit on OOM, chatRealloc unused) |
| LOW | 3 | smallchat-server.c (/nick unbounded, no FD_SETSIZE guard), smallchat-client.c (atoi, stdin swallow, unused param), chatlib.c (acceptClient livelock), chatlib.h (no FD_SETSIZE doc), Makefile (hygiene) |

### What's clean

- **Data model.** Array indexed by fd is simple and appropriate for a teaching example. The problem is the code around it, not the model.
- **createTCPServer.** Proper error handling, SO_REUSEADDR, reasonable backlog (511). No complaints.
- **TCPConnect iteration.** Iterating `getaddrinfo` results and trying each is correct. (The leak is the bug, not the iteration.)
- **No concurrency bugs.** Single-threaded, no locks, no races. Not applicable.
- **No API stability issues.** No public API changes. Not applicable.
- **No bisectability issues.** Not a patch series. Not applicable.

### Does the code pass?

No. Two CRITICAL memory-safety bugs on the accept path mean this code corrupts memory under routine conditions (accept failure, high fd). The server crashes on an assert for a recoverable condition. Non-blocking sockets are mishandled. The code does not pass review.

Fix the two CRITICAL findings first. Then the HIGHs. Then we can talk about the rest.
