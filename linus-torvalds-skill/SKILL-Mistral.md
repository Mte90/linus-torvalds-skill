```yaml
---
name: linus-torvalds-skill
description: "A language- and project-agnostic code review skill distilled from 38,000+ Linus Torvalds review moves and 500+ interview passages. It teaches reviewers how to apply Torvalds' method: prioritize correctness, design for maintainability, and reject anything that risks breaking users."
metadata:
  author: "torvalds-skill pipeline"
  version: "1.0.0"
  tags:
    - code-review
    - reviewer-method
    - torvalds
---
```

# Linus Torvalds Review Method

> This skill distills the reviewing patterns of Linus Torvalds from 38,000+ real code-review moves and 500+ interview passages. The method is language- and project-agnostic: it focuses on design invariants, maintainability, and protecting users. It is grounded in Torvalds’ own words and calibrated to his actual severity rates across 350 representative patterns.

---

## Reviewer Mindset

Torvalds’ code reviews are driven by five core attitudes. Each attitude is grounded in his own words and explains why it matters.

- **Correctness is the only thing that matters**
  - *Why it matters:* If the code doesn’t work, nothing else matters. Torvalds treats correctness as a non-negotiable invariant.
  - *Quote:* “code either works or it doesn’t” (Interview: cnn-transcript-2000)

- **Protect existing users at all costs**
  - *Why it matters:* Breaking userspace or APIs causes real harm. Torvalds rejects any change that risks regressions.
  - *Quote:* “I like boring... boring to me is no super exciting new features that will break machines for millions of people around the world.” (Interview: business-insider-2014-qa)

- **Design for maintainability, not cleverness**
  - *Why it matters:* Clever code is hard to maintain. Torvalds prefers simple, elegant designs that eliminate special cases.
  - *Quote:* “Choose a better data structure – a pointer to a pointer instead of a pointer – and the difference evaporates.” (Interview: blakecrosley-philosophy)

- **Never trust external systems or firmware**
  - *Why it matters:* External systems (ACPI, firmware, user input) are unreliable. Torvalds insists on validating everything locally.
  - *Quote:* “Yes. I think trusting ACPI is _always_ a mistake. It's insane. We should never ask the firmware for any data that we can just figure out ourselves.” (Category: abstraction, Move 8)

- **Be brutally honest in reviews**
  - *Why it matters:* Vague feedback wastes time. Torvalds’ bluntness ensures reviewers and authors understand the stakes immediately.
  - *Quote:* “I honestly despise being subtle or 'nice.' The fact is, people need to know what my position on things are.” (Interview: forbes-2013-07-16-bathrobe)

---

## Review Triggers

Review triggers are grouped into three tiers that mirror how a human expert reviews: fatal flaws first, then design issues, then nitpicks. Each trigger is language- and project-agnostic and labeled with its type.

### Level 1: Global Invariants (non-negotiables)

- **Trigger**: Fatal assertion/panic used for a recoverable condition
  - **Type**: invariant-false
  - **What to look for**: panic/crash in code paths that should handle errors gracefully
  - **Why it's a problem**: Recoverable errors must be handled without crashing
  - **Severity**: reject
  - **Example**: “This is fundamentally broken. You don't fatal assertion() a condition that can happen from bad user input.” (Category: error-handling, Move 13)

- **Trigger**: Breaking documented behavior or public interfaces without a migration path
  - **Type**: invariant-false
  - **What to look for**: Changes that break existing documented behavior or public APIs
  - **Why it's a problem**: Users depend on stable interfaces; breaking them causes regressions
  - **Severity**: request-changes
  - **Example**: “In other words, a kernel interface to user land changed. THAT IS ALWAYS A BUG. We don't change UI.” (Category: api-stability, Move 17)

- **Trigger**: Unsafe or untrusted boundary crossing without validation
  - **Type**: invariant-false
  - **What to look for**: External input or boundary crossing (e.g., user, network, device) without validation
  - **Why it's a problem**: Untrusted input can cause crashes or security issues
  - **Severity**: reject
  - **Example**: “The whole "sysfs_create_file()" thing is an example of that. If it fails, it fails. The caller can't do anythign about it anyway...” (Category: error-handling, Move 8)

- **Trigger**: Returning magic error codes instead of typed errors
  - **Type**: invariant-false
  - **What to look for**: Functions returning bare integers (e.g., -1, 0, NULL) instead of typed errors or success indicators
  - **Why it's a problem**: Magic codes are ambiguous and hard to maintain
  - **Severity**: reject
  - **Example**: “Returning zero from a write is basically insanity. It's not a valid error case.” (Category: error-handling, Move 25)

- **Trigger**: Silent swallowing of serious errors
  - **Type**: invariant-false
  - **What to look for**: Catching or ignoring serious errors without logging or propagating them
  - **Why it's a problem**: Silent failures hide bugs and make debugging impossible
  - **Severity**: reject
  - **Example**: “I'm getting *real* tired of that fatal assertion() shit... Killing the machine for idiotic things like that is truly offensive... Either that fatal assertion() cannot possibly happen, in which case it should damn well not exist in the first place.” (Category: error-handling, Move 13)

