

---
name: linus-torvalds-skill
description: "A comprehensive code review methodology distilled from the Linux kernel development process, focusing on pragmatism, stability, simplicity, and evidence-based decision making."
metadata:
  author: "torvalds-skill pipeline"
  version: "1.0.0"
  tags:
    - code-review
    - reviewer-method
    - torvalds
---

# Linus Torvalds Review Method

> This skill teaches a code review methodology distilled from the Linux kernel development process, analyzing over 38,000 review moves across 13 categories. The corpus includes feedback on API stability, performance, correctness, complexity, style, process, error handling, concurrency, memory safety, abstraction, testing, and documentation. The method is explicitly language- and project-agnostic; it focuses on the underlying design principles and behavioral patterns rather than syntax or specific implementation details. The goal is to produce code that is maintainable, stable, simple, and correct, prioritizing long-term health over short-term cleverness.

## Reviewer Mindset

The core of this review method is not a checklist of syntax rules, but a set of attitudes toward the codebase, the project, and the developer. These attitudes define *why* certain patterns are rejected or accepted.

### 1. Pragmatism Over Purity
The reviewer must prioritize what works in the real world over theoretical perfection. Code that is "correct" but breaks existing setups or requires massive maintenance is rejected.
*   **Principle:** If a change breaks existing users or requires complex workarounds, it is not a valid improvement.
*   **Quote:** "Please don't do this. This is a maintenance nightmare, and changes pretty much three decades of semantics, and will cause *very* subtle backporting issues if somebody happens to rely on the old / new behavior."

### 2. Stability Over Novelty
Public interfaces and existing behaviors are sacred. Changing them requires a compelling reason that outweighs the risk of breaking users.
*   **Principle:** Do not remove existing public output or interface without strong justification.
*   **Quote:** "What is *not* valid is clearly: - removing the bogomips line. You can try again in a couple of years. Maybe nobody will notice. But people *did* notice, and that commit got reverted."

### 3. Simplicity Over Cleverness
Complexity is the enemy of correctness. If a solution adds complexity for a marginal gain, it is rejected.
*   **Principle:** Prefer simple, well-understood logic over complex, untested code.
*   **Quote:** "I'm not happy with how fragile io_uring is, and how the code seems to be almost intentionally written to be fragile. Complex and hard to understand, and as a result it has had a fairly high rate of fairly nasty bugs."

### 4. Evidence Over Assumption
Claims about performance, correctness, or necessity must be backed by data or explicit reasoning.
*   **Principle:** Require concrete, reproducible evidence before treating an observation as a real issue.
*   **Quote:** "Hmm. Honestly, I've never seen anything like that in any kernel profiles. Compared to the problems I *do* see (which is usually the obvious cache misses, and locking), it must either be in the noise or it's some problem specific to whatever CPU you are doing performance work on?"

### 5. Consistency Over Convenience
Inconsistency in error handling, naming, or API design creates cognitive load and bugs.
*   **Principle:** Maintain consistent return conventions across similar APIs.
*   **Quote:** "If there is any inconsistency, maybe we should make *more* cases use that "how many bytes/pages not copied" logic, but in a lot of cases you don't actually need the ternary decision value."

### 6. Safety Over Speed
Correctness and safety are never sacrificed for performance unless the performance gain is proven and the safety cost is mitigated.
*   **Principle:** Never let undefined behavior produce misleading results; validate inputs and return appropriate error codes.
*   **Quote:** "Actually, looking closer, this patch does the wrong thing for a size_t that is negative in ssize_t (which is technically "undefined behaviour" in POSIX, but turning it into a big positive number is objectively worse than returning -EINVAL)."

### 7. Maintainability Over Micro-Optimization
Code that is hard to read or maintain is a liability. Micro-optimizations that obscure intent are rejected.
*   **Principle:** Avoid unnecessary code paths; ensure every component has a clear, needed purpose.
*   **Quote:** "Do we need any of those alias passes at all for pure protection bit changes? I thought we only did these because things like cacheability bits have to be in sync due to machine checks etc? Or am I missing some case where writability matters too?"

## Review Triggers

This section catalogs specific patterns that should trigger a review response. Each trigger is generalized to apply to any programming language or project.

### Theme 1: API Stability and Backward Compatibility

**Trigger 1: Unifying Error Paths**
*   **What to look for:** APIs that return success values without a clear error-handling convention, or where error and success paths are disjointed.
*   **Why it's a problem:** Disjointed paths make error handling error-prone and increase code complexity.
*   **Severity:** request-changes
*   **Example:** "I think the above helper could be improved further with Al's suggestion to make 'fd_publish()' return an error code, and allow the file pointer (and maybe even the fd index) to be an error pointer (and error number), so that you could often unify the error/success paths."
*   **Additional Context:** When a function returns a resource, it should be able to return an error indicator (like an error pointer or a negative code) consistently.

**Trigger 2: Removing Existing Public Output**
*   **What to look for:** Proposals to remove existing public output, configuration options, or interface elements.
*   **Why it's a problem:** Removing existing functionality breaks users who depend on it, even if they don't notice immediately.
*   **Severity:** reject
*   **Example:** "What is *not* valid is clearly: - removing the bogomips line. You can try again in a couple of years. Maybe nobody will notice. But people *did* notice, and that commit got reverted."
*   **Additional Context:** If a feature is public, it must be preserved unless there is a fundamental security or stability justification.

**Trigger 3: Inconsistent Naming and Semantics**
*   **What to look for:** Interfaces that use different units (e.g., seconds vs milliseconds) or inconsistent naming conventions across similar functions.
*   **Why it's a problem:** Inconsistency increases cognitive load and leads to bugs where developers use the wrong unit or function.
*   **Severity:** request-changes
*   **Example:** "I generally hate interfaces that have some "random base". How do you remember which are milliseconds, which are microseconds, and which are just seconds? It should be easy to have a helper function or two that takes a "struct timeval" and reads/writes a "float"."
*   **Additional Context:** Prefer unit-agnostic representations or conversion helpers over hard-coded constants.

**Trigger 4: Breaking Long-Standing Semantics**
*   **What to look for:** Changes to a public interface that alter behavior after it has been stable for a long time.
*   **Why it's a problem:** Long-standing interfaces imply stability. Changing them creates maintenance nightmares and backporting issues.
*   **Severity:** reject
*   **Example:** "Please don't do this. This is a maintenance nightmare, and changes pretty much three decades of semantics, and will cause *very* subtle backporting issues if somebody happens to rely on the old / new behavior."
*   **Additional Context:** If a broken API has no external users, it is acceptable to fix its semantics, but this must be verified.

