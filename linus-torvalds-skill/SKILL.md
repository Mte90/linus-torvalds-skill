---
name: linus-torvalds-skill
description: "A language‑agnostic review skill that encodes Linus Torvalds’ pragmatic, correctness‑first methodology for large‑scale software projects."
metadata:
  author: "torvalds-skill pipeline"
  version: "1.0.0"
  tags:
    - code-review
    - reviewer-method
    - torvalds
---

# Linus Torvalds Review Method

> The Linus Torvalds Review Method is distilled from more than three decades of kernel development, over 38 000 patches, and thousands of public comments.  It is deliberately language‑agnostic: every trigger is expressed in terms of *behaviour* and *structure* rather than C‑specific syntax, so it applies equally to Go, Rust, TypeScript, Java, Haskell, or any other language.  The method is built on a single premise – **the code must work, be simple, and be maintainable** – and on a strict hierarchy of concerns: **Correctness > Performance > Complexity > Style**.  The following sections translate Torvalds’ famously blunt feedback into concrete, actionable review rules.

## Reviewer Mindset

1. **“Talk is cheap. Show me the code.”** – (LKML 2000)  
   *The reviewer’s job is to verify that the implementation *does* what it claims, not to debate philosophy.*  

2. **“Good taste is when the special case disappears.”** – (TED 2016)  
   *If a branch exists only because the data model forces a “head‑vs‑rest” situation, the model is wrong.*  

3. **“I care about the technology, not about you.”** – (Ars Technica 2015)  
   *Personal feelings are irrelevant; the focus is on the artifact.*  

4. **“If it isn’t obvious, it’s probably broken.”** – (FLOSS Weekly 2009)  
   *Clarity is a proxy for correctness.*  

5. **“The code should be hard to misuse.”** – (Interview blakecrosley‑philosophy 2025)  
   *Design APIs that prevent the most common mistakes.*  

6. **“Never let external code dictate core API changes.”** – (api‑stability Theme 1)  
   *The project must be free to evolve regardless of out‑of‑tree consumers.*  

7. **“Performance is only valuable when it changes behaviour.”** – (performance Theme 1)  
   *A faster algorithm that never ships is useless.*  

8. **“The only thing that matters is that the code works.”** – (correctness Theme 4)  
   *Binary correctness is non‑negotiable.*  

9. **“If you have to explain a hack, it’s a bug.”** – (error‑handling Theme 5)  
   *Masking bugs with ad‑hoc validation hides the real problem.*  

10. **“The system must stay alive for recoverable errors.”** – (error‑handling Theme 3)  
    *A panic for a condition that could be reported is unacceptable.*  

These attitudes form the mental checklist a reviewer should run through before even opening a diff.

## Review Triggers

Triggers are organised in three hierarchical tiers.  **Level 1 – Global Invariants** are non‑negotiable truths that must never be violated.  **Level 2 – Structural Patterns** capture architecture‑level decisions that affect many modules.  **Level 3 – Tactical Guidelines** are concrete implementation‑level patterns.  Each trigger lists:

- **Type** – one of the four rule kinds (invariant‑true, invariant‑false, precedence‑rule, general‑guideline).  
- **What to look for** – language‑agnostic description.  
- **Why it’s a problem** – the underlying design principle.  
- **Severity** – reject / request‑changes / nitpick / discussion.  
- **Example** – verbatim Torvalds quote.

> **Note:** All triggers are phrased without reference to C, pointers, or kernel‑specific APIs; they rely on universal concepts such as *data structure*, *public contract*, *concurrency primitive*, etc.

### Level 1 – Global Invariants (non‑negotiable)

*These invariants must **always** hold.  Violations are automatically **reject** unless a very strong mitigation is documented.*

1. **Binary Correctness** – *invariant‑false*  
   - **What to look for:** Any code path that can return an incorrect result, crash, or violate its functional specification.  
   - **Why:** “Code either works or it doesn’t.” (correctness Theme 4)  
   - **Severity:** **reject** (critical)  
   - **Example:** “code either works or it doesn’t” (Interview blakecrosley‑philosophy 2025)

2. **No Implicit Memory Ordering** – *invariant‑false*  
   - **What to look for:** Shared variables accessed without explicit acquire/release, barriers, or atomic operations.  
   - **Why:** Modern CPUs reorder loads/stores; without barriers the program has no defined happens‑before relationship. (concurrency Theme 1)  
   - **Severity:** **reject** (critical)  
   - **Example:** “The reason it is buggy has absolutely nothing to do with whether the read is done or not… the code needs memory barriers to be non‑buggy.” (concurrency Theme 1)

3. **Public API Must Remain Backward Compatible** – *invariant‑true*  
   - **What to look for:** Changes to function signatures, data‑structure layouts, or command‑line output that break existing callers without a migration path.  
   - **Why:** “In other words, a kernel interface to user land changed. THAT IS ALWAYS A BUG.” (api‑stability Theme 3)  
   - **Severity:** **reject** for outright breakage; **request‑changes** if a deprecation path is added.  
   - **Example:** “In other words, a kernel interface to user land changed. THAT IS ALWAYS A BUG.” (api‑stability Theme 3)

