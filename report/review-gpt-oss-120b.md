---
title: Review of SmallChat by gpt-oss-120b
date: 2026-11-05
model: gpt-oss-120b
files_reviewed: 5
findings_count: 12
verdict: needs review
input_hash: 6760a917b6658c457c0cecd30d02616d08d0bf8feedf01d1f04ef188cc9284aa
---

## Review Summary

**Model:** gpt-oss-120b
**Files reviewed:** 5
**Total findings:** 12
**Findings by severity:** CRITICAL: 6, HIGH: 4, MEDIUM: 1, LOW: 1

## Findings

### smallchat-server.c

### CRITICAL Out-of-bounds read when generating initial nickname
- **Type:** invariant-false
- **Trigger:** (unmatched)
- **Location:** smallchat-server.c:79
- **Issue:** `snprintf` writes up to 31 characters into `nick[32]`. If the file descriptor number is large, `nicklen` will be greater than 31. The code then copies `nicklen+1` bytes from `nick` into the allocated nickname buffer, which reads past the end of `nick`. This is an out‑of‑bounds read that can corrupt memory or crash the program.
- **Fix:** Limit the length used for the nickname, e.g. `int nicklen = snprintf(nick, sizeof(nick), "user:%d", fd); if (nicklen >= sizeof(nick)) nicklen = sizeof(nick)-1;` and then copy only `nicklen+1` bytes. Alternatively, allocate the nickname buffer based on the actual length returned by `snprintf` and copy only that many bytes.
- **Pass:** 1

### CRITICAL Out-of-bounds write when storing client in array
- **Type:** invariant-false
- **Trigger:** (unmatched)
- **Location:** smallchat-server.c:85
- **Issue:** The client array `Chat->clients` has a fixed size of `MAX_CLIENTS` (1000). The code indexes this array directly with the file descriptor `c->fd`. If a client’s socket descriptor is 1000 or larger, the assignment `Chat->clients[c->fd] = c;` writes past the end of the array, corrupting memory and potentially crashing the program.
- **Fix:** Ensure that `c->fd` is less than `MAX_CLIENTS` before indexing, e.g. `if (c->fd >= MAX_CLIENTS) { /* handle error or grow the array */ }`. A better design is to use a dynamic data structure (e.g. a hash map) that maps file descriptors to client structures.
- **Pass:** 1

### CRITICAL Out-of-bounds write when freeing client
- **Type:** invariant-false
- **Trigger:** (unmatched)
- **Location:** smallchat-server.c:98
- **Issue:** The same array bounds problem occurs when unbinding a client: `Chat->clients[c->fd] = NULL;` can write past the end of the array if `c->fd` is >= `MAX_CLIENTS`. This corrupts memory and may lead to crashes.
- **Fix:** Apply the same bounds check as in the creation path, or redesign the client storage to avoid indexing by raw file descriptor.
- **Pass:** 1

### CRITICAL Out-of-bounds read when updating maxclient after client removal
- **Type:** invariant-false
- **Trigger:** (unmatched)
- **Location:** smallchat-server.c:104
- **Issue:** When a client is removed, the code scans backwards from `Chat->maxclient-1` to find the next highest occupied slot. If `Chat->maxclient` is greater than or equal to `MAX_CLIENTS`, the loop accesses `Chat->clients[j]` out of bounds, leading to undefined behaviour.
- **Fix:** Ensure that `Chat->maxclient` never exceeds `MAX_CLIENTS-1`. Add a bounds check before the loop, or maintain a separate data structure that tracks active clients without relying on the raw file descriptor as an index.
- **Pass:** 1

### CRITICAL Out-of-bounds read when broadcasting messages
- **Type:** invariant-false
- **Trigger:** (unmatched)
- **Location:** smallchat-server.c:136
- **Issue:** The broadcast loop iterates `j` from 0 to `Chat->maxclient`. If `Chat->maxclient` is larger than `MAX_CLIENTS-1`, the loop will read `Chat->clients[j]` beyond the array bounds, causing memory corruption or a crash.
- **Fix:** Keep `Chat->maxclient` bounded by `MAX_CLIENTS-1` or use a dynamic container that does not rely on the file descriptor as an index. Alternatively, add a guard: `if (j >= MAX_CLIENTS) break;` inside the loop.
- **Pass:** 1

