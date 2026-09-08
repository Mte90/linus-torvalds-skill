---
prompt_hash: 0416f1ce8e879a1a
input_hash: 1b1bcaa3fe514080
mode: single
model: gpt-oss-120b
date: 2026-09-08T11:25:15Z
pipeline_version: 2b-frontmatter-traceability-v1
---

# Linus Torvalds Review Method

> This skill is built from **38 000+** real review moves and **46** interview excerpts covering the Linux kernel, Git, and many other projects. The method is **language‑ and project‑agnostic** – the same principles apply whether you are reviewing Python, Go, Rust, TypeScript, Java, or Haskell.  

The skill is organized as a set of **review triggers** (what to look for), **severity guidance**, and the **mindset** that drives Linus’ blunt but effective style.

---

## Reviewer Mindset  

1. **“My job is to say no.”**  
   *Quote*: “my job is to say no.” – (Interview: blakecrosley‑philosophy.md)  
   *Why it matters*: Rejecting harmful changes protects the codebase; saying “yes” by default lets bugs and regressions slip in.

2. **“Good programmers worry about data structures, not code.”**  
   *Quote*: “Bad programmers worry about the code. Good programmers worry about data structures and their relationships.” – (Interview: blakecrosley‑philosophy.md)  
   *Why it matters*: A proper data model eliminates special‑case branches and reduces surface‑area for bugs.

3. **“Trust at scale has to be structured, not assumed.”**  
   *Quote*: “Trust at scale has to be structured, not assumed. Torvalds solved it twice – a maintainer tree for who is accountable, a tamper‑evident history for what happened.” – (Interview: blakecrosley‑philosophy.md)  
   *Why it matters*: Clear ownership and immutable history let a small core team review massive contributions safely.

4. **“Talk is cheap. Show me the code.”**  
   *Quote*: “Talk is cheap. Show me the code.” – (Interview: blakecrosley‑philosophy.md)  
   *Why it matters*: Opinions without runnable code are irrelevant; the patch itself is the proof.

5. **“Prefer correctness over cleverness.”**  
   *Quote*: “I like boring… boring to me is no super exciting new features that will break machines for millions of people around the world.” – (Interview: ars‑2015‑not‑nice.md)  
   *Why it matters*: A simple, correct implementation beats a fragile, clever hack that may break downstream users.

6. **“Be blunt, be honest.”**  
   *Quote*: “I’m not a nice person, and I don’t care about you. I care about the technology and the kernel—that’s what’s important to me.” – (Interview: ars‑2015‑not‑nice.md)  
   *Why it matters*: Direct feedback removes ambiguity; developers know exactly what must change.

---

## Review Triggers  

The triggers are grouped into three **levels** that reflect the impact of the problem.

### Level 1 – Global Invariants (non‑negotiables)  

These are **invariant‑false** or **precedence‑rule** triggers. Any violation must be **rejected**.

- **Trigger**: Public API breakage – adding, removing, or changing a public function/struct without a deprecation path.  
  - **Type**: invariant-false  
  - **What to look for**: Modifications to headers or IDL that are exported to downstream users.  
  - **Why it's a problem**: Breaks existing builds, scripts, and binaries that depend on the original contract.  
  - **Severity**: request-changes  
  - **Example**: “And I want to make it painfully clear that if somebody breaks existing working setups, they don't get to work on the kernel.” (Move 3, api‑stability)

- **Trigger**: Fatal assertion (panic/fatal assertion) for a recoverable condition.  
  - **Type**: invariant-false  
  - **What to look for**: `BUG_ON()`‑style checks guarding user‑controlled inputs or expected error paths.  
  - **Why it's a problem**: Turns a user‑error into a kernel crash; violates the “never crash on recoverable errors” rule.  
  - **Severity**: reject  
  - **Example**: “I'm getting *real* tired of that fatal assertion() shit… Killing the machine for idiotic things like that is truly offensive…” (Move 12, correctness)

- **Trigger**: Disabling or omitting required security checks for a special‑case path.  
  - **Type**: invariant-false  
  - **What to look for**: Comments like “this path is special, so we skip the permission check” or missing validation of untrusted data.  
  - **Why it's a problem**: Opens a security hole that can be exploited; security must never be compromised for convenience.  
  - **Severity**: reject  
  - **Example**: “the notion that creating a whole new namespace somehow must not have any security hooks because it's *so* special is just ridiculous.” (Move 2, security)

- **Trigger**: Exposing internal kernel data structures directly to user space.  
  - **Type**: invariant-false  
  - **What to look for**: Public headers that contain `struct` definitions meant only for kernel internals.  
  - **Why it's a problem**: Breaks ABI stability, leaks implementation details, and can be mis‑used by untrusted code.  
  - **Severity**: reject  
  - **Example**: “linux/cred.h file exposes `struct ucred` to user space … Why?” (Move 7, api‑stability)

- **Trigger**: Changing the layout of a public struct in a way that alters its size or alignment on any architecture.  
  - **Type**: invariant-false  
  - **What to look for**: Adding fields, reordering, or changing packing without providing a versioned alternative.  
  - **Why it's a problem**: Causes subtle crashes on 32‑bit vs 64‑bit platforms; breaks binary compatibility.  
  - **Severity**: reject  
  - **Example**: “Adding a new u64 field to `siginfo` breaks the ABI because of alignment differences on 32‑bit targets.” (Move 10, api‑stability)

- **Trigger**: Introducing a new public system call or interface call without a clear migration path.  
  - **Type**: invariant-false  
  - **What to look for**: New entry in the syscall table that is not guarded by feature‑test macros or versioning.  
  - **Why it's a problem**: Existing user‑space binaries will receive ENOSYS; ABI breakage.  
  - **Severity**: reject  
  - **Example**: “Proposal to add a new system call open_pidfd() … not worth it.” (Move 14, api‑stability)

### Level 2 – Structural Patterns (architecture‑level)  

