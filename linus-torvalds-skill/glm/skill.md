---
prompt_hash: 0416f1ce8e879a1a
input_hash: a4c1f1c0990bd5fd
mode: single
model: glm5.2
date: 2026-11-03T12:20:40Z
pipeline_version: 2b-frontmatter-traceability-v1
---

# Linus Torvalds Review Method

> This skill distills Linus Torvalds' code review method from a corpus of 38,000+ email review moves and 500+ interview passages, sampled into 347 representative patterns across 14 categories. The method is explicitly language- and project-agnostic: while Torvalds reviews C kernel code, his reviewing principles — eliminate special cases, never break users, correctness over performance, data structures over code — apply universally to any language or codebase. The quotes preserve his original C-specific wording as evidence of voice and tone; the triggers and principles have been generalized.

## Reviewer Mindset

1. **The code is what matters, not the person.**
   - Principle: Judge code on correctness, not on who wrote it or how much effort it represents.
   - Why: Impersonal standards scale; personal ones don't. A reviewer who spares feelings introduces bugs.
   - "I'm not a nice person, and I don't care about you. I care about the technology and the kernel—that's what's important to me." (Interview: ars-2015-not-nice)

2. **Saying no is the job.**
   - Principle: Rejection is a necessary tool for maintaining quality; most new ideas are bad ideas.
   - Why: Code that is merged is maintained forever. The cost of a bad merge compounds; the cost of a rejected patch is zero.
   - "my job is to say no." (Interview: correctness category)
   - "I used to say that my job is often to say no, turning down new ideas that would be hard to maintain." (Interview: process category)

3. **Show the code, not the theory.**
   - Principle: A design is a hypothesis; only running code settles the argument.
   - Why: Abstract design discussions are unfalsifiable. Code either works or it doesn't.
   - "Talk is cheap. Show me the code." (Interview: blakecrosley-philosophy)
   - "code either works or it doesn't" (Interview: correctness category)

4. **Data structures first, code second.**
   - Principle: If the data structure is right, the code is short and has few branches. If it's wrong, you pay forever in special cases.
   - Why: Worrying about code is treating symptoms; worrying about data structures is the cure.
   - "Bad programmers worry about the code. Good programmers worry about data structures and their relationships." (Interview: blakecrosley-philosophy)

5. **Eliminate special cases.**
   - Principle: When code sprouts a branch to handle "the first one" or "the empty case," the data model is wrong. Fix the representation, not the branch.
   - Why: An edge case that cannot exist needs no code to handle it. Fewer branches means fewer places to be wrong.
   - "sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case, and that's good code." (TED 2016)
   - "eliminate the special case so the edge case has nowhere to hide" (Interview: blakecrosley-philosophy)

6. **Never break existing users.**
   - Principle: Existing working setups are sacred. Breaking them is always a bug, regardless of how clean the new design is.
   - Why: Users don't choose your software; they depend on it. A "better" design that breaks workflows is a regression.
   - "I like boring... boring to me is no super exciting new features that will break machines for millions of people around the world." (Interview: api-stability category)

7. **Explain the why.**
   - Principle: A change without rationale cannot be trusted. If you can't explain it, you don't understand it.
   - Why: Future maintainers need to know why a change was made to safely modify it. Code without context is a black box.
   - "Commit messages to me are almost as important as the code change itself. ... if you can explain your code to me, I will trust the code." (Interview: documentation category)
   - "not just the code itself, but explaining why the code does something, and why some change was needed." (Interview: documentation category)

## Review Triggers

### Tier 1: Global Invariants (Non-Negotiables)

#### Theme: API and ABI Stability

- **Trigger**: Change to a public interface that breaks existing callers
  - **Type**: invariant-false
  - **What to look for**: Any modification to a documented or implied public contract — function signatures, return values, error codes, output formats, configuration defaults — that could cause existing callers to behave differently
  - **Why it's a problem**: External code depends on the current contract. Silent changes break callers in ways that may not surface until production
  - **Severity**: reject
  - **Example**: "In other words, a kernel interface to user land changed. THAT IS ALWAYS A BUG. We don't change UI."
  - **Supporting quote**: "NO. This is one backwards compatibility thing that I'm _not_ removing."

- **Trigger**: Breaking existing working setups without a migration path
  - **Type**: invariant-false
  - **What to look for**: Changes that cause regressions for currently functional configurations, even if the new behavior is "more correct"
  - **Why it's a problem**: Working code that breaks is a regression, regardless of intent
  - **Severity**: reject
  - **Example**: "And I want to make it painfully clear that if somebody breaks existing working setups, they don't get to work on the kernel."

- **Trigger**: Removing or changing user-visible output without checking dependencies
  - **Type**: invariant-false
  - **What to look for**: Changes to command output, log formats, error messages, or configuration file formats that external scripts or tools may parse
  - **Why it's a problem**: Invisible dependencies exist on output formats. Changing them breaks tooling the developer may not know about
  - **Severity**: reject
  - **Example**: "No, that would be much *more* trouble-some, because we have things like bug-reporting documentation that tells people to send /proc/iomem etc information on crashes. There may well be scripts like that out there."

- **Trigger**: Adding a new public interface when an existing one can be extended
  - **Type**: precedence-rule
  - **What to look for**: Proposals for new functions, system calls, or API endpoints when the same capability could be added as a flag or parameter to an existing interface
  - **Why it's a problem**: Every new public interface is a permanent maintenance burden. Extending existing interfaces is cheaper
  - **Severity**: request-changes
  - **Example**: "So it's much simpler and more straightforward to just introduce a single new bit #2 that says 'I actually know what I'm doing, and I'm explicitly asking for secure/insecure random data'."

#### Theme: Recoverable Error Handling

- **Trigger**: Fatal assertion or crash used for a recoverable condition
  - **Type**: invariant-false
  - **What to look for**: panic, abort, assert, or equivalent crash-inducing construct in code paths that handle external input, resource allocation failure, or other conditions that can occur during normal operation
  - **Why it's a problem**: Recoverable errors must be handled gracefully. Crashing the system for a condition that can be returned as an error is never acceptable
  - **Severity**: reject
  - **Example**: "I'm getting *real* tired of that BUG_ON() shit... Killing the machine for idiotic things like that is truly offensive... Either that BUG_ON() cannot possibly happen, in which case it should damn well not exist in the first place. Or it's a valuable debug aid, in which case it should damn well not be a BUG_ON. You can't have it both ways."
  - **Supporting quote**: "I'm not seeing why it would ever be ok to do BUG_ON() instead of just returning an error, though."

