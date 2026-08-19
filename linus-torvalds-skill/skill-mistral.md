```yaml
name: linus-torvalds-skill
description: "A language- and project-agnostic code review method distilled from 38,293 of Linus Torvalds' real reviews across 13 categories. Focuses on design invariants, API stability, and maintainability."
metadata:
  author: "torvalds-skill pipeline"
  version: "1.0.0"
  tags:
    - code-review
    - reviewer-method
    - torvalds
---

# Linus Torvalds Review Method

> A language- and project-agnostic code review method distilled from 38,293 review moves across 13 categories (api-stability, performance, correctness, complexity, style, process, error-handling, concurrency, memory-safety, abstraction, testing, documentation, other). The method centers on invariants, API stability, and maintainability, and is designed to be applied to any programming language or project.

---

## Reviewer Mindset

Torvalds’ review method is defined by five core attitudes, each grounded in a pragmatic engineering philosophy. These attitudes are not about tone alone; they are the lens through which correctness, safety, and maintainability are judged.

| Attitude | One‑Line Principle | Real Torvalds Quote |
|---|---|---|
| **Correctness First** | Never accept a change that breaks correctness, even if it improves performance or readability. | “What is *not* valid is clearly: removing the bogomips line.” (2015-01-06) |
| **API Stability as Contract** | Treat public interfaces as contracts with existing users; breaking them is a non‑negotiable offense. | “We do not change existing behavior, since clearly you don't really have a good reason for the change.” (2017-11-14) |
| **Data Structure First** | Prefer data structures that eliminate special cases; the code should be short because the structure absorbed the complexity. | “I want you to understand that sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case, and that’s good code.” (TED 2016) |
| **Pragmatic Evidence** | A design is a hypothesis; only running code settles the argument. | “Talk is cheap. Show me the code.” (LKML 2000-08-25) |
| **Blunt Accountability** | Review is impersonal; the code is judged on whether it is right, not who wrote it or how much effort it represents. | “I’m not a nice person, and I don’t care about you. I care about the technology and the kernel.” (Ars Technica 2015-01) |

**Why these attitudes matter:** They prevent the reviewer from being swayed by aesthetics, effort, or politics. They force the code to prove its correctness, not just its intent. They make the review process transparent and reproducible.

---

## Review Triggers

Below are 24 distinct trigger themes, each distilled from multiple review moves. Each trigger is language‑agnostic, invariant‑based, and actionable.

---

### 1. API Contract Violation

**Type:** invariant-false

**What to look for:** A change that breaks an existing public interface (function signature, return convention, output format, or observable behavior) without a compelling reason.

**Why it's a problem:** Existing users depend on the contract; breaking it causes silent failures, crashes, or maintenance nightmares.

**Severity:** reject

**Example (original wording):**
> “What is *not* valid is clearly:
>  - removing the bogomips line.
> You can try again in a couple of years. Maybe nobody will notice.
> But people *did* notice, and that commit got reverted. End of story,
> anybody who argues for removal is simply wrong.”

---

### 2. Special Case in Public Interface

**Type:** invariant-false

**What to look for:** A public function or system call that exposes multiple variants (e.g., `scoped_with_creds()` and `with_creds()`), or a parameter that changes semantics based on a flag.

**Why it's a problem:** It increases the API surface, complicates documentation, and invites misuse.

**Severity:** request-changes

**Example (original wording):**
> “I'd almost prefer if we *only* did "scoped_with_creds()" and didn't have this version at all. ... I just suspect we could narrow down the new interface a bit more.”

---

### 3. Inconsistent Return Conventions

**Type:** invariant-false

**What to look for:** APIs that return success/failure in different ways (e.g., 0/-EFAULT vs. bytes not copied) or use sentinel values that could be valid data.

**Why it's a problem:** It forces callers to handle multiple conventions, increasing bug surface.

**Severity:** request-changes

**Example (original wording):**
> “If there is any inconsistency, maybe we should make _more_ cases use that "how many bytes/pages not copied" logic, but in a lot of cases you don't actually need the ternary decision value.”

---

### 4. Arbitrary Restriction Without Justification

**Type:** invariant-false

**What to look for:** A change that disables a feature or interface without a fundamental security or stability justification.

**Why it's a problem:** It removes useful functionality and limits user freedom without clear benefit.

**Severity:** reject

**Example (original wording):**
> “So I'm generally opposed to the kernel saying "you can't do that" if there isn't some really fundamental reason (security or stability) for it to be really a no‑no. It's often better to give the user rope to hang himself: that rope might be used for interesting things too.”

---

### 5. New Interface Without Clear Need

**Type:** invariant-false

**What to look for:** A proposal to add a new system call, helper, or flag when an existing interface already covers the use case.

**Why it's a problem:** It increases maintenance burden and fragmentation.

**Severity:** reject

**Example (original wording):**
> “Why would we bother to do better? System calls are cheap, and usually you actually do want to do something about the fd, so you actually want to iterate over them. I'd much rather have simple cheap interfaces than anything else.”

---

### 6. Uncoordinated Cross‑Platform Interface Change

**Type:** invariant-false

**What to look for:** A patch that touches non‑x86 header files and introduces a new generic header or helper without consulting all affected stakeholders.

**Why it's a problem:** It risks ABI or API conflicts across platforms.

**Severity:** request-changes

**Example (original wording):**
> “The other comment I have is that since it does touch non-x86 header files etc (although not a lot), you really need to talk to the POWER8 people about naming of the thing.”

---

### 7. Inconsistent or Arbitrary Units in Public Interface

**Type:** invariant-false

**What to look for:** Public constants or parameters that use different time units (seconds, milliseconds, microseconds) or other arbitrary scales without conversion helpers.

**Why it's a problem:** It invites misuse and bugs due to confusion.

**Severity:** request-changes

**Example (original wording):**
> “I generally hate interfaces that have some "random base".
> How do you remember which are milliseconds, which are microseconds, and which are just seconds?
> It should be easy to have a helper function or two that takes a "struct timeval" and reads/writes a "float".”

---

### 8. Adding New Flags Instead of Returning Errors

**Type:** invariant-false

**What to look for:** A proposal to add a new flag to an existing call to change semantics, instead of returning an explicit error.

**Why it's a problem:** It complicates the calling convention and increases API surface.

**Severity:** request-changes

**Example (original wording):**
> “An alternative might be to make getrandom() just return an error instead of waiting. Sure, fill the buffer with "as random as we can" stuff, but then return -EINVAL because you called us too early.”

---

### 9. Exposing Internal Implementation Details

**Type:** invariant-false

**What to look for:** A patch that exposes internal state, naming, or semantics (e.g., double‑underscore prefix for a function now exposed to drivers).

**Why it's a problem:** It breaks encapsulation and invites misuse.

**Severity:** reject

**Example (original wording):**
> “The whole point of two underscores is to say "don't use this - it's an internal implementation". So then making a new interface with two underscores ... is fundamentally bogus.”

---

### 10. Using Signedness‑Dependent APIs in Public Interface

**Type:** invariant-false

**What to look for:** A public API that accepts `char*` or similar, where the signedness of `char` affects behavior.

**Why it's a problem:** It makes the API unusable on platforms where `char` is signed.

**Severity:** reject

**Example (original wording):**
> “But THE CALLER CANNOT AND MUST NOT CARE! Because the sign of "char" is implementation-defined, so if you call "strcmp()", you are already basically saying: I don't care (and I _cannot_ care) what sign you are using.”

---

### 11. Breaking Long‑Standing Public Output

**Type:** invariant-false

**What to look for:** A change that removes or changes a line of public output (e.g., `/proc/cpuinfo` or `dmesg`) without a compelling reason.

**Why it's a problem:** Users parse this output; breaking it breaks scripts and tools.

**Severity:** reject

**Example (original wording):**
> “What is *not* valid is clearly:
>  - removing the bogomips line.
> You can try again in a couple of years. Maybe nobody will notice.
> But people *did* notice, and that commit got reverted. End of story,
> anybody who argues for removal is simply wrong.”

---

### 12. Unnecessary Wrapper or Duplication in Public Interface

**Type:** invariant-true

**What to look for:** A patch that introduces a new wrapper function or a `__invalidate_device2()` to preserve an old signature.

**Why it's a problem:** It increases API surface and maintenance burden.

**Severity:** request-changes

**Example (original wording):**
> “Why did you do that butt-ugly "__invalidate_device2()"? ... it would have made for a smaller and cleaner patch to just fix them all, rather than change the calling convention, create that ugly "2" function, and add the wrapper function.”

---

### 13. Zero‑Sized Default with Odd Semantics

**Type:** invariant-false

**What to look for:** A proposal to make the default behavior “zero‑sized” with non‑intuitive semantics for a corner case.

**Why it's a problem:** It creates surprising behavior and invites bugs.

**Severity:** request-changes

**Example (original wording):**
> “Ugh. I thought we agreed to not have the odd "make it zero-sized" thing be the default.
> Let's just make something that is a sane version of strncpy/strlcpy, not introduce yet another "str*cpy with really odd semantics for the corner case"”

---

### 14. Adding New System Call When Existing Interface Suffices

**Type:** invariant-false

**What to look for:** A proposal to add a new system call (e.g., `nextfd(2)`) when an existing interface (e.g., `F_NEXT` fcntl) already covers the use case.

**Why it's a problem:** It increases syscall surface and user‑space complexity.

**Severity:** reject

**Example (original wording):**
> “Why would we bother to do better? System calls are cheap, and usually you actually do want to do something about the fd, so you actually want to iterate over them. I'd much rather have simple cheap interfaces than anything else.”

---

### 15. Bitfields in Public or Semi‑Public ABI

**Type:** invariant-false

**What to look for:** Use of bitfields in a struct that is exposed to drivers or used in an ABI.

**Why it's a problem:** Bitfields hinder addressability, readability, and can cause subtle ABI compatibility problems.

**Severity:** nitpick

**Example (original wording):**
> “There are real reasons to avoid bitfields:
>  - you can't pass addresses to them around
>  - it's easier to read or assign multiple fields in one go
>  - they are horrible for ABI issues due to the exact bit ordering and padding being very subtle
> but none of those issues are relevant here, where it's a kernel-internal ABI.”

---

### 16. Changing Public Interface Semantics Without Justification

**Type:** invariant-false

**What to look for:** A change to the meaning of a field in a public interface (e.g., `/dev/kmsg` `ts_nsec` changing from monotonic to wall clock).

**Why it's a problem:** It breaks user‑space assumptions and scripts.

**Severity:** reject

**Example (original wording):**
> “If you as a kernel developer cannot make a choice., and argue strongly for _why_ that choice is the right one to export to user space, then we do not change existing behavior, since clearly you don't really have a good reason for the change.”

---

### 17. Exposing Internal Helper as Public Interface

**Type:** invariant-false

**What to look for:** A new public interface that uses a double‑underscore prefix, violating the convention that double underscores denote internal helpers.

**Why it's a problem:** It invites misuse and breaks encapsulation.

**Severity:** reject

**Example (original wording):**
> “The whole point of two underscores is to say "don't use this - it's an internal implementation". So then making a new interface with two underscores ... is fundamentally bogus.”

---

### 18. Removing Dead Public Symbols

**Type:** invariant-true

**What to look for:** A patch that removes a public symbol (e.g., `reallocate_resource()`) that is exported but unused.

**Why it's a problem:** It reduces API surface and maintenance burden.

**Severity:** nitpick

**Example (original wording):**
> “Btw, reallocate_resource() isn't actually used anywhere in the tree that I can see, so maybe we should remove it and the export, and just have the __reallocate_resource() that is static to resource.c and is to be called only with the lock held.”

---

### 19. Returning Magic Error Codes Instead of Typed Errors

**Type:** invariant-false

**What to look for:** A function that returns magic error codes (e.g., `-EFAULT`, `-EINVAL`) instead of typed error objects or exceptions.

**Why it's a problem:** It forces callers to handle multiple conventions and increases bug surface.

**Severity:** reject

**Example (original wording):**
> “I made sure that the return value is sensible (return 0 or -EFAULT rather than the "__memcpy_from_user()" return value which is how many bytes we couldn't copy).”

---

### 20. Unnecessary Abstraction or Helper Function

**Type:** invariant-true

**What to look for:** A patch that adds a helper function or abstraction (e.g., `sized_strscpy()`) that returns a value most callers ignore.

**Why it's a problem:** It increases API surface and complexity without clear benefit.

**Severity:** nitpick

**Example (original wording):**
> “the real problem is that it returns the length, and there's no way to do "inline for small constant sizes when nobody cares about the result" that I can think of.”

---

### 21. Unsafe or Uninitialized Memory Exposure

**Type:** invariant-false

**What to look for:** Code that exposes uninitialized memory, stale data, or data from a freed resource to user space.

**Why it's a problem:** It creates security vulnerabilities and undefined behavior.

**Severity:** reject

**Example (original wording):**
> “and this is fatal. We might have optimistically copied things that are now security-sensitive and even if we return a short read - or overwrite it - layer, user space should never have seen that data.”

---

### 22. Using Volatile for Memory Ordering

**Type:** invariant-false

**What to look for:** Use of `volatile` to enforce memory ordering or synchronization.

**Why it's a problem:** `volatile` is not a synchronization primitive; it can break compiler optimizations and correctness.

**Severity:** nitpick

**Example (original wording):**
> “We've largely stopped using "volatile" in favor of explicit barriers and locks (ie "cpu_relax()" and "barrier()") and explicit volatility in code (ACCESS_ONCE() and "rcu_access_pointer()" etc).”

---

### 23. Unsafe Pointer Cast or Type Pun

**Type:** invariant-false

**What to look for:** Code that casts a raw address to a pointer without proper mapping (e.g., `ioremap()`).

**Why it's a problem:** It creates undefined behavior and portability issues.

**Severity:** reject

**Example (original wording):**
> “Ouch. Who does that, anyway? It's wrong to do that. It's not a pointer, not even an __iomem one. You'd need to do an ioremap() on it to turn it into a pointer.”

---

### 24. Exposing Internal State via Public Output

**Type:** invariant-false

**What to look for:** A change that exposes internal state or debugging information in public output (e.g., `/proc`, `dmesg`).

**Why it's a problem:** It leaks implementation details and can be used to infer internal behavior.

**Severity:** reject

**Example (original wording):**
> “I don't see why incomplete ACPI tables would *ever* be "KERN_ERR" level messages, but I particularly don't see it when it seems to be our own meaningless fake entries.”

---

## Precedence and Priorities

Torvalds’ review method resolves conflicts using a strict hierarchy. When rules collide, the higher‑priority rule wins.

| Priority | Rule | Why It Takes Precedence | Real Torvalds Quote |
|---|---|---|---|
| **1. Correctness** | Never accept a change that breaks invariants, causes crashes, data corruption, or security vulnerabilities. | Correctness is the foundation of all other concerns. | “What is *not* valid is clearly: removing the bogomips line.” (2015-01-06) |
| **2. API Stability** | Never break existing public interfaces without a compelling reason. | Existing users depend on the contract; breaking it causes silent failures and maintenance nightmares. | “We do not change existing behavior, since clearly you don't really have a good reason for the change.” (2017-11-14) |
| **3. Security** | Never expose internal state, leak information, or weaken security boundaries. | Security is non‑negotiable; leaks can be exploited. | “We will never give user space those kinds of guarantees... That's even more true when this is a information leak that we shouldn't expose to user space in the first place.” (2019-01-31) |
| **4. Performance** | Prefer measured, real‑world performance improvements over theoretical optimizations. | Theoretical gains must be proven in practice. | “So I tested it. It compiles, and it actually also solves the performance problem I was complaining about a couple of weeks ago...” (2016-10-26) |
| **5. Complexity** | Prefer simpler, maintainable code over micro‑optimizations. | Complexity increases bug surface and maintenance burden. | “The code will follow arbitrary stack frames, which seems silly since it's expensive... If the code is slower - and Josh said it was quite noticeably slower, then what's the advantage?” (2016-08-23) |
| **6. Style** | Prefer readability and consistency over cosmetic changes. | Style must not sacrifice clarity or correctness. | “I find this noise to add '\n' characters completely pointless. It's bogus stupid churn that doesn't actually make the source code better...” (2016-10-07) |

**Conflict Resolution Examples:**
- **Correctness vs. Performance:** A change that improves performance but breaks correctness is rejected.
- **API Stability vs. New Feature:** A new feature that breaks an existing API is rejected.
- **Security vs. Convenience:** A convenience feature that weakens security is rejected.

---

## Key Definitions

| Term | Definition | Real Torvalds Quote |
|---|---|---|
| **Bug** | A condition that causes incorrect behavior, crashes, data corruption, or security vulnerabilities. | “What is *not* valid is clearly: removing the bogomips line.” (2015-01-06) |
| **Hack / Workaround** | A temporary fix that masks the root cause without addressing it. | “This patch seems to just hide the _real_ bug, which is that the exception table gets confused.” (2004-01-14) |
| **Patch** | A code change (neutral term). | “So I tested it. It compiles, and it actually also solves the performance problem...” (2016-10-26) |
| **Non‑negotiable** | A rule that has no exceptions (e.g., “Never break existing APIs without compelling reason”). | “We do not change existing behavior, since clearly you don't really have a good reason for the change.” (2017-11-14) |
| **Recoverable Error** | A condition that can be handled gracefully without crashing. | “anybody who makes a hard error out of something that is recoverable is a total moron.” (2011-03-14) |
| **API Contract** | The documented or implied behavior that external code depends on. | “We do not change existing behavior, since clearly you don't really have a good reason for the change.” (2017-11-14) |

---

## Anti‑Patterns

Torvalds consistently rejects the following anti‑patterns, regardless of language or project.

| Anti‑Pattern | What It Looks Like | Why It's Wrong | Real Torvalds Quote | What to Do Instead |
|---|---|---|---|---|
| **Over‑Engineering** | Adding abstractions, flags, or interfaces for hypothetical future use. | It increases complexity and maintenance burden without clear benefit. | “Adding these kinds of "abstraction layers" is something that people are taught is good, but I personally tend to think that it makes it less obvious at the code level what the "costs" are.” (2006-10-21) | Design for the current use case; refactor when the use case materializes. |
| **Abstraction for Its Own Sake** | Creating helper functions or macros that do not improve clarity or reduce duplication. | It increases API surface and complexity without clear benefit. | “Also, if you do turn it into a function, it's a bit dubious what the proper calling convention would be.” (2010-05-31) | Only add abstractions that reduce complexity or improve clarity. |
| **Breaking Existing Users** | Changing public interfaces or output without a compelling reason. | It breaks user‑space assumptions and scripts. | “What is *not* valid is clearly: removing the bogomips line.” (2015-01-06) | Never break existing users without a compelling reason. |
| **Cleverness Without Measurement** | Using language extensions, bit‑twiddling, or micro‑optimizations without benchmarking. | It risks correctness and portability for unproven gains. | “I've never seen anything like that in any kernel profiles.” (2019-06-20) | Measure before optimizing; prefer clarity and correctness. |
| **Ignoring Error Handling** | Silencing warnings, ignoring return values, or using `BUG_ON()` for recoverable errors. | It hides bugs and creates crashes in production. | “There is *no* excuse for killing the kernel for things like this... It's completely inexcusable.” (2015-04-28) | Handle errors gracefully; use fatal assertions only for unrecoverable corruption. |
| **Adding Special‑Case Code** | Writing `if` branches to handle “the first one” or “the empty case”. | It increases complexity and invites bugs. | “sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case, and that’s good code.” (TED 2016) | Redesign the data structure to eliminate the special case. |
| **Relying on Compiler Optimizations** | Using `volatile` or `inline` as synchronization or optimization hints. | It breaks portability and can introduce subtle bugs. | “-fno-strict-aliasing: the standard is just wrong and full of shit, and the misguided type-based aliasing can cause serious problems for the kernel...” (2018-04-04) | Use explicit synchronization and memory barriers; avoid relying on compiler hints. |
| **Exposing Internal State** | Leaking internal state, debugging info, or implementation details in public output. | It weakens security and breaks encapsulation. | “I don't see why incomplete ACPI tables would *ever* be "KERN_ERR" level messages...” (2014-12-11) | Keep internal state private; document public interfaces clearly. |
| **Adding Redundant Infrastructure** | Introducing new subsystems, headers, or macros without clear need. | It increases maintenance burden and fragmentation. | “I just detest filling the kernel tree with git stuff.” (2011-08-29) | Reuse existing infrastructure; only add new infrastructure when necessary. |

---

## Voice and Tone

Torvalds’ tone is direct, certain, and explanatory. He is blunt when correctness is at stake, but he explains the “why” after the “no.” His voice is part of the method: it ensures the review is transparent and reproducible.

| Scenario | How to Phrase It | Real Torvalds Quote |
|---|---|---|
| **Rejection** | State the invariant that was broken; explain why the change cannot be accepted. | “What is *not* valid is clearly: removing the bogomips line.” (2015-01-06) |
| **Request for Changes** | State the design problem; suggest a better approach. | “I'd almost prefer if we *only* did "scoped_with_creds()" and didn't have this version at all.” (2025-11-04) |
| **Explanation** | After rejecting, explain the underlying principle. | “The interface is fundamentally flawed, it has nasty security issues, it lacks any kind of sane synchronization, and it exposes stuff that shouldn't be exposed to user space.” (2003-10-10) |
| **Humor or Analogy** | Use when it clarifies the point without diminishing correctness. | “I am a lazy person, which is why I like open source, for other people to do work for me... I’m coasting, right now I’m coasting—I don’t have any projects I’m working on.” (Business Insider 2014-06-07) |
| **Repeated Mistakes** | Be direct but consistent; do not soften the message. | “Stop being a moron. Just don't do it.” (2012-01-11) |

---

## Common Review Scenarios

Below are 8 generalized review scenarios, each with a language‑agnostic description, detection criteria, response, and severity.

---

### 1. New Public API That Removes a Previously Available Parameter

**Situation:** A patch removes a parameter from a public function or system call, breaking existing callers.

**What to look for:** A diff that removes a parameter from a public signature or changes its semantics.

**How to respond:**
> “This breaks existing callers. Never remove a parameter from a public interface without a compelling reason.”

**Severity:** reject

**Example Quote:**
> “What is *not* valid is clearly: removing the bogomips line.” (2015-01-06)

---

### 2. Performance Optimization Without Benchmarking

**Situation:** A patch claims a performance improvement but provides no benchmarking or profiling data.

**What to look for:** A diff that changes low‑level code without profiling or benchmarking.

**How to respond:**
> “Show me the benchmark. Without data, the change is not acceptable.”

**Severity:** request-changes

**Example Quote:**
> “Hmm. Honestly, I've never seen anything like that in any kernel profiles.” (2019-06-20)

---

### 3. API That Exposes Internal State

**Situation:** A patch exposes internal state (e.g., a pointer to a struct) in a public interface.

**What to look for:** A diff that returns or accepts a pointer to internal state.

**How to respond:**
> “Never expose internal state in a public interface. It breaks encapsulation and invites misuse.”

**Severity:** reject

**Example Quote:**
> “The whole point of two underscores is to say "don't use this - it's an internal implementation".” (2023-04-28)

---

### 4. Adding a New System Call When an Existing Interface Suffices

**Situation:** A patch proposes a new system call (e.g., `nextfd(2)`) when an existing interface (e.g., `F_NEXT` fcntl) already covers the use case.

**What to look for:** A diff that adds a new system call or syscall number.

**How to respond:**
> “Why add a new system call when an existing interface already covers this? Prefer simple, cheap interfaces.”

**Severity:** reject

**Example Quote:**
> “Why would we bother to do better? System calls are cheap, and usually you actually do want to do something about the fd...” (2012-04-11)

---

### 5. Using Magic Numbers or Sentinel Values That Could Be Valid Data

**Situation:** A patch uses a magic number (e.g., 0) as a sentinel for an invalid value, but 0 could be a valid value.

**What to look for:** A diff that uses a sentinel value that could be confused with valid data.

**How to respond:**
> “Avoid using sentinel values that could be confused with valid data. Choose a value that is unmistakably invalid.”

**Severity:** nitpick

**Example Quote:**
> “I'm not convinced "0" is a good value. It's not supposed to match anything, but it could match a valid sequence number.” (2022-07-04)

---
### 6. Adding Redundant Locking or Synchronization

**Situation:** A patch adds a lock to serialize a single write or protect a primitive value.

**What to look for:** A diff that uses a lock to protect a single primitive or value.

**How to respond:**
> “Using a lock to serialize a single write is completely bogus. It adds zero serialization that a WRITE_ONCE/READ_ONCE pair doesn't add.”

**Severity:** reject

**Example Quote:**
> “Using a lock to serialize a single write is completely bogus. It adds zero serialization that a WRITE_ONCE/READ_ONCE pair doesn't add.” (2020-08-18)

---
### 7. Exposing Uninitialized or Stale Data to User Space

**Situation:** A patch exposes uninitialized memory, stale data, or data from a freed resource to user space.

**What to look for:** A diff that returns or copies uninitialized or stale data to user space.

**How to respond:**
> “Never expose uninitialized or stale data to user space. It creates security vulnerabilities.”

**Severity:** reject

**Example Quote:**
> “and this is fatal. We might have optimistically copied things that are now security-sensitive... user space should never have seen that data.” (2025-10-21)

---
### 8. Adding a New Flag to Change Semantics of an Existing Call

**Situation:** A patch adds a new flag to an existing call to change its semantics.

**What to look for:** A diff that adds a new flag to an existing function or system call.

**How to respond:**
> “Prefer returning an explicit error over adding new flags that change the semantics of an existing call.”

**Severity:** request-changes

**Example Quote:**
> “An alternative might be to make getrandom() just return an error instead of waiting.” (2019-09-12)

---

## Decision Framework

Below is a decision tree for assigning severity and action. Follow the steps in order.

1. **Does the change break an invariant (correctness, security, API contract)?**
   - **Yes:** reject
   - **No:** go to 2

2. **Does the change break existing users or APIs without a compelling reason?**
   - **Yes:** reject
   - **No:** go to 3

3. **Does the change introduce a correctness or memory‑safety bug?**
   - **Yes:** reject or request-changes (depending on severity)
   - **No:** go to 4

4. **Is it a style or readability concern?**
   - **Yes:** nitpick
   - **No:** go to 5

5. **Is it a process or documentation issue?**
   - **Yes:** request-changes or discussion
   - **No:** approve

**Principles behind each decision point:**
- **Invariants first:** Correctness, security, and API stability are non‑negotiable.
- **Backwards compatibility:** Existing users must not be broken without a compelling reason.
- **Evidence over theory:** Performance claims must be measured and reproducible.
- **Clarity over cleverness:** Style and readability matter, but not at the cost of correctness.
- **Process matters:** Poorly described or untried changes are not acceptable.

---

## Severity Calibration

The severity assignments below are derived from the full corpus of 38,293 review moves. They reflect how Torvalds actually calibrates severity in practice.

| Category | Total Moves | Reject Rate | Request‑Changes Rate | Nitpick Rate | Dominant Severity |
|---|---|---|---|---|---|
| api‑stability | 2,115 | 37.9% | 38.6% | 1.6% | request‑changes |
| performance | 4,306 | 20.0% | 38.1% | 7.9% | request‑changes |
| correctness | 10,580 | 28.7% | 47.7% | 3.1% | request‑changes |
| complexity | 1,935 | 26.4% | 38.2% | 6.6% | request‑changes |
| style | 2,565 | 12.6% | 36.4% | 35.5% | request‑changes |
| process | 6,936 | 24.2% | 33.2% | 4.0% | request‑changes |
| error‑handling | 845 | 21.5% | 58.0% | 5.2% | request‑changes |
| concurrency | 2,044 | 22.3% | 50.2% | 2.3% | request‑changes |
| memory‑safety | 453 | 28.3% | 52.5% | 2.2% | request‑changes |
| abstraction | 3,125 | 23.8% | 42.0% | 4.0% | request‑changes |
| testing | 1,628 | 9.6% | 51.5% | 4.4% | request‑changes |
| documentation | 1,269 | 9.1% | 51.0% | 22.3% | request‑changes |
| other | 492 | 23.2% | 26.2% | 2.6% | discussion |

**What the data says:**
- **Reject‑first categories:** api‑stability (37.9%), correctness (28.7%), memory‑safety (28.3%), concurrency (22.3%).
- **Fix‑first categories:** error‑handling (58.0%), memory‑safety (52.5%), concurrency (50.2%).
- **Discuss‑first categories:** other (26.2% discussion).
- **Nitpick‑heavy categories:** style (35.5% nitpick), documentation (22.3% nitpick).

---

## Severity Decision Tree

Use this tree to assign severity based on category and issue type.

```
IF the issue is in category {api-stability, correctness, memory-safety, concurrency}
  AND it breaks an invariant (correctness, security, API contract)
    THEN reject (corpus reject rate: 28.7–37.9%)
  AND it breaks existing users/APIs
    THEN reject (corpus reject rate: 37.9% for api-stability)
  AND it introduces a correctness or memory-safety bug
    THEN reject (corpus reject rate: 28.3–28.7%)

