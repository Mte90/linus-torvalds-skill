---
name: linus-torvalds-skill
description: "A code review method distilled from 38,293 real code review moves by Linus Torvalds, teaching reviewers to prioritize correctness, simplicity, and existing users above all else — in any language, for any project."
metadata:
  author: "torvalds-skill pipeline"
  version: "1.0.0"
  tags:
    - code-review
    - reviewer-method
    - torvalds
---

# Linus Torvalds Review Method

> This skill distills the reviewing method of Linus Torvalds from a corpus of 38,293 code review moves extracted from real reviews on the Linux kernel mailing list. The method is language- and project-agnostic: every principle, trigger, and decision rule has been generalized from its original C/kernel context to apply to any programming language and any codebase. The quotes are preserved verbatim and illustrate the voice and tone; the triggers and principles contain no language-specific terms.

## Reviewer Mindset

**1. Correctness is non-negotiable.** Code that crashes, corrupts data, or produces wrong results is rejected regardless of any other merit. A performance optimization that introduces a correctness bug is worse than no optimization at all.

> "There is *no* excuse for killing the kernel for things like this (and in certain setups, BUG_ON() *will* cause the machine to be rebooted). None. It's completely inexcusable."

**2. Existing users come first.** Breaking working code — even for a "better" design — is the worst kind of change. If someone depends on a behavior, changing it requires overwhelming justification.

> "If you as a kernel developer cannot make a choice, and argue strongly for _why_ that choice is the right one to export to user space, then we do not change existing behavior, since clearly you don't really have a good reason for the change."

**3. Simplicity beats cleverness.** Complex code breeds bugs. When faced with a simple correct solution and a complex optimized one, the simple one wins unless the complex one has measured, significant benefits.

> "So clever features and extra complexity and smart things that can be done with it is often not all that useful"

**4. Evidence over theory.** Claims about performance, bugs, or behavior must be backed by concrete evidence — measurements, test cases, reproducible scenarios. Theoretical arguments are starting points, not conclusions.

> "Honestly, I've never seen anything like that in any kernel profiles. Compared to the problems I _do_ see (which is usually the obvious cache misses, and locking), it must either be in the noise or it's some problem specific to whatever CPU you are doing performance work on?"

**5. Fix the root cause.** Workarounds that mask symptoms are rejected. If there is a bug, fix the bug — don't add a workaround that hides it.

> "This patch seems to just hide the _real_ bug, which is that the exception table gets confused. How about just fixing the exception table instead?"

**6. Minimal interfaces.** Public APIs should be as small as possible. Every new parameter, flag, variant, or entry point is permanent maintenance burden. Add only what is demonstrably needed.

> "I'd almost prefer if we *only* did 'scoped_with_creds()' and didn't have this version at all. ... I just suspect we could narrow down the new interface a bit more."

**7. Explain the "why."** A change without a clear explanation of its purpose and rationale is incomplete. Reviewers and future maintainers need to understand not just what changed, but why.

> "Ask yourself: is that commit doing anything useful? Does the commit message explain what it is doing, and why you are doing it?"

## Review Triggers

### Theme 1: Breaking Existing APIs and Users

**Trigger 1.1 — Changing long-standing public interface semantics**
- **Type**: invariant-false
- **What to look for**: A change that alters the documented or de-facto behavior of a public API that external code depends on, without a compelling, well-argued reason.
- **Why it's a problem**: Existing users will break silently. Changes to long-standing semantics create maintenance and backporting nightmares.
- **Severity**: reject
- **Example**: "Please don't do this. This is a maintenance nightmare, and changes pretty much three decades of semantics, and will cause *very* subtle backporting issues if somebody happens to rely on the old / new behavior."

**Trigger 1.2 — Removing existing public output or functionality**
- **Type**: invariant-false
- **What to look for**: A patch that removes user-visible output, a configuration option, or a feature that people depend on, without strong justification.
- **Why it's a problem**: People notice. Removing functionality breaks workflows that the developer may not be aware of.
- **Severity**: reject
- **Example**: "What is *not* valid is clearly: removing the bogomips line. You can try again in a couple of years. Maybe nobody will notice. But people *did* notice, and that commit got reverted. End of story, anybody who argues for removal is simply wrong."

**Trigger 1.3 — Adding unnecessary API variants or wrappers**
- **Type**: general-guideline
- **What to look for**: A new version of an existing function (e.g., with a "2" suffix or a new flag) created to avoid updating existing callers, when fixing the callers directly would be simpler.
- **Why it's a problem**: Every variant is permanent maintenance burden. Fixing callers is usually a smaller, cleaner patch.
- **Severity**: request-changes
- **Example**: "Why did you do that butt-ugly '__invalidate_device2()'? ... it would have made for a smaller and cleaner patch to just fix them all, rather than change the calling convention, create that ugly '2' function, and add the wrapper function."

**Trigger 1.4 — Exposing internal-only symbols as public API**
- **Type**: invariant-false
- **What to look for**: A function or symbol that follows naming conventions indicating it is internal (e.g., double-underscore prefix) being promoted to a public interface.
- **Why it's a problem**: Naming conventions signal intent. Breaking them confuses users about what is stable vs. internal.
- **Severity**: reject
- **Example**: "The whole point of two underscores is to say 'don't use this - it's an internal implementation'. So then making a new interface with two underscores ... is fundamentally bogus."

**Trigger 1.5 — Inconsistent return conventions across similar APIs**
- **Type**: general-guideline
- **What to look for**: Functions that serve similar purposes but use different return conventions (e.g., one returns success/failure, another returns bytes processed, another returns a boolean).
- **Why it's a problem**: Inconsistency forces callers to remember which convention each function uses, leading to bugs.
- **Severity**: discussion
- **Example**: "If there is any inconsistency, maybe we should make _more_ cases use that 'how many bytes/pages not copied' logic, but in a lot of cases you don't actually need the ternary decision value."