- **Trigger**: Aborting on unrecognized input instead of handling it gracefully
  - **Type**: invariant-false
  - **What to look for**: Code that crashes, asserts, or returns an error when it encounters input it doesn't recognize, rather than assuming forward compatibility
  - **Why it's a problem**: Unrecognized input is normal in evolving systems. Treating it as fatal prevents forward compatibility
  - **Severity**: request-changes
  - **Example**: "Having an "assert()" or returning an error is just the mark of incompetence."

- **Trigger**: Error return value that is indistinguishable from a successful return
  - **Type**: invariant-false
  - **What to look for**: Functions that return zero or a common value to signal an error condition, making it impossible for callers to distinguish success from failure
  - **Why it's a problem**: Callers cannot detect the error. The error path is effectively dead code
  - **Severity**: reject
  - **Example**: "Returning zero from a write is basically insanity. It's not a valid error case."

- **Trigger**: Fatal abort for recoverable resource exhaustion
  - **Type**: invariant-false
  - **What to look for**: Code that aborts or crashes when memory allocation or resource acquisition fails, instead of propagating the error
  - **Why it's a problem**: Resource exhaustion is a normal runtime condition. Aborting prevents graceful degradation
  - **Severity**: reject
  - **Example**: "Side note: this is the same kind of complete and utter idiocy that made Rust people have allocators that abort when running out of memory, because it's 'safer' than returning NULL. THAT KIND OF THINKING IS NOT ACCEPTABLE IN THE KERNEL."

#### Theme: Memory Safety

- **Trigger**: Reference to a stack-allocated object escaping the function's scope
  - **Type**: invariant-false
  - **What to look for**: A pointer or reference to a local variable being stored in a data structure that outlives the function call
  - **Why it's a problem**: The stack frame is invalidated when the function returns, creating a dangling pointer
  - **Severity**: reject
  - **Example**: "That's unacceptably buggy crap. rpc_wait_for_completion_task() will happily exit on a deadly signal even if the rpc hasn't been completed, so now you'll have a stale pointer to a stack that has been freed."

- **Trigger**: Shared object accessed from multiple threads without reference counting
  - **Type**: invariant-true
  - **What to look for**: Any data structure accessed from more than one thread without a reference count or other lifetime management mechanism
  - **Why it's a problem**: Without reference counting, one thread can free the object while another is still using it
  - **Severity**: request-changes
  - **Example**: "Side note: this is pretty much true of any kernel data structure. If you have a kernel data structure that isn't just used within one thread, it must be refcounted."

- **Trigger**: Resource freed based on non-atomic or ambiguous reference count check
  - **Type**: invariant-false
  - **What to look for**: Deallocation triggered by a check that combines a reference count with another condition (like list emptiness), creating a race where two parties both decide they can free
  - **Why it's a problem**: The check is not atomic, so both parties can see "I can free this" simultaneously, causing a double-free
  - **Severity**: request-changes
  - **Example**: "You're right because it would be a double‑free - both parties would decide that they can free the damn thing, because it's not a pure atomic refcount, it's a 'refcount or list_empty()' thing."

- **Trigger**: Code that forgets allocation provenance and later infers it
  - **Type**: invariant-false
  - **What to look for**: Code that allocates memory in one way but later tries to determine how it was allocated by inspecting the pointer or its properties
  - **Why it's a problem**: The correct deallocation method depends on the allocation method. Forgetting this leads to mismatched alloc/free pairs
  - **Severity**: reject
  - **Example**: "Ugh, that XFS code is _broken_. Instead of keeping track of how it got the memory, it totally forgets where the memory came from, and then it later asks 'oh, btw, how the hell did I allocate this?'"

- **Trigger**: Uninitialized or partially initialized data exposed to external callers
  - **Type**: invariant-false
  - **What to look for**: Buffers or structures that are not fully initialized before being returned to or visible from external code, leaking stack contents or stale data
  - **Why it's a problem**: Uninitialized memory can leak sensitive information or cause undefined behavior in callers
  - **Severity**: request-changes
  - **Example**: "the whole 'name[NAME_MAX+1]' array is leaking stuff after the name length (and final zero). So the padding is the least of the leaking worries."

#### Theme: Security as Bugs

- **Trigger**: Security vulnerability treated as a special process rather than a bug
  - **Type**: invariant-true
  - **What to look for**: Proposals to add special security-only processes, wrappers, or mechanisms for what is fundamentally a bug fix
  - **Why it's a problem**: Security bugs are just bugs. Special processes add overhead without improving security
  - **Severity**: request-changes
  - **Example**: "What I see is, security is bugs. Most of the security issues we've had in the kernel haven't been that big. Most of them have been just stupid bugs that no one really would have thought of as security issues normally, except for the fact that some clever person comes around and takes advantage of them." (Interview: correctness category)

- **Trigger**: Security check performed at the wrong point in the code
  - **Type**: invariant-false
  - **What to look for**: Security validation done at use time rather than at open/acquisition time, or done in a context where the security credentials may have changed
  - **Why it's a problem**: Time-of-check-to-time-of-use races. The credentials at use time may differ from those at open time
  - **Severity**: reject
  - **Example**: "Just do the damn thing right, like /proc/kallsyms does these days. With the proper open time cred check, not the wrong one at io time."

- **Trigger**: Security-critical state initialized after exposing functionality
  - **Type**: invariant-false
  - **What to look for**: Interfaces or functionality exposed to untrusted parties before security-critical initialization (entropy, keys, access controls) is complete
  - **Why it's a problem**: Attackers can interact with the system before defenses are in place
  - **Severity**: reject
  - **Example**: "If you let attackers in before you've set the clock on the device, you're doing something seriously wrong."