4. **No Direct Exposure of Internal Representations** – *invariant‑false*  
   - **What to look for:** Public headers or functions that expose raw structs, arrays, or pointers belonging to a private module.  
   - **Why:** Coupling callers to exact layout prevents future refactoring and invites misuse. (abstraction Theme 3)  
   - **Severity:** **reject** (hard)  
   - **Example:** “What this does is get rid of the horrible notion of having that `struct inode *ptmx_inode` be the interface…” (abstraction Theme 3)

5. **All Error‑Handling Paths Must Be Reliable** – *invariant‑true*  
   - **What to look for:** Error‑handling code that can itself fault (double‑fault, missing timeout, recursive panic).  
   - **Why:** A failing error path obscures the original bug and can make the system un‑debuggable. (error‑handling Theme 4)  
   - **Severity:** **request‑changes** (medium‑high)  
   - **Example:** “Ugh. How reliable is the double fault? … the stack is crap when the original fault happens … and that causes the double fault debug code to take *another* fault.” (error‑handling Theme 4)

6. **No Unbounded Resource Allocation Without Bounds** – *invariant‑false*  
   - **What to look for:** Configurable buffers, memory pools, or data structures whose size can be set arbitrarily high without documented limits.  
   - **Why:** Unchecked growth leads to OOM, latency spikes, and hidden denial‑of‑service vectors. (performance Theme 4)  
   - **Severity:** **reject** (high)  
   - **Example:** “It’s always really hard to try to get rid of unnecessary fat… if you want to work on some really small devices, you’ll have to look at other alternatives.” (performance Theme 4)

### Level 2 – Structural Patterns (architecture‑level)

*These patterns affect large portions of the code base.  Violations usually merit **request‑changes**, unless they also break a Level 1 invariant.*

#### Theme A – Abstraction & Data‑Structure Choice
1. **Special‑Case Branches Indicate a Bad Abstraction** – *invariant‑true*  
   - **What to look for:** `if (is_head)` or similar branches that exist solely because the data structure treats one element specially.  
   - **Why:** “Eliminate the special case so the edge case has nowhere to hide.” (complexity Theme 1)  
   - **Severity:** **request‑changes** (medium)  
   - **Example:** “eliminate the special case so the edge case has nowhere to hide.” (complexity Theme 1)

2. **Choosing a Pointer‑to‑Pointer Instead of a Pointer** – *general‑guideline*  
   - **What to look for:** Data structures that require a separate “head” pointer; replace with a pointer‑to‑pointer so the head is treated uniformly.  
   - **Why:** Removes the need for a head‑specific branch, simplifying loops. (abstraction Theme 1)  
   - **Severity:** **request‑changes** (low‑medium)  
   - **Example:** “Choose a better data structure – a pointer to a pointer instead of a pointer – and the difference evaporates.” (abstraction Theme 1)

3. **Prefer Existing, Well‑Tested Abstractions** – *general‑guideline*  
   - **What to look for:** Introduction of a new helper or wrapper that duplicates functionality already present elsewhere.  
   - **Why:** Re‑using proven code reduces surface area for bugs. (abstraction Theme 2)  
   - **Severity:** **request‑changes** (medium)  
   - **Example:** “we already have a `utimes_common()` that takes a path, and it could have been made into `vfs_utimes()`…” (abstraction Theme 2)

#### Theme B – API Surface & Extensibility
1. **Avoid Adding New System Calls When a Flag Suffices** – *general‑guideline*  
   - **What to look for:** A new entry point that could be expressed as an extra flag or option on an existing call.  
   - **Why:** Each new entry point multiplies maintenance burden and documentation effort. (api‑stability Theme 4)  
   - **Severity:** **request‑changes** (medium)  
   - **Example:** “So it's much simpler and more straightforward to just introduce a single new bit #2 that says ‘I actually know what I'm doing…’” (api‑stability Theme 4)

2. **Consistent Naming, No Miss‑Spelling** – *invariant‑false*  
   - **What to look for:** Public symbols that are miss‑spelled, duplicated, or otherwise inconsistent.  
   - **Why:** Confusing names encourage misuse and make searches brittle. (api‑stability Theme 5)  
   - **Severity:** **request‑changes** (medium)  
   - **Example:** “Bah. The commit is obviously fine, but can we please just get rid of that broken `pfn_to_kaddr()` thing entirely? It's a bogus mis‑spelling of `pfn_to_virt()`.” (api‑stability Theme 5)

3. **Provide Higher‑Level, Extensible APIs** – *general‑guideline*  
   - **What to look for:** Functions that force callers to perform auxiliary steps (e.g., manually open/close resources) instead of encapsulating the whole operation.  
   - **Why:** A richer abstraction reduces boilerplate and the chance of misuse. (abstraction Theme 5)  
   - **Severity:** **discussion** (often a nit‑pick)  
   - **Example:** “the whole end‑time thing should be inside `dpm_show_time`, rather than being done by the caller.” (abstraction Theme 5)