**Trigger 1.6 — Adding a new public API when a standard one exists**
- **Type**: precedence-rule
- **What to look for**: A proposal for a new interface when an existing standard or widely-used interface already covers the use case.
- **Why it's a problem**: New interfaces are permanent maintenance burden. Standard interfaces are already understood and tested.
- **Severity**: reject
- **Example**: "If a standard interface exists, we should just use it. ... I'd much rather have simple cheap interfaces than anything else."

### Theme 2: Crashing on Recoverable Conditions

**Trigger 2.1 — Fatal assertion used for a recoverable error**
- **Type**: invariant-false
- **What to look for**: A fatal assertion (panic, abort, crash) used in a code path that handles an error condition that could be recovered from gracefully.
- **Why it's a problem**: Crashing the system for a recoverable condition is inexcusable. It turns a minor issue into a catastrophic failure.
- **Severity**: reject
- **Example**: "What is the point of that BUG_ON()? Hell, people add too many of those things. There is *no* excuse for killing the kernel for things like this"

**Trigger 2.2 — Turning a recoverable condition into a hard error**
- **Type**: invariant-false
- **What to look for**: Code that escalates a condition that could be handled gracefully into a fatal or blocking error.
- **Why it's a problem**: Hard errors hurt everybody. Recoverable conditions should remain recoverable.
- **Severity**: reject
- **Example**: "anybody who makes a hard error out of something that is recoverable is a total moron. ... It hurts everybody. Don't do it."

**Trigger 2.3 — Fail-fast mechanisms in production code paths**
- **Type**: general-guideline
- **What to look for**: Crash-on-failure mechanisms in code paths that run in production, rather than being limited to development/debug builds.
- **Why it's a problem**: Developers may want fail-fast during development, but users do not want crashes.
- **Severity**: discussion
- **Example**: "Forcing crashes can be very useful for the actual developer that is doing development on the code itself, kind of a 'fail fast, fail hard'. But users (or developers that are developing something _else_ than XFS ;) don't tend to like it."

### Theme 3: Hiding Bugs with Workarounds

**Trigger 3.1 — Workaround that masks a root cause**
- **Type**: invariant-false
- **What to look for**: A change that works around a symptom (e.g., adding a no-premature optimization hint attribute, adding a special case) without addressing the underlying bug.
- **Why it's a problem**: The bug remains. The workaround may itself introduce subtle issues. Future maintainers will be confused.
- **Severity**: request-changes
- **Example**: "This patch seems to just hide the _real_ bug, which is that the exception table gets confused. How about just fixing the exception table instead?"

**Trigger 3.2 — Adding guard checks to compensate for a flawed design**
- **Type**: invariant-false
- **What to look for**: Ad-hoc safety checks added to prevent a problematic behavior, rather than fixing the design that allows the behavior.
- **Why it's a problem**: The guards prove the design is wrong. Adding more guards doesn't fix it.
- **Severity**: reject
- **Example**: "Those safety guards literally make my argument for me: sending a signal to whoever randomly triggered a warning is simply _wrong_."

**Trigger 3.3 — Accepting a "temporary hack" without a plan to fix it**
- **Type**: general-guideline
- **What to look for**: A workaround explicitly labeled as temporary, without a clear path to the proper fix.
- **Why it's a problem**: Temporary hacks become permanent. Accept them only for release stability, not as long-term solutions.
- **Severity**: discussion
- **Example**: "I think the (second) patch I sent out is an acceptable hack in the presence of the current locking, but as I said, I'm not exactly happy about it, because I do think the locking is broken."

### Theme 4: Unnecessary Complexity

**Trigger 4.1 — Special-case handling where uniform logic suffices**
- **Type**: general-guideline
- **What to look for**: Code that branches on specific cases (e.g., different types, different callers) when a single uniform code path would handle all cases correctly.
- **Why it's a problem**: Special cases lead to subtle bugs because only one path gets tested. Uniform logic is simpler and more robust.
- **Severity**: request-changes
- **Example**: "So I'd actually prefer to just simplify the logic entirely, and say 'PF_USER_WORKER tasks do not participate in core dumps, end of story'. ... let's do the thing for both io_uring and vhost, and not split those two cases up."

**Trigger 4.2 — Adding complexity for rare, non-essential features**
- **Type**: invariant-false
- **What to look for**: New logic added to critical, shared code paths to support a rare use case that could be handled externally.
- **Why it's a problem**: Rare features burden all users of the common path. Complexity in critical code breeds bugs.
- **Severity**: reject
- **Example**: "Asking the kernel to do complex things in critical core functions for something that is very very rare and irrelevant to most people, and that can and should just be done in user space for the people who care is the wrong approach."

**Trigger 4.3 — Conditional behavior in shared code based on caller-specific flags**
- **Type**: invariant-false
- **What to look for**: Shared/library code that branches based on a caller-specific flag or option, causing different behavior for different callers.
- **Why it's a problem**: Even if 90% of code is shared, the branching leads to subtle bugs because only one path is tested.
- **Severity**: request-changes
- **Example**: "The if (sb->option.extent) .. do one thing .. else .. do another .. kind of thing is exactly what leads to problems later. Even if it allows sharing of 90% of the code ... it leads to problems exactly because of things that end up not quite working because people only tested one code-path"

**Trigger 4.4 — Unnecessary parameters or code paths**
- **Type**: general-guideline
- **What to look for**: A function parameter that is always one value except for a single special case, or a code path that exists only for one caller.
- **Why it's a problem**: Dead parameters and paths add interface complexity without value. Remove them.
- **Severity**: request-changes
- **Example**: "Could we please just remove that whole 'was_async' case entirely, and just make the cres->ops->read() path just do a workqueue (which seems to be what the true case does anyway)?"

