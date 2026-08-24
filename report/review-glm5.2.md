---\ntitle: "SmallChat Review Summary — Linus Torvalds Skill (GLM5.2)"\ndate: 2026-08-24\nmodel: glm5.2\nskill: linus-torvalds-skill/SKILL-GLM.md\nfiles_reviewed:\n  - smallchat-server.c\n  - smallchat-client.c\n  - chatlib.c\n  - chatlib.h\n  - Makefile\nfindings_count: 24\nseverity_breakdown:\n  critical: 2\n  high: 6\n  medium: 9\n  low: 7\nverdict: request-changes\n---\n\n## Persona Narrative\n\nThe skill reads like Torvalds on a bad patch day: impatient, precise, and unwilling to confuse effort with correctness. It does not soften. The opening line of the server review sets the tone — "code either works or it doesn't" — and then it proves the code doesn't, by tracing two memory-corruption paths that fire under normal load. The voice is consistent across files: it states the failure mode, names the root cause, and gives the fix in the same breath. No hedging, no "you might consider." The BUG_ON quote lands where it belongs — applied to an `assert()` that vanishes under `NDEBUG` — and it hits harder for being verbatim rather than paraphrased.\n\nWhat feels distinctly Torvalds is the refusal to let recoverable conditions masquerade as fatal ones. The skill returns to this theme five times across two files: `select()` EINTR, `read()` EINTR, the `assert()` on a duplicate fd, `exit(1)` on OOM in a support module, `exit(1)` on select failure. Each time it makes the same structural argument — the error is real, the response is wrong, and the crash is self-inflicted. That repetition is not noise; it is the skill identifying a systemic habit in the codebase rather than scoring individual points. A weaker reviewer would have flagged one EINTR and moved on. This one tracks the pattern across the process boundary.\n\nThe discipline shows in the small things too. Every finding carries a type label (`invariant-false`, `guideline`) and a named trigger. The precedence hierarchy (Correctness > Performance > Complexity > Style) is cited where it governs a severity call, not pasted decoratively. Naming and style findings sit at LOW, where they belong, below the memory-safety and error-handling findings that actually break the program. The skill knows what matters and spends its words there.\n\n## Technical Assessment\n\n**Coverage.** The review covered all five files in the SmallChat tree and hit every category the skill defines: memory safety, error handling, resource management, fatal-vs-recoverable, naming, and build correctness. The systemic defect — unchecked or mishandled syscall returns (`accept`, `select`, `read`, `write`, `socketSetNonBlockNoDelay`) — was identified as a theme rather than a list of unrelated bugs. The Makefile review extended the method beyond source code into the build system, correctly classifying a missing header prerequisite as a correctness bug (stale binaries lie about what they contain).\n\n**Accuracy.** Findings are technically sound. The two CRITICALs are real: indexing `Chat->clients[fd]` and `FD_SET(fd, &readfds)` without bounds checks corrupts the heap and stack once `accept()` hands out fd ≥ 1000 / ≥ 1024 — a condition reached by load, not malice. The `freeaddrinfo` leak in `TCPConnect` is on the primary non-blocking connect path, not an edge case. The EINTR findings are textbook-correct. The `snprintf`-as-length finding is correctly classified as latent rather than active. No fabricated bugs, no misread code.\n\n**Severity calibration.** Well-judged. The two CRITICALs are the only findings that corrupt memory unprovoked; the HIGHs crash the server or leak on the hot path; the MEDIUMs silently lose data or freeze the event loop; the LOWs are latent or cosmetic. The one debatable call is the Makefile missing-header finding at HIGH — it has no runtime impact, so MEDIUM would also be defensible — but the skill's own definition of "bug" ("code either works or it doesn't") makes a build that lies about freshness a correctness failure, so HIGH is internally consistent.\n\n**Precedence adherence.** Correctness dominated. Every CRITICAL and HIGH is a correctness or error-handling failure. No performance, complexity, or style finding was promoted above a correctness finding. Style findings (naming, dead code, magic numbers) sat at LOW. The hierarchy was applied, not just cited.\n\n## Strengths\n\n- Identified the unchecked-syscall-return pattern as a systemic defect across files, not isolated bugs — the EINTR theme spans server and client and shows the skill reading the codebase, not just the file.\n- Labeled every finding with type and trigger per the skill specification, making the review machine-parseable and self-auditing.\n- Quoted Torvalds verbatim where the quote governed the call (the BUG_ON quote on the vanishing `assert`), and paraphrased elsewhere — quotes used as evidence, not decoration.\n- Correctly classified the `snprintf` finding as latent, not active — resisted inflating severity for a bug that cannot fire under the current format string.\n- Extended the method to the build system: a Makefile that ships stale binaries is a correctness bug, and the review said so.\n\n## Weaknesses\n\n- Some LOW findings (magic number 127, dead `close(s)`/`return 0`, duplicated Makefile rules) are true but low-value; they dilute a review whose force comes from the CRITICALs and HIGHs.\n- The chatlib.h "inconsistent naming convention" finding is subjective and stylistic — calling it a finding at all stretches the skill's "code either works or it doesn't" standard into taste territory.\n- No finding on the single-threaded `select()` architecture itself — the review stayed tactical (EINTR, bounds) and never asked whether `select()` with a 1000-fd ceiling is the right shape for the problem. The skill is language-agnostic, but scalability is a correctness-under-load question.\n- The `exit()`-on-OOM finding in `chatlib.c` is argued well but the fix ("return NULL and let callers decide") understates that every caller would then need NULL checks the codebase has no pattern for — the fix is right, the migration cost is unmentioned.\n\n## Verdict\n\nNot production-ready. Two CRITICAL memory-safety bugs corrupt the heap and stack under normal load; six HIGHs crash the server on routine signals or leak on the primary connect path. Fix the CRITICALs and HIGHs before any deployment — the LOWs can wait.\n
## Findings