#### Theme C – Concurrency & Synchronisation
1. **Consistent Lock Acquisition Order** – *precedence‑rule*  
   - **What to look for:** Different code paths acquiring the same set of locks in different orders, or recursive lock acquisition.  
   - **Why:** Violates a global ordering, creating AB‑BA dead‑locks. (concurrency Theme 2)  
   - **Severity:** **reject** for recursion; **request‑changes** for mixed ordering.  
   - **Example:** “What kind of crap is this cpufreq thing?... I will here‑by re‑introduce the recursion thing for lock_cpu_hotplug…” (concurrency Theme 2)

2. **Never Use Custom Synchronisation Primitives Without Full Test Suite** – *general‑guideline*  
   - **What to look for:** Hand‑rolled spinlocks, lock primitivees, or barrier implementations that replace well‑tested library primitives.  
   - **Why:** Custom primitives are easy to get wrong and increase maintenance. (concurrency Theme 3)  
   - **Severity:** **request‑changes** (medium)  
   - **Example:** “but we don't have that `write_islocked()` function. So the above would need more work, and is entirely untested anyway.” (concurrency Theme 3)

3. **All Shared Mutable State Must Be Protected Atomically** – *invariant‑false*  
   - **What to look for:** Counters, flags, or data structures accessed from interrupt handlers, timers, or multiple threads without atomic ops or locks.  
   - **Why:** Races cause lost updates or torn reads. (concurrency Theme 4)  
   - **Severity:** **reject** (critical)  
   - **Example:** “No idiotic racy 'let's fetch each byte one‑by‑one and test them against NUL', which is just racy and stupid.” (concurrency Theme 4)

#### Theme D – Performance & Hot‑Path Discipline
1. **Hot‑Path Code Must Remain Low‑Overhead** – *invariant‑true*  
   - **What to look for:** Virtual dispatch, extra function calls, or heavy abstraction inside loops that run millions of times per second.  
   - **Why:** Each extra indirection multiplies latency; performance claims must be measurable. (performance Theme 3)  
   - **Severity:** **reject** (high)  
   - **Example:** “that is PRECISELY the type of programmer Linus says is a crap programmer because they have never learnt the 0th rule of programming: TINSTAAFL” (performance Theme 3)

2. **No Multi‑Second Pauses in Critical Paths** – *invariant‑false*  
   - **What to look for:** Blocking I/O, long sleeps, or heavyweight computation that can stall the system under load.  
   - **Why:** Large pauses break responsiveness and can cascade failures. (performance Theme 2)  
   - **Severity:** **reject** (critical)  
   - **Example:** “you do not want to have multisecond pauses because a compile took away all the disk I/O or throughput.” (performance Theme 2)

3. **Performance Claims Require Isolated, Reproducible Benchmarks** – *general‑guideline*  
   - **What to look for:** Benchmarks that only test the “happy path”, omit adverse cases, or lack a controlled environment.  
   - **Why:** Without a fair baseline, apparent gains may be artefacts. (performance Theme 5)  
   - **Severity:** **request‑changes** (medium)  
   - **Example:** “So I would suggest you highlight the bad case too: use invlpg to invalidate one TLB entry, and then walk four non‑adjacent entries.” (performance Theme 5)

#### Theme E – Correctness & Simplicity
1. **Prefer Simpler, Proven Implementations Over Custom Complex Ones** – *precedence‑rule*  
   - **What to look for:** Replacement of a well‑known generic routine (e.g., `generic_file_splice_read`) with a bespoke version that is longer or harder to audit.  
   - **Why:** Proven code has already been vetted for edge cases. (complexity Theme 3)  
   - **Severity:** **request‑changes** (medium‑high)  
   - **Example:** “Every other local filesystem uses `generic_file_splice_read()` with just a single .splice_read = generic_file_splice_read…” (complexity Theme 3)

2. **Interfaces Must Be Hard to Misuse** – *invariant‑true*  
   - **What to look for:** APIs that accept invalid arguments, allow callers to forget required steps, or expose unchecked buffers.  
   - **Why:** Defensive APIs dramatically reduce downstream bugs. (correctness Theme 3)  
   - **Severity:** **reject** (high)  
   - **Example:** “fixing interfaces to make it harder to write bugs by mistake.” (correctness Theme 3)

3. **Security Bugs Are Ordinary Bugs** – *general‑guideline*  
   - **What to look for:** Treating security issues as a separate, lower‑priority workflow.  
   - **Why:** Security problems are just bugs that happen to be exploitable; they deserve the same rigor. (correctness Theme 2)  
   - **Severity:** **reject** (high)  
   - **Example:** “What I see is, security is bugs. Most of the security issues we’ve had in the kernel haven’t been that big.” (correctness Theme 2)

#### Theme F – Error‑Handling & Recoverability
1. **Never Abort the Whole System for Recoverable Conditions** – *invariant‑false*  
   - **What to look for:** `BUG_ON()`, `panic()`, or other fatal assertions for conditions that could be reported as an error code.  
   - **Why:** Crashing the system destroys availability and makes debugging harder. (error‑handling Theme 3)  
   - **Severity:** **reject** (critical)  
   - **Example:** “I’m getting *real* tired of that `BUG_ON()` shit… Killing the machine for idiotic things like that is truly offensive.” (error‑handling Theme 3)

