---
name: linus-torvalds-skill
description: "A code review method distilled from Linus Torvalds' reviewing patterns across 38,000+ review moves and 500+ interview passages, teaching reviewers to eliminate special cases, protect existing users, reject recoverable crashes, and demand evidence over theory."
metadata:
  author: "torvalds-skill pipeline"
  version: "1.0.0"
  tags:
    - code-review
    - reviewer-method
    - torvalds
---

# Linus Torvalds Review Method

> This skill distills Linus Torvalds' code reviewing method from a corpus of 38,303 review moves and 500+ interview passages, sampled into 350 representative patterns across 14 categories. The method is entirely language- and project-agnostic: it describes design problems, not syntax problems, and applies equally to a reviewer reading Python, Go, Rust, TypeScript, Java, or any other language. No C-specific or kernel-specific constructs appear in triggers or principles; verbatim quotes preserve original wording as evidence of voice and tone only.

## Reviewer Mindset

The reviewer's mindset is not a set of rules but a disposition — a way of seeing code that determines which rules apply and when. Torvalds' approach is grounded in several core attitudes, each supported by his own reflective statements.

1. **Say no by default.** Reviewers exist to prevent bad code from merging, not to approve everything that arrives. Rejection is the default; acceptance must be earned.
   - "my job is to say no." (Interview: ars-2015-not-nice)
   - *Why it matters:* A reviewer who defaults to approval becomes a rubber stamp. The value of review is the filter, not the gate.

2. **Code is binary — it works or it doesn't.** Do not accept "mostly works" or "works in practice." Correctness is not a spectrum.
   - "code either works or it doesn't" (Interview: business-insider-2014-qa)
   - *Why it matters:* Treating correctness as negotiable invites subtle bugs that compound over time. A bug that "usually doesn't happen" is still a bug.

3. **Prefer boring, stable code over exciting features.** New features that break existing users are the enemy of reliability.
   - "I like boring... boring to me is no super exciting new features that will break machines for millions of people around the world." (Interview: TED 2016)
   - *Why it matters:* Stability is the foundation that everything else builds on. Flashy features that destabilize the system cost more than they deliver.

4. **Demand evidence, not theory.** A design is a hypothesis; only running, tested code settles the argument.
   - "Talk is cheap. Show me the code." (Interview: blakecrosley-philosophy, citing LKML 2000)
   - *Why it matters:* Theoretical arguments about performance, safety, or design can be wrong in ways that only implementation reveals. Code is the experiment.

5. **Be direct, not subtle.** Vague feedback wastes everyone's time and leads to misunderstandings.
   - "it can be much healthier to say 'hell no' at the outset and be sure that people understand" (Interview: ars-2015-not-nice)
   - *Why it matters:* Subtlety in written communication causes misinterpretation. Clear, direct feedback — even when blunt — is more efficient and more respectful than polite ambiguity.

6. **Structure trust; don't assume it.** At scale, you cannot personally verify everything, so trust must be built into the process.
   - "Trust at scale has to be structured, not assumed. Torvalds solved it twice – a maintainer tree for who is accountable, a tamper-evident history for what happened." (Interview: blakecrosley-philosophy)
   - *Why it matters:* A reviewer who tries to verify everything personally becomes a bottleneck. Delegating to trusted maintainers with clear accountability scales; ad-hoc trust does not.

7. **Fix interfaces to prevent bugs, not just patch them.** When bugs recur, the interface itself is likely the problem.
   - "fixing interfaces to make it harder to write bugs by mistake" (Interview: blakecrosley-philosophy)
   - *Why it matters:* If an interface makes it easy to write a particular bug, every new user of that interface will write the same bug. Fixing the interface fixes the class of bugs permanently.

## Review Triggers

### Theme: Eliminating Special Cases

The central principle of Torvalds' method: when code contains a special-case branch, the data model is likely wrong. Fix the representation, and the special case disappears — along with the bug it would have introduced.

- **Trigger**: Code contains a conditional branch that exists only to handle the first element, empty case, or boundary of a data structure
  - **Type**: general-guideline
  - **What to look for**: An `if` statement that checks whether an element is the head, first, or boundary case, with separate logic for that case versus the general case
  - **Why it's a problem**: The special case exists because the data model treats the boundary as different. A better representation (e.g., an indirection that makes the boundary identical to every other element) eliminates the branch entirely, which eliminates the class of bugs that branch could contain
  - **Severity**: request-changes
  - **Example**: "sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case, and that's good code." (TED 2016)

- **Trigger**: Code adds a new special-case branch to handle a situation that an existing special case already covers
  - **Type**: invariant-false
  - **What to look for**: A new conditional that handles a variant of an existing special case, rather than refactoring to eliminate the original special case
  - **Why it's a problem**: Each new special case multiplies the number of code paths that must be tested and maintained. The goal is to reduce special cases, not add to them
  - **Severity**: request-changes
  - **Example**: "Maybe we should just strive to get rid of all these SYSTEM_BOOTING special cases, instead of adding yet another a new one."

- **Trigger**: A function or operation is special-cased for a single variant when all similar operations follow a uniform pattern
  - **Type**: invariant-false
  - **What to look for**: One operation in a family of similar operations takes an extra parameter, follows a different code path, or has different semantics, with no structural reason for the difference
  - **Why it's a problem**: Special-casing one operation breaks the consistency contract of the interface. Every caller must learn the exception, and every future operation must decide whether to follow the rule or the exception
  - **Severity**: reject
  - **Example**: "Why the *hell* would mkdir() be so magical as to need something like that? ... What makes mkdir() so magical? Also, what about all the other ops?"

- **Trigger**: Code uses configuration markers or flags to compensate for an ordering bug or structural problem
  - **Type**: invariant-false
  - **What to look for**: A new flag, marker, or configuration option whose sole purpose is to work around incorrect ordering or a structural deficiency
  - **Why it's a problem**: The marker masks the root cause instead of fixing it. The ordering bug still exists; the marker just hides it until someone forgets to set it
  - **Severity**: reject
  - **Example**: "So the whole 'add DT markers because the subsystem now screws up ordering' smells really bad to me."

- **Trigger**: Code handles an edge case by adding logic rather than by changing the data representation so the edge case cannot occur
  - **Type**: general-guideline
  - **What to look for**: A branch that handles an edge case (null, empty, boundary, first/last) that could be eliminated by choosing a different data structure or representation
  - **Why it's a problem**: The edge case is not inherent to the problem — it is an artifact of the representation. Eliminating it at the representation level removes the branch and all bugs it could introduce
  - **Severity**: request-changes
  - **Example**: "eliminate the special case so the edge case has nowhere to hide" (Interview: blakecrosley-philosophy)

### Theme: API and Interface Stability

Existing users and their working code are sacred. Breaking them — even for a good reason — requires a compelling justification and a migration path.

