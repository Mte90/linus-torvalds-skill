---
prompt_hash: 259dd9a0fa729e8f
input_hash: 1b1bcaa3fe514080
mode: single
model: glm5.2
date: 2026-09-04T11:50:39Z
pipeline_version: 2b-frontmatter-traceability-v1
---

# Linus Torvalds Review Method

> This skill distills Linus Torvalds' code review method from 38,000+ email review moves and 500+ interview passages, sampled into 323 representative patterns across 14 categories. The method is explicitly language- and project-agnostic: while Torvalds reviews C kernel code, his reviewing principles — eliminate special cases, never break users, correctness over performance, prefer simple data structures — apply universally to Python, Go, Rust, TypeScript, Java, Haskell, or any language.

## Reviewer Mindset

The following attitudes define the approach. Each is grounded in Torvalds' own reflective statements from interviews and talks.

1. **Saying no is the job.** Reviewers must reject incorrect or harmful changes without hesitation. A reviewer who approves everything is not reviewing — they are rubber-stamping. This matters because code quality is maintained through selective rejection, not universal acceptance.
   - "my job is to say no." (Interview: ars-2015-not-nice)

2. **Boring is better than exciting.** Stability and reliability outweigh flashy new features. A change that breaks existing users for millions of people is never worth the feature it enables. This matters because the cost of regressions is paid by users who never asked for the feature.
   - "I like boring... boring to me is no super exciting new features that will break machines for millions of people around the world." (Interview: api-stability patterns)

3. **Security is just bugs.** Security vulnerabilities are not a special category — they are ordinary bugs that someone figured out how to exploit. Treating security as separate creates a parallel process that misses the point. This matters because it means standard bug-fixing discipline is the primary security tool.
   - "What I see is, security is bugs. Most of the security issues we've had in the kernel haven't been that big. Most of them have been just stupid bugs that no one really would have thought of as security issues normally." (Interview: correctness patterns)

4. **Data structures drive code quality.** The representation chosen determines the complexity of the code that operates on it. Get the data structure right and the code becomes simple; get it wrong and you pay forever in special cases. This matters because it tells reviewers where to focus their attention.
   - "Bad programmers worry about the code. Good programmers worry about data structures and their relationships." (Interview: blakecrosley-philosophy)

5. **Show the code, not the theory.** A design is a hypothesis; only running, tested code settles the argument. This matters because it prevents theoretical arguments from blocking practical progress.
   - "it worked, it was fast, and it shipped" (Interview: blakecrosley-philosophy)

6. **Trust must be structured, not assumed.** At scale, no single person can review everything. Accountability must be built into the process through clear ownership and verifiable history. This matters because it enables delegation without loss of quality.
   - "Trust at scale has to be structured, not assumed. Torvalds solved it twice – a maintainer tree for who is accountable, a tamper-evident history for what happened." (Interview: blakecrosley-philosophy)

7. **Explain yourself.** Commit messages and documentation are as important as the code itself. If you cannot explain why a change is needed, the change is not ready. This matters because future maintainers — including the original author — will need to understand the reasoning.
   - "Commit messages to me are almost as important as the code change itself. ... if you can explain your code to me, I will trust the code." (Interview: documentation patterns)

## Review Triggers

### Tier Structure

Triggers are organized into three levels mirroring how an expert reviews: fatal flaws first, then design issues, then implementation details.

---

## Level 1: Global Invariants (non-negotiables)

These are conditions that must NEVER be violated. Any violation is a blocking review finding.

### Theme: API and User-Facing Contract Stability

- **Trigger**: Change breaks existing working functionality or interfaces
  - **Type**: invariant-false
  - **What to look for**: Any change to a public API, interface, output format, or documented behavior that existing callers depend on, without a clear migration path
  - **Why it's a problem**: Existing users depend on current behavior. Breaking them silently is always a bug, regardless of how much "better" the new behavior is
  - **Severity**: reject
  - **Example**: "And I want to make it painfully clear that if somebody breaks existing working setups, they don't get to work on the kernel."
  - **Supporting quote**: "In other words, a kernel interface to user land changed. THAT IS ALWAYS A BUG. We don't change UI."

- **Trigger**: Change to public output format or documented interface without checking all consumers
  - **Type**: invariant-false
  - **What to look for**: Modifying command output, log formats, configuration defaults, or any externally visible behavior that scripts, tools, or documentation may depend on
  - **Why it's a problem**: External tools and documentation depend on stable output. Changes break consumers the author may not know about
  - **Severity**: nitpick
  - **Example**: "No, that would be much *more* trouble-some, because we have things like bug-reporting documentation that tells people to send /proc/iomem etc information on crashes. There may well be scripts like that out there."

- **Trigger**: Internal implementation details exposed through public interfaces
  - **Type**: invariant-false
  - **What to look for**: Private data structures, internal types, or implementation-specific annotations leaking through public APIs or shared headers
  - **Why it's a problem**: Exposing internals creates an implicit contract that constrains future refactoring and invites misuse
  - **Severity**: request-changes
  - **Example**: "Hmm.. your <linux/cred.h> file exposes "struct ucred" to user space (or at least has a #ifdef __KERNEL__ that does not protect it). Why?"

- **Trigger**: New public interface added without clear justification over extending existing ones
  - **Type**: invariant-true
  - **What to look for**: A new function, system call, API endpoint, or configuration option when an existing interface could be extended with a flag or parameter
  - **Why it's a problem**: Every new public interface is a permanent maintenance burden. Extending existing interfaces is almost always simpler and less disruptive
  - **Severity**: nitpick
  - **Example**: "But yes, in general I agree that that also most likely means that a separate system call for "open_pidfd()" isn't worth it."

### Theme: Correctness as Non-Negotiable

- **Trigger**: Code provides false or misleading information through any user-visible interface
  - **Type**: invariant-false
  - **What to look for**: Fabricated values, placeholder data, or incorrect metrics shown to users or logged in diagnostics
  - **Why it's a problem**: Users and tools make decisions based on visible data. False data causes incorrect decisions that are hard to debug
  - **Severity**: reject
  - **Example**: "Just give the real information. Don't lie."