**Trigger 4.5 — Adding unnecessary states to a system**
- **Type**: invariant-false
- **What to look for**: A new state variable, flag, or mode added when existing behavior already covers the case.
- **Why it's a problem**: More states mean more combinations to test and more ways to break.
- **Severity**: reject
- **Example**: "SIGKILL _already_ doesn't actually wake up a ptraced task. It just informs the tracer, last I looked. So a new state should be pretty simple, and I really think it would be the right way to go."

### Theme 5: Performance Without Evidence

**Trigger 5.1 — Performance claim without measurement**
- **Type**: general-guideline
- **What to look for**: A claim that something is a performance problem or improvement, without concrete, reproducible measurements.
- **Why it's a problem**: Without measurement, you don't know if the problem is real or in the noise. Optimizing without data wastes effort and may degrade other cases.
- **Severity**: discussion
- **Example**: "Honestly, I've never seen anything like that in any kernel profiles. Compared to the problems I _do_ see ... it must either be in the noise or it's some problem specific to whatever CPU you are doing performance work on?"

**Trigger 5.2 — Micro-benchmark used to justify a change**
- **Type**: general-guideline
- **What to look for**: A performance change justified by a micro-benchmark that doesn't represent real workloads.
- **Why it's a problem**: Micro-benchmarks run hot-cache and don't show effects that matter in production. Require macro-benchmarks.
- **Severity**: request-changes
- **Example**: "But that's something that really needs macro-benchmarks - exactly because microbenchmarks don't show those effects since they are always basically hot-cache."

**Trigger 5.3 — Optimization that degrades other cases**
- **Type**: invariant-false
- **What to look for**: An optimization that improves one specific scenario while penalizing others, especially when the improved scenario is a corner case.
- **Why it's a problem**: Artificial improvements in one case hide real regressions in others.
- **Severity**: reject
- **Example**: "I really think that the 'open twice' is wrong. It will look artificially good in this 'does not exist' case, but it will penalize other cases, and it just hides this issue."

**Trigger 5.4 — Adding complexity for marginal performance gain**
- **Type**: precedence-rule
- **What to look for**: A change that adds significant complexity (new abstractions, configuration options, code paths) for a small or theoretical performance improvement.
- **Why it's a problem**: The complexity cost outweighs the performance benefit. Simplicity and safety win over tiny speedups.
- **Severity**: nitpick
- **Example**: "So you really don't win all that much. At a minimum, you always have to convert all the writers to use RCU ... what you end up with is that you can avoid converting _some_ of the readers."

### Theme 6: Error Handling Violations

**Trigger 6.1 — Success return value used to indicate failure**
- **Type**: invariant-false
- **What to look for**: A function that returns a success value (e.g., 0, true, null) when an error or failure occurs.
- **Why it's a problem**: Callers cannot distinguish success from failure. The error is silently swallowed.
- **Severity**: reject
- **Example**: "This makes no sense. A write() returning 0 means 'Disk full'. It's most definitely an error, and a failure. ... I do not at all understand the sentence 'When user_events are disabled, its write operation should return zero' as an 'explanation' for this"

**Trigger 6.2 — Missing cleanup on error paths**
- **Type**: invariant-true
- **What to look for**: A function that returns an error without releasing resources it acquired (memory, locks, file handles).
- **Why it's a problem**: Resource leaks on error paths accumulate and eventually cause failures.
- **Severity**: reject
- **Example**: "So if a driver returns an error code, we should assume they screwed up potentially half-way and clean up. We should *not* assume that we don't need to."

**Trigger 6.3 — Modifying observable state on error paths**
- **Type**: invariant-false
- **What to look for**: Code that updates state (e.g., file position, counters, flags) even when the operation fails and returns an error.
- **Why it's a problem**: Callers expect state to be unchanged when an operation fails. Modifying it on error causes subtle bugs.
- **Severity**: discussion
- **Example**: "Not updating f_pos on errors sounds like the right thing to do to me, and if it also ends up fixing some nasty issues with hpfs and potentially other cases, I'd say 'go for it'."

**Trigger 6.4 — Mixing error codes with boolean success values**
- **Type**: general-guideline
- **What to look for**: Code that uses both error codes (negative = error, 0 = success) and boolean values (true/false) for success indication in the same context.
- **Why it's a problem**: The mixing is confusing. Callers don't know which convention to check.
- **Severity**: nitpick
- **Example**: "some of the patches in the middle were confusing because of how 0/ERROR was mixing with a success true/false thing, but the end result seems to be a whole lot more sensible."

**Trigger 6.5 — Unnecessary error handling that adds no value**
- **Type**: general-guideline
- **What to look for**: Error handling code for a condition that is not fatal and where the handling itself may be wrong or pointless.
- **Why it's a problem**: Unnecessary error handling adds complexity and may introduce new bugs. When the handling is wrong, it's doubly suspect.
- **Severity**: discussion
- **Example**: "At some point error handling doesn't actually add value, as long as the error itself isn't fatal. And when the error handling itself is wrong, it's doubly suspect."

### Theme 7: Concurrency and Synchronization

**Trigger 7.1 — Relying on source-level ordering for memory consistency**
- **Type**: invariant-false
- **What to look for**: Code that assumes memory operations will be visible to other threads in source order, without explicit synchronization primitives.
- **Why it's a problem**: Different architectures reorder memory operations differently. Source order does not guarantee execution order.
- **Severity**: reject
- **Example**: "If the coder doesn't lock his data structures, it doesn't matter _what_ order we execute the list modifications in - different architectures will do different thing with inter-CPU memory ordering, and trying to order memory accesses on a source level is futile."

**Trigger 7.2 — Heavyweight lock for a single primitive value**
- **Type**: invariant-false
- **What to look for**: A full lock (lock primitive, spinlock) used to protect access to a single variable or flag, when atomic operations would suffice.
- **Why it's a problem**: The lock adds no serialization that atomic operations wouldn't provide. It wastes CPU and confuses readers about what the locking means.
- **Severity**: reject
- **Example**: "Using a lock to serialize a single write is completely bogus. It adds zero serialization that a WRITE_ONCE/READ_ONCE pair doesn't add. At best it's just wasted CPU time. At worst, it confuses people about what the locking means and results in bugs down the line."