- **Trigger**: Change breaks existing, documented, or publicly visible behavior
  - **Type**: invariant-false
  - **What to look for**: Any change that alters the observable behavior of a public interface, including return values, error codes, output format, or side effects that external code may depend on
  - **Why it's a problem**: Existing users did not consent to having their code broken. Every breakage forces every consumer to audit and fix their code, and some will not discover the breakage until production
  - **Severity**: reject
  - **Example**: "In other words, a kernel interface to user land changed. THAT IS ALWAYS A BUG. We don't change UI."

- **Trigger**: Change removes or alters output that users, scripts, or documentation may depend on
  - **Type**: invariant-false
  - **What to look for**: Removal of lines from output, renaming of fields, or changes to the format of user-visible data
  - **Why it's a problem**: Even seemingly internal output may be consumed by scripts, monitoring tools, or documentation. Removing it silently breaks those consumers
  - **Severity**: reject
  - **Example**: "No, that would be much *more* trouble-some, because we have things like bug-reporting documentation that tells people to send /proc/iomem etc information on crashes. There may well be scripts like that out there."

- **Trigger**: Change to a public data layout that affects binary compatibility
  - **Type**: invariant-false
  - **What to look for**: Adding, removing, or reordering fields in a public structure, or changing alignment requirements
  - **Why it's a problem**: Binary compatibility breaks silently — code compiles but behaves incorrectly at runtime. The breakage may not surface until the code runs on a different platform or configuration
  - **Severity**: request-changes
  - **Example**: "I do keep coming back to the fact that we should *probably* just do something like typedef unsigned long long __attribute__((aligned(8))) __u64; and then introduce a separate 'u64_unaligned' type for all the legacy cases that depended on 32-bit alignment."

- **Trigger**: Proposal to add a new public interface when an existing interface could be extended
  - **Type**: precedence-rule
  - **What to look for**: A new function, method, endpoint, or configuration option that duplicates the purpose of an existing one with a minor variation
  - **Why it's a problem**: Every new public interface is a permanent maintenance burden. Extending an existing interface (e.g., adding a flag) is cheaper and keeps the surface area small
  - **Severity**: request-changes
  - **Example**: "So it's much simpler and more straightforward to just introduce a single new bit #2 that says 'I actually know what I'm doing, and I'm explicitly asking for secure/insecure random data'."

- **Trigger**: Internal implementation details exposed through a public interface
  - **Type**: invariant-false
  - **What to look for**: A public API that accepts or returns internal data structures, type annotations that leak implementation details, or interfaces that require callers to understand internal layout
  - **Why it's a problem**: Exposing internals freezes the implementation — any future refactoring of the internal structure becomes a breaking change
  - **Severity**: request-changes
  - **Example**: "What this does is get rid of the horrible notion of having that struct inode *ptmx_inode be the interface between the pty code and devpts."

- **Trigger**: Function returns a value that is ambiguous between success and failure
  - **Type**: invariant-false
  - **What to look for**: A function that returns zero for failure and a non-zero value that could also be a valid success result, or that returns the same value for both success and failure in different contexts
  - **Why it's a problem**: Callers cannot reliably distinguish success from failure. Bugs from misinterpreting the return value are inevitable
  - **Severity**: reject
  - **Example**: "Returning zero from a write is basically insanity. It's not a valid error case."

### Theme: Error Handling and Recovery

Recoverable errors must be handled gracefully. Fatal crashes are for unrecoverable conditions only.

- **Trigger**: Fatal assertion or crash used for a condition that can be triggered by external input or runtime state
  - **Type**: invariant-false
  - **What to look for**: A panic, abort, or fatal assertion in a code path that handles user input, external data, or any condition that could arise during normal operation
  - **Why it's a problem**: Crashing on recoverable input is not "safe" — it is a denial of service. The correct response is to return an error and let the caller decide what to do
  - **Severity**: reject
  - **Example**: "I'm getting *real* tired of that BUG_ON() shit... Killing the machine for idiotic things like that is truly offensive... Either that BUG_ON() cannot possibly happen, in which case it should damn well not exist in the first place. Or it's a valuable debug aid, in which case it should damn well not be a BUG_ON. You can't have it both ways."

- **Trigger**: Error handling that aborts or traps on a recoverable condition instead of returning an error
  - **Type**: invariant-false
  - **What to look for**: Code that calls abort, exit, or trap when it encounters an overflow, missing resource, or invalid input that could be reported to the caller
  - **Why it's a problem**: Aborting removes the caller's ability to handle the error. A library or module that aborts on recoverable conditions makes the entire system fragile
  - **Severity**: reject
  - **Example**: "Side note: this is the same kind of complete and utter idiocy that made Rust people have allocators that abort when running out of memory, because it's 'safer' than returning NULL. THAT KIND OF THINKING IS NOT ACCEPTABLE."

- **Trigger**: Function returns an error code that callers cannot meaningfully act on
  - **Type**: general-guideline
  - **What to look for**: A function that returns an error for a condition the caller can neither prevent nor recover from (e.g., returning an error because an internal resource is missing)
  - **Why it's a problem**: Callers are forced to handle errors they cannot fix, adding complexity without value. If the caller cannot act on the error, the function should handle it internally
  - **Severity**: request-changes
  - **Example**: "The whole 'sysfs_create_file()' thing is an example of that. If it fails, it fails. The caller can't do anythign about it anyway, except perhaps print a message. Why the hell does such a function have the 'right' to dictate what the user should do?"

- **Trigger**: Error handling path that masks or hides the underlying bug
  - **Type**: invariant-false
  - **What to look for**: Code that adds bounds checks, precision limits, or validation specifically to prevent a crash that would reveal a bug, rather than fixing the bug
  - **Why it's a problem**: The bug still exists — it is just silent. The validation code makes the bug harder to find because the crash that would have revealed it is suppressed
  - **Severity**: request-changes
  - **Example**: "All that precision code could ever do was to potentially hide bugs if the string wasn't NUL-terminated."

- **Trigger**: Warning assertion used where a one-time warning is more appropriate
  - **Type**: general-guideline
  - **What to look for**: A warning that fires repeatedly for the same condition, flooding logs, when the condition is a "serious bug but should never happen" situation
  - **Why it's a problem**: Repeated warnings train developers to ignore them. A one-time warning surfaces the problem without noise
  - **Severity**: request-changes
  - **Example**: "please make it a WARN_ON_ONCE(), just on basic principles. I can't imagine this happening a lot, but at the same time I don't think there's any reason _not_ to just always use WARN_ON_ONCE() for these kinds of 'serious bug, but should never happen' situations."

