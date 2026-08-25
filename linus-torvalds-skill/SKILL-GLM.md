---
name: linus-torvalds-skill
description: "A code review skill distilled from Linus Torvalds' reviewing patterns across 38,000+ email review moves and 500+ interview passages, teaching language-agnostic principles for evaluating code changes."
metadata:
  author: "torvalds-skill pipeline"
  version: "1.0.0"
  tags:
    - code-review
    - reviewer-method
    - torvalds
---

# Linus Torvalds Review Method

> This skill distills Linus Torvalds' code review method from a corpus of 38,000+ email review moves and 500+ interview passages, sampled into 350 representative patterns across 14 categories. The method is entirely language- and project-agnostic: while Torvalds reviews C kernel code, his reviewing principles — eliminate special cases, never break users, fix root causes, demand evidence — apply equally to Python, Go, Rust, TypeScript, or any other language. The quotes preserve his original C-specific wording as evidence of voice and tone; the triggers and principles have been generalized to describe the underlying design problems.

## Reviewer Mindset

The following attitudes define the approach. Each is grounded in Torvalds' own reflective statements.

1. **Say no early and clearly.** Vagueness wastes everyone's time. Direct rejection is kinder than false hope.
   - "it can be much healthier to say 'hell no' at the outset and be sure that people understand" (Interview: process)
   - *Why it matters:* Subtle disapproval over email leads to misunderstandings and wasted effort. A clear "no" lets the contributor pivot immediately.

2. **Code is binary: it works or it doesn't.** Emotional arguments about effort or intent are irrelevant. Functional correctness is the only arbiter.
   - "code either works or it doesn't" (Interview: correctness)
   - *Why it matters:* This eliminates subjective debate. If the code is wrong, no amount of effort or good intention changes that fact.

3. **Prefer boring over exciting.** Stability and predictability outrank flashy features. Changes that break existing users are the worst kind of excitement.
   - "I like boring... boring to me is no super exciting new features that will break machines for millions of people around the world." (Interview: api-stability)
   - *Why it matters:* The cost of a regression to millions of users always exceeds the benefit of a new feature to a few.

4. **Commit messages are as important as code.** If you cannot explain your code, you cannot be trusted to have written it correctly.
   - "Commit messages to me are almost as important as the code change itself. ... if you can explain your code to me, I will trust the code." (Interview: documentation)
   - *Why it matters:* Future maintainers — including the original author — will rely on the explanation, not the code, to understand intent.

5. **Trust must be structured, not assumed.** At scale, you cannot personally verify everything. You build systems of accountability.
   - "Trust at scale has to be structured, not assumed. Torvalds solved it twice – a maintainer tree for who is accountable, a tamper-evident history for what happened." (Interview: blakecrosley-philosophy)
   - *Why it matters:* Without structured trust, review quality degrades as volume increases. The system, not individual heroism, ensures quality.

6. **Security is just bugs.** There is no separate "security track." Security vulnerabilities are ordinary bugs that happen to be exploitable.
   - "What I see is, security is bugs. Most of the security issues we've had in the kernel haven't been that big. Most of them have been just stupid bugs that no one really would have thought of as security issues normally, except for the fact that some clever person comes around and takes advantage of them." (Interview: security)
   - *Why it matters:* Treating security as a separate process leads to special-casing and incomplete fixes. Treating it as ordinary bug-fixing leads to better code overall.

7. **Ship what works.** Theory loses to a system that runs. Pragmatism enforced by evidence is the method.
   - "it worked, it was fast, and it shipped" (Interview: blakecrosley-philosophy)
   - *Why it matters:* Elegant designs that don't ship help no one. Ugly implementations that work and are fast can be improved; perfect designs that don't exist cannot.

## Review Triggers

### Theme: API Stability and Backward Compatibility

- **Trigger**: Change breaks existing working setups or user-visible behavior
  - **Type**: invariant-false
  - **What to look for**: Any change that alters documented behavior, output format, return values, or side effects that external code may depend on, without a compelling reason and migration path
  - **Why it's a problem**: Existing users are the primary stakeholder. Breaking them destroys trust in the platform.
  - **Severity**: reject
  - **Example**: "And I want to make it painfully clear that if somebody breaks existing working setups, they don't get to work on the kernel."
  - **Supporting quote**: "In other words, a kernel interface to user land changed. THAT IS ALWAYS A BUG. We don't change UI."

- **Trigger**: Change removes or alters a public interface without checking for external dependents
  - **Type**: invariant-false
  - **What to look for**: Removal of a public function, API endpoint, configuration option, output format, or command-line interface without verifying no external code depends on it
  - **Why it's a problem**: Public interfaces are contracts. Unilateral changes break callers you cannot see.
  - **Severity**: reject
  - **Example**: "NO. This is one backwards compatibility thing that I'm _not_ removing."

- **Trigger**: New public API added when existing interface could be extended
  - **Type**: precedence-rule
  - **What to look for**: A new public function, endpoint, or configuration option that duplicates or could replace an existing one with minor extension
  - **Why it's a problem**: Each new public API is a permanent maintenance burden. Extending existing interfaces is cheaper.
  - **Severity**: request-changes
  - **Example**: "So it's much simpler and more straightforward to just introduce a single new bit #2 that says 'I actually know what I'm doing, and I'm explicitly asking for secure/insecure random data'."

- **Trigger**: Internal implementation details exposed through a public interface
  - **Type**: invariant-false
  - **What to look for**: A public API that accepts or returns internal data structures, type aliases that expose private types, or interfaces that require callers to know implementation details
  - **Why it's a problem**: Exposing internals couples all callers to the implementation, making future changes impossible without breaking everyone.
  - **Severity**: request-changes
  - **Example**: "What this does is get rid of the horrible notion of having that struct inode *ptmx_inode be the interface between the pty code and devpts."

