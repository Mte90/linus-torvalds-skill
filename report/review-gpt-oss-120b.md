---
title: "SmallChat Review – Linus Torvalds Style"
date: 2026-08-11
---

# smallchat-server.c

### [CRITICAL] Missing NUL terminator for client nickname
- **Type:** invariant-false
- **Trigger:** *A fatal abort for a recoverable condition* (Theme 2 – Consistent & Safe Error Handling, trigger 2.1) – the missing terminator can cause undefined behaviour and crashes.
- **Location:** smallchat-server.c:80‑85
- **Issue:** `c->nick` is allocated with `nicklen+1` bytes but only `nicklen` bytes are copied (`memcpy(c->nick,nick,nicklen);`). The string is not NUL‑terminated, leading to potential buffer over‑read when printed or sent.
- **Fix:** Copy the terminating byte as well, e.g. `memcpy(c->nick, nick, nicklen+1);` or use `strcpy`/`strdup`.

### [HIGH] Ignored error returns from non‑blocking socket setup and writes
- **Type:** invariant-false
- **Trigger:** *A fatal abort for a recoverable condition* (2.1) – silently ignoring failures can leave the server in a broken state.
- **Location:** smallchat-server.c:81, 143, 144
- **Issue:** `socketSetNonBlockNoDelay(fd);` and `write(Chat->clients[j]->fd,s,len);` return values are discarded. If `fcntl` or `setsockopt` fails, the socket may stay blocking; if `write` fails, data loss occurs.
- **Fix:** Check return values and handle errors, e.g. abort with a clear message or close the client.

### [MEDIUM] No handling of partial reads / message framing
- **Type:** general-guideline
- **Trigger:** *Running heavy analysis on a large repository without optimization* (Theme 3 – Performance, trigger 3.2) – the lack of proper buffering wastes CPU and can corrupt chat streams.
- **Location:** smallchat-server.c:209‑218
- **Issue:** `read(j,readbuf,sizeof(readbuf)-1)` may return a partial message; the code assumes a full line and forwards it directly.
- **Fix:** Implement a per‑client buffer, accumulate until a newline is seen, then process the complete line.

# smallchat-client.c

### [HIGH] Ignoring failure of `setRawMode`
- **Type:** invariant-false
- **Trigger:** *A fatal abort for a recoverable condition* (2.1)
- **Location:** smallchat-client.c:204‑205
- **Issue:** `setRawMode(fileno(stdin),1);` return value is ignored. If the terminal cannot be put into raw mode, the client will misbehave.
- **Fix:** Check the return value; on error print a message and exit.

### [HIGH] Ignoring write errors to socket and stdout
- **Type:** invariant-false
- **Trigger:** *A fatal abort for a recoverable condition* (2.1)
- **Location:** smallchat-client.c:235‑236, 247‑248
- **Issue:** Calls to `write(fileno(stdout),buf,count);` and `write(s,ib.buf,ib.len);` do not verify the number of bytes written.
- **Fix:** Verify the return value; on short write retry or abort with a clear error.

### [LOW] Magic number for input buffer size
- **Type:** invariant-false
- **Trigger:** *Magic numbers without named constants* (Theme 7 – Documentation, trigger 7.4)
- **Location:** smallchat-client.c:118
- **Issue:** `#define IB_MAX 128` is a hard‑coded limit with no explanatory name.
- **Fix:** Replace with a named constant like `#define INPUT_BUFFER_CAPACITY 128` and add a comment.

# chatlib.c

### [HIGH] Ignored error returns from `socketSetNonBlockNoDelay` and `setsockopt`
- **Type:** invariant-false
- **Trigger:** *A fatal abort for a recoverable condition* (2.1)
- **Location:** chatlib.c:23‑34, 84‑87
- **Issue:** The function returns `-1` on failure but callers discard the result, potentially leaving sockets in blocking mode or without `TCP_NODELAY`.
- **Fix:** Propagate the error to the caller and abort or fallback with a diagnostic.

### [HIGH] Missing NUL terminator for client nickname (duplicate logic)
- **Type:** invariant-false
- **Trigger:** *A fatal abort for a recoverable condition* (2.1)
- **Location:** chatlib.c:78‑85
- **Issue:** Same as in `smallchat-server.c`: `memcpy(c->nick,nick,nicklen);` omits the terminating byte.
- **Fix:** Copy `nicklen+1` bytes or use `strcpy`.

### [HIGH] Unchecked `write` in `sendMsgToAllClientsBut`
- **Type:** invariant-false
- **Trigger:** *A fatal abort for a recoverable condition* (2.1)
- **Location:** chatlib.c:135‑144
- **Issue:** `write(Chat->clients[j]->fd,s,len);` ignores the return value; a short write can drop messages.
- **Fix:** Loop until all bytes are written or handle the error.

# Makefile

*No violations detected.* The build rules are straightforward and respect the project's simplicity.

---

## Summary
- **Verdict:** The codebase is functional but contains several correctness‑critical bugs (missing string terminators, unchecked system‑call errors) and a handful of style/maintainability issues.
- **Findings by severity:**
  - CRITICAL: 1
  - HIGH: 7
  - MEDIUM: 1
  - LOW: 1
- **Pass/fail:** **FAIL** – the critical and high‑severity issues must be fixed before the code can be considered acceptable.
