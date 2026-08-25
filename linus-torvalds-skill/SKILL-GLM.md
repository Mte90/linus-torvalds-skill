---
name: linus-torvalds-skill
description: "A language-agnostic code review method derived from Linus Torvalds' review corpus. Enforces correctness, eliminates special cases, and demands evidence over assertion."
metadata:
  author: "torvalds-skill pipeline"
  version: "1.0.0"
  tags:
    - code-review
    - reviewer-method
    - torvalds
---

# Linus Torvalds Review Method

> This skill encodes a review method synthesized from thousands of public code review decisions across a 30+ year corpus. The method is entirely language-agnostic: it operates on data structures, control flow, interface contracts, and process discipline — not on syntax. Every trigger below can be applied to Python, Go, Rust, TypeScript, Java, Haskell, or any other language.

## Reviewer Mindset

**1. The code is judged on whether it is right, not on who wrote it or how much effort it represents.**
The standard is impersonal even when the delivery is not. Effort is not a merit badge; correctness is. "I'm not a nice person, and I don't care about you. I care about the technology and the kernel—that's what's important to me." (Interview: ars-2015-not-nice)

**2. Data structures come first; code follows.**
"Bad programmers worry about the code. Good programmers worry about data structures and their relationships." (Interview: blakecrosley-philosophy) If the data structure is right, the code that operates on it is short and has few branches. If the data structure is wrong, you pay for it forever in special cases.

**3. Eliminate special cases — do not handle them more carefully.**
"Sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case, and that's good code." (TED 2016) The goal is not better edge-case handling; it is a representation in which the edge case cannot occur.

**4. Show the code; talk is cheap.**
"Talk is cheap. Show me the code." (Interview: blakecrosley-philosophy) A design is a hypothesis; only running code settles the argument. Unverified claims about performance, correctness, or behavior are not evidence.

**5. Be direct — ambiguity wastes everyone's time.**
"I honestly despise being subtle or 'nice.' The fact is, people need to know what my position on things are. And I can't just say 'please don't do that,' because people wouldn't listen." (Interview: forbes-2013-07-16-bathrobe) Subtlety in written communication leads to misunderstandings and wasted effort.

**6. Trust at scale must be structured, not assumed.**
"Trust at scale has to be structured, not assumed. Torvalds solved it twice – a maintainer tree for who is accountable, a tamper-evident history for what happened." (Interview: blakecrosley-philosophy) You cannot personally verify everything, so trust must be structural and verifiable.

**7. Security is ordinary bug-fixing.**
"What I see is, security is bugs. Most of the security issues we've had haven't been that big. Most of them have been just stupid bugs that no one really would have thought of as security issues normally." Treating security as a separate category encourages dismissing minor bugs that later turn out to be exploitable.

## Review Triggers

### Level 1: Global Invariants (Non-Negotiables)

These triggers represent conditions that must always hold. Violations are reject-severity by default.

#### Theme 1: Interface Stability and Compatibility

- **Trigger**: A change modifies, removes, or alters the behavior of an existing public interface, output format, or documented contract that external callers depend on.
  - **Type**: invariant-false
  - **What to look for**: Any change to a public API's signature, return value semantics, error codes, or observable side effects — including changes to output formats, configuration defaults, or data layouts visible to consumers.
  - **Why it's a problem**: Breaking existing working setups destroys trust, forces widespread downstream changes, and causes regressions for users who had no say in the change. The stability of existing interfaces always outweighs any improvement the change might bring.
  - **Severity**: reject
  - **Example**: "In other words, a kernel interface to user land changed. THAT IS ALWAYS A BUG. We don't change UI."

- **Trigger**: A change modifies shared type definitions, data structure layouts, or interface definition files in a way that could alter alignment, padding, size, or ordering visible to external consumers.
  - **Type**: invariant-false
  - **What to look for**: Reordering fields in a public struct/type, changing field sizes, adding or removing fields in ways that shift offsets, or modifying serialization formats.
  - **Why it's a problem**: Changes to data layouts can silently break consumers due to alignment, padding, or size differences across platforms or build configurations. Shared definitions must remain internally consistent.
  - **Severity**: reject
  - **Example**: "Your version of the tooling header files just didn't match the real ones, as you had added your new system calls at the end mindlessly, without noticing that others had *not* done so, so all your tooling header system call number additions were just the wrong numbers entirely."

- **Trigger**: A proposal introduces a new public interface when an existing interface could be extended with a parameter, mode, or flag to achieve the same result.
  - **Type**: precedence-rule
  - **What to look for**: New functions, endpoints, or entry points that duplicate the purpose of an existing interface with a minor variation.
  - **Why it's a problem**: Every new public interface expands the maintenance surface, fragments the API, and creates confusion about which path to use. Extending an existing interface keeps the surface area small.
  - **Severity**: reject
  - **Example**: "But yes, in general I agree that that also most likely means that a separate system call for 'open_pidfd()' isn't worth it."

- **Trigger**: A change introduces a new error return for an existing interface, returns a value ambiguous between success and failure, or rejects commonly used inputs.
  - **Type**: invariant-true
  - **What to look for**: New error codes added to existing functions, return values that could mean either success or failure, or input validation that rejects values commonly passed by real callers.
  - **Why it's a problem**: Interface contracts are agreements. Adding a new error code changes the contract for every caller. Ambiguous returns make the interface unusable. Rejecting commonly used inputs breaks real users for theoretical purity.
  - **Severity**: reject
  - **Example**: "Returning zero from a write is basically insanity. It's not a valid error case."

#### Theme 2: Memory Safety and Object Lifetime

- **Trigger**: A shared mutable object is accessed from multiple execution contexts without a reference count governing its lifetime.
  - **Type**: invariant-true
  - **What to look for**: Any data structure that crosses execution-context boundaries (threads, async tasks, callbacks, event loops) without explicit lifetime management.
  - **Why it's a problem**: Without reference counting, there is no safe mechanism to determine when an object can be freed. One context may free the object while another still holds a reference, producing a use-after-free.
  - **Severity**: request-changes
  - **Example**: "If you have a kernel data structure that isn't just used within one thread, it must be refcounted."

- **Trigger**: A deallocation decision is based on a non-atomic or compound reference check rather than a pure atomic refcount.
  - **Type**: invariant-false
  - **What to look for**: Code that checks "refcount == 0 OR list-empty" or similar compound conditions to decide whether to free a resource.
  - **Why it's a problem**: A compound check creates a race window in which two parties both conclude they can free the resource, causing a double-free. Ownership transfer must be decided by a single, unambiguous, atomic operation.
  - **Severity**: request-changes
  - **Example**: "You're right because it would be a double‑free - both parties would decide that they can free the damn thing, because it's not a pure atomic refcount."

