---
name: linus-torvalds-skill
description: "A language- and project-agnostic skill for reviewing code the way Linus Torvalds does, distilled from 38,293 review moves across 14 categories in the Linux kernel."
metadata:
  author: "torvalds-skill pipeline"
  version: "1.0.0"
  tags:
    - code-review
    - reviewer-method
    - torvalds
---

# Linus Torvalds Review Method

> This skill teaches how to review code like Linus Torvalds, distilled from 38,293 review moves across 14 categories in the Linux kernel. The method is **language- and project-agnostic**: it applies to Python, Go, Rust, TypeScript, Java, Haskell, or any other language. The focus is on **design invariants, correctness, API stability, and maintainability**, not syntax or style. The skill is grounded in real Torvalds quotes and is designed to be a comprehensive reference for any code reviewer.

---

## Reviewer Mindset

Torvalds’ code reviews are defined by five core attitudes. These attitudes shape every decision and tone.

1. **Correctness is non-negotiable**
   > “If you as a kernel developer cannot make a choice, and argue strongly for _why_ that choice is the right one to export to user space, then we do not change existing behavior, since clearly you don't really have a good reason for the change.”
   Why it matters: Users depend on stable, correct behavior. Any change that risks breaking correctness is rejected unless the benefit is overwhelming.

2. **Users and existing behavior come first**
   > “What is *not* valid is clearly: removing the bogomips line. You can try again in a couple of years. Maybe nobody will notice. But people *did* notice, and that commit got reverted. End of story, anybody who argues for removal is simply wrong.”
   Why it matters: Breaking existing users or public interfaces is unacceptable unless there is a **compelling** reason and **overwhelming** evidence.

3. **Simplicity beats cleverness**
   > “Adding these kinds of ‘abstraction layers’ is something that people are taught is good, but I personally tend to think that it makes it less obvious at the code level what the ‘costs’ are.”
   Why it matters: Complexity is a tax on future maintainers. The simplest solution that works is always preferred.

4. **Evidence over opinion**
   > “Hmm. Honestly, I've never seen anything like that in any kernel profiles. Compared to the problems I _do_ see (which is usually the obvious cache misses, and locking), it must either be in the noise or it's some problem specific to whatever CPU you are doing performance work on?”
   Why it matters: Claims about performance or behavior must be backed by **measurement**, not speculation.

5. **Blunt honesty with a path forward**
   > “Ugh. Please make things like this just write out the full non-contracted thing. Ie ‘cannot’ is a perfectly fine word, we don't need to force spelling errors.”
   Why it matters: Feedback is direct and unfiltered, but always includes a **clear alternative** or **explanation** of why the current approach is wrong.

---

## Review Triggers

Below is a comprehensive catalog of **language- and project-agnostic** review triggers. Each trigger is labeled with its type and includes:
- **What to look for**: a generalized, language-agnostic pattern
- **Why it's a problem**: the underlying design principle being violated
- **Severity**: reject / request-changes / nitpick
- **Example (original wording)**: a real Torvalds quote showing how he handles it

---

### 1. API Contract Violation

**Type**: invariant-false

**What to look for**: A change that breaks an existing public interface or documented behavior, or removes a feature that users depend on.

**Why it's a problem**: Users rely on stable, documented behavior. Breaking it causes regressions and erodes trust.

**Severity**: reject

> **Trigger**: Proposal to remove the bogomips line from the kernel output
> **Example (original wording)**:
> “What is *not* valid is clearly:
>  - removing the bogomips line.
> You can try again in a couple of years. Maybe nobody will notice.
> But people *did* notice, and that commit got reverted. End of story,
> anybody who argues for removal is simply wrong.”

---

**Type**: invariant-true

**What to look for**: A public interface that exposes inconsistent return conventions (e.g., some functions return error codes, others return boolean success, others return byte counts).

**Why it's a problem**: Inconsistent error handling makes APIs error-prone and hard to use correctly.

