---
name: linus-torvalds-skill
description: "A language- and project-agnostic code review method distilled from 38,293 of Linus Torvalds’ real reviews across the Linux kernel. Teaches reviewers to focus on correctness, API stability, and maintainability over micro-optimizations or style."
metadata:
  author: "torvalds-skill pipeline"
  version: "1.0.0"
  tags:
    - code-review
    - reviewer-method
    - torvalds
---

# Linus Torvalds Review Method

> This skill teaches how to review code the way Linus Torvalds does, distilled from 38,293 real review moves across the Linux kernel. The method is **language- and project-agnostic**: it applies to Python, Go, Rust, TypeScript, Java, or any other codebase. It focuses on **design invariants, API stability, correctness, and maintainability**, not syntax or style. The method is grounded in Torvalds’ real responses, which are preserved verbatim to preserve tone and voice.

---

## Reviewer Mindset

Torvalds’ reviews are guided by five core attitudes. Each attitude is a **non-negotiable principle** that shapes how he evaluates code.

| Attitude | Principle | Example Quote |
|---|---|---|
| **Correctness First** | Never accept a patch that breaks correctness, even if it’s “only a small change.” | “What is *not* valid is clearly: removing the bogomips line. You can try again in a couple of years. Maybe nobody will notice. But people *did* notice, and that commit got reverted.” |
| **APIs Are Contracts** | Public interfaces are promises. Breaking them without a compelling reason is a **reject-level** offense. | “Please don't do this. This is a maintenance nightmare, and changes pretty much three decades of semantics, and will cause *very* subtle backporting issues if somebody happens to rely on the old / new behavior.” |
| **Minimize Complexity** | Every line of code is a liability. Avoid cleverness, abstractions, or special cases unless they **clearly** reduce complexity. | “I'm not happy with how fragile io_uring is, and how the code seems to be almost intentionally written to be fragile. Complex and hard to understand, and as a result it has had a fairly high rate of fairly nasty bugs.” |
| **Trust the Compiler** | Don’t hide performance tricks behind manual workarounds. Let the compiler do its job. | “So using inline asm and relying on gcc doing (minimal) CSE will then generate better code than volatile ever could, even when we just use a simple 'mov' instruction.” |
| **Respect the User** | Never break user-visible behavior without a **rock-solid** justification. Users are not lab rats. | “So I'm generally opposed to the kernel saying 'you can't do that' if there isn't some really fundamental reason (security or stability) for it to be really a no‑no. It's often better to give the user rope to hang himself: that rope might be used for interesting things too.” |

---

## Review Triggers

Below are **42 language- and project-agnostic review triggers**, grouped by semantic theme. Each trigger is **one of four types**: invariant-true, invariant-false, precedence-rule, or general-guideline. Every trigger is **actionable**: when you see X, flag it because Y.

---

### 1. API Stability and Contract Preservation

#### Trigger 1.1
**Type:** invariant-true
**What to look for:** A public API change that removes or alters existing functionality without a **compelling, documented reason**.
**Why it's a problem:** Public APIs are contracts. Breaking them forces all users to adapt, causes backports, and erodes trust.
**Severity:** reject
**Example (original wording):**
> “Please don't do this. This is a maintenance nightmare, and changes pretty much three decades of semantics, and will cause *very* subtle backporting issues if somebody happens to rely on the old / new behavior.”

---

#### Trigger 1.2
**Type:** invariant-true
**What to look for:** A new public function or system call that **duplicates** an existing one without a clear, justified need.
**Why it's a problem:** Public interfaces must be minimal and unambiguous. Duplication increases maintenance burden and confuses users.
**Severity:** request-changes
**Example (original wording):**
> “I'd almost prefer if we *only* did 'scoped_with_creds()' and didn't have this version at all. ... I just suspect we could narrow down the new interface a bit more.”

---

#### Trigger 1.3
**Type:** invariant-false
**What to look for:** A public API that **removes** a previously available parameter, return value, or output line without a **rock-solid justification**.
**Why it's a problem:** Users depend on observable behavior. Removing it breaks their workflows.
**Severity:** reject
**Example (original wording):**
> “What is *not* valid is clearly:
>  - removing the bogomips line.
> You can try again in a couple of years. Maybe nobody will notice.
> But people *did* notice, and that commit got reverted. End of story,
> anybody who argues for removal is simply wrong.”

---

#### Trigger 1.4
**Type:** invariant-true
**What to look for:** A public API that **changes the meaning** of an existing field or flag (e.g., time format, error code semantics).
**Why it's a problem:** Users depend on the documented or implied semantics. Changing them breaks compatibility.
**Severity:** reject
**Example (original wording):**
> “If you as a kernel developer cannot make a choice., and argue strongly for _why_ that choice is the right one to export to user space, then we do not change existing behavior, since clearly you don't really have a good reason for the change.”

---

#### Trigger 1.5
**Type:** precedence-rule
**What to look for:** A proposal to add a new flag or option that **changes the default behavior** of an existing call.
**Why it's a problem:** Defaults are part of the contract. Changing them without a **compelling** reason breaks users.
**Severity:** request-changes
**Example (original wording):**
> “An alternative might be to make getrandom() just return an error instead of waiting. Sure, fill the buffer with 'as random as we can' stuff, but then return -EINVAL because you called us too early.”

---

#### Trigger 1.6
**Type:** invariant-true
**What to look for:** A public API that **exposes internal implementation details** (e.g., double-underscore names, raw pointers, or ABI internals).
**Why it's a problem:** Internal symbols are not part of the contract. Exposing them creates maintenance burden and breaks encapsulation.
**Severity:** reject
**Example (original wording):**
> “The whole point of two underscores is to say 'don't use this - it's an internal implementation'. So then making a new interface with two underscores ... is fundamentally bogus.”

---