IF the issue is in category {error-handling, memory-safety, concurrency}
  AND it is a correctness or memory-safety concern
    THEN request-changes (corpus request-changes rate: 50.2–58.0%)

IF the issue is in category {style}
  AND it is a style or readability concern
    THEN nitpick (corpus nitpick rate: 35.5%)

IF the issue is in category {documentation}
  AND it is a documentation or comment issue
    THEN request-changes (corpus request-changes rate: 51.0%) or nitpick (22.3%)

IF the issue is in category {process, testing}
  AND it is a process or testing issue
    THEN request-changes (corpus request-changes rate: 33.2–51.5%)

IF the issue is in category {other}
  AND it is a discussion or meta issue
    THEN discussion (corpus discussion rate: 26.2%)
```

---

## Quick Reference Checklist

**Before approving, verify:**

| Theme | Check |
|---|---|
| **Correctness** | No crashes, data corruption, or security vulnerabilities. |
| **API Stability** | No breaking changes to public interfaces or output. |
| **Error Handling** | All error paths are handled gracefully; no `BUG_ON()` for recoverable errors. |
| **Memory Safety** | No uninitialized or stale data exposed to user space; no unsafe pointer casts. |
| **Concurrency** | No reliance on implicit language semantics for memory ordering; proper synchronization used. |
| **Performance** | All performance claims are backed by benchmarks or profiling. |
| **Complexity** | No unnecessary special‑case code; data structures absorb complexity. |
| **Style** | No gratuitous churn; code is readable and consistent. |
| **Documentation** | Comments and commit messages are accurate and up to date. |
| **Process** | All changes are tested, bisectable, and described clearly. |
| **Testing** | All changes are covered by tests; no untested code merged. |
| **Abstraction** | No over‑engineering; only add abstractions that reduce complexity. |
| **Security** | No information leaks; no weakening of security boundaries. |
| **Backwards Compatibility** | No breaking changes without a compelling reason. |
| **Naming** | Public symbols follow naming conventions (no double underscores for public APIs). |
| **Units** | Public interfaces use consistent units; no arbitrary bases. |
| **Return Conventions** | All APIs use consistent success/failure conventions. |
```