- **Trigger**: Code rejects commonly used input values that exceed nominal limits
  - **Type**: invariant-false
  - **What to look for**: Validation that rejects values like -1, 0, or maximum values that are commonly used in practice (e.g., to set all bits)
  - **Why it's a problem**: Users who rely on these values will experience silent failures. Validation should not break established usage patterns
  - **Severity**: reject
  - **Example**: "It's entirely possible that people end up doing something like echo -1 > /proc/sys/some_random_uint because that's a fairly normal thing to do to set all bits. Making that an error seems wrong."

### Theme: Concurrency and Synchronization

Shared mutable state requires explicit synchronization. Relying on compiler ordering, implicit guarantees, or "it usually works" is a bug.

- **Trigger**: Shared mutable data accessed from multiple threads without explicit synchronization
  - **Type**: invariant-false
  - **What to look for**: A variable or data structure read and written from multiple threads without locks, atomic operations, or memory ordering primitives
  - **Why it's a problem**: Without synchronization, the CPU and compiler may reorder reads and writes in ways that produce incorrect results. The code may appear to work in testing and fail in production
  - **Severity**: reject
  - **Example**: "The reason it is buggy has absolutely nothing to do with whether the read is done or not, it has to do with the fact that the CPU may re-order the reads regardless of whether the read is done in some specific order by the compiler or not! ... The above kind of code needs memory barriers to be non-buggy."

- **Trigger**: Flag variable shared between threads accessed without atomic or ordering primitives
  - **Type**: invariant-false
  - **What to look for**: A boolean or flag variable read on one thread and written on another without using atomic read/write or acquire/release semantics
  - **Why it's a problem**: Even a simple flag read/write can be reordered or torn. The fix is to use explicit atomic operations with appropriate ordering semantics
  - **Severity**: request-changes
  - **Example**: "If you have a single value that acts as a flag, use READ_ONCE/WRITE_ONCE to show that there's no relevant locking. In fact, better yet, use 'smp_store_release()' to set the flag and 'smp_load_acquire()' to read it."

- **Trigger**: Lock acquired in a different order in different code paths
  - **Type**: invariant-false
  - **What to look for**: Two or more locks that are acquired in opposite orders in different functions, creating a potential deadlock
  - **Why it's a problem**: If two threads execute the two paths simultaneously, each holds a lock the other needs, causing a permanent deadlock
  - **Severity**: reject
  - **Example**: "The common way to avoid AB-BA deadlocks in any threaded code (whether kernel or user space) is to just take two locks in a specific order, and the common way to do that for locks of the same type is simply to compare the addresses)."

- **Trigger**: Attempt to upgrade a read lock to a write lock
  - **Type**: invariant-false
  - **What to look for**: Code that holds a read lock and then attempts to acquire a write lock on the same resource
  - **Why it's a problem**: Two readers can both attempt to upgrade simultaneously, blocking each other forever. Read-lock upgrade is fundamentally impossible and will deadlock
  - **Severity**: reject
  - **Example**: "Upgrading a read lock is fundamentally impossible and will deadlock trivially (think just two readers that both want to do the upgrade – they'll block each other from doing so). So it's not actually a possible operation."

- **Trigger**: Resource freed while a lock is still held
  - **Type**: invariant-false
  - **What to look for**: An error-handling path that jumps to a cleanup label that frees resources, but the lock was acquired before the jump and is not released before the cleanup
  - **Why it's a problem**: The freed resource may be accessed by another thread that is waiting on the lock. The lock must be released before any resource it protects is freed
  - **Severity**: request-changes
  - **Example**: "You still have 'goto err' for cases that have the ctx locked. Which means that the thing gets free'd while still locked, which causes problems for lockdep etc, so don't do it."

- **Trigger**: Lock held while calling code that may block or attempt to acquire the same lock
  - **Type**: invariant-false
  - **What to look for**: A function that holds a lock and then calls another function that may sleep, schedule work, or attempt to acquire the same lock
  - **Why it's a problem**: If the called code blocks, it may hold the lock indefinitely, starving other threads. If it attempts the same lock, it deadlocks
  - **Severity**: request-changes
  - **Example**: "Now that's fine - as long as we never take that lock inside any delayed work - because then the delayed work itself may need the lock we hold in order to complete, and now the 'cancel_delayed_work_sync()' thing might deadlock."

### Theme: Memory Safety and Resource Management

Every allocated resource must have a clear owner, a defined lifetime, and a correct release path. Reference counting must be atomic and unambiguous.

- **Trigger**: Shared object accessed from multiple threads without reference counting
  - **Type**: invariant-false
  - **What to look for**: A data structure used by more than one thread or execution context without a reference count to manage its lifetime
  - **Why it's a problem**: Without a reference count, one thread may free the object while another is still using it. The object's lifetime is ambiguous, and use-after-free bugs are inevitable
  - **Severity**: request-changes
  - **Example**: "Side note: this is pretty much true of any kernel data structure. If you have a kernel data structure that isn't just used within one thread, it must be refcounted."

- **Trigger**: Reference to a stack-allocated object stored or accessed after the function returns
  - **Type**: invariant-false
  - **What to look for**: A function that stores a pointer or reference to a local variable in a data structure that outlives the function call
  - **Why it's a problem**: After the function returns, the stack frame is deallocated. The stored reference is now a dangling pointer, and accessing it causes undefined behavior
  - **Severity**: reject
  - **Example**: "That's unacceptably buggy crap. rpc_wait_for_completion_task() will happily exit on a deadly signal even if the rpc hasn't been completed, so now you'll have a stale pointer to a stack that has been freed."

- **Trigger**: Resource freed based on a non-atomic or ambiguous reference count check
  - **Type**: invariant-false
  - **What to look for**: A deallocation decision based on a check like "refcount is zero or list is empty" rather than a pure atomic reference count
  - **Why it's a problem**: A compound check can race: both threads see the condition as true and both free the resource, causing a double-free
  - **Severity**: request-changes
  - **Example**: "You're right because it would be a double-free - both parties would decide that they can free the damn thing, because it's not a pure atomic refcount, it's a 'refcount or list_empty()' thing."

- **Trigger**: Code loses track of how memory was allocated and later tries to infer the allocation method
  - **Type**: invariant-false
  - **What to look for**: Code that allocates memory in one place and later, at deallocation time, tries to determine how it was allocated (e.g., by checking flags or type metadata)
  - **Why it's a problem**: If the allocation method is not tracked explicitly, the deallocation method may be wrong, causing corruption or leaks. The allocation provenance must be explicit
  - **Severity**: reject
  - **Example**: "Ugh, that XFS code is _broken_. Instead of keeping track of how it got the memory, it totally forgets where the memory came from, and then it later asks 'oh, btw, how the hell did I allocate this?'"

- **Trigger**: Large stack allocations in a single function frame
  - **Type**: general-guideline
  - **What to look for**: A function that allocates large arrays or structures on the stack, especially in deeply nested call chains
  - **Why it's a problem**: Stack space is limited. Large frames can overflow the stack, especially in recursive or deeply nested paths, causing crashes that are hard to diagnose
  - **Severity**: request-changes
  - **Example**: "Because a 1kB stack frame is horrendous ... And no, ... is not an excuse for one single level to use up 1kB, much less 2kB."

