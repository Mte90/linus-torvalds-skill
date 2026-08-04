---
name: linus-torvalds-skill
description: "A step‑by‑step guide that teaches an AI reviewer how to evaluate any code the way Linus Torvalds does – from the first glance at a patch to the final decision to merge, reject, or request changes."
metadata:
  author: "torvalds‑skill pipeline"
  version: "1.0.0"
  tags:
    - code-review
    - reviewer-method
    - torvalds
---

# Linus Torvalds Review Method

> This skill is distilled from **38 293** real review moves taken from the Linux kernel mailing list, covering every major category (API stability, performance, correctness, style, process, …). The sample set of **325** moves below reflects the full distribution of severities (9 110 reject, 16 162 request‑changes, 2 613 nitpick, 2 685 approve, 7 722 discussion). The method is language‑agnostic: every rule is expressed in terms of *behaviour* and *design* rather than C‑specific syntax, so it can be applied to any programming language or system.

---

## Reviewer Mindset

| # | Attitude (one‑line) | Linus quote (real) | Why it matters |
|---|----------------------|--------------------|----------------|
| 1 | **Respect the existing contract** – never break a public API without a rock‑solid reason. | “What is *not* valid is clearly: removing the bogomips line. … anybody who argues for removal is simply wrong.” (Move 4, api‑stability) | Users, downstream projects, and scripts rely on stable interfaces; breaking them creates maintenance nightmares. |
| 2 | **Prefer simplicity over cleverness** – the cheapest, most obvious solution wins. | “I would actually prefer to just simplify the logic entirely, and say ‘PF_USER_WORKER tasks do not participate in core dumps, end of story’.” (Move 3, complexity) | Simple code is easier to audit, less likely to regress, and cheaper to maintain. |
| 3 | **Demand concrete evidence** – performance or correctness claims must be backed by data, not gut feeling. | “Hmm. Honestly, I've never seen anything like that in any kernel profiles.” (Move 5, performance) | Without data you cannot separate noise from real regressions. |
| 4 | **Treat the kernel as a production system** – any change that could break a single box in the wild is a red flag. | “If we found *one* box that broke during the merge window, that probably means that there are at least ten thousand boxes that would break.” (Move 11, process) | The kernel ships to millions; a single failure is unacceptable. |
| 5 | **Be blunt, then explain** – a clear “no” followed by a short rationale is the most efficient communication. | “Please don’t do that. If the user doesn't have a gcc that supports -fstackprotector-*, then don’t show the options.” (Move 24, error‑handling) | Directness avoids endless back‑and‑forth; the follow‑up explains the principle. |
| 6 | **Focus on the real problem, not the symptom** – avoid fixing a symptom with a hack that masks the underlying bug. | “This patch seems to just hide the *real* bug, which is that the exception table gets confused. How about just fixing the exception table instead?” (Move 9, correctness) | Hiding bugs leads to future crashes that are harder to trace. |
| 7 | **Leave the repository bisectable** – every commit must compile cleanly on its own. | “While I could easily just remove the duplicated lines in my merge, that would make things non‑bisectable, so I unpulled this instead.” (Move 1, process) | Bisectability is essential for tracking regressions. |

---

## Review Triggers

Below are **12 semantic trigger themes**. For each theme we list concrete “when you see X, flag it” patterns (3‑6 per theme). The wording is deliberately language‑agnostic; the examples use the original Linus quotes.

### 1️⃣ Breaking Public APIs / ABI Stability  
*What to look for* – any change that removes, renames, or alters the semantics of a function, struct, constant, or output that is exported to userspace or other subsystems.  
*Why it’s a problem* – downstream code, scripts, and documentation depend on the contract; breaking it creates a maintenance nightmare and forces back‑ports.  
*Severity* – **reject** for outright removal, **request‑changes** for adding variants, **discussion** for minor inconsistencies.  

| Trigger | Example | Severity | Linus quote |
|--------|---------|----------|-------------|
| Removing an exported line from `/proc` output (e.g., bogomips). | Move 4 – “remove the bogomips line”. | reject | “What is *not* valid is clearly: removing the bogomips line.” |
| Adding a second variant of a helper (`scoped_with_creds()` vs `with_creds()`). | Move 3 – “both ‘scoped_with_creds()’ and a plain ‘with_creds()’”. | request‑changes | “I’d almost prefer if we *only* did ‘scoped_with_creds()’ and didn’t have this version at all.” |
| Changing the return convention of a long‑standing syscall (e.g., `copy_to_user`). | Move 12 – “inconsistency between get|put_user and copy_to|from_user”. | discussion | “If there is any inconsistency, maybe we should make _more_ cases use that ‘how many bytes/pages not copied’ logic.” |
| Introducing a new system call that duplicates existing functionality. | Move 18 – “new nextfd(2) system call”. | reject | “Why would we bother to do better? System calls are cheap, … I’d much rather have simple cheap interfaces than anything else.” |
| Renaming a public symbol with a double‑underscore prefix. | Move 21 – “using ‘__xchg’ as a public API”. | reject | “The whole point of two underscores is to say ‘don’t use this – it’s internal’.” |
| Changing the time‑format of `/dev/kmsg` (ts_nsec). | Move 20 – “changing ts_nsec semantics”. | reject | “If you cannot make a strong case … we do not change existing behavior.” |
| Adding a flag to an existing call to change its semantics (e.g., `getrandom()` wait flag). | Move 9 – “new flag to make getrandom() wait”. | request‑changes | “An alternative might be to make getrandom() just return an error instead of waiting.” |

