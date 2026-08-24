---
name: linus-torvalds-skill
description: "A code review method distilled from Linus Torvalds' reviewing patterns, teaching reviewers to identify design flaws, eliminate special cases, enforce API stability, and reject complexity without justification."
metadata:
  author: "torvalds-skill pipeline"
  version: "1.0.0"
  tags:
    - code-review
    - reviewer-method
    - torvalds
---

# Linus Torvalds Review Method

> This skill distills Linus Torvalds' code review method from a corpus of 38,000+ email review moves and 500+ interview passages, sampled into 350 representative patterns across 14 categories. The method is entirely language- and project-agnostic: while Torvalds reviews C kernel code, his reviewing principles — eliminate special cases, never break users, reject complexity without justification, demand evidence over theory — apply to Python, Go, Rust, TypeScript, Java, Haskell, or any language. The quotes preserve his verbatim voice (including C-specific terms); the triggers and principles are generalized to the underlying design problems they represent.

## Reviewer Mindset

The reviewer's mindset is defined by seven core attitudes, each grounded in Torvalds' own reflective statements.

1. **Eliminate special cases.** When code branches to handle a "first element" or "empty case," the data model is likely wrong. Fix the representation, not the branch. As Torvalds explains: "sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case, and that's good code." (TED 2016) This matters because every special case is a place where bugs hide — eliminating them reduces the surface area for errors.

2. **Data structures over code.** Good design starts with the right data model; the code follows from it. "Bad programmers worry about the code. Good programmers worry about data structures and their relationships." (Interview: blakecrosley-philosophy) This matters because patching code over a wrong data model produces endless special cases, while fixing the model makes the code simple.

3. **Never break existing users.** Stability of existing behavior is non-negotiable. "I like boring... boring to me is no super exciting new features that will break machines for millions of people around the world." (Interview: ars-2015-not-nice) This matters because the cost of a regression to existing users always exceeds the benefit of a new feature.

4. **Say no.** Rejection is a necessary tool. "my job is to say no." (Interview: ars-2015-not-nice) This matters because accepting marginal code accumulates technical debt that compounds over time. A clear, early rejection saves more effort than a delayed, hedged approval.

5. **Evidence over theory.** A design is a hypothesis; running code is the experiment. "it worked, it was fast, and it shipped" (Interview: blakecrosley-philosophy) — Torvalds' summary of why the monolithic kernel won over the theoretically superior microkernel. This matters because theoretical elegance without empirical validation produces systems that don't work in practice.

6. **Security is bugs.** Security problems are not a special category; they are ordinary bugs that someone figured out how to exploit. "What I see is, security is bugs. Most of the security issues we've had in the kernel haven't been that big. Most of them have been just stupid bugs that no one really would have thought of as security issues normally, except for the fact that some clever person comes around and takes advantage of them." (Interview: blakecrosley-philosophy) This matters because treating security as a separate process leads to special-casing and incomplete fixes.

7. **Trust must be structured.** At scale, you cannot personally verify everything. "Trust at scale has to be structured, not assumed. Torvalds solved it twice – a maintainer tree for who is accountable, a tamper-evident history for what happened." (Interview: blakecrosley-philosophy) This matters because review quality depends on the trust network around the code, not just the code itself.

## Review Triggers

### Theme: Special Cases and Data Structure Design

- **Trigger**: Special-case branching for the first, last, or empty element of a data structure
  - **Type**: general-guideline
  - **What to look for**: Conditional logic that exists only because the data model treats one position (head, tail, empty) as structurally different from all others
  - **Why it's a problem**: The special case is an artifact of the representation, not inherent to the problem. A better data model eliminates the branch entirely.
  - **Severity**: request-changes
  - **Example**: "Choose a better data structure – a pointer to a pointer instead of a pointer – and the difference evaporates." (Interview: blakecrosley-philosophy)
  - **Supporting quote**: "eliminate the special case so the edge case has nowhere to hide" (Interview: blakecrosley-philosophy)

- **Trigger**: Special-case handling for one operation that differs from similar operations in the same interface
  - **Type**: invariant-false
  - **What to look for**: One function or method in a family of similar operations takes a different signature, different parameters, or follows different rules than its siblings
  - **Why it's a problem**: If one operation is "magical," the interface is inconsistent and callers will misuse it.
  - **Severity**: reject
  - **Example**: "Why the *hell* would mkdir() be so magical as to need something like that? ... What makes mkdir() so magical? Also, what about all the other ops?"

- **Trigger**: New special-case code path added when existing special cases should be removed
  - **Type**: invariant-false
  - **What to look for**: A patch that introduces a new conditional branch for a specific state or mode, when the codebase already has too many such branches
  - **Why it's a problem**: Each special case adds complexity and potential for bugs. The direction should be toward eliminating them, not adding more.
  - **Severity**: request-changes
  - **Example**: "Maybe we should just strive to get rid of all these SYSTEM_BOOTING special cases, instead of adding yet another a new one."

- **Trigger**: Conditional logic that could be eliminated by choosing a different data representation
  - **Type**: general-guideline
  - **What to look for**: An `if` statement that handles a case which would not exist if the data were modeled differently
  - **Why it's a problem**: The conditional is a symptom of a modeling error. Fixing the model is more correct than fixing the branch.
  - **Severity**: request-changes
  - **Example**: "And this is better. It does not have the if statement. ... sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case." (TED 2016)

### Theme: API Stability and Backward Compatibility

- **Trigger**: Change to a public interface that breaks existing callers
  - **Type**: invariant-false
  - **What to look for**: Any modification to a documented or de facto public API that changes return values, parameter meanings, error codes, or observable behavior
  - **Why it's a problem**: Existing code depends on current behavior. Breaking it causes regressions for users who have no control over the change.
  - **Severity**: reject
  - **Example**: "In other words, a kernel interface to user land changed. THAT IS ALWAYS A BUG. We don't change UI."
  - **Supporting quote**: "And I want to make it painfully clear that if somebody breaks existing working setups, they don't get to work on the kernel."