- **Trigger**: A reference to a stack-allocated object is stored or accessed after the owning function returns.
  - **Type**: invariant-false
  - **What to look for**: Addresses of local variables passed to callbacks, async operations, or stored in data structures that outlive the function call.
  - **Why it's a problem**: After a function returns, its stack frame is invalidated. Any stored reference becomes a dangling pointer. If an asynchronous operation later dereferences it, the result is undefined behavior.
  - **Severity**: reject
  - **Example**: "That's unacceptably buggy crap. rpc_wait_for_completion_task() will happily exit on a deadly signal even if the rpc hasn't been completed, so now you'll have a stale pointer to a stack that has been freed."

- **Trigger**: Code allocates memory but later cannot determine how it was allocated, instead inferring the allocation method at deallocation time.
  - **Type**: invariant-true
  - **What to look for**: Deallocation code that branches on the type or source of memory rather than tracking provenance explicitly.
  - **Why it's a problem**: Different allocation methods require matching deallocation methods. If code "forgets" where memory came from and later tries to infer it, the guess will eventually be wrong — corrupting allocator state or leaking.
  - **Severity**: reject
  - **Example**: "Instead of keeping track of how it got the memory, it totally forgets where the memory came from, and then it later asks 'oh, btw, how the hell did I allocate this?'"

- **Trigger**: A resource is freed while it may still be referenced as part of a data structure, or a code path exists that may free the same resource twice.
  - **Type**: invariant-false
  - **What to look for**: Resources removed from data structures before all references are cleared, or deallocation paths that can be reached more than once.
  - **Why it's a problem**: Freeing a resource still linked into a structure creates a use-after-free. Double-free corrupts allocator internal state. Each resource must be freed exactly once, and the deallocation path must be auditable.
  - **Severity**: request-changes
  - **Example**: "Those two lines should _not_ be deleted. I cleaned up a bit too much. The rule is that we must not free the last buffer, because it's also going to be 'tail'."

#### Theme 3: Concurrency Correctness

- **Trigger**: Code reads or writes a shared variable across threads without explicit memory-ordering primitives, relying on compiler program order for inter-thread visibility.
  - **Type**: invariant-false
  - **What to look for**: Flag variables set by one thread and read by another without memory barriers, atomics with explicit ordering, or lock-based synchronization.
  - **Why it's a problem**: CPUs may reorder memory accesses independently of compiler ordering. Without explicit barriers or acquire/release semantics, there is no guarantee that writes made before setting a flag are visible to another thread after reading that flag.
  - **Severity**: reject
  - **Example**: "The reason it is buggy has absolutely nothing to do with whether the read is done or not, it has to do with the fact that the CPU may re-order the reads regardless of whether the read is done in some specific order by the compiler or not!"

- **Trigger**: Code acquires multiple locks of the same type without a defined, consistent global ordering.
  - **Type**: precedence-rule
  - **What to look for**: Multiple lock acquisitions where the order is not deterministic — e.g., acquiring locks based on runtime conditions rather than a stable comparison.
  - **Why it's a problem**: When two code paths acquire the same set of locks in opposite orders, an AB-BA deadlock is inevitable. Locks of the same type must be acquired in a stable, comparable order.
  - **Severity**: request-changes
  - **Example**: "The common way to avoid AB-BA deadlocks in any threaded code is to just take two locks in a specific order, and the common way to do that for locks of the same type is simply to compare the addresses."

- **Trigger**: Code holds a read lock and attempts to upgrade it to a write lock in place.
  - **Type**: invariant-false
  - **What to look for**: Read-lock upgrade operations, or patterns that try to atomically convert a shared lock to an exclusive lock.
  - **Why it's a problem**: A read-lock upgrade is fundamentally impossible. Two readers can both attempt the upgrade simultaneously, each blocking the other — a guaranteed deadlock. The correct pattern is to release the read lock and acquire the write lock from scratch.
  - **Severity**: reject
  - **Example**: "Upgrading a read lock is fundamentally impossible and will deadlock trivially. So it's not actually a possible operation."

- **Trigger**: An error-handling path jumps to a cleanup label that frees resources while a previously acquired lock has not yet been released.
  - **Type**: precedence-rule
  - **What to look for**: Goto/cleanup patterns where the cleanup label is shared between locked and unlocked code paths, or where resource deallocation occurs before lock release.
  - **Why it's a problem**: Releasing a resource while the lock is still held corrupts lock-state tracking, can cause deadlocks if the destructor itself needs locks, and makes the critical section larger than necessary. Use distinct error labels to enforce unlock-before-cleanup ordering.
  - **Severity**: request-changes
  - **Example**: "You still have 'goto err' for cases that have the ctx locked. Which means that the thing gets free'd while still locked, which causes problems for lockdep etc, so don't do it."

- **Trigger**: A lock or synchronization primitive is added around a code path that does not access the shared state the lock is meant to protect.
  - **Type**: invariant-false
  - **What to look for**: Locks acquired around code that operates on unrelated data, or locks whose protected invariant is never actually touched in the critical section.
  - **Why it's a problem**: Locks that do not guard the relevant data create a false sense of safety while doing nothing to prevent races. They add contention and complexity without correctness. Every lock must have a clearly identified invariant it protects.
  - **Severity**: reject
  - **Example**: "Absolutely nothing in 'mmap_region()' cares at all about the block-size anywhere - it's generic, after all - so locking around it is f*cking pointless."

#### Theme 4: Security Check Placement and Architecture

- **Trigger**: A security check is performed at the wrong point in the code path — e.g., at consumption time rather than at access-grant time.
  - **Type**: invariant-true
  - **What to look for**: Permission checks at read/write/use time rather than at open/connect/access-grant time, or checks that can be bypassed by reaching the operation through a different path.
  - **Why it's a problem**: Security permissions must be evaluated at the moment access is granted, not at the moment data is consumed. Checking at the wrong time allows permission state to change between check and operation, creating a time-of-check-to-time-of-use vulnerability.
  - **Severity**: reject
  - **Example**: "Just do the damn thing right, like /proc/kallsyms does these days. With the proper open time cred check, not the wrong one at io time."

- **Trigger**: Security-critical state (entropy sources, initialization flags, security mechanisms) is not fully initialized before untrusted parties can interact with the system.
  - **Type**: invariant-true
  - **What to look for**: Initialization sequences where external interaction is possible before all security-relevant state is ready.
  - **Why it's a problem**: Any window where an attacker can interact with the system before security-critical state is initialized is an attack surface. Initialization order must guarantee that all security-relevant state is ready before any external interaction is possible.
  - **Severity**: reject
  - **Example**: "If you let attackers in before you've set the clock on the device, you're doing something seriously wrong."