**Severity**: discussion

> **Trigger**: Observed inconsistency between get|put_user and copy_to|from_user
> **Example (original wording)**:
> “If there is any inconsistency, maybe we should make _more_ cases use that ‘how many bytes/pages not copied’ logic, but in a lot of cases you don't actually need the ternary decision value.”

---

**Type**: precedence-rule

**What to look for**: A proposal to add a new flag or parameter that changes the semantics of an existing call, especially when the old behavior is widely used.

**Why it's a problem**: New flags create long-term maintenance burden and can break existing users.

**Severity**: request-changes

> **Trigger**: Suggestion to make getrandom() wait when called early, using a new flag
> **Example (original wording)**:
> “An alternative might be to make getrandom() just return an error instead of waiting. Sure, fill the buffer with ‘as random as we can’ stuff, but then return -EINVAL because you called us too early.”

---

### 2. Unnecessary Interface Complexity

**Type**: invariant-true

**What to look for**: Multiple variants of a function or interface that differ only in minor ways (e.g., `scoped_with_creds()` and `with_creds()`).

**Why it's a problem**: Narrow interfaces are easier to understand and maintain. Duplication increases the surface for bugs.

**Severity**: request-changes

> **Trigger**: The patch introduces both 'scoped_with_creds()' and a plain 'with_creds()' variant
> **Example (original wording)**:
> “I'd almost prefer if we *only* did ‘scoped_with_creds()’ and didn't have this version at all. ... I just suspect we could narrow down the new interface a bit more.”

---

**Type**: invariant-false

**What to look for**: A new system call or interface that is only needed for a rare use case, or a custom translation layer for supporting old kernels.

**Why it's a problem**: Custom layers add maintenance burden and complexity. Prefer using provided compatibility mechanisms.

**Severity**: approve / nitpick

> **Trigger**: Proposal to use a custom translation layer for supporting old kernels
> **Example (original wording)**:
> “The way the backwards-compatibility is _meant_ to work is that a driver can just do this:
> 	#ifndef IRQ_RETVAL
> 	  typedef void irqreturn_t;
> 	  #define IRQ_NONE
> 	  #define IRQ_HANDLED
> 	  #define IRQ_RETVAL(x)
> 	#endif
> and after that you can just use the 2.5.x semantics even with a 2.4.x kernel.
> Which is nice and clean, and allows you to support old kernels _without_ having any translation layer.”

---

### 3. Public Output or Interface Removal

**Type**: invariant-false

**What to look for**: A proposal to remove or change existing public output (e.g., `/proc`, `dmesg`, sysfs attributes) or a long-standing interface.

**Why it's a problem**: Users and tools depend on this output. Removing it breaks workflows.

**Severity**: reject

> **Trigger**: Proposal to remove the bogomips line from the kernel output
> **Example (original wording)**:
> “What is *not* valid is clearly:
>  - removing the bogomips line.
> You can try again in a couple of years. Maybe nobody will notice.
> But people *did* notice, and that commit got reverted. End of story,
> anybody who argues for removal is simply wrong.”

---

### 4. Arbitrary Restrictions Without Justification

**Type**: invariant-false

**What to look for**: A proposal to block a valid use case (e.g., unaligned shared mappings) without a **fundamental** security or stability reason.

**Why it's a problem**: Users should have the freedom to use valid features unless there is a clear, documented reason to restrict them.

**Severity**: reject

> **Trigger**: Proposal to disallow unaligned shared mappings without a clear security or stability reason
> **Example (original wording)**:
> “So I'm generally opposed to the kernel saying ‘you can't do that’ if there isn't some really fundamental reason (security or stability) for it to be really a no‑no. It's often better to give the user rope to hang himself: that rope might be used for interesting things too.”

---

### 5. Inconsistent or Non-Intuitive Semantics

**Type**: invariant-false

**What to look for**: A new API with surprising or non-intuitive semantics for corner cases (e.g., "zero-sized default", odd return values).