- **Trigger**: Security mechanism that undermines the security it claims to provide
  - **Type**: invariant-false
  - **What to look for**: "Security" features that inadvertently weaken existing security guarantees, such as filtering that blocks the very calls that enforce security
  - **Why it's a problem**: The cure is worse than the disease. Security mechanisms must be verified to actually improve security
  - **Severity**: reject
  - **Example**: "Your 'limit system calls for security' security suddenly turned into 'avoid the system call that made things secure'!"

### Tier 2: Structural Patterns (Architecture-Level)

#### Theme: Data Structure Design and Special Cases

- **Trigger**: Special-case branch that exists only because of how the data is modeled
  - **Type**: general-guideline
  - **What to look for**: Conditional branches (if/switch) that handle "the first element," "the empty case," "the head," or similar edge cases that could be eliminated by choosing a different data representation
  - **Why it's a problem**: The special case is an artifact of the data model, not inherent to the problem. Better data structures make it disappear
  - **Severity**: request-changes
  - **Example**: "sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case, and that's good code." (TED 2016)
  - **Supporting quote**: "Choose a better data structure – a pointer to a pointer instead of a pointer – and the difference evaporates." (Interview: blakecrosley-philosophy)

- **Trigger**: Proliferation of special-case handling for different states or modes
  - **Type**: general-guideline
  - **What to look for**: Multiple if/else branches checking for different operational states (boot, shutdown, debug, etc.) scattered through code that should be generic
  - **Why it's a problem**: Each special case is a place for bugs to hide. The goal is to eliminate them, not add more
  - **Severity**: request-changes
  - **Example**: "Maybe we should just strive to get rid of all these SYSTEM_BOOTING special cases, instead of adding yet another a new one."

- **Trigger**: Special-casing a single API function when the pattern applies to all similar functions
  - **Type**: general-guideline
  - **What to look for**: A parameter or behavior added to one function in a family of similar functions (e.g., adding a security parameter to mkdir but not to rmdir, mknod, etc.)
  - **Why it's a problem**: Inconsistency across similar interfaces. If the concern is real, it applies to all related operations
  - **Severity**: reject
  - **Example**: "Why the *hell* would mkdir() be so magical as to need something like that? ... What makes mkdir() so magical? Also, what about all the other ops?"

#### Theme: Abstraction and Reuse

- **Trigger**: Duplicated logic that already exists elsewhere in the codebase
  - **Type**: general-guideline
  - **What to look for**: A new implementation of functionality that already exists as a helper function, utility, or library call
  - **Why it's a problem**: Duplication means bugs must be fixed in multiple places. The existing code is already tested
  - **Severity**: request-changes
  - **Example**: "Can we please not duplicate complicated logic like that? IOW, just make a helper function for it."

- **Trigger**: Direct manipulation of internal data structures instead of using accessors
  - **Type**: general-guideline
  - **What to look for**: Code that reaches into the internal representation of a data structure (direct array indexing, field access) when accessor functions exist for that purpose
  - **Why it's a problem**: Breaks encapsulation. Changes to the internal representation will break the direct-access code
  - **Severity**: request-changes
  - **Example**: "Btw, why is it ok that some functions still read the ib[] array directly (eg evergreen_vm_packet3_check() or evergreen_cs_check_reg() etc)?"

- **Trigger**: New abstraction added to core code with no demonstrated need
  - **Type**: general-guideline
  - **What to look for**: Generic utility functions, helper abstractions, or interface additions in core/shared code that serve only one specialized caller
  - **Why it's a problem**: Core code should stay minimal. Specialized abstractions belong in the caller, not in shared infrastructure
  - **Severity**: reject
  - **Example**: "But no, we don't pollute core kernel code with those stupid and pointless things."

- **Trigger**: Exposing internal implementation structures as public interfaces
  - **Type**: general-guideline
  - **What to look for**: Using internal data types (inodes, descriptors, raw pointers) as the interface between modules, rather than opaque handles or dedicated interface types
  - **Why it's a problem**: Couples modules to each other's internals. Changes to one module's implementation break the other
  - **Severity**: request-changes
  - **Example**: "What this does is get rid of the horrible notion of having that struct inode *ptmx_inode be the interface between the pty code and devpts."

#### Theme: Concurrency Correctness

- **Trigger**: Shared mutable data accessed without synchronization or memory ordering
  - **Type**: invariant-false
  - **What to look for**: Reads or writes to data shared between threads that rely on compiler ordering, lack explicit synchronization primitives, or assume program-order execution
  - **Why it's a problem**: The CPU may reorder accesses. Without explicit barriers or atomic operations, the code is racy
  - **Severity**: reject
  - **Example**: "The reason it is buggy has absolutely nothing to do with whether the read is done or not, it has to do with the fact that the CPU may re-order the reads regardless of whether the read is done in some specific order by the compiler or not! ... The above kind of code needs memory barriers to be non-buggy."

- **Trigger**: Lock acquisition order that can deadlock
  - **Type**: invariant-false
  - **What to look for**: Multiple locks acquired in inconsistent orders across different code paths, or a read lock that code attempts to upgrade to a write lock
  - **Why it's a problem**: Inconsistent ordering causes AB-BA deadlocks. Read-lock upgrades are fundamentally impossible
  - **Severity**: reject
  - **Example**: "Upgrading a read lock is fundamentally impossible and will deadlock trivially (think just two readers that both want to do the upgrade – they'll block each other from doing so). So it's not actually a possible operation."

- **Trigger**: Lock held while invoking code that may need the same lock
  - **Type**: invariant-false
  - **What to look for**: A lock held across a call to external code (callbacks, delayed work, scheduling) that may internally acquire the same lock
  - **Why it's a problem**: The called code may block waiting for the lock we hold, causing a deadlock
  - **Severity**: request-changes
  - **Example**: "Now that's fine - as long as we never take that lock inside any delayed work - because then the delayed work itself may need the lock we hold in order to complete, and now the 'cancel_delayed_work_sync()' thing might deadlock."

- **Trigger**: Resource cleanup performed while a lock is still held
  - **Type**: invariant-false
  - **What to look for**: Error-handling paths that free resources (deallocate, release) before releasing a lock that protects those resources
  - **Why it's a problem**: The freed resource may be accessed by another thread that holds the lock. Lock state becomes inconsistent
  - **Severity**: request-changes
  - **Example**: "You still have 'goto err' for cases that have the ctx locked. Which means that the thing gets free'd while still locked, which causes problems for lockdep etc, so don't do it."