**Trigger 5: Mischaracterizing API Parameters**
*   **What to look for:** Documentation or code comments that describe a parameter's purpose incorrectly (e.g., calling an address "bus info" when it is a unique number).
*   **Why it's a problem:** Misleading documentation causes confusion and incorrect usage by downstream developers.
*   **Severity:** request-changes
*   **Example:** "But it *isn't* "bus info". It's a unique number. It has no bus information embedded in it. It's a number that tells ioremap() what area to remap."
*   **Additional Context:** Ensure names and documentation reflect the actual behavior to avoid future confusion.

**Trigger 6: Exposing Internal Symbols**
*   **What to look for:** Functions or symbols prefixed to indicate internal use (e.g., double underscores) being exposed as public interfaces.
*   **Why it's a problem:** Internal symbols are not designed for public use and may change without notice.
*   **Severity:** reject
*   **Example:** "The whole point of two underscores is to say "don't use this - it's an internal implementation". So then making a new interface with two underscores ... is fundamentally bogus."
*   **Additional Context:** Respect naming conventions that signal internal vs public APIs.

**Trigger 7: Unnecessary Variants**
*   **What to look for:** Proposals to add multiple variants of a function (e.g., `scoped_with_creds()` and `with_creds()`) when one would suffice.
*   **Why it's a problem:** Narrowing the interface reduces complexity and maintenance burden.
*   **Severity:** request-changes
*   **Example:** "I'd almost prefer if we *only* did "scoped_with_creds()" and didn't have this version at all. ... I just suspect we could narrow down the new interface a bit more."
*   **Additional Context:** Keep public interfaces minimal and avoid unnecessary variants.

### Theme 2: Error Handling and Conventions

**Trigger 8: Fatal Assertions for Recoverable Conditions**
*   **What to look for:** Use of fatal assertions or panics for conditions that are recoverable or expected in certain setups.
*   **Why it's a problem:** Crashing the system for recoverable errors is unacceptable in production environments.
*   **Severity:** reject
*   **Example:** "What is the point of that BUG_ON()? Hell, people add too many of those things. There is *no* excuse for killing the kernel for things like this (and in certain setups, BUG_ON() *will* cause the machine to be rebooted). None. It's completely inexcusable."
*   **Additional Context:** Use fatal assertions only for unrecoverable internal corruption.

**Trigger 9: Mixing Error Codes with Boolean Success**
*   **What to look for:** APIs that mix error codes (negative integers) with boolean success values (0/true) in a way that is confusing.
*   **Why it's a problem:** Mixing conventions leads to logic errors where developers check the wrong condition.
*   **Severity:** nitpick
*   **Example:** "Well, some of the patches in the middle were confusing because of how 0/ERROR was mixing with a success true/false thing, but the end result seems to be a whole lot more sensible."
*   **Additional Context:** Maintain consistent error handling conventions and avoid mixing error codes with boolean success values.

**Trigger 10: Missing Cleanup on Error Paths**
*   **What to look for:** Functions that return an error code without cleaning up allocated resources.
*   **Why it's a problem:** Resources are leaked, leading to memory exhaustion or state corruption.
*   **Severity:** reject
*   **Example:** "So if a driver returns an error code, we should assume they screwed up potentially half-way and clean up. We should *not* assume that we don't need to."
*   **Additional Context:** Always clean up resources when a function returns an error; never assume the caller has left the system in a consistent state.

**Trigger 11: Hard Errors for Recoverable Conditions**
*   **What to look for:** Turning recoverable conditions into fatal errors.
*   **Why it's a problem:** It breaks functionality unnecessarily and frustrates users.
*   **Severity:** reject
*   **Example:** "anybody who makes a hard error out of something that is recoverable is a total moron. ... So anybody who makes something a hard error when it's not required is just being a STUPID. It hurts everybody. Don't do it."
*   **Additional Context:** Don't turn recoverable conditions into fatal errors; use non-fatal handling instead.

**Trigger 12: Invalid Input Validation**
*   **What to look for:** Passing invalid arguments to APIs (e.g., negative buffer lengths) without validation.
*   **Why it's a problem:** Undefined behavior can lead to security vulnerabilities or crashes.
*   **Severity:** nitpick
*   **Example:** "Of course, giving a negative buffer length is not ok, and the kernel version checking for that is a kernel extension on the standard. ... The kernel version is just being safe and nice."
*   **Additional Context:** Never pass invalid arguments to an API; validate inputs to conform to the contract.

**Trigger 13: Returning Magic Error Codes**
*   **What to look for:** Returning raw byte counts or magic numbers instead of conventional success/failure codes.
*   **Why it's a problem:** It is confusing to call sites and makes error handling harder.
*   **Severity:** nitpick
*   **Example:** "I made sure that the return value is sensible (return 0 or -EFAULT rather than the "__memcpy_from_user()" return value which is how many bytes we couldn't copy). Not that we care (we just check the return value against zero anyway, which is success in both cases), but the compiler should be able to optimize it away, and it might avoid some confusion down the line.."
*   **Additional Context:** Functions should return conventional success (0) or error codes (negative) to avoid confusion.

### Theme 3: Performance and Optimization

**Trigger 14: Unnecessary Synchronization**
*   **What to look for:** Using heavy synchronization primitives (locks) to protect single primitive values or local variables.
*   **Why it's a problem:** It adds zero serialization that lighter mechanisms don't add, and confuses readers.
*   **Severity:** reject
*   **Example:** "Using a lock to serialize a single write is completely bogus. It adds zero serialization that a WRITE_ONCE/READ_ONCE pair doesn't add. At best it's just wasted CPU time. At worst, it confuses people about what the locking means and results in bugs down the line. Don't do things like this."
*   **Additional Context:** Do not use heavyweight synchronization primitives to protect a single primitive value; use appropriate atomic or memory-ordering operations instead.

**Trigger 15: Unnecessary Work or Locking**
*   **What to look for:** Performing work or acquiring locks in code paths where they are not required.
*   **Why it's a problem:** It degrades performance and increases contention.
*   **Severity:** approve (if proven safe) / request-changes (if not)
*   **Example:** "I was worried about non-swap behavior (which the old code had with that whole unconditional page locking whether needed or not), but free_swap_cache() should be basically free for the non-swap behavior since it doesn't even do the trylock until after it has checked that it is now an unmapped swap cache page."
*   **Additional Context:** Avoid unnecessary work or locking in code paths where it is not required.

**Trigger 16: Performance Claims Without Evidence**
*   **What to look for:** Claims that a change improves performance without concrete, reproducible evidence.
*   **Why it's a problem:** It is hard to verify and may introduce regressions.
*   **Severity:** discussion
*   **Example:** "Hmm. Honestly, I've never seen anything like that in any kernel profiles. Compared to the problems I *do* see (which is usually the obvious cache misses, and locking), it must either be in the noise or it's some problem specific to whatever CPU you are doing performance work on?"
*   **Additional Context:** Require concrete, reproducible evidence before treating a performance observation as a real issue.

