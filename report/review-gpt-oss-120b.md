---
title: Review of SmallChat by gpt-oss-120b
date: 2026-09-08
model: gpt-oss-120b
files_reviewed: 5
findings_count: 15
verdict: needs review
---

## Review Summary

**Model:** gpt-oss-120b
**Files reviewed:** 5
**Total findings:** 15
**Findings by severity:** CRITICAL: 4, HIGH: 5, MEDIUM: 2, LOW: 4

## Findings

### smallchat-server.c

### [CRITICAL] Buffer overflow in nickname construction
- **Type:** invariant-false
- **Trigger:** Performing an unchecked pointer arithmetic that can walk off the end of a buffer
- **Location:** smallchat-server.c:71
- **Issue:** `snprintf(nick,sizeof(nick),"user:%d",fd)` writes into a fixed 32‑byte buffer. If `fd` is large enough the formatted string exceeds 31 characters (plus NUL), overflowing `nick`. This corrupts stack memory and can lead to crashes or security issues.
- **Fix:** Verify the return value of `snprintf` and ensure the formatted nickname fits, or allocate the nickname buffer dynamically based on the needed size before formatting.
- **Pass:** 1

### [CRITICAL] Missing NUL‑terminator for client nickname
- **Type:** invariant-false
- **Trigger:** Performing an unchecked pointer arithmetic that can walk off the end of a buffer
- **Location:** smallchat-server.c:76
- **Issue:** After allocating `c->nick = chatMalloc(nicklen+1);` the code copies only `nicklen` bytes with `memcpy(c->nick,nick,nicklen);`. The terminating NUL byte is not copied, so `c->nick` is not a proper C‑string. Subsequent uses (e.g., in `snprintf` for messages) read past the allocated buffer, causing undefined behaviour.
- **Fix:** Copy `nicklen+1` bytes or use `strcpy`/`strdup` to include the terminating NUL.
- **Pass:** 1

### [CRITICAL] Out‑of‑bounds access of `Chat->clients` array
- **Type:** invariant-false
- **Trigger:** Performing an unchecked pointer arithmetic that can walk off the end of a buffer
- **Location:** smallchat-server.c:71, 84, 95, 115, 124, 138, 151, 166, 176, 191, 203
- **Issue:** The file descriptor `fd` is used directly as an index into `Chat->clients[MAX_CLIENTS]` without verifying that `fd < MAX_CLIENTS`. If a client receives a descriptor ≥ 1000 the code writes past the end of the array, corrupting memory and likely crashing the server.
- **Fix:** Add a bounds check (`if (fd >= MAX_CLIENTS) { /* reject or enlarge array */ }`) before indexing, and adjust loops that rely on `Chat->maxclient` accordingly.
- **Pass:** 1

### [HIGH] Reliance on `assert` for runtime invariant
- **Type:** invariant-false
- **Trigger:** Fatal assertion (panic/fatal assertion) for a recoverable condition
- **Location:** smallchat-server.c:73
- **Issue:** `assert(Chat->clients[c->fd] == NULL);` is used to guarantee that the slot is free. In a production build where `NDEBUG` is defined, the assert disappears, and the code will silently overwrite an existing client entry, leading to memory leaks and undefined behaviour.
- **Fix:** Replace the assert with an explicit runtime check that returns an error or aborts gracefully if the slot is already occupied.
- **Pass:** 1

### [HIGH] Ignoring possible failure of `socketSetNonBlockNoDelay`
- **Type:** invariant-false
- **Trigger:** Silently swallowing an error and continuing execution
- **Location:** smallchat-server.c:72
- **Issue:** `socketSetNonBlockNoDelay(fd);` is called with the comment “Pretend this will not fail.” If the call fails, the socket may remain blocking, breaking the non‑blocking logic of the server and potentially causing the main loop to hang.
- **Fix:** Check the return value and handle errors (e.g., close the socket and abort client creation).
- **Pass:** 1

### [HIGH] Ignoring write errors in `sendMsgToAllClientsBut`
- **Type:** invariant-false
- **Trigger:** Silently swallowing an error and continuing execution
- **Location:** smallchat-server.c:106
- **Issue:** The `write()` call’s return value is ignored. If a client’s receive buffer is full or the connection is broken, `write` will fail, but the server proceeds as if the message was delivered, potentially losing data and leaving the client in an inconsistent state.
- **Fix:** Check the return value of `write`; on error, handle it (e.g., close the client and clean up).
- **Pass:** 1

### [HIGH] Treating any `read` error as client disconnect
- **Type:** invariant-false
- **Trigger:** Silently swallowing an error and continuing execution
- **Location:** smallchat-server.c:138
- **Issue:** `if (nread <= 0)` treats both `-1` (error) and `0` (EOF) as a disconnect. Errors such as `EINTR` or temporary network glitches will cause the server to drop the client unnecessarily.
- **Fix:** Distinguish `nread == 0` (orderly shutdown) from `nread == -1` and handle recoverable errors (`errno == EINTR` or `EAGAIN`) without destroying the client.
- **Pass:** 1

