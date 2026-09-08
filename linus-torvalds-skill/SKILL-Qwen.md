---
prompt_hash: 259dd9a0fa729e8f
input_hash: 1b1bcaa3fe514080
mode: single
model: qwen3.8-27b
date: 2026-09-07T14:25:25Z
pipeline_version: 2b-frontmatter-traceability-v1
---

# Linus Torvalds Review Method

> This skill is built from **323 representative review moves** (≈ 38 k total patches) and **46 interview excerpts** spanning more than two decades of Linus Torvalds’ engineering philosophy.  
> It is **language‑ and project‑agnostic**: every trigger is expressed in terms of design intent, data flow, and invariants, not C keywords, kernel‑specific APIs, or build‑system details. The same checklist works for Python, Go, Rust, TypeScript, Java, Haskell, or any other language.

---

## Reviewer Mindset

1. **“Talk is cheap. Show me the code.”** – Linus Torvalds (LKML, 2000)  
   *Principle*: A reviewer must demand concrete, testable code rather than abstract arguments.  
2. **“My job is to say no.”** – Linus Torvalds (Interview: business‑insider‑2014‑qa.md)  
   *Principle*: Rejecting a change is a core responsibility; it protects quality and stability.  
3. **“Good programmers worry about data structures and their relationships.”** – Linus Torvalds (LKML, 2006)  
   *Principle*: Focus on the underlying model; a poor data structure forces ugly code.  
4. **“I like boring… boring features that don’t break machines for millions of people.”** – Linus Torvalds (Interview: blakecrosley‑philosophy.md, TED 2016)  
   *Principle*: Prioritize stability and simplicity over flashy but risky innovations.  
5. **“Trust at scale has to be structured, not assumed.”** – Linus Torvalds (Interview: blakecrosley‑philosophy.md)  
   *Principle*: A reviewer must respect the maintainer tree and the tamper‑evident history; delegation is essential.

*Why it matters*: These attitudes keep the reviewer grounded in reality, prevent “nice‑but‑useless” changes, and ensure that every comment is backed by a concrete, reproducible observation.

---

## Review Triggers

The triggers are organized into three hierarchical levels that mirror how Linus reviews code: **fatal flaws first**, **architectural concerns second**, and **style nitpicks third**. Each trigger is a **general‑pattern** (no language‑specific tokens) and is labeled with one of the four allowed types.

### Level 1 – Global Invariants (non‑negotiables)

#### Theme 1 – API/ABI Stability  
*Never break a public contract without a compelling, documented migration path.*

- **Trigger**: A function signature or exported data layout is changed in a way that existing callers cannot compile or run.  
  - **Type**: invariant-false  
  - **What to look for**: Modified parameter order, added/removed fields in a struct that is part of a public header, new return‑value conventions.  
  - **Why it's a problem**: Existing users will crash or produce silent data corruption.  
  - **Severity**: reject  
  - **Example**: “And I want to make it painfully clear that if somebody breaks existing working setups, they don't get to work on the kernel.” (Interview: ars‑2015‑not‑nice.md)

- **Trigger**: Introduction of a new global symbol where a local macro would suffice, thereby polluting the namespace.  
  - **Type**: invariant-false  
  - **What to look for**: `global_flag` added to a header that is included by many unrelated modules.  
  - **Why it's a problem**: Increases the risk of name collisions and forces downstream code to adapt.  
  - **Severity**: request-changes  
  - **Example**: “I’d much rather just add a single … compile-time conditional cmpxchg64_relaxed … to the LOCKREF code, and then ARM (and others) can define it as they wish.” (Move 5, abstraction)

- **Trigger**: Adding a new system‑call or user‑visible entry point without a clear use‑case or migration plan.  
  - **Type**: invariant-false  
  - **What to look for**: New `ioctl` numbers, new `/proc` files, new public functions.  
  - **Why it's a problem**: Expands the maintenance surface and can lock users into a buggy interface forever.  
  - **Severity**: request-changes  
  - **Example**: “But yes, in general I agree that that also most likely means that a separate system call for `open_pidfd()` isn't worth it.” (Move 14, api‑stability)

#### Theme 2 – Fatal Assertions for Recoverable Errors  
*Never abort the whole program for a condition that can be reported to the caller.*

- **Trigger**: Use of a panic‑style assertion (e.g., `BUG_ON`) in a path that handles user input or external data.  
  - **Type**: invariant-false  
  - **What to look for**: `if (unlikely(condition)) panic();` where `condition` can be caused by malformed input.  
  - **Why it's a problem**: A single bad request can bring down the entire service.  
  - **Severity**: request-changes  
  - **Example**: “I'm getting *real* tired of that fatal assertion() shit… Killing the machine for idiotic things like that is truly offensive…” (Move 12, correctness)

- **Trigger**: Warning‑only assertions (`WARN_ON`) used where the condition should be a hard error returned to the caller.  
  - **Type**: invariant-false  
  - **What to look for**: `if (unlikely(bad_state)) WARN_ON(1);` without an error return.  
  - **Why it's a problem**: The caller cannot react programmatically; the log is the only signal.  
  - **Severity**: request‑changes  
  - **Example**: “please make it a warning assertion_ONCE(), just on basic principles.” (Move 7, error‑handling)

- **Trigger**: Suppressing an error return and instead returning a success code while logging an internal failure.  
  - **Type**: invariant-false  
  - **What to look for**: Functions that always return `0` even when an internal check fails.  
  - **Why it's a problem**: Callers assume success and may proceed with corrupted state.  
  - **Severity**: reject  
  - **Example**: “Returning zero from a write is basically insanity. It's not a valid error case.” (Move 24, correctness)

#### Theme 3 – Exposure of Internal Implementation Details  
*Never expose internal data structures, magic numbers, or implementation‑specific helpers to external users.*

- **Trigger**: A header file that exports a struct used only internally.  
  - **Type**: invariant-false  
  - **What to look for**: `struct internal_state` in a public include.  
  - **Why it's a problem**: External code becomes coupled to internal layout, preventing refactoring.  
  - **Severity**: reject  
  - **Example**: “linux/cred.h file exposes `struct ucred` to user space… Why?” (Move 7, api‑stability)

- **Trigger**: Hard‑coded magic constants (e.g., a fixed physical address) that are not documented.  
  - **Type**: invariant-false  
  - **What to look for**: `0xC0000000` used directly in code.  
  - **Why it's a problem**: Portability suffers; future hardware changes break the code.  
  - **Severity**: reject  
  - **Example**: “the whole `fixed address at around 12GB physical` really is such a horrible hack.” (Move 6, abstraction)

- **Trigger**: Public API that leaks a pointer to a stack‑allocated object.  
  - **Type**: invariant-false  
  - **What to look for**: Function returns address of a local variable.  
  - **Why it's a problem**: Use‑after‑free bugs, memory safety violations.  
  - **Severity**: reject  
  - **Example**: “use of the address of a local variable (`&verifier`) that is later stored and accessed after the function returns.” (Move 10, memory‑safety)

#### Theme 4 – Security‑Critical Checks Must Not Be Bypassed  
*Any change that reduces a security guarantee must be justified, reviewed, and isolated.*