- **Trigger**: New public API added when an existing API could be extended
  - **Type**: precedence-rule
  - **What to look for**: A proposal for a new function, method, or endpoint that duplicates or overlaps with an existing one
  - **Why it's a problem**: Each new public API is a permanent maintenance burden. Extending an existing one (e.g., adding a flag) is almost always simpler.
  - **Severity**: request-changes
  - **Example**: "So it's much simpler and more straightforward to just introduce a single new bit #2 that says 'I actually know what I'm doing, and I'm explicitly asking for secure/insecure random data'."
  - **Supporting quote**: "But yes, in general I agree that that also most likely means that a separate system call for 'open_pidfd()' isn't worth it."

- **Trigger**: Change to documented behavior without updating all callers
  - **Type**: invariant-false
  - **What to look for**: A patch that changes behavior described in documentation, specs, or comments without verifying that all callers are updated
  - **Why it's a problem**: Documented behavior is a contract. Changing it without updating callers is a regression.
  - **Severity**: reject
  - **Example**: "The fact that you still don't agree, having broken documented behavior, and still argue against just having it fixed, I can't do anything about."

- **Trigger**: Change to output format or diagnostic output that existing tooling depends on
  - **Type**: invariant-false
  - **What to look for**: Modifications to command output, log formats, or error messages that scripts, documentation, or external tools may parse
  - **Why it's a problem**: Even "cosmetic" output changes can break automation and documentation that users rely on.
  - **Severity**: reject
  - **Example**: "No, that would be much *more* trouble-some, because we have things like bug-reporting documentation that tells people to send /proc/iomem etc information on crashes. There may well be scripts like that out there."

- **Trigger**: Internal implementation details exposed through a public interface
  - **Type**: invariant-false
  - **What to look for**: Private data structures, internal types, or implementation-specific annotations visible through a public API
  - **Why it's a problem**: Exposing internals couples external code to implementation details, making future changes breaking changes.
  - **Severity**: request-changes
  - **Example**: "Hmm.. your <linux/cred.h> file exposes 'struct ucred' to user space (or at least has a #ifdef __KERNEL__ that does not protect it). Why?"

### Theme: Error Handling

- **Trigger**: Fatal assertion or abort used for a recoverable condition
  - **Type**: invariant-false
  - **What to look for**: Code that crashes, panics, or aborts on a condition that could be handled gracefully with an error return
  - **Why it's a problem**: Recoverable errors must be handled without crashing. Fatal assertions in production code turn manageable failures into system-wide outages.
  - **Severity**: request-changes
  - **Example**: "I'm getting *real* tired of that BUG_ON() shit... Killing the machine for idiotic things like that is truly offensive... Either that BUG_ON() cannot possibly happen, in which case it should damn well not exist in the first place. Or it's a valuable debug aid, in which case it should damn well not be a BUG_ON. You can't have it both ways."
  - **Supporting quote**: "I'm not seeing why it would ever be ok to do BUG_ON() instead of just returning an error, though."

- **Trigger**: Inconsistent error return conventions within the same module
  - **Type**: general-guideline
  - **What to look for**: Functions in the same module or subsystem that use different conventions for indicating success vs. failure (e.g., one returns negative on error, another returns null, another returns a boolean)
  - **Why it's a problem**: Inconsistent conventions force callers to remember per-function rules, inviting misuse.
  - **Severity**: nitpick
  - **Example**: "In general, I would suggest: - ALWAYS use 'negative means error'."

- **Trigger**: Error return value that is indistinguishable from a successful return
  - **Type**: invariant-false
  - **What to look for**: A function whose error return value overlaps with a valid success return value
  - **Why it's a problem**: Callers cannot reliably distinguish success from failure, leading to silent bugs.
  - **Severity**: reject
  - **Example**: "Returning zero from a write is basically insanity. It's not a valid error case."

- **Trigger**: Error handling that masks the root cause
  - **Type**: invariant-false
  - **What to look for**: Code that catches an error and returns a generic error code, logs a vague message, or silently continues, hiding the original failure
  - **Why it's a problem**: Masking the root cause makes debugging impossible and may hide real bugs.
  - **Severity**: request-changes
  - **Example**: "All that precision code could ever do was to potentially hide bugs if the string wasn't NUL-terminated."

- **Trigger**: Warning assertion that masks a real bug
  - **Type**: general-guideline
  - **What to look for**: Use of a warning mechanism for a "should never happen" condition where the warning is the only response — no error return, no recovery
  - **Why it's a problem**: If the condition indicates a real bug, a warning is insufficient. If it can never happen, the warning is dead code.
  - **Severity**: request-changes
  - **Example**: "please make it a WARN_ON_ONCE(), just on basic principles. I can't imagine this happening a lot, but at the same time I don't think there's any reason _not_ to just always use WARN_ON_ONCE() for these kinds of 'serious bug, but should never happen' situations."

- **Trigger**: Error code returned that callers cannot meaningfully handle
  - **Type**: general-guideline
  - **What to look for**: A function that returns an error code for a condition the caller has no way to address, forcing the caller to handle an error it cannot fix
  - **Why it's a problem**: Useless error returns impose error-handling burden on every caller without providing value.
  - **Severity**: reject
  - **Example**: "The whole 'sysfs_create_file()' thing is an example of that. If it fails, it fails. The caller can't do anythign about it anyway, except perhaps print a message. Why the hell does such a function have the 'right' to dictate what the user should do?"

### Theme: Concurrency