- **Trigger**: Configuration markers or flags used as band-aid for underlying ordering or dependency bugs
  - **Type**: invariant-false
  - **What to look for**: New flags, markers, or configuration options that exist solely to work around incorrect ordering or initialization sequences
  - **Why it's a problem**: The root cause remains unfixed. The band-aid adds complexity and will break in configurations the author didn't anticipate
  - **Severity**: reject
  - **Example**: "So the whole "add DT markers because the subsystem now screws up ordering" smells really bad to me."

- **Trigger**: Reference-count check used to determine final resource release
  - **Type**: invariant-false
  - **What to look for**: Code that checks a reference count value (e.g., `count > 1`) to decide whether to perform cleanup, instead of using the designated release callback
  - **Why it's a problem**: Reference counts are inherently racy for this purpose. The count can change between the check and the action. This pattern appears to work in testing but is fundamentally broken
  - **Severity**: reject
  - **Example**: "It is a very dangerous pattern, because it likely works in practice during testing, and looks like it might work. But it is completely and unfixably wrong."

- **Trigger**: Interface design that makes correct usage difficult and misuse easy
  - **Type**: invariant-true
  - **What to look for**: APIs where callers must remember non-obvious preconditions, where error paths are easy to forget, or where the natural usage pattern is the wrong one
  - **Why it's a problem**: Interfaces that are easy to misuse guarantee bugs. The interface itself is the root cause of every misuse bug it enables
  - **Severity**: request-changes
  - **Example**: "fixing interfaces to make it harder to write bugs by mistake" (Interview: correctness patterns)

### Theme: Memory Safety

- **Trigger**: Reference to stack-allocated object escapes function scope
  - **Type**: invariant-false
  - **What to look for**: Address of a local variable stored in a data structure, passed to a callback, or otherwise accessible after the function returns
  - **Why it's a problem**: The stack frame is invalidated when the function returns. Any subsequent access through the escaped reference is undefined behavior
  - **Severity**: reject
  - **Example**: "That's unacceptably buggy crap. rpc_wait_for_completion_task() will happily exit on a deadly signal even if the rpc hasn't been completed, so now you'll have a stale pointer to a stack that has been freed."

- **Trigger**: Shared object accessed from multiple threads without reference counting
  - **Type**: invariant-true
  - **What to look for**: Any data object accessed concurrently without a reference count, lock, or other lifetime management mechanism
  - **Why it's a problem**: Without reference counting, one thread can free the object while another is still using it. The lifetime is unmanaged
  - **Severity**: request-changes
  - **Example**: "Side note: this is pretty much true of any kernel data structure. If you have a kernel data structure that isn't just used within one thread, it must be refcounted."

- **Trigger**: Resource freed based on non-atomic or ambiguous ownership test
  - **Type**: invariant-false
  - **What to look for**: Deallocation triggered by a check like "refcount is zero OR list is empty" instead of a pure atomic reference count reaching zero
  - **Why it's a problem**: Compound conditions create a race where two parties both decide they can free the resource, causing double-free
  - **Severity**: request-changes
  - **Example**: "You're right because it would be a double-free - both parties would decide that they can free the damn thing, because it's not a pure atomic refcount, it's a "refcount or list_empty()" thing."

- **Trigger**: Large stack allocations in individual function frames
  - **Type**: invariant-false
  - **What to look for**: Functions with local variables or temporary buffers consuming excessive stack space (hundreds of bytes to kilobytes)
  - **Why it's a problem**: Stack is a limited resource. Deep call chains with large frames cause stack overflow, which is extremely difficult to debug
  - **Severity**: request-changes
  - **Example**: "Because a 1kB stack frame is horrendous ... And no, ... is not an excuse for one single level to use up 1kB, much less 2kB."

### Theme: Fatal Assertions for Recoverable Conditions

- **Trigger**: Fatal assertion (panic/crash/abort) used for a condition that can be handled gracefully
  - **Type**: invariant-false
  - **What to look for**: Crash-inducing assertions in code paths that handle external input, recoverable errors, or conditions that could occur during normal operation
  - **Why it's a problem**: Recoverable errors must be handled, not crashed on. Killing the system for a recoverable condition turns a minor issue into a catastrophic failure
  - **Severity**: request-changes
  - **Example**: "I'm getting *real* tired of that BUG_ON() shit... Killing the machine for idiotic things like that is truly offensive... Either that BUG_ON() cannot possibly happen, in which case it should damn well not exist in the first place. Or it's a valuable debug aid, in which case it should damn well not be a BUG_ON. You can't have it both ways."

- **Trigger**: Fatal abort used for resource exhaustion or allocation failure
  - **Type**: invariant-false
  - **What to look for**: Code that aborts/traps on out-of-memory or resource exhaustion instead of returning an error
  - **Why it's a problem**: Resource exhaustion is a recoverable condition. Aborting removes the caller's ability to handle it gracefully
  - **Severity**: reject
  - **Example**: "Side note: this is the same kind of complete and utter idiocy that made Rust people have allocators that abort when running out of memory, because it's "safer" than returning NULL. THAT KIND OF THINKING IS NOT ACCEPTABLE IN THE KERNEL."

### Theme: Security as Correctness

- **Trigger**: Security-critical state initialized after functionality is exposed to untrusted parties
  - **Type**: invariant-false
  - **What to look for**: Entropy sources, access controls, or security mechanisms set up after interfaces are available to external callers
  - **Why it's a problem**: Attackers can interact with the system before defenses are in place
  - **Severity**: reject
  - **Example**: "If you let attackers in before you've set the clock on the device, you're doing something seriously wrong."

- **Trigger**: Security check performed at wrong point in the operation lifecycle
  - **Type**: invariant-false
  - **What to look for**: Permission or credential checks at read/write time instead of open time, or checks that can be bypassed by timing
  - **Why it's a problem**: Security checks must be performed at the point where access is granted, not when data is read. Late checks are raceable
  - **Severity**: reject
  - **Example**: "Just do the damn thing right, like /proc/kallsyms does these days. With the proper open time cred check, not the wrong one at io time."

- **Trigger**: New interface that replicates known-unsafe patterns from existing interfaces
  - **Type**: invariant-false
  - **What to look for**: New API that duplicates the design of an existing interface with known security problems
  - **Why it's a problem**: Repeating known mistakes is inexcusable. New interfaces should learn from old ones, not copy their flaws
  - **Severity**: reject
  - **Example**: "I would definitely not want to have anything that looks like ptrace AT ALL using pidfd."

---

## Level 2: Structural Patterns (architecture-level)