**Trigger 7.3 — Subtle ordering arguments instead of obvious primitives**
- **Type**: general-guideline
- **What to look for**: Code that relies on complex reasoning about memory ordering to prove correctness, when a more obvious synchronization primitive would make the intent clear.
- **Why it's a problem**: Subtle arguments are fragile. The next maintainer won't understand them. Use primitives that make the intent obvious.
- **Severity**: request-changes
- **Example**: "But if we want to have the code be obvious, and not have to refer to those kinds of arguments, I think smp_load_acquire() is the only actual 'obvious' thing to use."

**Trigger 7.4 — Holding locks longer than necessary**
- **Type**: general-guideline
- **What to look for**: A lock held across operations that don't require it, or acquired earlier than necessary.
- **Why it's a problem**: Unnecessary serialization reduces parallelism and can cause contention.
- **Severity**: discussion
- **Example**: "The only thing I don't love about the batching is that we now do hold the lock over some situations where we _could_ have allowed concurrency"

**Trigger 7.5 — Concurrency change that can yield incorrect results under some interleaving**
- **Type**: invariant-false
- **What to look for**: A concurrency change that is correct under most interleavings but can produce incorrect results under a specific, possible sequence of operations.
- **Why it's a problem**: If any interleaving produces wrong results, the code is broken. Correctness must hold for all possible orderings.
- **Severity**: reject
- **Example**: "Look, let's write 5.000950, 6.000150 and 7.000950 ... and look how the reader is happy, because it got the same nanoseconds twice. But the reader thinks it had a time of 6.000950, and AT NO POINT was that actually a valid time."

### Theme 8: Memory Safety Violations

**Trigger 8.1 — Stack reference escaping function scope**
- **Type**: invariant-false
- **What to look for**: A pointer or reference to a stack-allocated object stored in a data structure, returned, or passed to a callback that may outlive the current function call.
- **Why it's a problem**: After the function returns, the stack memory is reclaimed. The dangling pointer leads to use-after-free.
- **Severity**: reject
- **Example**: "That's unacceptably buggy crap. rpc_wait_for_completion_task() will happily exit on a deadly signal even if the rpc hasn't been completed, so now you'll have a stale pointer to a stack that has been freed."

**Trigger 8.2 — Using an object after its lifetime ends**
- **Type**: invariant-false
- **What to look for**: Code that accesses an object after it has been freed, released, or invalidated, even if the access appears safe.
- **Why it's a problem**: Use-after-free is undefined behavior and a common source of security vulnerabilities.
- **Severity**: request-changes
- **Example**: "So the fix may be as simple as just doing ... because the 'mapped_device' pointer hopefully is still valid, it's just 'tio' that has been freed."

**Trigger 8.3 — Marking uninitialized memory as executable**
- **Type**: invariant-false
- **What to look for**: Memory allocated but not initialized before being marked as executable or having executable permissions granted.
- **Why it's a problem**: Uninitialized memory contains random data. Executing it is a critical security vulnerability.
- **Severity**: reject
- **Example**: "Unless I mis-read it, it does a 'module_alloc()' to allocate the vmap area, and then just marks it executable without having even initialized the pages. ... It's random data that is now executable."

**Trigger 8.4 — Freeing an object while live references exist**
- **Type**: invariant-false
- **What to look for**: An object being deallocated while other data structures still hold pointers to it.
- **Why it's a problem**: The remaining references become dangling pointers. Any access through them is use-after-free.
- **Severity**: request-changes
- **Example**: "So I just think it is bad form to potentially free something before we get rid of all pointers to it. ... good code shouldn't do things like that"

**Trigger 8.5 — Exposing stale or freed data to external callers**
- **Type**: invariant-false
- **What to look for**: Data returned to a caller that may have come from a resource that was freed and potentially reused.
- **Why it's a problem**: The caller may receive data from a different, security-sensitive context. This is an information leak.
- **Severity**: reject
- **Example**: "and this is fatal. We might have optimistically copied things that are now security-sensitive and even if we return a short read - or overwrite it - layer, user space should never have seen that data."

### Theme 9: Abstraction Design

**Trigger 9.1 — Creating new abstractions when existing ones suffice**
- **Type**: precedence-rule
- **What to look for**: A new subsystem, mechanism, or abstraction layer proposed when an existing, proven one meets the requirements.
- **Why it's a problem**: New abstractions are untested and add maintenance burden. Existing ones have survived real-world use.
- **Severity**: discussion
- **Example**: "This is why I like pipes. You can use them today. They are simple, and extensible, and you don't need to come up with a new subsystem and some untested ad-hoc thing that nobody has actually used."

**Trigger 9.2 — Abstraction that hides performance costs**
- **Type**: general-guideline
- **What to look for**: An abstraction layer that wraps expensive operations behind a simple interface, making the cost invisible to callers.
- **Why it's a problem**: When costs are hidden, callers can't make informed decisions. Performance problems become hard to trace.
- **Severity**: nitpick
- **Example**: "Adding these kinds of 'abstraction layers' is something that people are taught is good, but I personally tend to think that it makes it less obvious at the code level what the 'costs' are."

**Trigger 9.3 — Unnecessary API surface that burdens many callers**
- **Type**: invariant-false
- **What to look for**: A new interface method, flag, or parameter added to a shared layer that most callers don't need and must work around.
- **Why it's a problem**: Every caller pays the complexity cost. Those who don't need the feature are burdened by it.
- **Severity**: nitpick
- **Example**: "One adds a VFS-layer filesystem method that most filesystems end up not really needing ... and other filesystems end up then having hacks with ('oh, I don't need to take this lock because it was already taken by the caller')"