### smallchat-client.c

### [HIGH] Ignoring write return value may cause SIGPIPE crash
- **Type:** guideline
- **Trigger:** Ignoring a returned error from a called function
- **Location:** smallchat-client.c:248
- **Issue:** The program writes to the socket without checking the return value. If the socket is closed, `write()` will raise `SIGPIPE` and terminate the process, causing a crash. This is a recoverable error that should be handled gracefully.
- **Fix:** Check the return value of `write(s,ib.buf,ib.len)`. If it returns `-1` and `errno == EPIPE`, handle it by closing the socket and exiting gracefully, or ignore the signal by setting `signal(SIGPIPE, SIG_IGN)` or using `MSG_NOSIGNAL`. Consider using `send()` with `MSG_NOSIGNAL` or ignoring `SIGPIPE` globally.
- **Pass:** 1

### chatlib.c

### [HIGH] TCPConnect leaks memory when connect returns EINPROGRESS in non-blocking mode
- **Type:** guideline
- **Trigger:** Ignoring a returned error from a called function
- **Location:** chatlib.c:94
- **Issue:** The function returns early on EINPROGRESS without freeing the addrinfo linked list, leaking memory.
- **Fix:** Call `freeaddrinfo(servinfo)` before returning, or restructure the loop to free before returning.
- **Pass:** 1

### [HIGH] socketSetNonBlockNoDelay ignores setsockopt error
- **Type:** guideline
- **Trigger:** Ignoring a returned error from a called function
- **Location:** chatlib.c:33
- **Issue:** The return value of `setsockopt` is ignored, so failures to set `TCP_NODELAY` are not detected.
- **Fix:** Check the return value of `setsockopt` and handle errors appropriately (e.g., log or return an error code).
- **Pass:** 1

### [HIGH] createTCPServer ignores setsockopt error
- **Type:** guideline
- **Trigger:** Ignoring a returned error from a called function
- **Location:** chatlib.c:43
- **Issue:** The return value of `setsockopt` is ignored, so failures to set `SO_REUSEADDR` are not detected.
- **Fix:** Check the return value of `setsockopt` and handle errors appropriately (e.g., log or return an error code).
- **Pass:** 1

### chatlib.h

### [CRITICAL] TCPConnect signature should use const char *addr
- **Type:** guideline
- **Trigger:** (unmatched)
- **Location:** chatlib.h:8
- **Issue:** The `TCPConnect` function takes a non‑const `char *addr`. If a caller passes a string literal or a const buffer, the implementation may attempt to modify it, leading to undefined behaviour and possible crashes. The API contract should enforce const correctness to prevent accidental modification of caller data.
- **Fix:** Change the prototype to `int TCPConnect(const char *addr, int port, int nonblock);`
- **Pass:** 1

### Makefile

### [MEDIUM] Missing .PHONY declarations
- **Type:** guideline
- **Trigger:** (unmatched)
- **Location:** Makefile:1
- **Issue:** The targets `all` and `clean` are not declared as `.PHONY`. If files named `all` or `clean` exist in the directory, the make process may treat them as up‑to‑date and skip rebuilding, leading to stale binaries or unexpected behavior.
- **Fix:** Add a `.PHONY` line at the top of the Makefile, e.g.  
  ```make
  .PHONY: all clean
  ```
- **Pass:** 2

### [LOW] Unnecessary `-W` flag
- **Type:** guideline
- **Trigger:** (unmatched)
- **Location:** Makefile:2
- **Issue:** The `-W` flag without a warning type is ambiguous and may produce a warning or error during compilation. It is better to use a specific warning flag such as `-Wextra` or remove it if not needed.
- **Fix:** Replace `-W` with `-Wextra` or delete it:  
  ```make
  CFLAGS=-O2 -Wall -Wextra -std=c99
  ```
- **Pass:** 2
