---
title: Review of SmallChat by glm5.2
date: 2026-09-04
model: glm5.2
files_reviewed: 5
findings_count: 8
verdict: needs review
---

## Review Summary

**Model:** glm5.2
**Files reviewed:** 5
**Total findings:** 8
**Findings by severity:** CRITICAL: 2, HIGH: 5, MEDIUM: 0, LOW: 1

## Findings

### smallchat-server.c

### [CRITICAL] Unchecked `acceptClient` return value causes out-of-bounds array write
- **Type:** invariant-false
- **Trigger:** Code provides false or misleading information through any user-visible interface / memory safety — reference to invalid index
- **Location:** smallchat-server.c:~155 (`int fd = acceptClient(Chat->serversock);` followed by `createClient(fd)`)
- **Issue:** `acceptClient` can return -1 on failure (EMFILE, ENFILE, network error). This -1 is passed directly to `createClient`, which executes `Chat->clients[c->fd] = c` — that is `Chat->clients[-1]`, an out-of-bounds write into the `chatState` struct. This corrupts memory before the `clients` array (the `maxclient` field or the struct header). The same -1 fd is also passed to `socketSetNonBlockNoDelay(-1)` and later `write(-1, ...)`. There is zero error checking between accept and use.
- **Fix:** Check the return value of `acceptClient` before calling `createClient`. If it returns -1, log the error and continue the event loop. Do not create a client for an invalid fd.
- **Pass:** 1

### [CRITICAL] No bounds check on file descriptor before indexing `clients[]` array or calling `FD_SET`
- **Type:** invariant-false
- **Trigger:** Memory safety — out-of-bounds access; large stack allocations / buffer overflow
- **Location:** smallchat-server.c:~113 (`Chat->clients[c->fd] = c;`), smallchat-server.c:~170 (`FD_SET(j, &readfds);`)
- **Issue:** `MAX_CLIENTS` is defined as 1000 and the `clients` array has exactly 1000 entries. But nothing enforces that `fd < MAX_CLIENTS`. If the process has high file descriptor numbers (e.g., from `ulimit -n` being raised, or leaked fds from prior operations), `createClient` writes past the end of the `clients` array — heap corruption. Separately, `FD_SET(j, &readfds)` in the main loop writes past the `fd_set` buffer on the stack if `j >= FD_SETSIZE` (typically 1024), causing a stack buffer overflow. The comment on `MAX_CLIENTS` says "This is actually the higher file descriptor" but the value is never used as a gate — it only sizes the array.
- **Fix:** In `createClient`, reject fds >= `MAX_CLIENTS` (and >= `FD_SETSIZE`) with an error. Close the socket and do not insert into the array. The `MAX_CLIENTS` constant must be enforced as a hard limit, not just an array size.
- **Pass:** 1

### [HIGH] `snprintf` return value used as `memcpy` length without truncation check — potential stack buffer over-read
- **Type:** invariant-false
- **Trigger:** Memory safety — out-of-bounds read from stack buffer
- **Location:** smallchat-server.c:~100-104 (`int nicklen = snprintf(nick,sizeof(nick),"user:%d",fd);` ... `memcpy(c->nick,nick,nicklen);`)
- **Issue:** `snprintf` returns the number of characters that *would have been written* if the buffer were unlimited, not the number actually written. If the formatted string exceeds 31 characters, `nicklen` will be >= 32, but only up to 31 bytes were written into the 32-byte `nick` buffer. The subsequent `memcpy(c->nick, nick, nicklen)` then reads `nicklen` bytes from a 32-byte stack buffer — reading past the end of `nick` into unrelated stack memory. While file descriptors are normally small enough that "user:%d" fits, nothing guarantees this, and the bug is real.
- **Fix:** Clamp `nicklen` to `sizeof(nick) - 1` after the `snprintf` call, or check the return value for truncation: `if (nicklen >= (int)sizeof(nick)) nicklen = sizeof(nick) - 1;`
- **Pass:** 1

### [HIGH] `write()` return values unchecked — messages silently truncated or lost
- **Type:** invariant-false
- **Trigger:** Correctness — error handling that masks the underlying bug; unchecked errors
- **Location:** smallchat-server.c:~157 (welcome message), ~213 (error message), ~143 (`sendMsgToAllClientsBut`), ~225 (broadcast message)
- **Issue:** Every `write()` call in the program ignores its return value. On a non-blocking socket (which these are — `socketSetNonBlockNoDelay` is called in `createClient`), `write` can return -1 (EAGAIN/EWOULDBLOCK) or a partial count. The welcome message, error messages, and broadcast messages can all be silently dropped or truncated. The code comments acknowledge this for the broadcast path ("we don't care"), but the welcome message and error message paths have the same problem with no acknowledgment. A client that receives a partial welcome message or no welcome at all will be confused about protocol state.
- **Fix:** At minimum, check `write()` return values for the welcome and error message paths and handle short writes. For the broadcast path, if the "no buffering" design is intentional, at minimum log when write fails so the operator knows messages are being dropped.
- **Pass:** 1