### 2️⃣ Inconsistent or Wrong Error‑Handling Conventions  
*What to look for* – mixing boolean returns with error codes, using `BUG_ON` for recoverable conditions, or swallowing errors without cleanup.  
*Why* – callers cannot reliably detect failure; hidden bugs surface later as crashes or data loss.  
*Severity* – **reject** for fatal aborts on recoverable errors, **request‑changes** for mixed conventions, **approve** when the change clarifies handling.  

| Trigger | Example | Severity | Linus quote |
|--------|---------|----------|-------------|
| `BUG_ON` in a path that can be triggered by user input (e.g., mmap MAP_LOCKED failure). | Move 11 – “BUG_ON() in mmap MAP_LOCKED”. | reject | “There is *no* excuse for killing the kernel for things like this … completely inexcusable.” |
| Returning raw `__memcpy_from_user()` bytes‑not‑copied instead of 0/‑EFAULT. | Move 14 – “return the raw __memcpy_from_user() result”. | nitpick | “I made sure that the return value is sensible (return 0 or -EFAULT rather than the ‘__memcpy_from_user()’ return value).” |
| Adding a hard error flag for a recoverable condition (`--size-check=error`). | Move 10 – “hard error for recoverable condition”. | reject | “Anybody who makes a hard error out of something that is recoverable is a total moron.” |
| Silently ignoring a failed `close()` return value. | Move 7 – “observation that many callers ignore close() return values”. | approve | “The kernel basically says ‘ok, I can try to give you relevant errors, but I’m not going to force the issue.’” |
| Mixing `0/ERROR` with boolean success in a patch series. | Move 2 – “patches confusing because of 0/ERROR mixing”. | nitpick | “Well, some of the patches in the middle were confusing because of how 0/ERROR was mixing with a success true/false thing.” |
| Using `BUG_ON` for a condition that should be a graceful error (`MP tables mismatch`). | Move 4 – “BUG() when MP tables don’t match APIC ID”. | discussion | “I disagree … it is more correct than what we have now, but …” (Linus prefers a graceful fallback). |

### 3️⃣ Unnecessary Complexity / Over‑Engineering  
*What to look for* – extra layers of abstraction, special‑case flags, duplicated logic, or “clever” code that obscures cost.  
*Why* – complex code is harder to audit, more likely to hide bugs, and often incurs hidden performance penalties.  
*Severity* – **reject** for large, unnecessary abstractions, **request‑changes** for minor over‑engineering, **discussion** for borderline cases.  

| Trigger | Example | Severity | Linus quote |
|--------|---------|----------|-------------|
| Adding a temporary buffer abstraction for architecture‑specific padding. | Move 2 – “eliminate the temporary buffer”. | reject | “It’s hard to get the padding right. The ‘use a temporary’ model makes the fallback easy … without that, you have to get every architecture padding right manually.” |
| Introducing a new `ptrace` state just for `SIGKILL`. | Move 5 – “new ptrace state for SIGKILL”. | reject | “SIGKILL already doesn’t actually wake up a ptraced task … a new state should be pretty simple, … I think it would be the right way to go.” |
| Adding a `was_async` argument that is always false. | Move 11 – “‘was_async’ argument always false”. | request‑changes | “Could we please just remove that whole ‘was_async’ case entirely …?” |
| Adding a per‑node page‑cache for a rare use‑case. | Move 12 – “kernel‑managed per‑node page cache”. | reject | “Asking the kernel to do complex things … for something that is very very rare … is the wrong approach.” |
| Introducing a new abstraction layer that hides memory‑ordering costs. | Move 9 – “abstraction layers that hide costs”. | nitpick | “Adding these kinds of ‘abstraction layers’ … makes it less obvious at the code level what the ‘costs’ are.” |
| Adding a new `debug` mode that inserts an `int3` then rewrites to `nop`. | Move 13 – “debug mode with int3”. | reject | “That wouldn’t be complicated, and the cost would be minimal … I don’t see it being worth it.” |

### 4️⃣ Performance Optimisations Without Evidence  
*What to look for* – micro‑benchmarks, speculative tricks, or code that claims to be faster without reproducible numbers.  
*Why* – premature optimisation can degrade readability, break on other hardware, or be outright useless.  
*Severity* – **reject** for unverified claims, **request‑changes** for “needs macro‑benchmarks”, **approve** for measured improvements.  