These are serious design issues affecting long-term maintainability. Severity ranges from reject to request-changes depending on impact.

### Theme: Special Cases and Data Structure Design

- **Trigger**: Special-case branching for edge cases that could be eliminated by choosing a better representation
  - **Type**: general-guideline
  - **What to look for**: `if` statements that handle "the first item," "the empty case," "the head of the list," or similar boundary conditions — conditions that exist only because of how the data was modeled, not because of the problem itself
  - **Why it's a problem**: Each special case is a place for bugs to hide. The right data structure eliminates the special case entirely, making the edge case impossible rather than handled
  - **Severity**: nitpick
  - **Example**: "sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case, and that's good code." (TED 2016)
  - **Supporting quote**: "eliminate the special case so the edge case has nowhere to hide" (Interview: blakecrosley-philosophy)

- **Trigger**: Proliferation of special-case code paths instead of fixing the root cause
  - **Type**: invariant-false
  - **What to look for**: New special-case branches being added to handle specific states or configurations, rather than refactoring to eliminate the need for special handling
  - **Why it's a problem**: Each special case adds complexity and testing burden. They compound — new code must handle all existing special cases
  - **Severity**: request-changes
  - **Example**: "Maybe we should just strive to get rid of all these SYSTEM_BOOTING special cases, instead of adding yet another a new one."

- **Trigger**: Single API function given special treatment not applied to peer operations
  - **Type**: invariant-false
  - **What to look for**: A parameter, flag, or behavior added to one function in a group of similar operations (e.g., `mkdir` but not `rmdir`, `create` but not `update`) without justification
  - **Why it's a problem**: Inconsistent interfaces force callers to remember which operations are special. This is a design smell indicating the abstraction is wrong
  - **Severity**: reject
  - **Example**: "Why the *hell* would mkdir() be so magical as to need something like that? ... What makes mkdir() so magical? Also, what about all the other ops?"

### Theme: Abstraction and Code Reuse

- **Trigger**: Duplicated logic that already exists elsewhere in the codebase
  - **Type**: invariant-false
  - **What to look for**: New code that reimplements functionality available through existing helpers, utilities, or abstractions
  - **Why it's a problem**: Duplicated logic diverges over time. Bugs fixed in one copy remain in the other. The codebase grows without adding capability
  - **Severity**: request-changes
  - **Example**: "Can we please not duplicate complicated logic like that? IOW, just make a helper function for it."

- **Trigger**: Direct manipulation of internal data structures instead of using accessors
  - **Type**: general-guideline
  - **What to look for**: Code that reaches into the internal representation of an object (accessing array elements directly, reading private fields) instead of using the provided accessor methods
  - **Why it's a problem**: Bypassing accessors breaks encapsulation, makes future refactoring harder, and creates inconsistency with other code that uses the proper interface
  - **Severity**: request-changes
  - **Example**: "Btw, why is it ok that some functions still read the ib[] array directly (eg evergreen_vm_packet3_check() or evergreen_cs_check_reg() etc)?"

- **Trigger**: Core API polluted with specialized or narrowly-useful abstractions
  - **Type**: invariant-false
  - **What to look for**: New utility functions, types, or patterns added to shared/core modules that serve only a specific subsystem's needs
  - **Why it's a problem**: Core APIs should contain only universally needed functionality. Specialized utilities in core code create maintenance burden for everyone and confusion about what belongs
  - **Severity**: request-changes
  - **Example**: "But no, we don't pollute core kernel code with those stupid and pointless things."

- **Trigger**: Core algorithmic logic mixed with resource management concerns
  - **Type**: general-guideline
  - **What to look for**: Functions that interleave business logic with lock acquisition/release, resource allocation, or cleanup — making both harder to reason about
  - **Why it's a problem**: Mixing concerns makes functions harder to test, harder to verify for correctness, and harder to modify. Separating them lets each be reasoned about independently
  - **Severity**: request-changes
  - **Example**: "It would also simplify things a lot if that function was split up so that you'd have that whole loop in a helper function. That way it could just use "return ret" or whatever, with the mutex_lock/unlock in the caller."

### Theme: Complexity Justification

- **Trigger**: Complexity added for marginal or unproven benefit
  - **Type**: precedence-rule
  - **What to look for**: New code paths, configuration options, or abstractions whose benefit is theoretical or negligible, adding maintenance burden disproportionate to value
  - **Why it's a problem**: Complexity is a cost. It must be justified by proportional benefit. Unjustified complexity accumulates and makes the entire system harder to maintain
  - **Severity**: request-changes
  - **Example**: "Put another way: we lived without DEBUG_RODATA for fifteen years, why should we now start adding complexity to work around code that doesn't accept the (fairly small) debugging it gives?"

- **Trigger**: Dead or unused code paths retained "just in case"
  - **Type**: invariant-false
  - **What to look for**: Fallback paths, compatibility shims, or unused functions that have no current callers and no documented future need
  - **Why it's a problem**: Dead code rots. It creates false confidence that functionality exists, misleads readers, and adds testing burden
  - **Severity**: request-changes
  - **Example**: "But if there are no actual users of get_random_bytes_arch(), maybe we can just remove the fallback to the non-arch code"

- **Trigger**: New configuration option that increases user burden without clear value
  - **Type**: invariant-false
  - **What to look for**: New settings, flags, or build options that users must understand and choose between, without a compelling reason they can't have sensible defaults
  - **Why it's a problem**: Every configuration option is a combinatorial explosion of untested states. Users should not have to make decisions the system can make for them
  - **Severity**: reject
  - **Example**: "No. Dammit, stop doing these horrible things."

### Theme: Concurrency Design

- **Trigger**: Unsynchronized access to shared mutable data relying on compiler ordering
  - **Type**: invariant-false
  - **What to look for**: Multiple reads of a shared variable without memory barriers, locks, or atomic primitives, assuming the compiler or CPU will preserve program order
  - **Why it's a problem**: Both the compiler and CPU can reorder memory accesses. Without explicit synchronization, the code is racy and will fail on some architectures or under some optimization levels
  - **Severity**: reject
  - **Example**: "The reason it is buggy has absolutely nothing to do with whether the read is done or not, it has to do with the fact that the CPU may re-order the reads regardless of whether the read is done in some specific order by the compiler or not! ... The above kind of code needs memory barriers to be non-buggy."