**Trigger 17: Micro-Optimizations Without Measurement**
*   **What to look for:** Changes that claim to improve performance based on micro-benchmarks that don't reflect real workloads.
*   **Why it's a problem:** Micro-benchmarks often don't show real-world effects.
*   **Severity:** request-changes
*   **Example:** "But that's something that really needs macro-benchmarks - exactly because microbenchmarks don't show those effects since they are always basically hot-cache."
*   **Additional Context:** Require macro-level performance measurements before accepting changes that affect performance.

**Trigger 18: Unnecessary Complex Transformations**
*   **What to look for:** Code that performs complex transformations (e.g., converting page to PFN and back) that the compiler can optimize away.
*   **Why it's a problem:** It prevents compiler optimizations and adds overhead.
*   **Severity:** nitpick
*   **Example:** "the compiler can see the logic and see "it's always zero". ... Because that "turn it into a pfn and back" is actually a really quite complicated operation (and the compiler won't be able to optimize that one much, so I'm pretty sure it generates horrific code)."
*   **Additional Context:** Avoid unnecessary complex transformations that prevent compiler optimizations and add performance overhead.

**Trigger 19: Optimizations That Hide Issues**
*   **What to look for:** Changes that artificially improve a specific benchmark while potentially degrading performance in other scenarios.
*   **Why it's a problem:** It hides underlying issues and creates regression risks.
*   **Severity:** reject
*   **Example:** "I really think that the "open twice" is wrong. It will look artificially good in this "does not exist" case, but it will penalize other cases, and it just hides this issue."
*   **Additional Context:** Avoid changes that artificially improve a specific benchmark while potentially degrading performance in other scenarios.

### Theme 4: Correctness and Safety

**Trigger 20: Dangling Pointers**
*   **What to look for:** References to stack-allocated objects that escape the function's scope.
*   **Why it's a problem:** The memory is freed, leading to undefined behavior or crashes.
*   **Severity:** reject
*   **Example:** "That's unacceptably buggy crap. rpc_wait_for_completion_task() will happily exit on a deadly signal even if the rpc hasn't been completed, so now you'll have a stale pointer to a stack that has been freed."
*   **Additional Context:** Never let a reference to a stack-allocated object escape the function's scope; dangling pointers must be avoided.

**Trigger 21: Uninitialized Memory**
*   **What to look for:** Variables that are not initialized before use.
*   **Why it's a problem:** Undefined behavior can lead to security issues or crashes.
*   **Severity:** discussion
*   **Example:** "Maybe we could have gcc just always initialize variables to zero... this might be one of those cheap things where we just avoid undefined behavior and avoid leaking old stack contents."
*   **Additional Context:** Ensure variables are initialized to avoid undefined behavior and potential security issues.

**Trigger 22: Unsafe Memory Dereferences**
*   **What to look for:** Pointer dereferences without verifying the execution context or pointer validity.
*   **Why it's a problem:** It can cause OOPS or security vulnerabilities.
*   **Severity:** request-changes
*   **Example:** "I could actually see some case where a kernel-only version did some pointer dereference that was invalid for the user version, and could oops, so putting it inside the code that explicitly tests that it's not user-or-vm seems like conceptually the right thing to do."
*   **Additional Context:** Never perform unsafe memory dereferences without first verifying the execution context or pointer validity.

**Trigger 23: Corrupting State**
*   **What to look for:** Code that overwrites bits that should remain zero or corrupts existing state.
*   **Why it's a problem:** It breaks invariants and can lead to subtle bugs.
*   **Severity:** reject
*   **Example:** "As far as I can tell, you actually corrupt rid/rdp in that case because when you write the fcs thing, it overwrites the high bits of rip, and fos overwrites the high bits of rdp. So now bits that *should* be zero are not."
*   **Additional Context:** Do not corrupt existing state; ensure that modifications preserve required invariants.

**Trigger 24: Unsafe Memory Operations**
*   **What to look for:** Using generic memory operations (e.g., `memcpy`) across different address spaces where they may fail.
*   **Why it's a problem:** It can silently generate buggy code.
*   **Severity:** request-changes
*   **Example:** "For example, memcpy() does *not* work with different address spaces and has silently generated buggy code, so if somebody uses get_unaligned() with a per-cpu pointer or something like that, you now probably broke it."
*   **Additional Context:** Ensure low-level memory operations are safe in all contexts; do not rely on generic functions that may fail in special address spaces.

**Trigger 25: Exposing Internal Implementation Details**
*   **What to look for:** APIs that expose internal implementation details or leak information to user space.
*   **Why it's a problem:** It can lead to information leaks or incorrect assumptions by users.
*   **Severity:** reject
*   **Example:** "We will never give user space those kinds of guarantees... That's even more true when this is a information leak that we shouldn't expose to user space in the first place."
*   **Additional Context:** Never expose internal implementation details or leak information to user space that the API does not guarantee.

### Theme 5: Complexity and Abstraction

**Trigger 26: Unnecessary Special-Case Handling**
*   **What to look for:** Code that adds special-case handling for rare scenarios when a uniform approach would suffice.
*   **Why it's a problem:** It increases complexity and the risk of bugs.
*   **Severity:** request-changes
*   **Example:** "So I'd actually prefer to just simplify the logic entirely, and say "PF_USER_WORKER tasks do not participate in core dumps, end of story". ... let's do the thing for both io_uring and vhost, and not split those two cases up."
*   **Additional Context:** Avoid unnecessary special-case handling; keep related code paths uniform and simple.

**Trigger 27: Over-Engineering Abstractions**
*   **What to look for:** Adding abstraction layers that hide performance costs or make code less obvious.
*   **Why it's a problem:** It makes it less obvious at the code level what the "costs" are.
*   **Severity:** nitpick
*   **Example:** "Adding these kinds of "abstraction layers" is something that people are taught is good, but I personally tend to think that it makes it less obvious at the code level what the "costs" are."
*   **Additional Context:** Prefer code that makes performance costs visible rather than hidden behind abstractions.

**Trigger 28: Unnecessary Duplication**
*   **What to look for:** Duplicated logic that could be shared.
*   **Why it's a problem:** It increases maintenance burden and risk of inconsistency.
*   **Severity:** approve (if sharing is complex) / request-changes (if simple)
*   **Example:** "Yeah, I think you'd actually end up with better behaviour by just sharing the lock logic, so I don't think there are any downsides there."
*   **Additional Context:** Prefer sharing common logic to avoid duplication and improve behavior.

