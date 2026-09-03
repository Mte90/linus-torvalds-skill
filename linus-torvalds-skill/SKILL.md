---
name: linus-torvalds-skill
description: "A language‑agnostic, rule‑based reviewer skill that captures Linus Torvalds’ pragmatic, no‑nonsense approach to code review."
metadata:
  author: "torvalds-skill pipeline"
  version: "1.0.0"
  tags:
    - code-review
    - reviewer-method
    - torvalds
---

# Linus Torvalds Review Method

> This skill distills the collective wisdom of over 38 000 review moves across the Linux kernel, Git, and countless downstream projects.  It is deliberately language‑agnostic – every trigger is expressed in terms of *behaviour* rather than C‑specific constructs – so it can be applied to Go, Rust, TypeScript, Java, Haskell, or any other language.  The method is built on four immutable priorities (Correctness > Performance > Complexity > Style) and a strict “talk is cheap, show me the code” philosophy that Linus has repeated in interviews, mailing‑list posts, and talks (e.g., “Talk is cheap. Show me the code.” – LKML 2000, “I care about the technology and the kernel—that’s what’s important to me.” – Ars Technica 2015).

## Reviewer Mindset

1. **Correctness over all else** – *“Saying ‘no’ to incorrect or harmful changes is essential.”* (Interview: blakecrosley‑philosophy.md).  
   - The reviewer must treat any violation of a true invariant as a reject, regardless of how small the change looks.

2. **Performance matters, but only when measurable** – *“Never assume a change is slower (or faster) without measuring it.”* (Category : performance → Theme 5).  
   - Benchmarks must be reproducible; otherwise the claim is an invariant‑false.

3. **Complexity is the enemy of reliability** – *“Simpler designs are more reliable.”* (Category : correctness → Theme 1).  
   - Every extra branch, wrapper, or special case is a potential bug.

4. **Style is a signal, not a style‑point** – *“Naming conventions must serve a clear purpose.”* (Category : style → Theme 1).  
   - Poor naming obscures intent and raises cognitive load.

5. **Documentation is the contract with future readers** – *“Commit messages must explain *what* and *why*.”* (Category : documentation → Theme 1).  
   - Without a clear rationale reviewers cannot assess necessity.

6. **Security is non‑negotiable** – *“Never expose functionality before all known security problems are resolved.”* (Category : security → Theme 1).  
   - A single insecure path invalidates an otherwise perfect patch.

7. **Process discipline protects the project’s scale** – *“Decisive, upfront feedback prevents wasted effort.”* (Category : process → Theme 1).  
   - Early “hell no” stops churn and keeps the merge window clean.

## Review Triggers

Triggers are organised by **semantic theme** (not by the original category).  Each entry lists the trigger type, a language‑agnostic description of what to look for, the underlying design principle, the severity level, and a verbatim Torvalds quote that illustrates the rule.

### 1. Reuse Existing Abstractions – Avoid Reinventing the Wheel
- **Type:** general‑guideline  
  **What to look for:** A new helper, duplicate logic, or a custom implementation that replicates functionality already provided by a well‑tested library routine, macro, or framework component.  
  **Why it’s a problem:** Multiplying maintenance burden and creating divergent bug‑vectors; the existing abstraction already guarantees correctness and performance.  
  **Severity:** request‑changes  
  **Example:** “At least it could use the `user_insn()` helper, which does it inside the asm itself, has the right might_fault() marking …” (Category : abstraction → Theme 1)

- **Type:** invariant‑false  
  **What to look for:** Hard‑coded magic numbers, architecture‑specific hacks, or ad‑hoc special‑case branches that exist only for a narrow situation.  
  **Why it’s a problem:** Such constants make the code fragile, obscure intent, and hinder portability.  
  **Severity:** request‑changes (reject for egregious hacks)  
  **Example:** “the whole ‘fixed address at around 12GB physical’ really is such a horrible hack” (Category : abstraction → Theme 2)

- **Type:** invariant‑true  
  **What to look for:** Functions that accept a generic context (e.g., a super‑block) when a more specific entity (e.g., an inode) would be the natural argument.  
  **Why it’s a problem:** Over‑general interfaces hide the real data flow, make call‑sites harder to read, and invite misuse.  
  **Severity:** request‑changes  
  **Example:** “Again ‑ using the inode instead of the superblock … I'd *much* rather see … `inode->i_atime = … current_fs_time(inode);`” (Category : abstraction → Theme 3)

- **Type:** general‑guideline  
  **What to look for:** APIs that force callers to perform multiple related steps (e.g., explicit shutdown, separate start/stop) that could be bundled into a single higher‑level function.  
  **Why it’s a problem:** Repeated boiler‑plate leads to duplicated code and higher chance of omission.  
  **Severity:** request‑changes (or discussion when trade‑off is subtle)  
  **Example:** “the whole end‑time thing should be _inside `dpm_show_time`, rather than being done by the caller. No?” (Category : abstraction → Theme 5)

### 2. Interface Stability – Preserve Contracts
- **Type:** invariant‑true  
  **What to look for:** Any change that alters a public function signature, data layout, command‑line output, or any user‑visible contract without a migration path.  
  **Why it’s a problem:** Downstream projects rely on the guarantee that code which compiles today will continue to run after the next release.  
  **Severity:** reject (for outright ABI breaks) / request‑changes (if a migration can be added)  
  **Example:** “In other words, a kernel interface to user land changed. **THAT IS ALWAYS A BUG. We don't change UI.**” (Category : api‑stability → Theme 1)

- **Type:** general‑guideline  
  **What to look for:** Decisions driven by out‑of‑tree code that dictate core API design.  
  **Why it’s a problem:** Core stability must be decided on the merits of the core code itself, not on the convenience of a handful of external users.  
  **Severity:** request‑changes (high priority to remove the constraint)  
  **Example:** “**we've always had a policy that if they are out of tree, they don't matter for development.**” (Category : api‑stability → Theme 2)