---

### Level 2: Structural Patterns (architecture-level)

#### Theme: Data Structure and Abstraction

- **Trigger**: Special-case handling for rare or edge cases
  - **Type**: general-guideline
  - **What to look for**: Code with if/else branches that exist only to handle “the first one” or “the empty case”
  - **Why it's a problem**: Special cases clutter code and mask design flaws; they should be eliminated by choosing the right data structure
  - **Severity**: request-changes
  - **Example**: “Choose a better data structure – a pointer to a pointer instead of a pointer – and the difference evaporates.” (Category: abstraction, Move 1)

- **Trigger**: Duplicating logic instead of factoring it into a helper
  - **Type**: general-guideline
  - **What to look for**: Copied code blocks that perform the same logic in multiple places
  - **Why it's a problem**: Duplication increases maintenance burden and risk of divergence
  - **Severity**: request-changes
  - **Example**: “Can we please not duplicate complicated logic like that? IOW, just make a helper function for it.” (Category: abstraction, Move 11)

- **Trigger**: Exposing internal structures as public interfaces
  - **Type**: general-guideline
  - **What to look for**: Public APIs that expose internal data structures or implementation details
  - **Why it's a problem**: Exposing internals locks the design into place and makes refactoring impossible
  - **Severity**: request-changes
  - **Example**: “What this does is get rid of the horrible notion of having that struct inode *ptmx_inode* be the interface between the pty code and devpts.” (Category: abstraction, Move 3)

- **Trigger**: Premature abstraction or helper functions without clear benefit
  - **Type**: general-guideline
  - **What to look for**: Adding helper functions or macros that provide no clear benefit over inlining
  - **Why it's a problem**: Abstractions add complexity and indirection without solving a real problem
  - **Severity**: request-changes
  - **Example**: “I'd much rather just add a single compile-time conditional cmpxchg64_relaxed ... to the LOCKREF code, and then ARM (and others) can define it as they wish.” (Category: abstraction, Move 9)

- **Trigger**: Hard-coded magic constants or hardware-specific hacks
  - **Type**: general-guideline
  - **What to look for**: Literal constants (e.g., 12GB, 0x1234) or hardware-specific hacks used as workarounds
  - **Why it's a problem**: Magic constants make code fragile and unportable; hacks mask the root cause
  - **Severity**: request-changes
  - **Example**: “the whole "fixed address at around 12GB physical" really is such a horrible hack” (Category: abstraction, Move 10)

#### Theme: API Design and Contracts

- **Trigger**: Changing a public interface's behavior without updating all callers
  - **Type**: invariant-false
  - **What to look for**: Modifying a function’s return value, arguments, or semantics without ensuring all callers are updated
  - **Why it's a problem**: Callers depend on the documented contract; breaking it causes regressions
  - **Severity**: request-changes
  - **Example**: “if you're changing next_thread() anyway, please just change it to be a completely new thing that returns NULL at the end, which is what everybody really seems to want, and don't add a new __next_thread() helper.” (Category: api-stability, Move 20)

- **Trigger**: Adding new global symbols or public interfaces without clear justification
  - **Type**: general-guideline
  - **What to look for**: New public functions, macros, or global variables introduced without a compelling reason
  - **Why it's a problem**: Global symbols pollute the namespace and increase maintenance burden
  - **Severity**: request-changes
  - **Example**: “I'd much rather just add a single compile-time conditional cmpxchg64_relaxed ... to the LOCKREF code” (Category: abstraction, Move 9)

- **Trigger**: Special-casing a single API function instead of generalizing
  - **Type**: general-guideline
  - **What to look for**: Adding a flag or parameter to one function (e.g., mkdir) while leaving similar functions unchanged
  - **Why it's a problem**: Inconsistent interfaces make code harder to use and maintain
  - **Severity**: request-changes
  - **Example**: “Why the *hell* would mkdir() be so magical as to need something like that? ... What makes mkdir() so magical? Also, what about all the other ops?” (Category: api-stability, Move 24)

- **Trigger**: Breaking ABI compatibility by changing data layout or alignment
  - **Type**: invariant-false
  - **What to look for**: Changes to struct layouts, padding, or alignment that break binary compatibility
  - **Why it's a problem**: Users depend on stable ABIs; breaking them causes regressions
  - **Severity**: request-changes
  - **Example**: “Adding a new u64 field to siginfo breaks the ABI because of alignment differences on 32‑bit targets” (Category: api-stability, Move 21)

#### Theme: Concurrency and Synchronization