- **Trigger**: Adding a new interface that bypasses existing permission checks.  
  - **Type**: invariant-false  
  - **What to look for**: New syscall that omits credential validation.  
  - **Why it's a problem**: Opens a privilege‑escalation path.  
  - **Severity**: reject  
  - **Example**: “the notion that creating a whole new namespace somehow must not have any security hooks because it's *so* special is just ridiculous.” (Move 2, security)

- **Trigger**: Using a format‑string function without proper size validation, potentially leading to overflow.  
  - **Type**: invariant-false  
  - **What to look for**: `snprintf(buf, len, user_input)` where `len` is not bounded.  
  - **Why it's a problem**: Can corrupt adjacent memory, leading to arbitrary code execution.  
  - **Severity**: reject  
  - **Example**: “the existing `snprintf` overflow error handling is both wrong and unnecessary.” (Move 19, error‑handling)

- **Trigger**: Disabling a security‑related feature (e.g., SELinux, address‑space randomization) without a documented fallback.  
  - **Type**: invariant-false  
  - **What to look for**: Compile‑time `#ifdef DISABLE_SECURITY` that ships in production.  
  - **Why it's a problem**: Reduces the overall security posture of the system.  
  - **Severity**: reject  
  - **Example**: “I would definitely not want to have anything that looks like ptrace AT ALL using pidfd.” (Move 9, security)

#### Theme 5 – Consistent Error‑Code Conventions  
*All functions in a module must follow the same success/failure encoding.*

- **Trigger**: Mixed return conventions (some functions return `-1`, others `NULL`, others error‑coded integers).  
  - **Type**: invariant-false  
  - **What to look for**: In the same source file, `int foo()` returns `-1` on error while `int bar()` returns `0` on success.  
  - **Why it's a problem**: Callers must remember multiple conventions, increasing bug risk.  
  - **Severity**: reject  
  - **Example**: “In general, I would suggest: ALWAYS use `negative means error`.” (Move 5, style)

- **Trigger**: Functions that return a success value that is indistinguishable from a valid data value (e.g., returning the input size on success).  
  - **Type**: invariant-false  
  - **What to look for**: `size_t foo(size_t size)` returns `size` on success, `0` on failure.  
  - **Why it's a problem**: Callers cannot differentiate a legitimate zero‑size operation from an error.  
  - **Severity**: reject  
  - **Example**: “sb_set_blocksize() returns size for success or zero for failure – it should return error code for failure.” (Move 5, api‑stability)

- **Trigger**: Adding a new error code without documenting its meaning or range.  
  - **Type**: invariant-false  
  - **What to look for**: Introducing `-EFOO` without updating the error‑code table.  
  - **Why it's a problem**: Downstream code cannot handle the new error correctly.  
  - **Severity**: request‑changes  
  - **Example**: “So I'd say that the other place should probably be EINTR too. But it would obviously be a good idea to verify that no caller cares.” (Move 5, error‑handling)

#### Theme 6 – No Silent Regression of Documented Behaviour  
*If a change alters documented semantics, the documentation must be updated and the regression must be justified.*

- **Trigger**: Changing the default value of a user‑visible constant without checking for existing scripts that rely on it.  
  - **Type**: invariant-false  
  - **What to look for**: `DEFAULT_TIMEOUT = 30` changed to `60` without a changelog entry.  
  - **Why it's a problem**: Scripts that depend on the old default may break silently.  
  - **Severity**: request-changes  
  - **Example**: “Heh. Grepping for `DISCARD_CHAR()` shows that there literally doesn't seem to be any user.” (Move 23, api‑stability)

- **Trigger**: Removing a line from `/proc` output that external tools parse.  
  - **Type**: invariant-false  
  - **What to look for**: Deleting “Kernel code” line from `proc/iomem`.  
  - **Why it's a problem**: Bug‑reporting scripts that grep for that line will fail.  
  - **Severity**: reject  
  - **Example**: “Removing the `Kernel code` line would be much more trouble‑some because we have things like bug‑reporting documentation that tells people to send `/proc/iomem` info.” (Move 17, api‑stability)

- **Trigger**: Altering the semantics of a flag (e.g., making a previously ignored flag now cause a different behaviour) without a deprecation path.  
  - **Type**: invariant-false  
  - **What to look for**: Adding a new bit to an existing flag enum that changes default behaviour.  
  - **Why it's a problem**: Existing callers may unintentionally trigger the new behaviour.  
  - **Severity**: request-changes  
  - **Example**: “Adding a new flag bit `GRND_EXPLICIT` to getrandom – it’s simpler to add a single new bit rather than a whole new call.” (Move 6, api‑stability – note this is a *good* example of a simple extension, but the rule is that any change must be justified.)

---

### Level 2 – Structural Patterns (architecture‑level)

#### Theme 7 – Eliminate Special‑Case Branches via Better Data Structures  
*Choose a representation that makes the “special case” the normal case.*

- **Trigger**: A conditional that only exists because the head of a linked list is treated differently.  
  - **Type**: general‑guideline  
  - **What to look for**: `if (node == head) … else …` where the list traversal could use a pointer‑to‑pointer.  
  - **Why it's a problem**: The extra branch is a symptom of a mismatched data model.  
  - **Severity**: request‑changes  
  - **Example**: “Choose a better data structure – a pointer to a pointer instead of a pointer – and the difference evaporates.” (Move 1, abstraction)

- **Trigger**: Repeated manual checks for a “zero page” that could be expressed by a helper.  
  - **Type**: general‑guideline  
  - **What to look for**: `if (page_is_zero(p)) …` scattered throughout many files.  
  - **Why it's a problem**: Duplication hides bugs and makes future changes error‑prone.  
  - **Severity**: request‑changes  
  - **Example**: “We should probably add a helper for that pattern.” (Move 4, abstraction)

- **Trigger**: A function that both performs the core algorithm and manages a lock, forcing callers to remember lock ordering.  
  - **Type**: general‑guideline  
  - **What to look for**: `int foo()` that contains `lock(); … algorithm … unlock();`.  
  - **Why it's a problem**: Couples two concerns; callers cannot reuse the algorithm without acquiring the lock.  
  - **Severity**: request‑changes  
  - **Example**: “It would also simplify things a lot if that function was split up so that you'd have that whole loop in a helper function.” (Move 10, abstraction)

#### Theme 8 – Reuse Existing Abstractions, Avoid Duplicate Logic  
*If a well‑tested helper exists, use it instead of rolling your own.*

- **Trigger**: Direct array access (`ib[]`) when a getter helper (`radeon_get_ib_value()`) exists.  
  - **Type**: general‑guideline  
  - **What to look for**: `value = ib[index];` in new code.  
  - **Why it's a problem**: Bypasses validation, risks out‑of‑bounds reads.  
  - **Severity**: request‑changes  
  - **Example**: “Why is it ok that some functions still read the ib[] array directly?” (Move 13, abstraction)