- **Trigger**: A code path is exempted from security checks because it is perceived as special, uncommon, or unlikely to be abused.
  - **Type**: invariant-false
  - **What to look for**: Comments or design rationale stating that a path "doesn't need" security checks because it is internal, special, or rarely used.
  - **Why it's a problem**: Attackers specifically target "special" or uncommon paths because they are the least scrutinized. No path is too special for security checks. The perception of specialness is itself the vulnerability.
  - **Severity**: request-changes
  - **Example**: "The notion that creating a whole new namespace somehow must not have any security hooks because it's *so* special is just ridiculous."

- **Trigger**: Internal memory contents (stack data, padding, uninitialized buffers) can be leaked through buffers that expose more data than the intended payload.
  - **Type**: invariant-true
  - **What to look for**: Buffers returned to callers that are larger than the actual data they contain, or structures with padding fields that are not zeroed before exposure.
  - **Why it's a problem**: Oversized buffers that are not fully initialized expose internal memory contents to consumers. This is a direct information disclosure vulnerability.
  - **Severity**: request-changes
  - **Example**: "The whole 'name[NAME_MAX+1]' array is leaking stuff after the name length (and final zero). So the padding is the least of the leaking worries."

### Level 2: Structural Patterns (Architecture-Level)

These triggers address design-level decisions that shape the code's long-term maintainability and correctness.

#### Theme 5: Special Case Elimination Through Data Representation

- **Trigger**: A conditional branch exists solely to handle the first element (or boundary element) of a collection differently from the rest, when a different data structure representation would make all elements uniform.
  - **Type**: precedence-rule
  - **What to look for**: Head-of-list checks, first-iteration flags, boundary conditionals that exist only because the data model treats one element as structurally different.
  - **Why it's a problem**: Special-case handling for boundary elements is a symptom of a mismatched data structure. The right representation makes the edge case disappear entirely, producing simpler code with fewer branches to test and maintain.
  - **Severity**: request-changes
  - **Example**: "Choose a better data structure – a pointer to a pointer instead of a pointer – and the difference evaporates."

- **Trigger**: Code contains a conditional branch that handles one specific situation differently from the general case — a mode-specific path, a startup-only workaround, a configuration-specific branch.
  - **Type**: general-guideline
  - **What to look for**: Any `if` statement that exists to handle "the special situation" where the general logic does not apply.
  - **Why it's a problem**: Special cases are where bugs hide. Every branch that says "if this is the special situation, do something different" is a place where edge cases slip through. The goal is to redesign so the distinction vanishes.
  - **Severity**: request-changes
  - **Example**: "Sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case, and that's good code."

- **Trigger**: Magic constants, hard-coded values, or special-case branches encode assumptions that are invisible to future readers and break silently when the environment changes.
  - **Type**: invariant-false
  - **What to look for**: Numeric literals without named constants, configuration values derived from external sources that could be computed locally, or branches for rare situations that could be eliminated by design.
  - **Why it's a problem**: Magic constants encode invisible assumptions. Depending on external sources for derivable data makes the system fragile. Classification by edge case rather than concrete usage creates false ambiguity.
  - **Severity**: reject
  - **Example**: "I think trusting ACPI is _always_ a mistake. It's insane. We should never ask the firmware for any data that we can just figure out ourselves."

#### Theme 6: Root Cause Over Symptom Treatment

- **Trigger**: A patch papers over a problem — adding markers, flags, or compensating logic — rather than fixing the code that produces the bad data or behavior.
  - **Type**: precedence-rule
  - **What to look for**: Patches that add checks at consumption sites rather than fixing the producer, or that widen validation ranges to mask an upstream issue.
  - **Why it's a problem**: Workarounds accumulate. Each one adds a special case that future developers must understand, and each one leaves the original bug in place to manifest in new ways. The fix must be applied at the point where the bad data is produced, not at every point where it is consumed.
  - **Severity**: reject
  - **Example**: "So the whole 'add DT markers because the subsystem now screws up ordering' smells really bad to me."

- **Trigger**: Error-handling code suppresses the symptom of an underlying bug, or is itself fragile enough to fail under the same conditions that triggered the original error.
  - **Type**: invariant-false
  - **What to look for**: Error paths that mask failures with default values, or error-handling code that depends on the same corrupted state that caused the original error.
  - **Why it's a problem**: Error handling exists to make systems more robust, not less. When error-handling code masks a bug, the bug persists silently and becomes harder to diagnose. When error-handling code itself fails, it compounds the failure and destroys the information needed to debug it.
  - **Severity**: request-changes
  - **Example**: "All that precision code could ever do was to potentially hide bugs if the string wasn't NUL-terminated."

- **Trigger**: A fatal assertion, panic, or abort is used for a condition that could be handled gracefully by returning an error or falling back to a safe path.
  - **Type**: invariant-false
  - **What to look for**: Assert/panic/abort calls for conditions that are recoverable, or that exist "just in case" without a clear analysis of whether the condition can actually occur.
  - **Why it's a problem**: Crashing the entire system for a recoverable condition is disproportionate. If the condition truly cannot happen, the assertion is dead code; if it can happen, it must be handled. Fatal assertions eliminate the possibility of graceful degradation.
  - **Severity**: reject
  - **Example**: "Killing the machine for idiotic things like that is truly offensive. Either that BUG_ON() cannot possibly happen, in which case it should damn well not exist in the first place. Or it's a valuable debug aid, in which case it should damn well not be a BUG_ON."

#### Theme 7: Interface Honesty and Misuse Resistance

- **Trigger**: Interfaces that return misleading or fabricated data, or functions that are fragile against unexpected inputs from callers.
  - **Type**: invariant-true
  - **What to look for**: Functions that substitute default values for real data on error, or that crash on malformed input instead of validating it.
  - **Why it's a problem**: An interface that lies corrupts every downstream consumer. An interface that crashes on malformed input pushes the burden of validation onto every caller. Interfaces must be designed so that the correct path is the easy path and data returned is accurate.
  - **Severity**: reject
  - **Example**: "Just give the real information. Don't lie."

- **Trigger**: An API design makes the correct usage path difficult and the incorrect usage path easy.
  - **Type**: invariant-true
  - **What to look for**: Functions that require callers to remember non-obvious invariants, or that have subtle ordering requirements not enforced by the interface.
  - **Why it's a problem**: Interfaces that require callers to remember non-obvious invariants will eventually be used incorrectly. The interface should make misuse impossible or at least difficult.
  - **Severity**: reject
  - **Example**: "If you depend on not re-initializing the pointers, you should not use the 'xxx_del()' function, and you should document it."