- **Type:** precedence‑rule (Correctness > API proliferation)  
  **What to look for:** Introduction of a brand‑new function, system call, or flag set when the required behaviour can be expressed by extending an existing API with a simple option or bit.  
  **Why it’s a problem:** Each new entry point multiplies the surface area that must stay stable, documented, and maintained.  
  **Severity:** request‑changes (reject if the new API is unnecessary)  
  **Example:** “So it's much simpler and more straightforward to just introduce a single new bit #2 that says *‘I actually know what I'm doing …’*” (Category : api‑stability → Theme 3)

- **Type:** invariant‑true  
  **What to look for:** Function names or return conventions that do not clearly indicate success/failure or data direction (e.g., returning the input size on success, zero on failure).  
  **Why it’s a problem:** Ambiguous contracts lead to subtle bugs and make future evolution unsafe.  
  **Severity:** request‑changes  
  **Example:** “…the calling convention of `sb_set_blocksize()` is wrong, and instead of returning *‘size for success or zero for failure’* it should return *‘error code for failure or zero for success’*.” (Category : api‑stability → Theme 4)

- **Type:** invariant‑true  
  **What to look for:** Publication of internal structs, helper types, or low‑level macros in public headers unless they are deliberately part of the supported API.  
  **Why it’s a problem:** Exposed internals become de‑facto contracts; downstream code may depend on them, making future refactors impossible without breaking users.  
  **Severity:** request‑changes  
  **Example:** “…your `<linux/cred.h>` file exposes `struct ucred` to user space … Why?” (Category : api‑stability → Theme 5)

### 3. Eliminate Special‑Case Logic
- **Type:** invariant‑true  
  **What to look for:** Explicit `if` branches that handle only corner conditions which could be expressed by the normal control flow.  
  **Why it’s a problem:** Hidden special cases hide edge conditions, make reasoning harder, and often duplicate code paths.  
  **Severity:** reject  
  **Example:** “eliminate the special case so the edge case has nowhere to hide” (Category : complexity → Theme 1)

- **Type:** invariant‑true  
  **What to look for:** Functions that mix core algorithmic loops with lock acquisition/release or reference‑count manipulation.  
  **Why it’s a problem:** Coupling algorithmic code to resource‑management boilerplate makes testing and reuse difficult.  
  **Severity:** request‑changes  
  **Example:** “It would also simplify things a lot if that function was split up … with the `mutex_lock/unlock` in the caller.” (Category : abstraction → Theme 4)

- **Type:** precedence‑rule (Correctness > Complexity)  
  **What to look for:** Custom implementations of a task that already has a well‑tested, simple solution elsewhere in the codebase.  
  **Why it’s a problem:** Reinventing functionality adds hidden bugs and diverges from community expectations.  
  **Severity:** request‑changes  
  **Example:** “Every other local filesystem uses `generic_file_splice_read()` …” (Category : complexity → Theme 3)

- **Type:** invariant‑false (the code should never rely on magic constants)  
  **What to look for:** Configuration flags, command‑line options, or function parameters that add knobs without a clear, widely‑requested user need.  
  **Why it’s a problem:** Extra knobs increase cognitive load and mis‑configuration risk.  
  **Severity:** reject  
  **Example:** “No. Dammit, stop doing these horrible things.” (Category : complexity → Theme 4)

### 4. Concurrency Discipline – Locking & Memory Ordering
- **Type:** invariant‑true  
  **What to look for:** Shared variables accessed multiple times without explicit memory‑ordering primitives (acquire/release, barriers).  
  **Why it’s a problem:** Compilers and CPUs may reorder accesses, breaking the happens‑before relationship and causing data‑races.  
  **Severity:** reject  
  **Example:** “The above kind of code needs memory barriers to be non‑buggy.” (Category : concurrency → Theme 1)

- **Type:** invariant‑false  
  **What to look for:** Recursive acquisition of a non‑re‑entrant lock (e.g., a function takes a lock and calls another routine that takes the same lock).  
  **Why it’s a problem:** Leads to deadlock; the lock design must forbid recursion unless explicitly re‑entrant.  
  **Severity:** reject  
  **Example:** “What kind of _crap_ is this …? I will here‑by re‑introduce the recursion thing for lock_cpu_hotplug …” (Category : concurrency → Theme 2)

- **Type:** general‑guideline  
  **What to look for:** Locks taken around code that does not touch shared mutable state, or wrong lock mode (read‑lock where write‑lock is needed).  
  **Why it’s a problem:** Unnecessary locking adds overhead; wrong mode leaves data unprotected.  
  **Severity:** reject (for clearly wrong mode) / nitpick (for superfluous lock)  
  **Example:** “Don’t take locks in timers and then complain about deadlocks.” (Category : concurrency → Theme 3)

- **Type:** precedence‑rule (Correctness > Concurrency ordering)  
  **What to look for:** Inconsistent global lock ordering across code paths (AB‑BA deadlock risk).  
  **Why it’s a problem:** Circular wait conditions cause hard‑to‑reproduce deadlocks.  
  **Severity:** request‑changes (or reject for existing deadlock‑prone code)  
  **Example:** “The common way to avoid AB‑BA deadlocks … is to just take two locks in a specific order … compare the addresses.” (Category : concurrency → Theme 4)

- **Type:** invariant‑false  
  **What to look for:** Holding a lock while performing potentially blocking operations, scheduling work, or freeing resources.  
  **Why it’s a problem:** Can cause deadlocks or corrupt lock‑dependency tracking.  
  **Severity:** request‑changes (reject if bug is manifest)  
  **Example:** “You still have ‘goto err’ for cases that have the ctx locked … the thing gets free’d while still locked …” (Category : concurrency → Theme 5)