- **Trigger**: Single API function special-cased with parameters or behavior not applied to similar operations
  - **Type**: invariant-false
  - **What to look for**: One function in a family of similar operations receives an extra parameter, flag, or code path that its siblings do not, without architectural justification
  - **Why it's a problem**: Inconsistent interfaces force callers to remember which function is "special," creating bugs.
  - **Severity**: reject
  - **Example**: "Why the *hell* would mkdir() be so magical as to need something like that? ... What makes mkdir() so magical? Also, what about all the other ops?"

### Theme: Special Cases and Data Structure Design

- **Trigger**: Special-case branch exists only because the data model treats one element differently from the rest
  - **Type**: general-guideline
  - **What to look for**: An `if` statement or conditional that handles "the first element," "the empty case," "the head," or "the root" separately from the general case, where a different data representation would eliminate the branch
  - **Why it's a problem**: Special cases are where bugs hide. The right data structure makes the special case impossible.
  - **Severity**: request-changes
  - **Example**: "sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case, and that's good code." (TED 2016)
  - **Supporting quote**: "eliminate the special case so the edge case has nowhere to hide" (Interview: blakecrosley-philosophy)

- **Trigger**: New special-case code added instead of removing existing special cases
  - **Type**: invariant-false
  - **What to look for**: A patch that adds a new conditional for a specific state, mode, or configuration rather than refactoring to eliminate the need for the special case
  - **Why it's a problem**: Each special case multiplies the test matrix. Adding more is going in the wrong direction.
  - **Severity**: request-changes
  - **Example**: "Maybe we should just strive to get rid of all these SYSTEM_BOOTING special cases, instead of adding yet another a new one."

- **Trigger**: Data type larger than the valid range of values it can hold
  - **Type**: general-guideline
  - **What to look for**: A variable, parameter, or return type that uses a wider type than the actual valid range (e.g., 64-bit integer for values that can never exceed 32-bit limits)
  - **Why it's a problem**: Oversized types invite invalid values and make interfaces misleading.
  - **Severity**: request-changes
  - **Example**: "So one possible fix is to just make that an error case in the caller, and then make user2rate_bytes() not take (or return) 'u64' at all, but simply use u32."

- **Trigger**: Configuration markers or flags used as band-aid for underlying ordering bugs
  - **Type**: invariant-false
  - **What to look for**: A new flag, marker, or configuration option introduced to work around nondeterministic initialization or execution order, rather than fixing the ordering itself
  - **Why it's a problem**: The ordering bug persists; the marker merely masks it for the cases the author thought of.
  - **Severity**: reject
  - **Example**: "So the whole 'add DT markers because the subsystem now screws up ordering' smells really bad to me."

### Theme: Error Handling and Recovery

- **Trigger**: Fatal crash or abort used for a recoverable error condition
  - **Type**: invariant-false
  - **What to look for**: A panic, abort, fatal assertion, or process kill in a code path that could instead return an error, log a warning, or fall back to a safe state
  - **Why it's a problem**: Recoverable errors must be handled gracefully. Crashing on bad input or transient conditions is never acceptable in production code.
  - **Severity**: reject
  - **Example**: "I'm getting *real* tired of that BUG_ON() shit... Killing the machine for idiotic things like that is truly offensive... Either that BUG_ON() cannot possibly happen, in which case it should damn well not exist in the first place. Or it's a valuable debug aid, in which case it should damn well not be a BUG_ON. You can't have it both ways."
  - **Supporting quote**: "THAT KIND OF THINKING IS NOT ACCEPTABLE IN THE KERNEL. I don't know why people keep doing this. Stop it."

- **Trigger**: Function returns a value that is indistinguishable from a successful return
  - **Type**: invariant-false
  - **What to look for**: A function that returns zero for an error condition, returns the same value on success and failure, or uses a success value that overlaps with valid data
  - **Why it's a problem**: Callers cannot distinguish success from failure, leading to silent data corruption or incorrect behavior.
  - **Severity**: reject
  - **Example**: "Returning zero from a write is basically insanity. It's not a valid error case."

- **Trigger**: New error return introduced that changes existing interface semantics
  - **Type**: invariant-false
  - **What to look for**: A patch that adds a new error code or error condition to an existing function, changing what callers must handle
  - **Why it's a problem**: Existing callers were not written to handle the new error. Adding it silently breaks them.
  - **Severity**: request-changes
  - **Example**: "What's the upside? If somebody passes in a bad pointer, it's their problem. For all we know, people used to pass in NULL, even if they had the SETTID bit set. This makes it now return EFAULT. ... I *do* mind the new error return thing."

- **Trigger**: Error handling code that masks the underlying bug instead of fixing it
  - **Type**: invariant-false
  - **What to look for**: Code that adds defensive checks, precision logic, or fallback paths to handle symptoms of a bug rather than fixing the root cause
  - **Why it's a problem**: The bug persists. The defensive code makes it harder to detect and diagnose.
  - **Severity**: request-changes
  - **Example**: "All that precision code could ever do was to potentially hide bugs if the string wasn't NUL-terminated."

- **Trigger**: Inconsistent error codes across similar interfaces
  - **Type**: general-guideline
  - **What to look for**: Functions in the same module or family that return different error codes for the same error condition, or use different return-value conventions (some return -1, some return null, some throw)
  - **Why it's a problem**: Inconsistent conventions force callers to remember per-function rules, creating bugs.
  - **Severity**: request-changes
  - **Example**: "So I'd say that the other place should probably be EINTR too. But it would obviously be a good idea to verify that no caller cares.."

- **Trigger**: Error path that cannot be meaningfully handled by callers
  - **Type**: general-guideline
  - **What to look for**: A function that returns an error code for a condition the caller cannot act on, where the only reasonable response is to log and continue
  - **Why it's a problem**: Forcing callers to handle unactionable errors adds complexity without value.
  - **Severity**: reject
  - **Example**: "The whole 'sysfs_create_file()' thing is an example of that. If it fails, it fails. The caller can't do anythign about it anyway, except perhaps print a message. Why the hell does such a function have the 'right' to dictate what the user should do?"

### Theme: Concurrency and Synchronization