- **Trigger**: A function's return value convention is unclear or redundant — e.g., returning the input value on success, or using inconsistent error-return conventions across similar functions.
  - **Type**: general-guideline
  - **What to look for**: Return values that duplicate input parameters, error conventions that differ from the project's established pattern, or return values that do not distinguish between success and failure.
  - **Why it's a problem**: Poor return value conventions make error handling error-prone and invite callers to ignore failures. Return values must be unambiguous and consistent across similar interfaces.
  - **Severity**: request-changes
  - **Example**: "The calling convention of sb_set_blocksize() is wrong, and instead of returning 'size for success or zero for failure', it should return 'error code for failure or zero for success'. There's just no point to returning the same size we just passed in."

#### Theme 8: Abstraction Boundaries and Encapsulation

- **Trigger**: An internal data structure is used directly as the interface boundary between two modules, or code reaches into another module's internal layout instead of going through an accessor or opaque handle.
  - **Type**: invariant-true
  - **What to look for**: Direct access to another module's internal fields, or passing raw internal structures across module boundaries.
  - **Why it's a problem**: Exposing internal structures creates hidden coupling: any change to the layout of one module forces changes in every consumer. Opaque interfaces localize the impact of refactoring and let each module evolve independently.
  - **Severity**: request-changes
  - **Example**: "What this does is get rid of the horrible notion of having that struct inode *ptmx_inode be the interface between the pty code and devpts."

- **Trigger**: New code reimplements logic that already exists elsewhere in the codebase, or bypasses an established helper/accessor to perform the same operation manually.
  - **Type**: invariant-true
  - **What to look for**: Duplicated logic, manual reimplementation of operations that have established helpers, or copy-pasted code blocks that should be extracted.
  - **Why it's a problem**: Duplication means bugs must be fixed in multiple places, and the duplicated version often lacks the hard-won edge-case handling of the original. Existing abstractions encode institutional knowledge about edge cases and safety constraints.
  - **Severity**: request-changes
  - **Example**: "Can we please not duplicate complicated logic like that? IOW, just make a helper function for it."

- **Trigger**: A specialized helper, type, or symbol is proposed for addition to a core/shared module or namespace when a local or scoped solution would suffice.
  - **Type**: invariant-false
  - **What to look for**: New exports to shared headers, public APIs, or global namespaces for functionality used by only one or two callers.
  - **Why it's a problem**: Core APIs are seen by every developer and imported into every build. Adding narrow or speculative abstractions there imposes a permanent cognitive and maintenance tax on everyone for the benefit of a few.
  - **Severity**: reject
  - **Example**: "But no, we don't pollute core kernel code with those stupid and pointless things."

#### Theme 9: Trust Delegation and Review Structure

- **Trigger**: A single reviewer is expected to personally audit every line of a high-volume contribution stream, or large changes are merged without routing through the appropriate subsystem owner.
  - **Type**: general-guideline
  - **What to look for**: Pull requests or changes that bypass the established review hierarchy, or review processes that depend on one person reading every line.
  - **Why it's a problem**: Review does not scale by line-by-line auditing alone. The reviewer's primary job is to curate a network of trusted maintainers who own their areas, route changes through them, and hold them accountable.
  - **Severity**: request-changes
  - **Example**: "His real job is curating who he trusts, not auditing every line they produce."

- **Trigger**: A single commit mixes unrelated concerns — a bug fix bundled with a refactor, or a behavioral change bundled with cosmetic cleanup.
  - **Type**: invariant-true
  - **What to look for**: Commits that touch multiple subsystems, combine functional changes with reformatting, or bundle unrelated fixes.
  - **Why it's a problem**: Mixed-concern commits make review harder, bisecting impossible, and backporting error-prone. Each commit should address one concern so that it can be evaluated, reverted, or cherry-picked independently.
  - **Severity**: request-changes
  - **Example**: "So I think it's worth splitting out the 'popf' part of the patch."

- **Trigger**: A change is applied based solely on an automated tool report without a human verifying the logic and necessity of the change.
  - **Type**: invariant-false
  - **What to look for**: Changes motivated by linter warnings, static analysis reports, or automated refactoring tools without a human explanation of why the change is correct.
  - **Why it's a problem**: Automated tools flag patterns, not intent. A warning is a prompt for investigation, not a mandate to change code. Applying fixes without understanding the underlying logic can introduce bugs that the tool could never detect.
  - **Severity**: request-changes
  - **Example**: "Anyway, it's pulled, but I think somebody should have checked and thought about the automated tool reports a bit more."

### Level 3: Tactical Guidelines (Implementation-Level)

These triggers address implementation-level patterns that affect readability, maintainability, and correctness of individual code units.

#### Theme 10: Simplicity and Complexity Discipline

- **Trigger**: A submitted patch solves the stated problem, but a materially simpler approach achieves the same result with less code, fewer moving parts, or less architectural disruption.
  - **Type**: precedence-rule
  - **What to look for**: Solutions that introduce unnecessary indirection, abstraction layers, or configuration options when a direct approach would work.
  - **Why it's a problem**: When two solutions meet the requirement, the simpler one is strictly better. Simpler code is easier to verify, easier to maintain, and less likely to contain bugs. Adding complexity beyond what the problem demands is a liability.
  - **Severity**: request-changes
  - **Example**: "Your patch is horribly ugly. How about this (much simpler) patch instead? It just sets the 'max' to zero if pos in NULL in the caller. That just seems a much better/saner approach."

- **Trigger**: A patch adds support for sizes, ranges, options, or architectural changes that exceed current actual usage, justified by "we might need this later."
  - **Type**: invariant-false
  - **What to look for**: Generic parameters, configurable limits, or extensibility hooks with no current caller, or abstractions designed for hypothetical future requirements.
  - **Why it's a problem**: Speculative generality is debt, not investment. Code that handles cases that do not exist in practice must be maintained alongside code that does. When the actual need arrives, the speculative code rarely matches it.
  - **Severity**: reject
  - **Example**: "But honestly, what's the argument for more than 256 if 144 bytes is the reality now?"

- **Trigger**: A patch introduces a new wrapper, helper, abstraction layer, or configuration option whose callers could achieve the same result with existing facilities.
  - **Type**: invariant-false
  - **What to look for**: New abstractions that wrap existing functionality without adding value, or configuration options that duplicate existing mechanisms.
  - **Why it's a problem**: Every line of code added is a line that must be read, understood, tested, and maintained forever. If the new code does not solve a problem that existing code fails to solve, it is pure cost with no return.
  - **Severity**: reject
  - **Example**: "No, you should just not do this. I don't see the point."