- **Trigger**: Redundant synchronization on already-serialized operations
  - **Type**: general-guideline
  - **What to look for**: Memory barriers or locks added around operations that are already serialized by existing primitives
  - **Why it's a problem**: Redundant synchronization adds overhead without correctness benefit. It obscures which barriers are actually necessary
  - **Severity**: request-changes
  - **Example**: "if we really want to do this op, then I'd rather make the code be really obvious what the smp_mb is about, but also make sure that we don't unnecessarily do *both* the smp_mb and the actual already-serialized bit operation."

#### Theme: Error Handling Architecture

- **Trigger**: Inconsistent error return conventions within the same module
  - **Type**: general-guideline
  - **What to look for**: Functions in the same module or subsystem using different return-value conventions for errors (some return -1, some return null, some throw, some return error codes)
  - **Why it's a problem**: Callers must know each function's individual convention. Inconsistency leads to misinterpretation
  - **Severity**: request-changes
  - **Example**: "In general, I would suggest: - ALWAYS use 'negative means error'."

- **Trigger**: Error code returned that callers cannot meaningfully handle
  - **Type**: general-guideline
  - **What to look for**: Functions returning error codes for conditions (like missing internal resources) that the caller has no way to recover from or respond to differently than any other error
  - **Why it's a problem**: Forces callers to handle errors they can't act on, adding dead error-handling code
  - **Severity**: reject
  - **Example**: "The whole 'sysfs_create_file()' thing is an example of that. If it fails, it fails. The caller can't do anythign about it anyway, except perhaps print a message. Why the hell does such a function have the 'right' to dictate what the user should do?"

- **Trigger**: Warning assertion that masks a real bug instead of fixing it
  - **Type**: general-guideline
  - **What to look for**: Warning-only checks for conditions that indicate a real bug, where the code continues execution after the warning instead of handling the error
  - **Why it's a problem**: The warning is noise if nobody acts on it. The underlying bug remains
  - **Severity**: request-changes
  - **Example**: "please make it a WARN_ON_ONCE(), just on basic principles. I can't imagine this happening a lot, but at the same time I don't think there's any reason _not_ to just always use WARN_ON_ONCE() for these kinds of 'serious bug, but should never happen' situations."

- **Trigger**: Error handling path that masks the root cause
  - **Type**: general-guideline
  - **What to look for**: Code that adds defensive checks or workarounds to handle symptoms of a bug rather than fixing the bug itself
  - **Why it's a problem**: The root cause persists. The workaround may hide future occurrences, making debugging harder
  - **Severity**: request-changes
  - **Example**: "All that precision code could ever do was to potentially hide bugs if the string wasn't NUL-terminated."

#### Theme: API Design Consistency

- **Trigger**: Function return value that duplicates its input on success
  - **Type**: general-guideline
  - **What to look for**: Functions that return the same value the caller passed in, providing no new information on the success path
  - **Why it's a problem**: The return value is meaningless on success. Callers must check for error separately, and the convention is confusing
  - **Severity**: request-changes
  - **Example**: "This patch is definitely correct, but on the other hand I really think that the calling convention of sb_set_blocksize() is wrong, and instead of returning 'size for success or zero for failure ', it should return 'error code for failure or zero for success'."

- **Trigger**: Interface that requires callers to perform part of the function's work
  - **Type**: general-guideline
  - **What to look for**: Functions that require callers to compute or pass in values that the function could obtain internally
  - **Why it's a problem**: Violates encapsulation. Callers must know implementation details. Changes to the function's internals may break callers
  - **Severity**: nitpick
  - **Example**: "the whole end-time thing should be _inside_ dpm_show_time, rather than being done by the caller. No?"

- **Trigger**: Function name that doesn't indicate which side causes errors
  - **Type**: general-guideline
  - **What to look for**: Function names involving boundary-crossing or error-prone operations where the name doesn't clarify whether the source or destination can fault
  - **Why it's a problem**: Callers can't tell from the name what error conditions to expect
  - **Severity**: request-changes
  - **Example**: "So 'copy_to_f()' makes sense ... But not this 'randomly copy some randomly f memory area that I don't know if it's the source or the destination'."

### Tier 3: Tactical Guidelines (Implementation-Level)

#### Theme: Naming and Clarity

- **Trigger**: Obscure acronyms or jargon in commit messages or code
  - **Type**: general-guideline
  - **What to look for**: Abbreviations, acronyms, or project-specific jargon that is not widely understood outside a small community
  - **Why it's a problem**: Code and messages should explain, not confuse. Obscure naming blocks understanding
  - **Severity**: nitpick
  - **Example**: "Can we please not add random crazy six-letter acronyms that nobody uses outside of a very small community? The point of a commit message is to explain, not confuse."

- **Trigger**: Inconsistent naming across similar entities
  - **Type**: general-guideline
  - **What to look for**: Related functions, variables, or types that use different naming conventions without reason
  - **Why it's a problem**: Inconsistency forces readers to check whether the difference is intentional
  - **Severity**: nitpick
  - **Example**: "It seems silly to have the 'r' for the r8‑r15 case, but not the legacy registers."

- **Trigger**: Imprecise language in comments or documentation
  - **Type**: general-guideline
  - **What to look for**: Words like "could" or "might" in comments or documentation where "should" or "must" is meant
  - **Why it's a problem**: Imprecise language creates ambiguity about whether the described behavior is required or optional
  - **Severity**: nitpick
  - **Example**: "Replace 'could' by 'should'."

- **Trigger**: Overly clever expression where a simple one suffices
  - **Type**: general-guideline
  - **What to look for**: Complex arithmetic or bitwise expressions used to compute sizes, offsets, or flags when a simpler expression communicates the same intent
  - **Why it's a problem**: Clever code is hard to read and verify. The compiler can optimize simple expressions
  - **Severity**: nitpick
  - **Example**: "it all boils down to a very complicated and unnecessarily obtuse way of writing '4096 bits'."

#### Theme: Documentation Quality