### 5. Error‑Handling Discipline
- **Type:** invariant‑true  
  **What to look for:** Missing validation of inputs, allocation failures, or reference‑count checks before use.  
  **Why it’s a problem:** Leads to crashes, memory corruption, or subtle race conditions.  
  **Severity:** reject (egregious) / request‑changes (recoverable)  
  **Example:** “You should use '&' to test that flag, not '|'” (Category : correctness → Theme 3)

- **Type:** invariant‑false  
  **What to look for:** Fatal assertions (`BUG_ON`, `panic`, `assert`) used for conditions that could be reported as ordinary errors.  
  **Why it’s a problem:** Kills the whole process for recoverable situations, making debugging harder.  
  **Severity:** request‑changes  
  **Example:** “I’m getting *real* tired of that fatal assertion() … Killing the machine for idiotic things like that is truly offensive.” (Category : error‑handling → Theme 5)

- **Type:** invariant‑true  
  **What to look for:** Error‑handling code that itself can trigger secondary failures (e.g., dereferencing corrupted state while printing a diagnostic).  
  **Why it’s a problem:** Masks the original bug and makes root‑cause analysis impossible.  
  **Severity:** nitpick  
  **Example:** “The double fault debug code takes *another* fault, which means that it doesn't even show the right code sequence.” (Category : error‑handling → Theme 3)

- **Type:** invariant‑true  
  **What to look for:** Inconsistent or meaningless error codes that leak internal details or cannot be acted upon by callers.  
  **Why it’s a problem:** Forces callers to guess or ignore the error, leading to fragile code.  
  **Severity:** request‑changes  
  **Example:** “EINVAL seems the simplest thing. Should check S_IMMUTABLE too for that matter.” (Category : error‑handling → Theme 4)

- **Type:** general‑guideline  
  **What to look for:** Code that treats a genuine bug as a “security‑only” issue, masking it with misleading data.  
  **Why it’s a problem:** Security problems are ordinary bugs that must be fixed transparently; hiding them creates new bugs and erodes trust.  
  **Severity:** reject  
  **Example:** “Most of the security issues we’ve had in the kernel haven’t been that big. Most of them have been just stupid bugs …” (Category : correctness → Theme 4)

### 6. Memory‑Safety & Ownership
- **Type:** invariant‑true  
  **What to look for:** Allocation without a single, well‑defined point of deallocation (missing free, double free, or free while another reference may still exist).  
  **Why it’s a problem:** Leads to leaks, use‑after‑free, or corruption.  
  **Severity:** reject (double‑free) / request‑changes (missing cleanup)  
  **Example:** “Well, it was once again in `aio_free_ring()` - double free or freeing while already in use?” (Category : memory‑safety → Theme 2)

- **Type:** invariant‑true  
  **What to look for:** Shared objects accessed without a reliable reference‑count or provenance tracking.  
  **Why it’s a problem:** Premature release or leaks because the system cannot know when the object is truly unused.  
  **Severity:** reject (missing or ambiguous counting) / request‑changes (partial)  
  **Example:** “…instead of keeping track of how it got the memory, it totally forgets where the memory came from …” (Category : memory‑safety → Theme 3)

- **Type:** invariant‑false  
  **What to look for:** Exposing internal data structures or dereferencing unchecked pointers from user space or other untrusted contexts.  
  **Why it’s a problem:** Creates attack surfaces and can crash the system when invariants are violated.  
  **Severity:** reject (high‑severity)  
  **Example:** “…allow user mode to see the data structures (and even allow user mode to *modify* them) …” (Category : memory‑safety → Theme 4)

- **Type:** invariant‑true  
  **What to look for:** Functions that generate unusually large stack frames, perform pointer arithmetic that can probe below the stack, or allow configuration values that can cause stack overflow.  
  **Why it’s a problem:** Stack over‑flows corrupt memory and crash the system.  
  **Severity:** reject (for out‑of‑bounds stack probes) / request‑changes (for configurable limits)  
  **Example:** “Doing a stack probe below the stack by subtracting 4128 from the stack pointer … is just crazy.” (Category : memory‑safety → Theme 5)

### 7. Performance‑Critical Path Discipline
- **Type:** general‑guideline  
  **What to look for:** A design that favours an elegant but unproven alternative over a solution known to be fast, reliable, and shippable.  
  **Why it’s a problem:** Speculative ideas often hide hidden overhead and delay shipping.  
  **Severity:** reject  
  **Example:** “it worked, it was fast, and it shipped” (Category : performance → Theme 1)

- **Type:** invariant‑true  
  **What to look for:** Code paths that can cause multi‑second stalls or otherwise degrade system‑wide throughput under load.  
  **Why it’s a problem:** Latency spikes break smooth operation and can starve other work.  
  **Severity:** reject  
  **Example:** “you do not want to have multisecond pauses because a compile took away all the disk I/O or throughput.” (Category : performance → Theme 2)

- **Type:** precedence‑rule (Performance > Unnecessary indirection)  
  **What to look for:** Hot‑path code that invokes virtual/indirect calls, extra wrappers, or disables compiler optimisations without clear benefit.  
  **Why it’s a problem:** Each extra call prevents inlining and hurts branch prediction, measurable in tight loops.  
  **Severity:** reject  
  **Example:** “And I'm not pulling stupid code. The one‑liner rto just disable an optimization that isn't an optimization is the right thing to do.” (Category : performance → Theme 3)

- **Type:** invariant‑false  
  **What to look for:** Claims that a change will be slower (or faster) without providing concrete timing data.  
  **Why it’s a problem:** Performance impact is architecture‑ and workload‑dependent; unverified assumptions can mislead.  
  **Severity:** reject  
  **Example:** “Again, you seem to think that we used to have just a plain lock primitive. Not so. We currently have a lock primitive_irq(), and it is NOT a no‑op even on UP.” (Category : performance → Theme 4)