- **Trigger**: Object accessed or released after its reference count has dropped to zero
  - **Type**: invariant-false
  - **What to look for**: Code that looks up an object and then uses or releases it without verifying the reference count is still positive
  - **Why it's a problem**: Between the lookup and the use, another thread may have decremented the count to zero and freed the object. The lookup must atomically increment the count
  - **Severity**: reject
  - **Example**: "Well, with my patch, there's no way you'll ever look up an object with a zero refcount, so you'll never release it twice. The atomic operations (atomic_inc_nonzero()) do guarantee that."

### Theme: Complexity and Simplicity

The simplest solution that works is the best solution. Complexity must be justified by measurable benefit.

- **Trigger**: Change adds complexity for marginal or unproven benefit
  - **Type**: general-guideline
  - **What to look for**: A patch that adds significant code, configuration options, or abstraction layers for a benefit that is theoretical, marginal, or unmeasured
  - **Why it's a problem**: Complexity is a permanent cost. If the benefit does not clearly outweigh the maintenance burden, the complexity should not be added
  - **Severity**: request-changes
  - **Example**: "Put another way: we lived without DEBUG_RODATA for fifteen years, why should we now start adding complexity to work around code that doesn't accept the (fairly small) debugging it gives?"

- **Trigger**: Custom solution created when an existing, well-tested solution already exists
  - **Type**: precedence-rule
  - **What to look for**: A new implementation of functionality that already exists in the codebase or standard library, without a clear reason why the existing solution is inadequate
  - **Why it's a problem**: The custom solution is untested, duplicates maintenance burden, and may contain bugs the existing solution already fixed. Reuse first; create only when reuse is impossible
  - **Severity**: request-changes
  - **Example**: "Can we please not duplicate complicated logic like that? IOW, just make a helper function for it."

- **Trigger**: Change adds a new configuration option that increases user burden
  - **Type**: invariant-false
  - **What to look for**: A new configuration option, setting, or build flag that users must understand and set correctly, when the behavior could be determined automatically
  - **Why it's a problem**: Every configuration option is a decision the user must make correctly. If the right answer can be determined automatically, forcing the user to choose adds burden without value
  - **Severity**: reject
  - **Example**: "No. Dammit, stop doing these horrible things."

- **Trigger**: Code that is more complex than necessary to solve the problem
  - **Type**: general-guideline
  - **What to look for**: A patch that uses a complex approach when a simpler one achieves the same result — e.g., a multi-step algorithm where a single operation suffices
  - **Why it's a problem**: Complexity creates bugs. The simpler the code, the fewer places there are for bugs to hide
  - **Severity**: request-changes
  - **Example**: "Your patch is horribly ugly. How about this (much simpler) patch instead? It just sets the 'max' to zero if pos in NULL in the caller. That just seems a much better/saner approach."

- **Trigger**: Dead or unused code paths retained "just in case"
  - **Type**: general-guideline
  - **What to look for**: Code that is never executed, or fallback paths that have no users, kept in the codebase without a clear plan for future use
  - **Why it's a problem**: Dead code increases the maintenance surface, confuses readers, and may rot into incorrectness. If it has no users, remove it; it can be restored from version control if needed
  - **Severity**: request-changes
  - **Example**: "But if there are no actual users of get_random_bytes_arch(), maybe we can just remove the fallback to the non-arch code, and add that return value (and the __must_check())."

### Theme: Performance and Measurement

Performance claims require measurement. Theoretical optimization is not optimization.

- **Trigger**: Performance claim made without controlled measurement
  - **Type**: general-guideline
  - **What to look for**: A claim that a change improves performance, based on uncontrolled comparison (e.g., different versions, different configs, different hardware)
  - **Why it's a problem**: Without controlled measurement, the apparent improvement may come from unrelated changes. The "optimization" may actually be a regression
  - **Severity**: request-changes
  - **Example**: "That's 2.5% - a huge difference. Particularly since kernel build times shouldn't even be that kernel-intensive. I think there's something else going on than the nops. Same config? There are likely many other differences between 5.10.19 and 5.12-rc3. So can you check just plain 5.12-rc3 and then 5.12-rc3 plus x86-nops, with otherwise identical configuration?"

- **Trigger**: Optimization that adds complexity without measurable benefit
  - **Type**: invariant-false
  - **What to look for**: Code that introduces abstraction, indirection, or complexity specifically for performance, without evidence that the performance matters
  - **Why it's a problem**: The complexity is a permanent cost; the performance benefit may be illusory. Only optimize when measurement shows the optimization is needed
  - **Severity**: reject
  - **Example**: "And I'm not pulling stupid code. The one-liner to just disable an optimization that isn't an optimization is the right thing to do."

- **Trigger**: Design that causes unpredictable latency spikes under load
  - **Type**: invariant-false
  - **What to look for**: Code that depends on scheduler timing, heuristic delays, or eventual consistency to maintain correctness, where the "eventual" may be very long under load
  - **Why it's a problem**: Latency spikes are worse than slow average performance. Users can adapt to consistent slowness; unpredictable pauses break real-time systems and user experience
  - **Severity**: reject
  - **Example**: "I suspect we could have some serious latency spikes."

- **Trigger**: Unprivileged code allowed to trigger expensive system-wide operations
  - **Type**: invariant-false
  - **What to look for**: An interface that lets any caller request a costly operation (e.g., cache flush, global synchronization) without checking whether the operation is necessary
  - **Why it's a problem**: A single caller can degrade system-wide performance for everyone. Expensive operations must be gated by necessity and privilege
  - **Severity**: reject
  - **Example**: "I don't want some application to go 'Oh, I'm _soo_ special and pretty and such a delicate flower, that I want to flush the L1D on every task switch, regardless of what CPU I am on, and regardless of whether there are errata or not'."

- **Trigger**: Redundant work performed because related operations are not combined
  - **Type**: general-guideline
  - **What to look for**: Two operations that modify the same data or walk the same data structure, performed sequentially when they could be combined into a single pass
  - **Why it's a problem**: The second pass re-does work the first pass already did. Combining them halves the cost
  - **Severity**: request-changes
  - **Example**: "that's absolutely something that we probably should do at the same time as moving the stack, so that we don't end up walking - and changing - the page tables twice."

### Theme: Security as Bugs

Security vulnerabilities are bugs. Treat them with the same engineering rigor as any other bug — no more, no less.

- **Trigger**: Security check performed at the wrong point in the code path
  - **Type**: invariant-false
  - **What to look for**: A permission or identity check performed at use time rather than at open or acquisition time, where the execution context may have changed between the two
  - **Why it's a problem**: Between open and use, the execution context may change (e.g., process fork, setuid). The check at use time validates the wrong context
  - **Severity**: reject
  - **Example**: "Just do the damn thing right, like /proc/kallsyms does these days. With the proper open time cred check, not the wrong one at io time."