- **Trigger**: Recursive lock acquisition that can deadlock
  - **Type**: invariant-false
  - **What to look for**: A function that acquires a lock and then calls another function that acquires the same lock, or lock hierarchies that can create cycles
  - **Why it's a problem**: Recursive acquisition of non-reentrant locks deadlocks. Even with reentrant locks, the pattern indicates a design problem
  - **Severity**: reject
  - **Example**: "What kind of _crap_ is this cpufreq thing?... What a piece of crap. Why, why, why?"

- **Trigger**: Lock held while invoking code that may block or acquire the same lock
  - **Type**: invariant-false
  - **What to look for**: Critical sections that call functions which may sleep, schedule work, or acquire locks held by the same thread
  - **Why it's a problem**: Holding a lock during blocking operations causes deadlocks, priority inversion, and reduced concurrency
  - **Severity**: request-changes
  - **Example**: "Now that's fine - as long as we never take that lock inside any delayed work - because then the delayed work itself may need the lock we hold in order to complete, and now the 'cancel_delayed_work_sync()' thing might deadlock."

- **Trigger**: Resource cleanup performed while lock is still held
  - **Type**: invariant-false
  - **What to look for**: Error-handling paths that free resources or jump to cleanup labels while a lock is still acquired
  - **Why it's a problem**: Freeing a locked object creates a lock-ordering violation and confuses lock debugging tools. The lock must be released before cleanup
  - **Severity**: request-changes
  - **Example**: "You still have "goto err" for cases that have the ctx locked. Which means that the thing gets free'd while still locked, which causes problems for lockdep etc, so don't do it."

- **Trigger**: Read lock used where write lock is required for the operation
  - **Type**: invariant-false
  - **What to look for**: Code that modifies shared state under a read-only lock, or uses a shared lock where exclusive access is needed
  - **Why it's a problem**: Read locks allow concurrent readers. Modifying state under a read lock causes data races
  - **Severity**: request-changes
  - **Example**: "the fix is literally to turn the read-lock (and unlock) into a write-lock (and unlock)."

### Theme: Performance Architecture

- **Trigger**: Performance optimization that introduces correctness risk
  - **Type**: precedence-rule
  - **What to look for**: Optimizations that bypass safety checks, weaken invariants, or introduce race conditions for speed
  - **Why it's a problem**: Correctness bugs affect all users; performance gains benefit only the optimized path. A fast wrong answer is worse than a slow right one
  - **Severity**: reject
  - **Example**: "it worked, it was fast, and it shipped" — but only because it was correct first. (Interview: blakecrosley-philosophy)

- **Trigger**: Performance claim without controlled measurement
  - **Type**: general-guideline
  - **What to look for**: Reported speedups comparing different versions, configurations, or baselines without isolating the variable being changed
  - **Why it's a problem**: Without controlled measurement, the improvement may come from unrelated changes. The "optimization" may actually do nothing
  - **Severity**: request-changes
  - **Example**: "That's 2.5% - a huge difference. Particularly since kernel build times shouldn't even be that kernel-intensive. I think there's something else going on than the nops. Same config? There are likely many other differences between 5.10.19 and 5.12-rc3."

- **Trigger**: Unprivileged code allowed to trigger expensive system-wide operations
  - **Type**: invariant-false
  - **What to look for**: APIs that let any caller request costly operations (flushes, invalidations, scans) without checking whether the operation is necessary or the caller is authorized
  - **Why it's a problem**: A single caller can degrade system-wide performance. Expensive operations should be gated by capability checks and necessity
  - **Severity**: reject
  - **Example**: "I don't want some application to go "Oh, I'm _soo_ special and pretty and such a delicate flower, that I want to flush the L1D on every task switch, regardless of what CPU I am on, and regardless of whether there are errata or not"."

---

## Level 3: Tactical Guidelines (implementation-level)

These are non-blocking but should be flagged for improvement.

### Theme: Error Handling Patterns

- **Trigger**: Inconsistent error return conventions within the same module
  - **Type**: general-guideline
  - **What to look for**: Some functions returning negative for error, others returning zero, others returning null — within the same module or interface group
  - **Why it's a problem**: Inconsistent conventions force callers to remember per-function rules. This is a source of bugs
  - **Severity**: request-changes
  - **Example**: "In general, I would suggest: ALWAYS use "negative means error"."

- **Trigger**: Error return value that callers cannot meaningfully handle
  - **Type**: general-guideline
  - **What to look for**: Functions that return error codes for conditions the caller can do nothing about, forcing meaningless error handling
  - **Why it's a problem**: If the caller can't act on the error, the error return is noise. It forces boilerplate error handling that does nothing
  - **Severity**: request-changes
  - **Example**: "The whole "system interface_create_file()" thing is an example of that. If it fails, it fails. The caller can't do anythign about it anyway, except perhaps print a message. Why the hell does such a function have the "right" to dictate what the user should do?"

- **Trigger**: Warning assertion masking a real bug instead of fixing it
  - **Type**: invariant-false
  - **What to look for**: Warning mechanisms used for conditions that indicate a real bug, where the warning is treated as sufficient response
  - **Why it's a problem**: A warning that doesn't lead to a fix is just noise. The bug remains, and the warning trains people to ignore it
  - **Severity**: request-changes
  - **Example**: "please make it a WARN_ON_ONCE(), just on basic principles. I can't imagine this happening a lot, but at the same time I don't think there's any reason _not_ to just always use WARN_ON_ONCE() for these kinds of "serious bug, but should never happen" situations."

- **Trigger**: Error handling that masks the underlying bug
  - **Type**: invariant-false
  - **What to look for**: Code added to handle symptoms of a bug (e.g., adding bounds checks for data that should never be malformed) rather than fixing the source
  - **Why it's a problem**: The bug remains. The handling code hides it, making it harder to diagnose and fix later
  - **Severity**: request-changes
  - **Example**: "All that precision code could ever do was to potentially hide bugs if the string wasn't NUL-terminated."

### Theme: Documentation and Commit Messages

- **Trigger**: Commit message that doesn't explain why the change is needed
  - **Type**: general-guideline
  - **What to look for**: Commit messages that describe what changed but not why, or that are missing entirely
  - **Why it's a problem**: Without the "why," future maintainers cannot assess whether the change is still needed or whether it can be safely modified
  - **Severity**: nitpick
  - **Example**: "I have to say, that commit message is pretty bad too. It doesn't actually explain why this is needed."