*No Pass 2 findings are reported because the file contains Pass 1 correctness issues.*

### smallchat-client.c

### [CRITICAL] Buffer overflow when appending newline to full input buffer
- **Type:** invariant-false
- **Trigger:** Performing an unchecked pointer arithmetic that can walk off the end of a buffer
- **Location:** smallchat-client.c:245
- **Issue:** When the input buffer reaches its maximum capacity (`IB_MAX`) the code still executes `inputBufferAppend(&ib,'\n')` without checking the return value. If the buffer is already full this writes past the end of `ib.buf`, corrupting memory and potentially causing a crash or security breach.
- **Fix:** Check the return value of `inputBufferAppend` before using the buffer and handle the overflow case (e.g., reject the line, clear the buffer, or enlarge the buffer). Do not write to the buffer when full.
- **Pass:** 1

### [HIGH] Ignored return value from setRawMode
- **Type:** invariant-false
- **Trigger:** Silently swallowing an error and continuing execution
- **Location:** smallchat-client.c:205
- **Issue:** `setRawMode(fileno(stdin),1);` is called without verifying its return value. If `setRawMode` fails (e.g., stdin is not a tty), the program proceeds with the terminal in an undefined state, leading to user‑visible misbehaviour or later failures.
- **Fix:** Check the return value and abort or fall back gracefully, for example:

```c
if (setRawMode(fileno(stdin),1) == -1) {
    perror("setRawMode");
    exit(1);
}
```

- **Pass:** 1

### chatlib.c

### [LOW] Missing `const` qualifier on `TCPConnect` address parameter  
- **Type:** (unmatched)  
- **Trigger:** (unmatched)  
- **Location:** chatlib.c:65  
- **Issue:** The function `int TCPConnect(char *addr, int port, int nonblock)` does not modify the address string, yet the parameter is not declared `const`. This permits accidental modification and reduces type safety.  
- **Fix:** Change the signature to `int TCPConnect(const char *addr, int port, int nonblock)` and update any internal uses accordingly.  
- **Pass:** 2

### [LOW] Magic number used for listen backlog  
- **Type:** general-guideline  
- **Trigger:** Magic numbers & hard‑coded constants (Theme 7)  
- **Location:** chatlib.c:58  
- **Issue:** The call `listen(s, 511)` embeds the backlog value directly as a literal. Hard‑coded numbers obscure intent and make future adjustments error‑prone.  
- **Fix:** Define a named constant, e.g., `#define LISTEN_BACKLOG 511` (or use a configuration macro) and replace the literal with `listen(s, LISTEN_BACKLOG)`.  
- **Pass:** 2

### chatlib.h

### [MEDIUM] Missing size_t definition
- **Type:** guideline
- **Trigger:** (unmatched)
- **Location:** chatlib.h:11
- **Issue:** `size_t` is used without including a header that defines it (`<stddef.h>` or `<stdlib.h>`). This will cause a compilation error on any translation unit that includes this header.
- **Fix:** Add `#include <stddef.h>` (or `<stdlib.h>`) before the function prototypes that use `size_t`.
- **Pass:** 2

### [LOW] Inconsistent naming convention
- **Type:** guideline
- **Trigger:** Identifier that does not convey its purpose (Naming & Comment Accuracy)
- **Location:** chatlib.h:5
- **Issue:** The API mixes snake_case (`createTCPServer`, `socketSetNonBlockNoDelay`, `acceptClient`) with camelCase (`TCPConnect`). Inconsistent naming hurts readability and maintenance.
- **Fix:** Adopt a single naming style (e.g., all snake_case) and rename the functions accordingly, updating all callers. For example, rename `TCPConnect` to `tcp_connect`.
- **Pass:** 2

### Makefile

### [MEDIUM] Missing .PHONY declarations
- **Type:** guideline
- **Trigger:** (unmatched)
- **Location:** Makefile:1
- **Issue:** The makefile does not declare the `all` and `clean` targets as phony. If files named `all` or `clean` ever appear in the source tree, `make` will consider the targets up‑to‑date and skip rebuilding, leading to stale binaries.
- **Fix:** Add a `.PHONY` line, e.g.:  
  ```make
  .PHONY: all clean
  ```
- **Pass:** 2

### [LOW] CFLAGS placed after output file
- **Type:** guideline
- **Trigger:** (unmatched)
- **Location:** Makefile:5,8
- **Issue:** Compiler flags (`$(CFLAGS)`) are placed after the `-o` option in the link commands. While the build still works, the conventional order is `$(CC) $(CFLAGS) sources -o target`. This improves readability and guarantees the flags are applied to the compilation stage rather than being passed to the linker unintentionally.
- **Fix:** Rearrange the commands, e.g.:  
  ```make
  $(CC) $(CFLAGS) smallchat-server.c chatlib.c -o smallchat-server
  $(CC) $(CFLAGS) smallchat-client.c chatlib.c -o smallchat-client
  ```
- **Pass:** 2