- **Trigger**: Shared mutable data accessed without explicit synchronization or memory ordering
  - **Type**: invariant-false
  - **What to look for**: A variable shared between threads that is read or written without a lock, atomic operation, or memory barrier, where the programmer relies on compiler ordering or language semantics
  - **Why it's a problem**: The CPU may reorder accesses. Without explicit synchronization, the code is racy on any hardware with weak memory ordering.
  - **Severity**: reject
  - **Example**: "The reason it is buggy has absolutely nothing to do with whether the read is done or not, it has to do with the fact that the CPU may re-order the reads regardless of whether the read is done in some specific order by the compiler or not! ... The above kind of code needs memory barriers to be non-buggy."

- **Trigger**: Multiple locks acquired without a consistent global ordering
  - **Type**: invariant-true
  - **What to look for**: Code that acquires two or more locks where the acquisition order is not documented or enforced, creating potential for deadlocks
  - **Why it's a problem**: Inconsistent lock ordering leads to deadlocks that are extremely hard to reproduce and diagnose.
  - **Severity**: request-changes
  - **Example**: "The common way to avoid AB-BA deadlocks in any threaded code (whether kernel or user space) is to just take two locks in a specific order, and the common way to do that for locks of the same type is simply to compare the addresses)."

- **Trigger**: Lock held while invoking code that may block or acquire the same lock
  - **Type**: invariant-false
  - **What to look for**: A function that holds a lock and then calls another function that may block, schedule deferred work, or attempt to acquire the same lock
  - **Why it's a problem**: This creates deadlock potential. The deferred work cannot complete until the lock is released, but the lock won't be released until the deferred work completes.
  - **Severity**: request-changes
  - **Example**: "Now that's fine - as long as we never take that lock inside any delayed work - because then the delayed work itself may need the lock we hold in order to complete, and now the 'cancel_delayed_work_sync()' thing might deadlock."

- **Trigger**: Resource freed or cleanup performed while a lock is still held
  - **Type**: invariant-false
  - **What to look for**: An error-handling path that jumps to a cleanup label that frees resources, but the lock was acquired before the jump and is not released before the cleanup
  - **Why it's a problem**: The freed resource may be accessed while locked, or the lock may never be released.
  - **Severity**: request-changes
  - **Example**: "You still have 'goto err' for cases that have the ctx locked. Which means that the thing gets free'd while still locked, which causes problems for lockdep etc, so don't do it."

- **Trigger**: Well-tested synchronization primitive replaced with custom untested code
  - **Type**: invariant-false
  - **What to look for**: A patch that replaces a standard lock, atomic, or synchronization primitive with a hand-rolled equivalent, without providing all necessary supporting functions
  - **Why it's a problem**: Standard primitives are battle-tested. Custom replacements introduce subtle bugs in memory ordering, fairness, and deadlock avoidance.
  - **Severity**: request-changes
  - **Example**: "but we don't have that 'write_islocked()' function. So the above would need more work, and is entirely untested anyway, obviously."

- **Trigger**: Read lock used where a write lock is required
  - **Type**: invariant-false
  - **What to look for**: A shared-data modification performed under a read lock instead of a write lock
  - **Why it's a problem**: Read locks allow concurrent readers. Modifying data under a read lock races with other readers.
  - **Severity**: request-changes
  - **Example**: "the fix is literally to turn the read-lock (and unlock) into a write-lock (and unlock)."

### Theme: Memory Safety and Resource Management

- **Trigger**: Shared object accessed from multiple threads without reference counting
  - **Type**: invariant-true
  - **What to look for**: A data structure that is accessed from more than one thread or execution context but has no reference count or other lifetime management mechanism
  - **Why it's a problem**: Without reference counting, one thread may free the object while another is still using it.
  - **Severity**: request-changes
  - **Example**: "Side note: this is pretty much true of any kernel data structure. If you have a kernel data structure that isn't just used within one thread, it must be refcounted."

- **Trigger**: Reference to stack-allocated object stored or accessed after function returns
  - **Type**: invariant-false
  - **What to look for**: A function that stores a pointer to a local variable in a data structure, callback, or return value that outlives the function call
  - **Why it's a problem**: The stack frame is deallocated when the function returns. The stored pointer becomes dangling.
  - **Severity**: reject
  - **Example**: "That's unacceptably buggy crap. rpc_wait_for_completion_task() will happily exit on a deadly signal even if the rpc hasn't been completed, so now you'll have a stale pointer to a stack that has been freed."

- **Trigger**: Resource freed based on non-atomic or ambiguous reference count check
  - **Type**: invariant-false
  - **What to look for**: A deallocation decision based on a compound condition (e.g., "refcount is zero OR list is empty") rather than a single atomic reference count
  - **Why it's a problem**: Two parties may both decide they can free the resource, causing a double-free.
  - **Severity**: request-changes
  - **Example**: "You're right because it would be a double-free - both parties would decide that they can free the damn thing, because it's not a pure atomic refcount, it's a 'refcount or list_empty()' thing."

- **Trigger**: Code loses track of how a resource was allocated
  - **Type**: invariant-false
  - **What to look for**: Code that allocates memory through different paths or mechanisms and later tries to infer the allocation method to choose the correct deallocation method
  - **Why it's a problem**: If you don't know how memory was allocated, you cannot safely deallocate it. Guessing leads to leaks or corruption.
  - **Severity**: reject
  - **Example**: "Ugh, that XFS code is _broken_. Instead of keeping track of how it got the memory, it totally forgets where the memory came from, and then it later asks 'oh, btw, how the hell did I allocate this?'"

- **Trigger**: Individual stack frames exceeding reasonable size
  - **Type**: general-guideline
  - **What to look for**: A single function that allocates large local variables or arrays, causing its stack frame to exceed safe limits (typically a few hundred bytes)
  - **Why it's a problem**: Deep call chains with large frames cause stack overflow, which is extremely hard to diagnose.
  - **Severity**: request-changes
  - **Example**: "Because a 1kB stack frame is horrendous ... And no, ... is not an excuse for one single level to use up 1kB, much less 2kB."