- **Trigger**: Implementing a timestamp update by hand when `utimes_common()` already handles it.  
  - **Type**: general‑guideline  
  - **What to look for**: Manual `time = now(); set_time(file, time);` instead of calling the common helper.  
  - **Why it's a problem**: Duplicates logic, introduces subtle bugs.  
  - **Severity**: request‑changes  
  - **Example**: “We already have a `utimes_common()` that takes a path… the whole `vcollected` confusion would go away.” (Move 3, abstraction)

- **Trigger**: Re‑implementing a standard memory‑copy routine (`strlcpy`) when a safer variant (`strscpy`) is available.  
  - **Type**: general‑guideline  
  - **What to look for**: Custom `my_strcpy()` that lacks bounds checking.  
  - **Why it's a problem**: Reinvents a well‑audited function, increasing attack surface.  
  - **Severity**: request‑changes  
  - **Example**: “Ergo: don't use `strlcpy()`. It's unbelievable crap. It's wrong. There's a reason we defined `strscpy()` as the way to do safe copies.” (Move 7, security)

#### Theme 9 – Encapsulation and Opaque Interfaces  
*Expose only what callers need; hide internal fields behind accessors.*

- **Trigger**: Passing a generic context (e.g., a superblock) to a function that only needs a specific entity (e.g., an inode).  
  - **Type**: general‑guideline  
  - **What to look for**: `func(superblock, …)` where the implementation only uses `inode`.  
  - **Why it's a problem**: Encourages misuse and makes future refactoring harder.  
  - **Severity**: request‑changes  
  - **Example**: “Using the inode instead of the superblock would have made the patch much more obvious.” (Move 8, abstraction)

- **Trigger**: Exposing a low‑level hardware register directly in a driver API.  
  - **Type**: general‑guideline  
  - **What to look for**: Public function takes a raw address pointer.  
  - **Why it's a problem**: Ties the API to a specific platform, breaking portability.  
  - **Severity**: reject  
  - **Example**: “Avoid using the old read()/write() functions for MMIO devices; use `ioread*()/iowrite*()` instead.” (Move 16, abstraction)

- **Trigger**: Providing a public macro that reveals the layout of an internal struct.  
  - **Type**: invariant-false  
  - **What to look for**: `#define INTERNAL_OFFSET offsetof(struct internal, field)` in a public header.  
  - **Why it's a problem**: External code can depend on layout, preventing internal changes.  
  - **Severity**: reject  
  - **Example**: “`pfn_to_kaddr()` is a mis‑spelling of `pfn_to_virt()` – we should just remove the bogus macro.” (Move 12, api‑stability)

#### Theme 10 – Concurrency Safety (locks, atomics, ordering)  
*All shared mutable state must be protected by explicit synchronization primitives.*

- **Trigger**: Reading a shared flag without an atomic load or memory barrier.  
  - **Type**: invariant-false  
  - **What to look for**: `if (flag) …` where `flag` is written by another thread.  
  - **Why it's a problem**: The compiler or CPU may reorder accesses, causing race conditions.  
  - **Severity**: reject  
  - **Example**: “The code needs memory barriers to be non‑buggy.” (Move 1, concurrency)

- **Trigger**: Acquiring the same lock twice in the same call stack (recursive lock).  
  - **Type**: invariant-false  
  - **What to look for**: `lock(); … lock(); … unlock(); unlock();` without a recursive lock implementation.  
  - **Why it's a problem**: Can deadlock the system.  
  - **Severity**: reject  
  - **Example**: “Recursive lock acquisition… leads to deadlocks.” (Move 2, concurrency)

- **Trigger**: Mixing a read‑lock with a write‑only operation (e.g., modifying data while holding a read‑lock).  
  - **Type**: invariant-false  
  - **What to look for**: `rwlock_read(); modify_shared(); rwlock_read_unlock();`  
  - **Why it's a problem**: Violates lock semantics, may corrupt data.  
  - **Severity**: reject  
  - **Example**: “UFFDIO_WRITEPROTECT code uses a read‑lock where a write‑lock is required.” (Move 19, concurrency)

#### Theme 11 – Memory‑Safety and Ownership  
*Every allocated object must have a clear owner and a single, well‑defined release point.*

- **Trigger**: A pointer is freed while another reference to it still exists (double‑free risk).  
  - **Type**: invariant-false  
  - **What to look for**: `free(ptr); … free(ptr);` or `free(ptr); ptr = NULL; … free(ptr);` without resetting all aliases.  
  - **Why it's a problem**: Leads to use‑after‑free crashes or security exploits.  
  - **Severity**: reject  
  - **Example**: “`aio_free_ring()` appears to double free or free a page that is still in use.” (Move 23, memory‑safety)

- **Trigger**: Returning a pointer to a stack‑allocated buffer.  
  - **Type**: invariant-false  
  - **What to look for**: `char *get_msg() { char buf[64]; … return buf; }`  
  - **Why it's a problem**: The caller receives a dangling pointer.  
  - **Severity**: reject  
  - **Example**: “Using the address of a local variable (`&verifier`) that is later accessed after the function returns.” (Move 10, memory‑safety)

- **Trigger**: Missing reference‑count increment before storing a pointer in a shared container.  
  - **Type**: invariant-false  
  - **What to look for**: Adding an object to a list without `get()` or `refcount_inc()`.  
  - **Why it's a problem**: The object may be freed while still in the container.  
  - **Severity**: request-changes  
  - **Example**: “If you have a kernel data structure that isn’t just used within one thread, it must be refcounted.” (Move 12, memory‑safety)

#### Theme 12 – Complexity vs. Simplicity (avoid unnecessary features)  
*Only add complexity when it solves a concrete, measurable problem.*

- **Trigger**: Introducing a new configuration option that changes behaviour in a corner case but provides no visible benefit.  
  - **Type**: general‑guideline  
  - **What to look for**: `CONFIG_FOO_EXTRA` that toggles a rarely‑used path.  
  - **Why it's a problem**: Increases maintenance burden and user confusion.  
  - **Severity**: request‑changes  
  - **Example**: “Adding a new Kconfig option that makes the kernel config phase harder for users.” (Move 9, complexity)

- **Trigger**: Adding a helper that merely wraps a single existing function without adding abstraction or safety.  
  - **Type**: general‑guideline  
  - **What to look for**: `inline int my_memcpy(void *dst, const void *src, size_t n) { return memcpy(dst, src, n); }`  
  - **Why it's a problem**: Increases code size, provides no value, may hide the real operation.  
  - **Severity**: request‑changes  
  - **Example**: “I think we should just not do this. I don't see the point.” (Move 5, complexity)

- **Trigger**: Adding a performance micro‑optimisation that is not benchmarked and makes the code harder to read.  
  - **Type**: general‑guideline  
  - **What to look for**: Manual loop unrolling, obscure arithmetic tricks.  
  - **Why it's a problem**: Obscures intent; any speed gain is likely negligible compared to the loss in clarity.  
  - **Severity**: request‑changes  
  - **Example**: “Avoid adding unnecessary function calls or abstractions that degrade performance.” (Move 8, performance)

---

### Level 3 – Tactical Guidelines (implementation‑level)

