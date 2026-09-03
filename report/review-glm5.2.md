---
title: Review of SmallChat by glm5.2
date: 2026-09-03
model: glm5.2
files_reviewed: 5
findings_count: 16
verdict: needs review
---

## Review Summary

**Model:** glm5.2
**Files reviewed:** 5
**Total findings:** 16
**Findings by severity:** CRITICAL: 2, HIGH: 12, MEDIUM: 1, LOW: 1

## Findings

### smallchat-server.c

No findings.

### smallchat-client.c

### HIGH — `select()` EINTR treated as fatal exit
- **Type:** invariant-false
- **Trigger:** Fatal assertion or crash used for a recoverable condition
- **Location:** smallchat-client.c:~190 (`select()` error path in `main`)
- **Issue:** `select()` returning -1 with `errno == EINTR` is a normal, recoverable condition — a signal was delivered. The code unconditionally calls `exit(1)`. For a terminal application, signals like `SIGWINCH` (window resize) are routine. The program will crash on terminal resize.
- **Fix:** Check for `EINTR` and `continue` the loop. Only exit on genuine errors.
- **Pass:** 1

### HIGH — `read()` EINTR on socket causes false disconnection
- **Type:** invariant-false
- **Trigger:** Fatal assertion or crash used for a recoverable condition
- **Location:** smallchat-client.c:~200 (`read(s, buf, sizeof(buf))` in `main`)
- **Issue:** `read()` returning -1 with `errno == EINTR` is treated as `count <= 0`, printing "Connection lost" and calling `exit(1)`. The connection is perfectly fine — a signal simply interrupted the read. The user is disconnected for no reason.
- **Fix:** Check for `errno == EINTR` after `read()` returns -1 and `continue` the loop instead of exiting.
- **Pass:** 1

### HIGH — Unchecked `inputBufferAppend()` return silently drops newline
- **Type:** invariant-false
- **Trigger:** Error handling that masks the root cause
- **Location:** smallchat-client.c:~210 (`IB_GOTLINE` case in `main`)
- **Issue:** When the user types exactly `IB_MAX` (128) characters and presses enter, `inputBufferAppend(&ib, '\n')` returns `IB_ERR` because the buffer is full. The return value is never checked. The newline is silently dropped, and `write(s, ib.buf, ib.len)` sends 128 bytes with no newline terminator to the server. The server likely expects newline-delimited messages, so this message is either merged with the next one or silently misinterpreted.
- **Fix:** Check the return value of `inputBufferAppend`. If the buffer is full, either flush the current buffer first and then append the newline, or ensure `IB_MAX` reserves one byte for the trailing newline.
- **Pass:** 1

### HIGH — stdin EOF causes 100% CPU busy loop
- **Type:** invariant-false
- **Trigger:** (unmatched)
- **Location:** smallchat-client.c:~205 (`read(stdin_fd, buf, sizeof(buf))` in `main`)
- **Issue:** When stdin reaches EOF (e.g., input pipe closes), `read()` returns 0. The code does not check for this condition. The `for` loop with `count == 0` does nothing, and the `while(1)` loop calls `select()` again. Since EOF is a persistent condition, `select()` immediately returns stdin as readable, `read()` returns 0 again, and the program spins forever at 100% CPU.
- **Fix:** Check for `count == 0` from `read(stdin_fd, ...)` and exit the loop (or break out of the program) when stdin is closed.
- **Pass:** 1

### HIGH — Unchecked `write()` to socket silently loses message data
- **Type:** invariant-false
- **Trigger:** (unmatched)
- **Location:** smallchat-client.c:~213 (`write(s, ib.buf, ib.len)` in `main`)
- **Issue:** The return value of `write(s, ib.buf, ib.len)` is never checked. If `write()` is interrupted by a signal (`EINTR`) or performs a partial write, message data is silently lost. The user believes their message was sent, but the server never received it (or received only part of it). For a chat client, silent message loss is a correctness defect.
- **Fix:** Check the return value of `write()`. Handle `EINTR` by retrying, and handle partial writes by looping until all bytes are written or a genuine error occurs.
- **Pass:** 1

---

**Pass 2 findings suppressed** — file has Pass-1 findings per merge rule.

### chatlib.c