### smallchat-server.c

---
model: glm5.2
skill: linus-torvalds-skill/SKILL-GLM.md
source: smallchat-server.c
reviewer: skill-applied
---

# Review: smallchat-server.c

Reviewed against the Linus Torvalds review method (SKILL-GLM.md). Findings ordered by severity.

---

### [CRITICAL] No bounds check on file descriptor before array and fd_set indexing

- **Type:** invariant-false
- **Trigger:** Memory Safety — shared object accessed without bounds enforcement; correctness priority (Correctness > Performance > Complexity > Style)
- **Location:** smallchat-server.c:85-88, 166
- **Issue:** `createClient()` writes `Chat->clients[c->fd] = c` (line 86) and `main()` calls `FD_SET(j, &readfds)` (line 166) without ever checking `fd < MAX_CLIENTS` (1000) or `fd < FD_SETSIZE` (typically 1024). The `clients` array has 1000 slots; `fd_set` has 1024 bits. Once the server accepts enough connections that `accept()` returns fd >= 1000, `Chat->clients[fd]` writes past the end of the array — heap corruption. Once fd >= 1024, `FD_SET` writes past the `fd_set` bitfield — stack corruption. The comment on `MAX_CLIENTS` ("This is actually the higher file descriptor") acknowledges the intent but the code never enforces it. This is a buffer overflow triggered by normal operation under load.
- **Fix:** In `createClient()`, before indexing, check `if (fd < 0 || fd >= MAX_CLIENTS) { close(fd); free(c); return NULL; }`. In `main()`, check the return of `createClient()` and handle NULL. Also reject fds >= `FD_SETSIZE` since `select()` cannot handle them. Log and close the excess connection rather than corrupting memory.

---

### [CRITICAL] acceptClient() return value not checked before use