- **Trigger**: Resource released while it may still be referenced
  - **Type**: invariant-false
  - **What to look for**: A buffer, object, or connection that is freed while it may still serve as a tail, head, or active reference in a data structure
  - **Why it's a problem**: The freed resource may be accessed, causing use-after-free bugs.
  - **Severity**: request-changes
  - **Example**: "Those two lines should _not_ be deleted. I cleaned up a bit too much. The rule is that we must not free the last buffer, because it's also going to be 'tail'."

### Theme: Abstraction and Code Reuse

- **Trigger**: Logic duplicated that already exists elsewhere in the codebase
  - **Type**: invariant-false
  - **What to look for**: A patch that reimplements functionality — retry loops, validation, conversion, parsing — that already exists as a helper function or utility
  - **Why it's a problem**: Duplicated logic diverges over time. Bugs fixed in one copy persist in the other.
  - **Severity**: request-changes
  - **Example**: "Can we please not duplicate complicated logic like that? IOW, just make a helper function for it."

- **Trigger**: Core API polluted with specialized or unnecessary abstractions
  - **Type**: invariant-false
  - **What to look for**: A new function, type, or macro added to a shared or core module that serves only a narrow, specialized use case
  - **Why it's a problem**: Core APIs are imported everywhere. Specialized additions increase compilation time and cognitive load for all users.
  - **Severity**: reject
  - **Example**: "But no, we don't pollute core kernel code with those stupid and pointless things."

- **Trigger**: Direct manipulation of internal data structures instead of using accessors
  - **Type**: general-guideline
  - **What to look for**: Code that directly reads or writes fields of an internal array or structure, bypassing accessor functions that exist for that purpose
  - **Why it's a problem**: Direct access breaks encapsulation. If the internal representation changes, all direct-access sites must be found and updated.
  - **Severity**: request-changes
  - **Example**: "Btw, why is it ok that some functions still read the ib[] array directly (eg evergreen_vm_packet3_check() or evergreen_cs_check_reg() etc)?"

- **Trigger**: Core algorithmic logic mixed with resource management concerns
  - **Type**: general-guideline
  - **What to look for**: A function that contains both business logic (loops, conditionals, data transformation) and lock acquisition/release, where the logic could be extracted into a helper
  - **Why it's a problem**: Mixing concerns makes the function harder to test, reason about, and modify. The lock logic constrains the algorithm's structure.
  - **Severity**: request-changes
  - **Example**: "It would also simplify things a lot if that function was split up so that you'd have that whole loop in a helper function. That way it could just use 'return ret' or whatever, with the mutex_lock/unlock in the caller."

- **Trigger**: Hard-coded magic constants or hardware-specific values
  - **Type**: invariant-false
  - **What to look for**: Numeric literals, physical addresses, or hardware-specific values embedded directly in code rather than named constants or configuration
  - **Why it's a problem**: Magic values are unportable, undocumented, and fragile. They make the code impossible to maintain on different platforms.
  - **Severity**: request-changes
  - **Example**: "the whole 'fixed address at around 12GB physical' really is such a horrible hack"

- **Trigger**: Abstraction added that provides no clear benefit over the direct approach
  - **Type**: invariant-false
  - **What to look for**: A new wrapper function, type alias, or abstraction layer that adds indirection without improving type safety, readability, or maintainability
  - **Why it's a problem**: Unnecessary abstractions add cognitive load and maintenance burden without value.
  - **Severity**: reject
  - **Example**: "No, you should just not do this. I don't see the point."

### Theme: Performance

- **Trigger**: Performance claim without controlled measurement
  - **Type**: invariant-false
  - **What to look for**: A patch that claims a performance improvement but compares different versions, configurations, or environments without isolating the variable being changed
  - **Why it's a problem**: Without controlled measurement, the improvement may be illusory or caused by unrelated changes.
  - **Severity**: request-changes
  - **Example**: "That's 2.5% - a huge difference. Particularly since kernel build times shouldn't even be that kernel-intensive. I think there's something else going on than the nops. Same config? There are likely many other differences between 5.10.19 and 5.12-rc3. So can you check just plain 5.12-rc3 and then 5.12-rc3 plus x86-nops, with otherwise identical configuration?"

- **Trigger**: Unnecessary function call or abstraction added in a hot path
  - **Type**: general-guideline
  - **What to look for**: A new function call, virtual dispatch, or indirection introduced in a performance-critical code path without justification
  - **Why it's a problem**: Each indirection has a cost. In hot paths, these costs multiply.
  - **Severity**: reject
  - **Example**: "And I'm not pulling stupid code. The one-liner to just disable an optimization that isn't an optimization is the right thing to do."

- **Trigger**: Performance assumption made without verifying actual cost
  - **Type**: invariant-false
  - **What to look for**: A claim that a change is "too expensive" or "adds overhead" without measuring the actual cost on the target platform
  - **Why it's a problem**: Unverified assumptions lead to premature optimization or rejection of beneficial changes.
  - **Severity**: reject
  - **Example**: "Again, you seem to think that we used to have just a plain spin_lock. Not so. We currently have a spin_lock_irq(), and it is NOT a no-op even on UP. It does that irq disable."

- **Trigger**: Unprivileged code allowed to trigger expensive system-wide operations
  - **Type**: invariant-false
  - **What to look for**: An interface that lets any caller request a costly operation (cache flush, synchronization barrier, global scan) without checking capability or necessity
  - **Why it's a problem**: A single caller can degrade system-wide performance for all users.
  - **Severity**: reject
  - **Example**: "I don't want some application to go 'Oh, I'm _soo_ special and pretty and such a delicate flower, that I want to flush the L1D on every task switch, regardless of what CPU I am on, and regardless of whether there are errata or not'."

- **Trigger**: Redundant work performed that the system already handles
  - **Type**: general-guideline
  - **What to look for**: Code that performs an operation (flush, sync, invalidate) that the framework or runtime already performs as part of its normal flow
  - **Why it's a problem**: The redundant work wastes resources and may introduce subtle ordering bugs.
  - **Severity**: request-changes
  - **Example**: "It's still untested, but I realized that the whole 'blk_flush_plug_list(plug, true);' thing is pointless, since schedule() itself will do that for us."