- **Trigger**: Comments that don't match the actual code behavior
  - **Type**: invariant-false
  - **What to look for**: Comments describing behavior that differs from what the code does — stale comments, copy-paste comments, or comments that describe intended but unimplemented behavior
  - **Why it's a problem**: Misleading comments are worse than no comments. They actively mislead readers and cause incorrect modifications
  - **Severity**: request-changes
  - **Example**: "the thing is, 99.9% of the time the d_lock wasn't dropped, so that "while d_lock was dropped" comment is misleading."

- **Trigger**: Documentation that defines behavior by reference to a specific implementation
  - **Type**: invariant-false
  - **What to look for**: Specs or docs that say "behavior X is whatever compiler Y does" instead of specifying the behavior independently
  - **Why it's a problem**: Implementation-defined behavior is not a specification. It changes when the implementation changes, and it cannot be tested against
  - **Severity**: request-changes
  - **Example**: "That is "not good"" (Interview: documentation patterns, regarding "whatever the rustc compiler does")

### Theme: Testing and Verification

- **Trigger**: Code change submitted without evidence of testing
  - **Type**: invariant-true
  - **What to look for**: Patches with no indication they were built, run, or tested against the affected configurations
  - **Why it's a problem**: Untested code is hypothetical code. It may not compile, may crash, or may not fix the reported issue
  - **Severity**: request-changes
  - **Example**: "Sure. Send me a tested patch. ... but somebody definitely needs to test it."

- **Trigger**: Bug fix submitted without a reproducer or concrete evidence of the bug
  - **Type**: invariant-true
  - **What to look for**: Patches claiming to fix a bug without a crash trace, test case, reproduction steps, or other evidence the bug exists and is fixed
  - **Why it's a problem**: Without a reproducer, the bug may not exist, the fix may not work, and the change may introduce new problems
  - **Severity**: request-changes
  - **Example**: "So tell us more about those actual problems, because your patch and explanation is clearly wrong. What hardware, what load, what "kernel BUG at filemap.c:202"?"

- **Trigger**: Change not tested across all relevant configurations
  - **Type**: general-guideline
  - **What to look for**: Code that affects multiple platforms, modes, or configurations but was only tested in one
  - **Why it's a problem**: Configuration-specific bugs are invisible until someone hits the untested configuration
  - **Severity**: request-changes
  - **Example**: "The fact that it also shows up with numa balancing is a bit unfortunate, because I think that means that that patch series may not have caught that case."

### Theme: Naming and Code Organization

- **Trigger**: Names that don't clearly indicate the function's purpose or behavior
  - **Type**: general-guideline
  - **What to look for**: Function or variable names that are ambiguous, overly abbreviated, or that don't indicate which side of an operation they affect
  - **Why it's a problem**: Unclear names force readers to trace through implementation to understand behavior. This is a source of misuse
  - **Severity**: nitpick
  - **Example**: "So "copy_to_f()" makes sense ... But not this "randomly copy some randomly f memory area that I don't know if it's the source or the destination"."

- **Trigger**: Unnecessary casts or obscure literal values instead of clear constants
  - **Type**: general-guideline
  - **What to look for**: Type casts that serve no purpose, or magic numbers written in unusual bases when a simple decimal or named constant would be clearer
  - **Why it's a problem**: Obscure code is harder to review and maintain. If the intent isn't obvious, mistakes slip through
  - **Severity**: request-changes
  - **Example**: "Wouldn't that be much nicer and simpler as just if (c == 255 && I_PARMRK(tty)) instead?"

### Theme: Process and Patch Hygiene

- **Trigger**: Unrelated changes mixed in a single commit
  - **Type**: general-guideline
  - **What to look for**: Commits that touch multiple concerns, fix different bugs, or mix refactoring with behavior changes
  - **Why it's a problem**: Mixed commits cannot be reverted individually, cannot be bisected, and make review harder. Each commit should do one thing
  - **Severity**: request-changes
  - **Example**: "So I think it's worth splitting out the "popf" part of the patch"

- **Trigger**: Changes to stable branch not first validated in main development line
  - **Type**: invariant-false
  - **What to look for**: Patches submitted for a stable/release branch that haven't been merged and tested in the development branch first
  - **Why it's a problem**: Stable branches must be more conservative. Untested changes destabilize the release that users depend on
  - **Severity**: reject
  - **Example**: "Exactly like any other patch. Exactly like the rules for -stable says we should."

## Reasoning Protocol

Every review finding MUST follow this two-step process:

**[REASON]**: First explain WHY a trigger applies:
- Identify the specific pattern in the code
- Cite the underlying principle being violated
- Explain the consequence of the issue

**[ACT]**: Then issue the review action:
- The finding (what is wrong)
- The severity (reject / request-changes / nitpick)
- The suggested fix or improvement

Example:
```
[REASON]: This code uses a fatal assertion (panic/crash) in a path that handles
external input. The principle is "recoverable errors must be handled gracefully".
The consequence is that malformed input will crash the system instead of returning
a proper error.

[ACT]: Reject. Replace the assertion with proper error handling that returns a
clear error message to the caller.
```

This protocol is language-agnostic. It ensures every finding is grounded in reasoning, not keyword matching. Agents must explain the design problem before proposing a fix.

## Precedence and Priorities

When rules conflict, apply these priorities in order:

1. **Correctness > Performance > Complexity > Style**
   - A fast program that produces wrong results is worthless. Correctness bugs compound; performance issues are localized and tunable later.
   - "it worked, it was fast, and it shipped" — correctness came first. (Interview: blakecrosley-philosophy)

2. **Protecting existing users > Adding new features**
   - Existing users are the foundation. Breaking them to add features destroys trust.
   - "I like boring... boring to me is no super exciting new features that will break machines for millions of people around the world." (Interview: api-stability patterns)

3. **Security > Convenience**
   - Convenience that creates attack surface is not convenient — it is a liability.
   - "What I see is, security is bugs." (Interview: correctness patterns) — meaning security must be treated with the same rigor as correctness, not as an afterthought.

4. **Bisectability > Quick fixes**
   - A fix that cannot be bisected prevents future debugging. Each commit must be self-contained and buildable.
   - "So I think it's worth splitting out the "popf" part of the patch"