**Why it's a problem**: Surprising behavior leads to bugs. APIs should be intuitive and consistent.

**Severity**: request-changes

> **Trigger**: proposal to make the default behavior "zero-sized" with odd semantics for a corner case
> **Example (original wording)**:
> “Ugh. I thought we agreed to not have the odd ‘make it zero-sized’ thing be the default.
> Let's just make something that is a sane version of strncpy/strlcpy, not introduce yet another ‘str*cpy with really odd semantics for the corner case’”

---

### 6. Public Interface Naming or ABI Violation

**Type**: invariant-false

**What to look for**: A new interface with a double-underscore prefix (e.g., `__xchg`) or a misleading name that violates naming conventions.

**Why it's a problem**: Double underscores denote internal helpers. Exposing them as public interfaces breaks expectations and can cause collisions.

**Severity**: reject

> **Trigger**: Using a double‑underscore prefix ("__xchg") for a function that is now being exposed to drivers
> **Example (original wording)**:
> “The whole point of two underscores is to say ‘don't use this - it's an internal implementation’. So then making a new interface with two underscores ... is fundamentally bogus.”

---

### 7. Inconsistent Return Conventions

**Type**: invariant-false

**What to look for**: APIs that return different types for similar operations (e.g., some return error codes, others return byte counts, others return boolean).

**Why it's a problem**: Inconsistent conventions make APIs error-prone and hard to use.

**Severity**: discussion

> **Trigger**: Observed inconsistency between get|put_user (which returns bytes/pages not copied) and copy_to|from_user (which uses 0/-EFAULT)
> **Example (original wording)**:
> “If there is any inconsistency, maybe we should make _more_ cases use that ‘how many bytes/pages not copied’ logic, but in a lot of cases you don't actually need the ternary decision value.”

---

### 8. Long-Standing Semantics Change

**Type**: invariant-false

**What to look for**: A change to a long-standing public interface (e.g., `copy_to_user`, `get_user`) that alters its semantics.

**Why it's a problem**: Such changes create maintenance and backporting nightmares and break user space.

**Severity**: reject

> **Trigger**: Proposal to add copy_{to/from}_user_partial interface that changes three decades of semantics
> **Example (original wording)**:
> “Please don't do this. This is a maintenance nightmare, and changes pretty much three decades of semantics, and will cause *very* subtle backporting issues if somebody happens to rely on the old / new behavior.”

---

### 9. Missing Essential Functionality

**Type**: invariant-true

**What to look for**: A public API that lacks a common use case (e.g., a function that maps a page for callers who just want data).

**Why it's a problem**: APIs should cover the most common use cases without forcing users to write boilerplate.

**Severity**: nitpick

> **Trigger**: Missing a way to map a page for callers who just want data
> **Example (original wording)**:
> “Now, I didn't actually try to make that whole thing very transparent. In particular, somebody who just wants to see the data (and ignore as much of the ‘tree’ details as possible) would really want to have not that ‘tree_entry’, but the whole ‘struct tree_level *’ and in particular a way to *map* the page.”

---

### 10. Inconsistent Unit or Base Representation

**Type**: invariant-false

**What to look for**: APIs that use different base units (seconds, milliseconds, microseconds) for similar operations without clear helpers.

**Why it's a problem**: Mixed units make APIs error-prone and hard to use.

**Severity**: request-changes

> **Trigger**: Using different time units (seconds, milliseconds, microseconds) as base constants across files
> **Example (original wording)**:
> “I generally hate interfaces that have some ‘random base’.
> How do you remember which are milliseconds, which are microseconds, and which are just seconds?
> It should be easy to have a helper function or two that takes a ‘struct timeval’ and reads/writes a ‘float’.”

---

### 11. Unnecessary Wrapper or Helper Functions

**Type**: invariant-true

**What to look for**: A patch that introduces a new wrapper function (e.g., `__invalidate_device2()`) or renames a function to preserve an old signature, instead of fixing the callers.