- **Trigger**: Security-critical state initialized after functionality is exposed to untrusted parties
  - **Type**: invariant-false
  - **What to look for**: Code that exposes interfaces or accepts untrusted input before all security-critical initialization (e.g., entropy, keys, permissions) is complete
  - **Why it's a problem**: An attacker who reaches the interface before initialization completes can exploit the uninitialized state
  - **Severity**: reject
  - **Example**: "If you let attackers in before you've set the clock on the device, you're doing something seriously wrong."

- **Trigger**: Security mechanism that is easy to get wrong in subtle ways
  - **Type**: general-guideline
  - **What to look for**: A new security feature whose correctness depends on subtle ordering, timing, or state assumptions that are not obviously enforced
  - **Why it's a problem**: Security code that is subtly wrong is worse than no security code, because it creates a false sense of protection. Subtle security code requires extreme vetting
  - **Severity**: request-changes
  - **Example**: "And security issues in particular are often *very* subtle... it turns out it's damn easy to get it wrong in all kinds of small subtle details."

- **Trigger**: Feature that introduces known security risks (e.g., ambiguous input handling)
  - **Type**: invariant-false
  - **What to look for**: A new feature that accepts input in a form known to be exploitable (e.g., homoglyphs in URLs, ambiguous encodings, unvalidated external data)
  - **Why it's a problem**: The risk is known and documented. Adding the feature creates a vulnerability class that will eventually be exploited
  - **Severity**: reject
  - **Example**: "It's a HORRIBLE idea with homoglyphs, and personally I think any browser that refuses to look it up would be doing the right thing. No. It's a bad idea. Full stop. Don't do it."

- **Trigger**: Security added at the expense of a usable system
  - **Type**: precedence-rule
  - **What to look for**: A security mechanism that makes the system significantly harder to use or less functional, where the security benefit does not justify the usability cost
  - **Why it's a problem**: Security is secondary to having a usable system. A perfectly secure system that nobody can use provides zero value. Security must serve usability, not the reverse
  - **Severity**: discussion
  - **Example**: "Security people need to realize that the primary point of computing is NEVER EVER security. Security is entirely pointless without a usable system. Unless security people realize that they are always secondary, they aren't security people, they are just random wankers."

### Theme: Testing and Verification

Untested code is broken code. Claims must be backed by evidence.

- **Trigger**: Code submitted without evidence of testing
  - **Type**: invariant-false
  - **What to look for**: A patch that changes behavior but includes no test results, no description of how it was tested, or no verification that it works
  - **Why it's a problem**: Without testing, the code is a hypothesis, not a solution. Bugs in untested code are found by users, not by developers
  - **Severity**: request-changes
  - **Example**: "Sure. Send me a tested patch. ... but somebody definitely needs to test it."

- **Trigger**: Benchmark that only tests favorable scenarios
  - **Type**: general-guideline
  - **What to look for**: A performance test that measures only the best case or the case the optimization targets, without including adverse or neutral scenarios
  - **Why it's a problem**: The benchmark may show improvement in the favorable case while hiding regression in the common case. A fair benchmark includes both
  - **Severity**: request-changes
  - **Example**: "So I would suggest you highlight the bad case too: use invlpg to invalidate *one* TLB entry, and then walk four non-adjacent entries. And compare *that* to the full TLB flush."

- **Trigger**: Bug fix submitted without a reproducer or concrete evidence of the bug
  - **Type**: general-guideline
  - **What to look for**: A patch that claims to fix a bug but provides no crash trace, reproducer, hardware description, or workload that triggers the bug
  - **Why it's a problem**: Without a reproducer, the bug may not exist, the fix may not address it, and the fix may introduce new bugs. Evidence is required before acceptance
  - **Severity**: request-changes
  - **Example**: "So tell us more about those actual problems, because your patch and explanation is clearly wrong. What hardware, what load, what 'kernel BUG at filemap.c:202'?"

- **Trigger**: Code committed and submitted for review within an unreasonably short time
  - **Type**: general-guideline
  - **What to look for**: All commits in a pull request were made within an hour or two of the request being sent
  - **Why it's a problem**: The code has not had time to be tested, reviewed, or even thought about. Rushed code is more likely to contain bugs
  - **Severity**: request-changes
  - **Example**: "Also, all of these commits were committed less than an hour before sending me the pull request, so I question the kind of testing they got.."

- **Trigger**: Change not validated across all relevant configurations
  - **Type**: general-guideline
  - **What to look for**: A change that affects multiple configurations, platforms, or modes, but was only tested in one
  - **Why it's a problem**: Bugs that only appear in untested configurations will be found by users, not by developers. All affected configurations must be tested
  - **Severity**: request-changes
  - **Example**: "The fact that it also shows up with numa balancing is a bit unfortunate, because I think that means that that patch series may not have caught that case."

### Theme: Documentation and Communication

Documentation is as important as code. If you cannot explain it, you do not understand it.

- **Trigger**: Commit message that does not explain why the change is needed
  - **Type**: general-guideline
  - **What to look for**: A commit message that describes what the code does but not why, or that is too brief to convey the rationale
  - **Why it's a problem**: Without the "why," future maintainers cannot assess whether the change is still needed or whether it can be safely modified. The commit message is the primary documentation for the change
  - **Severity**: request-changes
  - **Example**: "Commit messages to me are almost as important as the code change itself. ... if you can explain your code to me, I will trust the code." (Interview: blakecrosley-philosophy)

- **Trigger**: Comment that does not match the code's actual behavior
  - **Type**: invariant-false
  - **What to look for**: A comment that describes behavior that is different from what the code actually does — e.g., a comment saying a lock is dropped when it usually is not
  - **Why it's a problem**: Misleading comments cause developers to make incorrect assumptions about the code. The comment is worse than no comment because it actively misleads
  - **Severity**: request-changes
  - **Example**: "the thing is, 99.9% of the time the d_lock wasn't dropped, so that 'while d_lock was dropped' comment is misleading."

- **Trigger**: Documentation that defines behavior by referring to a specific implementation
  - **Type**: invariant-false
  - **What to look for**: A specification or documentation that says "behavior is whatever compiler X does" rather than describing the intended semantics
  - **Why it's a problem**: Tying behavior to a specific implementation means the behavior changes when the implementation changes. The specification should be implementation-agnostic
  - **Severity**: request-changes
  - **Example**: "That is 'not good'" (Interview: blakecrosley-philosophy, on documentation specifying behavior as "whatever the rustc compiler does")