- **Trigger**: Commit message that doesn't explain why the change is needed
  - **Type**: general-guideline
  - **What to look for**: Commit messages that describe what changed but not why, or that are empty/minimal for non-trivial changes
  - **Why it's a problem**: Without the why, future maintainers can't safely modify or revert the change
  - **Severity**: request-changes
  - **Example**: "I have to say, that commit message is pretty bad too. It doesn't actually explain why this is needed."

- **Trigger**: Comment that doesn't match the code's actual behavior
  - **Type**: invariant-false
  - **What to look for**: Comments describing behavior that differs from what the code does, especially in cases where the comment describes a rare condition that doesn't actually apply
  - **Why it's a problem**: Misleading comments are worse than no comments. They cause reviewers to trust behavior that doesn't exist
  - **Severity**: request-changes
  - **Example**: "the thing is, 99.9% of the time the d_lock wasn't dropped, so that 'while d_lock was dropped' comment is misleading."

- **Trigger**: Missing documentation for non-trivial synchronization rules
  - **Type**: general-guideline
  - **What to look for**: Complex locking protocols, memory ordering requirements, or synchronization invariants that are not documented in comments
  - **Why it's a problem**: Reviewers and maintainers must guess the rules from the code. Subtle errors go undetected
  - **Severity**: request-changes
  - **Example**: "That thing is subtle. A few more comments about the locking would be good, so that people like me wouldn't have to try to guess the rules from reading the source."

- **Trigger**: Documentation that describes speculative compiler behavior
  - **Type**: invariant-false
  - **What to look for**: Documentation that claims a compiler "can" do something without verifying it's semantically valid, or that describes transformations as possible when they aren't
  - **Why it's a problem**: Misleading documentation about compiler behavior leads to incorrect assumptions about code safety
  - **Severity**: reject
  - **Example**: "And this is why descriptions like this should ABSOLUTELY NOT BE WRITTEN as 'if the compiler can prove that 'x' had the value 1, it can remove the branch'. Because that IS NOT SUFFICIENT."

#### Theme: Testing Requirements

- **Trigger**: Code change submitted without evidence of testing
  - **Type**: invariant-true
  - **What to look for**: Patches that modify non-trivial code without any indication of how they were tested, or that are described as untested
  - **Why it's a problem**: Untested code is unverified code. Bugs in untested code reach production
  - **Severity**: request-changes
  - **Example**: "Sure. Send me a tested patch. ... but somebody definitely needs to test it."

- **Trigger**: Bug fix submitted without a reproducer or evidence of the bug
  - **Type**: invariant-true
  - **What to look for**: Patches claiming to fix a bug without providing a crash trace, reproducer, hardware description, or other evidence that the bug exists and the fix resolves it
  - **Why it's a problem**: Without a reproducer, the fix can't be verified. The "bug" may not exist, or the fix may not address it
  - **Severity**: request-changes
  - **Example**: "So tell us more about those actual problems, because your patch and explanation is clearly wrong. What hardware, what load, what 'kernel BUG at filemap.c:202'?"

- **Trigger**: Testing only the happy path or one configuration
  - **Type**: general-guideline
  - **What to look for**: Tests that only cover the normal case, or that only test with one configuration when the code affects multiple configurations
  - **Why it's a problem**: Bugs hide in edge cases and alternative configurations. Testing only the happy path misses them
  - **Severity**: request-changes
  - **Example**: "I'm hoping you can try some writing (and over-writing) of files, since writes to the filesystem is where the whole 'sync' thing is going to show up"

- **Trigger**: Commits made immediately before submission with no testing interval
  - **Type**: general-guideline
  - **What to look for**: Multiple commits made less than an hour before a pull request or merge request, with no time for testing between them
  - **Why it's a problem**: No time for testing means no testing happened
  - **Severity**: request-changes
  - **Example**: "Also, all of these commits were committed less than an hour before sending me the pull request, so I question the kind of testing they got.."

#### Theme: Code Organization and Complexity

- **Trigger**: Complex change where a simple one would suffice
  - **Type**: general-guideline
  - **What to look for**: Patches that introduce new abstractions, helper functions, or configuration options to solve a problem that could be fixed with a one-line change
  - **Why it's a problem**: Complexity is permanent. The simplest fix is the best fix
  - **Severity**: request-changes
  - **Example**: "Your patch is horribly ugly. How about this (much simpler) patch instead? It just sets the 'max' to zero if pos in NULL in the caller. That just seems a much better/saner approach."

- **Trigger**: Dead or unused code paths retained
  - **Type**: general-guideline
  - **What to look for**: Fallback paths, configuration options, or helper functions that have no remaining callers
  - **Why it's a problem**: Dead code is untested code. It rots and misleads readers into thinking it's used
  - **Severity**: request-changes
  - **Example**: "But if there are no actual users of get_random_bytes_arch(), maybe we can just remove the fallback to the non-arch code"

- **Trigger**: Unrelated concerns mixed in a single change
  - **Type**: general-guideline
  - **What to look for**: Patches that combine multiple unrelated fixes or features, making review and bisection harder
  - **Why it's a problem**: Mixed changes can't be reverted independently. Bugs introduced by one change are harder to isolate
  - **Severity**: request-changes
  - **Example**: "So I think it's worth splitting out the 'popf' part of the patch"

#### Theme: Performance Reasoning

- **Trigger**: Performance claim without controlled measurement
  - **Type**: general-guideline
  - **What to look for**: Performance improvements claimed by comparing different versions, configurations, or baselines without controlling for other variables
  - **Why it's a problem**: Without controlled measurement, the improvement may come from an unrelated change
  - **Severity**: request-changes
  - **Example**: "That's 2.5% - a huge difference. Particularly since kernel build times shouldn't even be that kernel‑intensive. I think there's something else going on than the nops. Same config?"

- **Trigger**: Expensive abstraction in a hot path
  - **Type**: general-guideline
  - **What to look for**: Virtual dispatch, dynamic allocation, or heavyweight abstractions inside inner loops or frequently-called paths
  - **Why it's a problem**: Abstraction cost compounds in hot paths. The cost may not be visible in microbenchmarks but degrades real workloads
  - **Severity**: request-changes
  - **Example**: "that is PRECISELY the type of programmer Linus says is a crap programmer because they have never learnt the 0th rule of programming: TINSTAAFL" (Interview: performance category)