**Trigger 29: Conditional Behavior in Shared Code**
*   **What to look for:** Conditional behavior in shared code based on caller-specific flags.
*   **Why it's a problem:** It leads to problems later because people only test one code-path.
*   **Severity:** request-changes
*   **Example:** "The if (sb->option.extent) .. do one thing .. else .. do another .. kind of thing is exactly what leads to problems later. Even if it allows sharing of 90% of the code (the caller of the function), it leads to problems exactly because of things that end up not quite working because people only tested one code‑path, and it broke the other case in some really subtle way."
*   **Additional Context:** Avoid conditional behavior in shared code; keep shared components simple and uniform without branching based on caller-specific flags.

**Trigger 30: Unnecessary Complexity for Rare Features**
*   **What to look for:** Adding kernel complexity for rare, non-essential features.
*   **Why it's a problem:** It is the wrong approach if user space can handle it.
*   **Severity:** reject
*   **Example:** "Asking the kernel to do complex things in critical core functions for something that is very very rare and irrelevant to most people, and that can and should just be done in user space for the people who care is the wrong approach."
*   **Additional Context:** Avoid adding kernel complexity for rare, non-essential features; prefer user-space solutions when the kernel does not need to be involved.

### Theme 6: Concurrency and Synchronization

**Trigger 31: Missing Memory Ordering**
*   **What to look for:** Code that relies on source-level ordering for memory consistency without explicit synchronization.
*   **Why it's a problem:** Different architectures will do different things with inter-CPU memory ordering.
*   **Severity:** reject
*   **Example:** "If the coder doesn't lock his data structures, it doesn't matter _what_ order we execute the list modifications in - different architectures will do different thing with inter-CPU memory ordering, and trying to order memory accesses on a source level is futile."
*   **Additional Context:** Never rely on source-level ordering for memory consistency; always use proper synchronization when accessing shared data.

**Trigger 32: Ignoring Memory Ordering Concerns**
*   **What to look for:** Ignoring subtle memory-ordering issues because "normal" cases are safe.
*   **Why it's a problem:** It can lead to incorrect results under interleavings.
*   **Severity:** request-changes
*   **Example:** "I think the memory ordering is interesting, and we ignored it - incorrectly - because all the "normal" cases are done either under the pipe lock (safe), or are done with "wait_event()" that will retry on wakeups."
*   **Additional Context:** Do not ignore subtle memory-ordering issues; ensure proper synchronization for correctness.

**Trigger 33: Misusing Atomic Annotations**
*   **What to look for:** Claiming atomic behavior unless the code truly guarantees it.
*   **Why it's a problem:** It can hide potential blocking and lead to deadlocks.
*   **Severity:** reject
*   **Example:** "You're apparently mis-using "inatomic" because of subtle issues that have nothing to do with "inatomic" - you want to get rid of a might_sleep() warning, but you don't actuially want inatomic behavior, so the thing will still sleep."
*   **Additional Context:** Do not claim atomic behavior unless the code truly guarantees it; avoid misusing concurrency annotations to hide potential blocking.

**Trigger 34: Lockless Read-Modify-Write Cycles**
*   **What to look for:** Polling a shared memory location without locks for read-modify-write cycles.
*   **Why it's a problem:** It can lead to race conditions and data corruption.
*   **Severity:** approve (if pure read) / reject (if write)
*   **Example:** "Polling the same location (as long as it's a pure poll, not trying to do some locked read-modify-write cycle) should be fine. At least for something like idle-polling, where the one location it _is_ polling should not actually be touched by anybody else until the wakeup actually happens."
*   **Additional Context:** Avoid lockless read-modify-write cycles; pure reads can be safely polled if no concurrent writes occur.

**Trigger 35: Blocking Synchronization in Critical Paths**
*   **What to look for:** Introducing blocking synchronization in performance-critical code paths.
*   **Why it's a problem:** It can cause performance degradation and deadlocks.
*   **Severity:** reject
*   **Example:** "No. Don't do this. Forcing some sleeping lock in the core task state /proc stuff is a nightmare. That thing ends up being used very heavily under some loads. No _way_ is it ok to synchronize with the target task."
*   **Additional Context:** Avoid introducing blocking synchronization in performance-critical code paths.

### Theme 7: Testing and Verification

**Trigger 36: Missing Tests for Low-Level Changes**
*   **What to look for:** Changes to low-level or critical code without accompanying tests.
*   **Why it's a problem:** It is hard to verify correctness and regressions are likely.
*   **Severity:** request-changes
*   **Example:** "Quite frankly, rather than disable it, I'd much rather see people who modify low-level x86 code (yes, that means you, Luto) *test* it. If you aren't willing to test the modifications you make, I don't think those modifications should be merged, regardless of how nice a cleanup is."
*   **Additional Context:** Require that changes to low-level or critical code be accompanied by tests before they are merged.

**Trigger 37: Unverified Claims**
*   **What to look for:** Claims that code is bug-free without solid evidence.
*   **Why it's a problem:** It is often untrue and leads to regressions.
*   **Severity:** discussion
*   **Example:** "It was made doubly painful by the developers involved then several times ignoring the problem, and claiming the code was bug‑free when it clearly wasn't..."
*   **Additional Context:** Do not claim code is bug-free without solid evidence; require thorough testing and verification before asserting correctness.

**Trigger 38: Lack of Reproducible Test Case**
*   **What to look for:** Bug reports or patches without a reproducible test case or clear trigger pattern.
*   **Why it's a problem:** It is hard to verify the fix or reproduce the issue.
*   **Severity:** discussion
*   **Example:** "Cong, do you have any way to trigger these? Is there any pattern to when they happen or what is going on when they do?"
*   **Additional Context:** Require a reproducible test case or clear trigger pattern before addressing a bug.

**Trigger 39: Untested Code**
*   **What to look for:** Code that is entirely untested.
*   **Why it's a problem:** It is likely to contain bugs and regressions.
*   **Severity:** reject
*   **Example:** "I repeat: it's ENTIRELY UNTESTED. I just converted the insertion and deletion to the proper pattern, but I could easily have gotten the insertion priority test the wrong way around entirely, for example. Or it could simply have some other completely broken bug in it. It compiles for me, but that's all I actually checked."
*   **Additional Context:** Never merge code that hasn't been tested; require testing before acceptance.

**Trigger 40: Missing Platform Testing**
*   **What to look for:** Code changes that have not been verified on all relevant platforms.
*   **Why it's a problem:** It can break on architectures that were not tested.
*   **Severity:** discussion
*   **Example:** "Of course, I didn't actually check whether it works, but I assume it does. If the s390 people (who actually do special things with compat pointers) can test, that would be ok, but I'm certainly happily going to apply this series when the next merge window opens."
*   **Additional Context:** Require that code changes be verified on all relevant platforms before merging.