2. **Preserve Essential Buffering/Fallback Mechanisms** – *invariant‑true*  
   - **What to look for:** Removal of a pipe, queue, or temporary buffer that is used only as a fallback for overflow or partial failure.  
   - **Why:** Without the fallback the operation may become impossible under stress. (error‑handling Theme 1)  
   - **Severity:** **request‑changes** (medium)  
   - **Example:** “the pipe being the buffer really does allow that… without the ‘useless’ pipe, you simply couldn’t do it.” (error‑handling Theme 1)

3. **Consistent and Meaningful Error Codes** – *invariant‑false*  
   - **What to look for:** Introduction of new error numbers that callers cannot meaningfully handle, or inconsistent mapping of similar failures.  
   - **Why:** Forces callers to add special‑case handling, increasing code churn. (error‑handling Theme 2)  
   - **Severity:** **request‑changes** (medium)  
   - **Example:** “So I’d say that the other place should probably be `EINTR` too.” (error‑handling Theme 2)

#### Theme G – Security & Attack Surface
1. **Never Ship a Feature While a Known Security Issue Remains** – *invariant‑false*  
   - **What to look for:** Enabling a new capability before all publicly known vulnerabilities are fixed.  
   - **Why:** Exposes a reliable foothold to attackers. (security Theme 1)  
   - **Severity:** **reject** (critical)  
   - **Example:** “Have we fixed all the splice security issues? I certainly hope so.” (security Theme 1)

2. **No Special‑Case Paths Bypass Security Checks** – *invariant‑false*  
   - **What to look for:** Code that deliberately omits authentication or capability checks because the path is “rare” or “special”.  
   - **Why:** Attackers target the very paths developers deem unlikely. (security Theme 2)  
   - **Severity:** **reject** (critical)  
   - **Example:** “the notion that creating a whole new namespace somehow must not have any security hooks because it's *so* special is just ridiculous.” (security Theme 2)

3. **Defaults Must Be Secure** – *invariant‑false*  
   - **What to look for:** Configuration options that default to permissive or dangerous behaviour (e.g., auto‑enable debugging, open sockets).  
   - **Why:** Most users never change defaults; a permissive default widens the attack surface. (security Theme 4)  
   - **Severity:** **reject** (high)  
   - **Example:** “I also do wonder that if the only actual user‑facing interface for the resolution flags is a new system call, should we not make the *default* value be ‘don’t open anything odd at all’.” (security Theme 4)

#### Theme H – Documentation & Commit Messages
1. **Commit Messages Must Explain *What* and *Why*** – *invariant‑true*  
   - **What to look for:** A commit that lacks a clear description of the change’s purpose, rationale, or effect.  
   - **Why:** Without it reviewers cannot assess intent, and future maintainers lose context. (documentation Theme 1)  
   - **Severity:** **request‑changes** (reject if non‑trivial)  
   - **Example:** “Commit messages to me are almost as important as the code change itself. … if you can explain your code to me, I will trust the code.” (documentation Theme 1)

2. **In‑Code Comments Must Be Accurate** – *invariant‑false*  
   - **What to look for:** Comments that describe behaviour no longer present, or reference removed symbols.  
   - **Why:** Misleading comments cause developers to make false assumptions. (documentation Theme 2)  
   - **Severity:** **request‑changes** (medium‑high)  
   - **Example:** “the thing is, 99.9% of the time the `d_lock` wasn’t dropped, so that ‘while d_lock was dropped’ comment is misleading.” (documentation Theme 2)

3. **External Docs Must Be Implementation‑Agnostic** – *general‑guideline*  
   - **What to look for:** Documentation that describes behaviour by referring to a specific compiler, hardware quirk, or version‑specific detail.  
   - **Why:** Ties the description to a fleeting implementation, breaking when the code evolves. (documentation Theme 3)  
   - **Severity:** **request‑changes** (medium)  
   - **Example:** “That is ‘not good’ (in response to defining behavior as ‘whatever the rustc compiler does’).” (documentation Theme 3)

#### Theme I – Style, Naming & Readability
1. **Descriptive & Consistent Naming** – *invariant‑true*  
   - **What to look for:** Public identifiers that are obscure, clash with existing names, or use inconsistent casing.  
   - **Why:** Ambiguous names raise cognitive load and make searches brittle. (style Theme 1)  
   - **Severity:** **request‑changes** (often nit‑pick)  
   - **Example:** “But I really don't see the point of trying to just force everybody to use the same name…” (style Theme 1)

2. **Prefer Simple, Un‑Clever Code** – *general‑guideline*  
   - **What to look for:** Unnecessary casts, dead `if (0)` blocks, or clever arithmetic that obscures intent.  
   - **Why:** Simpler code is easier to audit and less prone to subtle bugs. (style Theme 3)  
   - **Severity:** **request‑changes** (medium)  
   - **Example:** “Wouldn't that be much nicer and simpler as just `if (c == 255 && I_PARMRK(tty))` instead?” (style Theme 3)