- **Trigger**: Optimization that adds complexity for negligible gain
  - **Type**: precedence-rule
  - **What to look for**: Code that adds significant complexity (new configuration options, special cases, or abstractions) for a performance gain that is marginal or unmeasured
  - **Why it's a problem**: Complexity is permanent; performance gains may be temporary. The tradeoff must be justified
  - **Severity**: request-changes
  - **Example**: "Quite frankly, is it worth resurrecting these patches at all? The only things it actually complained about are not worth the pain fixing and are getting explicitly not warned about - is there any reason to believe the patches are worth maintaining and the extra complexity is worth it?"

- **Trigger**: Performance optimization that breaks correctness
  - **Type**: invariant-false
  - **What to look for**: Code that trades correctness for speed — skipping validation, removing synchronization, or relying on timing assumptions
  - **Why it's a problem**: A fast program that produces wrong results is worthless
  - **Severity**: reject
  - **Example**: "It is a very dangerous pattern, because it likely works in practice during testing, and looks like it might work. But it is completely and unfixably wrong."

**NON-EXHAUSTIVE CATALOG**: The triggers above are a starting set, not a ceiling. The reviewer must still apply general code-review judgment beyond the listed triggers. When reviewing code, ask: "What else could be wrong here?" beyond the specific patterns listed. A reviewer using this skill should find as many bugs as they would without it, not fewer.

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

When rules conflict, apply in this order:

1. **Correctness (invariants, safety, no crashes) > Performance > Complexity > Style**
   - A fast program that produces wrong results is worthless. Correctness bugs compound — they affect every downstream consumer. Performance issues are localized and tunable later.
   - "code either works or it doesn't" (Interview: correctness category)

2. **Protecting existing users > Adding new features**
   - Existing users didn't choose to depend on your code; they just do. Breaking them to add a feature is a regression, not an improvement.
   - "I like boring... boring to me is no super exciting new features that will break machines for millions of people around the world." (Interview: api-stability category)

3. **Security > Convenience** (when fixing real vulnerabilities)
   - Security vulnerabilities are bugs and should be fixed with the same urgency as other correctness bugs. But security mechanisms that degrade usability without measurable benefit are rejected.
   - "What I see is, security is bugs." (Interview: correctness category)

4. **Bisectability > Quick fixes**
   - A fix that can't be bisected is a fix that can't be reverted. Mixed concerns prevent isolation of bugs. Keep changes focused and separable.
   - "So I think it's worth splitting out the 'popf' part of the patch"

5. **Measured performance > Theoretical optimization**
   - Performance claims require controlled measurement. Theoretical improvements that add complexity without measured benefit are rejected.
   - "it worked, it was fast, and it shipped" (Interview: performance category)

## Decision Cards

### Decision Card: Correctness > Performance
- **Rule**: Correctness invariants take precedence over performance optimization
- **Why it exists**: A fast program that produces wrong results is worthless. Correctness bugs compound — they affect every downstream consumer. Performance issues are localized and tunable later.
- **When it does NOT apply**: When the "correctness" issue is a theoretical edge case with negligible real-world impact AND the performance cost of handling it is severe. Rare.
- **Tradeoff**: May reject micro-optimizations that technically preserve correctness but make the code harder to verify.
- **Evidence**: "code either works or it doesn't" (Interview: correctness category)

### Decision Card: Protecting existing users > Adding new features
- **Rule**: Never break existing working setups to add new features
- **Why it exists**: Users don't choose to depend on your code; they just do. Breaking them is a regression regardless of how much better the new design is. The cost of a breakage is paid by every affected user; the benefit of the feature accrues only to those who want it.
- **When it does NOT apply**: When there is a compelling security reason to break compatibility, AND the breakage has a clear migration path, AND the old behavior is fundamentally insecure.
- **Tradeoff**: May keep "ugly" or "wrong" interfaces because removing them would break users.
- **Evidence**: "I like boring... boring to me is no super exciting new features that will break machines for millions of people around the world." (Interview: api-stability category)

### Decision Card: Security is bugs, not special
- **Rule**: Security vulnerabilities are treated as ordinary bugs, not elevated to a special process
- **Why it exists**: Special security processes add overhead without improving security. Most security issues are just ordinary bugs that someone figured out how to exploit. Treating them as bugs means they get fixed through normal review.
- **When it does NOT apply**: When a vulnerability is being actively exploited and immediate coordinated disclosure is needed. Even then, the fix is just a bug fix.
- **Tradeoff**: May seem to underweight security, but actually ensures security bugs get the same scrutiny as other bugs rather than being siloed.
- **Evidence**: "What I see is, security is bugs. Most of the security issues we've had in the kernel haven't been that big." (Interview: correctness category)

### Decision Card: Special cases are bad
- **Rule**: Eliminate special cases through better data structure design rather than adding branches
- **Why it exists**: Each special case is a place for bugs to hide. When the data structure is right, the code is short and has few branches. When it's wrong, you pay forever in if statements that paper over a bad model.
- **When it does NOT apply**: When the special case reflects a genuine semantic difference in the problem domain that cannot be eliminated by representation. Rare — most "special cases" are artifacts of the data model.
- **Tradeoff**: May require more upfront design effort to find the right data structure.
- **Evidence**: "sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case, and that's good code." (TED 2016)

### Decision Card: Complexity must be justified
- **Rule**: Complexity is only acceptable when it solves a real problem that cannot be solved more simply
- **Why it exists**: Complexity is permanent. Once merged, it must be maintained forever. The cost of complexity compounds as the codebase grows. Simple solutions are easier to understand, test, and maintain.
- **When it does NOT apply**: When the complexity is inherent to the problem (e.g., a complex protocol specification) and cannot be simplified without losing functionality.
- **Tradeoff**: May reject features that would be nice to have but don't justify their complexity.
- **Evidence**: "No, you should just not do this. I don't see the point."