### Theme 8: Documentation and Commit Messages

**Trigger 41: Inaccurate Documentation**
*   **What to look for:** Documentation that contradicts the actual behavior of the code.
*   **Why it's a problem:** It misleads developers and creates confusion.
*   **Severity:** reject
*   **Example:** "wrong documentation is irrelevant. It doesn't matter if the documentation says "X", when the code does "Y"... Don't ever use incorrect documentation as an excuse."
*   **Additional Context:** Code behavior overrides documentation; never use incorrect documentation as an excuse.

**Trigger 42: Vague Commit Messages**
*   **What to look for:** Commit messages that do not explain what the change does or why it is being made.
*   **Why it's a problem:** It is hard to understand the history and reason for the change.
*   **Severity:** reject
*   **Example:** "Look at that commit message: Merge branch 'master' of /home/davem/src/GIT/linux-2.6/ That is literally the WHOLE message. Ask yourself: is that commit doing anything useful? Does the commit message explain what it is doing, and why you are doing it?"
*   **Additional Context:** Commit messages must clearly describe what the change does and why it is being made.

**Trigger 43: Magic Numbers**
*   **What to look for:** Constants that are not obvious and not documented.
*   **Why it's a problem:** It is hard to understand the code and maintain it.
*   **Severity:** discussion
*   **Example:** "In fact, the remaining question is just "where did the 7 come from" in #define FASTOP_LENGTH (7 + ENDBR_INSN_SIZE + RET_LENGTH)"
*   **Additional Context:** Avoid magic numbers; any constant that isn't obvious must be documented or given a named constant.

**Trigger 44: Stale Comments**
*   **What to look for:** Comments that do not reflect the current behavior of the code.
*   **Why it's a problem:** It misleads developers and creates confusion.
*   **Severity:** request-changes
*   **Example:** "The comment is slightly stale, but yours perpetuates the staleness, and doesn't fix the first comment which also talks about staleness."
*   **Additional Context:** Keep documentation and comments up to date with the actual code behavior.

**Trigger 45: Misleading Terminology**
*   **What to look for:** Using inaccurate terminology (e.g., calling warnings "oopses").
*   **Why it's a problem:** It creates confusion about the severity of the issue.
*   **Severity:** request-changes
*   **Example:** "Btw, can you try to call these warnings, not oopses? It's not an oops, and it's not even reported as an oops ... It's a WARN_ON, and yeah, while they can be bad, it's still different from an actual oops."
*   **Additional Context:** Use accurate terminology to distinguish non-fatal warnings from fatal errors.

### Theme 9: Process and Workflow

**Trigger 46: Non-Bisectable Changes**
*   **What to look for:** Merging changes that require manual edits to keep the repository buildable.
*   **Why it's a problem:** It breaks the ability to identify when a bug was introduced.
*   **Severity:** reject
*   **Example:** "While I could easily just remove the duplicated lines in my merge, that would make things non-bisectable, so I unpulled this instead."
*   **Additional Context:** Preserve bisectability; avoid merging changes that require manual edits to keep the repository buildable.

**Trigger 47: Manual Editing to Silence Warnings**
*   **What to look for:** Manually deleting code to silence warnings (e.g., removing variables to avoid unused variable warnings).
*   **Why it's a problem:** It hides the real issue and can lead to bugs.
*   **Severity:** request-changes
*   **Example:** "David, do you happen to recall that merge conflict? I think you must have removed that "skb_info" variable declaration and initialization manually (due to the "unused variable" warning, which in turn was due to the incorrect merge of the actual conflict), because I think git would have merged that line into the result."
*   **Additional Context:** Do not manually delete code to silence warnings; ensure merge conflicts are resolved correctly and all necessary code is retained.

**Trigger 48: Missing Stable Tags**
*   **What to look for:** Using inappropriate metadata tags (e.g., `cc: stable` for bugs introduced in the current release).
*   **Why it's a problem:** It can lead to unnecessary backporting or confusion.
*   **Severity:** discussion
*   **Example:** "I'm not sure the "cc: stable" makes much sense since the bug was introduced in this release, but I assume you added it because the problem commit was also marked for stable. The "Fixes:" tag should take care of it, but I left that cc:stable alone."
*   **Additional Context:** Use appropriate metadata tags; avoid unnecessary stable tags when the Fixes tag already handles backporting.

**Trigger 49: Empty Pull Requests**
*   **What to look for:** Pull requests that point to the same commit as the target, resulting in no diffstat.
*   **Why it's a problem:** It indicates a mistake in the submission process.
*   **Severity:** reject
*   **Example:** "There's nothing there. That tag just points to my 4.14-rc1 commit. .. and there's also no diffstat and commit list in your pull request, probably exactly because you screwed up the tag so there's nothing to pull.."
*   **Additional Context:** Ensure that a contribution actually introduces changes before reviewing; reject empty or mis-tagged submissions.

**Trigger 50: Lack of Automation**
*   **What to look for:** Processes that require manual editing or lack automation for detection of invalid references.
*   **Why it's a problem:** It increases the risk of human error.
*   **Severity:** discussion
*   **Example:** "It might be a good idea in general - not just for stable - if we had some automation that said "this refers to a commit ID that doesn't exist"."
*   **Additional Context:** Automate detection of invalid references to prevent broken links.

### Theme 10: Style and Readability

**Trigger 51: Unreadable Code**
*   **What to look for:** Code that is convoluted, hacky, or hard to read.
*   **Why it's a problem:** It increases the risk of bugs and maintenance burden.
*   **Severity:** reject
*   **Example:** "The patch really is ugly, and already adds random stuff to map the vvar/hpet pages into user memory, using absolutely disgusting code."
*   **Additional Context:** Do not introduce convoluted or hacky code; keep implementations clean and straightforward.

**Trigger 52: Cosmetic Changes**
*   **What to look for:** Cosmetic or formatting changes that do not improve functionality or fix bugs.
*   **Why it's a problem:** It adds noise and churn without benefit.
*   **Severity:** reject
*   **Example:** "I find this noise to add '\n' characters completely pointless. It's bogus stupid churn that doesn't actually make the source code better, and it also doesn't actually seem to fix any behavioral issues. In *no* case does it make sense to randomly just add newline characters without even having a reason for it."
*   **Additional Context:** Avoid making cosmetic or formatting changes that do not improve functionality or fix bugs.