**Trigger 9.4 — Opaque types that cause confusion**
- **Type**: invariant-false
- **What to look for**: A "fake" or opaque type definition used to hide the real type, when code or tooling depends on the actual type.
- **Why it's a problem**: Opaque types break type-based tooling, confuse developers, and provide no real encapsulation benefit.
- **Severity**: reject
- **Example**: "Ugh, please no. This is going to be very confusing, and it's going to mess with anything that does things based on type (eg traditionally module signatures etc)."

**Trigger 9.5 — Encapsulate configuration-specific logic in helpers**
- **Type**: general-guideline
- **What to look for**: Repeated conditional blocks checking the same configuration flag scattered through code, instead of being encapsulated in a named helper.
- **Why it's a problem**: Repeated conditionals are hard to read and maintain. A named helper makes the intent self-documenting.
- **Severity**: request-changes
- **Example**: "Can we please just introduce helper functions? ... that pattern could be much more naturally expressed as preempt_disable_under_spinlock(); ... which would make the code really explain what is going on."

### Theme 10: Process and Testing

**Trigger 10.1 — Non-bisectable change**
- **Type**: invariant-false
- **What to look for**: A change that, when applied at an intermediate commit, would not compile or would break the build, making git bisect unreliable.
- **Why it's a problem**: Bisectability is essential for finding regressions. Non-bisectable changes make debugging impossible.
- **Severity**: reject
- **Example**: "While I could easily just remove the duplicated lines in my merge, that would make things non-bisectable, so I unpulled this instead."

**Trigger 10.2 — Mixing new features with bug fixes**
- **Type**: invariant-false
- **What to look for**: A patch series labeled as "fixes" that includes new functionality, new error handling, or new development.
- **Why it's a problem**: Bug fixes need to be backported. New features don't. Mixing them makes it impossible to know what is safe to backport.
- **Severity**: reject
- **Example**: "They look like completely new error handling and recovery code. Very much new development, not fixes. ... In other words: no. This is not a 'fix'. This is fundamental new development"

**Trigger 10.3 — Untested code**
- **Type**: invariant-false
- **What to look for**: Code changes submitted without evidence of testing, especially for low-level or critical code paths.
- **Why it's a problem**: Unmerged code that compiles is not tested code. Bugs in untested code reach production.
- **Severity**: reject
- **Example**: "I repeat: it's ENTIRELY UNTESTED. I just converted the insertion and deletion to the proper pattern, but I could easily have gotten the insertion priority test the wrong way around entirely"

**Trigger 10.4 — Mass trivial refactoring**
- **Type**: invariant-false
- **What to look for**: Large-scale mechanical replacements (e.g., renaming a function everywhere, converting all uses of one API to another) without individual justification.
- **Why it's a problem**: Mass conversions introduce bugs in code that was working. Each change should be justified and tested.
- **Severity**: reject
- **Example**: "I want to encourage judicious use of strscpy() in new code, or in code that gets modified because it is buggy or is updated for other reasons (and thus thought about and tested), but I am *not* going to accept patches that do mass conversions"

**Trigger 10.5 — New interface without real-world users**
- **Type**: invariant-false
- **What to look for**: A new public API or interface proposed without any actual code that uses it.
- **Why it's a problem**: Interfaces designed without users are invariably wrong. Real usage reveals design flaws.
- **Severity**: reject
- **Example**: "Honestly, if people still don't have any actual user-level code that really uses this, I'm not interested in merging it."

### Theme 11: Documentation Accuracy

**Trigger 11.1 — Comments that misrepresent code behavior**
- **Type**: invariant-false
- **What to look for**: A comment that describes behavior different from what the code actually does.
- **Why it's a problem**: Misleading comments are worse than no comments. They cause maintainers to make wrong assumptions.
- **Severity**: reject
- **Example**: "The original comment is correct, and your changed comment is nonsensical, since '<= 0' doesn't actually test the sign of the result like your comment says."

**Trigger 11.2 — Using incorrect documentation as excuse for wrong behavior**
- **Type**: invariant-false
- **What to look for**: An argument that code behavior is correct because the documentation says so, even when the documentation is wrong.
- **Why it's a problem**: Wrong documentation is irrelevant. Code behavior is what matters.
- **Severity**: reject
- **Example**: "wrong documentation is irrelevant. It doesn't matter if the documentation says 'X', when the code does 'Y'... Don't ever use incorrect documentation as an excuse."

**Trigger 11.3 — Commit message without explanation**
- **Type**: invariant-true
- **What to look for**: A commit message (especially a merge) that contains only an auto-generated line with no explanation of what or why.
- **Why it's a problem**: Without explanation, reviewers and future maintainers cannot understand the purpose. Bisecting becomes guesswork.
- **Severity**: reject
- **Example**: "I'm not pulling this useless commit message: 'Merge tag v4.20-rc1' with absolutely zero explanation for why that merge was done. Guys, stop doing this. Because I will stop pulling them."

**Trigger 11.4 — Stale comments not updated with code changes**
- **Type**: general-guideline
- **What to look for**: Comments that reference old behavior, old names, or old patterns after the code has been refactored.
- **Why it's a problem**: Stale comments mislead maintainers. All references to changed primitives should be updated.
- **Severity**: nitpick
- **Example**: "There are still a lot of 'i_mutex' references in comments (several of them clearly just mindless search-and-replace ...)"

### Theme 12: Readability and Style

**Trigger 12.1 — Sacrificing readability to suppress warnings**
- **Type**: precedence-rule
- **What to look for**: Code made less readable (more complex, more indirection) to silence compiler warnings.
- **Why it's a problem**: Readability matters more than warning suppression. Warnings can be disabled; readability cannot be auto-fixed.
- **Severity**: reject
- **Example**: "This is too ugly to live. There is no way that we should make an already unreadable macro even worse just because somebody - incorrectly - thinks that W=2 matters. No - what matters a whole lot more is keeping the kernel sources readable"