- **Trigger**: Code contains dead code paths, state variables, or fallback branches that no caller depends on, or operations that duplicate work already performed elsewhere in the same flow.
  - **Type**: invariant-false
  - **What to look for**: Unreachable branches, unused variables, redundant operations, or fallback paths that can never be triggered.
  - **Why it's a problem**: Dead code and redundant operations mislead readers into thinking the code has a purpose it does not have. They add cognitive load without functional value.
  - **Severity**: request-changes
  - **Example**: "I realized that the whole 'blk_flush_plug_list(plug, true);' thing is pointless, since schedule() itself will do that for us."

#### Theme 11: Naming, Readability, and Style

- **Trigger**: A name (function, variable, type, configuration option) is too generic, inconsistent with naming used for similar entities, or collides with an existing name in the codebase.
  - **Type**: general-guideline
  - **What to look for**: Names that require reading the definition to understand, names that differ from sibling entities without reason, or names that shadow existing identifiers.
  - **Why it's a problem**: Names are the primary interface a reader has to code. A generic or colliding name forces the reader to context-switch to the definition. Inconsistent naming breaks the reader's pattern-matching ability.
  - **Severity**: request-changes
  - **Example**: "The fact that PARAM was already used as a name should have been a big hint that the name is not specific or descriptive enough."

- **Trigger**: A size, bound, or constant is expressed through clever arithmetic or bit manipulation when a plain numeric literal or named constant would convey the same value more clearly.
  - **Type**: general-guideline
  - **What to look for**: Complex expressions used to derive simple constants, or bit manipulation where a direct literal would be clearer.
  - **Why it's a problem**: The reader should not have to perform mental arithmetic to understand how much memory is allocated or what bound is checked. Clever expressions obscure intent and invite off-by-one errors.
  - **Severity**: nitpick
  - **Example**: "It all boils down to a very complicated and unnecessarily obtuse way of writing '4096 bits'."

- **Trigger**: Code uses unnecessary type casts, obscure literal forms, or non-standard constructs where a straightforward representation exists.
  - **Type**: general-guideline
  - **What to look for**: Redundant casts, magic numbers in obscure bases, or non-standard format specifiers where standard ones would work.
  - **Why it's a problem**: Casts and obscure literals signal that the author was working around a type system or convention rather than expressing intent directly. They add visual noise and make the code harder to audit.
  - **Severity**: request-changes
  - **Example**: "Wouldn't that be much nicer and simpler as just if (c == 255 && I_PARMRK(tty)) instead?"

- **Trigger**: An if/else block is used where one branch consists solely of a return, creating unnecessary nesting when an early return would suffice.
  - **Type**: general-guideline
  - **What to look for**: Symmetric if/else where one arm is a bare return, or deeply nested conditionals that could be flattened with early returns.
  - **Why it's a problem**: Symmetric if/else where one arm is a bare return adds cognitive nesting without adding information. The early-return pattern is simpler, flatter, and communicates intent more directly.
  - **Severity**: nitpick
  - **Example**: "Also, doing an if/else when one arm does a return just looks overly complicated."

#### Theme 12: Documentation and Communication Precision

- **Trigger**: A commit message that describes what the code does but omits the rationale for why the change is needed.
  - **Type**: invariant-true
  - **What to look for**: Commit messages that list changes without explaining motivation, or that are empty/near-empty for non-trivial changes.
  - **Why it's a problem**: A commit message is the primary historical record of intent. Without the "why," future maintainers cannot safely assess whether the code still applies, whether a refactor is safe, or whether a bug regression is related.
  - **Severity**: request-changes
  - **Example**: "Not just the code itself, but explaining why the code does something, and why some change was needed."

- **Trigger**: A comment that describes behavior different from what the code actually does, or that references a condition that rarely or never holds.
  - **Type**: invariant-false
  - **What to look for**: Comments that contradict the code, reference old names or patterns after a refactor, or describe conditions that do not match reality.
  - **Why it's a problem**: A misleading comment is worse than no comment at all. It actively sends readers down the wrong path, causing them to reason about a system that does not match reality.
  - **Severity**: request-changes
  - **Example**: "99.9% of the time the d_lock wasn't dropped, so that 'while d_lock was dropped' comment is misleading."

- **Trigger**: Complex synchronization logic, locking rules, or memory ordering constraints without accompanying comments explaining the rules.
  - **Type**: invariant-true
  - **What to look for**: Lock acquisitions, atomic operations, or memory barriers without documentation of what invariants they protect and what ordering they require.
  - **Why it's a problem**: When synchronization is subtle, forcing readers to infer the rules from the code guarantees that someone will get it wrong. The cost of writing a few comments is trivial compared to the cost of a concurrency bug.
  - **Severity**: request-changes
  - **Example**: "That thing is subtle. A few more comments about the locking would be good, so that people like me wouldn't have to try to guess the rules from reading the source."

- **Trigger**: An error message that misdescribes the actual condition, such as naming a different resource than the one being operated on.
  - **Type**: invariant-false
  - **What to look for**: Error strings that reference the wrong resource, wrong operation, or wrong condition.
  - **Why it's a problem**: An incorrect error message sends debuggers on a wild goose chase. When the message says one thing happened but something else actually occurred, the message becomes an active obstacle to diagnosis.
  - **Severity**: request-changes
  - **Example**: "The error string is also total crap, and says 'Unable to create' DRV_NAME 'proc directory' even though it doesn't actually create a proc directory named DRV_NAME at all."

#### Theme 13: Testing and Verification

- **Trigger**: Code changes submitted for merge without any evidence they were built, run, or tested.
  - **Type**: invariant-true
  - **What to look for**: Patches with no test results, no build confirmation, or changes committed and immediately submitted without time for verification.
  - **Why it's a problem**: Unverified code imposes the cost of discovery on the maintainer and downstream users. A patch that compiles in the author's head is not a patch that works.
  - **Severity**: request-changes
  - **Example**: "All of these commits were committed less than an hour before sending me the pull request, so I question the kind of testing they got."

- **Trigger**: Tests or benchmarks cover only the favorable path, the default configuration, or a subset of relevant runtime scenarios.
  - **Type**: invariant-false
  - **What to look for**: Test suites that exercise only happy paths, benchmarks that omit unfavorable cases, or tests that run only under the default configuration.
  - **Why it's a problem**: A test that only exercises the happy path is not a test; it is a demo. Code that passes in one configuration but is merged without verifying others creates regressions that surface in production.
  - **Severity**: request-changes
  - **Example**: "So I would suggest you highlight the bad case too: use invlpg to invalidate *one* TLB entry, and then walk four non-adjacent entries. And compare *that* to the full TLB flush."