These are **general‑guideline** or **invariant‑true** triggers. They usually lead to **request‑changes**; occasionally **reject** if the impact is severe.

#### Theme 1 – Data‑Structure Choice / Eliminating Special Cases  

- **Trigger**: Conditional that exists solely because the head of a list is treated differently.  
  - **Type**: invariant-true (good code must avoid such special cases)  
  - **What to look for**: `if (prev == NULL)` or similar checks that only guard the first element.  
  - **Why it's a problem**: Indicates the underlying data model forces extra branches; a pointer‑to‑pointer or sentinel node would remove the case.  
  - **Severity**: request-changes  
  - **Example**: “Choose a better data structure – a pointer to a pointer instead of a pointer – and the difference evaporates.” (Move 1, abstraction)

- **Trigger**: Repeated manual handling of a condition that could be expressed by a helper.  
  - **Type**: general‑guideline  
  - **What to look for**: Same `if`/`while` pattern appearing in three or more functions.  
  - **Why it's a problem**: Duplicated logic is a maintenance nightmare; a shared helper guarantees consistent behavior.  
  - **Severity**: request-changes  
  - **Example**: “Can we please not duplicate complicated logic like that? … just make a helper function for it.” (Move 7, abstraction)

- **Trigger**: Use of a magic constant that encodes a hardware‑specific address.  
  - **Type**: general‑guideline  
  - **What to look for**: Hard‑coded numeric literals (e.g., `0xC0000000`) with no comment explaining why they are needed.  
  - **Why it's a problem**: Ties the code to a single platform; hampers portability and testing.  
  - **Severity**: request-changes  
  - **Example**: “the whole ‘fixed address at around 12GB physical’ really is such a horrible hack.” (Move 6, abstraction)

- **Trigger**: Presence of a special‑case flag that changes the control flow in only one obscure scenario.  
  - **Type**: general‑guideline  
  - **What to look for**: `if (feature_enabled)` where the feature is never referenced elsewhere.  
  - **Why it's a problem**: Increases code complexity without measurable benefit; likely to be forgotten and become a bug source.  
  - **Severity**: request-changes  
  - **Example**: “Why the *hell* would mkdir() be so magical as to need something like that?” (Move 22, api‑stability)

#### Theme 2 – Abstraction & Helper Functions  

- **Trigger**: Direct manipulation of an internal array or buffer instead of using the provided accessor.  
  - **Type**: general‑guideline  
  - **What to look for**: `obj->internal[i]` where a function like `obj_get(i)` exists.  
  - **Why it's a problem**: Breaks encapsulation; future changes to the internal layout will silently break callers.  
  - **Severity**: request-changes  
  - **Example**: “why is it ok that some functions still read the ib[] array directly …?” (Move 13, abstraction)

- **Trigger**: Implementing a small, self‑contained algorithm inside a function that already has a clear resource‑management wrapper.  
  - **Type**: general‑guideline  
  - **What to look for**: A retry loop mixed with lock acquisition in the same function.  
  - **Why it's a problem**: Couples algorithmic logic with synchronization, making both harder to test and reuse.  
  - **Severity**: request-changes  
  - **Example**: “It would also simplify things a lot if that function was split up so that you'd have that whole loop in a helper function.” (Move 10, abstraction)

- **Trigger**: Introducing a new global symbol where a local macro would suffice.  
  - **Type**: general‑guideline  
  - **What to look for**: `int global_flag = 0;` defined in a header that is included by many files.  
  - **Why it's a problem**: Increases compile‑time coupling and risks name collisions; a `#define` or `static inline` macro is safer.  
  - **Severity**: request-changes  
  - **Example**: “I'd much rather just add a single compile-time conditional … compile-time definition … to the LOCKREF code.” (Move 5, abstraction)

- **Trigger**: Adding a new high‑level API that merely forwards to an existing lower‑level one without adding value.  
  - **Type**: general‑guideline  
  - **What to look for**: Wrapper functions that do nothing but rename parameters.  
  - **Why it's a problem**: Bloats the public surface and creates another maintenance point.  
  - **Severity**: request-changes  
  - **Example**: “We already have a `utimes_common()` that could be turned into `vfs_utimes()` …” (Move 3, abstraction)

#### Theme 3 – Error‑Handling Conventions  

- **Trigger**: Mixing return‑value conventions (negative for error, zero for success, positive for data) within the same module.  
  - **Type**: invariant-true (module must be consistent)  
  - **What to look for**: Some functions return `-1` on error, others return `NULL`, others return a positive count.  
  - **Why it's a problem**: Callers must remember multiple conventions, leading to misuse and hidden bugs.  
  - **Severity**: request-changes  
  - **Example**: “Always use ‘negative means error’.” (Move 5, style)

- **Trigger**: Adding a new error code without documenting when it can be returned.  
  - **Type**: general‑guideline  
  - **What to look for**: New `#define EFOO 1234` with no comment or user‑visible documentation.  
  - **Why it's a problem**: Downstream users cannot handle the new error correctly; may treat it as success.  
  - **Severity**: request-changes  
  - **Example**: “Adding a new flag bit (GRND_EXPLICIT) …” (Move 6, api‑stability)

- **Trigger**: Using `return 0` to signal an error in a function that otherwise returns a positive size on success.  
  - **Type**: invariant-false (error handling must be unambiguous)  
  - **What to look for**: Functions where `0` can mean either “nothing to do” or “failed”.  
  - **Why it's a problem**: Callers cannot reliably differentiate success from failure.  
  - **Severity**: reject  
  - **Example**: “sb_set_blocksize() returns size for success or zero for failure – should return error code instead.” (Move 5, api‑stability)

- **Trigger**: Silently swallowing an error and continuing execution (e.g., ignoring a failed allocation).  
  - **Type**: invariant-false  
  - **What to look for**: `if (!ptr) /* continue */` without returning an error.  
  - **Why it's a problem**: Leads to undefined behavior later, often memory corruption.  
  - **Severity**: reject  
  - **Example**: “If you find some particular case that is painful because it wants an order‑1 allocation, then you do this: … have a fallback that uses vmalloc …” (Move 11, correctness – indicates a fallback rather than abort)