**Why it's a problem**: Wrappers add complexity and hide the real logic. Fixing callers directly is simpler and clearer.

**Severity**: request-changes

> **Trigger**: The patch introduces a new function __invalidate_device2() and a wrapper to preserve the old __invalidate_device() signature
> **Example (original wording)**:
> “Why did you do that butt-ugly ‘__invalidate_device2()’? ... it would have made for a smaller and cleaner patch to just fix them all, rather than change the calling convention, create that ugly ‘2’ function, and add the wrapper function.”

---

### 12. Public Symbol Without Users

**Type**: invariant-true

**What to look for**: A public symbol (function, variable) that is exported but not used anywhere in the codebase.

**Why it's a problem**: Dead code increases maintenance burden and can become a security or correctness liability.

**Severity**: nitpick

> **Trigger**: reallocate_resource() is exported but not used anywhere in the tree
> **Example (original wording)**:
> “Btw, reallocate_resource() isn't actually used anywhere in the tree that I can see, so maybe we should remove it and the export, and just have the __reallocate_resource() that is static to resource.c and is to be called only with the lock held.”

---

### 13. Bitfields in Public or Semi-Public ABI

**Type**: invariant-false

**What to look for**: Use of bitfields in a struct that is exposed to drivers or user space, or used across subsystems.

**Why it's a problem**: Bitfields hinder addressability, readability, and can cause subtle ABI compatibility problems.

**Severity**: nitpick

> **Trigger**: Use of bitfields in a kernel-internal ABI struct
> **Example (original wording)**:
> “There are real reasons to avoid bitfields:
>  - you can't pass addresses to them around
>  - it's easier to read or assign multiple fields in one go
>  - they are horrible for ABI issues due to the exact bit ordering and padding being very subtle
> but none of those issues are relevant here, where it's a kernel-internal ABI.”

---

### 14. Changing Public Output Semantics

**Type**: invariant-false

**What to look for**: A change to the meaning of a field in a public interface (e.g., `/dev/kmsg`, sysfs attributes).

**Why it's a problem**: Users depend on stable, documented output. Changing it breaks tools and scripts.

**Severity**: reject

> **Trigger**: Proposal to change the meaning of ts_nsec in the exported /dev/kmsg interface (changing time format to wall clock vs monotonic)
> **Example (original wording)**:
> “If you as a kernel developer cannot make a choice., and argue strongly for _why_ that choice is the right one to export to user space, then we do not change existing behavior, since clearly you don't really have a good reason for the change.”

---

### 15. API Parameter Misrepresentation

**Type**: invariant-false

**What to look for**: A patch that misrepresents the purpose or semantics of an API parameter (e.g., calling an ioremap argument "bus info" when it is not).

**Why it's a problem**: Misleading names and documentation lead to misuse and bugs.

**Severity**: request-changes

> **Trigger**: Patch treats the ioremap() argument as "bus info" instead of a hardware‑dependent address
> **Example (original wording)**:
> “But it _isn't_ ‘bus info’. It's a unique number. It has no bus information embedded in it. It's a number that tells ioremap() what area to remap.”

---

### 16. Inconsistent or Confusing Naming Conventions

**Type**: invariant-false

**What to look for**: A new function or type that violates established naming conventions (e.g., using `__inline` as a macro instead of a keyword).

**Why it's a problem**: Inconsistent naming makes code harder to navigate and understand.

**Severity**: request-changes

> **Trigger**: The patch includes macro definitions #define __inline__ inline and #define __inline inline
> **Example (original wording)**:
> “we could get rid of these two lines in include/linux/compiler_types.h
>   #define __inline__ inline
>   #define __inline   inline
> and just say that ‘inline’ for the kernel means ‘always_inline’, but if you use __inline__ or __inline then you get the ‘raw’ compiler inlining.”

---

### 17. Public Interface That Forces Callers to Handle Unused Return Values