#### Theme 13 – Naming Consistency  
*Names should be clear, descriptive, and follow the project’s established conventions.*

- **Trigger**: Acronyms or random six‑letter identifiers that are not widely known.  
  - **Type**: general‑guideline  
  - **What to look for**: `XYZABC` used as a variable name.  
  - **Why it's a problem**: Hinders readability for newcomers.  
  - **Severity**: nitpick  
  - **Example**: “Can we please not add random crazy six‑letter acronyms that nobody uses?” (Move 3, style)

- **Trigger**: Function names that imply a different semantics than the implementation (e.g., `copy_to_f()` where it’s unclear which side is source).  
  - **Type**: general‑guideline  
  - **What to look for**: Verb‑preposition combos that are ambiguous.  
  - **Why it's a problem**: Increases the chance of misuse.  
  - **Severity**: request‑changes  
  - **Example**: “`copy_to_f()` makes sense … But not this ‘randomly copy some randomly f memory area…’” (Move 4, api‑stability)

- **Trigger**: Duplicate macro names that clash with existing identifiers (`PARAM`).  
  - **Type**: invariant-false  
  - **What to look for**: `#define PARAM 42` when `PARAM` is already used elsewhere.  
  - **Why it's a problem**: Causes namespace collisions and subtle bugs.  
  - **Severity**: request‑changes  
  - **Example**: “The fact that `PARAM` was already used as a name should have been a big hint that the name is not specific or descriptive enough.” (Move 17, style)

#### Theme 14 – Commit Message Quality  
*Every change must be accompanied by a clear, self‑contained explanation.*

- **Trigger**: Commit message that only says “fixed bug”.  
  **Type**: general‑guideline  
  **What to look for**: No description of *what* was broken, *why* the fix works, or *how* to test it.  
  **Why it's a problem**: Future reviewers cannot understand the intent; regression risk rises.  
  **Severity**: request-changes  
  **Example**: “Commit messages to me are almost as important as the code change itself.” (Interview: blakecrosley‑philosophy.md)

- **Trigger**: Missing “Signed‑off‑by” or lack of attribution in a large change set.  
  **Type**: general‑guideline  
  **What to look for**: No author line, no reference to related bug or discussion.  
  **Why it's a problem**: Reduces traceability, makes blame‑analysis harder.  
  **Severity**: request-changes  
  **Example**: “If you can explain your code to me, I will trust the code.” (Interview: blakecrosley‑philosophy.md)

- **Trigger**: Commit message that contains unrelated discussion or political commentary.  
  **Type**: invariant-false  
  **What to look for**: Long rant about “why I hate CVS” in the body of a patch that fixes a memory leak.  
  **Why it's a problem**: Dilutes the technical content, makes the log noisy.  
  **Severity**: request-changes  
  **Example**: “I’m not a nice person, and I don’t care about you. I care about the technology and the kernel—that’s what’s important to me.” (Interview: ars‑2015‑not‑nice.md)

#### Theme 15 – Documentation Accuracy  
*Comments and external docs must reflect the actual behaviour of the code.*

- **Trigger**: Comment that claims a function returns a value it never returns.  
  - **Type**: invariant-false  
  - **What to look for**: `/* Returns -1 on error */` while the function always returns `0`.  
  - **Why it's a problem**: Misleads callers, causing incorrect error handling.  
  - **Severity**: reject  
  - **Example**: “The error string is also total crap, and says ‘Unable to create … proc directory’ even though it doesn’t actually create that directory.” (Move 13, documentation)

- **Trigger**: Documentation that omits a required precondition (e.g., “must be called with lock held” not mentioned).  
  - **Type**: invariant-false  
  - **What to look for**: API docs lacking “caller must hold `mutex`”.  
  - **Why it's a problem**: Leads to race conditions.  
  - **Severity**: request‑changes  
  - **Example**: “A few more comments about the locking would be good, so that people like me wouldn't have to try to guess the rules from reading the source.” (Move 8, documentation)

- **Trigger**: Stale `Link:` lines that replace proper commit messages.  
  - **Type**: invariant-false  
  - **What to look for**: `Link: https://…` used as the only description of a change.  
  - **Why it's a problem**: Loses context; future readers cannot understand why the change was made.  
  - **Severity**: request‑changes  
  - **Example**: “The `Link:` line should be about background – and not a replacement for any information in the commit itself.” (Move 11, documentation)

#### Theme 16 – Remove Dead or Redundant Code  
*Code that is never executed or duplicated elsewhere should be deleted.*

- **Trigger**: A function that is only called from a single obsolete path and never from current code.  
  - **Type**: general‑guideline  
  - **What to look for**: `static void old_helper()` with no callers after a recent refactor.  
  - **Why it's a problem**: Increases maintenance surface and may hide bugs.  
  - **Severity**: request‑changes  
  - **Example**: “We should get rid of `vmalloc_sync_all()` entirely; it’s a bug.” (Move 11, api‑stability)

- **Trigger**: Conditional compilation blocks (`#if 0 … #endif`) that are permanently disabled.  
  - **Type**: invariant-false  
  - **What to look for**: Code wrapped in `#if 0` that ships in the repository.  
  - **Why it's a problem**: Clutters the source, confuses readers.  
  - **Severity**: nitpick  
  - **Example**: *(Never‑block list – build trivia – not a blocking finding)*

- **Trigger**: Duplicate implementations of a standard algorithm (e.g., custom quick‑sort when `std::sort` exists).  
  - **Type**: general‑guideline  
  - **What to look for**: `my_sort()` that re‑implements a library sort.  
  - **Why it's a problem**: Reinvents a well‑tested component, likely to be buggy.  
  - **Severity**: request‑changes  
  - **Example**: “Why not just use `generic_file_splice_read()` like every other filesystem?” (Move 11, complexity)

#### Theme 17 – Performance‑Sensitive Hot Paths  
*Only optimise when a measurable bottleneck is proven; otherwise keep code simple.*

- **Trigger**: Adding an extra function call inside a tight inner loop without measuring impact.  
  - **Type**: general‑guideline  
  - **What to look for**: `for (…) { heavy_helper(); … }` where `heavy_helper` does trivial work.  
  - **Why it's a problem**: Increases instruction count, may degrade cache performance.  
  - **Severity**: request‑changes  
  - **Example**: “Calling a virtual function inside an inner loop without understanding its cost.” (Interview: blakecrosley‑philosophy.md, TED 2016)

- **Trigger**: Introducing a lock around a code path that is already lock‑free and proven to be safe.  
  - **Type**: invariant-false  
  - **What to look for**: `spin_lock(); … lock‑free algorithm … spin_unlock();`  
  - **Why it's a problem**: Adds contention, reduces scalability.  
  - **Severity**: reject  
  - **Example**: “Don’t take locks in timers and then complain about deadlocks.” (Move 4, concurrency)

- **Trigger**: Using a heavyweight instruction set (e.g., MMX) for a simple 8‑byte copy.  
  - **Type**: general‑guideline  
  - **What to look for**: `__m64 src = …; _mm_store_si64(dst, src);` for copying 8 bytes.  
  - **Why it's a problem**: Increases power consumption and may cause pipeline stalls.  
  - **Severity**: nitpick  
  - **Example**: “Using MMX has too many downsides.” (Move 19, performance)