- **Trigger**: Unsynchronized access to shared mutable data
  - **Type**: invariant-false
  - **What to look for**: Concurrent reads/writes to shared data without locks, atomics, or memory barriers
  - **Why it's a problem**: Race conditions can corrupt data or cause crashes
  - **Severity**: reject
  - **Example**: “The reason it is buggy has absolutely nothing to do with whether the read is done or not, it has to do with the fact that the CPU may re-order the reads regardless of whether the read is done in some specific order by the compiler or not! ... The above kind of code needs memory barriers to be non-buggy.” (Category: concurrency, Move 1)

- **Trigger**: Recursive lock acquisition or lock upgrade
  - **Type**: invariant-false
  - **What to look for**: Acquiring the same lock twice or attempting to upgrade a read lock to a write lock
  - **Why it's a problem**: Recursive locks and lock upgrades can deadlock
  - **Severity**: reject
  - **Example**: “What kind of _crap_ is this cpufreq thing?... What a piece of crap. Why, why, why?” (Category: concurrency, Move 3)

- **Trigger**: Locking outside the critical section or releasing resources while holding a lock
  - **Type**: invariant-false
  - **What to look for**: Locking primitives that are not held for the entire critical section or that release resources while the lock is still held
  - **Why it's a problem**: Releasing resources while holding a lock can cause deadlocks or resource leaks
  - **Severity**: reject
  - **Example**: “You still have "goto err" for cases that have the ctx locked. Which means that the thing gets free'd while still locked, which causes problems for lockdep etc, so don't do it.” (Category: concurrency, Move 15)

- **Trigger**: Holding a lock while invoking code that may block or schedule work needing the same lock
  - **Type**: invariant-false
  - **What to look for**: Locks held across calls that may block or schedule work that needs the same lock
  - **Why it's a problem**: Can deadlock if the scheduled work tries to acquire the same lock
  - **Severity**: request-changes
  - **Example**: “Now that's fine - as long as we never take that lock inside any delayed work - because then the delayed work itself may need the lock we hold in order to complete, and now the 'cancel_delayed_work_sync()' thing might deadlock.” (Category: concurrency, Move 16)

#### Theme: Memory Safety

- **Trigger**: Manual memory allocation/deallocation without clear ownership
  - **Type**: invariant-false
  - **What to look for**: Manual manual allocation/manual deallocation or vmalloc/vfree without clear ownership or lifetime tracking
  - **Why it's a problem**: Manual memory management is error-prone and hard to maintain
  - **Severity**: reject
  - **Example**: “Ugh, that XFS code is _broken_. Instead of keeping track of how it got the memory, it totally forgets where the memory came from, and then it later asks "oh, btw, how the hell did I allocate this?".” (Category: memory-safety, Move 10)

- **Trigger**: Accessing freed or invalid memory
  - **Type**: invariant-false
  - **What to look for**: Code that dereferences pointers after freeing them or uses dangling pointers
  - **Why it's a problem**: Can cause crashes or memory corruption
  - **Severity**: reject
  - **Example**: “That's unacceptably buggy crap. rpc_wait_for_completion_task() will happily exit on a deadly signal even if the rpc hasn't been completed, so now you'll have a stale pointer to a stack that has been freed.” (Category: memory-safety, Move 17)

- **Trigger**: Large stack allocations or unsafe stack usage
  - **Type**: invariant-false
  - **What to look for**: Stack allocations larger than a few hundred bytes or unsafe stack usage (e.g., returning pointers to stack locals)
  - **Why it's a problem**: Can overflow the stack and cause crashes
  - **Severity**: reject
  - **Example**: “Because a 1kB stack frame is horrendous ... And no, ... is not an excuse for one single level to use up 1kB, much less 2kB.” (Category: memory-safety, Move 13)

- **Trigger**: Not using reference counting for shared objects
  - **Type**: invariant-false
  - **What to look for**: Shared objects accessed from multiple threads without refcounting
  - **Why it's a problem**: Can cause use-after-free or double-free
  - **Severity**: request-changes
  - **Example**: “Side note: this is pretty much true of any kernel data structure. If you have a kernel data structure that isn't just used within one thread, it must be refcounted.” (Category: memory-safety, Move 5)

#### Theme: Error Handling and Robustness

- **Trigger**: Not validating boundary-crossing returns before use
  - **Type**: invariant-false
  - **What to look for**: Ignoring error returns from functions that cross untrusted boundaries (e.g., user, network, device)
  - **Why it's a problem**: Can cause crashes or security issues
  - **Severity**: reject
  - **Example**: “EINVAL seems the simplest thing. Should check S_IMMUTABLE too for that matter.” (Category: error-handling, Move 2)

- **Trigger**: Using fatal assertions for recoverable conditions
  - **Type**: invariant-false
  - **What to look for**: fatal assertion() or similar fatal assertions in production code for conditions that can happen in normal operation
  - **Why it's a problem**: Crashes the system for recoverable errors
  - **Severity**: request-changes
  - **Example**: “I'm getting *real* tired of that fatal assertion() shit... Killing the machine for idiotic things like that is truly offensive... Either that fatal assertion() cannot possibly happen, in which case it should damn well not exist in the first place.” (Category: error-handling, Move 13)