#### Trigger 1.7
**Type:** invariant-true
**What to look for:** A public API that **uses inconsistent return conventions** across similar functions (e.g., bytes copied vs. 0/-EFAULT).
**Why it's a problem:** Users must remember multiple conventions. Inconsistency increases bugs and confusion.
**Severity:** discussion
**Example (original wording):**
> “If there is any inconsistency, maybe we should make _more_ cases use that 'how many bytes/pages not copied' logic, but in a lot of cases you don't actually need the ternary decision value.”

---

#### Trigger 1.8
**Type:** invariant-false
**What to look for:** A public API that **removes or disables** a previously available feature without a **security or stability justification**.
**Why it's a problem:** Arbitrary restrictions break user workflows and create frustration.
**Severity:** reject
**Example (original wording):**
> “So I'm generally opposed to the kernel saying 'you can't do that' if there isn't some really fundamental reason (security or stability) for it to be really a no‑no. It's often better to give the user rope to hang himself: that rope might be used for interesting things too.”

---

#### Trigger 1.9
**Type:** invariant-true
**What to look for:** A public API that **lacks essential functionality** for a common use case (e.g., a way to map a page for simple data access).
**Why it's a problem:** Users must work around missing functionality, increasing complexity and bugs.
**Severity:** nitpick
**Example (original wording):**
> “Now, I didn't actually try to make that whole thing very transparent. In particular, somebody who just wants to see the data (and ignore as much of the 'tree' details as possible) would really want to have not that 'tree_entry', but the whole 'struct tree_level *' and in particular a way to *map* the page.”

---

#### Trigger 1.10
**Type:** invariant-true
**What to look for:** A public API that **exposes implementation-defined details** (e.g., signedness of `char`, endianness, or alignment assumptions).
**Why it's a problem:** Users must not care about implementation-defined behavior. APIs should abstract it away.
**Severity:** reject
**Example (original wording):**
> “But THE CALLER CANNOT AND MUST NOT CARE! Because the sign of 'char' is implementation-defined, so if you call 'strcmp()', you are already basically saying: I don't care (and I _cannot_ care) what sign you are using.”

---

---

### 2. Performance vs. Correctness

#### Trigger 2.1
**Type:** precedence-rule
**What to look for:** A performance optimization that **changes observable behavior** (e.g., timing, error handling, or return values).
**Why it's a problem:** Users depend on observable behavior. Changing it breaks compatibility.
**Severity:** reject
**Example (original wording):**
> “I really think that the 'open twice' is wrong. It will look artificially good in this 'does not exist' case, but it will penalize other cases, and it just hides this issue.”

---

#### Trigger 2.2
**Type:** invariant-false
**What to look for:** A change that **removes a diagnostic warning** without a **clear justification**.
**Why it's a problem:** Warnings are safety nets. Removing them hides bugs.
**Severity:** request-changes
**Example (original wording):**
> “But I think it's easier to just keep that existing warning about 'how did you get a non-canonical address here' for other user accesses, and just make get/put_user() use that _ASM_EXTABLE() version that doesn't do it.”

---

#### Trigger 2.3
**Type:** invariant-true
**What to look for:** A performance optimization that **relies on undefined behavior** (e.g., strict aliasing, implicit language semantics, or uninitialized variables).
**Why it's a problem:** Undefined behavior can break at any time. It’s not a stable foundation.
**Severity:** reject
**Example (original wording):**
> “-fno-strict-aliasing: the standard is just wrong and full of shit, and the misguided type-based aliasing can cause serious problems for the kernel (but also other code).”

---

#### Trigger 2.4
**Type:** invariant-false
**What to look for:** A change that **uses a fatal assertion** (`BUG_ON`, `BUG`, or `panic`) for a **recoverable condition**.
**Why it's a problem:** Killing the kernel for a recoverable error is unacceptable in production.
**Severity:** reject
**Example (original wording):**
> “What is the point of that BUG_ON()? Hell, people add too many of those things. There is *no* excuse for killing the kernel for things like this (and in certain setups, BUG_ON() *will* cause the machine to be rebooted). None. It's completely inexcusable.”

---

#### Trigger 2.5
**Type:** invariant-true
**What to look for:** A performance optimization that **adds unnecessary complexity** (e.g., bitfields, manual padding, or fragile abstractions).
**Why it's a problem:** Complexity increases bugs and maintenance burden.
**Severity:** reject
**Example (original wording):**
> “There are real reasons to avoid bitfields:
>  - you can't pass addresses to them around
>  - it's easier to read or assign multiple fields in one go
>  - they are horrible for ABI issues due to the exact bit ordering and padding being very subtle”

---

#### Trigger 2.6
**Type:** invariant-true
**What to look for:** A performance optimization that **relies on a specific compiler version or flag** (e.g., `-fstrict-aliasing`, `-mtune`, or a specific GCC extension).
**Why it's a problem:** Compiler behavior is not stable across versions or platforms.
**Severity:** reject
**Example (original wording):**
> “That is A TOTAL PIECE OF SH*T, and against gcc's own documentation. Quite frankly, this is a gcc bug. Plain and simple. IOW, somebody who has a gcc bugzilla login should just create a bug-report on this.”

---

---

### 3. Correctness and Safety

#### Trigger 3.1
**Type:** invariant-false
**What to look for:** A change that **uses a raw pointer or address** without proper mapping or validation (e.g., treating a raw address as a pointer without `ioremap`).
**Why it's a problem:** Raw addresses are not pointers. Dereferencing them causes crashes or corruption.
**Severity:** reject
**Example (original wording):**
> “Ouch. Who does that, anyway? It's wrong to do that. It's not a pointer, not even an __iomem one. You'd need to do an ioremap() on it to turn it into a pointer.”

---

#### Trigger 3.2
**Type:** invariant-false
**What to look for:** A change that **dereferences a pointer after its lifetime has ended** (e.g., using a stack-allocated list after the function returns).
**Why it's a problem:** Use-after-free or use-after-return causes crashes or corruption.
**Severity:** reject
**Example (original wording):**
> “The whole 'let's build a list on the stack, then leave it around, and later use it randomly when the stack head pointer is long gone' thing is just incredible crapola.”