- **Type:** invariant-false
- **Trigger:** Error handling that masks the root cause — error return value consumed without validation
- **Location:** smallchat-server.c:188-189
- **Issue:** `int fd = acceptClient(Chat->serversock);` is passed directly to `createClient(fd)` with no check for -1 (the standard failure return for accept wrappers). If `acceptClient` returns -1, `createClient(-1)` executes: `socketSetNonBlockNoDelay(-1)` operates on an invalid descriptor, then `Chat->clients[-1]` is an out-of-bounds array access — both read (the assert) and write (`= c`). This is a memory-safety bug on any accept failure (EMFILE when out of file descriptors, EINTR, ECONNABORTED).
- **Fix:** `int fd = acceptClient(Chat->serversock); if (fd < 0) { perror("accept"); continue; }` before calling `createClient`.

---

### [HIGH] Fatal assertion used for a recoverable condition

- **Type:** invariant-false
- **Trigger:** Fatal assertion or abort used for a recoverable condition
- **Location:** smallchat-server.c:85
- **Issue:** `assert(Chat->clients[c->fd] == NULL)` aborts the entire server if the slot is already occupied. A duplicate fd is a recoverable condition — the function could return NULL and the caller closes the fd and continues. Worse, with `NDEBUG` defined (standard for release builds), the assert compiles to nothing, so the check vanishes entirely and the duplicate silently overwrites the existing client pointer, leaking it. This is the exact pattern the skill calls out: "Either that BUG_ON() cannot possibly happen, in which case it should damn well not exist in the first place. Or it's a valuable debug aid, in which case it should damn well not be a BUG_ON. You can't have it both ways."
- **Fix:** Replace the assert with a runtime check: `if (Chat->clients[c->fd] != NULL) { free(c->nick); free(c); return NULL; }`. Have the caller handle NULL.

---

### [HIGH] exit(1) on select() failure kills the server on any signal

- **Type:** invariant-false
- **Trigger:** Fatal assertion or abort used for a recoverable condition
- **Location:** smallchat-server.c:180-182
- **Issue:** `if (retval == -1) { perror("select() error"); exit(1); }` — `select()` returns -1 with `errno == EINTR` when interrupted by a signal. This is fully recoverable: the correct response is to continue the loop. Instead, any signal delivery (SIGCHLD from a child process, terminal resize, etc.) kills the server and disconnects every client. EINTR is not an error; it is a normal event.
- **Fix:** `if (retval == -1) { if (errno == EINTR) continue; perror("select() error"); exit(1); }`

---

### [MEDIUM] read() EINTR treated as client disconnect

- **Type:** invariant-false
- **Trigger:** Error handling that masks the root cause
- **Location:** smallchat-server.c:209-216
- **Issue:** `int nread = read(j, readbuf, sizeof(readbuf)-1); if (nread <= 0) { ... freeClient(...); }` — `read()` returns -1 with `errno == EINTR` when interrupted by a signal. The code treats this identically to EOF (nread == 0) and disconnects the client. A signal during a read kicks the user out of the chat for no reason. The root cause (signal interruption) is masked as a disconnect.
- **Fix:** `if (nread == -1 && errno == EINTR) continue;` before the `nread <= 0` check.

---

### [MEDIUM] write() return values silently discarded

- **Type:** invariant-false
- **Trigger:** Error handling that masks the root cause / Anti-pattern: Silent error swallowing
- **Location:** smallchat-server.c:143, 194, 248
- **Issue:** Every `write()` call ignores the return value. In `sendMsgToAllClientsBut` (line 143) the comment acknowledges this ("If the content does not fit, we don't care"), but the welcome message (line 194) and error message (line 248) have no such acknowledgment. A failed or short write silently loses data. On a blocking socket (see next finding), a failed write could also block the server indefinitely. The anti-pattern is explicit in the skill: "Catching an error and continuing without logging, returning, or handling it."
- **Fix:** At minimum, check the return value and log short writes. For the fan-out path, a short write means the client's kernel buffer is full — the correct response is to either buffer the remainder or disconnect the slow client, not silently drop the message.

---

### [MEDIUM] socketSetNonBlockNoDelay() failure ignored — "Pretend this will not fail"