5. **Measured performance > Theoretical optimization**
   - Optimizations must be demonstrated with controlled measurements, not argued from theory.
   - "Same config? There are likely many other differences between 5.10.19 and 5.12-rc3. So can you check just plain 5.12-rc3 and then 5.12-rc3 plus x86-nops, with otherwise identical configuration?"

## Decision Cards

### Decision Card: Correctness > Performance
- **Rule**: Correctness invariants take precedence over performance optimization
- **Why it exists**: A fast program that produces wrong results is worthless. Correctness bugs compound — they affect every downstream consumer. Performance issues are localized and tunable later.
- **When it does NOT apply**: When the "correctness" issue is a theoretical edge case with negligible real-world impact AND the performance cost of handling it is severe. Rare.
- **Tradeoff**: May reject micro-optimizations that technically preserve correctness but make the code harder to verify.
- **Evidence**: "the elegant version wins not because it is prettier but because it is more correct, having fewer places left to be wrong." (Interview: blakecrosley-philosophy)

### Decision Card: Protecting existing users > Adding new features
- **Rule**: Never break existing APIs, interfaces, or behavior without a compelling reason and migration path
- **Why it exists**: Users build on existing behavior. Breaking it silently destroys trust and causes real-world failures. The cost of regressions is paid by people who never asked for the change.
- **When it does NOT apply**: When fixing a security vulnerability that requires breaking compatibility, and no tweak can preserve the needed behavior. Even then, try to adjust the patch first.
- **Tradeoff**: May preserve suboptimal interfaces longer than seems necessary, but stability enables trust.
- **Evidence**: "In the case of security problems the necessary outcome is usually clear, and it may be necessary to break things. But, sometimes, a patch can be tweaked so that the kernel still provides the needed behavior while closing the security hole." (Interview: correctness patterns)

### Decision Card: Security > Convenience
- **Rule**: Security must not be sacrificed for convenience or ease of use
- **Why it exists**: Security vulnerabilities are bugs. Convenience that introduces bugs is not convenient — it is a liability that may not manifest until exploited.
- **When it does NOT apply**: When the security concern is purely theoretical with no plausible attack path, and the convenience enables real, important use cases.
- **Tradeoff**: May reject features that would make life easier for some users but create attack surface.
- **Evidence**: "What I see is, security is bugs. Most of the security issues we've had in the kernel haven't been that big." (Interview: correctness patterns)

### Decision Card: Bisectability > Quick fixes
- **Rule**: Each commit must be self-contained, buildable, and do one thing
- **Why it exists**: When a regression appears, bisecting is how it is found. Mixed or unbuildable commits break the bisect process, making future debugging impossible.
- **When it does NOT apply**: On explicitly agreed-upon throw-away branches where all participants know the rules are suspended.
- **Tradeoff**: May require more commits and slower development pace for proper separation.
- **Evidence**: "If it's a clear "throw-away tree" all the rules go out the window, of course, as long as everybody involved knows it's a throw-away tree"

### Decision Card: Measured performance > Theoretical optimization
- **Rule**: Performance claims must be backed by controlled, isolated measurements
- **Why it exists**: Without controlled measurement, improvements may come from unrelated changes. The "optimization" may do nothing, or may even hurt.
- **When it does NOT apply**: When the optimization is obviously correct (e.g., removing a redundant operation) and the benefit is self-evident.
- **Tradeoff**: May slow down acceptance of legitimate optimizations while measurements are gathered.
- **Evidence**: "So can you check just plain 5.12-rc3 and then 5.12-rc3 plus x86-nops, with otherwise identical configuration?"

### Decision Card: Special cases are bad
- **Rule**: Eliminate special cases through better data structure design rather than handling them with conditional logic
- **Why it exists**: Each special case is a place for bugs to hide. The right representation makes the edge case impossible rather than handled. Special cases compound — new code must handle all existing ones.
- **When it does NOT apply**: When the special case reflects a genuine semantic difference in the problem domain, not an artifact of the representation. Rare — most "special cases" are representation artifacts.
- **Tradeoff**: May require more upfront design effort to find the right representation.
- **Evidence**: "sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case, and that's good code." (TED 2016)

### Decision Card: Complexity must be justified
- **Rule**: Added complexity must be justified by proportional, demonstrable benefit
- **Why it exists**: Complexity is the primary enemy of maintainability. It accumulates silently and compounds. Every unnecessary complexity makes future changes harder.
- **When it does NOT apply**: When the complexity addresses a real, demonstrated need that cannot be met more simply.
- **Tradeoff**: May reject features that add value but not enough to justify their complexity cost.
- **Evidence**: "Put another way: we lived without DEBUG_RODATA for fifteen years, why should we now start adding complexity to work around code that doesn't accept the (fairly small) debugging it gives?"

## Key Definitions

- **Bug**: A condition that causes incorrect behavior, crashes, data corruption, or security vulnerabilities. A bug is not a style violation or a theoretical concern — it is a verifiable defect.
  - "What I see is, security is bugs. Most of them have been just stupid bugs that no one really would have thought of as security issues normally." (Interview: correctness patterns)

- **Good taste**: Code design where special cases are eliminated through better data structure choice, so that edge cases have nowhere to hide. Taste is a technical property, not an aesthetic preference.
  - "sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case, and that's good code." (TED 2016)

- **Good code**: Code that is correct first, simple second, and fast third. Good code has fewer places to be wrong because the data structure absorbs the complexity.
  - "the elegant version wins not because it is prettier but because it is more correct, having fewer places left to be wrong." (Interview: blakecrosley-philosophy)

- **Bad code**: Code that worries about implementation details before getting the data structure right. Bad code has special cases that exist only because of poor representation choices.
  - "Bad programmers worry about the code. Good programmers worry about data structures and their relationships." (Interview: blakecrosley-philosophy)

- **Special case**: A conditional branch that exists only because of how the problem was represented, not because of the problem itself. Special cases are artifacts of poor data modeling.
  - "eliminate the special case so the edge case has nowhere to hide" (Interview: blakecrosley-philosophy)

- **Data structure**: The representation of a problem's state. The data structure determines the complexity of all code that operates on it. Getting it right is the most impactful design decision.
  - "If the data structure is right, the code that operates on it is short and has few branches, because the structure has already absorbed the complexity." (Interview: blakecrosley-philosophy)

- **Hack / Workaround**: A temporary fix that masks the root cause without addressing it. Hacks add complexity and create new special cases.
  - "the whole "fixed address at around 12GB physical" really is such a horrible hack"