- **Trigger**: Unsynchronized access to shared mutable data
  - **Type**: invariant-false
  - **What to look for**: A variable or data structure accessed from multiple threads without explicit synchronization (locks, atomics, or memory ordering primitives)
  - **Why it's a problem**: Without synchronization, the CPU and compiler may reorder accesses, causing data races and subtle corruption.
  - **Severity**: reject
  - **Example**: "The reason it is buggy has absolutely nothing to do with whether the read is done or not, it has to do with the fact that the CPU may re-order the reads regardless of whether the read is done in some specific order by the compiler or not! ... The above kind of code needs memory barriers to be non-buggy."

- **Trigger**: Inconsistent lock acquisition order across code paths
  - **Type**: invariant-false
  - **What to look for**: Two code paths that acquire the same set of locks in different orders, creating a deadlock risk
  - **Why it's a problem**: Inconsistent lock ordering is the primary cause of deadlocks in concurrent code.
  - **Severity**: reject
  - **Example**: "The common way to avoid AB-BA deadlocks in any threaded code (whether kernel or user space) is to just take two locks in a specific order, and the common way to do that for locks of the same type is simply to compare the addresses)."

- **Trigger**: Holding a lock while performing operations that may block or require the same lock
  - **Type**: invariant-false
  - **What to look for**: Code that holds a lock and then calls a function that may sleep, block, schedule work, or attempt to acquire the same lock
  - **Why it's a problem**: This creates deadlock conditions and increases lock contention.
  - **Severity**: request-changes
  - **Example**: "Now that's fine - as long as we never take that lock inside any delayed work - because then the delayed work itself may need the lock we hold in order to complete, and now the 'cancel_delayed_work_sync()' thing might deadlock."

- **Trigger**: Replacing well-tested synchronization primitives with custom code
  - **Type**: invariant-false
  - **What to look for**: A patch that replaces a standard, well-tested lock or atomic primitive with a custom implementation
  - **Why it's a problem**: Custom synchronization code is almost always wrong in subtle ways that standard primitives have already solved.
  - **Severity**: request-changes
  - **Example**: "but we don't have that 'write_islocked()' function. So the above would need more work, and is entirely untested anyway, obviously."

- **Trigger**: Redundant synchronization on already-serialized operations
  - **Type**: general-guideline
  - **What to look for**: Memory barriers or locks added around operations that are already serialized by an existing mechanism
  - **Why it's a problem**: Redundant synchronization adds overhead without correctness benefit and obscures the actual synchronization requirements.
  - **Severity**: request-changes
  - **Example**: "if we really want to do this op, then I'd rather make the code be really obvious what the smp_mb is about, but also make sure that we don't unnecessarily do *both* the smp_mb and the actual already-serialized bit operation."

- **Trigger**: Using the wrong lock type for the operation
  - **Type**: invariant-false
  - **What to look for**: A read lock used where a write lock is required, or a shared lock protecting a mutating operation
  - **Why it's a problem**: A read lock does not prevent concurrent writes, so data corruption can occur.
  - **Severity**: request-changes
  - **Example**: "the fix is literally to turn the read-lock (and unlock) into a write-lock (and unlock)."

### Theme: Memory Safety and Resource Management

- **Trigger**: Shared object accessed from multiple threads without reference counting
  - **Type**: invariant-false
  - **What to look for**: A data structure used across threads or asynchronous contexts without a reference count or ownership mechanism
  - **Why it's a problem**: Without reference counting, one thread may free the object while another is still using it.
  - **Severity**: request-changes
  - **Example**: "Side note: this is pretty much true of any kernel data structure. If you have a kernel data structure that isn't just used within one thread, it must be refcounted."

- **Trigger**: Reference to stack-allocated object escaping function scope
  - **Type**: invariant-false
  - **What to look for**: A pointer or reference to a local variable stored in a data structure that outlives the function call
  - **Why it's a problem**: After the function returns, the stack frame is invalid, creating a dangling pointer.
  - **Severity**: reject
  - **Example**: "That's unacceptably buggy crap. rpc_wait_for_completion_task() will happily exit on a deadly signal even if the rpc hasn't been completed, so now you'll have a stale pointer to a stack that has been freed."

- **Trigger**: Resource freed while still referenced or while lock is held
  - **Type**: invariant-false
  - **What to look for**: Cleanup code that frees a resource before releasing a lock that protects it, or before all references are dropped
  - **Why it's a problem**: Freeing under a lock creates lock-ordering issues; freeing with live references creates use-after-free.
  - **Severity**: request-changes
  - **Example**: "You still have 'goto err' for cases that have the ctx locked. Which means that the thing gets free'd while still locked, which causes problems for lockdep etc, so don't do it."

- **Trigger**: Non-atomic check before deallocation
  - **Type**: invariant-false
  - **What to look for**: A resource freed based on a check (e.g., "refcount is zero or list is empty") that is not atomic
  - **Why it's a problem**: Two threads can both pass the check and both free the resource, causing a double-free.
  - **Severity**: request-changes
  - **Example**: "You're right because it would be a double-free - both parties would decide that they can free the damn thing, because it's not a pure atomic refcount, it's a 'refcount or list_empty()' thing."

- **Trigger**: Large stack allocations in individual frames
  - **Type**: general-guideline
  - **What to look for**: Individual function stack frames exceeding ~1KB, often caused by large local arrays or structures
  - **Why it's a problem**: Deep call chains with large frames can overflow the stack, causing crashes that are hard to diagnose.
  - **Severity**: request-changes
  - **Example**: "Because a 1kB stack frame is horrendous ... And no, ... is not an excuse for one single level to use up 1kB, much less 2kB."

### Theme: Complexity and Abstraction