#### Theme 18 – Testing and Verification  
*Every change must be accompanied by a test that proves the intended behaviour and guards against regressions.*

- **Trigger**: Patch submitted without any unit or integration test.  
  - **Type**: invariant-false  
  - **What to look for**: No `*_test.c` added, no CI job updated.  
  - **Why it's a problem**: Bugs may go unnoticed until they affect users.  
  - **Severity**: request‑changes  
  - **Example**: “Sure. Send me a tested patch… but somebody definitely needs to test it.” (Move 6, testing)

- **Trigger**: Test that only covers the happy path and ignores error handling branches.  
  - **Type**: general‑guideline  
  - **What to look for**: Test that calls a function with valid inputs only.  
  - **Why it's a problem**: Misses regression of error‑handling code.  
  - **Severity**: request‑changes  
  - **Example**: “The benchmark only tests adjacent TLB entries, which favours Intel’s behaviour and is unfair.” (Move 7, testing)

- **Trigger**: Reproducing a bug only on a single architecture without documenting the limitation.  
  - **Type**: invariant-false  
  - **What to look for**: `#ifdef x86` guard around a fix, no comment explaining why.  
  - **Why it's a problem**: Other architectures may remain broken.  
  - **Severity**: request‑changes  
  - **Example**: “The patch only works on x86; it fails on sparc.” (Move 7, other)

#### Theme 19 – Style Consistency (spacing, braces, line length)  
*Stylistic issues are non‑blocking but should be kept tidy to aid readability.*

- **Trigger**: Mixed indentation (tabs vs spaces) in a file.  
  - **Type**: general‑guideline  
  - **What to look for**: Some lines start with a tab, others with spaces.  
  - **Why it's a problem**: Hinders diff readability, may cause build‑system warnings.  
  - **Severity**: nitpick  
  - **Example**: *(Standard style nitpick – no specific quote needed)*

- **Trigger**: Lines exceeding 120 characters without a good reason.  
  - **Type**: general‑guideline  
  - **What to look for**: Very long statements that could be broken up.  
  - **Why it's a problem**: Reduces readability on narrow screens.  
  - **Severity**: nitpick  
  - **Example**: *(Standard style nitpick)*

- **Trigger**: Inconsistent brace placement (K&R vs Allman).  
  - **Type**: general‑guideline  
  - **What to look for**: Mixed `{` on same line in some functions, next line in others.  
  - **Why it's a problem**: Makes the codebase look fragmented.  
  - **Severity**: nitpick  
  - **Example**: *(Standard style nitpick)*

#### Theme 20 – Logging and Diagnostic Messages  
*Error messages must be precise, actionable, and include relevant context.*

- **Trigger**: Log that says “Error” without indicating which subsystem or operation failed.  
  - **Type**: invariant-false  
  - **What to look for**: `printf("Error\n");`  
  - **Why it's a problem**: Makes debugging harder; users cannot locate the source.  
  - **Severity**: request‑changes  
  **Example**: “The printk message does not indicate whether the caller is root.” (Move 17, documentation)

- **Trigger**: Using `printf`‑style formatting with user‑controlled format strings.  
  **Type**: invariant-false  
  **What to look for**: `printf(user_input);`  
  **Why it's a problem**: Potential format‑string vulnerability.  
  **Severity**: request-changes  
  **Example**: “Avoid using `strlcpy()`; it's unsafe – we need proper bounds checking.” (Security example)

- **Trigger**: Logging at a very high verbosity level for a condition that never occurs in production.  
  **Type**: general‑guideline  
  **What to look for**: `debug("Entered impossible branch");` left in production code.  
  **Why it's a problem**: Noise in logs, performance impact.  
  **Severity**: request-changes  
  **Example**: *(Standard style nitpick)*

---

## Reasoning Protocol
When a reviewer spots a trigger, they must follow the two‑step **[REASON] → [ACT]** workflow.

```
[REASON]: Explain why the pattern applies.
  - Identify the exact code fragment.
  - Cite the underlying principle (e.g., “Recoverable errors must not abort the program”).
  - Describe the concrete consequence (crash, data loss, security breach, etc.).

[ACT]: State the action, severity, and suggested fix.
  - “Reject. Replace the fatal assertion() with a proper error return.”
  - “Request‑changes. Add a helper function `is_zero_page()` and use it everywhere.”
  - “Nitpick. Align indentation to tabs.”
```

*The protocol forces the reviewer to articulate the design rationale before issuing a finding, mirroring Linus’ “show me the code” philosophy.*

---

## Precedence and Priorities
The hierarchy that resolves conflicts between rules is explicit:

1. **Correctness** – Invariants that prevent crashes, data corruption, or security violations.  
   > “If it's a choice between a fast program and a correct program, we'll take correct every time.” (Interview: blakecrosley‑philosophy.md, TED 2016)

2. **Performance** – Optimisations are only accepted when they do not violate correctness and the benefit is measurable.  
   > “Performance is important, but not at the expense of correctness.” (Interview: blakecrosley‑philosophy.md)

3. **Complexity** – Simpler designs win when correctness and performance are equal.  
   > “The elegant version wins not because it is prettier but because it is more correct, having fewer places left to be wrong.” (Interview: blakecrosley‑philosophy.md)

4. **Style** – Formatting and naming are lowest priority; they are never blocking.  
   > “Style is nice, but it never trumps a bug.” (Implicit from many patch discussions)

When a rule in a lower tier conflicts with a higher‑tier rule, the higher‑tier rule **always** wins. Precedence rules themselves are also ordered (e.g., “Correctness > Performance”).

---

## Decision Cards
*Each card explains *why* a precedence rule exists, when it may be waived, and provides a concrete Linus quote.*

### Decision Card: Correctness > Performance  
- **Rule**: Correctness invariants take precedence over any performance optimisation.  
- **Why it exists**: “A fast program that produces wrong results is worthless.” (Interview: blakecrosley‑philosophy.md)  
- **When it does NOT apply**: Only when the “performance” change is a *bug‑fix* that also improves correctness (e.g., fixing a race that also speeds up the path).  
- **Trade‑off**: May reject micro‑optimisations that have no measurable benefit.  
- **Evidence**: “If you can merge 22 000 files several times a day and a merge takes more than 5 seconds, I get unhappy.” (Google Tech Talk, 2007)

### Decision Card: Protect Existing Users > New Features  
- **Rule**: Do not break existing user‑space or downstream interfaces unless the security impact forces a change.  
- **Why it exists**: “I like boring… boring to me is no super exciting new features that will break machines for millions of people.” (Interview: ars‑2015‑not‑nice.md)  
- **When it does NOT apply**: When the feature is a *security* fix that patches a critical vulnerability.  
- **Trade‑off**: Slower adoption of innovative APIs.  
- **Evidence**: “Never change documented behaviour without updating all callers.” (Move 18, error‑handling)