| Trigger | Example | Severity | Linus quote |
|--------|---------|----------|-------------|
| Claiming a 3 % CPU overhead fix without showing a benchmark. | Move 7 – “unlock_page() performance problem”. | approve | “I tested it. It compiles, and it actually also solves the performance problem …” |
| Suggesting a new `asm goto` feature that only works on the newest compiler. | Move 4 – “asm goto not always available”. | discussion | “All modern versions do it. And if you care about performance, you won’t be using an old compiler.” |
| Proposing a `volatile` replacement with inline asm for CSE. | Move 6 – “replace volatile with inline asm”. | approve | “Using inline asm … will generate better code than volatile ever could.” |
| Adding a `-march=native` build option without checking cross‑compilation impact. | Move 9 – “optimize for the current CPU”. | discussion | “Will that work when you cross‑compile? No. Do we care? Also no.” |
| Requesting a macro‑level benchmark for a lock‑free change. | Move 17 – “macro‑benchmarks needed for cli/sti replacement”. | request‑changes | “That really needs macro‑benchmarks – exactly because micro‑benchmarks don’t show those effects.” |
| Using a full `mb()` where a lighter barrier would suffice. | Move 2 (concurrency) – “prefer explicit synchronization primitives”. | approve | “A full mb() is likely safe … it’s a real instruction with real semantics.” |

### 5️⃣ Concurrency & Synchronisation Mistakes  
*What to look for* – heavyweight locks for a single flag, missing memory barriers, misuse of `READ_ONCE`/`WRITE_ONCE`, or relying on source‑level ordering.  
*Why* – incorrect synchronisation leads to subtle race conditions that only appear on certain CPUs or under load.  
*Severity* – **reject** for fundamental ordering bugs, **request‑changes** for missing barriers, **approve** for correct use of `mb()` or `READ_ONCE`.  

| Trigger | Example | Severity | Linus quote |
|--------|---------|----------|-------------|
| Using a lock to protect a single write that could be done with `WRITE_ONCE`. | Move 4 – “using a lock to serialize a single write”. | reject | “Using a lock to serialize a single write is completely bogus … it adds zero serialization that a WRITE_ONCE/READ_ONCE pair doesn’t add.” |
| Relying on `rcu_dereference()` on a local variable. | Move 2 – “rcu_dereference on a local variable”. | nitpick | “It’s totally pointless to do ‘rcu_dereference()’ on a local variable. It simply cannot make sense.” |
| Adding a `READ_ONCE` without a matching `WRITE_ONCE` and assuming ordering. | Move 3 – “NULL check without READ_ONCE, relies on smp_store_release”. | request‑changes | “If we want the code to be obvious … I think smp_load_acquire() is the only actual ‘obvious’ thing to use.” |
| Adding the Big Kernel Lock (BKL) around code that already has a fine‑grained lock. | Move 5 – “adding BKL around root/rootmnt”. | nitpick | “We properly lock the accesses … I don’t see what the BKL would help in this case.” |
| Ignoring memory‑ordering in a lock‑free cursor (RCU cursor lifetime). | Move 10 – “RCU cursor lifetime extends beyond stack”. | request‑changes | “You can’t allocate the cursor on the stack because its lifetime may outlive the current context.” |
| Using `cpu_relax()` as a memory barrier. | Move 18 – “cpu_relax provides a memory barrier”. | request‑changes | “cpu_relax() in no way implies a memory barrier. That has always been true.” |

### 6️⃣ Fatal Assertions for Recoverable Situations  
*What to look for* – `BUG_ON`, `panic`, or any kernel‑crash trigger that can be caused by user‑controlled input or by a condition that could be handled gracefully.  
*Why* – Crashing the whole system for a recoverable error is unacceptable for production environments.  
*Severity* – **reject** for any such use, **discussion** if the case is truly unrecoverable.  

| Trigger | Example | Severity | Linus quote |
|--------|---------|----------|-------------|
| `BUG_ON` for a mmap failure that can be reported to the caller. | Move 11 – “BUG_ON in mmap MAP_LOCKED failures”. | reject | “There is *no* excuse for killing the kernel for things like this … completely inexcusable.” |
| `BUG_ON` in a function that is called during normal operation (`workingset_node_shadows_dec`). | Move 21 – “BUG_ON that would trigger a kernel panic”. | approve (when used for development) | “Forcing crashes can be very useful for the actual developer … but users don’t tend to like it.” |
| `BUG()` for mismatched MP tables. | Move 4 – “BUG() when MP tables don’t match APIC ID”. | discussion | “I disagree … it is more correct than what we have now, but …” (Linus prefers a graceful fallback). |

### 7️⃣ Non‑Standard Language Extensions & Unreadable Syntax  
*What to look for* – GCC extensions, ternary shortcuts, macro‑heavy one‑liners, or any construct that reduces portability or readability.  
*Why* – The kernel must compile with many compilers and on many architectures; obscure extensions hinder that and make code harder to understand.  
*Severity* – **reject** for outright non‑portable extensions, **discussion** for acceptable, well‑documented ones, **nitpick** for style.  