- **Trigger**: Inconsistent error code conventions within the same module
  - **Type**: general-guideline
  - **What to look for**: Some functions return -1 on error, others return NULL, others throw exceptions
  - **Why it's a problem**: Inconsistent conventions make code hard to use and maintain
  - **Severity**: request-changes
  - **Example**: “The calling convention of sb_set_blocksize() is wrong, and instead of returning "size for success or zero for failure", it should return "error code for failure or zero for success". There's just no point to returning the same size we just passed in.” (Category: api-stability, Move 6)

- **Trigger**: Swallowing errors that should be propagated
  - **Type**: invariant-false
  - **What to look for**: Catching errors and not logging or propagating them
  - **Why it's a problem**: Hides bugs and makes debugging impossible
  - **Severity**: request-changes
  - **Example**: “The whole "sysfs_create_file()" thing is an example of that. If it fails, it fails. The caller can't do anythign about it anyway...” (Category: error-handling, Move 8)

---

### Level 3: Tactical Guidelines (implementation-level)

#### Theme: Naming and Clarity

- **Trigger**: Obscure or non-descriptive naming
  - **Type**: general-guideline
  - **What to look for**: Names like PARAM, x, or random acronyms that don’t describe the entity
  - **Why it's a problem**: Obscure names make code hard to read and maintain
  - **Severity**: nitpick
  - **Example**: “The fact that PARAM was already used as a name should have been a big hint that the name is not specific or descriptive enough.” (Category: style, Move 24)

- **Trigger**: Inconsistent naming conventions
  - **Type**: general-guideline
  - **What to look for**: Inconsistent naming (e.g., camelCase vs snake_case, mixed prefixes)
  - **Why it's a problem**: Inconsistent conventions reduce readability
  - **Severity**: nitpick
  - **Example**: “It seems silly to have the 'r' for the r8‑r15 case, but not the legacy registers.” (Category: style, Move 7)

- **Trigger**: Using magic numbers or obscure character literals
  - **Type**: general-guideline
  - **What to look for**: Literal constants (e.g., 0377, '\377') instead of named constants
  - **Why it's a problem**: Magic numbers make code hard to understand and maintain
  - **Severity**: request-changes
  - **Example**: “Wouldn't that be much nicer and simpler as just if (c == 255 && I_PARMRK(tty)) instead?” (Category: style, Move 8)

#### Theme: Comments and Documentation

- **Trigger**: Inaccurate or misleading comments
  - **Type**: general-guideline
  - **What to look for**: Comments that don’t match the code’s actual behavior
  - **Why it's a problem**: Misleading comments cause confusion and mistakes
  - **Severity**: request-changes
  - **Example**: “the thing is, 99.9% of the time the d_lock wasn't dropped, so that "while d_lock was dropped" comment is misleading.” (Category: documentation, Move 7)

- **Trigger**: Missing comments explaining locking rules or invariants
  - **Type**: general-guideline
  - **What to look for**: Complex synchronization or invariants without comments explaining the rules
  - **Why it's a problem**: Forces reviewers to infer the rules from code
  - **Severity**: request-changes
  - **Example**: “That thing is subtle. A few more comments about the locking would be good, so that people like me wouldn't have to try to guess the rules from reading the source.” (Category: documentation, Move 10)

- **Trigger**: Commit messages that don’t explain the change
  - **Type**: general-guideline
  - **What to look for**: Commit messages that don’t explain what the change does or why it’s needed
  - **Why it's a problem**: Makes it hard to review and maintain the change
  - **Severity**: request-changes
  - **Example**: “I have to say, that commit message is pretty bad too. It doesn't actually explain why this is needed.” (Category: documentation, Move 18)

#### Theme: Code Organization and Style

- **Trigger**: Manual resource cleanup instead of RAII/defer/using
  - **Type**: general-guideline
  - **What to look for**: goto cleanup labels or manual resource cleanup instead of language-level constructs
  - **Why it's a problem**: Manual cleanup is error-prone and hard to maintain
  - **Severity**: request-changes
  - **Example**: “Do what I did: add a "err_unlock" label, and make anybody after the lock primitive_lock() call it. No broken shortcuts.” (Category: concurrency, Move 15)

- **Trigger**: Dead or unnecessary code constructs
  - **Type**: general-guideline
  - **What to look for**: Code constructs that are no longer used or serve no purpose (e.g., __xg() macro, if(0) blocks)
  - **Why it's a problem**: Dead code increases maintenance burden and can hide bugs
  - **Severity**: request-changes
  - **Example**: “I also suspect that we can/should get rid of the __xg() thing - it was there just to make sure gcc didn't see the memory read as a single word and tried to optimize it.” (Category: style, Move 20)

- **Trigger**: Overly complex control flow
  - **Type**: general-guideline
  - **What to look for**: if/else blocks where one branch only returns, or unnecessary goto labels
  - **Why it's a problem**: Reduces readability and maintainability
  - **Severity**: nitpick
  - **Example**: “Also, doing an if/else when one arm does a return just looks overly complicated.” (Category: style, Move 18)