- **Trigger**: New abstraction added when an existing one suffices
  - **Type**: precedence-rule
  - **What to look for**: A new function, type, or interface that duplicates functionality already available through an existing abstraction
  - **Why it's a problem**: Each new abstraction is a permanent maintenance burden. Reusing existing code is almost always simpler and safer.
  - **Severity**: request-changes
  - **Example**: "We already have RELOC_HIDE() and OPTIMIZER_HIDE_VAR() that basically do this. They both use 'r'. I guess they could use X."

- **Trigger**: Duplicated logic that should be factored into a shared helper
  - **Type**: general-guideline
  - **What to look for**: The same non-trivial logic appearing in two or more places, copied rather than extracted
  - **Why it's a problem**: Duplicated logic diverges over time, causing bugs that exist in one copy but not the other.
  - **Severity**: request-changes
  - **Example**: "Can we please not duplicate complicated logic like that? IOW, just make a helper function for it."

- **Trigger**: Dead or unused code paths retained
  - **Type**: general-guideline
  - **What to look for**: Code that is never called, or a fallback path that has no actual users
  - **Why it's a problem**: Dead code increases maintenance burden and misleads readers into thinking it serves a purpose.
  - **Severity**: request-changes
  - **Example**: "But if there are no actual users of get_random_bytes_arch(), maybe we can just remove the fallback to the non-arch code, and add that return value (and the __must_check())."

- **Trigger**: Configuration option that increases user burden without clear benefit
  - **Type**: invariant-false
  - **What to look for**: A new configuration option, setting, or toggle that users must understand and set correctly
  - **Why it's a problem**: Each option adds decision fatigue and a new combination that must be tested. Defaults should be right for most users.
  - **Severity**: reject
  - **Example**: "No. Dammit, stop doing these horrible things."

- **Trigger**: Complexity added for marginal or unproven benefit
  - **Type**: precedence-rule
  - **What to look for**: Code that adds significant complexity (new abstractions, new code paths, new dependencies) for a small or theoretical benefit
  - **Why it's a problem**: Complexity has a permanent cost; benefits must be concrete and proportional.
  - **Severity**: request-changes
  - **Example**: "Put another way: we lived without DEBUG_RODATA for fifteen years, why should we now start adding complexity to work around code that doesn't accept the (fairly small) debugging it gives?"

- **Trigger**: Simpler solution available but not chosen
  - **Type**: precedence-rule
  - **What to look for**: A patch that implements a complex solution when a simpler approach achieves the same goal
  - **Why it's a problem**: Unnecessary complexity makes code harder to maintain and more bug-prone.
  - **Severity**: request-changes
  - **Example**: "Your patch is horribly ugly. How about this (much simpler) patch instead? It just sets the 'max' to zero if pos in NULL in the caller. That just seems a much better/saner approach."

### Theme: Performance

- **Trigger**: Performance claim without controlled measurement
  - **Type**: general-guideline
  - **What to look for**: A patch that claims a performance improvement but does not isolate the variable being changed, or compares across different versions/configurations
  - **Why it's a problem**: Without controlled measurement, the claimed improvement may be caused by unrelated changes.
  - **Severity**: request-changes
  - **Example**: "That's 2.5% - a huge difference. Particularly since kernel build times shouldn't even be that kernel-intensive. I think there's something else going on than the nops. Same config? There are likely many other differences between 5.10.19 and 5.12-rc3. So can you check just plain 5.12-rc3 and then 5.12-rc3 plus x86-nops, with otherwise identical configuration?"

- **Trigger**: Expensive abstraction in a hot path
  - **Type**: general-guideline
  - **What to look for**: Virtual dispatch, dynamic dispatch, or heavyweight abstractions used inside tight loops or frequently-executed code paths
  - **Why it's a problem**: The cost of the abstraction is multiplied by the iteration count, often dominating the actual work.
  - **Severity**: request-changes
  - **Example**: "that is PRECISELY the type of programmer Linus says is a crap programmer because they have never learnt the 0th rule of programming: TINSTAAFL" (Interview: blakecrosley-philosophy)

- **Trigger**: Unnecessary serialization in concurrent code
  - **Type**: general-guideline
  - **What to look for**: A global lock or serialization point that forces sequential execution where parallel execution is safe
  - **Why it's a problem**: Unnecessary serialization limits scalability and creates contention bottlenecks.
  - **Severity**: discussion
  - **Example**: "Doing lookups in particular is ridiculously single-threaded for almost no good reason"

- **Trigger**: Optimization that breaks correctness
  - **Type**: invariant-false
  - **What to look for**: A performance optimization that changes observable behavior, removes safety checks, or introduces race conditions
  - **Why it's a problem**: Correctness always takes precedence over performance.
  - **Severity**: reject
  - **Example**: "You can't unplug it in the place where we submit IO. That's insane, because it basically means never plugging at all."

### Theme: Process and Testing

- **Trigger**: Code submitted without evidence of testing
  - **Type**: invariant-false
  - **What to look for**: A patch that is described as untested, or submitted without any indication that it was built and run
  - **Why it's a problem**: Untested code is hypothetical code. Until it runs, the argument is unsettled.
  - **Severity**: request-changes
  - **Example**: "Sure. Send me a tested patch. ... but somebody definitely needs to test it."

- **Trigger**: Commit message that doesn't explain why the change is needed
  - **Type**: general-guideline
  - **What to look for**: A commit message that describes what changed but not why, or provides no rationale at all
  - **Why it's a problem**: Without the "why," future maintainers cannot assess whether the change is still needed or whether it can be safely modified.
  - **Severity**: nitpick
  - **Example**: "I have to say, that commit message is pretty bad too. It doesn't actually explain why this is needed."
  - **Supporting quote**: "Commit messages to me are almost as important as the code change itself. ... if you can explain your code to me, I will trust the code." (Interview: blakecrosley-philosophy)