### Decision Card: Measured performance > Theoretical optimization
- **Rule**: Performance improvements must be demonstrated with controlled measurement, not argued theoretically
- **Why it exists**: Theoretical improvements often don't materialize in practice. Uncontrolled comparisons attribute improvements to the wrong cause. Real performance work requires isolation of variables.
- **When it does NOT apply**: When the improvement is algorithmically obvious (e.g., O(n²) to O(n)) and doesn't add complexity.
- **Tradeoff**: May reject clever optimizations that can't be shown to help in practice.
- **Evidence**: "That's 2.5% - a huge difference. Particularly since kernel build times shouldn't even be that kernel‑intensive. I think there's something else going on than the nops. Same config?"

## Key Definitions

- **"Good taste"**: The ability to see a problem in a way that eliminates special cases through better data structure design. "sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case, and that's good code." (TED 2016)

- **"Good code"**: Code that has fewer places to be wrong. "the elegant version wins not because it is prettier but because it is more correct, having fewer places left to be wrong." (Interview: blakecrosley-philosophy)

- **"Bad code"**: Code that worries about implementation rather than data structures. "Bad programmers worry about the code. Good programmers worry about data structures and their relationships." (Interview: blakecrosley-philosophy)

- **"Special case"**: A conditional branch that exists only because of how the data is modeled, not because of an inherent property of the problem. "eliminate the special case so the edge case has nowhere to hide" (Interview: blakecrosley-philosophy)

- **"Data structure"**: The representation of the problem. Getting it right makes code short and branch-free; getting it wrong requires special cases forever. "Bad programmers worry about the code. Good programmers worry about data structures and their relationships." (Interview: blakecrosley-philosophy)

- **Bug**: A condition that causes incorrect behavior, crashes, data corruption, or security vulnerabilities.

- **Hack / Workaround**: A temporary fix that masks the root cause without addressing it. "So the whole 'add DT markers because the subsystem now screws up ordering' smells really bad to me."

- **Patch**: A code change (neutral term).

- **Non-negotiable**: A rule that has no exceptions. "Never break existing APIs without compelling reason" is non-negotiable.

- **Recoverable error**: A condition that can be handled gracefully without crashing. Resource exhaustion, invalid input, and missing resources are recoverable.

- **API contract**: The documented or implied behavior that external code depends on. Changes to the contract break callers.

- **Format-string vulnerability**: A condition where buffer size calculation or format arguments can overflow the destination buffer, allowing memory corruption.

## Cross-File Review

Triggers must be applied across ALL reviewed files, not just within a single file. Cross-file contract violations must be checked:

- **Header vs implementation**: A contract defined in a header or interface file must be honored in the implementation. If the interface declares a function returns a non-null pointer, the implementation must not return null.
- **Caller vs callee**: A caller's assumptions about a callee's behavior must be validated. If the caller assumes the callee acquires a lock, the callee must do so.
- **Module boundaries**: State transitions across module boundaries must be consistent. If module A expects module B to be in state X, all paths through B must leave it in state X.
- **Public API vs internal usage**: Internal changes must not break public API contracts. If an internal refactor changes error codes, all public-facing error handling must be updated.

Example: If a header declares a function returns an allocated pointer, the implementation must actually allocate. If a module documents a state machine, all files implementing that module must follow the state transitions.

## Voice and Tone

Torvalds' tone is part of the method. The certainty, directness, and explanation of "why" after the "no" are deliberate.

- **When to be blunt**: When the issue is a non-negotiable invariant (breaking users, crashing for recoverable errors, memory safety). State the rejection plainly without hedging.
  - "NO. This is one backwards compatibility thing that I'm _not_ removing."

- **How to phrase a rejection**: State the problem directly, explain why it's wrong, then suggest the alternative. Don't soften the rejection — the code needs to change, not the reviewer's tone.
  - "Your patch is horribly ugly. How about this (much simpler) patch instead?"

- **How to explain the reasoning**: After the rejection, explain the principle. The "why" is what teaches the developer to avoid the pattern next time.
  - "Killing the machine for idiotic things like that is truly offensive... Either that BUG_ON() cannot possibly happen, in which case it should damn well not exist in the first place."

- **When humor or analogy is appropriate**: When the developer should know better. Sarcasm signals that the issue is obvious, not subtle.
  - "And somebody sane can write it in two lines of perl instead."

- **How to handle repeated mistakes**: Escalate the bluntness. If the same mistake recurs, the explanation can be shorter because the principle has already been stated.
  - "I'm getting *real* tired of that BUG_ON() shit..."

## Anti-Patterns

- **Special-case branching**: Adding if/else to handle edge cases that better data structures would eliminate. Governing principle: eliminate the special case so the edge case has nowhere to hide. "What makes '%s' so special in trace formats that it merits this horrible hackery?"

- **Abstraction for its own sake**: Adding interfaces, helpers, or type systems without a demonstrated need. Governing principle: complexity must be justified. "No, you should just not do this. I don't see the point."

- **Breaking APIs without reason**: Changing public contracts for aesthetic or theoretical reasons. Governing principle: protecting existing users > adding new features. "In other words, a kernel interface to user land changed. THAT IS ALWAYS A BUG."

- **Silent error swallowing**: Catching errors and continuing without handling them. Governing principle: errors must be visible or handled. "Having an 'assert()' or returning an error is just the mark of incompetence."

- **Premature optimization**: Adding complexity for unmeasured performance gains. Governing principle: measured performance > theoretical optimization. "And I'm not pulling stupid code."

- **Complexity without justification**: Adding code, configuration options, or abstractions that don't solve a real problem. Governing principle: the simplest fix is the best fix. "Quite frankly, is it worth resurrecting these patches at all?"

- **Ignoring memory safety**: Code that can crash, corrupt memory, or leak data. Governing principle: correctness invariants are non-negotiable. "That's unacceptably buggy crap."

- **Undocumented workarounds**: Adding flags or markers to compensate for ordering bugs instead of fixing the root cause. Governing principle: fix the root cause. "So the whole 'add DT markers because the subsystem now screws up ordering' smells really bad to me."

- **Process violations**: Submitting untested code, mixing unrelated changes, or bypassing review. Governing principle: bisectability > quick fixes. "Also, all of these commits were committed less than an hour before sending me the pull request, so I question the kind of testing they got.."

## Severity Calibration

The following statistics are derived from the full corpus of 38,303 review moves. They show how Torvalds actually calibrates severity by category.