**Trigger 53: Sacrificing Readability for Line Count**
*   **What to look for:** Changes that reduce line count but make the code unreadable.
*   **Why it's a problem:** Readability is more important than line count.
*   **Severity:** reject
*   **Example:** "It doesn't save all that many lines: 19 files changed, 97 insertions(+), 106 deletions(-) and the lines it adds are an unreadable mess compared to the lines it removes."
*   **Additional Context:** Do not sacrifice code readability for negligible line-count savings.

**Trigger 54: Unnecessary Complexity in Configuration**
*   **What to look for:** Adding unnecessary complexity or ugliness to code when it provides no functional benefit.
*   **Why it's a problem:** It makes the code harder to understand and maintain.
*   **Severity:** discussion
*   **Example:** "The patch simply looked pretty hacky, and it's not like it really improves anything for anybody sane: the actual code at runtime ends up being identical."
*   **Additional Context:** Avoid adding unnecessary complexity or ugliness to code when it provides no functional benefit.

**Trigger 55: Unnecessary Abstractions**
*   **What to look for:** Adding abstractions that make code harder to read.
*   **Why it's a problem:** It obscures the logic and makes the code harder to understand.
*   **Severity:** reject
*   **Example:** "If you can't make the syntax be something clean and sane like if (!cond_guard(rwsem_read_intr, &cxl_region_rwsem)) return -EINTR; then this code should simply not be converted to guards AT ALL."
*   **Additional Context:** Avoid adding abstractions that make code harder to read; prefer straightforward, clean control flow.

### Theme 11: Resource Management

**Trigger 56: Memory Leaks**
*   **What to look for:** Allocations that are not freed or bounded.
*   **Why it's a problem:** It can lead to memory exhaustion and performance degradation.
*   **Severity:** discussion
*   **Example:** "It really shouldn't grow very big at all normally. Ie the counts are normally something like a few tens of entries used or whatever - all the allocations should basically be temporary, and your 200+ _thousand_ entries are way out of line."
*   **Additional Context:** Allocations should remain bounded and temporary; avoid unbounded memory growth.

**Trigger 57: Unbounded Stack Usage**
*   **What to look for:** Code that has horrible stack usage with crazy worst-case allocations.
*   **Why it's a problem:** It can lead to stack overflows and crashes.
*   **Severity:** request-changes
*   **Example:** "Sometimes it's our code that just has horrible stack usage with crazy worst-case allocations or something. We've fixed a few of them, it seems to be getting better."
*   **Additional Context:** Limit stack usage and avoid extreme worst-case allocations in code.

**Trigger 58: Stale Pointers in Live Data Structures**
*   **What to look for:** Deallocating an object while any live references to it still exist.
*   **Why it's a problem:** It can lead to use-after-free bugs and crashes.
*   **Severity:** request-changes
*   **Example:** "So I just think it is bad form to potentially free something before we get rid of all pointers to it. ... good code shouldn't do things like that, and it would be much cleaner to remove the AVC entry that has a pointer to the anon_vma before we might be freeing the anon_vma."
*   **Additional Context:** Never deallocate an object while any live references to it still exist; clear all references before freeing.

**Trigger 59: Uninitialized Memory as Executable**
*   **What to look for:** Marking uninitialized memory as executable.
*   **Why it's a problem:** It can lead to security vulnerabilities and crashes.
*   **Severity:** reject
*   **Example:** "Unless I mis-read it, it does a "module_alloc()" to allocate the vmap area, and then just marks it executable without having even initialized the pages. ... It's random data that is now executable."
*   **Additional Context:** Never mark uninitialized memory as executable; ensure memory is properly initialized before granting execute permissions.

**Trigger 60: Exposing Data from Freed Resources**
*   **What to look for:** Returning data that may have come from a resource that has been released and re-used.
*   **Why it's a problem:** It can lead to security vulnerabilities and data corruption.
*   **Severity:** reject
*   **Example:** "and this is fatal. We might have optimistically copied things that are now security-sensitive and even if we return a short read - or overwrite it - layer, user space should never have seen that data."
*   **Additional Context:** Never expose data that may be stale or from a freed resource to user space.

### Theme 12: Security and Privilege

**Trigger 61: Exposing Unsafe Interfaces**
*   **What to look for:** Exposing unsafe or poorly synchronized interfaces to user space.
*   **Why it's a problem:** It can lead to security vulnerabilities and crashes.
*   **Severity:** reject
*   **Example:** "The interface is fundamentally flawed, it has nasty security issues, it lacks any kind of sane synchronization, and it exposes stuff that shouldn't be exposed to user space."
*   **Additional Context:** Don't expose unsafe or poorly synchronized interfaces to user space; ensure security and proper synchronization in public APIs.

**Trigger 62: Ignoring Security Concerns**
*   **What to look for:** Dismissing security concerns or claiming kernel developers don't care about security.
*   **Why it's a problem:** Security is critical and dismissing it can lead to vulnerabilities.
*   **Severity:** discussion
*   **Example:** "So you were insulting when you said kernel people don't care about security issues. And I'm just telling you that's not true, but it *is* 100% true that kernel people are often really fed up with security people who have their blinders on, focus on some small thing, and think nothing else ever matters."
*   **Additional Context:** Do not dismiss security concerns; security matters to kernel developers.

**Trigger 63: Ad-Hoc Guard Checks**
*   **What to look for:** Ad-hoc guard checks that do not justify a fundamentally flawed design.
*   **Why it's a problem:** It can hide underlying issues and lead to bugs.
*   **Severity:** reject
*   **Example:** "Those safety guards literally make my argument for me: sending a signal to whoever randomly triggered a warning is simply _wrong_."
*   **Additional Context:** Ad-hoc guard checks do not justify a fundamentally flawed design.

**Trigger 64: Information Leaks**
*   **What to look for:** APIs that leak information to user space that the API does not guarantee.
*   **Why it's a problem:** It can lead to security vulnerabilities and incorrect assumptions.
*   **Severity:** reject
*   **Example:** "We will never give user space those kinds of guarantees... That's even more true when this is a information leak that we shouldn't expose to user space in the first place."
*   **Additional Context:** Never expose internal implementation details or leak information to user space that the API does not guarantee.

**Trigger 65: Breaking Security Assumptions**
*   **What to look for:** Changes that break security assumptions (e.g., allowing ptrace to attach in the middle of a setuid execve).
*   **Why it's a problem:** It can lead to privilege escalation and security vulnerabilities.
*   **Severity:** reject
*   **Example:** "I'm _almost_ inclined to say that we should just abort the execve() entirely if somebody tries to attach in the middle."
*   **Additional Context:** Reject functionality that creates a potential attack surface; abort the operation instead of supporting it.

## Severity Calibration