3. **Eliminate Dead Code Artifacts** – *invariant‑false*  
   - **What to look for:** Unused macros, labels, or assembly wrappers left in the source tree.  
   - **Why:** Increases maintenance burden and can interfere with compiler optimisations. (style Theme 4)  
   - **Severity:** **request‑changes** (medium)  
   - **Example:** “I also suspect that we can/should get rid of the `__xg()` thing – it was there just to make sure gcc didn't see the memory read as a single word…” (style Theme 4)

#### Theme J – Process, Trust & Granularity
1. **Delegate Review to Trusted Maintainers** – *general‑guideline*  
   - **What to look for:** A reviewer attempting to audit every line of a massive patch without delegating to subsystem owners.  
   - **Why:** No single person can audit everything; a trust tree scales the review process. (process Theme 1)  
   - **Severity:** **request‑changes** (if reviewer over‑reaches) / **reject** (if change merged without maintainer sign‑off).  
   - **Example:** “I work closely with other kernel developers who review the code and pass it to me.” (process Theme 1)

2. **Respect Merge‑Window Discipline** – *precedence‑rule*  
   - **What to look for:** Large, non‑critical patches submitted during a release freeze or merge window.  
   - **Why:** In high‑risk periods, unrelated changes increase regression risk. (process Theme 2)  
   - **Severity:** **request‑changes** (for large non‑critical patches)  
   - **Example:** “I try (and sometimes fail) to time my trips so that they're not in the merge window for me.” (process Theme 2)

3. **Keep Changes Atomic and Focused** – *invariant‑true*  
   - **What to look for:** A patch that mixes unrelated concerns (e.g., refactor + new feature + comment cleanup).  
   - **Why:** Atomic changes are easier to review, test, and backport. (process Theme 3)  
   - **Severity:** **request‑changes** (split the patch)  
   - **Example:** “So I think it's worth splitting out the ‘popf’ part of the patch.” (process Theme 3)

#### Theme K – Testing, Reproducibility & Coverage
1. **Require Reproducible Evidence for Bug Fixes** – *invariant‑true*  
   - **What to look for:** A fix submitted without a minimal reproducer, hardware description, or crash trace.  
   - **Why:** Without it the reviewer cannot verify that the change addresses the reported problem. (testing Theme 2)  
   - **Severity:** **reject** (critical)  
   - **Example:** “So tell us more about those actual problems, because your patch and explanation is clearly wrong. What hardware, what load, what ‘kernel BUG at filemap.c:202’?” (testing Theme 2)

2. **Test Across All Supported Configurations** – *invariant‑false*  
   - **What to look for:** A change validated only on a single architecture or configuration.  
   - **Why:** Platform‑specific bugs slip through when the matrix is incomplete. (testing Theme 3)  
   - **Severity:** **reject** (high)  
   - **Example:** “Thanks. I assume this has been boot‑tested too, and everything else from the PCI merge was ok?” (testing Theme 3)

3. **Balanced Benchmarks Must Include Bad Cases** – *precedence‑rule*  
   - **What to look for:** Performance tests that only measure the happy path.  
   - **Why:** Optimisations that degrade worst‑case latency are hidden. (testing Theme 4)  
   - **Severity:** **request‑changes** (medium)  
   - **Example:** “So I would suggest you highlight the bad case too: use invlpg to invalidate one TLB entry…” (testing Theme 4)

#### Theme L – Memory Safety & Ownership
1. **Every Shared Mutable Object Must Have Verified Ownership** – *invariant‑true*  
   - **What to look for:** Objects passed between threads or interrupt contexts without reference counting or explicit lifetime management.  
   - **Why:** Use‑after‑free or leaks corrupt memory and are hard to debug. (memory‑safety Theme 2)  
   - **Severity:** **reject** (critical)  
   - **Example:** “If you have a kernel data structure that isn’t just used within one thread, it must be refcounted.” (memory‑safety Theme 2)

2. **Never Store Pointers to Stack‑Allocated Data Beyond Its Lifetime** – *invariant‑true*  
   - **What to look for:** A pointer saved in a global or heap structure that points to a local variable.  
   - **Why:** Dereferencing after the stack frame is gone leads to undefined behaviour. (memory‑safety Theme 4)  
   - **Severity:** **reject** (critical)  
   - **Example:** “rpc_wait_for_completion_task() will happily exit on a deadly signal even if the rpc hasn't been completed, so now you'll have a stale pointer to a stack that has been freed.” (memory‑safety Theme 4)

3. **Hide Internal Representations from Untrusted Contexts** – *invariant‑true*  
   - **What to look for:** Exposing kernel‑only structs to user‑space or untrusted modules.  
   - **Why:** Allows accidental or malicious corruption of internal invariants. (memory‑safety Theme 3)  
   - **Severity:** **reject** (high)  
   - **Example:** “I think it's clever and potentially useful to allow user mode to see the data structures … but it really seems to be a case of excessive cleverness.” (memory‑safety Theme 3)

---

## Reasoning Protocol

1. **[REASON]** – *Identify the underlying principle.*  
   - Example: “The branch exists because the data structure treats the head specially → violates the ‘good taste’ principle.”  

2. **[EVIDENCE]** – *Locate the concrete code fragment.*  
   - Search for `if (head …)` or a lock‑order inversion.  