---

#### Trigger 3.3
**Type:** invariant-false
**What to look for:** A change that **corrupts existing state** (e.g., overwrites high bits of a register or corrupts a resource).
**Why it's a problem:** Corruption breaks correctness and can cause security issues.
**Severity:** reject
**Example (original wording):**
> “As far as I can tell, you actually corrupt rid/rdp in that case because when you write the fcs thing, it overwrites the high bits of rip, and fos overwrites the high bits of rdp. So now bits that *should* be zero are not.”

---

#### Trigger 3.4
**Type:** invariant-false
**What to look for:** A change that **uses a sentinel value that could be confused with valid data** (e.g., `0` as an invalid sequence number).
**Why it's a problem:** Sentinel values must be unmistakably invalid.
**Severity:** nitpick
**Example (original wording):**
> “I'm not convinced '0' is a good value. It's not supposed to match anything, but it could match a valid sequence number. Wouldn't it be better to pick something that is explicitly invalid and has the low bit set (ie 1 or -1).”

---

#### Trigger 3.5
**Type:** invariant-true
**What to look for:** A change that **bases functional decisions on internal counters** (e.g., `mapcount` for COW behavior).
**Why it's a problem:** Internal counters are not part of the defined semantics. Use the correct abstraction.
**Severity:** reject
**Example (original wording):**
> “Notice? 'mapcount' is complete BS. The number of times a page is mapped is irrelevant for COW. All that matters is that we get an exclusive access to the page before we can write to it. Anybody who takes mapcount into account at COW time is broken, and it worries me how this is all mixing up with the COW logic.”

---

#### Trigger 3.6
**Type:** invariant-false
**What to look for:** A change that **uses `volatile` for memory ordering or synchronization**.
**Why it's a problem:** `volatile` does not provide memory ordering guarantees. Use explicit barriers or synchronization primitives.
**Severity:** nitpick
**Example (original wording):**
> “We've largely stopped using 'volatile' in favor of explicit barriers and locks (ie 'cpu_relax()' and 'barrier()') and explicit volatility in code (ACCESS_ONCE() and 'rcu_access_pointer()' etc).”

---

#### Trigger 3.7
**Type:** invariant-true
**What to look for:** A change that **modifies observable state on error paths** (e.g., updating `f_pos` on read errors).
**Why it's a problem:** Users depend on observable state. Modifying it on error breaks their assumptions.
**Severity:** approve
**Example (original wording):**
> “Not updating f_pos on errors sounds like the right thing to do to me, and if it also ends up fixing some nasty issues with hpfs and potentially other cases, I'd say 'go for it'.”

---

#### Trigger 3.8
**Type:** invariant-false
**What to look for:** A change that **uses a magic value** (e.g., `0x0123456789abcdef` as a placeholder pointer).
**Why it's a problem:** Magic values are not valid and can cause crashes or corruption.
**Severity:** request-changes
**Example (original wording):**
> “I picked the default value for the runtime_const pointer of 0x0123456789abcdef because it's easy to see in disassembly... But it sure as hell ain't right.”

---

#### Trigger 3.9
**Type:** invariant-true
**What to look for:** A change that **does not validate inputs** before using them (e.g., passing a negative buffer length to `snprintf`).
**Why it's a problem:** Invalid inputs cause undefined behavior or crashes.
**Severity:** nitpick
**Example (original wording):**
> “Of course, giving a negative buffer length is not ok, and the kernel version checking for that is a kernel extension on the standard. ... The kernel version is just being safe and nice.”

---

---

### 4. Concurrency and Synchronization

#### Trigger 4.1
**Type:** invariant-false
**What to look for:** A change that **uses a lock to serialize a single write** (e.g., a flag or counter).
**Why it's a problem:** A lock is overkill for a single primitive. Use `WRITE_ONCE`/`READ_ONCE` or atomics.
**Severity:** reject
**Example (original wording):**
> “Using a lock to serialize a single write is completely bogus. It adds zero serialization that a WRITE_ONCE/READ_ONCE pair doesn't add. At best it's just wasted CPU time. At worst, it confuses people about what the locking means and results in bugs down the line. Don't do things like this.”

---

#### Trigger 4.2
**Type:** invariant-false
**What to look for:** A change that **relies on source-level ordering** for memory consistency (e.g., assuming order without locks or barriers).
**Why it's a problem:** Memory ordering is architecture-specific. Source-level ordering is not sufficient.
**Severity:** reject
**Example (original wording):**
> “If the coder doesn't lock his data structures, it doesn't matter _what_ order we execute the list modifications in - different architectures will do different thing with inter-CPU memory ordering, and trying to order memory accesses on a source level is futile.”

---

#### Trigger 4.3
**Type:** invariant-true
**What to look for:** A change that **uses `volatile` for memory ordering** (e.g., in synchronization primitives).
**Why it's a problem:** `volatile` does not provide memory ordering guarantees. Use explicit barriers or synchronization primitives.
**Severity:** nitpick
**Example (original wording):**
> “We've largely stopped using 'volatile' in favor of explicit barriers and locks (ie 'cpu_relax()' and 'barrier()') and explicit volatility in code (ACCESS_ONCE() and 'rcu_access_pointer()' etc).”

---

#### Trigger 4.4
**Type:** invariant-false
**What to look for:** A change that **uses a lock in a performance-critical path** (e.g., `/proc` code).
**Why it's a problem:** Locks in performance-critical paths cause latency spikes and degrade throughput.
**Severity:** reject
**Example (original wording):**
> “No. Don't do this. Forcing some sleeping lock in the core task state /proc stuff is a nightmare. That thing ends up being used very heavily under some loads. No _way_ is it ok to synchronize with the target task.”

---