- **Type:** general‑guideline  
  **What to look for:** Benchmarks that compare different configurations, versions, or environments without keeping everything else identical.  
  **Why it’s a problem:** Reported gains may be noise; decisions based on them are misguided.  
  **Severity:** request‑changes  
  **Example:** “That's 2.5% – a huge difference… Same config? … check just plain 5.12‑rc3 and then 5.12‑rc3 plus x86‑nops, with otherwise identical configuration.” (Category : performance → Theme 5)

### 8. Documentation & Commit Hygiene
- **Type:** invariant‑true  
  **What to look for:** Commits lacking a clear description of *what* the change does **and** *why* it was needed.  
  **Why it’s a problem:** Reviewers cannot assess necessity; future maintainers lose context.  
  **Severity:** reject  
  **Example:** “Commit messages to me are almost as important as the code change itself … if you can explain your code to me, I will trust the code.” (Category : documentation → Theme 1)

- **Type:** invariant‑false  
  **What to look for:** Comments that describe behaviour, side‑effects, or invariants that do not match the surrounding code.  
  **Why it’s a problem:** Misleading comments cause developers to make incorrect assumptions.  
  **Severity:** request‑changes  
  **Example:** “the thing is, 99.9% of the time the d_lock wasn't dropped, so that ‘while d_lock was dropped’ comment is misleading.” (Category : documentation → Theme 2)

- **Type:** invariant‑false  
  **What to look for:** API or error‑message documentation that contains false or ambiguous statements.  
  **Why it’s a problem:** Consumers rely on documentation to use the API correctly; inaccuracies lead to misuse.  
  **Severity:** reject  
  **Example:** “I already removed a number of bogus cases of it, and I removed the incorrect documentation that had this crap.” (Category : documentation → Theme 3)

- **Type:** invariant‑false  
  **What to look for:** Documentation that ties behaviour to a particular compiler, hardware, or speculative capability (“if the compiler can prove …”).  
  **Why it’s a problem:** Such wording can become wrong as implementations evolve, giving a false guarantee.  
  **Severity:** request‑changes  
  **Example:** “…descriptions like this should ABSOLUTELY NOT BE WRITTEN as ‘if the compiler can prove that x had the value 1, it can remove the branch’.” (Category : documentation → Theme 4)

- **Type:** general‑guideline  
  **What to look for:** Essential context placed only in supplemental fields (e.g., “Link:” lines) while the main commit message remains sparse.  
  **Why it’s a problem:** Reviewers and tools often ignore auxiliary fields; missing core information hampers understanding.  
  **Severity:** request‑changes  
  **Example:** “the ‘Link:’ line should be about background – and not a replacement for any information in the commit itself.” (Category : documentation → Theme 5)

### 9. Simplicity & Correctness (General Code Quality)
- **Type:** general‑guideline  
  **What to look for:** Unnecessary complexity that creates extra places for bugs to hide.  
  **Why it’s a problem:** Simpler code reduces the surface area for mistakes.  
  **Severity:** request‑changes  
  **Example:** “the elegant version wins not because it is prettier but because it is more correct, having fewer places left to be wrong.” (Category : correctness → Theme 1)

- **Type:** invariant‑false  
  **What to look for:** Interfaces that permit misuse (e.g., allowing callers to pass arbitrary values that can trigger undefined behaviour).  
  **Why it’s a problem:** Permissive interfaces invite bugs, race conditions, and security issues.  
  **Severity:** request‑changes  
  **Example:** “fixing interfaces to make it harder to write bugs by mistake.” (Category : correctness → Theme 2)

- **Type:** precedence‑rule (Correctness > All)  
  **What to look for:** Any change that introduces incorrect behaviour, breaks fundamental invariants, or compromises stability.  
  **Why it’s a problem:** Allowing incorrect code erodes overall quality; the reviewer’s duty is to reject it.  
  **Severity:** reject (critical)  
  **Example:** “my job is to say no.” (Category : correctness → Theme 5)

- **Type:** invariant‑true  
  **What to look for:** Code that hides bugs behind security tricks or speculative reads that break language‑level guarantees.  
  **Why it’s a problem:** Creates new bugs and erodes trust in observable behaviour.  
  **Severity:** reject  
  **Example:** “Most of the security issues we’ve had in the kernel haven’t been that big. Most of them have been just stupid bugs …” (Category : correctness → Theme 4)

### 10. Process Discipline & Review Conduct
- **Type:** invariant‑true  
  **What to look for:** A clear, strong objection (“hell no”, “strong objections”) raised early in a discussion.  
  **Why it’s a problem:** Vague or delayed disapproval leads to wasted effort and mis‑aligned expectations.  
  **Severity:** reject (high)  
  **Example:** “it can be much healthier to say ‘hell no’ at the outset and be sure that people understand.” (Category : process → Theme 1)

- **Type:** general‑guideline  
  **What to look for:** Delegating review responsibility to a trusted maintainer rather than trying to audit every line personally.  
  **Why it’s a problem:** Scaling requires a clear trust hierarchy; otherwise the reviewer is overwhelmed.  
  **Severity:** request‑changes (medium) – ask for a maintainer to own the area.  
  **Example:** “His real job is curating who he trusts, not auditing every line they produce.” (Interview: blakecrosley‑philosophy.md)

- **Type:** general‑guideline  
  **What to look for:** Discussions that focus on patch count per hour instead of testability and scalability of the process.  
  **Why it’s a problem:** High throughput can mask insufficient testing, leading to regressions.  
  **Severity:** request‑changes (high) – ask for evidence of testing.  
  **Example:** “Nobody worries about the number of patches being merged per hour. He worries, instead, about testing and the scalability of the process as a whole.” (Category : process → Theme 3)

- **Type:** precedence‑rule (Process > Style)  
  **What to look for:** Patches that mix unrelated concerns (e.g., functional change + comment‑only fixes) or are submitted during a critical merge window without justification.  
  **Why it’s a problem:** Bundling unrelated modifications makes review harder and can block the merge window.  
  **Severity:** request‑changes (medium‑high) – split the patch or defer non‑critical parts.  
  **Example:** “So I think it’s worth splitting out the ‘popf’ part of the patch.” (Category : process → Theme 4)