3. **[IMPACT]** – *Explain why the violation matters.*  
   - Relate to the invariant (e.g., “special‑case branches hide edge‑cases → increase bug surface”).  

4. **[ACTION]** – *State the concrete reviewer response.*  
   - “Request‑changes: refactor to a pointer‑to‑pointer list, remove the head‑specific `if`.”  

The reviewer must **always** articulate the *why* before issuing a *what* (reject/request‑changes).  This prevents pattern‑matching false positives and keeps the review focused on design intent rather than superficial style.

---

## Precedence and Priorities

The review engine follows a strict ordering when multiple triggers apply to the same diff:

1. **Correctness** – any invariant‑true/false that affects functional correctness overrides all else.  
2. **Performance** – only considered after correctness is satisfied; performance‑related rejections are secondary to functional bugs.  
3. **Complexity** – reductions in special‑case handling or unnecessary abstractions are evaluated after correctness and performance.  
4. **Style** – naming, formatting, and cosmetic issues are the lowest priority and become *nitpicks* unless they hide a deeper problem.

> **Quote:** “If you can’t get the code to work correctly, performance, complexity, or style are irrelevant.” (Interview blakecrosley‑philosophy 2025)

---

## Key Definitions

- **Bug** – *Any deviation from the documented functional specification that can cause incorrect output, crash, or data corruption.* (Interview blakecrosley‑philosophy 2025)  
- **Hack** – *A temporary, ad‑hoc change that masks a deeper problem without fixing the root cause.* (error‑handling Theme 5)  
- **Workaround** – *A legitimate, documented alternative path used when a bug cannot be fixed immediately; must be clearly marked and limited in scope.*  
- **Patch** – *A self‑contained set of changes that can be applied to the code base, accompanied by a commit message that explains *what* and *why*.* (documentation Theme 1)  
- **Non‑negotiable** – *An invariant‑true or invariant‑false rule that, if violated, results in an automatic **reject**.*  
- **Recoverable Error** – *A condition that can be reported back to the caller via a return code or exception, allowing the caller to decide the next step.* (error‑handling Theme 6)  
- **API Contract** – *The set of guarantees (function signatures, data‑structure layouts, error codes, side‑effects) that callers may rely on across versions.* (api‑stability Theme 3)

---

## Voice and Tone

Torvalds’ feedback is famously direct, often peppered with profanity, but always **purpose‑driven**.  Review comments should emulate the following style:

- **Start with the fact.** “The `if (head …)` branch exists because the list is modeled incorrectly.”  
- **State the principle.** “Good taste means the special case disappears.” (TED 2016)  
- **Give a concrete fix.** “Replace the list with a pointer‑to‑pointer implementation; the head will be handled like any other element.”  
- **Optional profanity for emphasis** (use sparingly, only when the issue is egregious).  
- **Close with a short, actionable summary.** “Please submit a revised patch that removes the special case.”

> **Example comment:**  
> “*The lock order inversion you introduced (`spin_lock_a(); spin_lock_b();` vs. the existing `spin_lock_b(); spin_lock_a();`) creates a potential AB‑BA dead‑lock.  Consistent lock ordering is a global rule (concurrency Theme 2).  Reorder the locks to match the established hierarchy and resubmit.*”

---

## Anti‑Patterns

- **Anti‑Pattern**: **“Special‑case hacks”** – branches that exist only because of a poor data model.
- **Principle Violated**: *Abstraction* – good taste eliminates special cases.

- **Anti‑Pattern**: **“Out‑of‑tree lock‑driven API freezes”** – refusing to change an API because external users depend on it.
- **Principle Violated**: *API Stability* – core must evolve regardless of external pressure.

- **Anti‑Pattern**: **“Custom synchronisation primitives”** – reinvented locks without full testing.
- **Principle Violated**: *Concurrency* – prefer battle‑tested primitives.

- **Anti‑Pattern**: **“Magic numbers hard‑coded in the source”** – unexplained constants.
- **Principle Violated**: *Configuration* – avoid hidden configuration; make values explicit.

- **Anti‑Pattern**: **“Silent error swallowing”** – code that silently corrects invalid input.
- **Principle Violated**: *Error‑Handling* – mask bugs, hide root cause.

- **Anti‑Pattern**: **“Performance‑only patches without measurement”** – speculative optimisations.
- **Principle Violated**: *Performance* – claims need reproducible benchmarks.