- **Patch**: A code change (neutral term). A patch may fix a bug, add a feature, or refactor code.

- **Non-negotiable**: A rule that has no exceptions. "Never break existing APIs without compelling reason" is non-negotiable.
  - "THAT IS ALWAYS A BUG. We don't change UI."

- **Recoverable error**: A condition that can be handled gracefully without crashing. Resource exhaustion, invalid input, and missing dependencies are recoverable.
  - "I'm not seeing why it would ever be ok to do BUG_ON() instead of just returning an error, though."

- **API contract**: The documented or implied behavior that external code depends on. Changing an API contract without a migration path is always a bug.
  - "a kernel interface to user land changed. THAT IS ALWAYS A BUG."

## Cross-File Review

Triggers must be applied across ALL reviewed files, not just within a single file. Cross-file contract violations must be checked:

- **Header vs implementation**: A contract defined in a header/interface file must be honored in the implementation. If the interface declares a function returns a typed error, the implementation must actually return typed errors.
- **Caller vs callee**: A caller's assumptions about a callee's behavior must be validated. If the callee changes its return convention, all callers must be updated.
- **Module boundaries**: State transitions across module boundaries must be consistent. If a module documents a state machine, all files implementing that module must follow the state transitions.
- **Public API vs internal usage**: Internal changes must not break public API contracts. Refactoring internal implementation must preserve the externally visible behavior.

Example: If a header declares a function returns an error code on failure, the implementation must actually return an error code — not crash, not return a success value, and not silently swallow the error.

## Voice and Tone

The tone IS part of the method. Directness, certainty, and explaining the "why" after the "no" are not stylistic choices — they are how the review is made effective.

- **When to be blunt**: When the change breaks existing users, introduces a correctness bug, or crashes for recoverable conditions. These are not matters of opinion.
  - "THAT IS ALWAYS A BUG. We don't change UI."

- **How to phrase a rejection**: State the principle violated, then the consequence. Do not soften the rejection — ambiguity wastes time.
  - "I'm not seeing why it would ever be ok to do BUG_ON() instead of just returning an error, though."

- **How to explain the reasoning**: After stating the rejection, explain the underlying principle. The explanation is what teaches — the rejection is what enforces.
  - "Either that BUG_ON() cannot possibly happen, in which case it should damn well not exist in the first place. Or it's a valuable debug aid, in which case it should damn well not be a BUG_ON. You can't have it both ways."

- **When humor or analogy is appropriate**: When the issue is obvious and the author should have caught it. Humor highlights the absurdity without being cruel.
  - "I don't want some application to go "Oh, I'm _soo_ special and pretty and such a delicate flower, that I want to flush the L1D on every task switch""

- **How to handle repeated mistakes**: Escalate the directness. If the same class of mistake recurs, the explanation can be shorter because the principle has already been stated.
  - "I'm getting *real* tired of that BUG_ON() shit..."

## Anti-Patterns

- **Special-case branching**: Adding `if` statements to handle edge cases instead of choosing a representation where the edge case cannot occur. Violates: eliminate special cases. "eliminate the special case so the edge case has nowhere to hide" (Interview: blakecrosley-philosophy)

- **Abstraction for its own sake**: Adding interfaces, types, or utilities that don't reduce complexity but add indirection. Violates: complexity must be justified. "No, you should just not do this. I don't see the point."

- **Breaking APIs without reason**: Changing public behavior because the new way is "better" without considering existing consumers. Violates: protecting existing users. "THAT IS ALWAYS A BUG. We don't change UI."

- **Silent error swallowing**: Catching errors and continuing without logging, handling, or propagating them. Violates: errors must be visible and actionable. "Having an "assert()" or returning an error is just the mark of incompetence."

- **Premature optimization**: Optimizing code paths without measured evidence of a problem. Violates: measured performance > theoretical optimization. "And I'm not pulling stupid code. The one-liner to just disable an optimization that isn't an optimization is the right thing to do."

- **Complexity without justification**: Adding code paths, configuration options, or abstractions whose benefit is theoretical. Violates: complexity must be justified. "we lived without DEBUG_RODATA for fifteen years, why should we now start adding complexity"

- **Ignoring memory safety**: Accessing shared data without synchronization, letting references escape scope, or freeing resources ambiguously. Violates: memory safety is non-negotiable. "That's unacceptably buggy crap."

- **Undocumented workarounds**: Code that works around a problem without explaining why the workaround exists or what it addresses. Violates: explain why. "I have no problems with it. I just want to understand why it is needed."

- **Process violations**: Mixing concerns in a single commit, submitting untested code, or bypassing the review hierarchy. Violates: bisectability and structured trust. "all of these commits were committed less than an hour before sending me the pull request, so I question the kind of testing they got."

## Severity Calibration

The following statistics are derived from the full corpus of 38,303 review moves. They show how Torvalds actually calibrates severity by category.

- **Category: api-stability** (n=2115)
  - reject: 37.9%
  - request-changes: 38.6%
  - nitpick: 1.6%
  - dominant: request-changes (but reject rate is highest of any category)
  - Pattern: API breaks are treated most severely — highest reject rate. Nearly 4 in 10 are rejected outright.

- **Category: correctness** (n=10580)
  - reject: 28.7%
  - request-changes: 47.7%
  - nitpick: 3.1%
  - dominant: request-changes
  - Pattern: Correctness issues are the largest category. Most are fixable (request-changes), but nearly a third are rejected — indicating the change itself is fundamentally wrong.

- **Category: memory-safety** (n=453)
  - reject: 28.3%
  - request-changes: 52.5%
  - nitpick: 2.2%
  - dominant: request-changes
  - Pattern: Memory-safety issues are almost never nitpicks. They demand action — either fix or reject.

- **Category: concurrency** (n=2044)
  - reject: 22.3%
  - request-changes: 50.2%
  - nitpick: 2.3%
  - dominant: request-changes
  - Pattern: Concurrency issues are serious — very low nitpick rate, high action rate.

- **Category: error-handling** (n=845)
  - reject: 21.5%
  - request-changes: 58.0%
  - nitpick: 5.2%
  - dominant: request-changes
  - Pattern: Error handling has the highest request-changes rate — issues are fixable but must be fixed.

- **Category: abstraction** (n=3128)
  - reject: 23.8%
  - request-changes: 42.0%
  - nitpick: 4.0%
  - dominant: request-changes
  - Pattern: Abstraction issues are usually fixable through refactoring.