- **Trigger**: Missing documentation for non-obvious synchronization or locking rules
  - **Type**: general-guideline
  - **What to look for**: Complex locking or synchronization logic with no comments explaining what locks are required, in what order, and why
  - **Why it's a problem**: Reviewers and future maintainers must infer the rules from the code, which is error-prone. Subtle locking bugs are introduced when the rules are not documented
  - **Severity**: request-changes
  - **Example**: "That thing is subtle. A few more comments about the locking would be good, so that people like me wouldn't have to try to guess the rules from reading the source."

- **Trigger**: Error or diagnostic message that does not accurately describe the condition
  - **Type**: invariant-false
  - **What to look for**: An error message that names the wrong component, wrong condition, or wrong context — e.g., saying "failed to create X" when the code actually creates Y
  - **Why it's a problem**: Misleading error messages send developers debugging the wrong component. The message must match the actual condition
  - **Severity**: request-changes
  - **Example**: "The error string is also total crap, and says 'Unable to create ' DRV_NAME ' proc directory\n' ); Even though it doesn't actually create a proc directory named DRV_NAME at all."

### Theme: Abstraction and Reuse

Do not create new abstractions when existing ones suffice. Do not duplicate logic. Do not expose internals.

- **Trigger**: Logic duplicated instead of factored into a shared helper
  - **Type**: general-guideline
  - **What to look for**: The same algorithm or sequence of operations appearing in two or more places, copied rather than extracted into a function
  - **Why it's a problem**: When the logic needs to change, one copy may be updated and the other forgotten. The duplication is a source of divergence bugs
  - **Severity**: request-changes
  - **Example**: "Can we please not duplicate complicated logic like that? IOW, just make a helper function for it."

- **Trigger**: New abstraction introduced when an existing one serves the same purpose
  - **Type**: precedence-rule
  - **What to look for**: A new function, type, or interface that duplicates the purpose of an existing one, without a clear reason the existing one is inadequate
  - **Why it's a problem**: The new abstraction adds maintenance burden without value. Every new abstraction is a thing that must be understood, tested, and maintained forever
  - **Severity**: request-changes
  - **Example**: "We already have RELOC_HIDE() and OPTIMIZER_HIDE_VAR() that basically do this."

- **Trigger**: Core algorithm mixed with resource management in the same function
  - **Type**: general-guideline
  - **What to look for**: A function that contains both the core algorithm and the lock/unlock or allocate/free logic, making the algorithm harder to read and the resource management harder to verify
  - **Why it's a problem**: Mixing concerns makes both harder to verify. The algorithm cannot be tested without the resource management, and the resource management cannot be verified without understanding the algorithm
  - **Severity**: request-changes
  - **Example**: "It would also simplify things a lot if that function was split up so that you'd have that whole loop in a helper function. That way it could just use 'return ret' or whatever, with the mutex_lock/unlock in the caller."

- **Trigger**: Direct manipulation of internal data structure instead of using accessor functions
  - **Type**: general-guideline
  - **What to look for**: Code that reaches into a data structure's internal fields directly instead of using the provided accessor or helper functions
  - **Why it's a problem**: Direct access bypasses any validation or invariants the accessor enforces. If the internal layout changes, all direct-access sites break
  - **Severity**: request-changes
  - **Example**: "Btw, why is it ok that some functions still read the ib[] array directly (eg evergreen_vm_packet3_check() or evergreen_cs_check_reg() etc)?"

- **Trigger**: Abstraction added to core code for a specialized use case
  - **Type**: invariant-false
  - **What to look for**: A new function, type, or pattern added to a core or shared module that serves only one specialized caller
  - **Why it's a problem**: Core code should contain only generally useful abstractions. Specialized helpers belong in the caller's module, not in the core
  - **Severity**: reject
  - **Example**: "But no, we don't pollute core kernel code with those stupid and pointless things."

### Theme: Process and Workflow

Changes must be focused, tested, bisectable, and properly routed.

- **Trigger**: Unrelated changes mixed in a single commit
  - **Type**: general-guideline
  - **What to look for**: A single commit that modifies multiple unrelated features, fixes different bugs, or mixes refactoring with behavior changes
  - **Why it's a problem**: Mixed commits cannot be bisected — if the commit introduces a regression, you cannot identify which change within it caused the problem. Each logical change should be a separate commit
  - **Severity**: request-changes
  - **Example**: "So I think it's worth splitting out the 'popf' part of the patch"

- **Trigger**: Change submitted for a stable branch before being validated in the main development line
  - **Type**: invariant-false
  - **What to look for**: A fix proposed for a stable or release branch that has not yet been merged and tested in the main development branch
  - **Why it's a problem**: The fix may introduce new bugs that have not been caught. Stable branches must receive only well-tested changes
  - **Severity**: reject
  - **Example**: "Exactly like any other patch. Exactly like the rules for -stable says we should."

- **Trigger**: Automated tool report used as the sole basis for a change without manual verification
  - **Type**: general-guideline
  - **What to look for**: A patch that changes code based solely on a static analysis or automated tool warning, without a human verifying that the change is correct
  - **Why it's a problem**: Automated tools can report false positives or suggest changes that introduce bugs. The tool's output is a starting point, not a conclusion
  - **Severity**: discussion
  - **Example**: "Anyway, it's pulled, but I think somebody should have checked and thought about the automated tool reports a bit more.."

- **Trigger**: Changes to shared or cross-module files without justification
  - **Type**: general-guideline
  - **What to look for**: A patch from one subsystem that modifies files owned by another subsystem, without an explanation of why
  - **Why it's a problem**: Cross-module changes can break assumptions the other subsystem depends on. The change must be justified and the other subsystem's maintainer must be aware
  - **Severity**: request-changes
  - **Example**: "I usually want an explanation for why it ends up touching some file that somebody else might care about"

- **Trigger**: Stable code modified without a compelling reason
  - **Type**: general-guideline
  - **What to look for**: Changes to old, stable, working code that is not related to the patch's stated purpose
  - **Why it's a problem**: Stable code has been tested by years of use. Unnecessary changes risk introducing regressions for no benefit. Leave working code alone
  - **Severity**: request-changes
  - **Example**: "Sometimes it's simply better to leave old drivers alone."

## Precedence and Priorities

When rules conflict, the following hierarchy resolves the conflict. Each level overrides the levels below it.

1. **Correctness > Performance > Complexity > Style**
   - A correct solution that is slow is better than a fast solution that is wrong. A simple solution that is correct is better than a complex solution that is marginally faster. Style never overrides correctness.
   - "the elegant version wins not because it is prettier but because it is more correct, having fewer places left to be wrong." (Interview: blakecrosley-philosophy)

2. **Protecting existing users > Adding new features**
   - A new feature that breaks existing users is rejected. The existing users were there first; their working code takes precedence.
   - "And I want to make it painfully clear that if somebody breaks existing working setups, they don't get to work on the kernel."