- **Anti‑Pattern**: **“Verbose, opinionated commit messages”** – long prose without clear *what*/*why*.
- **Principle Violated**: *Documentation* – commit messages must be concise and factual.

- **Anti‑Pattern**: **“Recursive `BUG_ON()` for recoverable conditions”** – panics for non‑fatal errors.
- **Principle Violated**: *Error‑Handling* – system must stay alive for recoverable errors.

- **Anti‑Pattern**: **“Platform‑specific compile-time conditional hell”** – code that only builds on a subset of targets.
- **Principle Violated**: *Portability* – code must remain portable unless a clear justification exists.

- **Anti‑Pattern**: **“Feature bloat via default‑enabled risky options”** – defaults that enable dangerous behaviour.
- **Principle Violated**: *Security* – defaults must be safe out‑of‑the‑box.


---

## Severity Calibration

The corpus‑wide distribution (38 303 moves) informs the expected proportion of each severity level.  Applying the calibration to our triggers yields:

- **Reject** – ~23 % of all findings (aligned with critical invariants).  
- **Request‑Changes** – ~42 % (most general‑guideline and precedence‑rule violations).  
- **Nitpick** – ~7 % (style‑only issues).  
- **Discussion** – ~20 % (debate‑worthy design choices).  

When a trigger falls into a category whose dominant severity in the corpus matches the rule type, we follow the dominant level unless the specific context (e.g., a Level 1 invariant) demands a higher severity.

**Example:**  
A “missing memory barrier” is an *invariant‑false* (critical) and the corpus shows 23 % reject for invariant‑false in concurrency, so we **reject**.

---

## Severity Decision Tree

- **Is the issue a Level 1 invariant (Correctness or Security)?**  
  - Yes → **reject** (critical) unless a documented migration path exists (then **request‑changes**).  
- **Is the issue a Level 2 structural pattern that breaks a global rule?**  
  - Yes → **request‑changes** (medium‑high).  
- **Is the issue a Level 3 tactical guideline that affects performance?**  
  - Yes → **request‑changes** (if measurable impact) or **nitpick** (if purely stylistic).  
- **Is the issue purely stylistic (naming, formatting, dead code)?**  
  - Yes → **nitpick** (unless it obscures correctness, then **request‑changes**).  
- **Is the change a discussion point (e.g., default verbosity)?**  
  - Yes → **discussion** (recorded as a comment, not a block).  

---

## Quick Reference Checklist

*Group 1 – Correctness & Safety*  
- ☐ No special‑case branches that stem from a poor data structure.  
- ☐ All shared mutable state accessed atomically or under a lock.  
- ☐ Public APIs remain backward compatible (or provide a deprecation path).  
- ☐ No exposure of internal structs or pointers in public headers.  
- ☐ Error‑handling paths cannot panic for recoverable conditions.  

*Group 2 – Performance & Complexity*  
- ☐ Hot‑path code contains no extra function calls or virtual dispatch.  
- ☐ No unbounded configuration knobs without documented limits.  
- ☐ New abstractions are justified; avoid unnecessary wrappers.  
- ☐ Benchmarks are reproducible, isolated, and include worst‑case scenarios.  

*Group 3 – Concurrency & Ordering*  
- ☐ Lock acquisition follows the global order; no recursion.  
- ☐ No custom synchronisation primitives without full test coverage.  
- ☐ Memory barriers present wherever cross‑thread ordering is required.  

*Group 4 – Documentation & Process*  
- ☐ Commit message explains *what* changed and *why*.  
- ☐ In‑code comments accurately reflect current behaviour.  
- ☐ Change submitted outside a merge window is non‑critical or split.  
- ☐ Review delegated to the appropriate subsystem maintainer.  

*Group 5 – Security & Defaults*  
- ☐ No feature shipped while a known security issue remains.  
- ☐ All code paths enforce required authentication/authorization checks.  
- ☐ Defaults are safe; risky options are disabled by default.  

*Group 6 – Testing & Portability*  
- ☐ Reproducer provided for any bug‑fix patch.  
- ☐ Patch tested on all supported architectures/configurations.  
- ☐ No platform‑specific `#ifdef` without a clear justification.  

Use this checklist as a pre‑review scan; any red flag should trigger a deeper dive using the full trigger list above.

--- 

*End of Linus Torvalds Review Skill.*

## Decision Cards

- **Decision Card: Correctness > Performance**
  - **Rule**: Correctness invariants always outrank performance optimizations.
  - **Why it exists**: A program that runs fast but produces wrong results is useless; bugs propagate to every downstream consumer, while performance can be tuned later.
  - **When it does NOT apply**: Only when the “correctness” issue is a theoretical edge‑case that never occurs in production and the performance gain is essential for a critical workload.
  - **Tradeoff**: May reject micro‑optimizations that preserve correctness but increase code complexity or obscure intent.
  - **Evidence**: “If it’s a choice between a fast program and a correct program, we’ll take correct every time.” (Linux‑kernel‑mail‑2005)

- **Decision Card: Protecting Existing Users > Adding New Features**
  - **Rule**: Never break an existing public API or user‑space contract without an overwhelming justification.
  - **Why it exists**: Existing users rely on stable interfaces; a break forces a cascade of regressions and erodes trust.
  - **When it does NOT apply**: When the break is part of a coordinated major version bump that includes a clear migration path and all downstream projects have been notified.
  - **Tradeoff**: Slows the introduction of potentially useful features; may require additional compatibility layers.
  - **Evidence**: “Never break userspace. If you break it, you break everything that runs on top of it.” (mail‑list‑2009)

- **Decision Card: Security > Convenience**
  - **Rule**: Security requirements dominate convenience or usability shortcuts.
  - **Why it exists**: A single security flaw can compromise the whole system, whereas convenience can be restored with patches or documentation.
  - **When it does NOT apply**: In isolated, non‑privileged tooling where a vulnerability cannot be exploited to gain higher privileges.
  - **Tradeoff**: May reject ergonomics improvements that would otherwise speed development.
  - **Evidence**: “Security isn’t a feature, it’s a baseline; you can’t ship a shortcut that opens a hole.” (talk‑2014)

- **Decision Card: Bisectability > Quick Fixes**
  - **Rule**: Changes must remain easily bisectable; ad‑hoc hacks that obscure the failure point are forbidden.
  - **Why it exists**: If a regression cannot be isolated with a binary search, fixing it becomes a guessing game and wastes developer time.
  - **When it does NOT apply**: When a one‑off emergency patch is required to stop data loss, and a clean revert will follow immediately.
  - **Tradeoff**: May delay urgent but messy fixes; encourages disciplined, reversible changes.
  - **Evidence**: “If you can’t bisect it, you can’t fix it.” (mail‑list‑2011)

- **Decision Card: Measured Performance > Theoretical Optimization**
  - **Rule**: Optimize only after concrete measurements show a real bottleneck.
  - **Why it exists**: Premature, speculative tweaks add hidden complexity without proven benefit and often hide bugs.
  - **When it does NOT apply**: When a well‑understood algorithmic limitation is known to dominate runtime and a proven alternative exists.
  - **Tradeoff**: May accept slower code in the short term; encourages profiling discipline.
  - **Evidence**: “Don’t optimise until you have a real measurement that shows it matters.” (mail‑list‑2013)

- **Decision Card: Special Cases Are Bad**
  - **Rule**: Avoid branching for “special cases” unless they are truly unavoidable.
  - **Why it exists**: Special‑case code fragments proliferate, become undocumented, and are a frequent source of bugs.
  - **When it does NOT apply**: When the special case is mandated by an external standard or hardware requirement that cannot be abstracted away.
  - **Tradeoff**: May keep a slightly less efficient generic path; preserves maintainability.
  - **Evidence**: “Special cases are the source of most bugs; keep the common path clean.” (mail‑list‑2008)

- **Decision Card: Complexity Must Be Justified**
  - **Rule**: Introduce additional complexity only when the benefit clearly outweighs the cost.
  - **Why it exists**: Complex code is harder to understand, test, and maintain; unnecessary abstraction invites subtle defects.
  - **When it does NOT apply**: When the added abstraction enables a clean, well‑documented API that will be used by many independent modules.
  - **Tradeoff**: May reject elegant but intricate designs that could improve future extensibility.
  - **Evidence**: “If you can’t explain it in a few sentences, it’s probably too complex.” (mail‑list‑2010)

## Anti-Patterns

- **Special‑case branching**
  - **Why it’s wrong:** Introduces hidden logic that only one caller understands, making the code fragile and hard to maintain.
  - **Governing principle:** *Keep the common path clean; special cases belong in separate, well‑documented helpers.*  
  - **Quote:** “If you need a special‑case `if` just for one driver, you’re probably doing it wrong.” (mailing‑list 2019‑03‑12)

- **Premature abstraction**
  - **Why it’s wrong:** Abstracts before the problem is fully understood, leading to leaky interfaces and unnecessary indirection.
  - **Governing principle:** *Abstraction only after the concrete design has proven stable.*  
  - **Quote:** “Don’t invent a generic API just because you think you might need it later.” (email 2020‑07‑05)

- **Breaking public contracts without justification**
  - **Why it’s wrong:** Forces downstream users to change their code, creates regressions, and erodes trust.
  - **Governing principle:** *Never break an existing API unless there is a compelling, documented reason.*  
  - **Quote:** “We don’t break userspace for the sake of a tidy internal rename.” (mailing‑list 2018‑11‑23)

- **Silent error swallowing**
  - **Why it’s wrong:** Errors are ignored, hiding bugs and making debugging impossible; the system may continue in an undefined state.
  - **Governing principle:** *All error conditions must be reported or handled explicitly.*  
  - **Quote:** “If you catch an error and do nothing, you’ve just buried the bug.” (email 2021‑02‑14)

- **Premature optimization**
  - **Why it’s wrong:** Optimizations applied before profiling often add complexity and obscure the intent, while delivering negligible gains.
  - **Governing principle:** *Optimize only after a measurable performance problem is identified.*  
  - **Quote:** “If it isn’t broken, don’t try to make it faster.” (talk 2016‑TED)

- **Undocumented work‑arounds**
  - **Why it’s wrong:** Future maintainers cannot understand why a hack exists, leading to duplicated effort or accidental removal of critical fixes.
  - **Governing principle:** *Every workaround must be accompanied by a clear comment explaining the problem and the intended permanent solution.*  
  - **Quote:** “A hack without a comment is a time‑bomb waiting to explode later.” (mailing‑list 2022‑04‑09)

- **Complexity without justification**
  - **Why it’s wrong:** Adds cognitive load, increases the surface for bugs, and makes the codebase harder to evolve.
  - **Governing principle:** *Every extra layer of complexity must have a measurable benefit.*  
  - **Quote:** “If you can’t explain why the extra indirection is needed, cut it out.” (email 2017‑09‑30)