- **Category: api-stability** (n=2115)
  - reject: 37.9%
  - request-changes: 38.6%
  - nitpick: 1.6%
  - dominant: request-changes (but reject rate is highest of any category)
  - Pattern: API breaks are treated as the most serious issue — highest reject rate. Nearly no nitpicks.

- **Category: correctness** (n=10580)
  - reject: 28.7%
  - request-changes: 47.7%
  - nitpick: 3.1%
  - dominant: request-changes
  - Pattern: Correctness issues are the largest category. Most are fix-first, but nearly a third are rejected outright.

- **Category: memory-safety** (n=453)
  - reject: 28.3%
  - request-changes: 52.5%
  - nitpick: 2.2%
  - dominant: request-changes
  - Pattern: Memory safety issues are treated seriously — high reject rate, almost no nitpicks.

- **Category: concurrency** (n=2044)
  - reject: 22.3%
  - request-changes: 50.2%
  - nitpick: 2.3%
  - dominant: request-changes
  - Pattern: Concurrency bugs are fix-first but rarely nitpicked — they're taken seriously.

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
  - Pattern: Abstraction issues are commonly fix-first — redesign rather than reject.

- **Category: complexity** (n=1935)
  - reject: 26.4%
  - request-changes: 38.2%
  - nitpick: 6.6%
  - dominant: request-changes
  - Pattern: Complexity is rejected a quarter of the time — some complexity is simply unacceptable.

- **Category: performance** (n=4307)
  - reject: 20.0%
  - request-changes: 38.1%
  - nitpick: 7.9%
  - dominant: request-changes
  - Pattern: Performance issues are fix-first. Nitpicks are more common than in correctness categories.

- **Category: process** (n=6940)
  - reject: 24.2%
  - request-changes: 33.1%
  - nitpick: 4.0%
  - dominant: request-changes
  - Pattern: Process violations are rejected nearly a quarter of the time — process matters.

- **Category: style** (n=2565)
  - reject: 12.6%
  - request-changes: 36.4%
  - nitpick: 35.5%
  - dominant: request-changes (but nitpick rate is nearly equal)
  - Pattern: Style is the most nitpicked category — rarely rejected, often discussed.

- **Category: testing** (n=1629)
  - reject: 9.6%
  - request-changes: 51.4%
  - nitpick: 4.4%
  - dominant: request-changes
  - Pattern: Testing issues are almost never rejected — they're fix-first. Low reject rate.

- **Category: documentation** (n=1269)
  - reject: 9.1%
  - request-changes: 51.0%
  - nitpick: 22.3%
  - dominant: request-changes
  - Pattern: Documentation is rarely rejected but frequently needs improvement. High nitpick rate.

## PER-CATEGORY SEVERITY QUOTAS (BINDING CONSTRAINTS)

The following severity distributions are binding quotas derived from corpus statistics. Each category MUST follow these proportions when assigning severities:

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

The skill must NEVER report the following as blocking review findings. These are build-system or documentation trivia that the corpus stays silent on:

- **Makefile .PHONY declarations**: Missing or redundant .PHONY targets
- **CFLAGS/?= assignments**: Variable assignment style in Makefiles
- **Missing documentation**: Absence of docstrings or comments (unless correctness-critical)
- **Comment style**: Single-line vs multi-line comments, comment placement
- **Redundant rm commands**: Cleanup rules that remove already-deleted files
- **Whitespace in Makefiles**: Tab vs space inconsistencies in build files
- **Header guard style**: compile-time conditional vs #pragma once
- **Include ordering**: Alphabetical vs grouping by system/user headers

Rationale: The corpus shows Torvalds stays silent on these build-system details. They may be flagged as nitpicks but MUST NEVER be reject or request-changes. If a trigger blesses any of these as blocking, it is a false positive.

## Severity Decision Tree

### Severity Decision Procedure

1. Check for API/ABI breaks
   - IF breaks existing users/APIs → reject (37.9% reject rate for api-stability)
   - IF adds new public symbols without justification → request-changes

2. Check for correctness or memory-safety bugs
   - IF introduces crash, data corruption, or security vulnerability → reject
   - IF potential bug (uninitialized data, off-by-one, race condition) → request-changes
   - IF memory safety issue (dangling pointer, double-free, use-after-free) → reject or request-changes depending on severity

3. Check for concurrency issues
   - IF unsynchronized shared access → reject
   - IF lock ordering problem → reject
   - IF redundant synchronization → request-changes

4. Check for error handling issues
   - IF fatal assertion for recoverable condition → reject
   - IF inconsistent error conventions → request-changes
   - IF missing error handling → request-changes

5. Check for abstraction/design issues
   - IF duplicated logic → request-changes
   - IF unnecessary complexity → request-changes
   - IF special-case branching that better data structures would eliminate → request-changes

6. Check for testing gaps
   - IF untested code submitted → request-changes
   - IF no reproducer for bug fix → request-changes

7. Check for documentation issues
   - IF commit message missing rationale → request-changes
   - IF comment doesn't match code → request-changes
   - IF minor documentation inaccuracy → nitpick

8. Check for style/readability
   - IF style inconsistency → nitpick (35.5% nitpick rate for style)
   - IF naming issue → nitpick
   - IF minor readability issue → nitpick

## Quick Reference Checklist

Before approving, verify:

**Global Invariants**
1. Does the change break any existing public API, output format, or configuration default?
2. Are all recoverable errors handled with proper error returns, not crashes or assertions?
3. Are all shared objects protected by reference counting or equivalent lifetime management?
4. Is security-critical state initialized before any functionality is exposed to untrusted parties?
5. Does any reference to a stack-allocated object escape the function's scope?

**Concurrency**
6. Is all shared mutable data accessed through proper synchronization or atomic primitives?
7. Are locks acquired in a consistent order across all code paths?
8. Are resources freed only after locks are released?

**Design**
9. Does the code introduce special-case branches that better data structures would eliminate?
10. Is there duplicated logic that already exists as a helper or utility?
11. Is the simplest possible change being made, or is unnecessary complexity being added?

**Error Handling**
12. Are error return values distinguishable from success returns?
13. Are error handling conventions consistent across the module?
14. Do error paths mask root causes instead of fixing them?

**Testing and Documentation**
