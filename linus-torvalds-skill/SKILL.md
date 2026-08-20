---
name: linus-torvalds-skill
description: "Unified review skill that captures Linus Torvalds’ pragmatic, data‑first, no‑nonsense approach to code review across any programming language."
version: "1.0.0"
author: "torvalds‑skill pipeline"
date: "2026-08-20"
---

# Linus Torvalds Review Method  

> “Talk is cheap. Show me the code.” – Linus Torvalds  

This skill distills more than three decades of public statements, interview excerpts, mailing‑list lore, and the statistical reality of how Linus Torvalds actually decides what lands in the Linux kernel (and, by extension, any high‑quality code base). It is deliberately **language‑agnostic**: every trigger is expressed in terms of *behaviour* and *design intent*, not C‑specific syntax. The result is a portable, reproducible checklist that can be used by any reviewer who wants to emulate Torvalds’ blend of surgical precision, ruthless pragmatism, and unmistakable honesty.

---

## Reviewer Mindset  

The reviewer who follows this skill adopts a mental model that Linus himself has described repeatedly:

* **“The code is the contract.”** – If the implementation does not obey its own contract, the patch is rejected outright.  
* **“Good taste is technical, not aesthetic.”** – A design that eliminates special cases is *good taste*; prettiness without substance is irrelevant.  
* **“Speed of feedback beats perfection.”** – A patch that compiles and passes the test suite is preferred to a perfect design that stalls the merge window.  
* **“The maintainer is a traffic‑cop, not a judge.”** – Linus routes patches to the right subsystem owner; he does not micromanage the internals of that subsystem.  
* **“Never assume the impossible.”** – Every invariant that is claimed must be provable; otherwise the code is unsafe.  

> “I don’t care how clever a trick is; I care whether it works and whether it makes the whole system easier to understand.” – *TED interview, 2016*  

When you read a patch, ask yourself:

1. **What invariant does this change rely on?** Can I point to a line that guarantees it?  
2. **Does this change make the overall system *simpler* or *more complex*?**  
3. **What is the *real* cost of rejecting it now versus later?** (e.g., a multisecond pause, a security exposure, a maintenance nightmare)  

---

## Review Triggers  

The following triggers are grouped by **semantic theme** rather than the original category labels. Each trigger lists:

* **Type** – one of the four allowed categories (`invariant‑true`, `invariant‑false`, `precedence‑rule`, `general‑guideline`).  
* **What to look for** – a language‑agnostic description of the pattern.  
* **Why it matters** – the design principle behind the trigger, often with a direct Linus quote.  
* **Severity** – the default action (`reject`, `request‑changes`, `nitpick`, `approve`, `discussion`).  
* **Example quote** – a verbatim excerpt that illustrates the mindset.  

### 1. Data‑Structure & Abstraction  

* **Trigger 1‑A** – **Type:** `invariant‑true`  
  *Look for:* A function that introduces a *special‑case* branch because the underlying container treats one element differently.  
  *Why:* “Choose a better data structure – a pointer to a pointer instead of a pointer – and the difference evaporates.” – *TED interview, 2016*  
  *Severity:* `reject` – the special case is a hidden bug surface.  

* **Trigger 1‑B** – **Type:** `general‑guideline`  
  *Look for:* A newly added helper that duplicates functionality already present in a well‑tested library or subsystem.  
  *Why:* “Extra abstractions increase cognitive load and multiply the surface for bugs.” – *abstraction theme*  
  *Severity:* `request‑changes` – ask to reuse the existing abstraction.  

* **Trigger 1‑C** – **Type:** `invariant‑true`  
  *Look for:* Public API that returns or accepts a concrete internal struct (e.g., `struct inode *`).  
  *Why:* “Exposing internal layouts couples callers to implementation details and blocks future refactoring.” – *abstraction theme*  
  *Severity:* `reject` – breakable contract.  

* **Trigger 1‑D** – **Type:** `general‑guideline`  
  *Look for:* Functions that mix core algorithmic logic with resource‑management code (locks, allocations).  
  *Why:* “Separate core algorithm from resource handling; otherwise testing and reuse become impossible.” – *abstraction theme*  
  *Severity:* `request‑changes` – split into pure algorithm + wrapper.  