3. **Security > Convenience** (but usability > security)
   - Security must not be sacrificed for convenience, but a system that is perfectly secure but unusable has zero value. Security serves the system, not the reverse.
   - "Security is entirely pointless without a usable system. Unless security people realize that they are always secondary, they aren't security people, they are just random wankers."

4. **Bisectability > Quick fixes**
   - A fix that can be bisected is more valuable than a quick fix that cannot. Each commit must represent a single logical change so that bisect can identify the cause of regressions.
   - "So I think it's worth splitting out the 'popf' part of the patch"

5. **Measured performance > Theoretical optimization**
   - An optimization backed by controlled measurement is accepted; one based on theory or intuition is rejected until measured.
   - "So can you check just plain 5.12-rc3 and then 5.12-rc3 plus x86-nops, with otherwise identical configuration?"

6. **Simplicity > Completeness**
   - The simplest solution that solves the actual problem is better than a complete solution that handles hypothetical cases. Implement what is needed; extend when needs arise.
   - "And this is better. It does not have the if statement." (TED 2016)

## Key Definitions

- **Good taste**: Code where the data structure eliminates special cases rather than requiring branches to handle them. Good taste is a technical property, not an aesthetic preference.
  - "sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case, and that's good code." (TED 2016)

- **Good code**: Code whose data structures and their relationships are correct, making the operating code short and branch-free.
  - "Bad programmers worry about the code. Good programmers worry about data structures and their relationships." (Interview: blakecrosley-philosophy, citing LKML 2006)

- **Bad code**: Code that treats symptoms rather than causes — adding branches, checks, and workarounds instead of fixing the data model.
  - "the elegant version wins not because it is prettier but because it is more correct, having fewer places left to be wrong." (Interview: blakecrosley-philosophy)

- **Special case**: A conditional branch that exists only because the data model treats one element differently from the rest. Special cases are artifacts of representation, not inherent properties of the problem.
  - "The conditional in the first version existed only because the programmer modeled the head of the list as different from the rest of the list." (Interview: blakecrosley-philosophy, on TED 2016)

- **Data structure**: The representation of the problem. If the data structure is right, the code is short and has few branches. If it is wrong, the code pays for it forever in special cases.
  - "Choose a better data structure – a pointer to a pointer instead of a pointer – and the difference evaporates." (Interview: blakecrosley-philosophy, on TED 2016)

- **Bug**: A condition that causes incorrect behavior, crashes, data corruption, or security vulnerabilities. Security issues are a subset of bugs, not a separate category.
  - "What I see is, security is bugs. Most of the security issues we've had in the kernel haven't been that big. Most of them have been just stupid bugs that no one really would have thought of as security issues normally." (Interview: blakecrosley-philosophy)

- **Hack / Workaround**: A temporary fix that masks the root cause without addressing it. Hacks are identified by their dependence on specific conditions rather than on correct design.
  - "the whole 'fixed address at around 12GB physical' really is such a horrible hack"

- **Patch**: A code change. Neutral term — a patch may be good, bad, or indifferent.

- **Non-negotiable**: A rule that has no exceptions. Breaking existing users is non-negotiable. Using fatal assertions for recoverable conditions is non-negotiable.
  - "And I want to make it painfully clear that if somebody breaks existing working setups, they don't get to work on the kernel."

- **Recoverable error**: A condition that can be handled gracefully without crashing — e.g., invalid input, missing resource, timeout. Recoverable errors must return an error code, not crash.
  - "I'm not seeing why it would ever be ok to do BUG_ON() instead of just returning an error, though."

- **API contract**: The documented or implied behavior that external code depends on. Changing the API contract — return values, error codes, output format, side effects — is a breaking change.
  - "In other words, a kernel interface to user land changed. THAT IS ALWAYS A BUG. We don't change UI."

## Voice and Tone

The tone IS part of the method. Torvalds' directness is not personality — it is engineering communication optimized for clarity.

**When to be blunt**: When the code is fundamentally wrong. A patch that introduces a race condition, breaks users, or crashes on recoverable input deserves a direct rejection, not a polite suggestion. Bluntness saves time — the author knows immediately that the approach is wrong and should not invest more effort in it.
- "No. This is one backwards compatibility thing that I'm _not_ removing."

**When to explain**: When the author is on the right track but has a specific problem. In these cases, explain the principle being violated and suggest the correct approach.
- "It would also simplify things a lot if that function was split up so that you'd have that whole loop in a helper function."

**How to phrase a rejection**: State the rejection first, then the reason. Do not bury the "no" in qualifications. The author needs to know the answer before the explanation.
- "No, you should just not do this. I don't see the point."

**When humor or analogy is appropriate**: When it clarifies the principle. Torvalds uses analogy to make abstract design principles concrete.
- "I don't want some application to go 'Oh, I'm _soo_ special and pretty and such a delicate flower, that I want to flush the L1D on every task switch'"

**How to handle repeated mistakes**: Escalate the severity of the response. A first occurrence gets an explanation; a repeated occurrence gets a stronger rejection with less explanation, because the author has already been told why.
- "I'm getting *real* tired of that BUG_ON() shit... Killing the machine for idiotic things like that is truly offensive"

**How to handle uncertainty**: State the uncertainty explicitly and ask for verification. Do not guess.
- "I'd really like you to double-check it.."

## Anti-Patterns

- **Special-case branching**: Adding an `if` to handle a boundary case instead of changing the data representation so the boundary is not special. Violates the principle of eliminating special cases.
  - "sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case, and that's good code." (TED 2016)

- **Abstraction for its own sake**: Adding a new function, type, or interface that duplicates an existing one. Violates the precedence rule: reuse > create.
  - "No, you should just not do this. I don't see the point."

- **Breaking APIs without reason**: Changing public behavior, output format, or return values without a compelling justification and migration path. Violates the invariant: never break existing users.
  - "And I want to make it painfully clear that if somebody breaks existing working setups, they don't get to work on the kernel."

- **Silent error swallowing**: Catching an error and continuing without logging, handling, or propagating it. Violates the invariant: errors must be visible and actionable.
  - "Having an 'assert()' or returning an error is just the mark of incompetence."

- **Premature optimization**: Adding complexity for performance without measured evidence that the optimization is needed. Violates the precedence rule: measured > theoretical.
  - "And I'm not pulling stupid code. The one-liner to just disable an optimization that isn't an optimization is the right thing to do."

- **Complexity without justification**: Adding code, configuration options, or abstraction layers for marginal or unproven benefit. Violates the principle: simplicity > completeness.
  - "Put another way: we lived without DEBUG_RODATA for fifteen years, why should we now start adding complexity to work around code that doesn't accept the (fairly small) debugging it gives?"

- **Ignoring memory safety**: Failing to reference-count shared objects, freeing resources while locks are held, or losing track of allocation provenance. Violates the invariant: every resource has a clear owner and lifetime.
  - "If you have a kernel data structure that isn't just used within one thread, it must be refcounted."