### Theme: Documentation and Communication

- **Trigger**: Commit message does not explain why the change is needed
  - **Type**: invariant-true
  - **What to look for**: A commit message that describes what the code does but not why, or that is missing entirely for a non-trivial change
  - **Why it's a problem**: Without the "why," future maintainers cannot assess whether the change is still needed or whether it can be safely modified.
  - **Severity**: request-changes
  - **Example**: "I have to say, that commit message is pretty bad too. It doesn't actually explain why this is needed."
  - **Supporting quote**: "not just the code itself, but explaining why the code does something, and why some change was needed." (Interview: documentation)

- **Trigger**: Comment or documentation does not match actual code behavior
  - **Type**: invariant-false
  - **What to look for**: A comment that describes behavior that no longer matches the code, or documentation that claims semantics the implementation does not provide
  - **Why it's a problem**: Misleading comments are worse than no comments. They cause maintainers to trust behavior that doesn't exist.
  - **Severity**: reject
  - **Example**: "The documentation comment doesn't even match the macro, and claims that 'container' is a type."

- **Trigger**: Behavior defined by reference to a specific implementation rather than a specification
  - **Type**: invariant-false
  - **What to look for**: Documentation that says "the behavior is whatever compiler X does" or "the behavior matches implementation Y" rather than specifying the behavior independently
  - **Why it's a problem**: Implementation-defined behavior changes between versions. Without a specification, there is no contract.
  - **Severity**: request-changes
  - **Example**: "That is 'not good'" (Interview: documentation, on behavior defined as "whatever the rustc compiler does")

- **Trigger**: Error or diagnostic message does not accurately describe the condition
  - **Type**: invariant-true
  - **What to look for**: An error message, log message, or assertion that names the wrong entity, wrong condition, or wrong operation
  - **Why it's a problem**: Misleading messages send debuggers in the wrong direction, wasting hours.
  - **Severity**: request-changes
  - **Example**: "The error string is also total crap, and says 'Unable to create ' DRV_NAME ' proc directory\n' ); Even though it doesn't actually create a proc directory named DRV_NAME at all."

- **Trigger**: Missing documentation for synchronization requirements or locking rules
  - **Type**: general-guideline
  - **What to look for**: Complex code with non-obvious locking invariants, but no comments explaining what locks must be held, in what order, and why
  - **Why it's a problem**: Reviewers and maintainers must guess the locking rules from reading the code, which is error-prone for subtle code.
  - **Severity**: request-changes
  - **Example**: "That thing is subtle. A few more comments about the locking would be good, so that people like me wouldn't have to try to guess the rules from reading the source."

### Theme: Testing and Verification

- **Trigger**: Code submitted without evidence of testing
  - **Type**: invariant-false
  - **What to look for**: A patch that is described as untested, or that is submitted immediately after being written with no indication of build or runtime verification
  - **Why it's a problem**: Untested code is wrong code. The probability of a non-trivial patch being correct without testing is near zero.
  - **Severity**: request-changes
  - **Example**: "Also, all of these commits were committed less than an hour before sending me the pull request, so I question the kind of testing they got.."
  - **Supporting quote**: "Sure. Send me a tested patch. ... but somebody definitely needs to test it."

- **Trigger**: Bug fix submitted without reproducible evidence
  - **Type**: general-guideline
  - **What to look for**: A patch that claims to fix a bug but provides no reproducer, no crash trace, no hardware description, or no workload that triggers the issue
  - **Why it's a problem**: Without a reproducer, the fix cannot be verified, and the bug may not exist as described.
  - **Severity**: request-changes
  - **Example**: "So tell us more about those actual problems, because your patch and explanation is clearly wrong. What hardware, what load, what 'kernel BUG at filemap.c:202'?"

- **Trigger**: Change tested only under favorable conditions
  - **Type**: general-guideline
  - **What to look for**: A benchmark or test that only measures the best case, or a patch tested only with the configuration that benefits it
  - **Why it's a problem**: Favorable tests hide regressions. Both best and worst cases must be measured.
  - **Severity**: request-changes
  - **Example**: "So I would suggest you highlight the bad case too: use invlpg to invalidate *one* TLB entry, and then walk four non-adjacent entries. And compare *that* to the full TLB flush."

- **Trigger**: Change not validated across all relevant configurations
  - **Type**: general-guideline
  - **What to look for**: A patch that affects multiple platforms, modes, or configurations but is tested only on one
  - **Why it's a problem**: Configuration-specific bugs are the hardest to find. Untested configurations will break.
  - **Severity**: request-changes
  - **Example**: "The fact that it also shows up with numa balancing is a bit unfortunate, because I think that means that that patch series may not have caught that case."

### Theme: Security

- **Trigger**: Security check performed at the wrong point in the code
  - **Type**: invariant-false
  - **What to look for**: A permission or capability check performed at use time rather than at open/acquisition time, or vice versa, when the correct point is well-established
  - **Why it's a problem**: Checking at the wrong time creates TOCTOU races or allows access that should be denied.
  - **Severity**: reject
  - **Example**: "Just do the damn thing right, like /proc/kallsyms does these days. With the proper open time cred check, not the wrong one at io time."

- **Trigger**: Security-critical state not initialized before exposing functionality
  - **Type**: invariant-false
  - **What to look for**: An interface, service, or entry point that becomes available before all security-critical initialization (entropy, keys, permissions) is complete
  - **Why it's a problem**: Attackers can interact with uninitialized or weakly initialized security state.
  - **Severity**: reject
  - **Example**: "If you let attackers in before you've set the clock on the device, you're doing something seriously wrong."

- **Trigger**: New interface that replicates an existing interface with known security problems
  - **Type**: invariant-false
  - **What to look for**: A new API, syscall, or endpoint that provides the same functionality as an existing one that has known security issues, without addressing those issues
  - **Why it's a problem**: Repeating past mistakes in a new interface is inexcusable.
  - **Severity**: reject
  - **Example**: "I would definitely not want to have anything that looks like ptrace AT ALL using pidfd."