**Type**: invariant-false

**What to look for**: An API that returns a value (e.g., length) that most callers do not need, forcing them to handle it.

**Why it's a problem**: APIs should not force callers to handle return values they never use.

**Severity**: nitpick

> **Trigger**: APIs should not force callers to handle return values they never use
> **Example (original wording)**:
> “the real problem is that it returns the length, and there's no way to do ‘inline for small constant sizes when nobody cares about the result’ that I can think of.”

---

### 18. Unnecessary System Call Addition

**Type**: invariant-true

**What to look for**: A proposal to add a new system call when a simpler, existing interface (e.g., fcntl) can do the job.

**Why it's a problem**: New system calls increase the surface for bugs and maintenance. Reuse existing interfaces when possible.

**Severity**: reject

> **Trigger**: Proposal of a new nextfd(2) system call to iterate over file descriptors
> **Example (original wording)**:
> “Why would we bother to do better? System calls are cheap, and usually you actually do want to do something about the fd, so you actually want to iterate over them. I'd much rather have simple cheap interfaces than anything else. If SuS has a F_NEXT fcntl, let's just do that thing. Much simpler than doing something more complex and then just having to emulate the simple thing in user space anyway. If a standard interface exists, we should just use it.”

---

---

## Performance

### 1. Unnecessary Work or Locking

**Type**: invariant-false

**What to look for**: Code that performs unnecessary work or locking in a hot path (e.g., `free_swap_cache()` called unconditionally).

**Why it's a problem**: Unnecessary work increases latency and CPU usage.

**Severity**: approve

> **Trigger**: free_swap_cache() being called in non-swap code paths, potentially causing unnecessary locking
> **Example (original wording)**:
> “I was worried about non-swap behavior (which the old code had with that whole unconditional page locking whether needed or not), but free_swap_cache() should be basically free for the non-swap behavior since it doesn't even do the trylock until after it has checked that it is now an unmapped swap cache page.”

---

### 2. Unnecessary Synchronization Primitives

**Type**: invariant-false

**What to look for**: Use of heavyweight synchronization (e.g., lock, mutex) to protect a single primitive value or local variable.

**Why it's a problem**: Atomic operations or memory ordering primitives are sufficient for single values. Locks add overhead and complexity.

**Severity**: reject

> **Trigger**: Using a lock to serialize a single write (a single value/flag)
> **Example (original wording)**:
> “Using a lock to serialize a single write is completely bogus. It adds zero serialization that a WRITE_ONCE/READ_ONCE pair doesn't add. At best it's just wasted CPU time. At worst, it confuses people about what the locking means and results in bugs down the line. Don't do things like this.”

---

### 3. Over-Reliance on Compiler Optimizations

**Type**: invariant-false

**What to look for**: Code that relies on compiler optimizations (e.g., CSE, inlining) for correctness or performance, especially in low-level code.

**Why it's a problem**: Compiler optimizations are not guaranteed. Code must be correct regardless of optimization level.

**Severity**: reject

> **Trigger**: David Howells suggested that gcc will automatically combine logical operations in test_bit() usage
> **Example (original wording)**:
> “Nope. Look again.
> test_bit() with a constant number is done very much in C, and very much on purpose. _Exactly_ to allow the compiler to combine these kinds of things.”

---

### 4. Unnecessary Complex Transformations

**Type**: invariant-false

**What to look for**: Code that performs complex transformations (e.g., converting a page to a PFN and back) that prevent compiler optimizations.

**Why it's a problem**: Such transformations can prevent the compiler from optimizing and add performance overhead.

**Severity**: nitpick

> **Trigger**: Code that converts a page to a PFN and back just to test a condition that the compiler can already see is always zero
> **Example (original wording)**:
> “the compiler can see the logic and see ‘it's always zero’. ... Because that ‘turn it into a pfn and back’ is actually a really quite complicated operation (and the compiler won't be able to optimize that one much, so I'm pretty sure it generates horrific code).”