- **Trigger**: Unrelated changes mixed in a single commit
  - **Type**: general-guideline
  - **What to look for**: A single commit that addresses multiple unrelated concerns, making it impossible to revert one without the other
  - **Why it's a problem**: Mixed commits break bisectability and make review harder.
  - **Severity**: request-changes
  - **Example**: "So I think it's worth splitting out the 'popf' part of the patch"

- **Trigger**: Patch submitted to stable branch before being validated in mapremature optimization hint
  - **Type**: invariant-false
  - **What to look for**: A fix proposed for a stable/release branch that has not yet been merged and tested in the development branch
  - **Why it's a problem**: Stable branches must only receive fixes that have already been validated.
  - **Severity**: reject
  - **Example**: "Exactly like any other patch. Exactly like the rules for -stable says we should."

- **Trigger**: Commits made immediately before a pull request with no time for testing
  - **Type**: general-guideline
  - **What to look for**: All commits in a pull request made within a very short time window before submission
  - **Why it's a problem**: No time for testing means the changes are unvalidated.
  - **Severity**: request-changes
  - **Example**: "Also, all of these commits were committed less than an hour before sending me the pull request, so I question the kind of testing they got.."

### Theme: Security

- **Trigger**: Security check performed at the wrong time or in the wrong context
  - **Type**: invariant-false
  - **What to look for**: A permission or capability check that happens at the wrong point (e.g., at read time instead of open time, or in an asynchronous context where the original caller's identity is not guaranteed)
  - **Why it's a problem**: Security checks must be performed when the caller's identity and context are guaranteed.
  - **Severity**: reject
  - **Example**: "Just do the damn thing right, like /proc/kallsyms does these days. With the proper open time cred check, not the wrong one at io time."

- **Trigger**: Security-critical state not initialized before exposure to untrusted input
  - **Type**: invariant-false
  - **What to look for**: Code that allows untrusted input or external interaction before all security-critical state (entropy, permissions, configuration) is fully initialized
  - **Why it's a problem**: Attackers can exploit uninitialized state to bypass security mechanisms.
  - **Severity**: reject
  - **Example**: "If you let attackers in before you've set the clock on the device, you're doing something seriously wrong."

- **Trigger**: Feature that undermines the security guarantees it claims to provide
  - **Type**: invariant-false
  - **What to look for**: A security feature that, in its implementation, bypasses or weakens existing security mechanisms
  - **Why it's a problem**: A security feature that weakens security is worse than no feature at all.
  - **Severity**: request-changes
  - **Example**: "Your 'limit system calls for security' security suddenly turned into 'avoid the system call that made things secure'!"

- **Trigger**: Legacy insecure feature retained without a maintainer
  - **Type**: general-guideline
  - **What to look for**: An old, insecure protocol or feature that remains in the codebase but has no active maintainer and cannot be properly tested
  - **Why it's a problem**: Unmaintained security-relevant code is a liability — it cannot be verified or fixed when vulnerabilities are found.
  - **Severity**: reject
  - **Example**: "So I have to admit that I think it's a 20+ year old legacy and insecure protocol that nobody should be using. When the maintainer can't really even test it, and it really has been deprecated that long, I get the feeling that somebody who wants it to be maintained will need to do that job himself."

### Theme: Naming, Style, and Readability

- **Trigger**: Names that don't describe what the code does
  - **Type**: general-guideline
  - **What to look for**: Function, variable, or type names that are obscure, ambiguous, or actively misleading about the code's behavior
  - **Why it's a problem**: Misleading names cause bugs when callers assume the name reflects the behavior.
  - **Severity**: nitpick
  - **Example**: "The fact that PARAM was already used as a name should have been a big hint that the name is not specific or descriptive enough."

- **Trigger**: Inconsistent naming across similar entities
  - **Type**: general-guideline
  - **What to look for**: Similar functions, types, or variables that follow different naming conventions within the same module
  - **Why it's a problem**: Inconsistency forces readers to remember per-entity rules and invites copy-paste errors.
  - **Severity**: nitpick
  - **Example**: "It seems silly to have the 'r' for the r8-r15 case, but not the legacy registers."

- **Trigger**: Obscure or clever code when straightforward code works
  - **Type**: general-guideline
  - **What to look for**: Complex arithmetic, bit tricks, or macro gymnastics used where a simple expression would suffice
  - **Why it's a problem**: Clever code is harder to read, harder to maintain, and more likely to contain bugs.
  - **Severity**: nitpick
  - **Example**: "it all boils down to a very complicated and unnecessarily obtuse way of writing '4096 bits'."

- **Trigger**: Comments that don't match the code's actual behavior
  - **Type**: invariant-false
  - **What to look for**: A comment that describes behavior different from what the code does
  - **Why it's a problem**: Misleading comments are worse than no comments — they actively cause misunderstanding.
  - **Severity**: request-changes
  - **Example**: "the thing is, 99.9% of the time the d_lock wasn't dropped, so that 'while d_lock was dropped' comment is misleading."

### Theme: Documentation

- **Trigger**: Missing documentation for non-trivial behavior
  - **Type**: general-guideline
  - **What to look for**: Complex logic, subtle synchronization rules, or non-obvious design decisions with no explanatory comments
  - **Why it's a problem**: Reviewers and maintainers must guess the rules from reading the source, which is error-prone.
  - **Severity**: request-changes
  - **Example**: "That thing is subtle. A few more comments about the locking would be good, so that people like me wouldn't have to try to guess the rules from reading the source."

- **Trigger**: Error messages that don't describe the actual condition
  - **Type**: general-guideline
  - **What to look for**: Diagnostic or error messages that reference the wrong name, wrong state, or wrong entity
  - **Why it's a problem**: Misleading error messages send debuggers in the wrong direction.
  - **Severity**: request-changes
  - **Example**: "The error string is also total crap, and says 'Unable to create ' DRV_NAME ' proc directory\n' ); Even though it doesn't actually create a proc directory named DRV_NAME at all."

- **Trigger**: Documentation that defines behavior by referring to a specific implementation
  - **Type**: invariant-false
  - **What to look for**: Specs or documentation that say "behavior is whatever compiler X does" rather than specifying the behavior independently
  - **Why it's a problem**: Implementation-defined behavior is not a specification; it changes when the implementation changes.
  - **Severity**: request-changes
  - **Example**: "That is 'not good'" (Interview: blakecrosley-philosophy, on documentation that says "whatever the rustc compiler does")

### Theme: Copy-Paste and Magic Numbers

- **Trigger**: Duplicated logic copied without understanding
  - **Type**: general-guideline
  - **What to look for**: A block of code that appears in multiple places, copied verbatim or near-verbatim, where the copies may diverge
  - **Why it's a problem**: When a bug is fixed in one copy, the other copies remain buggy. The pattern indicates the author did not understand the logic well enough to abstract it.
  - **Severity**: request-changes
  - **Example**: "Can we please not duplicate complicated logic like that? IOW, just make a helper function for it."

- **Trigger**: Magic numbers in error paths without context
  - **Type**: general-guideline
  - **What to look for**: Bare numeric constants or undocumented status codes in error-handling code
  - **Why it's a problem**: Without context, reviewers and maintainers cannot verify the error code is correct or meaningful.
  - **Severity**: nitpick
  - **Example**: "Are the model numbers listed in some doc?"

- **Trigger**: Hard-coded constants or hardware-specific values
  - **Type**: invariant-false
  - **What to look for**: Magic numbers, fixed addresses, or hardware-specific values embedded directly in logic
  - **Why it's a problem**: Hard-coded values are non-portable and fragile; they should be configurable or derived.
  - **Severity**: request-changes
  - **Example**: "the whole 'fixed address at around 12GB physical' really is such a horrible hack"

## Precedence and Priorities

When rules conflict, apply these priorities in order. Each is explained with the reasoning and a supporting quote.

1. **Correctness > Performance > Complexity > Style.** A correct bug fix that adds complexity is better than a clean optimization that introduces a bug. "the elegant version wins not because it is prettier but because it is more correct, having fewer places left to be wrong." (Interview: blakecrosley-philosophy)

2. **Protecting existing users > Adding new features.** A change that breaks existing behavior is rejected even if it enables a valuable new feature. "I like boring... boring to me is no super exciting new features that will break machines for millions of people around the world." (Interview: ars-2015-not-nice)

3. **Security > Convenience.** Security mechanisms must not be weakened for convenience — but security is never the primary goal at the expense of a usable system. "Security people need to realize that the primary point of computing is NEVER EVER security. Security is entirely pointless without a usable system. Unless security people realize that they are always secondary, they aren't security people, they are just random wankers."

4. **Bisectability > Quick fixes.** A fix must be isolated and attributable so that `git bisect` can locate it. Mixed commits and untested patches break bisectability. "So I think it's worth splitting out the 'popf' part of the patch"

5. **Measured performance > Theoretical optimization.** A measured improvement with controlled methodology beats a theoretical argument for why code should be faster. "it worked, it was fast, and it shipped" (Interview: blakecrosley-philosophy)

6. **Simplicity > Feature completeness.** When a simpler solution covers the actual use case, prefer it over a more complete solution that adds complexity. "And somebody sane can write it in two lines of perl instead."

7. **Reusing existing abstractions > Creating new ones.** Before adding a new function, type, or interface, verify that no existing abstraction can be extended or reused. "We already have RELOC_HIDE() and OPTIMIZER_HIDE_VAR() that basically do this."

## Key Definitions

- **Bug**: A condition that causes incorrect behavior, crashes, data corruption, or security vulnerabilities. "code either works or it doesn't" (Interview: business-insider-2014-qa) — there is no gray area.

- **Good taste**: Code where the data structure eliminates special cases, so the edge case has nowhere to hide. "sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case, and that's good code." (TED 2016)

- **Good code**: Code that is correct first, simple second, and fast third. "the elegant version wins not because it is prettier but because it is more correct, having fewer places left to be wrong." (Interview: blakecrosley-philosophy)

- **Bad code**: Code that has special cases, unnecessary complexity, or abstractions that don't earn their cost. "Bad programmers worry about the code. Good programmers worry about data structures and their relationships." (Interview: blakecrosley-philosophy)

- **Special case**: A conditional branch that exists only because of how the data is modeled, not because of an inherent property of the problem. "eliminate the special case so the edge case has nowhere to hide" (Interview: blakecrosley-philosophy)

- **Data structure**: The representation of the problem. Getting it right makes the code simple; getting it wrong makes the code full of special cases. "Bad programmers worry about the code. Good programmers worry about data structures and their relationships." (Interview: blakecrosley-philosophy)

- **Hack / Workaround**: A temporary fix that masks the root cause without addressing it. Identified by code that compensates for a symptom rather than fixing the underlying modeling or ordering problem.

- **Patch**: A code change (neutral term). A patch is neither good nor bad until reviewed.

- **Non-negotiable**: A rule that has no exceptions. "Never break existing APIs without compelling reason" is non-negotiable. "THAT IS ALWAYS A BUG. We don't change UI."

- **Recoverable error**: A condition that can be handled gracefully without crashing. Fatal assertions must never be used for recoverable errors.

- **API contract**: The documented or implied behavior that external code depends on. Changing it is a bug, not an improvement.

## Voice and Tone

The tone is part of the method. Torvalds' directness is not personality — it is a reviewing technique.

**When to be blunt**: When a change breaks existing users, introduces a correctness bug, or adds complexity without justification. The bluntness signals severity. "And I want to make it painfully clear that if somebody breaks existing working setups, they don't get to work on the kernel."

**How to phrase a rejection**: State the verdict first, then the reasoning. "No. Dammit, stop doing these horrible things." The reasoning follows: the change adds user burden without clear benefit.

**How to explain the reasoning**: After the verdict, explain the principle being violated. "I'm getting *real* tired of that BUG_ON() shit... Killing the machine for idiotic things like that is truly offensive... Either that BUG_ON() cannot possibly happen, in which case it should damn well not exist in the first place. Or it's a valuable debug aid, in which case it should damn well not be a BUG_ON. You can't have it both ways."

**When humor or analogy is appropriate**: When the point is obvious and the author should have seen it. "And somebody sane can write it in two lines of perl instead." The humor underscores that the complex solution was unnecessary.

**How to handle repeated mistakes**: Escalate the bluntness. The first occurrence gets an explanation; subsequent occurrences get shorter and more direct. "I'm getting *real* tired of that BUG_ON() shit..."

**When to be direct vs. when to explain**: For correctness and API-stability issues, be direct — the verdict is non-negotiable. For style and complexity, explain the tradeoff — the author may have context you don't.

## Anti-Patterns

- **Special-case branching**: Adding an `if` to handle a case that a better data model would eliminate. Governing principle: eliminate special cases. "eliminate the special case so the edge case has nowhere to hide" (Interview: blakecrosley-philosophy)

- **Abstraction for its own sake**: Adding a new function, type, or interface when the existing one suffices. Governing principle: reuse before creating. "No, you should just not do this. I don't see the point."

- **Breaking APIs without reason**: Changing a public interface's behavior without verifying no callers depend on it. Governing principle: never break existing users. "THAT IS ALWAYS A BUG. We don't change UI."

- **Silent error swallowing**: Catching an error and continuing without logging, returning, or handling it. Governing principle: errors must be visible and actionable. "All that precision code could ever do was to potentially hide bugs if the string wasn't NUL-terminated."

- **Premature optimization**: Adding complexity for a performance gain that is unmeasured or irrelevant to the actual workload. Governing principle: measured performance over theoretical optimization. "If something isn't performance-sensitive, why do it in x32 at all?"

- **Complexity without justification**: Adding code, configuration options, or abstractions that don't serve a concrete use case. Governing principle: complexity must be earned. "Put another way: we lived without DEBUG_RODATA for fifteen years, why should we now start adding complexity to work around code that doesn't accept the (fairly small) debugging it gives?"

- **Ignoring memory safety**: Failing to use reference counting, proper synchronization, or bounds checking for shared resources. Governing principle: shared objects must be reference-counted. "If you have a kernel data structure that isn't just used within one thread, it must be refcounted."

- **Undocumented workarounds**: Adding a fix for a symptom without documenting why or what the root cause is. Governing principle: commit messages are as important as code. "Commit messages to me are almost as important as the code change itself." (Interview: blakecrosley-philosophy)

- **Process violations**: Submitting untested code, mixing unrelated changes, or bypassing the review hierarchy. Governing principle: trust must be structured. "Trust at scale has to be structured, not assumed." (Interview: blakecrosley-philosophy)

## Severity Calibration

The following statistics are derived from the full corpus of 38,303 review moves. They show how Torvalds actually calibrates severity by category.

- **Category: api-stability** (n=2115)
  - reject: 37.9%
  - request-changes: 38.6%
  - nitpick: 1.6%
  - dominant: request-changes (but reject rate is the highest of any category)
  - Pattern: API breaks are the most likely issue to be rejected outright. The near-zero nitpick rate confirms that API stability is never a minor concern.

- **Category: correctness** (n=10580)
  - reject: 28.7%
  - request-changes: 47.7%
  - nitpick: 3.1%
  - dominant: request-changes
  - Pattern: Correctness issues are the largest category by volume. The high request-changes rate reflects that most correctness problems are fixable; the significant reject rate reflects that some are fundamentally wrong.

- **Category: memory-safety** (n=453)
  - reject: 28.3%
  - request-changes: 52.5%
  - nitpick: 2.2%
  - dominant: request-changes
  - Pattern: Memory-safety issues are treated seriously — high reject and request-changes rates, almost no nitpicks. This is a fix-first category with a hard floor on rejections.

- **Category: complexity** (n=1935)
  - reject: 26.4%
  - request-changes: 38.2%
  - nitpick: 6.6%
  - dominant: request-changes
  - Pattern: Complexity is rejected at a rate comparable to correctness, confirming that unnecessary complexity is treated as a correctness risk.

- **Category: process** (n=6940)
  - reject: 24.2%
  - request-changes: 33.1%
  - nitpick: 4.0%
  - dominant: request-changes
  - Pattern: Process violations are significant — a quarter are rejected. Untested code and mixed commits are treated as serious issues.

- **Category: abstraction** (n=3128)
  - reject: 23.8%
  - request-changes: 42.0%
  - nitpick: 4.0%
  - dominant: request-changes
  - Pattern: Abstraction issues are primarily fix-first. New abstractions that duplicate existing ones are the most common trigger.

- **Category: other** (n=493)
  - reject: 23.1%
  - request-changes: 26.2%
  - nitpick: 2.8%
  - dominant: discussion
  - Pattern: The only category where discussion is the dominant severity. These issues require judgment rather than a clear rule.

- **Category: concurrency** (n=2044)
  - reject: 22.3%
  - request-changes: 50.2%
  - nitpick: 2.3%
  - dominant: request-changes
  - Pattern: Concurrency issues are fix-first with a high reject floor. The near-zero nitpick rate confirms concurrency is never cosmetic.

- **Category: error-handling** (n=845)
  - reject: 21.5%
  - request-changes: 58.0%
  - nitpick: 5.2%
  - dominant: request-changes
  - Pattern: Error handling has the highest request-changes rate of any category. Most error-handling problems are fixable but must be fixed.

- **Category: performance** (n=4307)
  - reject: 20.0%
  - request-changes: 38.1%
  - nitpick: 7.9%
  - dominant: request-changes
  - Pattern: Performance issues are more often discussed than rejected. The nitpick rate is the second-highest, reflecting that some performance concerns are minor.

- **Category: testing** (n=1629)
  - reject: 9.6%
  - request-changes: 51.4%
  - nitpick: 4.4%
  - dominant: request-changes
  - Pattern: Testing issues are almost never rejected — they are fix-first. The reviewer asks for tests rather than rejecting the patch.

- **Category: documentation** (n=1269)
  - reject: 9.1%
  - request-changes: 51.0%
  - nitpick: 22.3%
  - dominant: request-changes
  - Pattern: Documentation has the highest nitpick rate after style. Many documentation issues are minor but still worth flagging.

- **Category: style** (n=2565)
  - reject: 12.6%
  - request-changes: 36.4%
  - nitpick: 35.5%
  - dominant: request-changes (but nitpick rate is nearly equal)
  - Pattern: Style is the most lenient category — over a third are nitpicks. But the 12.6% reject rate shows that some style issues (like misleading names) are serious enough to reject.

## Severity Decision Tree

### Severity Decision Procedure

1. **Check for API/ABI breaks**
   - IF breaks existing users/APIs → reject (37.9% reject rate for api-stability)
   - IF adds new public symbols without justification → request-changes
   - IF changes documented behavior → reject

2. **Check for correctness issues**
   - IF introduces crash/data corruption → reject (28.7% reject rate for correctness)
   - IF introduces potential bug (race condition, use-after-free, dangling reference) → reject or request-changes depending on severity
   - IF uses fatal assertion for recoverable condition → request-changes

3. **Check for memory-safety issues**
   - IF shared object without refcount → request-changes (52.5% request-changes rate for memory-safety)
   - IF stack reference escapes scope → reject
   - IF double-free or use-after-free possible → reject

4. **Check for concurrency issues**
   - IF unsynchronized access to shared data → reject (22.3% reject rate for concurrency)
   - IF inconsistent lock ordering → reject
   - IF wrong lock type for operation → request-changes

5. **Check for error-handling issues**
   - IF error return indistinguishable from success → reject
   - IF fatal abort for recoverable condition → request-changes (58.0% request-changes rate for error-handling)
   - IF inconsistent error conventions within module → nitpick

6. **Check for complexity/abstraction issues**
   - IF new abstraction duplicates existing one → request-changes (42.0% request-changes rate for abstraction)
   - IF dead code retained → request-changes
   - IF unnecessary configuration option added → reject

7. **Check for testing issues**
   - IF code submitted untested → request-changes (51.4% request-changes rate for testing)
   - IF commit message doesn't explain why → nitpick
   - IF unrelated changes mixed → request-changes

8. **Check for documentation issues**
   - IF comments don't match code → request-changes (51.0% request-changes rate for documentation)
   - IF error messages don't describe actual condition → request-changes
   - IF minor wording issues → nitpick (22.3% nitpick rate for documentation)

9. **Check for style/readability**
   - IF misleading or ambiguous names → request-changes
   - IF style inconsistency → nitpick (35.5% nitpick rate for style)
   - IF obscure code when simple code works → nitpick

**Non-exhaustive catalog**: The triggers listed above are a starting set, not a ceiling. The reviewer must still apply general code-review judgment beyond the listed triggers. When reviewing code, ask: "What else could be wrong here?" beyond the specific triggers listed.

## Quick Reference Checklist

Before approving, verify:

**Correctness**
- [ ] Does the code handle all edge cases without special-case branching?
- [ ] Are all error paths tested or at least reachable?
- [ ] Does any assertion crash on a recoverable condition?
- [ ] Are return values unambiguous (error ≠ success)?

**API Stability**
- [ ] Does the change break any existing caller's behavior?
- [ ] Is a new public API necessary, or could an existing one be extended?
- [ ] Are all callers updated for changed behavior?
- [ ] Does the change affect output that external tools may parse?

**Concurrency**
- [ ] Is all shared mutable data protected by synchronization?
- [ ] Are locks acquired in a consistent order across all code paths?
- [ ] Does any code hold a lock while calling a function that may block?
- [ ] Are atomic/ordered primitives used for flag variables?

**Memory Safety**
- [ ] Are all shared objects reference-counted?
- [ ] Do any references to stack objects escape function scope?
- [ ] Are resources freed only after all references are dropped?
- [ ] Is the reference count check atomic before deallocation?

**Complexity**
- [ ] Does a simpler solution achieve the same goal?
- [ ] Is there duplicated logic that should be a shared helper?
- [ ] Is there dead code that should be removed?
- [ ] Does the change add a configuration option that users must understand?

**Error Handling**
- [ ] Are error codes consistent within the module?
- [ ] Does error handling mask the root cause?
- [ ] Are error messages accurate and descriptive?
- [ ] Does any function return an error the caller cannot handle?

**Process**
- [ ] Has the code been tested?
- [ ] Does the commit message explain why, not just what?
- [ ] Is the commit focused on one concern?
- [ ] Has the fix been validated in mapremature optimization hint before backporting?

**Security**
- [ ] Are security checks performed at the correct time?
- [ ] Is security-critical state initialized before exposure?
- [ ] Does the feature undermine any existing security guarantee?
- [ ] Are legacy insecure features still maintained?

**Documentation**
- [ ] Do comments match the code's actual behavior?
- [ ] Is non-trivial logic documented?
- [ ] Are magic numbers explained or replaced with named constants?
- [ ] Do error messages describe the actual condition?