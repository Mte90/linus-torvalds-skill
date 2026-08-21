---
title: "Smallchat Code Review Summary — GLM5.2"
date: 2026-08-21
model: glm5.2
files_reviewed: 5
findings_count: 24
verdict: "reject — multiple critical correctness and memory-safety defects"
---

## Persona Narrative

The skill reads like sitting next to someone who has read every LKML thread and internalized the disposition rather than memorized rules. The reviewer mindset section sets the tone before any trigger fires: "code either works or it doesn't" is not a platitude here, it is the lens. Applying it to smallchat felt less like running a checklist and more like adopting a stance — default to no, demand evidence, and treat every special case as a symptom of a wrong data model.

In practice, the triggers fired predictably and with good signal-to-noise. The "fatal assertion for a recoverable condition" trigger caught both the `assert()` on the client slot and the `exit(1)` in the OOM allocators — exactly the kind of bug the skill's example quote calls "complete and utter idiocy." The "error handling that aborts on a recoverable condition" trigger caught every `EINTR`-kills-the-server instance. The skill did not produce stylistic navel-gazing; it produced findings about whether the code works. The voice — direct, profane where warranted, evidence-anchored — carried through without forcing the reviewer to perform a character.

The one place the skill felt slightly mechanical was in the lower-severity findings. The "misleading comment" and "inconsistent naming" triggers fired correctly but read more like generic lint output than Torvalds-style critique. The skill's strength is in the correctness and error-handling themes; the style and documentation themes are thinner and produce less distinctive output. A reviewer applying this skill would not mistake themselves for Torvalds on a naming-convention finding, but they would on a buffer-overflow finding.

## Technical Assessment

**Coverage.** The review touched 9 of the skill's 12 trigger themes across 5 files. Error Handling and Recovery dominated (8 findings), followed by Memory Safety and Resource Management (3), API and Interface Stability (3), Documentation and Communication (3), Complexity and Simplicity (2), and Abstraction and Reuse (2). Concurrency, Performance, Testing, and Process themes did not fire — appropriate for a single-threaded chat server with no performance claims and no patch series to bisect.

**Accuracy.** Every finding cites a concrete line range, a specific trigger, and a verbatim quote from the skill. The two CRITICAL findings (fd bounds check, assert on runtime condition) are real buffer-overflow and memory-corruption bugs, not theoretical concerns. The EAGAIN-as-disconnection finding is the strongest technical catch: the code sets non-blocking mode but never handles non-blocking semantics, a genuine logic error the skill's "code is binary" mindset is designed to surface.

**Severity calibration.** Calibration is mostly correct but slightly conservative in one case. The skill prescribes `reject` for "error handling that aborts on a recoverable condition." The chatlib.c OOM-abort finding was labeled HIGH rather than CRITICAL, which understates it — the skill's own example quote calls this pattern "NOT ACCEPTABLE." The two CRITICAL findings are correctly calibrated. The MEDIUM and LOW findings align with the skill's `request-changes` and `discussion` severities.

**Precedence adherence.** The review follows the skill's precedence hierarchy (Correctness > Performance > Complexity > Style > API-stability). The two CRITICAL findings are correctness/memory-safety defects. The HIGH findings are correctness defects (EAGAIN, EINTR, unchecked returns). Style and documentation findings (naming, comments) are correctly deprioritized to LOW. No finding violates the hierarchy.

## Strengths

- Triggers fire on real bugs, not style preferences: the fd-bounds-check and EAGAIN findings are exploitable defects, not opinions.
- Every finding is anchored to a verbatim skill quote and a specific trigger type, making the review auditable and reproducible.
- The "eliminating special cases" theme correctly identified the maxclient recalculation as a data-model symptom rather than a local bug.
- Error-handling coverage is thorough: every `exit(1)` on a recoverable condition (EINTR, OOM, select failure) was caught across both server and client.
- The review correctly treats security as a subset of correctness — the fd overflow is filed as a memory-safety bug, not a "security finding," matching the skill's framing.

## Weaknesses

- The chatlib.c OOM-abort finding is under-severitized: the skill prescribes `reject` and calls the pattern "NOT ACCEPTABLE," but the finding was labeled HIGH rather than CRITICAL.
- Lower-severity findings (naming convention, dead code, comment fixes) read as generic lint output and do not carry the skill's distinctive voice.
- No finding engaged the Concurrency, Performance, or Testing themes — defensible for this codebase, but the review did not note the absence of tests as a finding, which the skill's Testing theme would support.
- The Makefile findings use the "ambiguous return value" trigger loosely; a missing header prerequisite is a build-correctness issue, not a return-value ambiguity.
- The review does not synthesize across files: the same EINTR bug appears in both server and client, but the findings are filed independently without noting the systemic pattern.