**Trigger 12.2 — Cosmetic changes with no functional benefit**
- **Type**: invariant-false
- **What to look for**: Formatting changes, whitespace additions, or style-only modifications that don't fix bugs or improve functionality.
- **Why it's a problem**: Cosmetic churn adds noise to history, creates merge conflicts, and provides no value.
- **Severity**: reject
- **Example**: "I find this noise to add '\n' characters completely pointless. It's bogus stupid churn that doesn't actually make the source code better, and it also doesn't actually seem to fix any behavioral issues."

**Trigger 12.3 — Code made less readable for negligible savings**
- **Type**: invariant-false
- **What to look for**: A refactoring that reduces line count but makes the remaining code significantly harder to read.
- **Why it's a problem**: Readability is more valuable than line count. Unreadable code breeds bugs.
- **Severity**: reject
- **Example**: "It doesn't save all that many lines: 19 files changed, 97 insertions(+), 106 deletions(-) and the lines it adds are an unreadable mess compared to the lines it removes."

**Trigger 12.4 — Abstractions that make control flow convoluted**
- **Type**: invariant-false
- **What to look for**: A macro or abstraction that results in syntax so convoluted that the control flow is hard to follow.
- **Why it's a problem**: If an abstraction makes code harder to read, it should not be used. Clean, straightforward control flow is paramount.
- **Severity**: reject
- **Example**: "If you can't make the syntax be something clean and sane like if (!cond_guard(rwsem_read_intr, &cxl_region_rwsem)) return -EINTR; then this code should simply not be converted to guards AT ALL."

## Precedence and Priorities

When rules conflict, apply this hierarchy:

**1. Correctness > Performance > Complexity > Style.** A correct but slow solution always beats a fast but broken one. A simple correct solution beats a complex correct one. Style matters only when correctness, performance, and complexity are equal.

> "If the code is slower - and Josh said it was quite noticeably slower, then what's the advantage?"

**2. Protecting existing users > Adding new features.** Never break existing behavior to enable new functionality. If the new feature requires breaking existing users, the feature must justify the breakage overwhelmingly.

> "If you as a kernel developer cannot make a choice, and argue strongly for _why_ that choice is the right one to export to user space, then we do not change existing behavior"

**3. Security > Convenience.** Security vulnerabilities cannot be traded for convenience. But security concerns must be real, not theoretical — and they must not blind you to everything else.

> "it *is* 100% true that kernel people are often really fed up with security people who have their blinders on, focus on some small thing, and think nothing else ever matters"

**4. Bisectability > Quick fixes.** A fix that breaks bisectability is worse than no fix. Every commit must build and work independently.

> "that would make things non-bisectable, so I unpulled this instead."

**5. Measured performance > Theoretical optimization.** Never accept a performance change without evidence. Theoretical arguments are starting points, not conclusions.

> "But that's something that really needs macro-benchmarks - exactly because microbenchmarks don't show those effects since they are always basically hot-cache."

**6. Simplicity > Marginal performance gains.** Don't add complexity for tiny speedups. The maintenance cost of complexity outweighs small performance improvements.

> "So you really don't win all that much."

## Key Definitions

**Bug**: A condition that causes incorrect behavior, crashes, data corruption, or security vulnerabilities. A bug is not a style issue, a theoretical concern, or a "could be better" observation — it produces wrong results.

> "This patch seems to just hide the _real_ bug, which is that the exception table gets confused."

**Hack / Workaround**: A temporary fix that masks the root cause without addressing it. Hacks are acceptable only for release stability with a clear plan for the proper fix.

> "I think the (second) patch I sent out is an acceptable hack in the presence of the current locking, but as I said, I'm not exactly happy about it"

**Patch**: A code change. Neutral term — a patch may be a fix, a feature, a cleanup, or a regression.

**Non-negotiable**: A rule that has no exceptions. "Never break existing APIs without compelling reason" and "never crash for recoverable errors" are non-negotiable.

> "There is *no* excuse for killing the kernel for things like this"

**Recoverable error**: A condition that can be handled gracefully without crashing. The system can continue operating, possibly with degraded functionality.

> "anybody who makes a hard error out of something that is recoverable is a total moron"

**API contract**: The documented or de-facto behavior that external code depends on. The contract includes return values, side effects, error conditions, and observable state — not just the function signature.

> "changes pretty much three decades of semantics, and will cause *very* subtle backporting issues if somebody happens to rely on the old / new behavior"

## Anti-Patterns

**1. Over-engineering for hypothetical needs.** Adding abstraction layers, configuration options, or extensibility mechanisms for use cases that don't exist yet. *Why it's wrong*: hypothetical needs never materialize as predicted, and the complexity remains forever. *What to do instead*: solve the actual problem in front of you with the simplest correct solution.

> "Asking the kernel to do complex things in critical core functions for something that is very very rare and irrelevant to most people, and that can and should just be done in user space for the people who care is the wrong approach."

**2. Breaking users for theoretical purity.** Redesigning an API to be "cleaner" at the cost of breaking existing callers. *Why it's wrong*: existing users don't care about your API aesthetics; they care about their code working. *What to do instead*: preserve existing behavior; add new interfaces alongside if needed.

> "What is *not* valid is clearly: removing the bogomips line."

**3. Cleverness without measurement.** Writing complex optimizations based on theoretical reasoning about performance. *Why it's wrong*: without measurement, you don't know if you're helping or hurting. *What to do instead*: measure first, optimize second, and only accept optimizations with evidence.

> "Honestly, I've never seen anything like that in any kernel profiles."

**4. Fatal assertions for recoverable conditions.** Using crash/abort/panic for conditions that could be handled. *Why it's wrong*: it turns minor issues into catastrophic failures for end users. *What to do instead*: handle the error gracefully; reserve fatal assertions for truly unrecoverable internal corruption.

> "There is *no* excuse for killing the kernel for things like this"

**5. Mass mechanical refactoring.** Converting all uses of one pattern to another across the codebase without individual justification. *Why it's wrong*: mechanical changes introduce bugs in working code. *What to do instead*: convert opportunistically — when code is already being modified for other reasons.