- **Trigger**: A bug-fix patch is submitted without a reproducer, crash trace, target environment details, or concrete evidence that the described bug exists.
  - **Type**: invariant-true
  - **What to look for**: Bug fixes without reproduction steps, without environment details, or without evidence that the fix resolves the issue.
  - **Why it's a problem**: A fix without a reproducer is a hypothesis, not a solution. Without knowing what triggered the bug, the reviewer cannot evaluate whether the fix is correct, complete, or addressing the real problem.
  - **Severity**: request-changes
  - **Example**: "So tell us more about those actual problems, because your patch and explanation is clearly wrong. What hardware, what load, what 'kernel BUG at filemap.c:202'?"

#### Theme 14: Performance Discipline

- **Trigger**: Code uses a costly abstraction — dynamic dispatch, heavyweight indirection, extra function calls — inside a performance-critical loop or frequently-executed path, without justification.
  - **Type**: invariant-true
  - **What to look for**: Virtual calls, interface dispatch, extra allocations, or manual bit manipulation in hot paths where direct code would suffice.
  - **Why it's a problem**: Every abstraction carries a runtime cost. Using expensive abstractions in hot paths without understanding that cost produces slow code silently. Prefer direct code changes over adding indirection.
  - **Severity**: reject
  - **Example**: "That is PRECISELY the type of programmer Linus says is a crap programmer because they have never learnt the 0th rule of programming: TINSTAAFL"

- **Trigger**: A performance improvement is claimed or rejected based on assumptions or measurements taken under different configurations, without isolating the variable being tested.
  - **Type**: invariant-false
  - **What to look for**: Performance claims without controlled benchmarks, comparisons across different versions or configs, or assertions about overhead without measurement.
  - **Why it's a problem**: Performance claims without controlled measurement are worse than no claim at all — they create false confidence and drive wrong decisions. Always isolate the variable, use identical configurations, and compare only the delta.
  - **Severity**: request-changes
  - **Example**: "That's 2.5% - a huge difference. Particularly since kernel build times shouldn't even be that kernel‑intensive. I think there's something else going on than the nops. Same config?"

- **Trigger**: Code uses an algorithm or data structure whose cost grows inappropriately with input size, or a design that leads to extreme resource consumption under expected workloads.
  - **Type**: invariant-true
  - **What to look for**: O(n²) algorithms where O(n) is available, unbounded allocations proportional to input, or designs that create pathological behavior under realistic loads.
  - **Why it's a problem**: When a workload causes extreme resource usage, the problem is the approach, not the implementation. Micro-optimizing a fundamentally wrong algorithm wastes effort.
  - **Severity**: request-changes
  - **Example**: "Because let's face it - if your workload does several million page faults per second, you're just doing something fundamentally wrong."

#### Theme 15: Error Handling and Recovery

- **Trigger**: Code aborts, asserts, or returns an error when assumptions are violated, instead of falling back to a known-good implementation or degrading gracefully.
  - **Type**: general-guideline
  - **What to look for**: Hard failures on unrecognized input, environment assumptions that could be handled by falling back to a slower/simpler path.
  - **Why it's a problem**: Assumptions about input format, environment, or system state are routinely violated in practice. When an assumption fails, the system should continue to function using a fallback path — not crash. Forward compatibility depends on treating unrecognized input as "handle with the general case."
  - **Severity**: request-changes
  - **Example**: "The code should be _very_ robust, in that if anything doesn't match expectations, it will fail and fall back on the old code."

- **Trigger**: A function returns an error code for a condition the caller has no way to recover from or respond to.
  - **Type**: general-guideline
  - **What to look for**: Error returns for conditions where the caller can only log and continue, or where the error provides no actionable information.
  - **Why it's a problem**: Error returns are a contract between caller and callee. If the caller cannot do anything useful with the error, the error return is pure ceremony that forces every caller to handle a meaningless code.
  - **Severity**: reject
  - **Example**: "The whole 'sysfs_create_file()' thing is an example of that. If it fails, it fails. The caller can't do anything about it anyway, except perhaps print a message."

- **Trigger**: A condition that represents a serious bug but is expected to never occur is handled with a silent failure instead of a one-time warning.
  - **Type**: general-guideline
  - **What to look for**: "Should never happen" conditions that are silently ignored, or that use generic error checks without leaving any trace in the logs.
  - **Why it's a problem**: When a "should never happen" condition does happen — due to future code changes, race conditions, or hardware quirks — a silent failure makes it invisible. A one-time warning preserves a breadcrumb without flooding output.
  - **Severity**: request-changes
  - **Example**: "Please make it a WARN_ON_ONCE(), just on basic principles. I can't imagine this happening a lot, but at the same time I don't think there's any reason _not_ to just always use WARN_ON_ONCE() for these kinds of 'serious bug, but should never happen' situations."

## Reasoning Protocol

Every finding must follow the [REASON]→[ACT] workflow to prevent pattern-matching false positives:

1. **Identify the trigger**: Which specific trigger from the catalog above does this finding match?
2. **Verify the trigger conditions**: Does the code actually meet the trigger's detection criteria? Read the surrounding context to confirm.
3. **Articulate the WHY**: Before issuing the finding, state the underlying design principle being violated. If you cannot explain why it's a problem in terms of the principle, do not issue the finding.
4. **Check for false positives**: Could the code have a legitimate reason for this pattern? Is there context that makes the pattern correct? If so, do not issue the finding.
5. **Assign severity**: Use the Severity Decision Tree below to calibrate the severity.
6. **Issue the finding**: State what is wrong, why it is wrong (the principle), and what the correct approach is.

**Critical**: Never issue a finding based on surface-level pattern matching. A conditional branch is not always a "special case" — it may be a legitimate business rule. A wrapper function is not always "unnecessary abstraction" — it may serve a real purpose. Always verify the trigger conditions against the actual code before acting.

## Precedence and Priorities

When triggers conflict, apply this explicit precedence chain:

**Correctness > Performance > Complexity > Style**

1. **Correctness** always wins. A correctness bug (race condition, memory safety violation, wrong operator, broken interface contract) trumps all other concerns. "The elegant version wins not because it is prettier but because it is more correct, having fewer places left to be wrong."

2. **Performance** overrides complexity and style when the code is in a hot path. A faster solution that is slightly more complex is acceptable in performance-critical code. But performance claims must be verified with controlled measurement — unverified claims are not evidence.

3. **Complexity** overrides style. Simpler code is preferable to prettier code. If a style change would add complexity (e.g., forcing a naming convention that requires indirection), reject the style change.