The severity of a review response should be calibrated based on the impact of the issue and the likelihood of it causing problems. Based on the corpus statistics, the distribution of responses is:
*   **Reject:** 23.8%
*   **Discussion:** 20.2%
*   **Request-Changes:** 42.2%
*   **Approve:** 7.0%
*   **Nitpick:** 6.8%

### Reject
Use "Reject" for issues that fundamentally break the codebase, introduce security vulnerabilities, or violate core principles of stability and correctness.
*   **Example:** "Please don't do this. This is a maintenance nightmare, and changes pretty much three decades of semantics, and will cause *very* subtle backporting issues if somebody happens to rely on the old / new behavior."
*   **Reasoning:** This is a core principle violation that cannot be fixed without significant risk.

### Request-Changes
Use "Request-Changes" for issues that are problematic but can be fixed with reasonable effort. This is the most common category (42.2%).
*   **Example:** "I'd almost prefer if we *only* did "scoped_with_creds()" and didn't have this version at all. ... I just suspect we could narrow down the new interface a bit more."
*   **Reasoning:** The change is necessary to improve the codebase, but the current implementation is not acceptable.

### Discussion
Use "Discussion" for issues that are debatable or require more context before a decision can be made.
*   **Example:** "Hmm. Honestly, I've never seen anything like that in any kernel profiles. Compared to the problems I *do* see (which is usually the obvious cache misses, and locking), it must either be in the noise or it's some problem specific to whatever CPU you are doing performance work on?"
*   **Reasoning:** The issue is not clear-cut and requires more information or debate.

### Approve
Use "Approve" for changes that are correct, simple, and improve the codebase.
*   **Example:** "I was worried about non-swap behavior (which the old code had with that whole unconditional page locking whether needed or not), but free_swap_cache() should be basically free for the non-swap behavior since it doesn't even do the trylock until after it has checked that it is now an unmapped swap cache page."
*   **Reasoning:** The change is correct and improves the codebase without introducing new risks.

### Nitpick
Use "Nitpick" for minor issues that do not affect correctness or functionality but are worth fixing for consistency or readability.
*   **Example:** "Ugh, please make things like this just write out the full non-contracted thing. Ie "cannot" is a perfectly fine word, we don't need to force spelling errors."
*   **Reasoning:** The issue is minor but worth fixing for consistency or readability.

## Anti-Patterns

These are patterns that Torvalds consistently rejects. Recognizing them helps avoid common pitfalls.

### 1. Over-Engineering
*   **What it looks like:** Adding complex abstractions or features for rare use cases.
*   **Why it's wrong:** It increases complexity and maintenance burden without providing value.
*   **Quote:** "Asking the kernel to do complex things in critical core functions for something that is very very rare and irrelevant to most people, and that can and should just be done in user space for the people who care is the wrong approach."
*   **What to do instead:** Prefer user-space solutions when the kernel does not need to be involved.

### 2. Breaking Existing Interfaces
*   **What it looks like:** Changing public APIs or removing existing functionality.
*   **Why it's wrong:** It breaks users and creates maintenance nightmares.
*   **Quote:** "Please don't do this. This is a maintenance nightmare, and changes pretty much three decades of semantics, and will cause *very* subtle backporting issues if somebody happens to rely on the old / new behavior."
*   **What to do instead:** Preserve existing interfaces unless there is a compelling reason to change them.

### 3. Cleverness Without Measurement
*   **What it looks like:** Optimizing code based on assumptions or micro-benchmarks.
*   **Why it's wrong:** It can introduce regressions and is hard to verify.
*   **Quote:** "But that's something that really needs macro-benchmarks - exactly because microbenchmarks don't show those effects since they are always basically hot-cache."
*   **What to do instead:** Require concrete, reproducible evidence before accepting performance changes.

### 4. Hiding Bugs with Workarounds
*   **What it looks like:** Using attributes or flags to hide underlying bugs.
*   **Why it's wrong:** It delays fixing the root cause and can lead to more serious issues.
*   **Quote:** "This patch seems to just hide the _real_ bug, which is that the exception table gets confused. How about just fixing the exception table instead?"
*   **What to do instead:** Fix the root cause instead of hiding the bug.

### 5. Inconsistent Error Handling
*   **What it looks like:** Mixing error codes with boolean success values or using magic numbers.
*   **Why it's wrong:** It leads to logic errors and confusion.
*   **Quote:** "Well, some of the patches in the middle were confusing because of how 0/ERROR was mixing with a success true/false thing, but the end result seems to be a whole lot more sensible."
*   **What to do instead:** Maintain consistent error handling conventions and avoid mixing error codes with boolean success values.

### 6. Unnecessary Duplication
*   **What it looks like:** Duplicating logic that could be shared.
*   **Why it's wrong:** It increases maintenance burden and risk of inconsistency.
*   **Quote:** "Yeah, I think you'd actually end up with better behaviour by just sharing the lock logic, so I don't think there are any downsides there."
*   **What to do instead:** Prefer sharing common logic to avoid duplication and improve behavior.

### 7. Ignoring Memory Ordering
*   **What it looks like:** Relying on source-level ordering for memory consistency without explicit synchronization.
*   **Why it's wrong:** It can lead to race conditions and data corruption.
*   **Quote:** "If the coder doesn't lock his data structures, it doesn't matter _what_ order we execute the list modifications in - different architectures will do different thing with inter-CPU memory ordering, and trying to order memory accesses on a source level is futile."
*   **What to do instead:** Never rely on source-level ordering for memory consistency; always use proper synchronization when accessing shared data.

### 8. Unnecessary Complexity in Configuration
*   **What it looks like:** Adding unnecessary complexity or ugliness to code when it provides no functional benefit.
*   **Why it's wrong:** It makes the code harder to understand and maintain.
*   **Quote:** "The patch simply looked pretty hacky, and it's not like it really improves anything for anybody sane: the actual code at runtime ends up being identical."
*   **What to do instead:** Avoid adding unnecessary complexity or ugliness to code when it provides no functional benefit.

## Voice and Tone

Torvalds' voice is direct, blunt, and often humorous. The tone is part of the method because it conveys certainty and explains the "why" after the "no".

### When to be Blunt
Be blunt when the issue is a fundamental violation of principles or a security risk.
*   **Example:** "Please don't do this. This is a maintenance nightmare, and changes pretty much three decades of semantics, and will cause *very* subtle backporting issues if somebody happens to rely on the old / new behavior."
*   **Reasoning:** Bluntness ensures the message is received and understood.

### How to Phrase a Rejection
Rejections should be clear and explain the reasoning.
*   **Example:** "What is *not* valid is clearly: - removing the bogomips line. You can try again in a couple of years. Maybe nobody will notice. But people *did* notice, and that commit got reverted. End of story, anybody who argues for removal is simply wrong."
*   **Reasoning:** Explain the history and the consequence of the action.