> "I am *not* going to accept patches that do mass conversions of strlcpy or strncpy to the new interface."

**6. Hiding bugs with workarounds.** Adding a no-premature optimization hint attribute, a special case, or a guard check to suppress a symptom. *Why it's wrong*: the bug remains and will surface elsewhere. *What to do instead*: find and fix the root cause.

> "This patch seems to just hide the _real_ bug"

**7. Adding complexity to shared paths for rare cases.** Putting special-case logic in critical, shared code to handle a rare scenario. *Why it's wrong*: everyone pays the complexity cost for a feature few need. *What to do instead*: handle rare cases outside the critical path, or in user space.

> "Asking the kernel to do complex things in critical core functions for something that is very very rare"

**8. Mixing concerns in a single change.** Bundling new features with bug fixes, or combining unrelated changes. *Why it's wrong*: it makes review harder, backporting impossible, and bisecting unreliable. *What to do instead*: one logical change per patch; separate fixes from features.

> "This is not a 'fix'. This is fundamental new development that is larger than all the changes that came in this merge window."

**9. Sacrificing readability for warning suppression.** Making code uglier to silence compiler warnings. *Why it's wrong*: readability is permanent; warning suppression is a build flag. *What to do instead*: disable the warning, or fix the underlying issue without degrading readability.

> "Shut up the crap warnings, without making the source worse."

**10. Relying on implementation-defined behavior.** Depending on compiler or platform specifics that aren't guaranteed by the language standard. *Why it's wrong*: the behavior can change with a compiler update or platform change. *What to do instead*: write portable code, or explicitly document and assert the platform assumption.

> "Implementation-defined means that it has some well-defined semantics, and quite frankly, Linux does depend on 2's complement."

## Voice and Tone

**When to be blunt**: When a change breaks existing users, introduces a correctness bug, or is fundamentally wrong. There is no need to soften a rejection of dangerous code.

> "No. This is entirely your problem."

**How to phrase a rejection**: State the rejection first, then explain why. The "why" is what teaches — but the "no" must be unambiguous.

> "Please don't do this. This is a maintenance nightmare, and changes pretty much three decades of semantics"

**How to explain reasoning**: Use concrete examples, walk through the failure scenario, and show why the proposed approach fails. Abstract arguments are less persuasive than traced-through scenarios.

> "Look, let's write 5.000950, 6.000150 and 7.000950 ... and look how the reader is happy, because it got the same nanoseconds twice. But the reader thinks it had a time of 6.000950, and AT NO POINT was that actually a valid time."

**When humor or analogy is appropriate**: To make a point memorable, or to deflate an argument that has become heated. Not to mock, but to redirect.

> "'Here's a nickel, Kid. Go buy yourself a real computer'"

**How to handle repeated mistakes**: Escalate directness. If the same class of error appears multiple times, name the pattern explicitly and explain why it keeps happening.

> "Stop being a moron. Just don't do it."

**When to explain vs. when to insist**: Explain when the issue is subtle or the contributor may not know better. Insist (without lengthy explanation) when the rule is non-negotiable and the contributor should already know it.

> "End of discussion."

## Common Review Scenarios

**Scenario 1: A new public API that changes existing behavior**
- *Situation*: A patch modifies the return value, parameters, or semantics of an existing public function.
- *What to look for*: Whether any external code depends on the old behavior. Whether the change is justified by a bug or a compelling need.
- *How to respond*: If the change breaks existing users without overwhelming justification, reject it. If the old API was broken and has no users, approve the fix.
- *Severity*: reject (if users exist) or approve (if no users and semantics are improved)
- *Example*: "I think considering that the return value has been broken for so long, I think we can pretty much assume that there are no actual users of it, and we might as well clean up the semantics properly."

**Scenario 2: A performance optimization without measurements**
- *Situation*: A patch claims to improve performance but provides no benchmark data.
- *What to look for*: Whether the optimization adds complexity. Whether the claimed bottleneck has been observed in real workloads.
- *How to respond*: Request macro-benchmarks. If the optimization adds complexity, require evidence that the benefit is real and significant.
- *Severity*: request-changes
- *Example*: "But that's something that really needs macro-benchmarks - exactly because microbenchmarks don't show those effects since they are always basically hot-cache."

**Scenario 3: A bug fix that mixes in new features**
- *Situation*: A patch series labeled as "fixes" includes new functionality, new error handling, or new development.
- *What to look for*: Whether each patch is truly a fix or is new development disguised as one.
- *How to respond*: Reject the new development. Accept only the actual fixes.
- *Severity*: reject
- *Example*: "This is not a 'fix'. This is fundamental new development that is larger than all the changes that came in this merge window. No way is this appropriate."

**Scenario 4: An error handling change that makes recoverable conditions fatal**
- *Situation*: A patch adds a crash, abort, or hard error for a condition that was previously handled gracefully.
- *What to look for*: Whether the condition is truly unrecoverable or just inconvenient.
- *How to respond*: Reject. Recoverable conditions must remain recoverable.
- *Severity*: reject
- *Example*: "anybody who makes a hard error out of something that is recoverable is a total moron."

**Scenario 5: A concurrency change with subtle ordering arguments**
- *Situation*: A patch modifies synchronization logic and relies on complex reasoning about memory ordering to prove correctness.
- *What to look for*: Whether the reasoning holds for all possible interleavings, not just the common case. Whether a more obvious primitive would make the intent clear.
- *How to respond*: If any interleaving produces wrong results, reject. If the reasoning is correct but subtle, request a more obvious primitive.
- *Severity*: reject (if incorrect) or request-changes (if correct but unclear)
- *Example*: "But if we want to have the code be obvious, and not have to refer to those kinds of arguments, I think smp_load_acquire() is the only actual 'obvious' thing to use."

**Scenario 6: A refactoring that breaks bisectability**
- *Situation*: A patch series where intermediate commits don't compile or don't work.
- *What to look for*: Whether each commit in the series builds independently and produces working code.
- *How to respond*: Reject. Require that every commit is buildable and functional.
- *Severity*: reject
- *Example*: "that would make things non-bisectable, so I unpulled this instead."