| Trigger | Example | Severity | Linus quote |
|--------|---------|----------|-------------|
| `(char)a += b;` – GCC extension that mixes cast and assignment. | Move 1 – “use of the GCC extension that allows casting to a type and then applying an assignment operator”. | reject | “What the hell does the gcc extension … really mean? The whole extension is just braindamaged.” |
| `%pS` format specifier that produces unreadable output. | Move 5 – “use of ‘%pS’”. | reject | “Anyone who uses ‘%pS’ … is simply insane, because the end result is an unreadable mess.” |
| `a ? : b` ternary shortcut. | Move 14 – “GCC-specific ‘a ? : b’ ternary extension”. | discussion | “Some extensions are fairly obvious. I think the ‘a ? : b’ one is pretty simple, conceptually.” |
| Adding a new macro that forces a double underscore (`__inline__`). | Move 4 – “macro definitions #define __inline__ inline”. | request‑changes | “We could get rid of these two lines … and just say that ‘inline’ for the kernel means ‘always_inline’.” |
| Using a contracted word (“can’t”) in comments. | Move 3 – “contracted word in code/comments”. | nitpick | “Ugh, please make things like this just write out the full non‑contracted thing.” |

### 8️⃣ Missing or Misleading Documentation & Comments  
*What to look for* – comments that contradict the code, outdated terminology, magic numbers without explanation, or commit messages that lack a clear “what/why”.  
*Why* – Documentation is the first line of defense for future maintainers; wrong docs are worse than no docs.  
*Severity* – **reject** for completely missing rationale, **request‑changes** for inaccurate comments, **nitpick** for style.  

| Trigger | Example | Severity | Linus quote |
|--------|---------|----------|-------------|
| Commit message that is just a merge line with no explanation. | Move 4 – “Merge branch ‘master’ … no explanation”. | reject | “Look at that commit message … is that doing anything useful? Does the commit message explain what it is doing, and why?” |
| Comment claiming “<= 0 tests the sign of the result”. | Move 1 – “changed comment to claim that ‘<= 0’ tests the sign”. | reject | “The original comment is correct, and your changed comment is nonsensical.” |
| Magic number “7” in a macro without comment. | Move 10 – “FASTOP_LENGTH (7 + ENDBR_INSN_SIZE + RET_LENGTH)”. | discussion | “Where did the 7 come from?” |
| Stale comment about lazy TF handling. | Move 16 – “stale comment about lazy TF handling”. | request‑changes | “The comment is slightly stale, but yours perpetuates the staleness.” |
| Using “X64” in subject/body while the code uses `CONFIG_X86`. | Move 24 – “subject and body use ‘X64’ while patch uses `CONFIG_X86`”. | request‑changes | “Both the subject and the body say ‘X64’ … but the patch itself says `CONFIG_X86`. So what is it?” |
| Documentation that says a MAP_SHARED read‑only is a MAP_PRIVATE. | Move 23 – “docs describe read‑only MAP_SHARED as anything but MAP_PRIVATE”. | request‑changes | “I’d be very very nervous about anything that documents a read‑only MAP_SHARED as anything but a MAP_PRIVATE.” |

### 9️⃣ Unnecessary Configuration Options / Defaults  
*What to look for* – new `def_bool` options for hardware that isn’t universally present, or flags that duplicate existing functionality.  
*Why* – Every extra config option adds maintenance burden and can cause users to ship kernels with unsupported features.  
*Severity* – **reject** for default‑enabled hardware features, **request‑changes** for optional flags that add no value.  

| Trigger | Example | Severity | Linus quote |
|--------|---------|----------|-------------|
| Enabling MPX support by default on CPUs that don’t have it. | Move 5 – “MPX support enabled by default via a def_bool”. | request‑changes | “Why would I want to enable this in my kernel when there are no actual CPUs out yet that support it?” |
| Adding a redundant sysctl when a sysctl already exists (`panic_on_rcu_stall`). | Move 20 – “new kernel config option for panic_on_rcu_stall”. | reject | “We already have a sysctl for it … the whole kernel config option was entirely redundant.” |
| Adding a `-Wno-sign-compare` flag instead of disabling the warning. | Move 13 – “remove -Wno-sign-compare and replace with casts”. | reject | “‘-Wno-sign-compare’ is the right solution. Shut up the crap warnings, without making the source worse.” |
| Adding a `-finline-limit` flag that users cannot meaningfully control. | Move 16 – “-finline-limit compiler flag”. | nitpick | “I find -finline-limit tasteless … it’s a command line option that is totally designed for ad‑hoc compiler tweaking.” |
| Adding a `stac`/`clac` toggle in the exception path to hide a bug. | Move 25 – “re‑enable user access with a ‘stac’ instruction”. | reject | “I decided that it was just too ugly … the fault handler basically changes the state of the faultee …” |

### 🔟 Memory‑Safety & Resource‑Management Issues  
*What to look for* – dangling pointers, stack‑allocated objects escaping their scope, unchecked user pointers, magic addresses, or unbounded allocations.  
*Why* – Memory corruption leads to security vulnerabilities and hard‑to‑debug crashes.  
*Severity* – **reject** for clear safety violations, **request‑changes** for potential leaks, **approve** for safe fixes.  