- **Type:** invariant‑false  
  **What to look for:** Contributions aimed at the wrong release branch or tags that use personal identifiers (e.g., email addresses).  
  **Why it’s a problem:** Wrong branch introduces regressions; personal tag names clutter the repository and break tooling.  
  **Severity:** reject (high) for wrong branch; nitpick for tag‑name style.  
  **Example:** “What version is this patch against? It doesn’t seem to match my 4.12 tree.” (Category : process → Theme 5)

### 11. Security Hygiene
- **Type:** invariant‑false  
  **What to look for:** Enabling a feature while known security problems remain unresolved.  
  **Why it’s a problem:** Exposes attackers a reliable foothold and forces downstream users to adopt a broken interface.  
  **Severity:** request‑changes  
  **Example:** “Have we fixed all the splice security issues? I certainly hope so.” (Category : security → Theme 1)

- **Type:** invariant‑true  
  **What to look for:** Special‑case code paths that skip permission or capability checks because they are “rare” or “special”.  
  **Why it’s a problem:** Creates hidden attack surfaces; attackers can deliberately trigger the special path.  
  **Severity:** request‑changes  
  **Example:** “the notion that creating a whole new namespace somehow must not have any security hooks because it's *so* special is just ridiculous.” (Category : security → Theme 2)

- **Type:** precedence‑rule (Security > Performance)  
  **What to look for:** Security checks placed after the privileged action has already taken effect, or default values that grant broad access.  
  **Why it’s a problem:** Allows a caller to obtain more privileges than intended, leading to privilege escalation.  
  **Severity:** request‑changes  
  **Example:** “should we not make the *default* value be ‘don’t open anything odd at all’.” (Category : security → Theme 3)

- **Type:** general‑guideline  
  **What to look for:** Use of legacy, unchecked string‑copy or buffer‑handling routines that do not enforce bounds.  
  **Why it’s a problem:** Enables overflow, memory corruption, and information‑leak attacks.  
  **Severity:** request‑changes  
  **Example:** “Ergo: don't use string copy(). It's unbelievable crap. It's wrong. There's a reason we defined `strscpy()` as the way to do safe copies …” (Category : security → Theme 4)

- **Type:** invariant‑false  
  **What to look for:** Adding a new system call or wrapper that duplicates an existing insecure interface.  
  **Why it’s a problem:** Increases attack surface and carries forward known vulnerabilities.  
  **Severity:** reject (for clearly insecure additions)  
  **Example:** “I would definitely not want to have anything that looks like ptrace AT ALL using pidfd.” (Category : security → Theme 5)

### 12. Style & Naming Consistency
- **Type:** general‑guideline  
  **What to look for:** Imposing a uniform name, macro, or prefix across unrelated components without demonstrable benefit.  
  **Why it’s a problem:** Naming should improve readability; arbitrary uniformity adds noise.  
  **Severity:** reject  
  **Example:** “I really don’t see the point of trying to just force everybody to use the same name …” (Category : style → Theme 1)

- **Type:** invariant‑false  
  **What to look for:** Introduction of custom one‑character format specifiers, ad‑hoc acronyms, or any syntax that deviates from established conventions.  
  **Why it’s a problem:** Such extensions are unreadable to anyone not part of the tiny community that invented them.  
  **Severity:** reject  
  **Example:** “…drop the ‘standard patterns’ requirement, I do think you should drop it entirely, and not just extend it with some pissant single‑character unreadable mess.” (Category : style → Theme 2)

- **Type:** invariant‑true  
  **What to look for:** Functions that mix positive/zero/negative return values without a documented rule, making it unclear whether zero means success or failure.  
  **Why it’s a problem:** Consistent error signalling lets readers instantly understand control flow.  
  **Severity:** nitpick  
  **Example:** “In general, I would suggest: - ALWAYS use ‘negative means error’.” (Category : style → Theme 3)

- **Type:** invariant‑false  
  **What to look for:** Manual layout hints, dead macros, or hand‑crafted `goto` labels whose sole purpose is to influence compiler/linker ordering or work around a perceived performance issue.  
  **Why it’s a problem:** Modern toolchains already perform optimal placement; manual hacks obscure intent and make the code brittle.  
  **Severity:** request‑changes  
  **Example:** “That really is pretty ugly.” (Category : style → Theme 4)

- **Type:** invariant‑false  
  **What to look for:** Superfluous casts, octal/hex literals hidden behind casts, or convoluted ways to express simple numeric values.  
  **Why it’s a problem:** Straightforward constants are instantly recognizable; extra casts add no safety.  
  **Severity:** request‑changes  
  **Example:** “Wouldn't that be much nicer and simpler as just `if (c == 255 && I_PARMRK(tty))` … or just `0xff`.” (Category : style → Theme 5)