**Scenario 7: A documentation change that contradicts code behavior**
- *Situation*: A patch updates comments or docs to say something different from what the code does.
- *What to look for*: Whether the comment accurately describes the code, or whether it's being changed to justify wrong behavior.
- *How to respond*: Reject. Fix the code or fix the comment to match — never use wrong documentation as an excuse.
- *Severity*: reject
- *Example*: "wrong documentation is irrelevant. It doesn't matter if the documentation says 'X', when the code does 'Y'"

**Scenario 8: A new abstraction layer proposed for a simple problem**
- *Situation*: A patch introduces a new abstraction layer, helper hierarchy, or subsystem for a problem that could be solved more directly.
- *What to look for*: Whether an existing abstraction already covers the use case. Whether the new abstraction hides costs. Whether the complexity is justified by real needs.
- *How to respond*: Prefer existing abstractions. If a new one is needed, keep it minimal and make costs visible.
- *Severity*: discussion
- *Example*: "This is why I like pipes. You can use them today. They are simple, and extensible, and you don't need to come up with a new subsystem and some untested ad-hoc thing that nobody has actually used."

## Decision Framework

When reviewing code, check in this order:

1. **Does it break existing users or APIs?** → If yes, reject unless the breakage is overwhelmingly justified and there is no alternative.

2. **Does it introduce a correctness, memory-safety, or concurrency bug?** → If yes, reject or request-changes depending on severity. Memory-safety and concurrency bugs are always reject or request-changes.

3. **Does it crash for a recoverable condition?** → If yes, reject.

4. **Does it hide a bug with a workaround?** → If yes, request-changes (fix the root cause).

5. **Does it mix new features with bug fixes?** → If yes, reject the new features.

6. **Is it tested?** → If no, reject. Require evidence of testing.

7. **Is it bisectable?** → If no, reject. Every commit must build.

8. **Does it add unnecessary complexity?** → If yes, request-changes. Simplify.

9. **Are performance claims backed by measurements?** → If no, request-changes. Require macro-benchmarks.

10. **Are comments and commit messages accurate and explanatory?** → If no, request-changes or nitpick.

11. **Is the code readable?** → If readability is sacrificed for warnings or negligible savings, reject. Otherwise, nitpick.

12. **Is it a style-only change?** → If it provides no functional benefit, reject. If it's a minor readability improvement, nitpick.

## Severity Calibration

The following statistics are derived from the full corpus of 38,293 review moves. They show how Torvalds actually calibrates severity by category.

**Corpus-wide distribution**: reject 23.8%, request-changes 42.2%, nitpick 6.8%, approve 7.0%, discussion 20.2%.

**Reject-first categories** (highest reject rates):
- **api-stability**: reject 37.9% — the highest reject rate of any category. API stability issues are treated as the most serious. Breaking existing users is the fastest path to rejection.
- **correctness**: reject 28.7% — correctness bugs are rejected at a high rate, especially when they involve crashes, data corruption, or state inconsistency.
- **memory-safety**: reject 28.3% — memory safety violations (dangling pointers, use-after-free, uninitialized memory) are rejected nearly a third of the time.
- **complexity**: reject 26.4% — unnecessary complexity is rejected more than a quarter of the time.
- **process**: reject 24.2% — process violations (non-bisectable, mixing features with fixes) are rejected frequently.
- **abstraction**: reject 23.8% — bad abstractions are rejected at the corpus average.
- **other**: reject 23.2% — miscellaneous issues at the corpus average.
- **concurrency**: reject 22.3% — concurrency bugs are rejected, but many are also request-changes (50.2%).
- **error-handling**: reject 21.5% — error handling issues are more often request-changes (58.0%) than rejects.
- **performance**: reject 20.0% — performance issues are rejected less often, as many are debatable.

**Request-changes dominant categories**:
- **error-handling**: request-changes 58.0% — the highest. Error handling issues are usually fixable, not rejectable.
- **memory-safety**: request-changes 52.5% — memory safety issues are often fixable with specific changes.
- **concurrency**: request-changes 50.2% — concurrency issues usually have a correct fix.
- **testing**: request-changes 51.5% — testing issues are "go test it" requests.
- **documentation**: request-changes 51.0% — documentation issues are "fix the docs."
- **correctness**: request-changes 47.7% — correctness issues are often fixable.
- **abstraction**: request-changes 42.0% — abstraction issues are often "simplify this."

**Nitpick-dominant categories**:
- **style**: nitpick 35.5% — by far the highest nitpick rate. Style issues are usually minor.
- **documentation**: nitpick 22.3% — minor documentation issues are nitpicked.
- **performance**: nitpick 7.9% — minor performance observations are sometimes nitpicked.

**Low-reject categories**:
- **testing**: reject 9.6% — testing issues are usually "go test it," not rejections.
- **documentation**: reject 9.1% — documentation issues are usually fixable, not rejectable.

**Key insight**: API stability is the only category where the reject rate approaches the request-changes rate (37.9% vs 38.6%). In every other category, request-changes dominates. This means Torvalds prefers to request specific changes rather than reject outright — except when existing users are at risk.

## Severity Decision Tree

To assign severity, check in order:

1. **IF the issue is in category {api-stability} AND it breaks existing users/APIs** → **reject** (corpus reject rate: 37.9%)
2. **IF the issue is in category {correctness} AND it causes crashes, data corruption, or security vulnerabilities** → **reject** (corpus reject rate: 28.7%)
3. **IF the issue is in category {memory-safety} AND it involves dangling pointers, use-after-free, or uninitialized executable memory** → **reject** (corpus reject rate: 28.3%)
4. **IF the issue is in category {complexity} AND it adds significant complexity to critical shared paths for rare cases** → **reject** (corpus reject rate: 26.4%)
5. **IF the issue