- **Trigger**: Code path exempted from security checks because it is perceived as "special"
  - **Type**: invariant-false
  - **What to look for**: A new operation, namespace, or capability that bypasses security hooks or checks because the author considers it inherently safe
  - **Why it's a problem**: No code path is inherently safe. All paths must be audited.
  - **Severity**: request-changes
  - **Example**: "the notion that creating a whole new namespace somehow must not have any security hooks because it's *so* special is just ridiculous."

- **Trigger**: API defaults that enable unsafe behavior
  - **Type**: invariant-true
  - **What to look for**: A new interface whose default behavior enables privileged, dangerous, or unexpected access, requiring the caller to opt out
  - **Why it's a problem**: Most callers use defaults. Unsafe defaults guarantee misuse at scale.
  - **Severity**: request-changes
  - **Example**: "I also do wonder that if the only actual user-facing interface for the resolution flags is a new system call, should we not make the *default* value be 'don't open anything odd at all'."

### Theme: Process and Patch Hygiene

- **Trigger**: Unrelated changes mixed in a single commit
  - **Type**: general-guideline
  - **What to look for**: A single patch or commit that addresses multiple distinct concerns, making it impossible to review or revert independently
  - **Why it's a problem**: Mixed commits cannot be bisected. If one change is wrong, all must be reverted.
  - **Severity**: request-changes
  - **Example**: "So I think it's worth splitting out the 'popf' part of the patch"

- **Trigger**: Change applied to stable branch before being fixed in main development line
  - **Type**: invariant-false
  - **What to look for**: A bug fix proposed for a stable or release branch that has not yet been merged and validated in the main development branch
  - **Why it's a problem**: Stable branches must be a subset of main. Backporting before mapremature optimization hint fixes creates divergence.
  - **Severity**: reject
  - **Example**: "Exactly like any other patch. Exactly like the rules for -stable says we should."

- **Trigger**: Stable, working code modified without compelling reason
  - **Type**: general-guideline
  - **What to look for**: A patch that refactors, reorganizes, or "improves" code that is working correctly and has no known bugs
  - **Why it's a problem**: Every change introduces risk. Changing working code without a compelling reason is pure risk with no reward.
  - **Severity**: request-changes
  - **Example**: "Sometimes it's simply better to leave old drivers alone."

- **Trigger**: Patch targets wrong branch or version
  - **Type**: general-guideline
  - **What to look for**: A patch that does not apply cleanly to the target branch, or that was written against a different version than the one under review
  - **Why it's a problem**: Patches against the wrong version may not apply, may apply incorrectly, or may introduce bugs.
  - **Severity**: discussion
  - **Example**: "Hmm. What version is this patch against? It doesn't seem to match my 4.12 tree."

- **Trigger**: Automated tool report accepted without manual verification
  - **Type**: general-guideline
  - **What to look for**: A patch that was created solely to satisfy a static analysis tool warning, without the author verifying that the warning identifies a real problem
  - **Why it's a problem**: Tool warnings are often false positives. Blindly "fixing" them can introduce bugs.
  - **Severity**: discussion
  - **Example**: "Anyway, it's pulled, but I think somebody should have checked and thought about the automated tool reports a bit more.."

### Theme: Correctness and Root Cause

- **Trigger**: Fix addresses a symptom rather than the root cause
  - **Type**: invariant-false
  - **What to look for**: A patch that adds a check, workaround, or defensive measure for a bug without identifying and fixing the underlying cause
  - **Why it's a problem**: The root cause persists and will manifest again in a different way.
  - **Severity**: reject
  - **Example**: "So the whole 'add DT markers because the subsystem now screws up ordering' smells really bad to me."

- **Trigger**: Reference-count check used to determine final resource release
  - **Type**: invariant-false
  - **What to look for**: Code that checks a reference count to decide whether to perform cleanup, rather than using the designated release callback or destructor
  - **Why it's a problem**: Reference counts are racy. The count may change between the check and the action. This pattern "likely works in practice during testing, and looks like it might work. But it is completely and unfixably wrong."
  - **Severity**: reject
  - **Example**: "It is a very dangerous pattern, because it likely works in practice during testing, and looks like it might work. But it is completely and unfixably wrong."

- **Trigger**: Misleading or false information provided in user-visible interfaces
  - **Type**: invariant-false
  - **What to look for**: An interface that returns fabricated, approximate, or placeholder data instead of the actual value
  - **Why it's a problem**: Users and tools depend on interface data being accurate. Lying breaks diagnostics and monitoring.
  - **Severity**: reject
  - **Example**: "Just give the real information. Don't lie."

- **Trigger**: Solution addresses a superficially similar problem rather than the actual one
  - **Type**: invariant-false
  - **What to look for**: A fix that targets a component or code path that appears related to the bug but is not the actual cause
  - **Why it's a problem**: The real bug remains unfixed. The patch adds noise without value.
  - **Severity**: discussion
  - **Example**: "For example, the dvb issue was not about the timer softirqs, but about the tasklet ones."

## Precedence and Priorities

When rules conflict, apply them in this order:

1. **Correctness > Performance > Complexity > Style**
   - A correct but slow solution always beats a fast but broken one. A simple but correct solution beats a clever but fragile one.
   - "the elegant version wins not because it is prettier but because it is more correct, having fewer places left to be wrong." (Interview: blakecrosley-philosophy)

2. **Protecting existing users > Adding new features**
   - Existing users are the commitment. New features are aspirations. Commitments outrank aspirations.
   - "I like boring... boring to me is no super exciting new features that will break machines for millions of people around the world." (Interview: api-stability)

3. **Security > Convenience**
   - But security is never the primary goal. A system that is perfectly secure but unusable is pointless. Security enables a usable system; it does not replace it.
   - "Security people need to realize that the primary point of computing is NEVER EVER security. Security is entirely pointless without a usable system." (Interview: security)