- **Type:** invariant-false
- **Trigger:** Error handling that masks the root cause
- **Location:** smallchat-server.c:81
- **Issue:** The comment "Pretend this will not fail" admits the error is swallowed. If `socketSetNonBlockNoDelay(fd)` fails, the socket remains in blocking mode. The entire server architecture is built on `select()` + non-blocking reads — a blocking socket in the set causes `read()` to block the single-threaded event loop, freezing the server for all clients. The failure mode is silent and catastrophic.
- **Fix:** Check the return value. If it fails, close the fd, free the client, and return NULL from `createClient()`. Do not admit a client whose socket is in the wrong mode.

---

### [LOW] snprintf return value used as memcpy length without truncation check

- **Type:** invariant-false
- **Trigger:** Error return value that is indistinguishable from a successful return (latent)
- **Location:** smallchat-server.c:79, 83-84
- **Issue:** `int nicklen = snprintf(nick, sizeof(nick), "user:%d", fd);` — `snprintf` returns the number of characters that *would* have been written, which can exceed `sizeof(nick)` if the output is truncated. The code then does `chatMalloc(nicklen+1)` and `memcpy(c->nick, nick, nicklen)` — if truncated, `nicklen > sizeof(nick)`, so `memcpy` reads past the end of the `nick[32]` stack buffer. With the current format string (`"user:%d"`, max ~15 chars for a 32-bit int) truncation cannot occur, so this is a latent bug, not an active one. But the pattern is wrong: any future change to the format string that could exceed 31 chars introduces a stack buffer over-read with no warning.
- **Fix:** `if (nicklen >= (int)sizeof(nick)) nicklen = sizeof(nick)-1;` after the `snprintf` call, before using `nicklen` as a length.

---

## Summary

8 findings: 2 CRITICAL, 2 HIGH, 3 MEDIUM, 1 LOW.

The two CRITICAL findings are both memory-safety bugs: missing bounds checks that cause out-of-bounds writes during normal operation under load. Either can corrupt the heap or stack. The HIGH findings are error-handling failures that crash the server or vanish safety checks in production builds. The MEDIUM findings silently lose data or freeze the server. The LOW finding is a latent buffer over-read.

The core issue is that error returns from system calls (`accept`, `select`, `read`, `write`, `socketSetNonBlockNoDelay`) are either unchecked or mishandled. The skill's principle is direct: "code either works or it doesn't." This code doesn't — it corrupts memory on load and crashes on signals.

### smallchat-client.c

# Review: smallchat-client.c

**Reviewer:** Linus Torvalds skill (GLM5.2)
**File:** `/tmp/smallchat/smallchat-client.c`
**Lines reviewed:** 1–261

---

### [HIGH] select() exits on EINTR — suspend/resume kills the client

- **Type:** invariant-false
- **Trigger:** Fatal assertion or abort used for a recoverable condition
- **Location:** smallchat-client.c:220–223
- **Issue:** `select()` returns -1 with `errno == EINTR` when interrupted by a signal. The code treats this as a fatal error and calls `exit(1)`. Raw mode leaves ISIG enabled (line 86 comment: "take signal chars (^Z,^C) enabled"), so `^Z` (SIGTSTP) stops the process. When the user resumes with `fg`, select returns EINTR and the client prints "select() error" and dies. A user pressing `^Z` then `fg` — a routine operation — loses their chat session. EINTR is recoverable: the correct response is to retry the select.
- **Fix:** Check for EINTR explicitly and continue the loop:
  ```c
  if (num_events == -1) {
      if (errno == EINTR) continue;
      perror("select() error");
      exit(1);
  }
  ```

---

### [HIGH] read() from server treats EINTR as "Connection lost"

- **Type:** invariant-false
- **Trigger:** Error handling that masks the root cause
- **Location:** smallchat-client.c:229–233
- **Issue:** `read(s, buf, sizeof(buf))` returns -1 on signal interruption (EINTR). The code checks `count <= 0`, prints "Connection lost", and exits. The connection is not lost — the read was interrupted. The user sees a misleading message and loses their session for a non-existent failure. The root cause (signal interruption) is masked as a connection failure.
- **Fix:** Distinguish error from clean EOF, and retry on EINTR:
  ```c
  ssize_t count = read(s, buf, sizeof(buf));
  if (count == -1 && errno == EINTR) continue;
  if (count <= 0) {
      printf("Connection lost\n");
      exit(1);
  }
  ```