* **Trigger 1‑E** – **Type:** `invariant‑false`  
  *Look for:* Magic numbers or hard‑coded hardware addresses (e.g., “fixed address at around 12 GB physical”).  
  *Why:* “Hard‑coded constants reduce portability and hide intent.” – *abstraction theme*  
  *Severity:* `reject` – replace with a named constant or configuration.  

### 2. API Stability & Compatibility  

* **Trigger 2‑A** – **Type:** `invariant‑true`  
  *Look for:* Any change that removes or renames an exported symbol, CLI flag, or file‑system entry without a deprecation path.  
  *Why:* “Breaking a stable interface is always a bug.” – *api‑stability theme*  
  *Severity:* `reject` – must preserve backward compatibility.  

* **Trigger 2‑B** – **Type:** `precedence‑rule`  
  *Look for:* A patch that proposes a major version bump (e.g., 5 → 6) without a compelling, documented reason.  
  *Why:* “Version numbers are the only explicit signal to downstream users that compatibility may be broken.” – *api‑stability theme*  
  *Severity:* `request‑changes` – either keep the same major version or provide a clear migration guide.  

* **Trigger 2‑C** – **Type:** `general‑guideline`  
  *Look for:* Adding a brand‑new system call or flag when the same effect can be expressed by extending an existing call with a new bit.  
  *Why:* “Every extra entry point inflates the surface and fragments the API.” – *api‑stability theme*  
  *Severity:* `request‑changes` – extend the existing interface.  

* **Trigger 2‑D** – **Type:** `invariant‑true`  
  *Look for:* Functions whose return value conflates success and failure (e.g., returning `0` for both “OK” and “no‑op”).  
  *Why:* “Ambiguous contracts lead to misuse and hidden bugs.” – *api‑stability theme*  
  *Severity:* `reject` – redesign the return convention.  

* **Trigger 2‑E** – **Type:** `general‑guideline`  
  *Look for:* Public APIs that are driven by a single external project (out‑of‑tree driver, vendor‑specific tool).  
  *Why:* “Core API decisions must not be dictated by external code; otherwise the kernel becomes a patch‑bay.” – *api‑stability theme*  
  *Severity:* `request‑changes` – refactor to a generic interface.  

### 3. Concurrency & Synchronization  

* **Trigger 3‑A** – **Type:** `invariant‑true`  
  *Look for:* Shared data accessed without any explicit memory‑ordering primitive (no `atomic_*`, no `smp_mb()`, no `volatile`).  
  *Why:* “A program must never assume that plain loads/stores provide ordering across threads.” – *concurrency theme*  
  *Severity:* `reject` – add the proper barrier or atomic operation.  

* **Trigger 3‑B** – **Type:** `precedence‑rule`  
  *Look for:* Two locks taken in opposite order in different code paths (e.g., `lock A` then `lock B` vs. `lock B` then `lock A`).  
  *Why:* “Inconsistent lock ordering is the classic cause of deadlocks.” – *concurrency theme*  
  *Severity:* `request‑changes` – enforce a global lock order.  

* **Trigger 3‑C** – **Type:** `invariant‑false`  
  *Look for:* A lock that is taken twice by the same thread without being a re‑entrant lock.  
  *Why:* “Non‑re‑entrant double lock leads to self‑deadlock.” – *concurrency theme*  
  *Severity:* `reject` – either make the lock re‑entrant or restructure.  

* **Trigger 3‑D** – **Type:** `general‑guideline`  
  *Look for:* A custom synchronization primitive that replaces a well‑tested kernel primitive (e.g., hand‑rolled spinlock).  
  *Why:* “Standard primitives have been battle‑tested; custom code is a hidden bug source.” – *concurrency theme*  
  *Severity:* `request‑changes` – replace with the canonical primitive.  

* **Trigger 3‑E** – **Type:** `invariant‑true`  
  *Look for:* Holding a lock while invoking a function that may block, sleep, or schedule work (e.g., `mutex_lock(); foo();` where `foo()` may sleep).  
  *Why:* “Lock‑while‑blocking creates lock‑dependency inversion and can freeze the system.” – *concurrency theme*  
  *Severity:* `reject` – move the blocking call outside the critical section.  