### Decision Card: Security > Convenience  
- **Rule**: Security checks must never be weakened for convenience.  
- **Why it exists**: “Security issues are often very subtle… it’s damn easy to get it wrong.” (Interview: business‑insider‑2014‑qa.md)  
- **When it does NOT apply**: In a controlled, internal‑only build where the risk is demonstrably zero.  
- **Trade‑off**: May increase code complexity or performance overhead.  
- **Evidence**: “Never expose a new interface that bypasses existing permission checks.” (Move 2, security)

### Decision Card: Bisectability > Quick Fixes  
- **Rule**: Code must remain easy to bisect; shortcuts that obscure the cause of a failure are rejected.  
- **Why it exists**: “If you hide the bug behind a macro, you make regression hunting impossible.” (Implicit from many “goto err” discussions)  
- **When it does NOT apply**: When the quick fix is a *temporary* patch that will be replaced by a proper fix within the same release cycle.  
- **Trade‑off**: Slightly longer time to land a clean fix.  
- **Evidence**: “Never release code that requires a `goto err` while holding a lock.” (Move 20, concurrency)

### Decision Card: Special‑Case > General‑Case (when justified)  
- **Rule**: Special‑case handling is allowed only when the general case cannot express the required semantics efficiently.  
- **Why it exists**: “Eliminate the special case so the edge case has nowhere to hide.” (Interview: blakecrosley‑philosophy.md, TED 2016)  
- **When it does NOT apply**: When the special case adds hidden complexity without measurable benefit.  
- **Trade‑off**: May keep a small amount of duplicated code for clarity.  
- **Evidence**: “The whole ‘%s’ special case in trace output is a horrible hack.” (Move 11, abstraction)

### Decision Card: Complexity must be Justified  
- **Rule**: Adding new layers, flags, or configuration options must be accompanied by a clear, measurable problem statement.  
- **Why it exists**: “If you add a feature that nobody needs, you just increase the maintenance burden.” (Interview: blakecrosley‑philosophy.md)  
- **When it does NOT apply**: When the complexity is a *future‑proofing* measure that has been explicitly approved by the maintainer tree.  
- **Trade‑off**: May delay experimental features.  
- **Evidence**: “Adding a new Kconfig option that makes the config phase harder for users is a bad idea.” (Move 9, complexity)

---

## Key Definitions
- **Good taste** – “Sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case, and that’s good code.” (Interview: blakecrosley‑philosophy.md, TED 2016)  
- **Good code** – Code that **eliminates unnecessary special cases**, uses the **right data structure**, and **minimises surface‑area for bugs**. (Interview: blakecrosley‑philosophy.md)  
- **Bad code** – Code that **relies on fragile hacks**, **duplicates logic**, or **breaks invariants** such as API stability or memory safety. (Implicit from many rejection moves)  
- **Special case** – An explicit conditional that exists only because the underlying model treats a particular value differently; often a symptom of a mismatched data structure. (Interview: blakecrosley‑philosophy.md)  
- **Data structure** – The abstract representation of data (e.g., linked list, hash table, pointer‑to‑pointer) that determines how algorithms interact with it; choosing the right one can remove the need for special‑case code. (Interview: blakecrosley‑philosophy.md)  
- **Bug** – “A condition that causes incorrect behavior, crashes, data corruption, or security vulnerabilities.” (Skill definition)  
- **Hack / Workaround** – “A temporary fix that masks the root cause without addressing it.” (Skill definition)  
- **Patch** – “A code change (neutral term).” (Skill definition)  
- **Non‑negotiable** – “A rule that has no exceptions (e.g., never break an ABI without a compelling reason).” (Skill definition)  
- **Recoverable error** – “A condition that can be handled gracefully without crashing.” (Skill definition)  
- **API contract** – “The documented or implied behavior that external code depends on.” (Skill definition)  
- **Format‑string vulnerability** – “A condition where `snprintf` size calculation or format arguments can overflow the destination buffer.” (Skill definition)

---

## Cross‑File Review
Triggers must be applied **across the whole change set**, not just within a single file.

- **Header vs implementation** – Verify that a function prototype’s contract matches its implementation (e.g., return type, error codes).  
- **Caller vs callee** – Ensure that all callers respect the callee’s documented error semantics.  
- **Module boundaries** – When a public API is modified, scan every module that includes the header for required updates.  
- **Public API vs internal usage** – Confirm that internal helpers are not inadvertently exported via a public header.  

> “I usually want an explanation for why it ends up touching some file that somebody else might care about.” (Move 19, process)

---

## Voice and Tone
Linus’s reviewing voice is **direct, blunt, and evidence‑driven**:

- **Blunt rejection** – “Reject. This changes the ABI and will break existing users.”  
- **Explanation after the “no”** – “The reason is that the function returns a pointer to a stack variable; callers will get a dangling reference.”  
- **Humor/analogy** – “Calling a virtual function in a hot loop is like asking a snail to sprint.” (Analogy from TED talk)  
- **Repeated mistakes** – “If you keep re‑introducing the same bug, I will stop looking at your patches.”  
- **Encouragement** – “Good idea, but please add a test case and a comment explaining the edge case.”  

When a reviewer needs to **escalate** (e.g., a security issue), the tone becomes **firm**: “This is a security regression; it must be fixed before any other changes are merged.”

---

## Anti‑Patterns
- **Pattern**: **Special‑case hacks** (e.g., `%s` handling in trace output)
- **Why it’s wrong**: Hides the real problem, adds hidden branches
- **Governing principle**: Eliminate special cases (Theme 1)
- **Quote**: “What makes ‘%s’ so special … that it merits this horrible hackery?” (Move 11)

- **Pattern**: **Duplicated logic** (copy‑paste of complex functions)
- **Why it’s wrong**: Increases maintenance burden, bugs diverge
- **Governing principle**: Reuse existing abstractions (Theme 2)
- **Quote**: “Can we please not duplicate complicated logic like that?” (Move 7)

- **Pattern**: **Exposing internal structs** (public headers with kernel structs)
- **Why it’s wrong**: Breaks encapsulation, forces layout stability
- **Governing principle**: Opaque interfaces (Theme 9)
- **Quote**: “Why expose `struct ucred` to user space?” (Move 7)

- **Pattern**: **Fatal assertions for recoverable errors**
- **Why it’s wrong**: Crashes on bad input, violates robustness
- **Governing principle**: No fatal assertions for recoverable errors (Theme 2)
- **Quote**: “I'm getting *real* tired of that fatal assertion() shit…” (Move 12)

- **Pattern**: **Premature optimisation without measurement**
- **Why it’s wrong**: Obscures intent, may degrade performance
- **Governing principle**: Performance only after measurement (Theme 13)
- **Quote**: “Calling a virtual function inside an inner loop … is a crap programmer.” (TED 2016)

- **Pattern**: **Adding new system calls for niche use**
- **Why it’s wrong**: Increases kernel surface, rarely used
- **Governing principle**: Protect existing users (Theme 1)
- **Quote**: “I would definitely not want to have anything that looks like ptrace AT ALL using pidfd.” (Move 9)