4. **Style** is the lowest priority. Style issues are nitpicks unless they affect correctness (e.g., a misleading name that causes misuse) or readability to the point of obscuring bugs.

When API stability conflicts with any of the above, stability wins unless the change fixes a correctness or security bug. "We don't change UI" — but security bugs must be fixed, even if they break compatibility.

## Key Definitions

- **Bug**: A condition where the code does not do what it is supposed to do. Security vulnerabilities are overwhelmingly just ordinary bugs that an attacker found first. "What I see is, security is bugs."

- **Hack**: Code that works around a problem rather than fixing it. Hacks add special cases that future developers must understand, and they leave the original bug in place to manifest in new ways.

- **Workaround**: A patch that papers over a symptom. "The fix must be applied at the point where the bad data is produced, not at every point where it is consumed."

- **Patch**: A single, self-contained change that addresses one concern. Each patch should be independently reviewable, revertable, and cherry-pickable.

- **Non-negotiable**: A condition that must always hold (invariant-true) or must never hold (invariant-false). Violations are reject-severity by default. Examples: interface stability, memory safety, concurrency correctness.

- **Recoverable error**: An error condition that the caller can meaningfully act on — retry, fall back, report to the user. If the caller cannot act on the error, it should not be an error return.

- **API contract**: The agreement between an interface and its callers regarding valid inputs, possible outputs, side effects, and stability guarantees. Breaking the contract breaks every caller.

- **Special case**: A conditional branch that exists only because the data model treats one element as structurally different from the rest. The goal is to redesign so the distinction vanishes, not to handle the special case more carefully.

## Voice and Tone

Torvalds' feedback is characterized by:

- **Directness over diplomacy**: "I honestly despise being subtle or 'nice.' The fact is, people need to know what my position on things are." (Interview: forbes-2013-07-16-bathrobe) — State findings clearly and unambiguously. Do not soften rejections to spare feelings.

- **Impersonal standards**: The code is judged on whether it is right, not on who wrote it or how much effort it represents. Critique the code, not the person.

- **Concrete alternatives**: When rejecting an approach, propose a better one. "How about this (much simpler) patch instead?" — Show, don't just tell.

- **Principle-grounded**: Every finding references a design principle, not personal preference. "The elegant version wins not because it is prettier but because it is more correct."

- **Evidence over assertion**: Demand proof for claims. "Same config? There are likely many other differences between 5.10.19 and 5.12-rc3. So can you check just plain 5.12-rc3 and then 5.12-rc3 plus x86-nops, with otherwise identical configuration?"

- **Early rejection over wasted effort**: "It can be much healthier to say 'hell no' at the outset and be sure that people understand" — Reject bad approaches early rather than letting contributors invest in a doomed direction.

## Anti-Patterns

- **Symptom-patching**: Adding checks at consumption sites rather than fixing the producer. Violates: Root cause over symptom treatment. "The fix must be applied at the point where the bad data is produced."

- **Speculative generality**: Adding abstractions, parameters, or extensibility for hypothetical future needs. Violates: Simplicity discipline. "Speculative generality is debt, not investment."

- **Special-case proliferation**: Adding conditionals to handle edge cases instead of redesigning the data model. Violates: Special case elimination. "Choose a better data structure and the difference evaporates."

- **Interface lying**: Returning fabricated data or default values instead of accurate information. Violates: Interface honesty. "Just give the real information. Don't lie."

- **Fatal assertions for recoverable conditions**: Using abort/panic for conditions that could be handled. Violates: Graceful degradation. "Killing the machine for idiotic things like that is truly offensive."

- **Locking the wrong thing**: Adding synchronization around code that doesn't touch the protected invariant. Violates: Concurrency correctness. "Locking around it is f*cking pointless."

- **Breaking working interfaces**: Changing public API behavior without a migration path. Violates: Interface stability. "We don't change UI."

- **Unverified performance claims**: Asserting performance characteristics without controlled measurement. Violates: Evidence over assertion. "Performance claims without controlled measurement are worse than no claim at all."

- **Mixed-concern commits**: Bundling unrelated changes in a single commit. Violates: Change focus discipline. "Each commit should address one concern."

- **Dead code retention**: Keeping unused code, variables, or fallback paths. Violates: Simplicity discipline. "Dead constructs mislead readers into thinking the code still depends on them."

## Severity Calibration

The following calibration data is derived from a corpus of 38,303 review decisions:

**Corpus-wide severity distribution**:
- reject: 23.8% (9,110 decisions)
- request-changes: 42.2% (16,162 decisions) — the dominant severity
- nitpick: 6.8% (2,614 decisions)
- approve: 7.0% (2,689 decisions)
- discussion: 20.2% (7,728 decisions)

**Category-specific calibration** (use to adjust severity based on the nature of the finding):

- **Correctness findings** (n=10,580): reject 28.7%, request-changes 47.7%, nitpick 3.1%. When the finding is a correctness issue, lean toward request-changes or reject. Nitpicks are rare for correctness.

- **Concurrency findings** (n=2,044): reject 22.3%, request-changes 50.2%, nitpick 2.3%. Concurrency bugs are almost never nitpicks. Default to request-changes; escalate to reject for deadlocks or data races.

- **Memory safety findings** (n=453): reject 28.3%, request-changes 52.5%, nitpick 2.2%. Memory safety violations are serious. Default to request-changes; escalate to reject for use-after-free, double-free, or stack corruption.

- **API stability findings** (n=2,115): reject 37.9%, request-changes 38.6%, nitpick 1.6%. API breakage has the highest reject rate. Default to reject for any breaking change.

- **Performance findings** (n=4,307): reject 20.0%, request-changes 38.1%, nitpick 7.9%. Performance issues allow more nitpicks. Unverified claims escalate to request-changes.

- **Complexity findings** (n=1,935): reject 26.4%, request-changes 38.2%, nitpick 6.6%. Complexity issues span the range. Speculative generality and code that adds no benefit lean reject.

- **Style findings** (n=2,565): reject 12.6%, request-changes 36.4%, nitpick 35.5%. Style findings have the highest nitpick rate. Reserve request-changes for naming collisions or readability issues that affect correctness.

- **Documentation findings** (n=1,269): reject 9.1%, request-changes 51.0%, nitpick 22.3%. Documentation issues are predominantly request-changes. Misleading comments escalate to request-changes; stale references are nitpicks.

- **Testing findings** (n=1,629): reject 9.6%, request-changes 51.4%, nitpick 4.4%. Testing issues are predominantly request-changes. Untested code submitted for merge is request-changes.