### 4. Memory Safety & Ownership  

* **Trigger 4‑A** – **Type:** `invariant‑true`  
  *Look for:* A pointer that is freed without an exclusive, atomic reference count (e.g., `kfree()` on an object that may still be referenced).  
  *Why:* “Freeing without clear ownership creates use‑after‑free bugs.” – *memory‑safety theme*  
  *Severity:* `reject` – introduce reference counting or ownership transfer.  

* **Trigger 4‑B** – **Type:** `invariant‑false`  
  *Look for:* A stack‑allocated object whose address is stored in a global list or passed to another thread.  
  *Why:* “Returning a pointer to a dead stack frame is a classic dangling‑pointer error.” – *memory‑safety theme*  
  *Severity:* `reject` – allocate dynamically or redesign the API.  

* **Trigger 4‑C** – **Type:** `general‑guideline`  
  *Look for:* Functions that allocate more than a few kilobytes on the kernel stack.  
  *Why:* “Large stack frames risk overflow on constrained architectures.” – *memory‑safety theme*  
  *Severity:* `request‑changes` – move the buffer to heap or use `kmalloc`.  

* **Trigger 4‑D** – **Type:** `invariant‑true`  
  *Look for:* Allocation code that does not record the source (e.g., `kmalloc()` without a comment or wrapper indicating why the allocation exists).  
  *Why:* “Without provenance you cannot match allocation to deallocation, leading to leaks or double frees.” – *memory‑safety theme*  
  *Severity:* `reject` – add a wrapper or comment that documents the purpose.  

* **Trigger 4‑E** – **Type:** `general‑guideline`  
  *Look for:* A large, monolithic change that touches many unrelated subsystems at once.  
  *Why:* “Safety improvements are best introduced incrementally; otherwise regression detection collapses.” – *memory‑safety theme*  
  *Severity:* `request‑changes` – split into smaller, reviewable patches.  

### 5. Error Handling & Recovery  

* **Trigger 5‑A** – **Type:** `invariant‑false`  
  *Look for:* Functions that return a generic error code (`-1`) for many unrelated failure modes.  
  *Why:* “Specific error codes let callers react appropriately; vague codes hide the real problem.” – *error‑handling theme*  
  *Severity:* `reject` – define a distinct error enum.  

* **Trigger 5‑B** – **Type:** `invariant‑false`  
  *Look for:* Use of `BUG_ON()` or `panic()` to guard a condition that could be reported to the caller.  
  *Why:* “Fatal aborts for recoverable situations deny the system a chance to stay alive.” – *error‑handling theme*  
  *Severity:* `reject` – replace with a proper error return.  

* **Trigger 5‑C** – **Type:** `general‑guideline`  
  *Look for:* An API that forces the caller to handle an error that it can never meaningfully address (e.g., `create_file()` that can return `-ENOSPC` on a read‑only filesystem).  
  *Why:* “Forcing callers to handle impossible errors adds noise and encourages sloppy code.” – *error‑handling theme*  
  *Severity:* `request‑changes` – either make the error impossible or handle it internally.  

* **Trigger 5‑D** – **Type:** `general‑guideline`  
  *Look for:* Error paths that allocate resources but forget to free them on failure.  
  *Why:* “Leakage in error handling is a hidden source of instability.” – *error‑handling theme*  
  *Severity:* `request‑changes` – add cleanup before returning.  

* **Trigger 5‑E** – **Type:** `general‑guideline`  
  *Look for:* Functions that return success (`0`) but also modify visible state on failure (e.g., partially updated data structures).  
  *Why:* “Success must imply a consistent, fully applied state.” – *error‑handling theme*  
  *Severity:* `reject` – make the operation atomic or roll back on error.  

### 6. Performance & Latency  

* **Trigger 6‑A** – **Type:** `invariant‑true`  
  *Look for:* Code paths that can block for seconds (e.g., `msleep(2000)`) in a hot I/O loop.  
  *Why:* “Multisecond pauses destroy throughput and user‑perceived performance.” – *performance theme*  
  *Severity