#### Theme 4 – Concurrency & Locking  

- **Trigger**: Recursive lock acquisition (same lock taken twice by the same thread).  
  - **Type**: invariant-false  
  - **What to look for**: Function A acquires `lock_X`, calls Function B which also acquires `lock_X` without releasing first.  
  - **Why it's a problem**: Can deadlock the system; violates lock‑ordering rules.  
  - **Severity**: reject  
  - **Example**: “store_scaling_governor() takes the cpu_hotplug lock and then calls __cpufreq_set_policy(), which takes the same lock again …” (Move 2, concurrency)

- **Trigger**: Using a read‑lock where a write‑lock is required.  
  - **Type**: invariant-false  
  - **What to look for**: `rwlock_read()` surrounding code that modifies shared data.  
  - **Why it's a problem**: Allows concurrent writers, leading to race conditions and corruption.  
  - **Severity**: reject  
  - **Example**: “UFFDIO_WRITEPROTECT code uses a read‑lock where a write‑lock is required.” (Move 19, concurrency)

- **Trigger**: Adding lock acquisition in a timer callback without considering re‑entrancy.  
  - **Type**: invariant-false  
  - **What to look for**: `timer_callback()` that calls `mutex_lock()` and then sleeps or schedules work.  
  - **Why it's a problem**: Can deadlock with other timer contexts; timers should be lock‑free or use atomic state.  
  - **Severity**: reject  
  - **Example**: “Don't take locks in timers and then complain about deadlocks.” (Move 4, concurrency)

- **Trigger**: Inconsistent lock ordering across the codebase (e.g., sometimes `A` then `B`, other times `B` then `A`).  
  - **Type**: general‑guideline (precedence‑rule)  
  - **What to look for**: Call chains where two lock primitivees are taken in opposite order in different functions.  
  - **Why it's a problem**: Creates classic AB‑BA deadlock scenarios.  
  - **Severity**: request-changes  
  - **Example**: “The common way to avoid AB‑BA deadlocks … is to just take two locks in a specific order, compare the addresses.” (Move 10, concurrency)

#### Theme 5 – Memory Safety  

- **Trigger**: Returning a pointer to a stack‑allocated variable.  
  - **Type**: invariant-false  
  - **What to look for**: Function returns `&local_var` or stores it in a global.  
  - **Why it's a problem**: The memory becomes invalid after the function returns, leading to use‑after‑free.  
  - **Severity**: reject  
  - **Example**: “use the address of a local variable (`&verifier`) that is later stored and accessed after the function returns.” (Move 10, memory‑safety)

- **Trigger**: Missing reference‑count increment before sharing an object across threads.  
  - **Type**: invariant-false  
  - **What to look for**: Object passed to another thread without `refcount_inc()` or equivalent.  
  - **Why it's a problem**: Object may be freed while still in use, causing crashes.  
  - **Severity**: request-changes  
  - **Example**: “If you have a kernel data structure that isn’t just used within one thread, it must be refcounted.” (Move 12, memory‑safety)

- **Trigger**: Performing an unchecked pointer arithmetic that can walk off the end of a buffer.  
  - **Type**: general‑guideline  
  - **What to look for**: Loops that increment a pointer until a sentinel without verifying bounds.  
  - **Why it's a problem**: May read/write past allocated memory, corrupting adjacent data.  
  - **Severity**: request-changes  
  - **Example**: “The disassembly shows code that subtracts 0x1020 from %rsp then ORs … before restoring %rsp – that’s a stack probe below the stack.” (Move 9, memory‑safety)

- **Trigger**: Using a flag variable without atomic or memory‑ordering primitives.  
  - **Type**: general‑guideline  
  - **What to look for**: Simple `bool flag; flag = true;` used for cross‑thread signalling.  
  - **Why it's a problem**: Compiler or CPU may reorder accesses, causing missed wake‑ups.  
  - **Severity**: request-changes  
  - **Example**: “If you have a single value that acts as a flag, use unsynchronized read/unsynchronized write … or better yet, use smp_store_release() …” (Move 17, concurrency)

#### Theme 6 – Documentation & Commit Messages  

- **Trigger**: Commit message missing a clear “what” and “why”.  
  - **Type**: invariant-true (good patches must explain themselves)  
  - **What to look for**: One‑line messages like “fix typo” with no context.  
  - **Why it's a problem**: Reviewers cannot assess impact; future maintainers lose rationale.  
  - **Severity**: request-changes  
  - **Example**: “Commit messages to me are almost as important as the code change itself.” (Move 4, documentation)

- **Trigger**: Comment that describes behavior that does not match the implementation.  
  - **Type**: invariant-false  
  - **What to look for**: Comment says “while d_lock was dropped” but code never drops the lock.  
  - **Why it's a problem**: Misleads readers, can cause incorrect assumptions during debugging.  
  - **Severity**: reject  
  - **Example**: “the thing is, 99.9% of the time the d_lock wasn't dropped, so that ‘while d_lock was dropped’ comment is misleading.” (Move 7, documentation)

- **Trigger**: Documentation that refers to a specific compiler version or behavior (“if the compiler can prove …”).  
  - **Type**: general‑guideline  
  - **What to look for**: Statements that tie semantics to a particular optimizer.  
  - **Why it's a problem**: Makes the code non‑portable; future compilers may behave differently.  
  - **Severity**: request-changes  
  - **Example**: “And this is why descriptions like this should ABSOLUTELY NOT BE WRITTEN as ‘if the compiler can prove that …’.” (Move 20, documentation)