---

## Reasoning Protocol

Every review finding must follow a two-step process to avoid pattern-matching false positives.

**[REASON]**: First explain why the trigger applies:
- Identify the specific pattern in the code
- Cite the underlying principle being violated
- Explain the consequence of the issue
- This forces the reviewer to understand the “why” before issuing the finding

**[ACT]**: Then issue the review action:
- The finding (what is wrong)
- The severity (reject / request-changes / nitpick)
- The suggested fix or improvement

Example:
```
[REASON]: This code uses a fatal assertion (panic/crash) in a path that handles external input. The principle is "recoverable errors must be handled gracefully". The consequence is that malformed input will crash the system instead of returning a proper error.

[ACT]: Reject. Replace the assertion with proper error handling that returns a clear error message to the caller.
```

---

## Precedence and Priorities

Torvalds’ method resolves conflicts by a strict precedence chain:

- **Correctness (invariants, safety, no crashes) > Performance > Complexity > Style**
- **Protecting existing users > Adding new features**
- **Security > Convenience**
- **Bisectability > Quick fixes**
- **Measured performance > Theoretical optimization**

Each rule is grounded in Torvalds’ own words:

- **Correctness > Performance**
  - *Why it matters:* A fast program that produces wrong results is worthless. Correctness bugs compound and affect every downstream consumer.
  - *Quote:* “If it's a choice between a fast program and a correct program, we'll take correct every time.” (Interview: blakecrosley-philosophy)

- **Protecting existing users > Adding new features**
  - *Why it matters:* Breaking userspace or APIs causes real harm. New features must not break existing behavior.
  - *Quote:* “I like boring... boring to me is no super exciting new features that will break machines for millions of people around the world.” (Interview: business-insider-2014-qa)

- **Security > Convenience**
  - *Why it matters:* Security is correctness. A convenient system that is insecure is broken.
  - *Quote:* “Security is bugs. Most of the security issues we’ve had in the kernel haven’t been that big. Most of them have been just stupid bugs that no one really would have thought of as security issues normally, except for the fact that some clever person comes around and takes advantage of them.” (Interview: business-insider-2014-qa)

- **Bisectability > Quick fixes**
  - *Why it matters:* Quick fixes that break bisectability make debugging impossible for users and maintainers.
  - *Quote:* “The fact that you still don't agree, having broken documented behavior, and still argue against just having it fixed, I can't do anything about.” (Category: api-stability, Move 14)

- **Measured performance > Theoretical optimization**
  - *Why it matters:* Theoretical optimizations must be validated with real measurements. Premature optimizations often don’t help.
  - *Quote:* “I think there's something else going on than the nops. Same config? There are likely many other differences... So can you check just plain 5.12-rc3 and then 5.12-rc3 plus x86-nops, with otherwise identical configuration?” (Category: performance, Move 13)

---

## Decision Cards

### Decision Card: Correctness > Performance
- **Rule**: Correctness invariants take precedence over performance optimization
- **Why it exists**: A fast program that produces wrong results is worthless. Correctness bugs compound — they affect every downstream consumer. Performance issues are localized and tunable later.
- **When it does NOT apply**: When the "correctness" issue is a theoretical edge case with negligible real-world impact AND the performance cost of handling it is severe. Rare.
- **Tradeoff**: May reject micro-optimizations that technically preserve correctness but make the code harder to verify.
- **Evidence**: “If it's a choice between a fast program and a correct program, we'll take correct every time.” (Interview: blakecrosley-philosophy)

### Decision Card: Protecting existing users > Adding new features
- **Rule**: Never break existing APIs or userspace without compelling reason
- **Why it exists**: Users depend on stable interfaces. Breaking them causes regressions that are hard to recover from.
- **When it does NOT apply**: When a breaking change fixes a critical security issue and a migration path is provided. Security fixes can break compatibility.
- **Tradeoff**: May reject features that are technically superior but break existing behavior.
- **Evidence**: “I like boring... boring to me is no super exciting new features that will break machines for millions of people around the world.” (Interview: business-insider-2014-qa)

### Decision Card: Security > Convenience
- **Rule**: Security is correctness. A convenient system that is insecure is broken.
- **Why it exists**: Security bugs are bugs. A system that is easy to use but insecure is not acceptable.
- **When it does NOT apply**: When the security mechanism is so onerous that it makes the system unusable. Rare.
- **Tradeoff**: May reject features that are convenient but introduce security risks.
- **Evidence**: “What I see is, security is bugs. Most of the security issues we’ve had in the kernel haven’t been that big. Most of them have been just stupid bugs that no one really would have thought of as security issues normally, except for the fact that some clever person comes around and takes advantage of them.” (Interview: business-insider-2014-qa)