---

### [MEDIUM] setRawMode overwrites real errno with ENOTTY

- **Type:** invariant-false
- **Trigger:** Error handling that masks the root cause
- **Location:** smallchat-client.c:96–98
- **Issue:** The `fatal:` label unconditionally sets `errno = ENOTTY`. If the failure came from `tcgetattr` (line 73) or `tcsetattr` (line 92), those functions already set errno to the real error (EBADF, EIO, etc.). Overwriting with ENOTTY destroys the diagnostic. The caller calling `perror` or logging errno sees "Not a tty" regardless of the actual failure, sending debugging in the wrong direction. The ENOTTY assignment is only correct for the `!isatty(fd)` path; for the tcgetattr/tcsetattr paths it is wrong.
- **Fix:** Set `errno = ENOTTY` only before the `isatty` check, or remove it entirely and let the system call's errno propagate:
  ```c
  if (!isatty(fd)) { errno = ENOTTY; return -1; }
  if (!atexit_registered) { ... }
  if (tcgetattr(fd, &orig_termios) == -1) return -1;
  ...
  if (tcsetattr(fd, TCSAFLUSH, &raw) < 0) return -1;
  ```

---

### [MEDIUM] read() from stdin ignores error return

- **Type:** invariant-false
- **Trigger:** Error handling that masks the root cause
- **Location:** smallchat-client.c:239–240
- **Issue:** `read(stdin_fd, buf, sizeof(buf))` does not check for -1. On error, `count` is -1 (ssize_t, signed). The loop `for (int j = 0; j < count; j++)` evaluates `0 < -1` as false, so the loop body is silently skipped. The error is swallowed with no log, no recovery, no exit. This is also inconsistent with the server read path (line 229–233), which at least checks `count <= 0`. Two read paths in the same function handle errors differently — one checks, one doesn't.
- **Fix:** Check the return value before entering the loop:
  ```c
  ssize_t count = read(stdin_fd, buf, sizeof(buf));
  if (count <= 0) {
      if (count == -1 && errno == EINTR) continue;
      perror("read(stdin)");
      exit(1);
  }
  for (int j = 0; j < count; j++) { ... }
  ```

---

### [LOW] close(s) and return 0 are dead code

- **Type:** guideline
- **Trigger:** Dead or unused code paths retained
- **Location:** smallchat-client.c:259–260
- **Issue:** The main loop is `while(1)` with no `break` statement. Every exit path goes through `exit(1)` (lines 191, 198, 223, 232). The `close(s)` on line 259 and `return 0` on line 260 are unreachable. Dead code misleads readers into thinking the loop can terminate normally and that the socket is cleaned up on normal exit — it isn't.
- **Fix:** Remove the unreachable lines, or restructure the loop to `break` on clean disconnection so the cleanup path is actually reached.

---

### [LOW] Magic number 127 for backspace

- **Type:** invariant-false
- **Trigger:** Hard-coded constants or hardware-specific values
- **Location:** smallchat-client.c:151
- **Issue:** `case 127:` uses a bare numeric constant for the ASCII DEL character (used as backspace by most terminals). The value 127 has no name and no comment explaining what it represents. A reader unfamiliar with ASCII codes cannot verify correctness. The rest of the function uses character literals (`'\n'`, `'\r'`) — this one case breaks the pattern.
- **Fix:** Use a named constant or character literal:
  ```c
  #define BACKSPACE 127
  ...
  case BACKSPACE:
  ```
  or use `'\b'` (0x08) if that is the intended character, with a comment noting which terminal convention is being followed.

### chatlib.c

---
file: chatlib.c
reviewer_skill: linus-torvalds-skill (SKILL-GLM.md)
model: glm5.2
---

# Review: chatlib.c