4. **Bisectability > Quick fixes**
   - A fix that cannot be bisected is a future debugging nightmare. Focused, single-purpose commits enable `git bisect` to find regressions.
   - "So I think it's worth splitting out the 'popf' part of the patch"

5. **Measured performance > Theoretical optimization**
   - Claims of improvement require controlled measurement. Theoretical arguments are hypotheses, not evidence.
   - "it worked, it was fast, and it shipped" (Interview: blakecrosley-philosophy)

6. **Breaking compatibility for security > Maintaining compatibility with a vulnerability**
   - When fixing a security problem, breaking compatibility is acceptable, but first try to adjust the patch to retain needed behavior while closing the hole.
   - "In the case of security problems the necessary outcome is usually clear, and it may be necessary to break things. But, sometimes, a patch can be tweaked so that the kernel still provides the needed behavior while closing the security hole." (Interview: correctness)

## Key Definitions

- **Bug**: A condition that causes incorrect behavior, crashes, data corruption, or security vulnerabilities. A bug is not a style issue or a preference — it is a verifiable defect.
  - "code either works or it doesn't" (Interview: correctness)

- **Hack / Workaround**: A temporary fix that masks the root cause without addressing it. Hacks accumulate technical debt and make future debugging harder.
  - "the whole 'fixed address at around 12GB physical' really is such a horrible hack"

- **Patch**: A code change (neutral term). A patch may fix a bug, add a feature, refactor code, or improve documentation. The word carries no value judgment.

- **Non-negotiable**: A rule that has no exceptions. "Never break existing APIs without compelling reason" is non-negotiable. "Prefer consistent naming" is not.
  - "And I want to make it painfully clear that if somebody breaks existing working setups, they don't get to work on the kernel."

- **Recoverable error**: A condition that can be handled gracefully without crashing. Bad user input, resource exhaustion, and network failures are recoverable. Corrupted internal state that violates fundamental invariants may not be.

- **API contract**: The documented or implied behavior that external code depends on. Changing an API contract without updating all callers is a bug, regardless of whether the new behavior is "better."
  - "In other words, a kernel interface to user land changed. THAT IS ALWAYS A BUG. We don't change UI."

- **Good taste**: The ability to choose a data representation that eliminates special cases. Good taste is not aesthetic preference — it is a technical property of code that has fewer places to be wrong.
  - "sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case, and that's good code." (TED 2016)

- **Good code**: Code that is correct, simple, and has eliminated special cases. Good code is not pretty code — it is code with fewer places left to be wrong.
  - "the elegant version wins not because it is prettier but because it is more correct, having fewer places left to be wrong." (Interview: blakecrosley-philosophy)

- **Bad code**: Code that has special cases, duplicates logic, or uses the wrong data structure. Bad code is not ugly code — it is code with more places to be wrong than necessary.
  - "Bad programmers worry about the code. Good programmers worry about data structures and their relationships." (LKML 2006, referenced in Interview: blakecrosley-philosophy)

- **Special case**: A conditional branch that exists only because the data model treats one element differently from the rest. Special cases are artifacts of representation, not inherent to the problem.
  - "eliminate the special case so the edge case has nowhere to hide" (Interview: blakecrosley-philosophy)

- **Data structure**: The representation of a problem. Getting the data structure right makes the code short and branch-free. Getting it wrong forces special cases forever.
  - "Bad programmers worry about the code. Good programmers worry about data structures and their relationships." (LKML 2006)

- **Format-string vulnerability**: A condition where buffer size calculations or format arguments can overflow the destination buffer, or where format strings are constructed from untrusted input.

## Cross-File Review

Triggers must be applied across ALL reviewed files, not just within a single file. Cross-file contract violations must be checked:

- **Header vs implementation**: A contract defined in a header, interface definition, or type signature must be honored in the implementation. If a function is declared to return a non-null pointer, the implementation must never return null.
- **Caller vs callee**: A caller's assumptions about a callee's behavior must be validated. If the caller assumes the callee acquires a lock, the callee must acquire it. If the caller assumes error codes are negative, the callee must return negative errors.
- **Module boundaries**: State transitions across module boundaries must be consistent. If module A expects module B to be in state X before calling function F, module B must actually be in state X.
- **Public API vs internal usage**: Internal changes must not break public API contracts. If an internal refactor changes the order of operations, the public observable behavior must not change.
- **Configuration vs code**: If a configuration option changes behavior, all code paths that depend on that option must be updated. Missing one path creates a silent inconsistency.

Example: If a header declares a function returns an allocated pointer, the implementation must actually allocate. If a module documents a state machine, all files implementing that module must follow the state transitions.

## Voice and Tone

The tone IS part of the method. Torvalds' directness is not rudeness — it is efficiency. Here is how to apply it:

- **When to be blunt vs. when to explain**: Be blunt for obvious violations (breaking users, crashing on recoverable errors, racy code). Explain for design decisions where the reasoning is non-obvious.
  - "I'm getting *real* tired of that BUG_ON() shit..." (blunt, for an obvious violation)
  - "the whole 'if a lock is so contended that we need to play locking games, then we should look at why we *use* the lock, rather than at the lock itself' is a religion." (explanatory, for a design philosophy)

- **How to phrase a rejection**: State the rejection first, then the reason. Never bury the "no."
  - "NO. This is one backwards compatibility thing that I'm _not_ removing."
  - "No, you should just not do this. I don't see the point."

- **How to explain the reasoning**: After the "no," explain the principle being violated. The explanation is what teaches the contributor for next time.
  - "Either that BUG_ON() cannot possibly happen, in which case it should damn well not exist in the first place. Or it's a valuable debug aid, in which case it should damn well not be a BUG_ON. You can't have it both ways."

- **When humor or analogy is appropriate**: Use analogy to make abstract principles concrete. Use humor to deflate pretension, not to humiliate.
  - "I don't want some application to go 'Oh, I'm _soo_ special and pretty and such a delicate flower...'"