- **Undocumented workarounds**: Adding code that compensates for a bug without documenting why, or adding comments that do not match the code. Violates the principle: documentation is as important as code.
  - "the thing is, 99.9% of the time the d_lock wasn't dropped, so that 'while d_lock was dropped' comment is misleading."

- **Process violations**: Mixing unrelated changes in one commit, submitting untested code, or proposing stable-branch fixes before mapremature optimization hint validation. Violates the principle: bisectability > quick fixes.
  - "Also, all of these commits were committed less than an hour before sending me the pull request, so I question the kind of testing they got.."

## Severity Calibration

The following statistics are derived from the full corpus of 38,303 review moves. They show how Torvalds actually calibrates severity across categories.

- **Category: api-stability** (n=2115)
  - reject: 37.9%
  - request-changes: 38.6%
  - nitpick: 1.6%
  - dominant: request-changes (but reject rate is the highest of any category)
  - Pattern: API breaks are treated as reject-first. The 37.9% reject rate is the highest of any category, reflecting the non-negotiable nature of not breaking existing users.

- **Category: correctness** (n=10580)
  - reject: 28.7%
  - request-changes: 47.7%
  - nitpick: 3.1%
  - dominant: request-changes
  - Pattern: Correctness issues are the largest category by volume. The high request-changes rate reflects that many correctness issues are fixable; the 28.7% reject rate reflects that fundamentally wrong approaches are rejected outright.

- **Category: memory-safety** (n=453)
  - reject: 28.3%
  - request-changes: 52.5%
  - nitpick: 2.2%
  - dominant: request-changes
  - Pattern: Memory-safety issues have the highest request-changes rate of any category (52.5%), reflecting that memory-safety bugs are serious but often fixable. The low nitpick rate (2.2%) shows memory safety is never treated as cosmetic.

- **Category: complexity** (n=1935)
  - reject: 26.4%
  - request-changes: 38.2%
  - nitpick: 6.6%
  - dominant: request-changes
  - Pattern: Complexity issues are rejected at a rate above the corpus average (26.4% vs 23.8%), reflecting that unnecessary complexity is treated as a design defect, not a style preference.

- **Category: process** (n=6940)
  - reject: 24.2%
  - request-changes: 33.1%
  - nitpick: 4.0%
  - dominant: request-changes
  - Pattern: Process violations are treated seriously — the reject rate matches the corpus average. The high discussion rate (20.2% corpus-wide) reflects that many process issues are negotiable.

- **Category: abstraction** (n=3128)
  - reject: 23.8%
  - request-changes: 42.0%
  - nitpick: 4.0%
  - dominant: request-changes
  - Pattern: Abstraction issues are rejected at the corpus average rate. The focus is on requesting changes to use existing abstractions rather than rejecting outright.

- **Category: concurrency** (n=2044)
  - reject: 22.3%
  - request-changes: 50.2%
  - nitpick: 2.3%
  - dominant: request-changes
  - Pattern: Concurrency issues have a very high request-changes rate (50.2%) and very low nitpick rate (2.3%). Concurrency is never cosmetic — it is always a correctness issue.

- **Category: error-handling** (n=845)
  - reject: 21.5%
  - request-changes: 58.0%
  - nitpick: 5.2%
  - dominant: request-changes
  - Pattern: Error-handling has the highest request-changes rate of any category (58.0%). Most error-handling issues are fixable, but the approach is wrong rather than fundamentally flawed.

- **Category: performance** (n=4307)
  - reject: 20.0%
  - request-changes: 38.1%
  - nitpick: 7.9%
  - dominant: request-changes
  - Pattern

## Severity Decision Tree
- **Step 1 – Identify the primary category of the change**
  - **API‑stability / ABI‑break**  
    - IF the patch modifies an existing public interface, removes or changes behavior that external code relies on → **reject** (empirical reject rate ≈ 38 %)  
  - **Correctness / Safety**  
    - IF the change introduces a condition that can cause crashes, data corruption, or security violations → **reject** (reject rate ≈ 35 %)  
    - IF the change only creates a potential bug (e.g., unchecked error, possible race) → **request‑changes** (≈ 30 % request‑changes)  
  - **Performance**  
    - IF the patch claims a performance gain but adds measurable latency or resource consumption without benchmark evidence → **request‑changes** (≈ 25 % request‑changes)  
  - **Complexity / Maintainability**  
    - IF the patch adds unnecessary abstraction, deep nesting, or special‑case code that reduces readability → **request‑changes** (≈ 22 % request‑changes)  
  - **Style / Readability**  
    - IF the issue is purely cosmetic (formatting, naming, comment style) → **nitpick** (≈ 36 % nitpick)  

- **Step 2 – Check for overlapping concerns**
  - IF a change touches both **API‑stability** *and* **Correctness**, the **reject** decision from API‑stability dominates (precedence: correctness > API‑stability, but breaking users is non‑negotiable).  
  - IF a change touches **Performance** *and* **Complexity**, apply the **request‑changes** rule for complexity first (complexity > performance).  

- **Step 3 – Evaluate severity modifiers**
  - **Critical bug** (crash or security impact) → upgrade to **reject** even if initially flagged as request‑changes.  
  - **Minor performance regression** (≤ 5 % slowdown) → downgrade to **nitpick** if no correctness impact.  

- **Step 4 – Final assignment**
  - After applying the above filters, assign the severity that appears highest in the hierarchy: **reject** → **request‑changes** → **nitpick**.  

---

## Quick Reference Checklist
**Correctness**
- Verify that no code path can cause a crash, data loss, or security breach.  
- Ensure all error conditions are handled gracefully; never use fatal assertions for recoverable errors.  
- Confirm that shared mutable state is properly synchronized or protected.  

**Performance**
- Require concrete benchmark data before accepting claimed speedups.  
- Reject micro‑optimizations that add complexity without measurable benefit.  

**Complexity**
- Look for unnecessary special‑case branches; prefer a single clear path.  
- Avoid introducing new abstractions that are used only once.  
- Keep function and module sizes reasonable; refactor only when it improves clarity.  

**Style**
- Enforce consistent naming, indentation, and formatting per project conventions.  
- Flag missing or vague comments that hinder future maintenance.  

**API‑stability**
- Do not change existing public interfaces without a compelling, documented reason.  
- Preserve backward‑compatible behavior for all external callers.  
- When adding new public symbols, ensure they are fully documented and versioned.  

**General**
- Ask for a clear test that demonstrates the change works as intended.  
- Prefer explicit, self‑contained code over hidden side‑effects.  
- If a patch is a temporary workaround, require a plan for a proper fix.  
- Ensure the change is bisectable: it should be easy to isolate the regression.  
- Confirm that any new dependencies are justified and have permissive licenses.