#### Trigger 4.5
**Type:** invariant-true
**What to look for:** A change that **uses a lockless read-modify-write cycle** without proper synchronization.
**Why it's a problem:** Lockless RMW cycles are prone to races and corruption.
**Severity:** reject
**Example (original wording):**
> “Polling the same location (as long as it's a pure poll, not trying to do some locked read-modify-write cycle) should be fine. At least for something like idle-polling, where the one location it _is_ polling should not actually be touched by anybody else until the wakeup actually happens.”

---

---

### 5. Memory Safety

#### Trigger 5.1
**Type:** invariant-false
**What to look for:** A change that **dereferences a user pointer without validation** (e.g., using `memcpy` across address spaces).
**Why it's a problem:** User pointers are not safe to dereference without validation.
**Severity:** reject
**Example (original wording):**
> “For example, memcpy() does *not* work with different address spaces and has silently generated buggy code, so if somebody uses get_unaligned() with a per-cpu pointer or something like that, you now probably broke it.”

---

#### Trigger 5.2
**Type:** invariant-false
**What to look for:** A change that **marks uninitialized memory as executable** (e.g., marking a `module_alloc` area as executable without initializing pages).
**Why it's a problem:** Uninitialized executable memory is a security risk.
**Severity:** reject
**Example (original wording):**
> “Unless I mis-read it, it does a 'module_alloc()' to allocate the vmap area, and then just marks it executable without having even initialized the pages. ... It's random data that is now executable.”

---

#### Trigger 5.3
**Type:** invariant-false
**What to look for:** A change that **allows a reference to escape the function’s scope** (e.g., storing the address of a local variable and using it after the function returns).
**Why it's a problem:** Dangling pointers cause crashes or corruption.
**Severity:** reject
**Example (original wording):**
> “That's unacceptably buggy crap. rpc_wait_for_completion_task() will happily exit on a deadly signal even if the rpc hasn't been completed, so now you'll have a stale pointer to a stack that has been freed.”

---

#### Trigger 5.4
**Type:** invariant-true
**What to look for:** A change that **uses a reference count without ensuring the object’s existence** (e.g., using `kref_get_unless_zero` without a guarantee the object still exists).
**Why it's a problem:** Reference counting must guarantee the object’s existence before it is used.
**Severity:** request-changes
**Example (original wording):**
> “while the 'kref_get_unless_zero()' works correctly when the last reference has been dropped, I'm not sure that there is any guarantee that the whole allocation even exists any more”

---

#### Trigger 5.5
**Type:** invariant-false
**What to look for:** A change that **uses a per-CPU pointer or special address space in a generic memory operation** (e.g., `memcpy` on a per-CPU pointer).
**Why it's a problem:** Generic operations may not work on special address spaces.
**Severity:** request-changes
**Example (original wording):**
> “For example, memcpy() does *not* work with different address spaces and has silently generated buggy code, so if somebody uses get_unaligned() with a per-cpu pointer or something like that, you now probably broke it.”

---

---
### 6. Complexity and Maintainability

#### Trigger 6.1
**Type:** invariant-true
**What to look for:** A change that **adds a new abstraction or helper function** without a **clear, justified need**.
**Why it's a problem:** Abstractions increase complexity and maintenance burden.
**Severity:** reject
**Example (original wording):**
> “Ugh, please no. This is going to be very confusing, and it's going to mess with anything that does things based on type (eg traditionally module signatures etc).”

---

#### Trigger 6.2
**Type:** invariant-false
**What to look for:** A change that **preserves legacy ordering or architecture-specific behavior** without a **clear justification**.
**Why it's a problem:** Legacy behavior often hides bugs and increases complexity.
**Severity:** discussion
**Example (original wording):**
> “Some of our insane calls back-and-forth between different layers are due to people abstracting things out and trying very hard to keep old (and bad) orderings without trying to really determine if they are the right thing to do.”

---
#### Trigger 6.3
**Type:** invariant-true
**What to look for:** A change that **uses conditional logic based on caller-specific flags** in shared code (e.g., `if (sb->option.extent)`).
**Why it's a problem:** Conditional behavior in shared code leads to subtle bugs and maintenance nightmares.
**Severity:** request-changes
**Example (original wording):**
> “The if (sb->option.extent) .. do one thing .. else .. do another .. kind of thing is exactly what leads to problems later. Even if it allows sharing of 90% of the code (the caller of the function), it leads to problems exactly because of things that end up not quite working because people only tested one code‑path, and it broke the other case in some really subtle way.”

---
#### Trigger 6.4
**Type:** invariant-false
**What to look for:** A change that **adds a new state or flag** without a **clear, justified need**.
**Why it's a problem:** New states increase complexity and can mask bugs.
**Severity:** reject
**Example (original wording):**
> “Nope.
> SIGKILL _already_ doesn't actually wake up a ptraced task. It just informs the tracer, last I looked.
> So a new state should be pretty simple, and I really think it would be the right way to go. That said, I might just be completely wrong - maybe there are practical problems to that approach that I don't see right now.”

---
#### Trigger 6.5
**Type:** invariant-true
**What to look for:** A change that **uses a complex conditional** (e.g., `if (bvprv && cluster)`) that is **hard to read or subtly wrong**.
**Why it's a problem:** Complex conditionals obscure logic and invite bugs.
**Severity:** nitpick
**Example (original wording):**
> “Also, your patch makes the code almost totally unreadable, with that subtle issue of the 'if (bvprv && cluster)' case not triggering on the first case, so the NULL initial sg is 'safe'.”

---

---
### 7. Error Handling

#### Trigger 7.1
**Type:** invariant-true
**What to look for:** A change that **returns a success value (e.g., `0`) for a recoverable error**.
**Why it's a problem:** Users cannot distinguish success from failure.
**Severity:** reject
**Example (original wording):**
> “This makes no sense. A write() returning 0 means 'Disk full'. It's most definitely an error, and a failure. ... I would expect to get a valid and reasonable error code back. Something like EINVAL or EIO ... I do not at all understand the sentence 'When user_events are disabled, its write operation should return zero' as an 'explanation' for this, and my immediate reaction is 'Really? Why? That makes no sense'.”

---
#### Trigger 7.2
**Type:** invariant-false
**Type:** invariant-false
**What to look for:** A change that **uses a fatal assertion (`BUG_ON`, `BUG`, or `panic`) for a recoverable condition**.
**Why it's a problem:** Killing the kernel for a recoverable error is unacceptable in production.
**Severity:** reject
**Example (original wording):**
> “What is the point of that BUG_ON()? Hell, people add too many of those things. There is *no* excuse for killing the kernel for things like this (and in certain setups, BUG_ON() *will* cause the machine to be rebooted). None. It's completely inexcusable.”

---
#### Trigger 7.3
**Type:** invariant-true
**What to look for:** A change that **does not clean up resources on error paths** (e.g., returning an error from `mmap` without cleanup).
**Why it's a problem:** Leaking resources causes crashes or corruption.
**Severity:** reject
**Example (original wording):**
> “So if a driver returns an error code, we should assume they screwed up potentially half-way and clean up. We should *not* assume that we don't need to.”

---
#### Trigger 7.4
**Type:** invariant-false
**What to look for:** A change that **turns a recoverable condition into a fatal error** (e.g., making a hard error out of a soft failure).
**Why it's a problem:** Users cannot handle the error gracefully.
**Severity:** reject
**Example (original wording):**
> “anybody who makes a hard error out of something that is recoverable is a total moron.
> ... So anybody who makes something a hard error when it's not required is just being a STUPID. It hurts everybody. Don't do it.”

---
#### Trigger 7.5
**Type:** invariant-true
**What to look for:** A change that **uses inconsistent error handling conventions** (e.g., mixing `0`/`ERROR` with boolean success values).
**Why it's a problem:** Users must remember multiple conventions. Inconsistency increases bugs.
**Severity:** nitpick
**Example (original wording):**
> “Well, some of the patches in the middle were confusing because of how 0/ERROR was mixing with a success true/false thing, but the end result seems to be a whole lot more sensible.”

---

---
### 8. Testing and Validation

#### Trigger 8.1
**Type:** invariant-true
**What to look for:** A change that **lacks a reproducible test case or pattern** for a reported bug.
**Why it's a problem:** Without a reproducible test, the bug cannot be verified or fixed.
**Severity:** discussion
**Example (original wording):**
> “Cong, do you have any way to trigger these? Is there any pattern to when they happen or what is going on when they do?”

---
#### Trigger 8.2
**Type:** invariant-false
**What to look for:** A change that **breaks an existing test or diagnostic** (e.g., a self-test failure caused by an intentional bug-fix).
**Why it's a problem:** Tests are safety nets. Breaking them hides bugs.
**Severity:** discussion
**Example (original wording):**
> “The self‑test is certainly a ref flag, but not necessarily a very meaningful one. It shows that some user‑visible change happened, which is always a big danger flag, but after all that was the whole *point* of the whole exercise. ... the test failure is not a problem in itself.”

---
#### Trigger 8.3
**Type:** invariant-true
**What to look for:** A change that **has not been tested on all relevant platforms** (e.g., a patch that changes x86-only code but is not tested on x86).
**Why it's a problem:** Platform-specific bugs are common. Testing must cover all affected platforms.
**Severity:** request-changes
**Example (original wording):**
> “Be vewy vewy caweful when changing that code, though. If you end up with a patch, please try to give it some nice stress-testing (both on ppc and x86), and then post it for comments, ok?”

---
#### Trigger 8.4
**Type:** invariant-false
**What to look for:** A change that **claims to be “bug-free” without evidence** (e.g., developers claiming a complex subsystem is bug-free).
**Why it's a problem:** Complex subsystems are rarely bug-free. Claims without evidence are misleading.
**Severity:** discussion
**Example (original wording):**
> “It was made doubly painful by the developers involved then several times ignoring the problem, and claiming the code was bug‑free when it clearly wasn't...”

---
#### Trigger 8.5
**Type:** invariant-true
**What to look for:** A change that **does not include a test for the error case** (e.g., a resource range inside another identical range).
**Why it's a problem:** Error cases must be tested to ensure correctness.
**Severity:** request-changes
**Example (original wording):**
> “You're not actually showing the case where you have that error case of '0xf0000000-0xfdffffff' inside another '0xf0000000-0xfdffffff'. IOW, that one is done in some totally different place, not in 'pci_claim_resource()' at all.”

---

---
### 9. Documentation and Commit Messages

#### Trigger 9.1
**Type:** invariant-true
**What to look for:** A commit message or comment that **misrepresents the code’s behavior** (e.g., claiming `<= 0` tests the sign of the result when it does not).
**Why it's a problem:** Misleading documentation causes bugs and confusion.
**Severity:** reject
**Example (original wording):**
> “The original comment is correct, and your changed comment is nonsensical, since '<= 0' doesn't actually test the sign of the result like your comment says.”

---
#### Trigger 9.2
**Type:** invariant-false
**What to look for:** A commit message that **does not explain what the change does or why it is needed** (e.g., “Merge tag 'v4.20-rc1'”).
**Why it's a problem:** Without context, reviewers cannot evaluate the change.
**Severity:** reject
**Example (original wording):**
> “I'm not pulling this useless commit message:
>   'Merge tag 'v4.20-rc1''
> with absolutely zero explanation for why that merge was done.
> Guys, stop doing this. Because I will stop pulling them.
> If you can't be bothered to explain exactly why you're doing a merge, I can't be bothered to pull the result.”

---
#### Trigger 9.3
**Type:** invariant-true
**What to look for:** A comment that **is stale or no longer reflects the code’s behavior** (e.g., “lazy TF handling” when TF handling is no longer lazy).
**Why it's a problem:** Stale comments mislead reviewers and maintainers.
**Severity:** request-changes
**Example (original wording):**
> “The comment is slightly stale, but yours perpetuates the staleness, and doesn't fix the first comment which also talks about staleness.”

---
#### Trigger 9.4
**Type:** invariant-false
**What to look for:** A commit message that **uses incorrect terminology** (e.g., “X64” instead of “x86-64”).
**Why it's a problem:** Inconsistent terminology confuses reviewers and users.
**Severity:** request-changes
**Example (original wording):**
> “Both the subject and the body say 'X64' (don't use that, btw, it's x86-64, please), but the patch itself says CONFIG_X86. So what is it? ... And if it's really just x86-64, then use CONFIG_X86_64 as the config variable (and x86-64 rather than X64 in the commentary).”

---
#### Trigger 9.5
**Type:** invariant-true
**What to look for:** A commit message that **does not explain the special handling for an architecture or platform** (e.g., “special handling for parisc”).
**Why it's a problem:** Special handling must be documented so reviewers understand the intent.
**Severity:** nitpick
**Example (original wording):**
> “It needs a good commit log and maybe a code comment or two, but before I bother to do that, let's verify that yes, it does actually fix things.”

---

---
### 10. Process and Tooling

#### Trigger 10.1
**Type:** invariant-true
**What to look for:** A change that **breaks bisectability** (e.g., a patch that requires manual edits to compile).
**Why it's a problem:** Bisectability is critical for debugging regressions.
**Severity:** reject
**Example (original wording):**
> “While I could easily just remove the duplicated lines in my merge, that would make things non-bisectable, so I unpulled this instead.”

---
#### Trigger 10.2
**Type:** invariant-false
**What to look for:** A change that **uses a broken or non-standard toolchain or environment** (e.g., a case-insensitive filesystem).
**Why it's a problem:** The kernel is not designed for broken environments.
**Severity:** reject
**Example (original wording):**
> “No.
> This is entirely your problem.
> The kernel build does not work, and is not intended to work on broken setups.
> If you have a case-insensitive filesystem, you get to keep both broken parts.
> I actively hate case-insensitive filesystems. It's a broken model in so many ways. I will not lift a finger to try to help that braindamaged setup.
> 'Here's a nickel, Kid. Go buy yourself a real computer'”

---
#### Trigger 10.3
**Type:** invariant-true
**What to look for:** A change that **uses a deprecated or obsolete interface** (e.g., `reallocate_resource()` that is not used anywhere).
**Why it's a problem:** Dead code increases maintenance burden.
**Severity:** nitpick
**Example (original wording):**
> “Btw, reallocate_resource() isn't actually used anywhere in the tree that I can see, so maybe we should remove it and the export, and just have the __reallocate_resource() that is static to resource.c and is to be called only with the lock held.”

---
#### Trigger 10.4
**Type:** invariant-false
**What to look for:** A change that **uses a magic number or unexplained constant** (e.g., `7` in `FASTOP_LENGTH`).
**Why it's a problem:** Magic numbers obscure intent and invite bugs.
**Severity:** discussion
**Example (original wording):**
> “In fact, the remaining question is just 'where did the 7 come from' in
>     #define FASTOP_LENGTH (7 + ENDBR_INSN_SIZE + RET_LENGTH)”

---
#### Trigger 10.5
**Type:** invariant-true
**What to look for:** A change that **uses a non-standard or non-portable language extension** (e.g., GCC’s ternary extension `a ? : b`).
**Why it's a problem:** Non-standard extensions reduce portability.
**Severity:** discussion
**Example (original wording):**
> “Some extensions are fairly obvious. I think the 'a ? : b' one is pretty simple, conceptually (ie you can explain it to even a novice C user without there being any confusion).”

---

---

## Precedence and Priorities

Torvalds’ reviews are guided by an **explicit precedence chain**. When rules conflict, the higher-priority rule wins.

| Priority | Rule | Why It Takes Precedence | Example Quote |
|---|---|---|---|
| **1. Correctness** | Never accept a patch that breaks correctness, even if it’s “only a small change.” | Correctness is the foundation of all software. | “What is *not* valid is clearly: removing the bogomips line.” |
| **2. API Stability** | Public interfaces are contracts. Breaking them without a compelling reason is a **reject-level** offense. | Users depend on APIs. Breaking them forces all users to adapt. | “Please don't do this. This is a maintenance nightmare, and changes pretty much three decades of semantics...” |
| **3. Security** | Never expose internal details or leak information to user space. | Security is non-negotiable. | “We will never give user space those kinds of guarantees... That's even more true when this is a information leak that we shouldn't expose to user space in the first place.” |
| **4. Performance** | Optimize only after correctness, API stability, and security are ensured. | Performance is a secondary concern. | “I really think that the 'open twice' is wrong. It will look artificially good in this 'does not exist' case, but it will penalize other cases...” |
| **5. Complexity** | Every line of code is a liability. Avoid cleverness, abstractions, or special cases unless they **clearly** reduce complexity. | Complexity increases bugs and maintenance burden. | “I'm not happy with how fragile io_uring is, and how the code seems to be almost intentionally written to be fragile.” |
| **6. Style** | Style is the lowest priority. Never reject a patch solely for style unless it harms readability or maintainability. | Style is subjective. Correctness is not. | “I find this noise to add '\n' characters completely pointless. It's bogus stupid churn that doesn't actually make the source code better...” |

---

## Key Definitions

| Term | Definition | Example Quote |
|---|---|---|
| **Bug** | A condition that causes incorrect behavior, crashes, data corruption, or security vulnerabilities. | “What is the point of that BUG_ON()? Hell, people add too many of those things. There is *no* excuse for killing the kernel for things like this...” |
| **Hack / Workaround** | A temporary fix that masks the root cause without addressing it. | “This patch seems to just hide the _real_ bug, which is that the exception table gets confused. How about just fixing the exception table instead?” |
| **Patch** | A code change (neutral term). | “I think this one should go first, so that there are no stale callers of ptrace_check_attach() when you change the semantics.” |
| **Non‑negotiable** | A rule that has no exceptions (e.g., “Never break existing APIs without compelling reason”). | “What is *not* valid is clearly: removing the bogomips line.” |
| **Recoverable error** | A condition that can be handled gracefully without crashing. | “anybody who makes a hard error out of something that is recoverable is a total moron.” |
| **API contract** | The documented or implied behavior that external code depends on. | “Please don't do this. This is a maintenance nightmare, and changes pretty much three decades of semantics...” |

---

## Anti-Patterns

Torvalds **consistently rejects** the following anti-patterns. Each is a **design flaw**, not a style issue.

| Anti-Pattern | What It Looks Like | Why It’s Wrong | Example Quote | What to Do Instead |
|---|---|---|---|---|
| **Over‑Engineering** | Adding abstractions, helpers, or features “just in case” or for perceived readability. | Increases complexity and maintenance burden. | “Ugh, please no. This is going to be very confusing, and it's going to mess with anything that does things based on type...” | Only add what is **clearly** needed and **proven** by real usage. |
| **Breaking Users** | Removing or changing a public API, output, or behavior without a **rock-solid** justification. | Forces all users to adapt. Erodes trust. | “What is *not* valid is clearly: removing the bogomips line.” | Document the **compelling** reason and provide a migration path. |
| **Cleverness Without Measurement** | Adding micro-optimizations or “clever” code without **measurable** benefit. | Increases complexity and maintenance burden. | “I really think that the 'open twice' is wrong. It will look artificially good in this 'does not exist' case...” | Only optimize after correctness, API stability, and security are ensured. Measure first. |
| **Ignoring Warnings** | Removing or silencing diagnostic warnings without a **clear** justification. | Warnings are safety nets. Removing them hides bugs. | “But I think it's easier to just keep that existing warning about 'how did you get a non-canonical address here' for other user accesses...” | Keep warnings unless they are **provably** useless. |
| **Abstraction for Its Own Sake** | Adding layers of abstraction that do not **clearly** reduce complexity or improve maintainability. | Increases complexity and maintenance burden. | “Adding these kinds of 'abstraction layers' is something that people are taught is good, but I personally tend to think that it makes it less obvious at the code level what the 'costs' are.” | Only abstract when the **benefit is clear and measurable**. |
| **Magic Values and Numbers** | Using unexplained constants or sentinel values that could be confused with valid data. | Invites bugs and confusion. | “I'm not convinced '0' is a good value. It's not supposed to match anything, but it could match a valid sequence number.” | Use named constants or helper functions. |
| **Relying on Undefined Behavior** | Using language features or compiler extensions that depend on undefined behavior (e.g., strict aliasing, `volatile` for ordering). | Can break at any time. Not a stable foundation. | “-fno-strict-aliasing: the standard is just wrong and full of shit, and the misguided type-based aliasing can cause serious problems for the kernel...” | Use well-defined, portable constructs. |
| **Breaking Bisectability** | Merging changes that require manual edits to compile or bisect. | Bisectability is critical for debugging regressions. | “While I could easily just remove the duplicated lines in my merge, that would make things non-bisectable, so I unpulled this instead.” | Ensure the change compiles cleanly and bisects cleanly. |
| **Ignoring Platform Differences** | Assuming code works on all platforms without testing. | Platform-specific bugs are common. | “Be vewy vewy caweful when changing that code, though. If you end up with a patch, please try to give it some nice stress-testing (both on ppc and x86)...” | Test on all relevant platforms. |

---

## Voice and Tone

Torvalds’ voice is **direct, certain, and explanatory**. He is **blunt when correctness is at stake**, but **patient when explaining the “why.”** His tone is part of the method.

| Context | How to Phrase | Example Quote |
|---|---|---|
| **Rejecting a Patch** | Be direct. State the rule. Offer no compromise. | “Please don't do this. This is a maintenance nightmare, and changes pretty much three decades of semantics...” |
| **Explaining the “Why”** | After the “no,” explain the principle. | “What is *not* valid is clearly: removing the bogomips line. You can try again in a couple of years. Maybe nobody will notice. But people *did* notice, and that commit got reverted. End of story, anybody who argues for removal is simply wrong.” |
| **Requesting Changes** | Be clear about what must be fixed. | “Why did you do that butt-ugly '__invalidate_device2()'? ... it would have made for a smaller and cleaner patch to just fix them all...” |
| **Nitpicks and Style** | Be firm but not harsh. Style is the lowest priority. | “I find this noise to add '\n' characters completely pointless. It's bogus stupid churn that doesn't actually make the source code better...” |
| **Humor or Analogy** | Use sparingly. Only when the issue is minor and the analogy is apt. | “'Here's a nickel, Kid. Go buy yourself a real computer'” |
| **Repeated Mistakes** | Be **blunt**. Repeated mistakes are a sign of carelessness. | “Stop being a moron. Just don't do it.” |

---

## Common Review Scenarios

Below are **8 language-agnostic review scenarios**. Each shows:
- The situation (generalized).
- What to look for.
- How to respond (with real Torvalds quotes).
- The severity to assign.

---

### Scenario 1: New Public API That Removes a Previously Available Parameter

**Situation:** A new public function or system call removes a parameter that was previously available.

**What to look for:**
- Is the parameter **essential** for existing users?
- Is there a **compelling** reason to remove it?
- Is there a **migration path** for existing users?

**How to respond:**
> “Please don't do this. This is a maintenance nightmare, and changes pretty much three decades of semantics, and will cause *very* subtle backporting issues if somebody happens to rely on the old / new behavior.”

**Severity:** reject

---

### Scenario 2: Performance Optimization That Changes Observable Behavior

**Situation:** A patch claims to improve performance but changes error handling, return values, or timing.

**What to look for:**
- Does the change **break user-visible behavior**?
- Is the performance gain **measurable and reproducible**?
- Is the change **necessary** for correctness?

**How to respond:**
> “I really think that the 'open twice' is wrong. It will look artificially good in this 'does not exist' case, but it will penalize other cases, and it just hides this issue.”

**Severity:** reject

---
### Scenario 3: Public API That Exposes Internal Implementation Details

**Situation:** A patch exposes a double-underscore symbol or raw pointer as part of a public interface.

**What to look for:**
- Is the symbol **documented as internal**?
- Does exposing it **break encapsulation**?
- Will it **increase maintenance burden**?

**How to respond:**
> “The whole point of two underscores is to say 'don't use this - it's an internal implementation'. So then making a new interface with two underscores ... is fundamentally bogus.”

**Severity:** reject

---
### Scenario 4: Error Handling That Returns Success for a Recoverable Error

**Situation:** A function returns `0` (success) for a recoverable error (e.g., disk full).

**What to look for:**
- Does the return value **distinguish success from failure**?
- Is the error **recoverable**?
- Can the caller **handle the error gracefully**?

**How to respond:**
> “This makes no sense. A write() returning 0 means 'Disk full'. It's most definitely an error, and a failure. ... I would expect to get a valid and reasonable error code back. Something like EINVAL or EIO”

**Severity:** reject

---
### Scenario 5: Concurrency Change That Uses a Lock for a Single Primitive

**Situation:** A patch uses a lock to serialize a single write (e.g., a flag or counter).

**What to look for:**
- Is the primitive **shared**?
- Is the lock **necessary** for correctness?
- Is there a **lighter-weight** alternative (e.g., `WRITE_ONCE`)?

**How to respond:**
> “Using a lock to serialize a single write is completely bogus. It adds zero serialization that a WRITE_ONCE/READ_ONCE pair doesn't add. At best it's just wasted CPU time. At worst, it confuses people about what the locking means and results in bugs down the line. Don't do things like this.”

**Severity:** reject

---
### Scenario 6: API That Lacks Essential Functionality for a Common Use Case

**Situation:** A public API lacks a way to map a page for simple data access.

**What to look for:**
- Is the missing functionality **essential** for a common use case?
- Is there a **workaround**?
- Can the API be **extended** without breaking existing users?

**How to respond:**
> “Now, I didn't actually try to make that whole thing very transparent. In particular, somebody who just wants to see the data (and ignore as much of the 'tree' details as possible) would really want to have not that 'tree_entry', but the whole 'struct tree_level *' and in particular a way to *map* the page.”

**Severity:** nitpick

---
### Scenario 7: Change That Uses a Magic Value or Sentinel

**Situation:** A patch uses `0` as an invalid sequence number.

**What to look for:**
- Could the sentinel be **confused with valid data**?
- Is the sentinel **unmistakably invalid**?
- Can a **named constant** or helper function be used instead?

**How to respond:**
> “I'm not convinced '0' is a good value. It's not supposed to match anything, but it could match a valid sequence number. Wouldn't it be better to pick something that is explicitly invalid and has the low bit set (ie 1 or -1).”

**Severity:** nitpick

---
### Scenario 8: Change That Breaks Bisectability

**Situation:** A patch requires manual edits to compile or bisect.

**What to look for:**
- Does the patch **compile cleanly**?
- Does it **bisect cleanly**?
- Are there **trivial conflicts** that require manual resolution?

**How to respond:**
> “While I could easily just remove the duplicated lines in my merge, that would make things non-bisectable, so I unpulled this instead.”

**Severity:** reject

---

## Decision Framework

Below is a **decision tree** for reviewers. Follow it in order.

```
1. Is the patch **correct**?
   - If NO → reject
   - If YES →
2. Does the patch **break a public API contract**?
   - If YES → reject (unless **compelling** reason)
   - If NO →
3. Does the patch **expose internal details** or **leak information**?
   - If YES → reject
   - If NO →
4. Does the patch **change observable behavior** (e.g., error handling, return values, timing)?
   - If YES → reject
   - If NO →
5. Is the patch **a performance optimization**?
   - If YES → require **measurable** benefit and **no regression**
   - If NO →
6. Does the patch **increase complexity** without **clear benefit**?
   - If YES → request-changes
   - If NO →
7. Is the patch **a style change** with **no functional benefit**?
   - If YES → reject
   - If NO → approve
```

---

## Quick Reference Checklist

**Before approving, verify:**

| Category | Check |
|---|---|
| **Correctness** | ✅ No fatal assertions for recoverable errors |
|  | ✅ No corruption of existing state |
|  | ✅ No use-after-free or use-after-return |
| **API Stability** | ✅ No breaking changes without **compelling** reason |
|  | ✅ Public interfaces are minimal and unambiguous |
|  | ✅ Return conventions are consistent |
| **Security** | ✅ No exposure of internal details |
|  | ✅ No marking of uninitialized memory as executable |
|  | ✅ No information leaks to user space |
| **Performance** | ✅ No changes to observable behavior for optimization |
|  | ✅ Performance gains are **measurable and reproducible** |
| **Complexity** | ✅ No unnecessary abstractions or helpers |
|  | ✅ No legacy behavior preserved without justification |
|  | ✅ No new states or flags without justification |
| **Error Handling** | ✅ Errors are recoverable and distinguishable |
|  | ✅ Resources are cleaned up on error paths |
|  | ✅ No magic sentinel values |
| **Concurrency** | ✅ No locks for single primitives |
|  | ✅ No reliance on source-level ordering |
|  | ✅ No `volatile` for memory ordering |
| **Memory Safety** | ✅ No raw pointer dereferences without mapping |
|  | ✅ No dangling pointers |
|  | ✅ No uninitialized executable memory |
| **Testing** | ✅ Reproducible test case for bug fixes |
|  | ✅ Tested on all relevant platforms |
| **Documentation** | ✅ Commit messages explain **what** and **why** |
|  | ✅ Comments are **not stale** |
|  | ✅ No incorrect terminology |
| **Process** | ✅ Patch compiles cleanly and bisects cleanly |
|  | ✅ No broken toolchain or environment assumptions |
|  | ✅ No magic numbers or unexplained constants |