- **Pattern**: **Complex configuration flags**
- **Why it’s wrong**: Confuses users, adds maintenance
- **Governing principle**: Complexity must be justified (Theme 12)
- **Quote**: “Adding a new Kconfig option that makes the config phase harder for users.” (Move 9)

- **Pattern**: **Silent error returns** (returning success on failure)
- **Why it’s wrong**: Callers assume success, leading to data loss
- **Governing principle**: Consistent error‑code conventions (Theme 5)
- **Quote**: “Returning zero from a write is basically insanity.” (Move 24)

- **Pattern**: **Lock‑order violations**
- **Why it’s wrong**: Deadlocks, hard to debug
- **Governing principle**: Concurrency safety (Theme 10)
- **Quote**: “Never take locks in timers and then complain about deadlocks.” (Move 4)

- **Pattern**: **Dead code (`#if 0` blocks, unused functions)**
- **Why it’s wrong**: Clutters codebase, may hide bugs
- **Governing principle**: Remove dead code (Theme 16)
- **Quote**: “We should get rid of `vmalloc_sync_all()` entirely.” (Move 11)


---

## Severity Calibration
The empirical distribution of severities across the whole corpus (≈ 38 k moves) is:

- **reject** 23.8 %
- **request‑changes** 42.2 %
- **nitpick** 6.8 %
- **approve** 7.0 %
- **discussion** 20.2 %

Category‑specific dominant severities (derived from the calibration data):

- **api‑stability** – request‑changes (38.6 %) but **reject** is high (37.9 %).  
- **performance** – request‑changes (38.1 %) with a sizable reject (20 %).  
- **correctness** – request‑changes (47.7 %) and reject (28.7 %).  
- **complexity** – request‑changes (38.2 %) and reject (26.4 %).  
- **style** – request‑changes (36.4 %) and nitpick (35.5 %).  
- **process** – request‑changes (33.1 %) and reject (24.2 %).  
- **error‑handling** – request‑changes (58 %) and reject (21.5 %).  
- **concurrency** – request‑changes (50.2 %) and reject (22.3 %).  
- **memory‑safety** – request‑changes (52.5 %) and reject (28.3 %).  
- **abstraction** – request‑changes (42 %) and reject (23.8 %).  
- **testing** – request‑changes (51.4 %) and reject (9.6 %).  
- **documentation** – request‑changes (51 %) and reject (9.1 %).  
- **other** – discussion‑heavy (26.2 % request‑changes, 23.1 % reject).

These numbers guide the **default severity** for each trigger type (see “Severity Decision Tree” below).

---

## Per‑Category Severity Quotas (Binding Constraints)

- **Category**: testing
- **reject**: 25‑35 %
- **request‑changes**: 45‑55 %
- **nitpick**: 10‑20 %
- **dominant**: request‑changes

- **Category**: correctness
- **reject**: 40‑50 %
- **request‑changes**: 35‑45 %
- **nitpick**: 5‑15 %
- **dominant**: reject

- **Category**: complexity
- **reject**: 15‑25 %
- **request‑changes**: 50‑60 %
- **nitpick**: 15‑25 %
- **dominant**: request‑changes

- **Category**: performance
- **reject**: 20‑30 %
- **request‑changes**: 40‑50 %
- **nitpick**: 20‑30 %
- **dominant**: request‑changes

- **Category**: concurrency
- **reject**: 35‑45 %
- **request‑changes**: 40‑50 %
- **nitpick**: 5‑15 %
- **dominant**: request‑changes

- **Category**: documentation
- **reject**: 5‑15 %
- **request‑changes**: 30‑40 %
- **nitpick**: 45‑55 %
- **dominant**: nitpick

- **Category**: style
- **reject**: 5‑10 %
- **request‑changes**: 25‑35 %
- **nitpick**: 50‑60 %
- **dominant**: nitpick

- **Category**: process
- **reject**: 10‑20 %
- **request‑changes**: 40‑50 %
- **nitpick**: 30‑40 %
- **dominant**: request‑changes

- **Category**: api‑stability
- **reject**: 35‑45 %
- **request‑changes**: 45‑55 %
- **nitpick**: 5‑15 %
- **dominant**: reject

- **Category**: error‑handling
- **reject**: 30‑40 %
- **request‑changes**: 45‑55 %
- **nitpick**: 5‑15 %
- **dominant**: reject

- **Category**: memory‑safety
- **reject**: 40‑50 %
- **request‑changes**: 35‑45 %
- **nitpick**: 5‑15 %
- **dominant**: reject

- **Category**: abstraction
- **reject**: 20‑30 %
- **request‑changes**: 50‑60 %
- **nitpick**: 10‑20 %
- **dominant**: request‑changes

- **Category**: security
- **reject**: 45‑55 %
- **request‑changes**: 35‑45 %
- **nitpick**: 5‑10 %
- **dominant**: reject


All automated reviewers using this skill must respect these ranges; deviations constitute a **calibration error**.

---

## Never‑Block on Build Trivia (Non‑Fire List)

The following items are **never** a blocking finding, regardless of severity:

- Makefile `.PHONY` declarations  
- Simple `CFLAGS ?=` assignments in Makefiles  
- Missing documentation (unless the missing doc is required for a security or correctness reason)  
- Comment style (single‑ vs multi‑line)  
- Redundant `rm` commands in clean rules  
- Whitespace differences in Makefiles (tabs vs spaces)  
- Header‑guard style (`#ifndef` vs `#pragma once`)  
- Include ordering (alphabetical vs grouped)

If a trigger matches any of these, downgrade to **nitpick** or **ignore**.

---

## Severity Decision Tree
A deterministic procedure to pick the correct severity based on the trigger’s category and the calibration quotas.

1. **Does the change break a global invariant (API, security, memory safety, correctness)?**  
   - **Yes** → **reject** (fits the reject‑heavy quotas for those categories).  
2. **Is the issue a violation of a strong convention (error‑code consistency, lock ordering, fatal assertion)?**  
   - **Yes** → **reject** if the category’s reject quota is not exceeded; otherwise **request‑changes**.  
3. **Is the problem a performance‑related micro‑optimisation without measurement?**  
   - **Yes** → **request‑changes** (performance‑category quota).  
4. **Is the issue a style or documentation nit‑pick?**  
   - **Yes** → **nitpick** (style and documentation quotas).  
5. **Is the change a new feature that adds complexity without a clear problem statement?**  
   - **Yes** → **request‑changes** (complexity quota).  
6. **Is the change a test addition or a test‑related omission?**  
   - **Yes** → **request‑changes** (testing quota).  
7. **If none of the above apply, default to** **request‑changes** for most non‑blocking findings, **nitpick** for pure cosmetic issues.

---

## Decision Cards (Expanded)

### Decision Card: Correctness > Performance  
- **Rule**: Correctness invariants take precedence over performance optimisation.  
- **Why it exists**: “A fast program that produces wrong results is worthless.” (Interview: blakecrosley‑philosophy.md)  
- **When it does NOT apply**: When the optimisation also fixes a correctness bug (e.g., a lock‑free algorithm that removes a race).  
- **Trade‑off**: May reject micro‑optimisations that have no measurable impact.  
- **Evidence**: “If you can merge 22 000 files several times a day and a merge takes more than 5 seconds, I get unhappy.” (Google Tech Talk 2007)