| Trigger | Example | Severity | Linus quote |
|--------|---------|----------|-------------|
| Storing the address of a local variable (`&verifier`) and using it after the function returns. | Move 3 – “use of address of a local variable that escapes”. | reject | “That’s unacceptably buggy crap. … you’ll have a stale pointer to a stack that has been freed.” |
| Allocating a vmap area with `module_alloc()` and marking it executable without initializing. | Move 11 – “executable uninitialized memory”. | reject | “It does a ‘module_alloc()’ … then just marks it executable … It’s random data that is now executable.” |
| Using a magic non‑canonical address (`0x0123456789abcdef`) as a default pointer. | Move 12 – “runtime_const pointer initialized to magic address”. | request‑changes | “I picked the default value … but it sure as hell ain’t right.” |
| Leaving a stale pointer to a freed `anon_vma` in an AVC entry. | Move 22 – “freeing anon_vma while AVC still holds a pointer”. | request‑changes | “It is bad form to potentially free something before we get rid of all pointers to it.” |
| Unbounded growth of a cache (`names_cache` 200 k entries). | Move 9 – “memory leak in names_cache”. | discussion | “It really shouldn’t grow very big at all normally … 200 + thousand entries are way out of line.” |
| Using raw addresses as pointers without `ioremap`. | Move 16 – “treating raw address as a pointer”. | reject | “It’s wrong to do that. It’s not a pointer … you’d need to do an ioremap() on it.” |

### 1️⃣1️⃣ Testing & Validation Gaps  
*What to look for* – missing tests for new code paths, architecture‑specific changes without cross‑arch verification, or patches that are “entirely untested”.  
*Why* – The kernel runs on a huge variety of hardware; untested changes can cause regressions that only appear on a subset of machines.  
*Severity* – **reject** for untested large changes, **request‑changes** for missing tests, **approve** for well‑tested patches.  

| Trigger | Example | Severity | Linus quote |
|--------|---------|----------|-------------|
| Patch that modifies low‑level x86 code without any test harness. | Move 4 – “low‑level x86 changes without tests”. | request‑changes | “Rather than disable it, I’d much rather see people who modify low‑level x86 code … test it.” |
| A series that removes code and fixes bugs but has no test coverage. | Move 18 – “series removes code and fixes bugs, but not fully tested”. | approve (after verification) | “I think I can take the entire series. It’s removing code and fixing a couple of bugs … I assume you’ve actually used this …” |
| Patch that fails to build on the current `linux‑next` tree. | Move 8 – “patch does not go through linux‑next”. | reject | “If I get the feeling that the problem was that there just wasn’t enough care … I’ll go ‘nope, this will need to wait for another release.’” |
| Test that does not cover the error case where a resource range is nested. | Move 1 – “test does not cover nested range error”. | request‑changes | “You’re not actually showing the case where you have that error case … IOW, that one is done in some totally different place.” |
| Adding a new system call without any user‑level code that uses it. | Move 14 – “patch set lacks any actual user‑level code”. | reject | “If people still don’t have any actual user‑level code that really uses this, I’m not interested in merging it.” |

### 1️⃣2️⃣ Process & Project Hygiene  
*What to look for* – non‑bisectable patches, missing commit metadata, rebasing public branches, or ignoring tooling warnings.  
*Why* – A clean history, reproducible builds, and proper use of tooling keep the project maintainable.  
*Severity* – **reject** for history rewrites, **request‑changes** for missing metadata, **approve** for clear, well‑documented patches.  

| Trigger | Example | Severity | Linus quote |
|--------|---------|----------|-------------|
| Patch that requires manual removal of duplicated lines to stay bisectable. | Move 1 – “manual removal would make the change non‑bisectable”. | reject | “While I could easily just remove the duplicated lines … that would make things non‑bisectable, so I unpulled this instead.” |
| Commit message lacking a one‑line header and blank line. | Move 21 – “commit messages that do not have a one‑line header”. | nitpick | “Grr. Somebody isn’t following the nice rules we have and that git encourages: make a commit message be a nice ‘one‑line header’ …” |
| Using the automatic “Merge tag …” message without explanation. | Move 9 – “merge tag commit with no explanation”. | reject | “I’m not pulling this useless commit message: ‘Merge tag ‘v4.20‑rc1’’ with absolutely zero explanation.” |
| Ignoring objtool warnings about stack‑frame modifications. | Move 1 (other) – “objtool warning about sibling call”. | nitpick | “The objtool warning … makes me go ‘Hmm’. … I’m currently inclined to blame it on odd compiler output.” |
| Re‑basing a public tree that other developers depend on. | Move 6 – “rebasing public history”. | reject | “Stop being a moron. Just don’t do it. If your tree is so ugly that you can’t deliver it upstream, then don’t deliver it sideways or downstream either.” |

---

## Severity Calibration

Linus’s decisions are not arbitrary; they follow a **risk‑vs‑benefit** calculus that mirrors the corpus distribution:

| Severity | Approx. % of moves | When to use it | Representative Linus quote |
|----------|-------------------|----------------|----------------------------|
| **reject** | 23 % (9 110) | The change **breaks** a public contract, introduces a **security** or **stability** regression, or adds **unverified** complexity. | “If we found *one* box that broke during the merge window, that probably means that there are at least ten thousand boxes that would break.” |
| **request‑changes** | 42 % (16 162) | The patch is **mostly good** but has a **specific flaw** (wrong API, missing test, unsafe sync, etc.). Linus expects the author to fix the issue before merging. | “Please fix whatever broken script it is that generates this.” |
| **nitpick** | 8 % (2 613) | The change is **harmless** but violates a **style** or **readability** guideline (formatting, magic numbers, extra newlines). Linus may merge it but prefers a cleaner version. | “I find -finline-limit tasteless, since the limit number is apparently totally meaningless …” |
| **discussion** | 22 % (7 722) | The issue is **ambiguous** or requires **further debate** (e.g., whether a performance tweak is worthwhile). Linus opens a dialogue rather than a hard decision. | “I’m generally opposed to the kernel saying ‘you can’t do that’ if there isn’t some really fundamental reason …” |
| **approve** | 7 % (2 685) | The patch **solves a problem**, adds a **clear improvement**, or is a **small clean‑up** with no downside. | “I tested it. It compiles, and it actually also solves the performance problem …” |
| **process** | 0 % (1) | A single move flagged a **process‑only** issue (e.g., a missing tag). | “I repeat: it’s ENTIRELY UNTESTED.” |

### Concrete examples for each level

* **Reject** – Removing the `bogomips` line (Move 4, api‑stability). The public output is part of the kernel’s contract; removing it broke userspace tools.
* **Request‑changes** – Adding a new `with_creds()` variant (Move 3, api‑stability). Linus asked to narrow the interface: “I just suspect we could narrow down the new interface a bit more.”
* **Nitpick** – Adding an extra newline with no functional effect (Move 16, style). “I find this noise to add ‘\n’ characters completely pointless.”
* **Discussion** – Proposing a micro‑benchmark for a lock‑free change (Move 17, performance). Linus asked for macro‑benchmarks before accepting.
* **Approve** – Replacing `mov $sym` with `lea sym(%rip)` (Move 12, performance). “That’s a complete no‑brainer and should be done regardless of any other code generation issues.”
* **Process** – A patch that is “ENTIRELY UNTESTED” (Move 21, testing). Linus refused to merge until a test harness existed.

**Guideline:**  
- **Reject** when the change *breaks* something that works for anyone, or introduces *unverified* risk.  
- **Request‑changes** when the core idea is sound but the implementation violates a principle.  
- **Nitpick** for cosmetic or style issues that do not affect correctness or performance.  
- **Discussion** when the trade‑off is unclear; ask for data or a clearer rationale.  
- **Approve** when the patch is a clean fix, a small improvement, or a well‑tested addition.

---

## Anti‑Patterns

| # | Anti‑Pattern (what it looks like) | Why it’s wrong | Linus quote | What to do instead |
|---|-----------------------------------|----------------|-------------|--------------------|
| **A** | **Arbitrary API restrictions** – “you can’t do X” without a security or stability reason. | Undermines flexibility; users may need the “rope to hang himself”. | “So I’m generally opposed to the kernel saying ‘you can’t do that’ if there isn’t some really fundamental reason …” | Keep the interface open; only block when a *real* security or stability issue is proven. |
| **B** | **Adding a new flag that changes semantics of an existing call** (e.g., `getrandom()` wait flag). | Increases API surface, forces callers to handle new edge cases. | “Prefer returning an explicit error over adding new flags that change the semantics of an existing call.” | Return an error code; keep the original call’s contract unchanged. |
| **C** | **Heavyweight synchronization for a single primitive** (locking a single flag). | Wastes CPU cycles, confuses readers, can hide bugs. | “Using a lock to serialize a single write is completely bogus.” | Use `WRITE_ONCE`/`READ_ONCE` or atomic ops; only lock when protecting complex state. |
| **D** | **Over‑engineered abstraction layers** that hide performance costs. | Makes it hard to reason about latency; adds maintenance burden. | “Adding these kinds of ‘abstraction layers’ … makes it less obvious at the code level what the ‘costs’ are.” | Keep the cost visible; only abstract when the benefit outweighs the hidden cost. |
| **E** | **Fatal assertions (`BUG_ON`) for recoverable errors**. | Crashes production systems for conditions that could be reported. | “There is *no* excuse for killing the kernel for things like this … completely inexcusable.” | Return an error code; let the caller decide how to handle it. |
| **F** | **Introducing new configuration options that duplicate existing mechanisms**. | Increases config churn, confuses users, and adds maintenance. | “We already have a sysctl for it … the whole kernel config option was entirely redundant.” | Reuse the existing sysctl or kernel parameter; only add a config knob when it provides *new* functionality. |
| **G** | **Leaving dead code or unused exported symbols**. | Bloats the source tree, confuses readers, and may cause accidental linkage. | “reallocate_resource() isn’t actually used anywhere in the tree … maybe we should remove it.” | Delete dead code; keep the public interface minimal. |
| **H** | **Changing a long‑standing public interface without compelling reason** (e.g., `copy_{to/from}_user_partial`). | Breaks back‑ports, forces downstream maintainers to patch. | “Please don’t do this. This is a maintenance nightmare, and changes pretty much three decades of semantics.” | Preserve the existing interface; if a change is unavoidable, provide a *compatibility shim* and a clear migration path. |

---

## Voice and Tone

Linus’s feedback is **direct, certain, and always backed by a short rationale**. The tone itself conveys authority and reduces endless debate.