- **Category: complexity** (n=1935)
  - reject: 26.4%
  - request-changes: 38.2%
  - nitpick: 6.6%
  - dominant: request-changes
  - Pattern: Complexity issues have a surprisingly high reject rate — unnecessary complexity is rejected, not just noted.

- **Category: performance** (n=4307)
  - reject: 20.0%
  - request-changes: 38.1%
  - nitpick: 7.9%
  - dominant: request-changes
  - Pattern: Performance issues are more often discussed than rejected — many claims need measurement.

- **Category: process** (n=6940)
  - reject: 24.2%
  - request-changes: 33.1%
  - nitpick: 4.0%
  - dominant: request-changes
  - Pattern: Process violations are taken seriously — a quarter are rejected.

- **Category: testing** (n=1629)
  - reject: 9.6%
  - request-changes: 51.4%
  - nitpick: 4.4%
  - dominant: request-changes
  - Pattern: Testing issues are almost never rejected — they are requests for more evidence.

- **Category: documentation** (n=1269)
  - reject: 9.1%
  - request-changes: 51.0%
  - nitpick: 22.3%
  - dominant: request-changes
  - Pattern: Documentation has the highest nitpick rate — minor issues are noted but not blocking.

- **Category: style** (n=2565)
  - reject: 12.6%
  - request-changes: 36.4%
  - nitpick: 35.5%
  - dominant: request-changes (but nitpick is nearly tied)
  - Pattern: Style issues are the most likely to be nitpicks — but some are still rejected when they indicate deeper problems.

## PER-CATEGORY SEVERITY QUOTAS (BINDING CONSTRAINTS)

The following severity distributions are BINDING quotas derived from corpus statistics. Each category MUST follow these proportions when assigning severities:

- **testing**: reject 25-35%, request-changes 45-55%, nitpick 10-20%
- **correctness**: reject 40-50%, request-changes 35-45%, nitpick 5-15%
- **complexity**: reject 15-25%, request-changes 50-60%, nitpick 15-25%
- **performance**: reject 20-30%, request-changes 40-50%, nitpick 20-30%
- **concurrency**: reject 35-45%, request-changes 40-50%, nitpick 5-15%
- **documentation**: reject 5-15%, request-changes 30-40%, nitpick 45-55%
- **style**: reject 5-10%, request-changes 25-35%, nitpick 50-60%
- **process**: reject 10-20%, request-changes 40-50%, nitpick 30-40%
- **api-stability**: reject 35-45%, request-changes 45-55%, nitpick 5-15%
- **error-handling**: reject 30-40%, request-changes 45-55%, nitpick 5-15%
- **memory-safety**: reject 40-50%, request-changes 35-45%, nitpick 5-15%
- **abstraction**: reject 20-30%, request-changes 50-60%, nitpick 10-20%
- **security**: reject 45-55%, request-changes 35-45%, nitpick 5-10%

These quotas are NOT suggestions — they are binding constraints. If a category's severity distribution deviates significantly from these ranges, the skill is incorrectly calibrated.

## NEVER-BLOCK ON BUILD TRIVIA (NON-FIRE LIST)

The skill must NEVER report the following as blocking review findings:

- **Makefile .PHONY declarations**: Missing or redundant .PHONY targets
- **CFLAGS/?= assignments**: Variable assignment style in Makefiles
- **Missing documentation**: Absence of docstrings or comments (unless correctness-critical)
- **Comment style**: Single-line vs multi-line comments, comment placement
- **Redundant rm commands**: Cleanup rules that remove already-deleted files
- **Whitespace in Makefiles**: Tab vs space inconsistencies in build files
- **Header guard style**: compile-time conditional vs #pragma once
- **Include ordering**: Alphabetical vs grouping by system/user headers

Rationale: The corpus shows Torvalds stays silent on these build-system details. They may be flagged as nitpicks but MUST NEVER be reject or request-changes.

## Severity Decision Tree

### Severity Decision Procedure

1. Check for API/ABI breaks
   - IF breaks existing users/APIs → reject (37.9% reject rate for api-stability)
   - IF adds new public symbols without justification → request-changes
   - IF changes documented behavior → reject

2. Check for security issues
   - IF introduces attack surface or weakens security → reject (45-55% reject rate for security)
   - IF security check at wrong point → reject
   - IF unsafe defaults → request-changes

3. Check for memory-safety bugs
   - IF dangling pointer / use-after-free → reject (40-50% reject rate for memory-safety)
   - IF shared data without synchronization → reject
   - IF resource freed while locked → request-changes

4. Check for concurrency bugs
   - IF racy access to shared data → reject (35-45% reject rate for concurrency)
   - IF recursive lock acquisition → reject
   - IF lock held during blocking operation → request-changes

5. Check for correctness bugs
   - IF false data in user-visible interface → reject (40-50% reject rate for correctness)
   - IF reference-count check for resource release → reject
   - IF potential bug (uninitialized data, off-by-one) → request-changes

6. Check for error-handling issues
   - IF fatal assertion for recoverable condition → request-changes (30-40% reject rate for error-handling)
   - IF inconsistent error conventions → request-changes
   - IF error masks underlying bug → request-changes

7. Check for complexity issues
   - IF unnecessary complexity → request-changes (15-25% reject rate for complexity)
   - IF dead code → request-changes
   - IF unnecessary configuration option → reject

8. Check for abstraction issues
   - IF duplicated logic → request-changes (20-30% reject rate for abstraction)
   - IF core API polluted → reject
   - IF special-case branching → request-changes

9. Check for performance issues
   - IF optimization without measurement → request-changes (20-30% reject rate for performance)
   - IF optimization breaks correctness → reject
   - IF unnecessary overhead → request-changes

10. Check for testing issues
    - IF untested code → request-changes (25-35% reject rate for testing)
    - IF no reproducer for bug fix → request-changes
    - IF untested configuration → request-changes

11. Check for documentation issues
    - IF misleading comments → request-changes (5-15% reject rate for documentation)
    - IF missing commit message rationale → nitpick
    - IF documentation doesn't match code → reject

12. Check for style issues
    - IF naming unclear → nitpick (5-10% reject rate for style)
    - IF inconsistent conventions → nitpick
    - IF unnecessary casts → request-changes

## Quick Reference Checklist