### smallchat-client.c

No findings.

### chatlib.c

### [HIGH] Memory leak in TCPConnect on EINPROGRESS return path
- **Type:** invariant-false
- **Trigger:** Resource leak — function returns without releasing allocated resource
- **Location:** chatlib.c:TCPConnect (the `if (errno == EINPROGRESS && nonblock) return s;` line)
- **Issue:** When `connect()` returns -1 with `errno == EINPROGRESS` and `nonblock` is set, the function executes `return s` immediately without calling `freeaddrinfo(servinfo)`. This is the **normal** code path for every non-blocking connect — `EINPROGRESS` is the expected return, not an edge case. The `servinfo` linked list allocated by `getaddrinfo()` is leaked on every single non-blocking connection attempt. The `freeaddrinfo(servinfo)` call at the end of the function is only reached on the success path and the error-break path, never on the EINPROGRESS path.
- **Fix:** Store the return socket in `retval`, break out of the loop instead of returning directly, so the existing `freeaddrinfo` cleanup runs:
  ```c
  if (errno == EINPROGRESS && nonblock) {
      retval = s;
      break;
  }
  ```
- **Pass:** 1

---

### [HIGH] Fatal exit on out-of-memory in chatMalloc and chatRealloc
- **Type:** invariant-false
- **Trigger:** Fatal abort used for resource exhaustion or allocation failure
- **Location:** chatlib.c:chatMalloc, chatlib.c:chatRealloc
- **Issue:** Both `chatMalloc` and `chatRealloc` call `exit(1)` when `malloc`/`realloc` returns NULL. The comment argues that OOM recovery is "often futile" for long-running programs. But resource exhaustion is a recoverable condition — the caller may be able to free caches, refuse a connection, or degrade gracefully. Aborting removes that option entirely and turns a local allocation failure into a process-wide crash. The principle: a function that allocates memory should return an error indicator on failure, not unilaterally terminate the process. The caller — not the allocator – decides whether the failure is fatal.
- **Fix:** Return `NULL` on allocation failure and let callers handle it. If the application truly wants crash-on-OOM behavior, that policy belongs at the call site, not baked into the allocator wrapper.
- **Pass:** 1

### chatlib.h

### [HIGH] Non-const `addr` parameter permits modification of caller's string data
- **Type:** invariant-false
- **Trigger:** Interface design that makes correct usage difficult and misuse easy
- **Location:** chatlib.h:7
- **Issue:** `TCPConnect(char *addr, int port, int nonblock)` declares `addr` as `char *` instead of `const char *`. A connect function has no legitimate reason to modify the address string. Without `const`, the signature silently permits the implementation to write into the caller's buffer. If a caller passes a string literal — `TCPConnect("127.0.0.1", 8080, 0)` — and the implementation modifies it, the behavior is undefined; on platforms with read-only string literals this is a crash. The interface makes the correct usage pattern (passing a literal) indistinguishable from a dangerous one. Callers cannot know from the signature whether their data is safe.
- **Fix:** Change the declaration to `int TCPConnect(const char *addr, int port, int nonblock)`. If the implementation currently mutates `addr` (e.g., `strtok` or in-place parsing), that is a separate bug — copy to a local buffer instead of modifying caller-owned data.
- **Pass:** 1

---

**Pass 2 findings:** Dropped — file has Pass-1 findings per the two-pass merge rule.

**Summary:** One finding. The non-const `addr` parameter is a correctness contract violation — the signature allows modification of data the caller has no reason to expect will be touched. Fix the `const` qualifier; if the implementation relies on mutability, fix the implementation.

### Makefile

### [LOW] Missing header file prerequisites
- **Type:** guideline
- **Trigger:** (unmatched — build correctness, no direct skill trigger for Makefile dependency tracking)
- **Location:** Makefile:5-6, 8-9
- **Issue:** The `smallchat-server` and `smallchat-client` targets list only `.c` files as prerequisites. If a `chatlib.h` (or any other shared header) exists and is included by these source files, editing the header will not trigger a rebuild. The resulting stale binaries can have inconsistent struct layouts or function signatures across compilation units — a silent source of corruption that is extremely hard to debug.
- **Fix:** Add header prerequisites to each target, e.g. `smallchat-server: smallchat-server.c chatlib.c chatlib.h` and `smallchat-client: smallchat-client.c chatlib.c chatlib.h`. Alternatively, use compiler-generated dependency files (`-MMD -MP`) with `-include` of the `.d` files for a scalable solution.
- **Pass:** 2

---

**Summary:** The Makefile is simple and functional. The one substantive issue is missing header dependencies, which can cause stale builds. Everything else (`.PHONY` declarations, `CFLAGS` assignment style, `rm` command structure) falls under build trivia and is not worth blocking on.