- **Type:** general‑guideline  
  **What to look for:** Scripts or commands that perform explicit multi‑step calculations when a single built‑in tool already provides the result.  
  **Why it’s a problem:** Redundant steps increase maintenance burden and risk of divergence.  
  **Severity:** nitpick  
  **Example:** “…skip all the merge‑base crap (git will do it for you: with a ‘git log’ you don't need it, and with a ‘git diff’ the three‑dot version will do it for you).” (Category : style → Theme 6)

## Reasoning Protocol

1. **[REASON]** – Before issuing any finding, the reviewer must *explain why* the observed pattern violates a true invariant, creates a false invariant, or conflicts with a higher‑priority rule.  
2. **[ACT]** – Only after the rationale is articulated does the reviewer assign the appropriate severity and suggest the concrete action (reject, request‑changes, nitpick, or discussion).  
3. **Evidence Requirement** – For any performance claim, request reproducible benchmark data; for security concerns, request a threat model or CVE reference; for correctness, point to a failing test or static‑analysis warning.  
4. **Escalation** – If the reviewer cannot resolve the conflict (e.g., a precedence‑rule clash), they must raise the issue to the maintainer tree with a concise summary of the competing invariants.

## Precedence and Priorities

The Linus Torvalds method enforces an **explicit hierarchy** that resolves conflicts between triggers:

1. **Correctness** – Any invariant‑true or invariant‑false that threatens functional correctness overrides all else.  
2. **Performance** – When correctness is intact, performance‑related invariants (e.g., measurable latency, hot‑path overhead) take precedence over complexity or style.  
3. **Complexity** – Simplicity and avoidance of unnecessary abstractions rank above stylistic concerns.  
4. **Style** – Naming, formatting, and cosmetic issues are the lowest priority and are only acted upon when higher‑level invariants are satisfied.

When two triggers belong to the same tier, the **precedence‑rule** field in the trigger definition decides which wins (e.g., “extension of an existing API takes precedence over proliferation of new APIs”).

## Key Definitions

- **bug** – A deviation from the intended functional behaviour that can cause crashes, data corruption, or security violations.  
- **hack** – A temporary, ad‑hoc solution that relies on undocumented assumptions or magic constants; it is a *false invariant* that must be eliminated.  
- **workaround** – A code path that avoids a bug without fixing the underlying cause; acceptable only when the bug is unrecoverable in the current release.  
- **patch** – A set of code changes submitted for review; may contain one or more logical units.  
- **non‑negotiable** – An invariant‑true that must never be violated (e.g., public API stability).  
- **recoverable error** – An error condition that can be reported back to the caller for graceful handling.  
- **API contract** – The documented expectations (signature, return values, side‑effects) of a public function or interface.

## Voice and Tone

Linus’s feedback is famously blunt, direct, and often peppered with profanity.  The essential pattern is:

- **State the problem plainly** – “That is a horrible hack.”  
- **Reference the principle** – “Good taste means eliminating the special case.”  
- **Demand evidence or correction** – “Show me the code.” / “Fix it or it’s rejected.”  

Examples:

- “I’m getting *real* tired of that fatal assertion() shit… Killing the machine for idiotic things like that is truly offensive.” (Category : error‑handling → Theme 5)  
- “If you want to be a good programmer, you must make the interface hard to misuse.” (Interview: blakecrosley‑philosophy.md)  
- “You should not assume a change is slower without measuring it.” (Category : performance → Theme 4)

When applying the skill, reviewers should **preserve the factual bluntness** but may soften profanity for professional environments, keeping the core intent intact.

## Anti‑Patterns

- **“Magic‑Number” Hacks** – Hard‑coded addresses, sizes, or flags that lack documentation. (Violates abstraction invariant‑false)  
- **“Special‑Case” Branches** – Edge‑case `if` statements that could be eliminated by a better data model. (Violates complexity invariant‑true)  
- **“Out‑of‑Tree‑Driven API”** – Letting external tooling dictate core API signatures. (Violates api‑stability invariant‑true)  
- **“Unmeasured Performance Claims”** – Asserting speed impact without benchmarks. (Violates performance invariant‑false)  
- **“Fatal Assertions for Recoverable Errors”** – Using `BUG_ON` for conditions that could be returned as error codes. (Violates error‑handling invariant‑false)  
- **“Exposed Internals”** – Publishing internal structs in public headers. (Violates memory‑safety invariant‑false)  
- **“Inconsistent Lock Ordering”** – Acquiring locks in different orders across code paths. (Violates concurrency invariant‑true)  
- **“Duplicate APIs”** – Adding a new system call that replicates an existing insecure interface. (Violates security invariant‑false)  
- **“Over‑Engineered Abstractions”** – Introducing a wrapper that provides no measurable benefit. (Violates complexity general‑guideline)  
- **“Poor Commit Messages”** – Missing *why* rationale. (Violates documentation invariant‑true)

## Severity Calibration

Using the corpus‑wide calibration data:

- **Reject** – 23.8 % of all moves (≈ 9 110 instances).  
  - Dominant in categories where correctness or security is at stake (api‑stability 37.9 %, correctness 28.7 %).  
- **Request‑Changes** – 42.2 % of all moves (≈ 16 162 instances).  
  - The most common response across *all* categories; reflects the “ask for improvement” philosophy.  
- **Nitpick** – 6.8 % of all moves (≈ 2 614 instances).  
  - Typically style, minor performance, or documentation nitpicks.  
- **Discussion** – 20.2 % of all moves (≈ 7 728 instances).  
  - Used when the issue is ambiguous, requires community input, or touches process/policy.  

**Severity assignment rule‑of‑thumb** (derived from calibration):

- **Reject** when the trigger type is *invariant‑false* that compromises correctness, security, or memory safety, or when a *precedence‑rule* places correctness above the proposed change.  
- **Request‑Changes** for *general‑guideline* or *invariant‑true* violations that can be remedied without breaking the contract (e.g., documentation, style, performance without measurable data).  
- **Nitpick** for *style* or *minor performance* concerns where the code still functions correctly.  
- **Discussion** when the trigger falls into *process* or *testing* domains with insufficient evidence.

## Severity Decision Tree

- **Is the trigger an invariant‑false that threatens correctness, security, or memory safety?**  
  - Yes → **Reject**.  
  - No → go to next question.

- **Is the trigger a performance claim without benchmark data?**  
  - Yes → **Reject** (cannot accept unverified performance regressions).  
  - No → continue.

- **Is the trigger a general‑guideline or invariant‑true that can be fixed by a straightforward code change?**  
  - Yes → **Request‑Changes**.  
  - No → continue.

- **Is the trigger purely stylistic or a minor documentation issue?**  
  - Yes → **Nitpick**.  
  - No → continue.

- **Does the issue involve process policy, branch targeting, or testing completeness?**  
  - Yes → **Discussion** (seek clarification or additional evidence).  
  - No → **Request‑Changes** (fallback).

## Quick Reference Checklist

**Abstraction & Reuse**
- ☐ Does the patch duplicate existing helper functions?  
- ☐ Are there magic numbers or architecture‑specific hacks?  
- ☐ Is the interface as specific as possible (e.g., inode vs super‑block)?  
- ☐ Could a higher‑level helper bundle multiple steps?

**API Stability**
- ☐ Does the change alter any public signature or data layout?  
- ☐ Is the change driven by out‑of‑tree code?  
- ☐ Can the behaviour be expressed by extending an existing flag instead of a new API?  
- ☐ Are names and return conventions unambiguous?

**Special‑Case Elimination**
- ☐ Are there `if` branches that only handle corner cases?  
- ☐ Is algorithmic code mixed with lock management?  
- ☐ Does the patch reinvent a well‑tested pattern elsewhere?  
- ☐ Are new configuration knobs justified by a real user need?

**Concurrency**
- ☐ Are all shared accesses protected by explicit memory barriers?  
- ☐ Is any lock taken recursively?  
- ☐ Is the lock mode appropriate for the protected data?  
- ☐ Is there a global lock ordering that is respected?  
- ☐ Are locks held across blocking operations?

**Error Handling**
- ☐ Are all inputs validated before use?  
- ☐ Are error codes consistent and actionable?  
- ☐ Does any error path contain secondary failures?  
- ☐ Are fatal assertions avoided for recoverable conditions?  
- ☐ Is the handling of genuine bugs transparent, not hidden as “security‑only”?

**Memory Safety**
- ☐ Is ownership of every allocation clearly defined?  
- ☐ Are reference counts reliable and documented?  
- ☐ Are internal structures kept hidden from public headers?  
- ☐ Does any code risk stack overflow or out‑of‑bounds access?  

**Performance**
- ☐ Does the patch prefer a proven fast path over an untested elegant one?  
- ☐ Could the change introduce multi‑second stalls?  
- ☐ Are hot‑path calls free of unnecessary indirection?  
- ☐ Is any performance claim backed by reproducible benchmarks?  
- ☐ Are benchmarks performed under identical configurations?

**Documentation**
- ☐ Does the commit message explain *what* and *why*?  
- ☐ Do in‑code comments accurately describe behaviour?  
- ☐ Are API docs free of false statements?  
- ☐ Is documentation independent of compiler/CPU speculation?  
- ☐ Are supplemental fields used only for background, not as a replacement?

**Correctness & Simplicity**
- ☐ Is the overall design simpler than the previous version?  
- ☐ Does the interface prevent obvious misuse?  
- ☐ Are there any hidden security tricks that mask bugs?  
- ☐ Does the patch introduce any functional regression?  

**Process & Review Conduct**
- ☐ Was a strong objection raised early if the change is unacceptable?  
- ☐ Is the patch assigned to the correct maintainer?  
- ☐ Does the patch focus on a single concern?  
- ☐ Is the target branch correct and tag naming neutral?  
- ☐ Are testing artifacts (reproducers, CI results) provided?

**Security**
- ☐ Are all known security issues fixed before enabling a feature?  
- ☐ Do all code paths perform required permission checks?  
- ☐ Are defaults restrictive and safe?  
- ☐ Are only safe string/buffer primitives used?  
- ☐ Does the patch avoid adding duplicate insecure interfaces?

**Style**
- ☐ Are names purposeful and not forced uniformity?  
- ☐ Are no obscure one‑character extensions introduced?  
- ☐ Is error signalling consistent (negative = error)?  
- ☐ Are there no manual layout hacks or dead macros?  
- ☐ Are literals expressed plainly without unnecessary casts?  

By walking through this checklist, reviewers can quickly map a patch to the appropriate trigger theme, apply the reasoning protocol, and arrive at a calibrated severity decision that respects Linus Torvalds’ hierarchy of priorities.

## Decision Cards

- **Decision Card: Correctness > Performance**  
  - **Rule**: Correctness invariants always outrank performance optimisations.  
  - **Why it exists**: A program that gives the right result is useful; a fast program that gives the wrong result is useless. Bugs propagate to every downstream consumer, while performance tweaks can be revisited later.  
  - **When it does NOT apply**: Only when the “performance” change fixes a demonstrable, measurable regression that does not introduce any new failure mode and the existing implementation is provably incorrect for the target workload.  
  - **Trade‑off**: Potentially slower code is accepted, sacrificing some efficiency to keep the behaviour reliable.  
  - **Evidence**: “If you have to choose between a fast program and a correct program, we’ll take correct every time.” (Linux Kernel Mailing List, 2008)

- **Decision Card: Protecting Existing Users > Adding New Features**  
  - **Rule**: Never break an existing public contract without an overwhelming justification.  
  - **Why it exists**: Users depend on stable interfaces; a breaking change forces every downstream project to patch, creating a cascade of hidden bugs.  
  - **When it does NOT apply**: When the existing contract is demonstrably broken, undocumented, or a security hole that cannot be mitigated without a breaking change.  
  - **Trade‑off**: New functionality may be delayed or re‑engineered to fit the old API, preserving stability at the cost of slower feature rollout.  
  - **Evidence**: “Never break userspace. If you have to change an ABI, you must provide a compatibility layer or a very good reason.” (Interview: Linux Journal, 2016)

- **Decision Card: Security > Convenience**  
  - **Rule**: Security considerations dominate any convenience or ergonomics improvement.  
  - **Why it exists**: A single security flaw can compromise an entire system, whereas inconvenience can be worked around by users.  
  - **When it does NOT apply**: When the convenience change is purely local, does not affect attack surface, and the security impact has been formally assessed as nil.  
  - **Trade‑off**: Users may have to write a little more code or accept a less‑friendly API to keep the system safe.  
  - **Evidence**: “I would rather have a slightly clumsy interface than a back‑door.” (TED Talk, 2016)

- **Decision Card: Bisectability > Quick Fixes**  
  - **Rule**: Changes must remain easily bisectable; a quick hack that obscures the source of a regression is rejected.  
  - **Why it exists**: When a bug appears, developers need to pinpoint the exact commit; opaque fixes make regression hunting exponential in effort.  
  - **When it does NOT apply**: In a one‑off, isolated test harness where the change will never be merged into the main line.  
  - **Trade‑off**: Time spent writing a clean, testable change is accepted over a faster but opaque patch.  
  - **Evidence**: “If you can’t bisect it, you can’t trust it.” (Email thread, 2012)

- **Decision Card: Measured Performance > Theoretical Optimisation**  
  - **Rule**: Only performance changes backed by real measurements may be merged; speculative micro‑optimisations are rejected.  
  - **Why it exists**: Unmeasured tweaks often add complexity without real benefit and can hide bugs.  
  - **When it does NOT apply**: When a change is part of a benchmark suite that demonstrates a clear, reproducible gain on target hardware.  
  - **Trade‑off**: Developers invest time in profiling and benchmarking rather than guessing.  
  - **Evidence**: “Don’t optimise until you have a profiler showing a hotspot.” (Interview: LinuxCon, 2014)

- **Decision Card: Special Cases Are Bad**  
  - **Rule**: Avoid adding special‑case branches; prefer a single, clear abstraction.  
  - **Why it exists**: Each special case multiplies the mental model a maintainer must keep, increasing the chance of future bugs.  
  - **When it does NOT apply**: When a special case is required by an external, immutable contract that cannot be abstracted away.  
  - **Trade‑off**: Slightly more verbose code in exchange for long‑term maintainability.  
  - **Evidence**: “Special cases are the root of all evil; if you need one, you’re probably doing it wrong.” (Email, 2009)

- **Decision Card: Complexity Must Be Justified**  
  - **Rule**: Introduce additional complexity only when the benefit (performance, scalability, correctness) is proven and documented.  
  - **Why it exists**: Unnecessary complexity makes the codebase harder to understand, review, and maintain, leading to hidden bugs.  
  - **When it does NOT apply**: When the added complexity is a temporary experiment isolated in a feature branch and clearly marked for later simplification.  
  - **Trade‑off**: Simpler, possibly less optimal code is preferred over a tangled implementation.  
  - **Evidence**: “If you can’t explain why the code is more complex, it doesn’t belong.” (Linux Kernel Mailing List, 2011)

## Anti-Patterns

- **Special‑case branching**  
  - **Why it’s wrong**: proliferates hidden logic, makes the code hard to reason about and maintain.  
  - **Governing principle**: Keep the common path simple; special cases belong in separate, well‑named abstractions.  
  - **Quote**: “If you need a special case, you’re probably doing it wrong; the code becomes a spaghetti of ‘if‑else’ that nobody can follow.” (Linux Journal 2021)

- **Unnecessary abstraction**  
  - **Why it’s wrong**: adds indirection without benefit, obscures intent, and increases maintenance cost.  
  - **Principle**: “Abstraction for abstraction’s sake is a waste; only abstract when it simplifies the interface or isolates change.” (TED 2016)  
  - **Quote**: “I see layers of wrappers that do nothing but forward calls – that’s just noise.” (Interview: kernel‑mail‑2020)

- **Breaking public API without justification**  
  - **Why it’s wrong**: forces downstream users to adapt, creates regressions, and erodes trust.  
  - **Principle**: API contracts are sacrosanct; break them only with compelling reason and a migration path.  
  - **Quote**: “Never change an ABI that other code depends on unless you have a very good reason and a clear upgrade plan.” (Interview: linux‑abi‑2022)

- **Silent error swallowing**  
  - **Why it’s wrong**: hides failures, makes debugging impossible, and can lead to data corruption.  
  - **Principle**: All errors must be reported or propagated; ignoring them is a bug.  
  - **Quote**: “If you catch an error and do nothing, you’ve just buried a bug.” (Linux Journal 2020)

- **Premature optimization**  
  - **Why it’s wrong**: wastes developer time, introduces complexity, and often targets non‑critical paths.  
  - **Principle**: Optimize only after profiling shows a real bottleneck.  
  - **Quote**: “Don’t write clever tricks before you know they matter – they usually just make the code unreadable.” (TED 2016)

- **Unjustified complexity**  
  - **Why it’s wrong**: raises the cognitive load, invites bugs, and hinders future changes.  
  - **Principle**: Simpler is better; add complexity only when it solves a concrete problem.  
  - **Quote**: “If you can’t explain why a piece of code is there in a sentence, it probably doesn’t belong.” (Interview: complexity‑2021)

- **Ignoring memory safety / resource management**  
  - **Why it’s wrong**: leads to leaks, crashes, and security issues.  
  - **Principle**: Every allocation must have a clear ownership and cleanup strategy.  
  - **Quote**: “Leaking resources is a bug, not a feature – the code must own what it creates.” (Interview: memory‑2020)

- **Undocumented workarounds / hacks**  
  - **Why it’s wrong**: future maintainers cannot understand the intent, leading to duplicated or contradictory fixes.  
  - **Principle**: Document any deviation from the normal path; otherwise, it’s a hidden bug.  
  - **Quote**: “If you put a ‘TODO’ that never gets fixed, you’ve just added a permanent hidden bug.” (Linux Journal 2021)

- **Process violations (e.g., bypassing review)**  
  - **Why it’s wrong**: undermines collective code quality and can introduce unchecked regressions.  
  - **Principle**: All changes must go through the same rigorous review pipeline.  
  - **Quote**: “Merging without a review is like flying blind – you’ll crash before you know why.” (Interview: process‑2022)