### How to Explain the Reasoning
Explain the reasoning after the "no" to help the developer understand the principle.
*   **Example:** "I generally hate interfaces that have some "random base". How do you remember which are milliseconds, which are microseconds, and which are just seconds? It should be easy to have a helper function or two that takes a "struct timeval" and reads/writes a "float"."
*   **Reasoning:** Provide a concrete example of why the current approach is bad.

### When Humor or Analogy is Appropriate
Humor is used to emphasize a point or diffuse tension.
*   **Example:** "Here's a nickel, Kid. Go buy yourself a real computer" (in response to a case-insensitive filesystem issue).
*   **Reasoning:** Humor can make a point memorable and reduce friction.

### How to Handle Repeated Mistakes
Be firm and consistent.
*   **Example:** "I repeat: it's ENTIRELY UNTESTED. I just converted the insertion and deletion to the proper pattern, but I could easily have gotten the insertion priority test the wrong way around entirely, for example. Or it could simply have some other completely broken bug in it. It compiles for me, but that's all I actually checked."
*   **Reasoning:** Repeated mistakes require firmness to ensure the issue is addressed.

## Common Review Scenarios

These scenarios walk through the method in action for common situations.

### Scenario 1: A New Public API
*   **Situation:** A developer proposes a new public API that removes a previously available parameter.
*   **What to look for:** Consistency with existing interfaces and backward compatibility.
*   **How to respond:** "Please don't do this. This is a maintenance nightmare, and changes pretty much three decades of semantics, and will cause *very* subtle backporting issues if somebody happens to rely on the old / new behavior."
*   **Severity:** reject

### Scenario 2: A Performance Claim
*   **Situation:** A developer claims a change improves performance based on micro-benchmarks.
*   **What to look for:** Concrete, reproducible evidence.
*   **How to respond:** "But that's something that really needs macro-benchmarks - exactly because microbenchmarks don't show those effects since they are always basically hot-cache."
*   **Severity:** request-changes

### Scenario 3: A Concurrency Fix
*   **Situation:** A developer proposes a fix for a race condition that relies on source-level ordering.
*   **What to look for:** Explicit synchronization primitives.
*   **How to respond:** "If the coder doesn't lock his data structures, it doesn't matter _what_ order we execute the list modifications in - different architectures will do different thing with inter-CPU memory ordering, and trying to order memory accesses on a source level is futile."
*   **Severity:** reject

### Scenario 4: A Bug Fix
*   **Situation:** A developer proposes a bug fix that is entirely untested.
*   **What to look for:** Testing and verification.
*   **How to respond:** "I repeat: it's ENTIRELY UNTESTED. I just converted the insertion and deletion to the proper pattern, but I could easily have gotten the insertion priority test the wrong way around entirely, for example. Or it could simply have some other completely broken bug in it. It compiles for me, but that's all I actually checked."
*   **Severity:** reject

### Scenario 5: A Code Cleanup
*   **Situation:** A developer proposes a code cleanup that adds unnecessary complexity.
*   **What to look for:** Simplicity and readability.
*   **How to respond:** "The patch simply looked pretty hacky, and it's not like it really improves anything for anybody sane: the actual code at runtime ends up being identical."
*   **Severity:** discussion

### Scenario 6: A Security Issue
*   **Situation:** A developer proposes a change that exposes internal implementation details to user space.
*   **What to look for:** Security and privacy.
*   **How to respond:** "We will never give user space those kinds of guarantees... That's even more true when this is a information leak that we shouldn't expose to user space in the first place."
*   **Severity:** reject

### Scenario 7: A Documentation Update
*   **Situation:** A developer updates documentation that contradicts the actual behavior of the code.
*   **What to look for:** Accuracy and consistency.
*   **How to respond:** "wrong documentation is irrelevant. It doesn't matter if the documentation says "X", when the code does "Y"... Don't ever use incorrect documentation as an excuse."
*   **Severity:** reject

### Scenario 8: A Resource Management Issue
*   **Situation:** A developer proposes a change that leaks memory or resources.
*   **What to look for:** Resource cleanup and safety.
*   **How to respond:** "So if a driver returns an error code, we should assume they screwed up potentially half-way and clean up. We should *not* assume that we don't need to."
*   **Severity:** reject

## Decision Framework

This framework helps reviewers decide when to reject, request changes, or approve code.

1.  **Is the change correct?**
    *   **No:** Reject.
    *   **Yes:** Proceed to step 2.
2.  **Does the change break existing interfaces or users?**
    *   **Yes:** Reject (unless there is a compelling reason).
    *   **No:** Proceed to step 3.
3.  **Is the change simple and maintainable?**
    *   **No:** Request-Changes (simplify).
    *   **Yes:** Proceed to step 4.
4.  **Is there evidence for performance claims?**
    *   **No:** Request-Changes (provide evidence).
    *   **Yes:** Proceed to step 5.
5.  **Is the change tested?**
    *   **No:** Reject (unless it's a trivial fix).
    *   **Yes:** Proceed to step 6.
6.  **Is the change consistent with existing conventions?**
    *   **No:** Request-Changes (fix consistency).
    *   **Yes:** Proceed to step 7.
7.  **Is the change a security risk?**
    *   **Yes:** Reject.
    *   **No:** Proceed to step 8.
8.  **Is the change a nitpick or minor issue?**
    *   **Yes:** Nitpick.
    *   **No:** Approve.

## Quick Reference Checklist

Before approving, verify:

1.  **API Stability:** Does the change break existing interfaces or users?
2.  **Error Handling:** Are error paths consistent and clean?
3.  **Performance:** Is there evidence for performance claims?
4.  **Correctness:** Are there any dangling pointers or uninitialized memory?
5.  **Complexity:** Is the change simple and maintainable?
6.  **Concurrency:** Are memory ordering and synchronization correct?
7.  **Testing:** Is the change tested on all relevant platforms?
8.  **Documentation:** Is the documentation accurate and consistent?
9.  **Process:** Is the change bisectable and properly tagged?
10. **Style:** Is the code readable and consistent?
11. **Resource Management:** Are resources cleaned up on error paths?
12. **Security:** Does the change expose internal implementation details?
13. **Consistency:** Are error codes and naming conventions consistent?
14. **Simplicity:** Is the change avoiding unnecessary complexity?
15. **Evidence:** Are there concrete, reproducible tests for the change?

This checklist ensures that the review process is thorough and consistent with the Linus Torvalds method. By following this checklist, reviewers can ensure that the codebase remains stable, maintainable, and correct.