### [HIGH] Memory leak in TCPConnect on non-blocking connect success path
- **Type:** invariant-false
- **Trigger:** Resource management — early return skips cleanup (non-exhaustive catalog: "The triggers listed above are a starting set, not a ceiling. The reviewer must still apply general code-review judgment.")
- **Location:** chatlib.c:94
- **Issue:** `getaddrinfo` allocates a linked list at line 75. The normal success path for a non-blocking connect is `errno == EINPROGRESS`, which hits `return s;` at line 94 — this exits the function without calling `freeaddrinfo(servinfo)` at line 107. Every non-blocking connect leaks the entire addrinfo list. This is not an edge case; it is the primary code path for `nonblock != 0`.
- **Fix:** Replace `return s;` with `retval = s; break;` so the function falls through to the single `freeaddrinfo(servinfo)` at line 107. One exit point, no leak:
  ```c
  if (errno == EINPROGRESS && nonblock) {
      retval = s;
      break;
  }
  ```

### [MEDIUM] exit() on OOM removes caller control in a support module
- **Type:** invariant-false
- **Trigger:** Fatal assertion or abort used for a recoverable condition (Error Handling theme)
- **Location:** chatlib.c:140, chatlib.c:150
- **Issue:** `chatMalloc` and `chatRealloc` call `exit(1)` on allocation failure. The comment argues OOM recovery is "often futile" for long-running programs — but it also says this pattern is for programs "that are not libraries." `chatlib.c` is structured as a library (support module linked into the server). `exit()` here prevents the caller from degrading gracefully: a chat server could drop the connection that triggered the allocation rather than killing the whole process. The comment's own justification contradicts the file's role.
- **Fix:** Return `NULL` on failure and let callers decide. If exit-on-OOM is the deliberate program-level policy, enforce it in the main program, not in an allocator that every module transitively depends on.

### [LOW] Missing const on TCPConnect addr parameter
- **Type:** guideline
- **Trigger:** Names that don't describe what the code does (Naming, Style, and Readability theme)
- **Location:** chatlib.c:65
- **Issue:** `char *addr` should be `const char *addr`. The function does not modify the string. The missing `const` signals to callers that it might, and prevents passing string literals under strict compilation flags.
- **Fix:** Change the signature to `int TCPConnect(const char *addr, int port, int nonblock)`.

### chatlib.h

# Review: chatlib.h

Skill: linus-torvalds-skill/SKILL-GLM.md
Source: /tmp/smallchat/chatlib.h

---

### [MEDIUM] Missing `const` qualifier on read-only string parameter
- **Type:** invariant-false
- **Trigger:** General code-review judgment (skill triggers are non-exhaustive; closest to "Internal implementation details exposed through a public interface")
- **Location:** chatlib.h:8
- **Issue:** `TCPConnect(char *addr, ...)` declares `addr` as `char *` without `const`. The function consumes an address string and should not modify it. Without `const`, the API implies mutation that likely does not occur, and prevents callers from passing string literals safely — in C11, assigning a string literal (`const char *`) to `char *` is a constraint violation. The signature lies about the function's behavior.
- **Fix:** Change the declaration to `int TCPConnect(const char *addr, int port, int nonblock);`

### [MEDIUM] Return values and error semantics are undocumented
- **Type:** guideline
- **Trigger:** Missing documentation for non-trivial behavior
- **Location:** chatlib.h:5-12
- **Issue:** No function in this header documents its return value or error conditions. Callers cannot determine from the API what constitutes success or failure: Does `createTCPServer` return a file descriptor or -1? Does `socketSetNonBlockNoDelay` return 0 on success and -1 on error? Does `chatMalloc` return NULL on failure or abort? The error semantics of every function are non-trivial and must be documented in the public header.
- **Fix:** Document each function's return value, error conditions, and error return values. For `chatMalloc`/`chatRealloc`, state explicitly whether they abort on failure or return NULL. For `chatRealloc`, document whether standard `realloc` semantics apply (NULL ptr = malloc, failure returns NULL but original block is preserved).