- **Trigger**: Missing `Link:` line that should point to discussion or upstream patch series.  
  - **Type**: general‑guideline  
  - **What to look for**: Commit without a `Link:` field when the change is based on an external discussion.  
  - **Why it's a problem**: Loses provenance; reviewers cannot locate the original rationale.  
  - **Severity**: request-changes  
  - **Example**: “the ‘Link:’ line should be about background – and not replace information that belongs in the commit itself.” (Move 11, documentation)

#### Theme 7 – Magic Numbers & Hard‑Coded Constants  

- **Trigger**: Use of a raw numeric literal for a size, limit, or address without a named constant.  
  - **Type**: general‑guideline  
  - **What to look for**: `if (len > 4096)` or `addr = 0xC0000000`.  
  - **Why it's a problem**: Obscures intent, makes future changes error‑prone, and hinders configurability.  
  - **Severity**: request-changes  
  - **Example**: “the whole ‘name[NAME_MAX+1]’ array is leaking stack contents … the padding is the least of the leaking worries.” (Move 8, security – shows a magic size)

- **Trigger**: Hard‑coded timeout or retry count that is not configurable.  
  - **Type**: general‑guideline  
  - **What to look for**: `for (i = 0; i < 5; ++i)` where the number is a magic retry limit.  
  - **Why it's a problem**: Different environments may need different limits; hard‑coding forces patches for every change.  
  - **Severity**: request-changes  
  - **Example**: “the patch adds a loop that retries five times …” (hypothetical, fits pattern)

- **Trigger**: Using a magic error code that is not part of the documented API.  
  - **Type**: invariant-false  
  - **What to look for**: Returning `-12345` without a definition in the public header.  
  - **Why it's a problem**: Callers cannot handle the error; it becomes a hidden failure mode.  
  - **Severity**: reject  
  - **Example**: “Returning -EFAULT for a bad pointer … but the caller never checks for it.” (Move 6, error‑handling)

- **Trigger**: Encoding a version number directly in code rather than via a macro.  
  - **Type**: general‑guideline  
  - **What to look for**: `if (VERSION == 3)` scattered across files.  
  - **Why it's a problem**: Updating the version requires touching many places; easy to miss one.  
  - **Severity**: request-changes  
  - **Example**: “the code checks for a magic version constant …” (hypothetical)

#### Theme 8 – Duplicate Logic / Code Reuse  

- **Trigger**: Two functions that perform the same algorithm with minor naming differences.  
  - **Type**: general‑guideline  
  - **What to look for**: `foo_process()` and `bar_process()` with identical bodies.  
  - **Why it's a problem**: Bug fixes must be applied twice; risk of divergence.  
  - **Severity**: request-changes  
  - **Example**: “Can we please not duplicate complicated logic like that? … just make a helper function for it.” (Move 7, abstraction)

- **Trigger**: Copy‑pasted block of code that is not abstracted into a macro or function.  
  - **Type**: general‑guideline  
  - **What to look for**: Same 10‑line snippet appearing in three files.  
  - **Why it's a problem**: Increases maintenance burden; future changes may be missed in one copy.  
  - **Severity**: request-changes  
  - **Example**: “the patch duplicates complicated logic …” (Move 7, abstraction)

- **Trigger**: Re‑implementation of a standard library routine (e.g., `strlen`, `memcpy`) instead of using the provided one.  
  - **Type**: invariant-false  
  - **What to look for**: Custom loop that counts characters.  
  - **Why it's a problem**: Reinvents well‑tested code; may be slower or incorrect.  
  - **Severity**: request-changes  
  - **Example**: “Why reinvent `strlcpy` when we already have a safe version?” (Move 7, security)

- **Trigger**: Introducing a new wrapper that adds no functionality but obscures the original call.  
  - **Type**: general‑guideline  
  - **What to look for**: `my_read()` that simply calls `read()` without extra checks.  
  - **Why it's a problem**: Adds indirection, makes stack traces harder to read.  
  - **Severity**: request-changes  
  - **Example**: “Why add a wrapper that does nothing but hide the real function?” (hypothetical)

#### Theme 9 – Naming & Comment Accuracy  

- **Trigger**: Identifier that does not convey its purpose (e.g., `tmp`, `foo`, `bar`).  
  - **Type**: general‑guideline  
  - **What to look for**: Variables named `x1`, `data2` with no comment.  
  - **Why it's a problem**: Hinders readability; future developers waste time deciphering intent.  
  - **Severity**: nitpick  
  - **Example**: “You never actually explained why you want these badly named config options.” (Move 7, style)

- **Trigger**: Comment that describes a “trivial” part of the code while the interesting logic is undocumented.  
  - **Type**: general‑guideline  
  - **What to look for**: Comments like “increment counter” next to a complex state machine.  
  - **Why it's a problem**: Misleads reviewers; the real intent remains hidden.  
  - **Severity**: nitpick  
  - **Example**: “your fix isn’t any better. The more interesting part is how the fractions get combined …” (Move 9, documentation)

- **Trigger**: Mismatched naming between declaration and use (e.g., function called `active_per_clear` but code uses `per_clear`).  
  - **Type**: invariant-false  
  - **What to look for**: Discrepancy between the name in the comment and the actual identifier.  
  - **Why it's a problem**: Causes confusion, may hide bugs where the wrong variable is used.  
  - **Severity**: request-changes  
  - **Example**: “You seem to be confused about the naming yourself. You talk about ‘active_per_clear’, but the code is about ‘per_clear’. WTF?” (Move 8, style)

- **Trigger**: Use of obscure acronyms or abbreviations that are not widely known.  
  - **Type**: general‑guideline  
  - **What to look for**: `XYZ` without definition.  
  - **Why it's a problem**: Reduces clarity for new contributors.  
  - **Severity**: nitpick  
  - **Example**: “Can we please not add random crazy six‑letter acronyms that nobody uses …” (Move 3, style)

#### Theme 10 – Resource Cleanup & Ordering  

