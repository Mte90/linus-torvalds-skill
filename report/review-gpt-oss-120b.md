---
title: SmallChat Code Review (Linus Torvalds Style)
date: 2026-08-12
---

# smallchat-server.c

### CRITICAL Missing NUL terminator for client nickname
- **Type:** invariant-false
- **Trigger:** *Memory Safety* – “Variables are used without being initialized.”
- **Location:** smallchat-server.c:80-85
- **Issue:** `c->nick` is allocated with `chatMalloc(nicklen+1)` but only `nicklen` bytes are copied from `nick` (lines 83‑84). The string is not NUL‑terminated, leading to undefined behavior when later used in `printf`/`write`.
- **Fix:** Copy the terminating byte or use `strcpy`/`snprintf` to ensure `c->nick[nicklen] = '\0';`.

### HIGH Ignored error return from `socketSetNonBlockNoDelay`
- **Type:** invariant-false
- **Trigger:** *Error‑Handling Consistency* – “A fatal abort (panic) is used for a condition that can be recovered.”
- **Location:** smallchat-server.c:81
- **Issue:** The call to `socketSetNonBlockNoDelay(fd)` is assumed to succeed (comment “Pretend this will not fail”). If it fails, the socket remains blocking, breaking the event loop.
- **Fix:** Check the return value and abort with a clear error message if non‑zero.

### HIGH Ignored write errors in `sendMsgToAllClientsBut`
- **Type:** invariant-false
- **Trigger:** *Error‑Handling Consistency* – “A fatal abort (panic) is used for a condition that can be recovered.”
- **Location:** smallchat-server.c:143
- **Issue:** `write(Chat->clients[j]->fd,s,len);` discards the return value. A short write or `EPIPE` is silently ignored, potentially losing messages or crashing later.
- **Fix:** Capture the return value, handle `EPIPE` by closing the client, and retry or log partial writes.

### LOW Magic numbers without named constants
- **Type:** invariant-false
- **Trigger:** *Memory Safety* – “Magic numbers appear in code without a named constant or comment.”
- **Location:** smallchat-server.c:45 (MAX_CLIENTS 1000), 46 (SERVER_PORT 7711), 511 backlog in `listen` (line 51), timeout `tv.tv_sec = 1` (line 171).
- **Issue:** Hard‑coded literals obscure intent and make future changes error‑prone.
- **Fix:** Define `#define LISTEN_BACKLOG 511`, `#define SELECT_TIMEOUT_SEC 1`, etc., with comments.

# smallchat-client.c

### HIGH Ignored error return from `setRawMode`
- **Type:** invariant-false
- **Trigger:** *Error‑Handling Consistency* – “A fatal abort (panic) is used for a condition that can be recovered.”
- **Location:** smallchat-client.c:204
- **Issue:** `setRawMode(fileno(stdin),1);` is called without checking its return. Failure leaves the terminal in cooked mode, breaking input handling.
- **Fix:** Check the return value and abort with a diagnostic if non‑zero.

### HIGH Ignored write errors to server socket
- **Type:** invariant-false
- **Trigger:** *Error‑Handling Consistency* – “A fatal abort (panic) is used for a condition that can be recovered.”
- **Location:** smallchat-client.c:248
- **Issue:** `write(s,ib.buf,ib.len);` discards the result. A failed write (e.g., broken pipe) is not detected, leading to silent data loss.
- **Fix:** Capture the return value, handle `EPIPE` by terminating the client gracefully.

### HIGH Input buffer overflow silently ignored
- **Type:** invariant-false
- **Trigger:** *Error‑Handling Consistency* – “A fatal abort (panic) is used for a condition that can be recovered.”
- **Location:** smallchat-client.c:160‑162
- **Issue:** When `inputBufferAppend` returns `IB_ERR` (buffer full), `inputBufferFeedChar` still returns `IB_OK` and discards the error, truncating user input without notice.
- **Fix:** Propagate the error (`IB_ERR`) up to the caller, display a warning, and possibly enlarge the buffer.

### LOW Magic number for input buffer size
- **Type:** invariant-false
- **Trigger:** *Memory Safety* – “Magic numbers appear in code without a named constant or comment.”
- **Location:** smallchat-client.c:118 (`#define IB_MAX 128`).
- **Issue:** Hard‑coded size limits line length without explanation.
- **Fix:** Replace with a named constant and document the intended maximum line length.

# chatlib.c

### HIGH Use of `assert` for runtime sanity check
- **Type:** invariant-false
- **Trigger:** *Error‑Handling Consistency* – “A fatal abort (panic) is used for a condition that can be recovered.”
- **Location:** chatlib.c:85
- **Issue:** `assert(Chat->clients[c->fd] == NULL);` aborts the whole program if the slot is already occupied. In production this is a recoverable error; aborting is unacceptable.
- **Fix:** Replace with proper error handling: return an error code and let the caller decide.

### HIGH Ignored return values from `socketSetNonBlockNoDelay`
- **Type:** invariant-false
- **Trigger:** *Error‑Handling Consistency* – “A fatal abort (panic) is used for a condition that can be recovered.”
- **Location:** chatlib.c:23‑35 (calls in `createClient` and `TCPConnect`).
- **Issue:** The function can fail (e.g., `fcntl` error) but the caller proceeds as if the socket is non‑blocking.
- **Fix:** Check the return value and handle the error (close socket, report).

### HIGH Ignored `write` errors in `sendMsgToAllClientsBut`
- **Type:** invariant-false
- **Trigger:** *Error‑Handling Consistency* – “A fatal abort (panic) is used for a condition that can be recovered.”
- **Location:** chatlib.c:143
- **Issue:** Same as server: `write` return value is discarded, hiding partial writes or `EPIPE`.
- **Fix:** Handle the return value, close broken connections, and possibly retry.

### LOW Magic numbers without named constants
- **Type:** invariant-false
- **Trigger:** *Memory Safety* – “Magic numbers appear in code without a named constant or comment.”
- **Location:** chatlib.c:45 (`511` backlog), 46 (`SERVER_PORT` defined elsewhere), 70 (`char portstr[6]`), 118 (`IB_MAX` already covered), 151‑152 (`MAX_CLIENTS 1000`).
- **Issue:** Hard‑coded literals reduce readability.
- **Fix:** Define descriptive macros/constants.

# Makefile

### LOW Magic numbers in compilation flags
- **Type:** invariant-false
- **Trigger:** *Memory Safety* – “Magic numbers appear in code without a named constant or comment.”
- **Location:** Makefile:2 (`-O2 -Wall -W -std=c99`).
- **Issue:** Optimization level and warning flags are hard‑coded; not a bug but a style point.
- **Fix:** Document the chosen flags or move them to a variable.

---

## Summary
- **Verdict:** The code compiles and runs, but several correctness‑critical bugs (missing NUL terminator, unchecked system‑call failures, misuse of `assert`) make it **unacceptable** for production.
- **Findings by severity:**
  - CRITICAL: 1
  - HIGH: 9
  - MEDIUM: 0
  - LOW: 5
- **Pass/Fail:** **FAIL** – the code does **not** pass the Linus‑style review. All high‑rank issues must be fixed before merging.