### [LOW] Inconsistent function naming convention
- **Type:** guideline
- **Trigger:** Inconsistent naming across similar entities
- **Location:** chatlib.h:5-12
- **Issue:** Functions in the same header follow different naming patterns: some lead with a verb (`createTCPServer`, `acceptClient`), others lead with a noun prefix (`socketSetNonBlockNoDelay`, `TCPConnect`, `chatMalloc`, `chatRealloc`). The prefix itself varies (`socket`, `TCP`, `chat`). There is no consistent namespace or verb-noun convention. `TCPConnect` capitalizes the acronym at the start while `createTCPServer` embeds it mid-name.
- **Fix:** Pick one convention — either verb-first (`connectTCP`, `createServer`, `acceptClient`) or namespace-prefixed (`chatConnect`, `chatCreateServer`, `chatAccept`) — and apply it uniformly.

### [LOW] Inconsistent parameter naming: snake_case mixed with camelCase
- **Type:** guideline
- **Trigger:** Inconsistent naming across similar entities
- **Location:** chatlib.h:7
- **Issue:** `acceptClient(int server_socket)` uses snake_case for the parameter name, while every other parameter in the header uses lowercase or camelCase (`port`, `fd`, `addr`, `nonblock`). The inconsistency forces readers to remember per-parameter conventions.
- **Fix:** Rename to `serverSocket` (or `server_fd`) to match the camelCase convention used by the rest of the header.

### Makefile

---
reviewer: glm5.2
skill: linus-torvalds-skill/SKILL-GLM.md
file: Makefile
verdict: request-changes
---

# Review: Makefile

## Findings

### [HIGH] Header file not listed as a build prerequisite — stale binaries
- **Type:** invariant-false
- **Trigger:** Correctness invariant — "code either works or it doesn't" (Key Definitions: Bug). The build must produce binaries that reflect the current sources; a build that claims "nothing to do" while sources have changed is lying.
- **Location:** Makefile:4-8
- **Issue:** `chatlib.h` is `#include`d by `smallchat-server.c`, `smallchat-client.c`, and `chatlib.c` (verified), yet no target lists it as a prerequisite. Editing the header and running `make` prints "up to date" and ships a stale binary. This is a silent correctness bug in the build system — the kind that wastes hours because the developer debugs the wrong code.
- **Fix:** Add `chatlib.h` to every target that compiles a source which includes it:

  ```makefile
  smallchat-server: smallchat-server.c chatlib.c chatlib.h
  	$(CC) smallchat-server.c chatlib.c -o smallchat-server $(CFLAGS)

  smallchat-client: smallchat-client.c chatlib.c chatlib.h
  	$(CC) smallchat-client.c chatlib.c -o smallchat-client $(CFLAGS)
  ```

  For a project this shape, a pattern rule with a shared prerequisite is cleaner (see LOW finding).

### [MEDIUM] Phony targets not declared `.PHONY`
- **Type:** invariant-false
- **Trigger:** Correctness invariant — the build must do what its targets promise. `all` and `clean` are phony by intent but not by declaration.
- **Location:** Makefile:1,10
- **Issue:** `all` and `clean` produce no output file of that name. If a file named `all` or `clean` ever appears in the directory (common with stray output, test artifacts, or `touch clean`), `make all` / `make clean` silently do nothing. The build breaks with no error message.
- **Fix:** Declare phony targets explicitly:

  ```makefile
  .PHONY: all clean
  all: smallchat-server smallchat-client
  ```

### [LOW] Duplicated compile rules
- **Type:** guideline
- **Trigger:** Duplicated logic that should be factored into a shared helper.
- **Location:** Makefile:4-8
- **Issue:** The server and client rules are identical except for the source and output name. Two copies of the same logic will drift if one is edited and the other is forgotten.
- **Fix:** Collapse into a pattern rule so the compile command exists once:

  ```makefile
  smallchat-server smallchat-client: %: %.c chatlib.c chatlib.h
  	$(CC) $< chatlib.c -o $@ $(CFLAGS)
  ```

  This also fixes the header prerequisite from the HIGH finding for free.