### HIGH Memory leak in TCPConnect on non-blocking EINPROGRESS return
- **Type:** invariant-false
- **Trigger:** (unmatched) — resource leak on early return path
- **Location:** chatlib.c:`TCPConnect` — `if (errno == EINPROGRESS && nonblock) return s;`
- **Issue:** When `connect()` returns -1 with `errno == EINPROGRESS` and `nonblock` is true, the function returns the socket descriptor `s` immediately **without calling `freeaddrinfo(servinfo)`**. The entire `addrinfo` linked list allocated by `getaddrinfo()` is leaked on every non-blocking connect attempt. In a long-running server that makes non-blocking connections, this is an unbounded memory leak — every single non-blocking connect leaks the full resolved address list.
- **Fix:** Free the addrinfo list before returning:
  ```c
  if (errno == EINPROGRESS && nonblock) {
      freeaddrinfo(servinfo);
      return s;
  }
  ```
- **Pass:** 1

---

### HIGH TCPConnect does not try alternative addresses on connect failure
- **Type:** invariant-true
- **Trigger:** Comment that does not match the actual behavior of the code
- **Location:** chatlib.c:`TCPConnect` — the `close(s); break;` path after `connect()` failure
- **Issue:** The comment at the top of the loop explicitly states: *"If we fail in the socket() call, or on connect(), we retry with the next entry in servinfo."* But the code does `break` on connect failure, not `continue`. This means if the first resolved address fails to connect (e.g., IPv6 address with no IPv6 connectivity, or connection refused), the remaining addresses from `getaddrinfo` are never tried. The `socket()` failure path correctly uses `continue`, but the `connect()` failure path uses `break` — contradicting both the comment and the apparent design intent. The consequence is that `TCPConnect` will report failure when a connection to a secondary address would have succeeded.
- **Fix:** Change `break` to `continue` so the loop tries the next resolved address:
  ```c
  /* Otherwise it's an error. */
  close(s);
  continue;  /* was: break; */
  ```
- **Pass:** 1

---

## Pass 2 — Style and Build Findings

Dropped — file has Pass-1 findings.

### chatlib.h

### MEDIUM] Missing `const` qualifier on `TCPConnect` address parameter
- **Type:** invariant-false
- **Trigger:** Function requires caller to perform part of the work / API contract mismatch
- **Location:** chatlib.h:9
- **Issue:** `TCPConnect(char *addr, int port, int nonblock)` declares `addr` as a non-const `char *`. This signals the function may modify the caller's string. Callers who pass string literals (e.g., `TCPConnect("127.0.0.1", port, 0)`) invoke undefined behavior if the implementation writes through the pointer. The API contract should promise read-only access to the address string. This is a correctness-adjacent design flaw: the signature permits a class of bugs that `const` would make impossible.
- **Fix:** Change the declaration to `int TCPConnect(const char *addr, int port, int nonblock)`.
- **Pass:** 2

### [LOW] Inconsistent naming convention across public API
- **Type:** guideline
- **Trigger:** Inconsistent naming across similar entities
- **Location:** chatlib.h:4-9
- **Issue:** The four networking functions follow three different naming patterns: `createTCPServer` (lowerCamelCase), `socketSetNonBlockNoDelay` (lowerCamelCase with `socket` prefix), `acceptClient` (lowerCamelCase), and `TCPConnect` (PascalCase prefix). There is no consistent convention. Callers must remember which prefix or casing each function uses, increasing cognitive load and the chance of misspelling a call.
- **Fix:** Pick one convention (e.g., all lowerCamelCase with a shared prefix like `chat` or `net`) and apply it uniformly across all declarations.
- **Pass:** 2

### Makefile

### HIGH Missing `.PHONY` declaration for phony targets
- **Type:** invariant-false
- **Trigger:** Breaking existing working setups
- **Location:** Makefile:1,12
- **Issue:** The `all` and `clean` targets are not declared `.PHONY`. If a file named `all` or `clean` ever appears in the build directory, `make all` or `make clean` will silently do nothing — Make sees the file, concludes the target is up-to-date, and skips the recipe entirely. This is a silent build failure. The user types `make clean`, sees no error, and assumes it worked. That is a correctness bug in the build system.
- **Fix:** Add `.PHONY: all clean` before the `all` target.
- **Pass:** 1

### HIGH Missing header file dependencies in build rules
- **Type:** invariant-false
- **Trigger:** Breaking existing working setups
- **Location:** Makefile:4,7
- **Issue:** The build rules list only `.c` files as prerequisites. A multi-file C project like this virtually certainly has at least one header (e.g., `chatlib.h`) shared between `smallchat-server.c`, `smallchat-client.c`, and `chatlib.c`. Modifying that header will not trigger a rebuild. The user edits the header, runs `make`, gets no recompilation, and runs stale binaries that don't match the source. That is build corruption — the output silently disagrees with the input.
- **Fix:** Add all header files as prerequisites to every target that includes them. For example: `smallchat-server: smallchat-server.c chatlib.c chatlib.h`.
- **Pass:** 1

---

Pass 2 findings suppressed — file has Pass-1 findings.