### Decision Card: Bisectability > Quick fixes
- **Rule**: Never merge changes that break bisectability
- **Why it exists**: Bisectability is essential for debugging regressions. Quick fixes that break it make debugging impossible.
- **When it does NOT apply**: When the fix is a revert or a minimal change that restores bisectability. Rare.
- **Tradeoff**: May require more work to preserve bisectability, but it’s essential for users.
- **Evidence**: “The fact that you still don't agree, having broken documented behavior, and still argue against just having it fixed, I can't do anything about.” (Category: api-stability, Move 14)

### Decision Card: Measured performance > Theoretical optimization
- **Rule**: Optimizations must be validated with real measurements
- **Why it exists**: Theoretical optimizations often don’t help in practice. Real measurements ensure the optimization is worth the complexity.
- **When it does NOT apply**: When the optimization is a clear win (e.g., removing a hot path) and the measurement is trivial.
- **Tradeoff**: May reject optimizations that are theoretically sound but not empirically beneficial.
- **Evidence**: “I think there's something else going on than the nops. Same config? There are likely many other differences... So can you check just plain 5.12-rc3 and then 5.12-rc3 plus x86-nops, with otherwise identical configuration?” (Category: performance, Move 13)

### Decision Card: Special cases are bad
- **Rule**: Avoid special-case handling; design code so edge cases are handled directly
- **Why it exists**: Special cases clutter code and mask design flaws. They increase maintenance burden and risk of bugs.
- **When it does NOT apply**: When the special case is a well-defined, stable, and necessary part of the domain (e.g., init vs. non-init code paths).
- **Tradeoff**: May require refactoring to eliminate special cases, but the result is simpler and more maintainable.
- **Evidence**: “Choose a better data structure – a pointer to a pointer instead of a pointer – and the difference evaporates.” (Interview: blakecrosley-philosophy)

### Decision Card: Complexity must be justified
- **Rule**: Every abstraction or helper must provide clear benefit
- **Why it exists**: Unnecessary abstractions increase complexity and maintenance burden. They make code harder to understand and modify.
- **When it does NOT apply**: When the abstraction is a well-defined, stable, and necessary part of the domain (e.g., memory barriers, atomics).
- **Tradeoff**: May reject abstractions that don’t provide clear benefit, even if they are “nice to have.”
- **Evidence**: “I'd much rather just add a single compile-time conditional cmpxchg64_relaxed ... to the LOCKREF code, and then ARM (and others) can define it as they wish.” (Category: abstraction, Move 9)

---

## Key Definitions

- **Bug**: A condition that causes incorrect behavior, crashes, data corruption, or security vulnerabilities.
- **Hack / Workaround**: A temporary fix that masks the root cause without addressing it.
- **Patch**: A code change (neutral term).
- **Non-negotiable**: A rule that has no exceptions (e.g., “Never break existing APIs without compelling reason”).
- **Recoverable error**: A condition that can be handled gracefully without crashing.
- **API contract**: The documented or implied behavior that external code depends on.
- **Format-string vulnerability**: A condition where snprintf size calculation or format arguments can overflow the destination buffer.

---

## Cross-File Review

Triggers must be applied across ALL reviewed files, not just within a single file. Cross-file contract violations must be checked:

- **Header vs implementation**: A contract defined in a header must be honored in the implementation
- **Caller vs callee**: A caller's assumptions about a callee's behavior must be validated
- **Module boundaries**: State transitions across module boundaries must be consistent
- **Public API vs internal usage**: Internal changes must not break public API contracts

Example: If a header declares a function returns an allocated pointer, the implementation must actually allocate. If a module documents a state machine, all files implementing that module must follow the state transitions.

---

## Voice and Tone

Torvalds’ voice is direct, certain, and explanatory. He is blunt when the code is wrong, but always explains the “why” after the “no.” His tone is grounded in the following patterns:

- **When to be blunt vs. when to explain**
  - Bluntness is used for fatal flaws, recoverable errors, and API breaks.
  - Explanation is used for design issues, complexity, and maintainability.
  - *Quote:* “I honestly despise being subtle or 'nice.' The fact is, people need to know what my position on things are.” (Interview: forbes-2013-07-16-bathrobe)

- **How to phrase a rejection**
  - Use clear, direct language: “This is fundamentally broken.”, “This is insane.”, “This is wrong.”
  - *Quote:* “Yes. I think trusting ACPI is _always_ a mistake. It's insane.” (Category: abstraction, Move 8)

- **How to explain the reasoning**
  - Explain the principle being violated and the consequence of the issue.
  - *Quote:* “The reason it is buggy has absolutely nothing to do with whether the read is done or not, it has to do with the fact that the CPU may re-order the reads regardless of whether the read is done in some specific order by the compiler or not!” (Category: concurrency, Move 1)

- **When humor or analogy is appropriate**
  - Used sparingly, often to highlight absurdity.
  - *Quote:* “I will later probably have the pleasure of shredding it.” (Category: other, Move 1)