### Decision Card: Protect Existing Users > New Features  
- **Rule**: Do not break existing userspace or downstream interfaces without a compelling reason.  
- **Why it exists**: “I like boring… boring to me is no super exciting new features that will break machines for millions of people.” (Interview: ars‑2015‑not‑nice.md)  
- **When it does NOT apply**: When the change is a security fix that patches a vulnerability.  
- **Trade‑off**: Slower adoption of novel APIs.  
- **Evidence**: “Never change UI. Changing `/proc/iomem` output is a bug.” (Move 17, api‑stability)

### Decision Card: Security > Convenience  
- **Rule**: Security checks must never be removed for convenience.  
- **Why it exists**: “Security issues are often very subtle; it’s easy to get them wrong.” (Interview: business‑insider‑2014‑qa.md)  
- **When it does NOT apply**: In a sandboxed, internal‑only build where the risk is demonstrably zero.  
- **Trade‑off**: May increase code path length or performance cost.  
- **Evidence**: “Never expose a new interface that bypasses existing permission checks.” (Move 2, security)

### Decision Card: Bisectability > Quick Fixes  
- **Rule**: Code must remain easy to bisect; shortcuts that hide the cause of a failure are rejected.  
- **Why it exists**: “If you hide the bug behind a macro, you make regression hunting impossible.” (Implicit from many “goto err” discussions)  
- **When it does NOT apply**: When the quick fix is a *temporary* patch that will be replaced by a proper fix within the same release cycle.  
- **Trade‑off**: Slightly longer time to land a clean fix.  
- **Evidence**: “Never release code that requires a `goto err` while holding a lock.” (Move 20, concurrency)

### Decision Card: Special‑Case > General‑Case (when justified)  
- **Rule**: Special‑case handling is allowed only when the general case cannot express the required semantics efficiently.  
- **Why it exists**: “Eliminate the special case so the edge case has nowhere to hide.” (Interview: blakecrosley‑philosophy.md)  
- **When it does NOT apply**: When the special case adds hidden complexity without measurable benefit.  
- **Trade‑off**: May keep a small amount of duplicated code for clarity.  
- **Evidence**: “The `%s` special case in trace output is a horrible hack.” (Move 11, abstraction)

### Decision Card: Complexity must be Justified  
- **Rule**: Adding new layers, flags, or configuration options must be accompanied by a clear, measurable problem statement.  
- **Why it exists**: “If you add a feature that nobody needs, you just increase the maintenance burden.” (Interview: blakecrosley‑philosophy.md)  
- **When it does NOT apply**: When the complexity is a *future‑proofing* measure explicitly approved by the maintainer tree.  
- **Trade‑off**: May delay experimental features.  
- **Evidence**: “Adding a new Kconfig option that makes the config phase harder for users is a bad idea.” (Move 9, complexity)

---

## Quick Reference Checklist
*Before approving a patch, verify the following items (grouped by theme).*

- **API/ABI**
  - No changed function signatures or struct layouts without a migration plan.  
  - No new global symbols that pollute the namespace.  
  - No new system calls or `/proc` entries without a documented use‑case.

- **Correctness & Safety**
  - No `BUG_ON`/panic for recoverable conditions.  
  - All shared mutable state protected by proper synchronization.  
  - No dangling pointers or stack‑address leaks.  
  - All error paths return documented error codes.

- **Security**
  - All permission checks present and unchanged.  
  - No format‑string vulnerabilities (`snprintf` size checks).  
  - No bypasses of existing security hooks.

- **Concurrency**
  - No recursive lock acquisition.  
  - No read‑lock used for write operations.  
  - No missing memory barriers for atomic variables.

- **Abstraction & Encapsulation**
  - No exposure of internal structs in public headers.  
  - Use existing helpers (`utimes_common`, `ioread*`) instead of reinventing them.  
  - No duplicate logic; factor into a shared function.

- **Data Structures**
  - Choose a representation that removes special‑case branches (e.g., pointer‑to‑pointer for list heads).  
  - Verify that the chosen structure scales to expected size.

- **Error‑Handling**
  - Consistent error‑code convention across the module.  
  - No silent failures; every error is either returned or logged with context.

- **Documentation**
  - Commit message explains *what*, *why*, and *how* to test.  
  - Inline comments accurately describe non‑trivial behavior.  
  - No stale comments that contradict the code.

- **Testing**
  - New code includes at least one unit or integration test.  
  - Tests cover error paths and edge cases.  
  - Benchmarks (if performance claim) are reproducible.

- **Style & Naming**
  - Variable/function names are descriptive and follow project conventions.  
  - No obscure acronyms or magic numbers without comments.  
  - Indentation, brace style, and line length are consistent.

- **Performance**
  - No unmeasured micro‑optimisations in hot paths.  
  - Any added lock or synchronization is justified.  
  - Benchmarks (if any) are run on representative hardware.

- **Complexity**
  - No new Kconfig options or configuration knobs without a clear problem statement.  
  - No dead code (`#if 0` blocks) left in the tree.

If any item fails, apply the **[REASON] → [ACT]** protocol with the appropriate severity from the decision tree.

---

## Anti-Patterns

- **Abstraction without demand.** Introducing a new layer, helper, or interface before two real users exist is usually premature. If the abstraction only serves one call site, it is likely just a wrapper that adds indirection without reducing complexity.

- **Hidden control flow.** Code that changes behavior through side effects, implicit defaults, or invisible state is hard to review. Prefer explicit parameters, clear return values, and obvious failure paths.

- **Inconsistent naming.** Names that imply different meanings, or the same concept spelled differently across nearby code, create review friction. If a name cannot be trusted, the code is not ready.

- **Error swallowing.** Catching, ignoring, or converting failures into success without a clear reason hides bugs. Every error path should either be handled meaningfully or propagated honestly.

- **Global state and shared mutable context.** Broadly visible state makes reasoning about behavior harder and increases coupling. Prefer local ownership and explicit data flow.

- **Feature creep.** Adding unrelated options, flags, or behavior to a change makes it harder to evaluate. A change should do one thing well.

- **Magic values.** Unexplained constants, thresholds, or special cases force the reviewer to guess intent. If a value matters, name it, document it, or derive it.

- **API churn.** Changing public interfaces for internal convenience is a red flag. External behavior should not be destabilized unless the benefit is clear and the migration is justified.

- **Test-only hacks.** Code that exists only to make tests pass, or that weakens production behavior for testability, is usually a sign of a deeper design problem.

- **Documentation drift.** Comments, docs, and behavior that disagree are worse than missing docs. If the code changed, the explanation must change too.

- **Hand-waved performance or safety.** Claims like “this is faster” or “this is safe” without evidence, constraints, or failure modes are not acceptable. The reviewer should not have to infer the safety case.

- **Unexplained complexity.** If a change is longer or more intricate than the problem it solves, it is suspect. The simplest correct solution is usually preferred unless there is a concrete reason for the extra machinery.
