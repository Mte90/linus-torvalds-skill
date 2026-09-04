---
title: Review of SmallChat by gpt-oss-120b
date: 2026-09-04
model: gpt-oss-120b
files_reviewed: 5
findings_count: 9
verdict: needs review
---

## Review Summary

**Model:** gpt-oss-120b
**Files reviewed:** 5
**Total findings:** 9
**Findings by severity:** CRITICAL: 3, HIGH: 4, MEDIUM: 0, LOW: 2

## Findings

### smallchat-server.c

### CRITICAL Missing NUL terminator for client nickname  
- **Type:** invariant‑false  
- **Trigger:** (unmatched) – missing string termination leads to undefined behaviour when the nickname is used as a C‑string.  
- **Location:** smallchat-server.c:71  
- **Issue:** `createClient()` allocates `c->nick` with `nicklen+1` bytes but copies only `nicklen` bytes from the temporary buffer, leaving the last byte uninitialised. Subsequent uses of `c->nick` with `%s` expect a NUL‑terminated string, which can cause buffer over‑reads and crashes.  
- **Fix:** Copy the terminating byte as well, e.g. `memcpy(c->nick, nick, nicklen+1);` or simply use `strcpy(c->nick, nick);`.  
- **Pass:** 1

### CRITICAL Out‑of‑bounds access of `Chat->clients` array  
- **Type:** invariant‑false  
- **Trigger:** (unmatched) – using a file descriptor as an index without bounds checking can write/read past the `MAX_CLIENTS` array.  
- **Location:** smallchat-server.c:71 (indexing in `createClient`) and smallchat-server.c:115 (indexing in `freeClient`).  
- **Issue:** The code assumes every socket descriptor (`fd`) is less than `MAX_CLIENTS`. If the OS returns a descriptor ≥ 1000, the write `Chat->clients[c->fd] = c;` writes out of bounds, corrupting memory and leading to crashes.  
- **Fix:** Verify `fd` is within range before using it as an index, e.g.:  
  ```c
  if (fd < 0 || fd >= MAX_CLIENTS) {
      close(fd);
      return NULL;   // or handle the error appropriately
  }
  ```  
  Apply the same check wherever `fd` is used as an array index.  
- **Pass:** 1

### HIGH Unchecked allocation results in possible NULL dereference  
- **Type:** invariant‑false  
- **Trigger:** Ignoring the result of a resource‑allocation call before using the resource  
- **Location:** smallchat-server.c:71 (`chatMalloc(sizeof(*c))`), smallchat-server.c:84 (`chatMalloc(nicklen+1)`), and smallchat-server.c:46 (`chatMalloc(sizeof(*Chat))`).  
- **Issue:** The code calls `chatMalloc` (presumably a wrapper around `malloc`) and proceeds to use the returned pointer without verifying it is non‑NULL. On out‑of‑memory conditions this will cause a NULL‑pointer dereference and crash.  
- **Fix:** Check each allocation, e.g.:  
  ```c
  struct client *c = chatMalloc(sizeof(*c));
  if (!c) { perror("malloc"); exit(1); }
  ```  
  Do the same for all other allocations.  
- **Pass:** 1

### HIGH Unchecked return value from `acceptClient` may lead to invalid client creation  
- **Type:** invariant‑false  
- **Trigger:** Ignoring the result of a resource‑allocation call before using the resource  
- **Location:** smallchat-server.c:102 (`int fd = acceptClient(Chat->serversock);`).  
- **Issue:** `acceptClient` can return –1 on error, but the code immediately passes this value to `createClient(fd)`. This results in an invalid file descriptor being stored in the global state and later used as an array index, triggering out‑of‑bounds accesses and crashes.  
- **Fix:** Verify the return value before proceeding:  
  ```c
  int fd = acceptClient(Chat->serversock);
  if (fd == -1) {
      perror("accept");
      continue;   // or handle the error appropriately
  }
  struct client *c = createClient(fd);
  ```  
- **Pass:** 1

### smallchat-client.c

### HIGH Ignoring LF line terminator prevents line submission
- **Type:** invariant‑false
- **Trigger:** (unmatched)
- **Location:** smallchat-client.c:132
- **Issue:** `inputBufferFeedChar` discards `'\n'` characters (`case '\n': break;`) and only treats `'\r'` as end‑of‑line. On systems where the terminal sends a line‑feed (`'\n'`) this prevents the client from ever recognizing a completed line, breaking the chat protocol.
- **Fix:** Treat `'\n'` the same as `'\r'` (return `IB_GOTLINE`) or normalize input to a single line‑ending character before processing.
- **Pass:** 1

### chatlib.c

### HIGH Memory leak on early return in TCPConnect
- **Type:** invariant-false
- **Trigger:** (unmatched)
- **Location:** chatlib.c:94
- **Issue:** When `connect()` returns `EINPROGRESS` in non‑blocking mode, the function returns the socket descriptor immediately. This bypasses the `freeaddrinfo(servinfo);` call that appears later, leaking the memory allocated by `getaddrinfo`.
- **Fix:** Free `servinfo` before returning, e.g.:

```c
if (errno == EINPROGRESS && nonblock) {
    freeaddrinfo(servinfo);
    return s;
}
```

or restructure the logic to store the socket in `retval`, break the loop, and let the single `freeaddrinfo` at the end run.

- **Pass:** 1

### chatlib.h

### [CRITICAL] Missing definition for `size_t`
- **Type:** invariant-false
- **Trigger:** (unmatched)
- **Location:** chatlib.h:11
- **Issue:** The header uses `size_t` without including the required definition (`<stddef.h>` or `<stdlib.h>`), causing a compilation error.
- **Fix:** Add `#include <stddef.h>` (or `<stdlib.h>`) before the function declarations that use `size_t`.
- **Pass:** 1

### Makefile

### LOW Missing .PHONY declarations  
- **Type:** guideline  
- **Trigger:** (unmatched)  
- **Location:** Makefile:1  
- **Issue:** The makefile does not declare its public targets (`all`, `clean`, `smallchat-server`, `smallchat-client`) as `.PHONY`. Without this, if a file with one of those names exists in the directory, `make` may consider the target up‑to‑date and skip the commands, leading to confusing builds.  
- **Fix:** Add a `.PHONY` line near the top, e.g.:  
  ```make
  .PHONY: all clean smallchat-server smallchat-client
  ```  
- **Pass:** 2

### LOW Inconsistent placement of compilation flags  
- **Type:** guideline  
- **Trigger:** (unmatched)  
- **Location:** Makefile:5-8  
- **Issue:** The `$(CFLAGS)` variable, which contains compile‑time options (`-O2 -Wall -W -std=c99`), is placed after the `-o` option in the link command. While GCC accepts this ordering, the conventional style is to put compilation flags before the source files so that they are clearly applied during compilation, not linking. This improves readability and avoids accidental omission if the command is later split.  
- **Fix:** Reorder the command lines, e.g.:  
  ```make
  smallchat-server: smallchat-server.c chatlib.c
  	$(CC) $(CFLAGS) smallchat-server.c chatlib.c -o smallchat-server

  smallchat-client: smallchat-client.c chatlib.c
  	$(CC) $(CFLAGS) smallchat-client.c chatlib.c -o smallchat-client
  ```  
- **Pass:** 2