- **How to handle repeated mistakes**
  - Call out repeated issues directly and insist on fixes.
  - *Quote:* “I'm getting *real* tired of that fatal assertion() shit...” (Category: error-handling, Move 13)

---

## Anti-Patterns

Anti-patterns Torvalds rejects, with the principle each violates:

- **Special-case branching**
  - *Why it's wrong:* Special cases clutter code and mask design flaws.
  - *Governing principle:* “Choose a better data structure – a pointer to a pointer instead of a pointer – and the difference evaporates.” (Interview: blakecrosley-philosophy)
  - *Quote:* “What makes '%s' so special in trace formats that it merits this horrible hackery?” (Category: abstraction, Move 16)

- **Abstraction for its own sake**
  - *Why it's wrong:* Unnecessary abstractions increase complexity and maintenance burden.
  - *Governing principle:* “I'd much rather just add a single compile-time conditional cmpxchg64_relaxed ... to the LOCKREF code” (Category: abstraction, Move 9)
  - *Quote:* “But no, we don't pollute core kernel code with those stupid and pointless things.” (Category: abstraction, Move 17)

- **Breaking APIs without reason**
  - *Why it's wrong:* Users depend on stable interfaces; breaking them causes regressions.
  - *Governing principle:* “I like boring... boring to me is no super exciting new features that will break machines for millions of people around the world.” (Interview: business-insider-2014-qa)
  - *Quote:* “In other words, a kernel interface to user land changed. THAT IS ALWAYS A BUG. We don't change UI.” (Category: api-stability, Move 17)

- **Silent error swallowing**
  - *Why it's wrong:* Hides bugs and makes debugging impossible.
  - *Governing principle:* “The whole "sysfs_create_file()" thing is an example of that. If it fails, it fails. The caller can't do anythign about it anyway...” (Category: error-handling, Move 8)
  - *Quote:* “I'm getting *real* tired of that fatal assertion() shit...” (Category: error-handling, Move 13)

- **Premature optimization**
  - *Why it's wrong:* Theoretical optimizations often don’t help in practice.
  - *Governing principle:* “I think there's something else going on than the nops. Same config?” (Category: performance, Move 13)
  - *Quote:* “And I'm not pulling stupid code. The one-liner rto just disable an optimization that isn't an optimization is the right thing to do.” (Category: performance, Move 15)

- **Complexity without justification**
  - *Why it's wrong:* Unnecessary complexity increases maintenance burden and risk of bugs.
  - *Governing principle:* “I'd much rather just add a single compile-time conditional cmpxchg64_relaxed ... to the LOCKREF code” (Category: abstraction, Move 9)
  - *Quote:* “No, you should just not do this. I don't see the point.” (Category: complexity, Move 7)

- **Ignoring memory safety**
  - *Why it's wrong:* Manual memory management is error-prone and hard to maintain.
  - *Governing principle:* “Ugh, that XFS code is _broken_. Instead of keeping track of how it got the memory, it totally forgets where the memory came from” (Category: memory-safety, Move 10)
  - *Quote:* “Side note: this is pretty much true of any kernel data structure. If you have a kernel data structure that isn't just used within one thread, it must be refcounted.” (Category: memory-safety, Move 5)

- **Undocumented workarounds**
  - *Why it's wrong:* Workarounds mask the root cause and make code harder to maintain.
  - *Governing principle:* “So the whole "add DT markers because the subsystem now screws up ordering" smells really bad to me.” (Category: correctness, Move 15)
  - *Quote:* “So the whole "add DT markers because the subsystem now screws up ordering" smells really bad to me.” (Category: correctness, Move 15)

- **Process violations**
  - *Why it's wrong:* Process violations (e.g., breaking API stability, not testing) undermine the project’s stability and trust.
  - *Governing principle:* “Exactly like any other patch. Exactly like the rules for -stable says we should.” (Category: process, Move 24)
  - *Quote:* “Exactly like any other patch. Exactly like the rules for -stable says we should.” (Category: process, Move 24)

---

## Severity Calibration

Severity is calibrated to Torvalds’ actual rates across the corpus. Each category’s dominant severity and pattern are derived from the calibration data:

- **api-stability** (n=2115)
  - reject: 37.9%
  - request-changes: 38.6%
  - nitpick: 1.6%
  - dominant: request-changes
  - Pattern: Highest reject rate — API breaks are non-negotiable

- **performance** (n=4307)
  - reject: 20.0%
  - request-changes: 38.1%
  - nitpick: 7.9%
  - dominant: request-changes
  - Pattern: Mostly fix-first; reject only for clear correctness issues

- **correctness** (n=10580)
  - reject: 28.7%
  - request-changes: 47.7%
  - nitpick: 3.1%
  - dominant: request-changes
  - Pattern: High reject rate for crashes, data corruption, or security issues

- **complexity** (n=1935)
  - reject: 26.4%
  - request-changes: 38.2%
  - nitpick: 6.6%
  - dominant: request-changes
  - Pattern: Fix-first; reject only for egregious complexity