---

### 5. Unnecessary Memory Barriers or Ordering

**Type**: invariant-false

**What to look for**: Use of memory barriers or ordering primitives where they are not needed, or reliance on `cpu_relax()` for memory ordering.

**Why it's a problem**: Memory barriers have performance cost. Use them only when necessary for correctness.

**Severity**: request-changes

> **Trigger**: Patch suggests that cpu_relax() provides a memory barrier
> **Example (original wording)**:
> “Put another way: from a kernel standpoint, cpu_relax() in _no_ way implies a memory barrier. That has always been true, and that continues to be true.
> But Linux does expect that if some other CPU modifies a memory location, then we _will_ see that modification eventually. If the CPU needs help to do so, then cpu_relax() needs to do that. Again - this has nothing to do with memory barriers. It's just a basic requirement.”

---

### 6. Holding Locks Longer Than Necessary

**Type**: invariant-false

**What to look for**: Code that holds a lock over situations where concurrency could be allowed, or acquires a lock synchronously in a hot path.

**Why it's a problem**: Longer lock hold times reduce concurrency and scalability.

**Severity**: discussion

> **Trigger**: batching now holds the lock over some situations where concurrency could be allowed (e.g., avc allocations)
> **Example (original wording)**:
> “The only thing I don't love about the batching is that we now do hold the lock over some situations where we _could_ have allowed concurrency (notably some avc allocations), but I think it's a good trade-off.”

---

### 7. Unnecessary Atomic Operations

**Type**: invariant-false

**What to look for**: Use of atomic operations where a non-atomic version is safe and sufficient.

**Why it's a problem**: Atomic operations have higher overhead than non-atomic ones. Use them only when necessary for correctness.

**Severity**: discussion

> **Trigger**: the non‑atomic version might be safe for huge pages, suggesting the atomic read‑and‑clear could be removed even for the non‑NUMA case
> **Example (original wording)**:
> “So it might actually be that the non-atomic version is safe for hpages. And we could possibly get rid of the ‘atomic read-and-clear’ even for the non-numa case.”

---

### 8. Unnecessary Recursion or Stack Usage

**Type**: invariant-false

**What to look for**: Code that uses recursion or large stack allocations in hot paths, or lacks a way to limit recursion depth.

**Why it's a problem**: Recursion and large stack usage can cause stack overflows and increase latency.

**Severity**: discussion

> **Trigger**: Patch introduces recursive vsnprintf without any mechanism to limit recursion depth
> **Example (original wording)**:
> “I'd love to have some way to limit recursion, and I'd also love to see some actual numbers of how deep the vsnprintf stack frame is, but I don't see how to do the first, and I'm hoping the second isn't too horrible.”

---

### 9. Unnecessary Branches or Conditionals

**Type**: invariant-false

**What to look for**: Code that adds conditionals or branches that are unlikely to be taken or that obscure the main logic.

**Why it's a problem**: Conditionals increase code size and can hurt branch prediction.

**Severity**: nitpick

> **Trigger**: Code that uses conditionals like "if (sb->option.extent) ... else ..." to handle different filesystem behaviors in shared VFS-layer code
> **Example (original wording)**:
> “The if (sb->option.extent) .. do one thing .. else .. do another .. kind of thing is exactly what leads to problems later. Even if it allows sharing of 90% of the code (the caller of the function), it leads to problems exactly because of things that end up not quite working because people only tested one code‑path, and it broke the other case in some really subtle way.”

---

### 10. Unnecessary or Misleading Optimizations

**Type**: invariant-false

**What to look for**: Code that optimizes a micro-benchmark at the cost of real-world performance or correctness (e.g., "open twice" hack for execve).

**Why it's a problem**: Such "optimizations" can degrade performance in other scenarios and hide underlying issues.

**Severity**: reject