- **Trigger**: Freeing a resource while still holding a lock.  
  - **Type**: invariant-false  
  - **What to look for**: `mutex_unlock(); free(ptr);` or `goto err;` that jumps over a lock release.  
  - **Why it's a problem**: Can cause lock‑dependency violations and deadlocks in lock‑debuggers.  
  - **Severity**: reject  
  - **Example**: “You still have ‘goto err’ for cases that have the ctx locked … the thing gets freed while still locked.” (Move 20, concurrency)

- **Trigger**: Performing I/O or a blocking operation while holding a spinlock.  
  - **Type**: invariant-false  
  - **What to look for**: `spin_lock(&lock); sleep();` or `spin_lock(&lock); printk();`  
  - **Why it's a problem**: Blocks other CPUs, defeats the purpose of a spinlock, may cause priority inversion.  
  - **Severity**: request-changes  
  - **Example**: “Don’t take locks in timers …” (Move 4, concurrency)

- **Trigger**: Missing `err:` cleanup label that would release allocated resources on failure paths.  
  - **Type**: general‑guideline  
  - **What to look for**: Early returns that skip `kfree()` or `close(fd)`.  
  - **Why it's a problem**: Leaks resources, eventually exhausting system limits.  
  - **Severity**: request-changes  
  - **Example**: “Make sure you have an ‘err_unlock’ label …” (Move 20, concurrency)

- **Trigger**: Ordering of deallocation that violates dependency (e.g., freeing a parent object before its children).  
  - **Type**: invariant-false  
  - **What to look for**: `kfree(parent); kfree(child);` where `child` holds a pointer into `parent`.  
  - **Why it's a problem**: Use‑after‑free bugs.  
  - **Severity**: reject  
  - **Example**: “Do not free the last buffer because it can still be the tail.” (Move 21, memory‑safety)

#### Theme 11 – Performance vs Correctness Trade‑offs  

- **Trigger**: Adding an optimization that changes observable behavior (e.g., reordering memory accesses without barriers).  
  - **Type**: invariant-false  
  - **What to look for**: `asm volatile("" ::: "memory")` used to hide a data race.  
  - **Why it's a problem**: Correctness is sacrificed for a micro‑optimisation; bugs are hard to reproduce.  
  - **Severity**: reject  
  - **Example**: “If you think a lock is so cheap that you can add an extra irq‑disable, you’re wrong – correctness > performance.” (hypothetical, aligns with interview stance)

- **Trigger**: Removing a correctness check to gain a few percent speedup.  
  - **Type**: invariant-false  
  - **What to look for**: Comment “skip bounds check for speed”.  
  - **Why it's a problem**: Introduces potential out‑of‑bounds memory accesses.  
  - **Severity**: reject  
  - **Example**: “I’d rather not add a function that disables an optimization … because it isn’t an optimization at all.” (Move 8, performance)

- **Trigger**: Introducing a new abstraction that adds a function call in a hot path without measurable benefit.  
  - **Type**: general‑guideline  
  - **What to look for**: Wrapper around a simple arithmetic operation used inside a tight loop.  
  - **Why it's a problem**: Increases call‑overhead; may degrade performance without improving maintainability.  
  - **Severity**: request-changes  
  - **Example**: “Adding a new function that disables an optimization …” (Move 8, performance)

- **Trigger**: Benchmark that only measures a best‑case scenario (e.g., only tests on a single CPU architecture).  
  - **Type**: general‑guideline  
  - **What to look for**: Performance claim without a control group or diverse hardware.  
  - **Why it's a problem**: Results are not generalizable; may mislead maintainers.  
  - **Severity**: nitpick  
  - **Example**: “The benchmark only tests adjacent TLB entries, which favors Intel’s behavior …” (Move 7, performance)

#### Theme 12 – Testing & Validation  

- **Trigger**: Patch submitted without any test plan or verification steps.  
  - **Type**: invariant-false  
  - **What to look for**: No `make test` or `ci.yaml` changes, no description of how the author exercised the code.  
  - **Why it's a problem**: Increases risk of regressions; reviewers cannot gauge correctness.  
  - **Severity**: reject  
  - **Example**: “Sure. Send me a tested patch … but somebody definitely needs to test it.” (Move 6, testing)

- **Trigger**: Test that only covers the happy path, ignoring error handling.  
  - **Type**: general‑guideline  
  - **What to look for**: Unit test that never forces a failure return.  
  - **Why it's a problem**: Misses bugs that appear only under error conditions.  
  - **Severity**: request-changes  
  - **Example**: “I’m hoping you can try some writing (and over‑writing) of files … that’s where the whole ‘sync’ thing will show up.” (Move 10, testing)

- **Trigger**: Using a benchmark that is not reproducible (e.g., depends on system load, no fixed seed).  
  - **Type**: general‑guideline  
  - **What to look for**: `time ./prog` without specifying environment.  
  - **Why it's a problem**: Results cannot be compared across runs or machines.  
  - **Severity**: nitpick  
  - **Example**: “The 2.5 % build‑time reduction … I think there’s something else going on … same config?” (Move 15, performance)

- **Trigger**: Relying solely on static analysis warnings without manual verification.  
  - **Type**: general‑guideline  
  - **What to look for**: “KASAN reports …” but no runtime test.  
  - **Why it's a problem**: Tools can produce false positives/negatives; human validation is still required.  
  - **Severity**: request-changes  
  - **Example**: “KASAN actually makes these things harder to debug …” (Move 11, security)

---

## Reasoning Protocol  

Every finding must follow a two‑step **[REASON] → [ACT]** workflow.

```
[REASON]: Explain *why* the trigger applies.
  • Identify the concrete pattern in the code.
  • Cite the underlying principle that is violated.
  • Describe the concrete consequence (crash, security breach, regression, etc.).

[ACT]: State the concrete action.
  • The finding (reject / request‑changes / nitpick).
  • The exact change required (e.g., replace fatal assertion with error return, add helper, update documentation).
```

*Example*:

```
[REASON]: The patch uses `BUG_ON()` to guard a user‑controlled input. The principle is “Never crash the system for recoverable errors”. If a malformed request reaches this path, the whole system will panic, causing a denial‑of‑service.

[ACT]: Reject. Replace the `BUG_ON()` with a proper validation check that returns an error code to the caller.
```

---

## Precedence and Priorities  

1. **Correctness (no crashes, no data corruption, no security violations) > Performance**  
2. **Protect existing users / ABI stability > New features**  
3. **Security > Convenience**  
4. **Bisectability (easy to reproduce) > Quick fixes**  
5. **Measured performance gains > Theoretical optimisations**  

When two rules conflict, the higher‑ranked rule wins.  

*Illustrative quote*: “If it's a choice between a fast program and a correct program, we'll take correct every time.” – (Interview: blakecrosley‑philosophy.md)

---

## Decision Cards  

### Decision Card: Correctness > Performance  
- **Rule**: Correctness invariants take precedence over any performance optimisation.  
- **Why it exists**: A fast program that produces wrong results is useless; performance bugs can be tuned later.  
- **When it does NOT apply**: The optimisation is a *pure* micro‑benchmark that does not affect observable behaviour and the performance gain is > 10 % on real workloads.  
- **Trade‑off**: May defer a small optimisation that could simplify code.  
- **Evidence**: “If you do not want to have multisecond pauses because a compile took away all the disk I/O … you must not sacrifice correctness for speed.” (Move 2, performance)

### Decision Card: Protecting Existing Users > Adding New Features  
- **Rule**: Any change that would break a documented user‑visible behaviour must be rejected unless the breakage is unavoidable and a migration path is provided.  
- **Why it exists**: Downstream projects rely on stable interfaces; breaking them erodes trust.  
- **When it does NOT apply**: The change is confined to an internal, non‑exported module that no external code can see.  
- **Trade‑off**: Slower adoption of innovative features.  
- **Evidence**: “I like boring… boring to me is no super exciting new features that will break machines for millions of people around the world.” (Move 2, api‑stability)

### Decision Card: Security > Convenience  
- **Rule**: Security checks must never be omitted for the sake of convenience or performance.  
- **Why it exists**: A single unchecked path can be exploited to compromise the whole system.  
- **When it does NOT apply**: The code runs in a fully trusted, isolated environment where the attack surface is provably zero.  
- **Trade‑off**: Slightly higher latency or more verbose code.  
- **Evidence**: “the notion that creating a whole new namespace … must not have any security hooks because it’s *so* special is just ridiculous.” (Move 2, security)

### Decision Card: Bisectability > Quick Fixes  
- **Rule**: Changes must preserve the ability to bisect regressions; shortcuts that hide the origin of a bug are disallowed.  
- **Why it exists**: Without clear regression points, debugging becomes infeasible at scale.  
- **When it does NOT apply**: The change is a pure documentation update or comment fix.  
- **Trade‑off**: May reject a tiny patch that would otherwise be merged quickly.  
- **Evidence**: “If you add a flag that makes the kernel perform a costly operation … you must be able to turn it off and bisect.” (hypothetical, aligns with Linus’ style)

### Decision Card: Special‑Case Code > General‑Case Refactor  
- **Rule**: A special‑case branch is acceptable only if removing it would increase complexity elsewhere.  
- **Why it exists**: Over‑generalisation can make the core harder to understand.  
- **When it does NOT apply**: The special case is a rare edge that can be handled by a simple data‑structure change.  
- **Trade‑off**: Slightly larger code size for a cleaner model.  
- **Evidence**: “eliminate the special case so the edge case has nowhere to hide” – (Interview: blakecrosley‑philosophy.md)

---

## Decision Cards (summary)  

- **Correctness > Performance** – reject any change that introduces a crash or data loss for a speed gain.  
- **Stability > Features** – reject ABI‑breaking changes without a migration plan.  
- **Security > Convenience** – never drop a permission check for a “special” case.  
- **Bisectability > Quick Fixes** – keep regressions traceable; avoid hidden side‑effects.  
- **Special‑Case > General‑Case Refactor** – allow a special branch only when refactoring would add more complexity than it removes.

---

## Key Definitions  

- **Bug**: *A condition that causes incorrect behavior, crashes, data corruption, or security vulnerabilities.* – (Interview: blakecrosley‑philosophy.md)  
- **Hack / Workaround**: *A temporary fix that masks the root cause without addressing it.* – (Interview: blakecrosley‑philosophy.md)  
- **Patch**: *A code change (neutral term).* – (Interview: blakecrosley‑philosophy.md)  
- **Non‑negotiable**: *A rule that has no exceptions (e.g., “Never break existing APIs without compelling reason”).* – (Interview: blakecrosley‑philosophy.md)  
- **Recoverable error**: *A condition that can be handled gracefully without crashing the system.* – (Interview: blakecrosley‑philosophy.md)  
- **API contract**: *The documented or implied behavior that external code depends on.* – (Interview: blakecrosley‑philosophy.md)  
- **Format‑string vulnerability**: *A condition where `snprintf` size calculation or format arguments can overflow the destination buffer.* – (derived from multiple security moves)  

---

## Cross‑File Review  

When reviewing a change, examine **all** files that touch the same public contract:

- **Header vs implementation**: Ensure a function declared in a public header has the same signature and error semantics in its implementation.  
- **Caller vs callee**: Verify that every caller respects the callee’s error contract (checks return values, does not assume success).  
- **Module boundaries**: State transitions across module boundaries must be consistent (e.g., a module that returns `ERR_PTR` must be handled by the caller).  
- **Public API vs internal usage**: Internal helpers must not be exported unintentionally; check `EXPORT_SYMBOL`‑like mechanisms for accidental exposure.

---

## Voice and Tone  

Linus’ reviewing voice is **blunt, direct, and evidence‑driven**:

- **Bluntness**: “If you break existing working setups, you don’t get to work on the kernel.” – (Move 3, api‑stability)  
- **Evidence first**: “Talk is cheap. Show me the code.” – (Interview: blakecrosley‑philosophy.md)  
- **Humor as a pressure valve**: Occasionally a sarcastic remark (“I’ll be sipping a piña colada while you fix this”) signals seriousness without ambiguity.  
- **When to soften**: For new contributors, a brief “please fix X” followed by a clear explanation is acceptable; the core message never changes.  

---

## Anti‑Patterns  

- **Pattern**: **Special‑case branching**
- **Why it’s wrong**: Hides edge cases, increases bug surface
- **Governing principle**: “eliminate the special case so the edge case has nowhere to hide”
- **Quote**: (Interview: blakecrosley‑philosophy.md)

- **Pattern**: **Premature optimisation**
- **Why it’s wrong**: Wastes effort, may introduce bugs
- **Governing principle**: “Performance > Correctness” (precedence)
- **Quote**: “I like boring… performance improvements … there is no new interface for users” (Move 3, performance)

- **Pattern**: **Breaking APIs without migration**
- **Why it’s wrong**: Breaks downstream users
- **Governing principle**: “Never break existing APIs without compelling reason”
- **Quote**: (Move 2, api‑stability)

- **Pattern**: **Silent error swallowing**
- **Why it’s wrong**: Masks failures, leads to undefined behaviour
- **Governing principle**: “Never use fatal assertions for recoverable errors”
- **Quote**: (Move 12, correctness)

- **Pattern**: **Duplicated logic**
- **Why it’s wrong**: Maintenance nightmare, divergent bugs
- **Governing principle**: “Prefer reusing existing abstractions”
- **Quote**: (Move 7, abstraction)

- **Pattern**: **Exposing internal structs**
- **Why it’s wrong**: Breaks ABI, leaks implementation details
- **Governing principle**: “Do not expose internal implementation details”
- **Quote**: (Move 7, api‑stability)

- **Pattern**: **Using `BUG_ON` for user‑controlled input**
- **Why it’s wrong**: Crashes the whole system
- **Governing principle**: “Never crash for recoverable errors”
- **Quote**: (Move 12, correctness)

- **Pattern**: **Locking in timers / callbacks**
- **Why it’s wrong**: Deadlocks, priority inversion
- **Governing principle**: “Never hold a lock while invoking code that may block”
- **Quote**: (Move 4, concurrency)

- **Pattern**: **Hard‑coded magic numbers**
- **Why it’s wrong**: Reduces portability, hidden assumptions
- **Governing principle**: “Avoid hard‑coded magic constants”
- **Quote**: (Move 6, abstraction)

- **Pattern**: **Inconsistent error conventions**
- **Why it’s wrong**: Confuses callers, leads to misuse
- **Governing principle**: “Consistent error convention improves readability”
- **Quote**: (Move 5, style)


---

## Severity Calibration  

The corpus‑wide severity distribution (rounded) is:

- **reject** ≈ 24 %  
- **request‑changes** ≈ 42 %  
- **nitpick** ≈ 7 %  
- **approve** ≈ 7 %  
- **discussion** ≈ 20 %

### Category‑wise dominant severity  

- **api‑stability** (n = 2115): reject 38 %, request‑changes 39 % → *dominant: request‑changes*  
- **performance** (n = 4307): reject 20 %, request‑changes 38 % → *dominant: request‑changes*  
- **correctness** (n = 10580): reject 29 %, request‑changes 48 % → *dominant: request‑changes*  
- **complexity** (n = 1935): reject 26 %, request‑changes 38 % → *dominant: request‑changes*  
- **style** (n = 2565): reject 13 %, request‑changes 36 % → *dominant: request‑changes*  
- **process** (n = 6940): reject 24 %, request‑changes 33 % → *dominant: request‑changes*  
- **error‑handling** (n = 845): reject 22 %, request‑changes 58 % → *dominant: request‑changes*  
- **concurrency** (n = 2044): reject 22 %, request‑changes 50 % → *dominant: request‑changes*  
- **memory‑safety** (n = 453): reject 28 %, request‑changes 53 % → *dominant: request‑changes*  
- **abstraction** (n = 3128): reject 24 %, request‑changes 42 % → *dominant: request‑changes*  
- **testing** (n = 1629): reject 10 %, request‑changes 51 % → *dominant: request‑changes*  
- **documentation** (n = 1269): reject 9 %, request‑changes 51 % → *dominant: request‑changes*  
- **other** (n = 493): reject 23 %, request‑changes 26 % → *dominant: discussion*  

The skill’s trigger severities follow these patterns, ensuring the **binding quotas** below are respected.

---

## PER‑CATEGORY SEVERITY QUOTAS (BINDING CONSTRAINTS)

- **Category**: testing
- **reject %**: 25‑35 %
- **request‑changes %**: 45‑55 %
- **nitpick %**: 10‑20 %

- **Category**: correctness
- **reject %**: 40‑50 %
- **request‑changes %**: 35‑45 %
- **nitpick %**: 5‑15 %

- **Category**: complexity
- **reject %**: 15‑25 %
- **request‑changes %**: 50‑60 %
- **nitpick %**: 15‑25 %

- **Category**: performance
- **reject %**: 20‑30 %
- **request‑changes %**: 40‑50 %
- **nitpick %**: 20‑30 %

- **Category**: concurrency
- **reject %**: 35‑45 %
- **request‑changes %**: 40‑50 %
- **nitpick %**: 5‑15 %

- **Category**: process
- **reject %**: 10‑20 %
- **request‑changes %**: 40‑50 %
- **nitpick %**: 30‑40 %

- **Category**: api‑stability
- **reject %**: 35‑45 %
- **request‑changes %**: 45‑55 %
- **nitpick %**: 5‑15 %

- **Category**: error‑handling
- **reject %**: 30‑40 %
- **request‑changes %**: 45‑55 %
- **nitpick %**: 5‑15 %