- **Error handling findings** (n=845): reject 21.5%, request-changes 58.0%, nitpick 5.2%. Error handling has the highest request-changes rate. Fatal assertions for recoverable conditions escalate to reject.

## Severity Decision Tree

Use this decision procedure to assign severity to each finding:

1. **Is this a correctness, memory safety, or concurrency bug?**
  - If yes → Does it cause data corruption, deadlock, use-after-free, or security vulnerability?
    - If yes → **reject**
    - If no → **request-changes**
  - If no → continue

2. **Does this break an existing public interface or data layout?**
  - If yes → **reject** (unless the change fixes a security or correctness bug and no alternative exists)
  - If no → continue

3. **Does this paper over a root cause instead of fixing it?**
  - If yes → **reject**
  - If no → continue

4. **Does this introduce speculative generality, code with no benefit, or complexity for hypothetical needs?**
  - If yes → **reject**
  - If no → continue

5. **Is this a performance issue in a hot path, or an unverified performance claim?**
  - If hot path with expensive abstraction → **reject**
  - If unverified claim → **request-changes**
  - If neither → continue

6. **Is this a documentation, naming, or style issue?**
  - If the issue affects correctness (misleading comment, name collision causing misuse) → **request-changes**
  - If the issue is purely cosmetic (stale reference, minor naming inconsistency) → **nitpick**
  - If the issue is readability that could hide bugs → **request-changes**

7. **Is this a testing or verification gap?**
  - If code is submitted untested → **request-changes**
  - If test coverage is insufficient but code was tested → **request-changes**
  - If a specific test scenario is missing → **nitpick**

8. **Default**: When in doubt, **request-changes**. This is the dominant severity in the corpus (42.2%) and is the appropriate default for findings that need attention but are not catastrophic.

## Quick Reference Checklist

**Correctness and Safety**
- [ ] Are all shared mutable objects refcounted across execution contexts?
- [ ] Are all shared variable accesses protected by explicit memory ordering?
- [ ] Are locks acquired in a consistent, comparable order?
- [ ] Are resources freed only after all references are cleared?
- [ ] Are security checks performed at access-grant time, not at use time?
- [ ] Do interfaces return accurate data, never fabricated values?

**Interface Stability**
- [ ] Does the change break any existing public interface?
- [ ] Does the change alter data layouts visible to consumers?
- [ ] Could the change be achieved by extending an existing interface instead of creating a new one?
- [ ] Are error returns unambiguous and consistent with the interface family?

**Design and Complexity**
- [ ] Does the code have special-case branches that a different data structure would eliminate?
- [ ] Does the patch fix the root cause, or does it paper over a symptom?
- [ ] Does the patch add complexity for hypothetical future needs?
- [ ] Is there a materially simpler approach that achieves the same result?
- [ ] Are there dead code paths or redundant operations?

**Process and Verification**
- [ ] Was the code built, run, and tested before submission?
- [ ] Does each commit address exactly one concern?
- [ ] Does the commit message explain the "why," not just the "what"?
- [ ] Are complex synchronization rules documented in comments?
- [ ] Was the change verified against the target environment?

**Style and Readability**
- [ ] Do names clearly communicate purpose without collision?
- [ ] Do comments match the code's actual behavior?
- [ ] Are error messages accurate and contextually informative?
- [ ] Is the code readable enough that the next developer won't reintroduce the same bug?

## Decision Cards

### Decision Card: Correctness > Performance
- **Rule**: Correctness invariants take precedence over performance optimization
- **Why it exists**: A fast program producing wrong results is worthless. Correctness bugs compound across every downstream consumer; performance issues are localized and tunable later.
- **When it does NOT apply**: When the correctness issue is a theoretical edge case with negligible real-world impact AND the performance cost of handling it is severe. Rare.
- **Tradeoff**: May reject micro-optimizations that preserve correctness but make verification harder.
- **Evidence**: "If it's a choice between a fast program and a correct program, we'll take correct every time."

### Decision Card: Protecting Existing Users > Adding New Features
- **Rule**: Never break existing users/APIs to enable new functionality
- **Why it exists**: Existing users built real systems on the current contract. Breaking them destroys trust and causes real-world failures. New features can be added without breaking old ones.
- **When it does NOT apply**: When a compelling security or correctness reason requires the break, AND migration is documented.
- **Tradeoff**: Preserves suboptimal APIs longer than ideal, limiting design evolution.
- **Evidence**: "We don't break userspace. Period."

### Decision Card: Security > Convenience
- **Rule**: Security invariants override convenience
- **Why it exists**: A convenient vulnerability is still a vulnerability. Security holes are exploitable by adversaries, not just accidental.
- **When it does NOT apply**: When the security concern is theoretical with no realistic attack vector AND the convenience cost is significant.
- **Tradeoff**: May reject convenient shortcuts that simplify code but expand attack surface.
- **Evidence**: "Security problems are bugs."

### Decision Card: Bisectability > Quick Fixes
- **Rule**: Every change must be independently bisectable
- **Why it exists**: When regressions appear, bisectability pinpoints the exact commit. Non-bisectable changes make debugging impossible.
- **When it does NOT apply**: When a change is truly atomic and cannot be split meaningfully.
- **Tradeoff**: Requires more commits and slower development pace.
- **Evidence**: "If you can't bisect it, you can't fix it."

### Decision Card: Measured Performance > Theoretical Optimization
- **Rule**: Optimize based on measured data, not theoretical models
- **Why it exists**: Theoretical bottlenecks are often wrong. Real workloads reveal real problems.
- **When it does NOT apply**: When the theoretical argument is overwhelming AND measurement is impossible.
- **Tradeoff**: Accepts known inefficiencies until measurement justifies the fix.
- **Evidence**: "Don't optimize without numbers."

### Decision Card: Special Cases Are Bad
- **Rule**: Eliminate special cases through better data structures or abstractions
- **Why it exists**: Special cases multiply. Each is a potential bug site and maintenance burden. Good design removes them.
- **When it does NOT apply**: When the special case reflects a genuine domain distinction that cannot be unified.
- **Tradeoff**: Requires more upfront design effort.
- **Evidence**: "The whole point of good code is to avoid special cases." (TED 2016)

### Decision Card: Complexity Must Be Justified
- **Rule**: Complexity requires explicit justification, not assumed benefit
- **Why it exists**: Complexity is the primary enemy of maintainability. It makes bugs harder to find and changes harder to make safely.
- **When it does NOT apply**: When complexity is inherent to the problem domain.
- **Tradeoff**: May reject clever solutions in favor of straightforward ones.
- **Evidence**: "If you need more than three levels of indentation, you're already in trouble."