> **Trigger**: Proposal to implement an "open twice" hack to avoid allocating a struct file for execve
> **Example (original wording)**:
> “I really think that the ‘open twice’ is wrong. It will look artificially good in this ‘does not exist’ case, but it will penalize other cases, and it just hides this issue.”

---

---

## Correctness

### 1. Fatal Assertions on Recoverable Errors

**Type**: invariant-false

**What to look for**: Use of `BUG_ON()` or similar fatal assertions for recoverable or expected error conditions.

**Why it's a problem**: Fatal assertions crash the system for conditions that could be handled gracefully.

**Severity**: reject

> **Trigger**: Presence of a BUG_ON() in the code path handling mmap MAP_LOCKED failures
> **Example (original wording)**:
> “What is the point of that BUG_ON()? Hell, people add too many of those things. There is *no* excuse for killing the kernel for things like this (and in certain setups, BUG_ON() *will* cause the machine to be rebooted). None. It's completely inexcusable.”

---

### 2. Relying on Undefined or Implementation-Defined Behavior

**Type**: invariant-false

**What to look for**: Code that relies on implementation-defined behavior (e.g., signed char, strict aliasing, two's complement) or undefined behavior (e.g., signed integer overflow).

**Why it's a problem**: Such code is not portable and can break on other compilers or architectures.

**Severity**: reject

> **Trigger**: Reliance on strict aliasing optimizations (e.g., -fstrict-aliasing)
> **Example (original wording)**:
> “-fno-strict-aliasing: the standard is just wrong and full of shit, and the misguided type-based aliasing can cause serious problems for the kernel (but also other code).”

---

### 3. Unverified Static Analysis Claims

**Type**: invariant-false

**What to look for**: Code comments or commit messages that state invariants (e.g., "node->next should be NULL") based on static analysis without detailed justification.

**Why it's a problem**: Static analysis is not a substitute for verifiable logic. Code must be correct by design.

**Severity**: request-changes

> **Trigger**: Patch comment says 'node->next should be NULL' based on static analysis without detailed justification
> **Example (original wording)**:
> “This explanation makes me nervous.
> *What* static analysis? It's very unclear. And the ‘should be NULL’ doesn't make me get the warm and fuzzies.
> ... No ‘should be NULL’, in other words. I want a rock-solid ‘node->next is always NULL because XYZ’ explanation, not a wishy-washy ‘static analysis says’ without spelling it out.”

---

### 4. Misuse of Internal Counters

**Type**: invariant-false

**What to look for**: Code that bases functional decisions on internal counters (e.g., `mapcount`) that are not part of the defined semantics.

**Why it's a problem**: Internal counters are not part of the API contract and can change without notice.

**Severity**: reject

> **Trigger**: The patch uses mapcount == 1 to decide when to unshare a page for FAULT_FLAG_UNSHARE
> **Example (original wording)**:
> “Notice? ‘mapcount’ is complete BS. The number of times a page is mapped is irrelevant for COW. All that matters is that we get an exclusive access to the page before we can write to it. Anybody who takes mapcount into account at COW time is broken, and it worries me how this is all mixing up with the COW logic.”

---

### 5. Unsafe Memory Access or Dangling Pointers

**Type**: invariant-false

**What to look for**: Code that dereferences a pointer after the object has been freed, or stores a pointer to stack-allocated memory and uses it later.

**Why it's a problem**: Dangling pointers cause use-after-free bugs and memory corruption.

**Severity**: reject

> **Trigger**: use the address of a local variable ("&verifier") that is later stored and accessed after the function returns
> **Example (original wording)**:
> “That's unacceptably buggy crap. rpc_wait_for_completion_task() will happily exit on a deadly signal even if the rpc hasn't been completed, so now you'll have a stale pointer to a stack that has been freed.”

---

### 6. Uninitialized Variables

**Type**: invariant-false

**What to look for**: Code that uses uninitialized variables, especially in security-sensitive or user-facing paths.

**Why it's a problem**: Uninitialized variables can leak stack contents or cause undefined behavior.

**Severity**: discussion

> **Trigger**: uninitialized automatic variables leading to undefined behavior
> **Example (original wording)**:
> “Maybe we could have gcc just always initialize variables to zero... this might be one of those cheap things where we just avoid undefined behavior and avoid leaking old stack contents.”

---

### 7. Exposing Stale or Sensitive Data to User Space

**Type**: invariant-false

**What to look for**: Code that returns data that may have come from a folio that has been released and re-used, or that exposes internal state to user space.

**Why it's a problem**: Such data can be stale, sensitive, or cause security issues.

**Severity**: reject

> **Trigger**: returning data that may have come from a folio that has been released and re-used
> **Example (original wording)**:
> “and this is fatal. We might have optimistically copied things that are now security-sensitive and even if we return a short read - or overwrite it - layer, user space should never have seen that data.”

---

### 8. Corrupting Existing State

**Type**: invariant-false

**What to look for**: Code that overwrites bits that should remain zero, or corrupts registers or memory in a way that violates the architecture’s ABI.

**Why it's a problem**: Such corruption can cause subtle bugs and security issues.

**Severity**: reject

> **Trigger**: you actually corrupt rid/rdp ... overwrites the high bits of rip, and fos overwrites the high bits of rdp. So now bits that *should* be zero are not.
> **Example (original wording)**:
> “As far as I can tell, you actually corrupt rid/rdp in that case because when you write the fcs thing, it overwrites the high bits of rip, and fos overwrites the high bits of rdp. So now bits that *should* be zero are not.”

---

### 9. Incorrect Error Handling or Cleanup

**Type**: invariant-false

**What to look for**: Code that returns an error from a function (e.g., `mmap()`) without cleaning up resources, or that assumes resources are in a consistent state after an error.

**Why it's a problem**: Inconsistent state can cause use-after-free or other bugs.

**Severity**: reject

> **Trigger**: A driver returns an error code from the mmap() helper without performing cleanup
> **Example (original wording)**:
> “So if a driver returns an error code, we should assume they screwed up potentially half-way and clean up. We should *not* assume that we don't need to.”

---

### 10. Use of Magic or Placeholder Values

**Type**: invariant-false

**What to look for**: Code that uses placeholder values (e.g., `0x0123456789abcdef`) that are not valid or safe.

**Why it's a problem**: Placeholder values can cause bugs and are not meaningful.

**Severity**: request-changes

> **Trigger**: runtime_const pointer is initialized to the magic non‑canonical address 0x0123456789abcdef
> **Example (original wording)**:
> “I picked the default value for the runtime_const pointer of 0x0123456789abcdef because it's easy to see in disassembly... But it sure as hell ain't right.”

---

---

## Complexity

### 1. Unnecessary Abstraction Layers

**Type**: invariant-false

**What to look for**: Code that introduces abstraction layers that hide performance costs or make the code less obvious.

**Why it's a problem**: Abstractions should not hide costs. The simplest code that works is preferred.

**Severity**: nitpick

> **Trigger**: Proposal to extend Kconfig ternary logic to a quinary 'Y/y/m/n/N' system with forced values
> **Example (original wording)**:
> “The problem here is that:
>  - you can get inconsistent situations (‘but he wanted to both force that on *and* off!’)
>  - ‘select’ actually is much nicer, in that it unambiguously selects one other symbol. But ‘depends on’ is very hard to force, because you may have something like (totally made up)
> 	depends on X86 || (ALPHA && PCI)
>  which is impossible to force (*which* one do you force?) on.”

---

### 2. Unnecessary Special-Case Handling

**Type**: invariant-false

**What to look for**: Code that adds special-case handling for rare or non-essential features (e.g., kernel-managed per-node page cache).

**Why it's a problem**: Special cases increase complexity and maintenance burden.

**Severity**: reject

> **Trigger**: proposal to add kernel-managed per-node page cache for a very rare use case
> **