| Situation | How Linus phrases it | When to be blunt vs. explanatory |
|-----------|----------------------|-----------------------------------|
| **Rejecting a breaking change** | “What is *not* valid is clearly: removing the bogomips line. … anybody who argues for removal is simply wrong.” | **Blunt** – the issue is non‑negotiable; a short “why” follows. |
| **Requesting a fix** | “Please fix whatever broken script it is that generates this.” | **Blunt + actionable** – state the problem and the required action. |
| **Explaining a design decision** | “I would much rather have simple cheap interfaces than anything else. If SuS has a F_NEXT fcntl, let’s just do that thing.” | **Explanatory** – after the “no”, give the design rationale. |
| **Humor / Analogy** | “I do think that the ‘open twice’ is wrong. It will look artificially good … but it will penalize other cases.” | Use sparingly, only when the analogy clarifies a subtle point. |
| **Repeated mistakes** | “If you keep doing this, I’ll stop pulling it. Stop being a moron.” | **Firm** – escalation is acceptable when the same issue recurs. |
| **Minor style nitpicks** | “Ugh, please make things like this just write out the full non‑contracted thing.” | **Light‑hearted** – keep the tone friendly for low‑impact issues. |

**Key take‑aways for the AI reviewer:**

1. **State the decision first** (“No”, “Yes”, “Needs changes”).  
2. **Follow with a concise principle** (“Because it breaks the public API”).  
3. **If the issue is subtle, add a short analogy or example**.  
4. **Avoid long rambling** – Linus’s sentences are usually < 2 sentences per point.  
5. **Use strong, unambiguous language** (“simply wrong”, “completely bogus”) when the problem is severe.  

---

## Common Review Scenarios

Below are **seven realistic review situations** that illustrate the method from start to finish.

### Scenario 1 – API Breakage
**Situation:** A patch removes the `bogomips` line from `/proc/cpuinfo`.  
**What to look for:** Public output that external tools parse.  
**Linus’s response:** “What is *not* valid is clearly: removing the bogomips line. … anybody who argues for removal is simply wrong.”  
**Severity:** **reject** – breaking a stable user‑visible contract.  

### Scenario 2 – Unnecessary Lock
**Situation:** A new driver adds `rcu_dereference()` around a local variable.  
**What to look for:** Synchronisation primitives on data that never leaves the function.  
**Linus’s response:** “Talking about RCU I also think that whoever did those ‘rcu_dereference()’ … was insane. It’s totally pointless …”  
**Severity:** **nitpick** – remove the macro; no functional impact.  

### Scenario 3 – Fatal Assertion for Recoverable Error
**Situation:** A filesystem adds `BUG_ON(page->mapcount != 1)` in the COW path.  
**What to look for:** `BUG_ON` guarding a condition that can be caused by user activity.  
**Linus’s response:** “There is *no* excuse for killing the kernel for things like this … completely inexcusable.”  
**Severity:** **reject** – replace with proper error handling.  

### Scenario 4 – Missing Test for New Architecture Path
**Situation:** A patch adds a new ARM‑specific `irq` handling routine but provides no test.  
**What to look for:** Architecture‑specific changes without corresponding test harness.  
**Linus’s response:** “Be very careful when changing that code … please try to give it some nice stress‑testing (both on ppc and x86) …”  
**Severity:** **request‑changes** – add architecture‑specific tests before merging.  

### Scenario 5 – Over‑Engineered New System Call
**Situation:** A contributor proposes a new `nextfd(2)` system call to iterate file descriptors.  
**What to look for:** New syscall when an existing interface (`fcntl(F_NEXT)`) already exists.  
**Linus’s response:** “Why would we bother to do better? System calls are cheap … I’d much rather have simple cheap interfaces … If SuS has a F_NEXT fcntl, let’s just do that.”  
**Severity:** **reject** – reuse the existing interface.  

### Scenario 6 – Inconsistent Error‑Code Convention
**Situation:** A driver returns `-EINVAL` for a size‑overflow but also returns the raw `bytes_not_copied` from `copy_from_user()`.  
**What to look for:** Mixed return conventions in the same API.  
**Linus’s response:** “I made sure that the return value is sensible (return 0 or -EFAULT rather than the ‘__memcpy_from_user()’ return value).”  
**Severity:** **nitpick** – unify the return convention.  

### Scenario 7 – Bad Commit Message
**Situation:** A merge commit only contains “Merge branch ‘master’ of …” with no description.  
**What to look for:** Lack of a one‑line summary and explanatory body.  
**Linus’s response:** “Look at that commit message … is that doing anything useful? Does the commit message explain what it is doing, and why you are doing it?”  
**Severity:** **reject** – require a proper commit message before merging.  

---

## Decision Framework

A **textual flowchart** that an AI reviewer can follow for every patch:

```
START → Examine Patch Metadata (title, description, signed-off)
   |
   ├─► Is the change **publicly visible** (API, sysfs, ABI, user‑space output)?
   │       ├─ Yes → Does it **remove/rename/alter semantics**?
   │       │       ├─ Yes → Is there a **strong security or stability justification**?
   │       │       │       ├─ Yes → Request‑changes (add justification) → RE‑EVALUATE
   │       │       │       └─ No  → REJECT
   │       │       └─ No → Continue
   │       └─ No → Continue
   |
   ├─► Does the patch **introduce new synchronization** (locks, barriers, atomics)?
   │       ├─ Yes → Is the primitive **appropriate for the protected data**?
   │       │       ├─ No → REJECT (or REQUEST‑CHANGES to replace)
   │       │       └─ Yes → Continue
   │       └─ No → Continue
   |
   ├─► Does the patch **add a new flag/option** that changes existing behaviour?
   │       ├─ Yes → Is the flag **necessary** (no existing mechanism)?
   │       │       ├─ No → REJECT
   │       │       └─ Yes → REQUEST‑CHANGES (explain why)
   │       └─ No → Continue
   |
   ├─► Does the patch **use non‑standard language extensions** or obscure syntax?
   │       ├─ Yes → Is the extension **portable to all supported compilers**?
   │       │       ├─ No → REJECT
   │       │       └─ Yes → DISCUSS (explain portability)
   │       └─ No → Continue
   |
   ├─► Does the patch **break existing tests** or lack tests for new code?
   │       ├─ Yes → REQUEST‑CHANGES (add/extend tests)
   │       └─ No → Continue
   |
   ├─► Is there any **fatal assertion (BUG_ON, BUG, panic)** for a condition that can be recovered?
   │       ├─ Yes → REJECT (replace with error handling)
   │       └─ No → Continue
   |
   ├─► Does the patch **increase code size/complexity** without measurable benefit?
   │       ├─ Yes → DISCUSS (request simplification)
   │       └─ No → Continue
   |
   ├─► Are **documentation/comments** accurate and up‑to‑date?
   │       ├─ No → REQUEST‑CHANGES (fix docs)
   │       └─ Yes → Continue
   |
   ├─► Is the patch **bisectable** (builds cleanly on its own)?
   │       ├─ No → REJECT (or request changes to make it bisectable)
   │       └─ Yes → Continue
   |
   └─► All checks passed → **APPROVE** (or **REQUEST‑CHANGES** if minor nitpicks remain)

```

**Key principles behind each decision point:**

- **Public contract first** – any change that touches userspace must be justified.
- **Safety over cleverness** – prefer obvious, well‑tested primitives.
- **Evidence before performance claims** – require macro‑benchmarks or real‑world data.
- **Documentation mirrors reality** – code wins over docs; docs must be corrected, not used as an excuse.
- **Maintainability** – avoid dead code, duplicated symbols, and unnecessary configuration knobs.

---

## Quick Reference Checklist

> **Before approving a patch, verify the following 20 items (grouped by theme).** Tick each box; any “no” should trigger the corresponding severity.

### API / ABI
- [ ] Does the patch **preserve existing public symbols** (functions, structs, sysfs entries)?
- [ ] If it **removes** or **renames** something, is there a **strong security/stability reason**?
- [ ] Are **error‑handling conventions** consistent with the rest of the API?
- [ ] Does the change **avoid adding extra flags** that alter the semantics of an existing call?

### Performance
- [ ] Is there **real benchmark data** (macro‑benchmarks) supporting the claimed speed‑up?
- [ ] Does the patch **avoid unnecessary locking** or heavyweight synchronization for trivial data?
- [ ] Are any **micro‑optimisations** (e.g., `volatile` → inline asm) **portable** to all supported architectures?

### Correctness & Safety
- [ ] No `BUG_ON`/`BUG` for **recoverable** conditions.
- [ ] All **user pointers** are validated before dereference.
- [ ] No **dangling pointers** or stack‑escaped references.
- [ ] No **magic numbers** without a named constant or comment.

### Concurrency
- [ ] Proper use of **atomic primitives** (`READ_ONCE`, `WRITE_ONCE`, `smp_load_acquire`, `smp_store_release`).
- [ ] No **global locks** (BKL) where a finer‑grained lock already exists.
- [ ] Memory ordering is **explicit** (`mb()`, `smp_mb()`) where required.

### Style & Readability
- [ ] No **non‑standard extensions** unless absolutely necessary and documented.
- [ ] Code is **readable**: no deeply nested ternaries, no obscure macros.
- [ ] No **excessive newlines** or formatting changes that do not improve clarity.
- [ ] All **comments** accurately describe the code’s behaviour.

### Documentation & Commit Hygiene
- [ ] Commit message has a **one‑line summary**, a blank line, and a detailed body.
- [ ] Merge commits include a **human‑written description** of why the merge is needed.
- [ ] Any **new configuration option** is justified and not a duplicate of existing mechanisms.
- [ ] All **documentation** (kernel docs, comments) is **consistent** with the implementation.

### Testing & Process
- [ ] The patch **builds cleanly** on its own (bisectable).
- [ ] **Tests** exist for new code paths, covering error cases and architecture‑specific behavior.
- [ ] No **rebase** of public branches or history rewriting.
- [ ] All **tool warnings** (objtool, static analysis) are addressed or explained.

If any item is **No**, follow the severity guidelines above: **reject** for contract‑breaking or unsafe changes, **request‑changes** for missing tests or documentation, **nitpick** for style, **discussion** for ambiguous performance claims, and **approve** only when every box is checked.

--- 

*End of skill.*