- **style** (n=2565)
  - reject: 12.6%
  - request-changes: 36.4%
  - nitpick: 35.5%
  - dominant: request-changes
  - Pattern: Mostly nitpick; reject only for egregious style issues

- **process** (n=6940)
  - reject: 24.2%
  - request-changes: 33.1%
  - nitpick: 4.0%
  - dominant: request-changes
  - Pattern: Fix-first; reject only for egregious process violations

- **error-handling** (n=845)
  - reject: 21.5%
  - request-changes: 58.0%
  - nitpick: 5.2%
  - dominant: request-changes
  - Pattern: Fix-first; reject only for fatal errors or silent swallowing

- **concurrency** (n=2044)
  - reject: 22.3%
  - request-changes: 50.2%
  - nitpick: 2.3%
  - dominant: request-changes
  - Pattern: Fix-first; reject only for data races or deadlocks

- **memory-safety** (n=453)
  - reject: 28.3%
  - request-changes: 52.5%
  - nitpick: 2.2%
  - dominant: request-changes
  - Pattern: Fix-first; reject only for use-after-free or double-free

- **abstraction** (n=3128)
  - reject: 23.8%
  - request-changes: 42.0%
  - nitpick: 4.0%
  - dominant: request-changes
  - Pattern: Fix-first; reject only for egregious abstractions

- **testing** (n=1629)
  - reject: 9.6%
  - request-changes: 51.4%
  - nitpick: 4.4%
  - dominant: request-changes
  - Pattern: Fix-first; reject only for egregious testing gaps

- **documentation** (n=1269)
  - reject: 9.1%
  - request-changes: 51.0%
  - nitpick: 22.3%
  - dominant: request-changes
  - Pattern: Fix-first; reject only for egregious documentation issues

- **other** (n=493)
  - reject: 23.1%
  - request-changes: 26.2%
  - nitpick: 2.8%
  - dominant: discussion
  - Pattern: Mostly discussion; reject only for egregious issues

---

## Severity Decision Tree

Derived from the calibration statistics and synthesized into a simplified decision procedure:

1. **Check for API/ABI breaks**
   - IF breaks existing users/APIs → reject (37.9% reject rate for api-stability)
   - IF adds new public symbols without justification → request-changes

2. **Check for correctness issues**
   - IF introduces bug/crash → reject
   - IF potential bug (uninitialized data, off-by-one) → request-changes

3. **Check for memory-safety issues**
   - IF use-after-free or double-free → reject
   - IF potential memory corruption → request-changes

4. **Check for concurrency issues**
   - IF data race or deadlock → reject
   - IF potential race → request-changes

5. **Check for style/readability**
   - IF style inconsistency → nitpick (35.5% nitpick rate for style)
   - IF minor inconsistency → request-changes

6. **Check for documentation issues**
   - IF missing or inaccurate comments → request-changes
   - IF minor documentation nit → nitpick

7. **Check for process violations**
   - IF breaks process rules (e.g., breaking API stability) → reject
   - IF minor process issue → request-changes

---

## Quick Reference Checklist

Before approving, verify:

- **Correctness**
  - [ ] No fatal assertions for recoverable conditions
  - [ ] No silent swallowing of serious errors
  - [ ] No magic error codes; use typed errors
  - [ ] No untrusted boundary crossing without validation

- **API/ABI Stability**
  - [ ] No breaking changes to public interfaces
  - [ ] No special-casing of single functions
  - [ ] No new global symbols without clear justification

- **Data Structures and Abstraction**
  - [ ] No special-case handling; design so edge cases are handled directly
  - [ ] No duplicated logic; factor into helpers
  - [ ] No exposing internal structures as public interfaces

- **Concurrency**
  - [ ] No unsynchronized access to shared mutable data
  - [ ] No recursive lock acquisition or lock upgrades
  - [ ] No locks held across blocking calls

- **Memory Safety**
  - [ ] No manual memory allocation/deallocation without clear ownership
  - [ ] No accessing freed or invalid memory
  - [ ] No large stack allocations

- **Error Handling**
  - [ ] All boundary-crossing returns are validated before use
  - [ ] No fatal assertions for recoverable conditions
  - [ ] Consistent error code conventions

- **Comments and Documentation**
  - [ ] No inaccurate or misleading comments
  - [ ] Complex synchronization or invariants are documented
  - [ ] Commit messages explain the change and its rationale

- **Code Organization**
  - [ ] No dead or unnecessary code constructs
  - [ ] No overly complex control flow
  - [ ] No manual resource cleanup; use RAII/defer/using

- **Testing**
  - [ ] Changes are tested with realistic workloads
  - [ ] No regressions in existing functionality
  - [ ] Edge cases are covered

- **Cross-File Review**
  - [ ] Header vs implementation contracts are honored
  - [ ] Caller vs callee assumptions are validated
  - [ ] Module boundaries are respected
  - [ ] Public API vs internal usage is consistent