## Verdict

Not production-ready. The codebase contains two CRITICAL memory-safety defects (buffer overflow on fd index, assert compiled out in release builds) and multiple HIGH correctness defects (EAGAIN mishandling, EINTR crashes, unchecked I/O returns). The skill correctly identifies these as reject-level issues; the code must be fixed before any deployment.

## Findings

### smallchat-server.c

# Review: smallchat-server.c

**File:** `/tmp/smallchat/smallchat-server.c`
**Skill:** `linus-torvalds-skill/SKILL-GLM.md`
**Reviewer:** glm5.2

---

### [CRITICAL] No bounds check on file descriptor before array access
- **Type:** invariant-false
- **Trigger:** Fatal assertion or crash used for a condition that can be triggered by external input or runtime state (correctness — code either works or it doesn't)
- **Location:** smallchat-server.c:85-86 (createClient)
- **Issue:** `createClient` stores the client at `Chat->clients[c->fd]` without verifying `c->fd < MAX_CLIENTS`. The `clients` array is sized to `MAX_CLIENTS` (1000 elements, indices 0–999). If `acceptClient` returns an fd ≥ 1000 — entirely possible on a system with many open file descriptors — the write at line 86 overflows the array. There is no validation anywhere in the call chain. This is a buffer overflow: memory corruption, crash, or exploitable vulnerability.
- **Fix:** Add a bounds check at the top of `createClient`:
  ```c
  if (fd < 0 || fd >= MAX_CLIENTS) {
      close(fd);
      return NULL;
  }
  ```
  Handle the `NULL` return in the caller (`main`, line 189) by refusing the connection.

---

### [CRITICAL] assert() used for runtime condition — disappears in release builds
- **Type:** invariant-false
- **Trigger:** Fatal assertion or crash used for a condition that can be triggered by external input or runtime state
- **Location:** smallchat-server.c:85
- **Issue:** `assert(Chat->clients[c->fd] == NULL)` checks a runtime condition — whether the slot is free. File descriptors are reused after `close()`, so a slot can become occupied again. In release builds (`-DNDEBUG`), the assert is compiled out entirely. The check vanishes, and if the slot is occupied, the existing client pointer is silently overwritten — a memory leak and potential use-after-free. You can't have it both ways: either the condition can happen (in which case it needs a real runtime check, not an assert), or it cannot happen (in which case the assert should not exist).
- **Fix:** Replace the assert with a runtime check and recovery:
  ```c
  if (Chat->clients[c->fd] != NULL) {
      freeClient(Chat->clients[c->fd]);
  }
  ```

---

### [HIGH] read() treats EAGAIN as disconnection on non-blocking socket
- **Type:** invariant-false
- **Trigger:** Code either works or it doesn't (correctness)
- **Location:** smallchat-server.c:209-216
- **Issue:** Sockets are set to non-blocking mode (line 81: `socketSetNonBlockNoDelay(fd)`), but `read()` returning -1 with `EAGAIN`/`EWOULDBLOCK` is treated as disconnection (`nread <= 0` → `freeClient`). On a non-blocking socket, `EAGAIN` means "no data right now, try again" — it is not an error and not a disconnection. Clients are spuriously disconnected. The code sets non-blocking mode but does not handle non-blocking semantics.
- **Fix:** Distinguish EAGAIN from real disconnection:
  ```c
  if (nread == 0 || (nread == -1 && errno != EAGAIN && errno != EWOULDBLOCK)) {
      freeClient(Chat->clients[j]);
  } else if (nread > 0) {
      /* process data */
  }
  ```

---

### [HIGH] select() error causes server exit — EINTR is recoverable
- **Type:** invariant-false
- **Trigger:** Error handling that aborts or traps on a recoverable condition instead of returning an error
- **Location:** smallchat-server.c:180-182
- **Issue:** `select()` can fail with `EINTR` (interrupted by a signal), which is fully recoverable — the server should retry the loop. Instead, `exit(1)` kills the server on any `select` error, including a harmless signal interruption. A single `SIGCHLD` or terminal resize signal takes down the entire chat server.
- **Fix:** Handle EINTR and continue; exit only on real errors:
  ```c
  if (retval == -1) {
      if (errno == EINTR) continue;
      perror("select() error");
      exit(1);
  }
  ```

---

### [HIGH] socketSetNonBlockNoDelay return value ignored — server can hang
- **Type:** invariant-false
- **Trigger:** Error handling path that masks or hides the underlying bug
- **Location:** smallchat-server.c:81
- **Issue:** The comment says `// Pretend this will not fail.` If `socketSetNonBlockNoDelay` fails, the socket remains in blocking mode. A blocking `read()` in the main event loop (line 209) would then hang the entire server on a single slow or stalled client. One client stalls → the whole server freezes. Pretending a failure cannot happen does not make it so — it just removes your ability to detect it.
- **Fix:** Check the return value and refuse the connection on failure:
  ```c
  if (socketSetNonBlockNoDelay(fd) == -1) {
      close(fd);
      return NULL;
  }
  ```

---

### [MEDIUM] select()/FD_SET vulnerable to FD_SETSIZE overflow
- **Type:** invariant-false
- **Trigger:** Shared mutable data accessed without explicit synchronization → memory safety (buffer overflow in fd_set bitmask)
- **Location:** smallchat-server.c:163-166
- **Issue:** `FD_SET` writes to a fixed-size bitmask (`fd_set`, typically 1024 bits on Linux). If a file descriptor ≥ `FD_SETSIZE` (usually 1024), `FD_SET` writes out of bounds — a stack buffer overflow. With `MAX_CLIENTS` set to 1000, the server operates close to this limit. `select()` itself also cannot handle fds ≥ `FD_SETSIZE` and will fail or produce undefined behavior.
- **Fix:** Either check `fd < FD_SETSIZE` before `FD_SET` and reject connections that exceed it, or switch to `poll()` or `epoll()`, which have no fixed-size bitmask limitation.

---

### [MEDIUM] write() return values ignored — messages silently lost
- **Type:** invariant-false
- **Trigger:** Silent error swallowing (anti-pattern: errors must be visible and actionable)
- **Location:** smallchat-server.c:143, 194, 248
- **Issue:** All `write()` calls ignore the return value. On a non-blocking socket, `write()` can return -1 with `EAGAIN` (buffer full) or a short write (partial data sent). Messages are silently truncated or dropped. The comment at lines 140–142 acknowledges this ("we don't care"), but ignoring errors means data loss is invisible — neither the sender nor the receiver knows a message was lost.
- **Fix:** At minimum, log short writes and `EAGAIN` returns. For correctness, buffer pending data per client and retry on the next `select()` iteration when the socket is writable again.

---

### [MEDIUM] Misleading comment on MAX_CLIENTS
- **Type:** invariant-false
- **Trigger:** Comment that does not match the code's actual behavior
- **Location:** smallchat-server.c:45
- **Issue:** `#define MAX_CLIENTS 1000 // This is actually the higher file descriptor.` The comment says "higher file descriptor," but `MAX_CLIENTS` is used as the array size (line 62: `struct client *clients[MAX_CLIENTS]`). The actual highest fd is tracked separately in `Chat->maxclient`. The comment misleads readers into thinking the constant represents a file descriptor value rather than an array bound, which obscures the bounds-check issue (see CRITICAL finding above).
- **Fix:** Change the comment to match the actual usage:
  ```c
  #define MAX_CLIENTS 1000 // Maximum number of connected clients (array size, indexed by fd).
  ```

---

### [LOW] maxclient recalculation is a special case created by the data model
- **Type:** general-guideline
- **Trigger:** Code contains a conditional branch that exists only to handle the first element, empty case, or boundary of a data structure
- **Location:** smallchat-server.c:100-111
- **Issue:** When the highest client disconnects, the code scans backward through the array to find the new max (lines 104–109), with a special case for the empty state (line 110: `if (j == -1) Chat->maxclient = -1`). This special case exists because the data model uses the file descriptor as a direct array index, which requires tracking the highest occupied slot. A different representation — a count-tracked structure or a linked list — would eliminate the branch and the scan.
- **Fix:** This is a design observation, not a bug. The fd-indexed array is a deliberate simplicity choice for this example program. If the server grows beyond a toy, switch to a data structure that does not require max-slot tracking.

### smallchat-client.c

# Review: smallchat-client.c

Skill: `linus-torvalds-skill/SKILL-GLM.md`
Source: `/tmp/smallchat/smallchat-client.c`

---

### [HIGH] select() exits on EINTR instead of retrying
- **Type:** invariant-false
- **Trigger:** Error handling that aborts or traps on a recoverable condition instead of returning an error
- **Location:** smallchat-client.c:221-223
- **Issue:** `select()` returns -1 with `errno=EINTR` when interrupted by a signal. The code treats this as fatal and calls `exit(1)`. EINTR is recoverable — the correct response is to retry the `select()`. After resuming from Ctrl-Z suspension (SIGTSTP), or upon receiving any signal (SIGURG, SIGCHLD from a child, etc.), the client crashes with "select() error: Interrupted system call". The program enables signal characters in raw mode (ISIG not cleared, line 85-86), so Ctrl-Z suspension is a supported interaction that breaks the client on resume.
- **Fix:** Check for `EINTR` specifically and `continue` the loop; only exit on other errors:
  ```c
  if (num_events == -1) {
      if (errno == EINTR) continue;
      perror("select() error");
      exit(1);
  }
  ```

### [HIGH] stdin read() return value unchecked; EOF causes busy loop
- **Type:** invariant-false
- **Trigger:** Error handling path that masks the underlying bug / Silent error swallowing (anti-pattern)
- **Location:** smallchat-client.c:239-240
- **Issue:** `read(stdin_fd, buf, sizeof(buf))` can return -1 (error) or 0 (EOF). Neither is checked. The loop `for (int j = 0; j < count; j++)` simply does not execute when `count <= 0`, and the program continues the `while(1)` loop. On EOF, `select()` keeps returning `stdin_fd` as ready (EOF is a level-triggered persistent condition), `read()` keeps returning 0, and the program busy-loops at 100% CPU forever. On read error, the error is silently swallowed. The server-socket read at lines 229-233 correctly checks `count <= 0`; the stdin read does not, creating an asymmetry that is a real bug.
- **Fix:** Check `count <= 0` after the stdin read, mirroring the server-socket path. On EOF, exit cleanly; on error, report and exit:
  ```c
  ssize_t count = read(stdin_fd, buf, sizeof(buf));
  if (count <= 0) {
      printf("Input closed\n");
      exit(0);
  }
  ```

### [MEDIUM] setRawMode() return value ignored
- **Type:** invariant-false
- **Trigger:** Silent error swallowing (anti-pattern)
- **Location:** smallchat-client.c:204
- **Issue:** `setRawMode()` returns -1 on failure (non-tty fd, `tcgetattr`/`tcsetattr` failure), but `main()` ignores the return value. If raw mode setup fails — e.g., stdin is a pipe, not a terminal — the program continues with the terminal in cooked mode. Input handling is then broken: line buffering, local echo, and canonical processing all produce wrong behavior. The user sees garbage with no error message explaining why.
- **Fix:** Check the return value; on failure, print an error and exit:
  ```c
  if (setRawMode(fileno(stdin), 1) == -1) {
      perror("setRawMode");
      exit(1);
  }
  ```

### [MEDIUM] write() to server socket unchecked; user messages silently lost
- **Type:** invariant-false
- **Trigger:** Silent error swallowing (anti-pattern)
- **Location:** smallchat-client.c:248
- **Issue:** `write(s, ib.buf, ib.len)` sends the user's message to the server. The return value is not checked. If the write fails — e.g., the connection broke between the last successful read and this write — the message is silently lost. The user sees their message echoed locally (line 247) but it was never delivered. The breakage is only detected on the next `read` from the server, which may be much later. The user has no way to know their message was dropped.
- **Fix:** Check the write return value; on failure, report and exit, same as the read path:
  ```c
  if (write(s, ib.buf, ib.len) < 0) {
      perror("send");
      exit(1);
  }
  ```

### [LOW] Dead code after infinite loop
- **Type:** guideline
- **Trigger:** Dead or unused code paths retained "just in case"
- **Location:** smallchat-client.c:259-260
- **Issue:** `close(s)` and `return 0` are unreachable. The `while(1)` loop only exits via `exit(1)` calls (lines 223, 232). This code can never execute. Dead code confuses readers into thinking there is a clean shutdown path when there is not.
- **Fix:** Remove the dead code, or restructure the loop with a proper exit condition so resources are released on shutdown.

### [LOW] Misleading comment contradicts the code
- **Type:** invariant-false
- **Trigger:** Comment that does not match the code's actual behavior
- **Location:** smallchat-client.c:61
- **Issue:** The comment says "Don't even check the return value as it's too late." But line 62 does check the return value: `tcsetattr(fd, TCSAFLUSH, &orig_termios) != -1`. The condition uses the return value to decide whether to reset `rawmode_is_set`. The comment actively misleads a reader into thinking the return is ignored when it is not.
- **Fix:** Fix the comment to match the code, or remove it. The code is self-explanatory without it.

### [LOW] errno overwritten with ENOTTY regardless of actual failure
- **Type:** invariant-false
- **Trigger:** Error or diagnostic message that does not accurately describe the condition
- **Location:** smallchat-client.c:97
- **Issue:** The `fatal:` label sets `errno = ENOTTY` unconditionally. But `fatal` is reached from three different failure points: `!isatty(fd)` (line 68, where ENOTTY is correct), `tcgetattr` failure (line 73), and `tcsetattr` failure (line 92). For the latter two, the syscall already set `errno` to the actual error (e.g., EBADF, EACCES), and the unconditional `errno = ENOTTY` overwrites it with the wrong value. A caller checking `errno` after `setRawMode` returns -1 gets misleading information.
- **Fix:** Only set `errno = ENOTTY` for the `!isatty` case. For the `tcgetattr`/`tcsetattr` failures, let the syscall's `errno` propagate:
  ```c
  if (!isatty(fd)) { errno = ENOTTY; return -1; }
  ```
  Remove the `goto fatal` pattern or give each failure path its own error handling.

### chatlib.c

# Review: chatlib.c

Skill applied: linus-torvalds-skill (SKILL-GLM.md)
Source: /tmp/smallchat/chatlib.c

---

### [HIGH] Allocators abort the process on out-of-memory
- **Type:** invariant-false
- **Trigger:** Error handling that aborts or traps on a recoverable condition instead of returning an error
- **Location:** chatlib.c:136-143 (chatMalloc), chatlib.c:146-153 (chatRealloc)
- **Issue:** `chatMalloc` and `chatRealloc` call `exit(1)` when `malloc`/`realloc` returns NULL. Out-of-memory is a recoverable condition: the caller could free other memory, retry, degrade gracefully, or propagate the error upward. Aborting removes the caller's ability to handle the error and makes the entire system fragile. The comment attempts to justify this ("trying to recover from out of memory is often futile"), but the skill explicitly rejects this reasoning — the reference example is about allocators that abort on OOM being called "complete and utter idiocy" and "NOT ACCEPTABLE." A module named `chatlib` is a library; a library that aborts on recoverable conditions dictates policy to every caller and makes the whole program fragile.
- **Fix:** Return NULL on allocation failure instead of calling `exit(1)`. Let callers decide how to handle OOM. If the application layer wants a crash-on-OOM policy, implement it there, not in the allocator.

---

### [MEDIUM] TCPConnect leaks addrinfo on non-blocking connect path
- **Type:** invariant-false
- **Trigger:** Every allocated resource must have a clear owner, a defined lifetime, and a correct release path (Memory Safety and Resource Management)
- **Location:** chatlib.c:94
- **Issue:** When `connect()` returns -1 with `errno == EINPROGRESS` and `nonblock` is set, the function returns `s` immediately without calling `freeaddrinfo(servinfo)`. The `servinfo` linked list was allocated by `getaddrinfo` on line 75 and is only freed on line 107, which this return path bypasses. Every non-blocking connect attempt leaks the addrinfo structure. For a long-running process making repeated connections, this is an unbounded memory leak.
- **Fix:** Call `freeaddrinfo(servinfo)` before returning `s`:
  ```c
  if (errno == EINPROGRESS && nonblock) {
      freeaddrinfo(servinfo);
      return s;
  }
  ```

### chatlib.h

# Skill Review: chatlib.h

**Skill:** linus-torvalds-skill (SKILL-GLM.md)
**Source:** `/tmp/smallchat/chatlib.h`
**Reviewer:** glm5.2

---

### [MEDIUM] Header not self-contained — `size_t` used without `<stddef.h>`
- **Type:** invariant-false
- **Trigger:** "Code is binary — it works or it doesn't." (Reviewer Mindset #2)
- **Location:** chatlib.h:11-12
- **Issue:** The header uses `size_t` in `chatMalloc` and `chatRealloc` but does not include `<stddef.h>` (or any header defining `size_t`). A header must compile standalone when included first. Including `chatlib.h` before any standard header that transitively defines `size_t` produces a compilation failure. The header's correctness depends on include order — that is a latent bug.
- **Fix:** Add `#include <stddef.h>` immediately after the include guard.

### [MEDIUM] `TCPConnect` parameter `addr` should be `const char *`
- **Type:** invariant-false
- **Trigger:** Internal implementation details exposed through a public interface — the interface contract implies mutability the function should not have.
- **Location:** chatlib.h:8
- **Issue:** `TCPConnect(char *addr, ...)` takes a non-const pointer to the address string. A connect operation has no reason to modify the caller's buffer. The non-const signature (a) implies the function may write through `addr`, which is false and misleading; (b) prevents callers from passing string literals or `const char *` data without a cast; (c) is deprecated for string literals in C99+. The interface is wrong — it advertises a capability (mutation) the function does not need.
- **Fix:** Change the parameter to `const char *addr`.

### [LOW] `nonblock` boolean flag should be a discriminated type
- **Type:** guideline
- **Trigger:** Prefer discriminated types over boolean flags to self-document intent.
- **Location:** chatlib.h:8
- **Issue:** `TCPConnect(char *addr, int port, int nonblock)` uses a bare `int` as a boolean. At a call site, `TCPConnect(addr, 8080, 1)` does not convey whether `1` means blocking or non-blocking. A reader must look up the declaration. An enum or named constant would make the call self-documenting.
- **Fix:** Replace with an enum, e.g. `enum connect_mode { CONN_BLOCKING, CONN_NONBLOCKING }`, or at minimum a named constant with a comment.

### [LOW] Inconsistent naming convention across the API surface
- **Type:** guideline
- **Trigger:** Enforce consistent naming, indentation, and formatting per project conventions.
- **Location:** chatlib.h:5-8
- **Issue:** The function names mix conventions: `TCPConnect` (PascalCase acronym prefix) alongside `createTCPServer`, `acceptClient`, `socketSetNonBlockNoDelay` (camelCase). A caller scanning the API cannot predict the naming pattern, which makes the surface harder to navigate. `TCPConnect` also breaks the verb-first pattern (`create`, `accept`, `connect`) by leading with the noun `TCP`.
- **Fix:** Pick one convention — camelCase with verb-first names — and rename `TCPConnect` to `connectTCP` or `tcpConnect` to match `createTCPServer` and `acceptClient`.

### Makefile

# Review: Makefile

Source: `/tmp/smallchat/Makefile`
Skill: `linus-torvalds-skill/SKILL-GLM.md`

---

### [HIGH] Missing header dependency: `chatlib.h` not tracked as a prerequisite

- **Type:** invariant-false
- **Trigger:** Function returns a value that is ambiguous between success and failure
- **Location:** Makefile:4-5, Makefile:7-8
- **Issue:** Both `smallchat-server.c` and `smallchat-client.c` include `chatlib.h` (smallchat-server.c:38, smallchat-client.c:40), but the build rules list only the `.c` files as prerequisites:
  ```makefile
  smallchat-server: smallchat-server.c chatlib.c
  smallchat-client: smallchat-client.c chatlib.c
  ```
  Editing `chatlib.h` does not trigger a recompile. `make` reports "nothing to do" and exits 0, but the binaries are stale — compiled against the old header. The build system returns success for a build that is silently incorrect. A developer debugging sees behavior that doesn't match the source because the binary was built from a previous version of the header.
- **Fix:** Add `chatlib.h` to the prerequisite list of both targets:
  ```makefile
  smallchat-server: smallchat-server.c chatlib.c chatlib.h
  smallchat-client: smallchat-client.c chatlib.c chatlib.h
  ```

---

### [MEDIUM] Phony targets `all` and `clean` not declared with `.PHONY`

- **Type:** invariant-false
- **Trigger:** Function returns a value that is ambiguous between success and failure
- **Location:** Makefile:1, Makefile:10
- **Issue:** `all` and `clean` are phony targets — they do not produce files named `all` or `clean`. Without a `.PHONY` declaration, Make checks whether a file named `all` or `clean` exists in the directory. If one does (a test artifact, a backup, an accidental `touch clean`), Make considers the target up-to-date and does nothing. `make clean` exits 0 without cleaning. `make all` exits 0 without building. The return value is ambiguous between "did the work" and "skipped because a file matched."
- **Fix:** Add `.PHONY` at the top of the file:
  ```makefile
  .PHONY: all clean
  ```