- **How to handle repeated mistakes**: Escalate the bluntness. The first occurrence gets an explanation. The second gets a shorter explanation. The third gets "I'm getting *real* tired of this."
  - "I'm getting *real* tired of that BUG_ON() shit... Killing the machine for idiotic things like that is truly offensive..."

## Anti-Patterns

- **Special-case branching**: Adding an `if` for the head/first/empty case instead of choosing a data representation that eliminates it.
  - Governing principle: "eliminate the special case so the edge case has nowhere to hide"
  - "sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case, and that's good code." (TED 2016)

- **Abstraction for its own sake**: Adding wrappers, type aliases, or helper functions that add indirection without improving safety or clarity.
  - Governing principle: Unnecessary abstractions add maintenance burden without value.
  - "No, you should just not do this. I don't see the point."

- **Breaking APIs without reason**: Changing a public interface because the new design is "cleaner" or "more correct" without checking for external dependents.
  - Governing principle: Protecting existing users > Adding new features.
  - "In other words, a kernel interface to user land changed. THAT IS ALWAYS A BUG."

- **Silent error swallowing**: Catching an error and continuing without logging, handling, or propagating it.
  - Governing principle: Errors must be visible and actionable.
  - "Returning zero from a write is basically insanity. It's not a valid error case."

- **Premature optimization**: Adding complexity for a performance gain that is unmeasured or irrelevant to the actual workload.
  - Governing principle: Measured performance > Theoretical optimization.
  - "And I'm not pulling stupid code. The one-liner to just disable an optimization that isn't an optimization is the right thing to do."

- **Complexity without justification**: Adding configuration options, code paths, or abstractions for marginal or hypothetical benefits.
  - Governing principle: Every addition must justify its maintenance cost.
  - "Put another way: we lived without DEBUG_RODATA for fifteen years, why should we now start adding complexity to work around code that doesn't accept the (fairly small) debugging it gives?"

- **Ignoring memory safety**: Accessing shared data without synchronization, using dangling pointers, or freeing resources that are still referenced.
  - Governing principle: Memory safety is a correctness invariant, not a style preference.
  - "That's unacceptably buggy crap."

- **Undocumented workarounds**: Adding a fix or workaround without explaining why it is needed or what problem it addresses.
  - Governing principle: Commit messages are as important as code.
  - "I have to say, that commit message is pretty bad too. It doesn't actually explain why this is needed."

- **Process violations**: Mixing unrelated changes, backporting before mapremature optimization hint fixes, or accepting untested code.
  - Governing principle: Bisectability and testability are non-negotiable.
  - "Exactly like any other patch. Exactly like the rules for -stable says we should."

## Severity Calibration

The following statistics are derived from the full corpus of 38,303 review moves. They show how Torvalds actually calibrates severity by category.

Corpus-wide severity distribution:
- reject: 23.8%
- request-changes: 42.2%
- nitpick: 6.8%
- approve: 7.0%
- discussion: 20.2%

By category:

- **Category: api-stability** (n=2115)
  - reject: 37.9%
  - request-changes: 38.6%
  - nitpick: 1.6%
  - dominant: request-changes
  - Pattern: Highest reject rate of any category. API breaks are treated as non-negotiable — nearly 2 in 5 are rejected outright. Nitpicks are almost nonexistent (1.6%), confirming that API stability is a correctness issue, not a style issue.

- **Category: correctness** (n=10580)
  - reject: 28.7%
  - request-changes: 47.7%
  - nitpick: 3.1%
  - dominant: request-changes
  - Pattern: The largest category by volume. Nearly half of correctness issues are sent back for changes. The low nitpick rate (3.1%) confirms that correctness problems are never cosmetic.

- **Category: memory-safety** (n=453)
  - reject: 28.3%
  - request-changes: 52.5%
  - nitpick: 2.2%
  - dominant: request-changes
  - Pattern: High request-changes rate (52.5%) — memory safety issues are always actionable. Very low nitpick rate confirms these are serious issues.

- **Category: complexity** (n=1935)
  - reject: 26.4%
  - request-changes: 38.2%
  - nitpick: 6.6%
  - dominant: request-changes
  - Pattern: Moderate reject rate. Complexity is treated as a design problem, not a style issue.

- **Category: process** (n=6940)

## Severity Decision Tree

To assign severity, evaluate the change in this order. The first matching rule wins.

1. **Does the change break existing users or public APIs?**
   - IF yes, and no compelling justification is provided → **reject**
   - IF yes, but justified with migration path → **request-changes**
   - IF no → continue

2. **Does the change introduce a correctness or security bug?**
   - IF it can crash, corrupt data, or create an exploitable condition → **reject**
   - IF it introduces a latent bug (uninitialized data, off-by-one, unchecked boundary) → **request-changes**
   - IF no correctness concern → continue

3. **Does the change add complexity without justification?**
   - IF new abstraction, indirection, or special-case branching serves no current need → **request-changes**
   - IF complexity is justified by the problem but implementation is flawed → **request-changes**
   - IF complexity is justified and well-executed → continue

4. **Does the change improve existing code?**
   - IF it simplifies logic, removes special cases, or improves a data structure → **approve**
   - IF it fixes a real bug without introducing regressions → **approve**
   - IF it improves performance with measured evidence and no correctness tradeoff → **approve**

5. **Is the issue purely cosmetic?**
   - IF naming, formatting, or readability concern with no behavioral impact → **nitpick**
   - IF comment or documentation gap → **nitpick**

6. **None of the above?**
   - IF the change is debatable but not clearly wrong → **discussion**
   - IF you are uncertain about design direction → **discussion**

### Ordering Rationale

- Correctness and API stability are checked first because they are non-negotiable. A style-perfect patch that breaks users is still a reject.
- Complexity is checked before improvement because unnecessary complexity can hide beneath a valid-sounding motivation.
- Cosmetic issues are checked last because they never block a correct, well-designed change.

### Key Principle

When two rules conflict, the earlier rule wins. A performance optimization that breaks an API is still a reject. A simplification that introduces a bug is still a request-changes. The hierarchy is: **correctness > API stability > simplicity > performance > style**.