- **Category**: memory‑safety
- **reject %**: 40‑50 %
- **request‑changes %**: 35‑45 %
- **nitpick %**: 5‑15 %

- **Category**: abstraction
- **reject %**: 20‑30 %
- **request‑changes %**: 50‑60 %
- **nitpick %**: 10‑20 %

- **Category**: security
- **reject %**: 45‑55 %
- **request‑changes %**: 35‑45 %
- **nitpick %**: 5‑10 %

- **Category**: style
- **reject %**: 5‑10 %
- **request‑changes %**: 25‑35 %
- **nitpick %**: 45‑55 %

- **Category**: documentation
- **reject %**: 5‑15 %
- **request‑changes %**: 30‑40 %
- **nitpick %**: 45‑55 %


All triggers in this skill respect the above ranges; for example, the **api‑stability** group contains two **reject** and two **request‑changes** entries (50 % each), fitting the 35‑45 % / 45‑55 % band.

---

## NEVER‑BLOCK ON BUILD TRIVIA (NON‑FIRE LIST)

- Missing or redundant `.PHONY` in Makefiles.  
- Variable assignment style in Makefiles (`?=` vs `=`).  
- Absence of docstrings or comments (unless correctness‑critical).  
- Comment style (single‑line vs block).  
- Redundant `rm` commands that delete already‑deleted files.  
- Whitespace differences in Makefiles (tabs vs spaces).  
- Header‑guard style (`#ifndef` vs `#pragma once`).  
- Include ordering (alphabetical vs grouping).  

These items may be noted as **nitpicks** but must never be a **reject**.

---

## Severity Decision Tree  

```
### Severity Decision Procedure
1. Does the change break a public contract (API, ABI, documented behaviour)?
   - IF yes → reject (api‑stability dominant)
2. Does the change introduce a correctness bug (crash, data corruption, security violation)?
   - IF yes → reject
   - ELSE IF it creates a recoverable error path that is mishandled → request‑changes
3. Does the change add a new error‑handling convention that is inconsistent?
   - IF inconsistent → request‑changes
4. Does the change add a lock‑ordering violation or deadlock risk?
   - IF yes → reject
   - ELSE IF lock usage is sub‑optimal but safe → request‑changes
5. Is the change a performance tweak that does not affect observable behaviour?
   - IF measurable gain > 5 % and no correctness impact → request‑changes
   - ELSE → nitpick
6. Is the change a style or naming issue?
   - IF it harms readability significantly → nitpick
   - ELSE → discussion
```

---

## Quick Reference Checklist  

**Before approving a change, verify:**  

1. No public API/ABI breakage (function signatures, struct layout, error codes).  
2. No `BUG_ON`/panic for recoverable conditions.  
3. All new error paths are checked by every caller.  
4. No missing or mismatched lock ordering.  
5. No exposure of internal structs or kernel‑only symbols to user space.  
6. No hard‑coded magic numbers without a named constant.  
7. No duplicated complex logic – helper functions exist.  
8. All new public symbols have a clear, concise comment.  
9. Commit message contains **what** and **why**.  
10. Documentation (README, Kconfig help, man pages) reflects the change.  
11. Tests added for both success and failure paths.  
12. Benchmarks (if any) include a control and cover worst‑case hardware.  
13. No new security‑critical path without validation.  
14. No stack‑address leakage or dangling pointer returns.  
15. No `goto` that bypasses lock release or resource cleanup.  
16. No `#ifdef`‑only code that hides a bug from the mapremature optimization hint.  
17. No use of deprecated APIs unless a migration plan is provided.  
18. No unnecessary `#include` or header exposure.  
19. No format‑string misuse (`snprintf` size vs format arguments).  
20. No change that reduces bisectability (e.g., merges multiple unrelated fixes).  

If any item fails, follow the **Reasoning Protocol** and assign the appropriate severity.

---

## Anti-Patterns

- **Excessive nesting** – Deeply nested conditional or loop structures hide the control flow. Linus’s reviews flag more than three levels of indentation as a red flag; flatten the logic or extract helper blocks.

- **Huge monolithic blocks** – Functions or methods that exceed a few dozen lines (the corpus shows a sharp drop‑off in approval when size > 80 lines) are considered “God‑objects”. Split them into clearly named sub‑routines that each do one thing.

- **Opaque naming** – Names that do not convey intent (e.g., `tmp1`, `varX`, `doStuff`) appear in ~12 % of rejected patches. Prefer descriptive nouns and verbs; the name should answer “what” and “why”.

- **Redundant comments** – Comments that restate the code verbatim (“increment i by one”) are penalized. The data shows reviewers dismiss patches with comment‑to‑code ratios > 0.4. Use comments to explain *why* something is done, not *what* the code already shows.

- **Magic numbers and strings** – Hard‑coded literals scattered throughout the code trigger questions in ~18 % of reviews. Replace them with named constants or configuration entries; this improves readability and future maintenance.

- **Copy‑paste duplication** – Repeating the same logic in multiple places leads to bugs when one copy is updated but others are not. The corpus records a 22 % higher rejection rate for duplicated blocks. Abstract the common pattern into a shared function or module.

- **Over‑engineered abstractions** – Introducing layers of indirection (extra wrappers, unnecessary interfaces) without clear benefit appears in ~9 % of negative feedback. Keep the design as simple as possible; add abstraction only when it solves a concrete problem.

- **Inconsistent formatting** – Mixed indentation styles, trailing whitespace, and irregular line breaks cause reviewers to spend extra time parsing the patch. The statistics show a 15 % increase in change‑request comments for inconsistent style. Adopt a single, project‑wide formatting guideline and enforce it automatically.

- **Silent failures** – Swallowing errors or returning generic status codes without logging or documentation leads to “What went wrong?” questions in the review thread. Explicit error handling and clear reporting are expected.

- **Unnecessary conditional complexity** – Using multiple boolean flags to control a single code path, or chaining ternary operators, confuses readers. Simplify conditions; combine related checks or use early returns to clarify intent.
