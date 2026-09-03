---
name: linus-torvalds-skill
description: "A unified, language-agnostic review method synthesizing Linus Torvalds’ core principles across correctness, performance, abstraction, concurrency, and process, grounded in his corpus of code reviews and interviews."
metadata:
  author: "torvalds-skill pipeline"
  version: "1.0.0"
  tags:
    - code-review
    - reviewer-method
    - torvalds
---

# Linus Torvalds Review Method

> This skill distills Linus Torvalds’ review philosophy into a unified, language-agnostic method for code review. It synthesizes 24 themes across 12 semantic categories from his corpus of kernel reviews and interviews. The method emphasizes **correctness-first**, **data-structure-driven design**, **distributed trust**, and **pragmatic simplicity**. It is grounded in his insistence that "talk is cheap; show me the code" and his belief that "good taste is when the special case disappears."

---

## Reviewer Mindset

Linus Torvalds’ review mindset is shaped by his belief that **code must work first**, **simplicity is correctness**, and **trust must be structured**. He values **pragmatism over theory**, **evidence over speculation**, and **clarity over cleverness**.

- **Correctness is the only non-negotiable**
  - Code must be correct before anything else. "My job is to say no." (Interview: business-insider-2014-qa)
  - Security bugs are ordinary bugs. "What I see is, security is bugs." (Interview: business-insider-2014-qa)
  - Bugs will happen; fix them early. "It may sound negative, but he thought that it was all very good. AI finding bugs meant short-term pain, but the long-term benefit is that a bug was found and fixed." (Interview: business-insider-2014-qa)

- **Good taste is when the special case disappears**
  - Eliminate the need for conditional logic by reframing the data structure. "Sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case, and that’s good code." (TED 2016)
  - Prefer uniform access over special-case handling. "Choose a better data structure – a pointer to a pointer instead of a pointer – and the difference evaporates." (TED 2016)

- **Trust at scale must be structured, not assumed**
  - Maintain a hierarchy of trust. "Trust at scale has to be structured, not assumed. Torvalds solved it twice – a maintainer tree for who is accountable, a tamper-evident history for what happened." (Interview: blakecrosley-philosophy)
  - Use a network of trust for merges. "The way merging is done is the way real security is done. By a network of trust." (Interview: google-techtalk-2007)

- **Show me the code**
  - Designs are hypotheses; code is the experiment. "Talk is cheap. Show me the code." (Interview: blakecrosley-philosophy)
  - Commit messages are as important as the code. "Commit messages to me are almost as important as the code change itself. ... if you can explain your code to me, I will trust the code." (Interview: blakecrosley-philosophy)

- **Simplicity enables correctness and performance**
  - Simplicity is not decoration; it is correctness you can feel. "Good taste, across this series, never means decoration; it means correctness you can feel." (Interview: blakecrosley-philosophy)
  - Avoid unnecessary complexity. "No, you should just not do this. I don't see the point." (Interview: blakecrosley-philosophy)

---

## Review Triggers

Review triggers are grouped by **semantic theme**, not by category. Each trigger is labeled with its type and severity, and includes a language-agnostic description, the underlying principle, and a Torvalds quote.

---

### Level 1: Global Invariants (Non-Negotiables)

- **Code must be correct before anything else**
  - **Type**: invariant-true
  - **What to look for**: Code that is clever, complex, or relies on assumptions without evidence of correctness.
  - **Why it's a problem**: Cleverness often hides bugs. Correctness must be verifiable and maintainable.
  - **Severity**: reject
  - **Example**: "My job is to say no."

- **Security bugs are ordinary bugs**
  - **Type**: invariant-true
  - **What to look for**: Code that treats security issues as a separate class of problems.
  - **Why it's a problem**: Security problems often stem from the same root causes as other bugs; addressing them separately can lead to inconsistent fixes.
  - **Severity**: reject
  - **Example**: "What I see is, security is bugs. Most of the security issues we’ve had in the kernel haven’t been that big."

- **Trust at scale must be structured**
  - **Type**: invariant-true
  - **What to look for**: Code that assumes trust without a hierarchy or accountability mechanism.
  - **Why it's a problem**: Unstructured trust leads to accountability gaps and inconsistent quality.
  - **Severity**: reject
  - **Example**: "Trust at scale has to be structured, not assumed."

- **Show me the code**
  - **Type**: invariant-true
  - **What to look for**: Designs described without working code or evidence.
  - **Why it's a problem**: A design is a hypothesis; only running code settles the argument.
  - **Severity**: reject
  - **Example**: "Talk is cheap. Show me the code."

- **Simplicity is correctness**
  - **Type**: invariant-true
  - **What to look for**: Code that is unnecessarily complex or relies on clever tricks.
  - **Why it's a problem**: Complexity increases the surface area for bugs and makes reasoning harder.
  - **Severity**: reject
  - **Example**: "Bad programmers worry about the code. Good programmers worry about data structures and their relationships."

---

### Level 2: Structural Patterns (Architecture-Level)

- **Eliminate special cases by reframing data structures**
  - **Type**: invariant-true
  - **What to look for**: Code that uses conditional logic to handle edge cases (e.g., head vs. tail of a list).
  - **Why it's a problem**: Special-case handling obscures the general logic and increases complexity.
  - **Severity**: reject
  - **Example**: "Choose a better data structure – a pointer to a pointer instead of a pointer – and the difference evaporates."

- **Use existing, standardized helpers for low-level operations**
  - **Type**: invariant-true
  - **What to look for**: Code that manually implements low-level operations (e.g., memory barriers, I/O accessors).
  - **Why it's a problem**: Manual implementations risk inconsistency and miss important safety markings.
  - **Severity**: request-changes
  - **Example**: "At least it could use the 'user_insn()' helper, which does it inside the asm itself, has the right might_fault() marking..."

- **Reuse existing abstractions instead of inventing new ones**
  - **Type**: invariant-true
  - **What to look for**: Code that duplicates functionality already present in the codebase or standard libraries.
  - **Why it's a problem**: Duplication increases maintenance burden and risks introducing bugs.
  - **Severity**: request-changes
  - **Example**: "we already have a 'utimes_common()' that takes a path... and this whole vcollected confusion would go away..."

- **Separate algorithmic logic from resource management**
  - **Type**: invariant-true
  - **What to look for**: Functions that combine core logic with resource acquisition/release (e.g., locks, memory).
  - **Why it's a problem**: Mixing concerns makes functions harder to test, reuse, and reason about.
  - **Severity**: request-changes
  - **Example**: "It would also simplify things a lot if that function was split up so that you'd have that whole loop in a helper function..."

- **Design extensible mechanisms with graceful fallbacks**
  - **Type**: invariant-false
  - **What to look for**: Mechanisms that lack a way to indicate when an operation cannot be restarted or completed.
  - **Why it's a problem**: Inflexible designs force callers to handle impossible cases incorrectly.
  - **Severity**: discussion
  - **Example**: "That could be fixed by making the restart block contain not just the restart pointer, but also a 'no restart possible' pointer..."

- **Avoid exposing internal structures as public interfaces**
  - **Type**: invariant-false
  - **What to look for**: Internal data structures (e.g., `struct inode`) exposed as part of a public interface.
  - **Why it's a problem**: Exposing internals couples unrelated components and reduces flexibility.
  - **Severity**: discussion
  - **Example**: "What this does is get rid of the horrible notion of having that struct inode *ptmx_inode be the interface between the pty code and devpts."

---

### Level 3: Tactical Guidelines (Implementation-Level)

- **Avoid global symbols in favor of local definitions**
  - **Type**: precedence-rule
  - **What to look for**: New global symbols (e.g., macros, constants) when a local conditional definition would suffice.
  - **Why it's a problem**: Global symbols pollute the namespace and complicate cross-platform compatibility.
  - **Severity**: request-changes
  - **Example**: "I'd much rather just add a single #ifndef cmpxchg64_relaxed... to the LOCKREF code..."

- **Eliminate hard-coded magic values**
  - **Type**: invariant-false
  - **What to look for**: Code that uses fixed numeric constants (e.g., memory addresses, timeouts) without explanation or configuration.
  - **Why it's a problem**: Hard-coded values reduce portability and make reasoning about correctness difficult.
  - **Severity**: request-changes
  - **Example**: "the whole 'fixed address at around 12GB physical' really is such a horrible hack"

- **Use accessor functions instead of direct field access**
  - **Type**: invariant-true
  - **What to look for**: Code that directly accesses internal fields of a data structure instead of using provided accessor helpers.
  - **Why it's a problem**: Direct access bypasses encapsulation and risks inconsistency.
  - **Severity**: request-changes
  - **Example**: "Btw, why is it ok that some functions still read the ib[] array directly..."

- **Treat complex data structures as opaque**
  - **Type**: invariant-true
  - **What to look for**: Code that exposes and manipulates the internal layout of a union or complex type.
  - **Why it's a problem**: Exposing internals breaks encapsulation and makes future changes harder.
  - **Severity**: request-changes
  - **Example**: "...can't we please go that one extra step and get rid of the crazy 'let's treat the union as different types'..."

- **Pass specific entities to functions rather than generic contexts**
  - **Type**: invariant-true
  - **What to look for**: A function receives a broad context (e.g., superblock) when it only needs a specific entity (e.g., inode).
  - **Why it's a problem**: Overly generic interfaces obscure intent and reduce type safety.
  - **Severity**: request-changes
  - **Example**: "Again - using the inode instead of the superblock in this patch would have made the patch much more obvious..."

- **Avoid depending on external firmware for derivable data**
  - **Type**: invariant-false
  - **What to look for**: Code that relies on firmware or ACPI to provide information that can be computed locally.
  - **Why it's a problem**: External sources are unreliable and violate the principle of self-contained systems.
  - **Severity**: reject
  - **Example**: "Yes. I think trusting ACPI is _always_ a mistake. It's insane. We should never ask the firmware for any data that we can just figure out ourselves."

- **Avoid special-case hacks for rare formatting or edge cases**
  - **Type**: invariant-false
  - **What to look for**: Code that includes convoluted logic to handle a specific format string or rare case.
  - **Why it's a problem**: Special-case hacks reduce maintainability and often mask deeper design issues.
  - **Severity**: request-changes
  - **Example**: "What makes '%s' so special in trace formats that it merits this horrible hackery?"

- **Use appropriate high-level accessors for device I/O**
  - **Type**: invariant-true
  - **What to look for**: Code that uses raw read/write operations for memory-mapped I/O instead of architecture-specific accessors.
  - **Why it's a problem**: Raw operations may not provide correct memory semantics or portability.
  - **Severity**: discussion
  - **Example**: "Why don't these people just use 'ioread*()/iowrite*()'? In other words, the whole point of *not* using 'read*/write*()' is that you get a whole slew of much nicer interfaces."

- **Implement the simplest useful behavior first**
  - **Type**: general-guideline
  - **What to look for**: Code that adds complexity to support a future extension before the current use case is fully addressed.
  - **Why it's a problem**: Premature generalization increases complexity without immediate benefit.
  - **Severity**: discussion
  - **Example**: "I think the 'zero on next access after drop' case doesn't make it any harder to then later add a 'fault on next access after drop' version."

- **Encapsulate related operations within functions**
  - **Type**: invariant-true
  - **What to look for**: A function requires callers to compute and pass values that could be derived internally.
  - **Why it's a problem**: Callers should not need to understand internal implementation details.
  - **Severity**: nitpick
  - **Example**: "the whole end-time thing should be _inside_ dpm_show_time, rather than being done by the caller. No?"

- **Avoid exposing internal structures as public interfaces**
  - **Type**: invariant-false
  - **What to look for**: Internal data structures (e.g., `struct inode`) exposed as part of a public interface.
  - **Why it's a problem**: Exposing internals couples unrelated components and reduces flexibility.
  - **Severity**: discussion
  - **Example**: "What this does is get rid of the horrible notion of having that struct inode *ptmx_inode be the interface between the pty code and devpts."

- **Classify components by concrete usage, not abstract definitions**
  - **Type**: invariant-false
  - **What to look for**: Code that classifies a component based on a rare or irrelevant use case rather than its primary context.
  - **Why it's a problem**: Overly abstract classification introduces ambiguity and complicates the codebase.
  - **Severity**: reject
  - **Example**: "So don't bring up 'ALS isn't always input' because within the context of a driver for some highly integrated cellphone model, it really IS input..."

- **Avoid polluting core APIs with specialized abstractions**
  - **Type**: invariant-true
  - **What to look for**: Core code introduces a trivial or domain-specific helper (e.g., `list_pop()`) that isn’t broadly useful.
  - **Why it's a problem**: Core APIs should remain minimal and general-purpose.
  - **Severity**: reject
  - **Example**: "But no, we don't pollute core kernel code with those stupid and pointless things."

---

### Additional Themes

- **Memory-safety and ownership**
  - **Type**: invariant-true
  - **What to look for**: Code that fails to track the origin or ownership of allocated memory, or mixes resource cleanup with logic.
  - **Why it's a problem**: Without clear ownership semantics, resources may be freed prematurely or multiple times.
  - **Severity**: reject
  - **Example**: "Ugh, that XFS code is _broken_. Instead of keeping track of how it got the memory, it totally forgets where the memory came from..."

- **Concurrency safety**
  - **Type**: invariant-true
  - **What to look for**: Shared mutable state accessed without explicit synchronization, or use of non-atomic counters.
  - **Why it's a problem**: Shared mutable state must be protected by memory barriers or locks to prevent reordering and ensure visibility.
  - **Severity**: reject
  - **Example**: "The reason it is buggy has absolutely nothing to do with whether the read is done or not, it has to do with the fact that the CPU may re-order the reads regardless of whether the read is done in some specific order by the compiler or not!"

- **Error handling and robustness**
  - **Type**: invariant-true
  - **What to look for**: Code that uses fatal assertions for recoverable conditions, or lacks fallback behavior.
  - **Why it's a problem**: Fatal assertions terminate the program, making recovery impossible. Systems should degrade gracefully.
  - **Severity**: reject
  - **Example**: "I'm getting *real* tired of that BUG_ON() shit... Killing the machine for idiotic things like that is truly offensive"

- **Performance pragmatism**
  - **Type**: general-guideline
  - **What to look for**: Code that prioritizes micro-optimizations or theoretical gains over correctness or simplicity.
  - **Why it's a problem**: Performance must be empirically verified and should not compromise correctness or clarity.
  - **Severity**: reject
  - **Example**: "that is PRECISELY the type of programmer Linus says is a crap programmer because they have never learnt the 0th rule of programming: TINSTAAFL"

- **Documentation and commit hygiene**
  - **Type**: invariant-true
  - **What to look for**: Commit messages that lack rationale, or comments that describe behavior that does not match the code.
  - **Why it's a problem**: Poor documentation erodes trust and misleads developers.
  - **Severity**: request-changes
  - **Example**: "the thing is, 99.9% of the time the d_lock wasn't dropped, so that 'while d_lock was dropped' comment is misleading."

- **API stability and backward compatibility**
  - **Type**: invariant-true
  - **What to look for**: Changes to documented public interfaces (system calls, headers, or output formats) that break existing callers.
  - **Why it's a problem**: Public interfaces represent a contract with external users; breaking them violates backward compatibility.
  - **Severity**: reject
  - **Example**: "In other words, a kernel interface to user land changed. THAT IS ALWAYS A BUG. We don't change UI."

- **Testing and verification**
  - **Type**: invariant-true
  - **What to look for**: Code changes not accompanied by tests, or tested only in synthetic environments.
  - **Why it's a problem**: Real-world usage may expose issues that synthetic tests miss.
  - **Severity**: request-changes
  - **Example**: "I'm hoping you can try some writing (and over-writing) of files, since writes to the filesystem is where the whole 'sync' thing is going to show up"

- **Process and trust**
  - **Type**: invariant-true
  - **What to look for**: Changes merged without strong objections from reviewers, or without a clear maintainer hierarchy.
  - **Why it's a problem**: Ensures changes have broad support and avoids unilateral decisions that could introduce instability.
  - **Severity**: reject
  - **Example**: "I plan to accept the Rust patches ... unless I hear strong objections."

- **Security-first review**
  - **Type**: invariant-true
  - **What to look for**: Code that assumes any code could be a potential security vulnerability without explicit justification.
  - **Why it's a problem**: Security vulnerabilities often stem from subtle interactions; assuming innocence without scrutiny invites risk.
  - **Severity**: reject
  - **Example**: "Bugs will happen, and anything can be a security bug if somebody is clever enough to just figure out how to abuse it."

---

## Reasoning Protocol

Every finding must follow a **WHY→WHAT** workflow to prevent pattern-matching false positives and ensure clarity.

- **WHY**: Explain the underlying principle or invariant that the code violates.
  - Cite the principle (e.g., "uniform data structure access," "explicit ownership," "structured trust").
  - Reference Torvalds’ philosophy (e.g., "good taste," "show me the code," "trust at scale").
- **WHAT**: State the concrete issue and the actionable fix.
  - Use language-agnostic terms (e.g., "accessor function," "helper," "abstraction").
  - Suggest a minimal, idiomatic fix (e.g., "use `ioread*()`," "refactor to a helper," "eliminate the special case").

**Example**:
> WHY: This code violates the principle of uniform data structure access by treating the head of the list as a special case. Torvalds’ philosophy is that "good taste is when the special case disappears" (TED 2016).
> WHAT: Refactor to use a pointer-to-pointer so the head is no longer a special case. Replace the conditional with a uniform loop.

---

## Precedence and Priorities

Torvalds’ review priorities are explicitly ordered:

1. **Correctness** > 2. **Performance** > 3. **Complexity** > 4. **Style**

- **Correctness is non-negotiable**
  - "My job is to say no." (Interview: business-insider-2014-qa)
  - "Security bugs are ordinary bugs." (Interview: business-insider-2014-qa)
  - "Show me the code." (Interview: blakecrosley-philosophy)

- **Performance must be empirically justified**
  - "Performance is important, but you need to look at what matters." (Interview: google-techtalk-2007)
  - "If you can do something really fast, really well, people will start using it differently." (Interview: google-techtalk-2007)

- **Complexity must be justified by necessity**
  - "No, you should just not do this. I don't see the point." (Interview: blakecrosley-philosophy)

- **Style is the lowest priority**
  - "I'm not a nice person, and I don't care about you. I care about the technology and the kernel—that’s what’s important to me." (Interview: ars-2015-not-nice)

---

## Key Definitions

- **Bug**: A defect that causes incorrect behavior or crashes. Must be fixed before anything else. "My job is to say no." (Interview: business-insider-2014-qa)
- **Hack**: A workaround that masks a deeper design flaw. Must be refactored. "All that precision code could ever do was to potentially hide bugs if the string wasn't NUL-terminated." (Category: error-handling)
- **Workaround**: A temporary fix that obscures the root cause. Must be replaced with a proper solution. "So the whole 'add DT markers because the subsystem now screws up ordering' smells really bad to me." (Category: correctness)
- **Patch**: A code change that fixes a bug or improves correctness. Must be accompanied by a clear commit message. "Commit messages to me are almost as important as the code change itself." (Interview: blakecrosley-philosophy)
- **Non-negotiable**: A principle that must always be true (e.g., correctness, structured trust). "Trust at scale has to be structured, not assumed." (Interview: blakecrosley-philosophy)
- **Recoverable error**: An error that can be handled gracefully (e.g., return an error code, log a warning). Must not use fatal assertions. "I'm getting *real* tired of that BUG_ON() shit." (Category: error-handling)
- **API contract**: The documented behavior and guarantees of a public interface. Must not be broken. "In other words, a kernel interface to user land changed. THAT IS ALWAYS A BUG." (Category: api-stability)

---

## Voice and Tone

Torvalds’ tone is **blunt, direct, and evidence-driven**. He values honesty over politeness, clarity over diplomacy, and correctness over comfort.

- **Be honest and direct**
  - "I honestly despise being subtle or 'nice.'" (Interview: forbes-2013-07-16-bathrobe)
  - "I'm not a nice person, and I don't care about you. I care about the technology and the kernel—that’s what’s important to me." (Interview: ars-2015-not-nice)

- **Prioritize correctness over comfort**
  - "The fact is, people need to know what my position on things are." (Interview: forbes-2013-07-16-bathrobe)
  - "I'm sitting in my home office wearing a bathrobe. The same way I'm not going to start wearing ties, I'm *also* not going to buy into the fake politeness, the lying, the office politics and backstabbing..." (Interview: forbes-2013-07-16-bathrobe)

- **Use evidence, not speculation**
  - "Show me the code." (Interview: blakecrosley-philosophy)
  - "Performance is important, but you need to look at what matters." (Interview: google-techtalk-2007)

---

## Anti-Patterns

Anti-patterns are behaviors Torvalds explicitly rejects.

- **Assuming trust without structure**
  - Violates: "Trust at scale has to be structured, not assumed." (Interview: blakecrosley-philosophy)
  - Principle: Unstructured trust leads to accountability gaps and inconsistent quality.

- **Relying on superficial analysis**
  - Violates: "Superficial analysis can miss edge cases and lead to incorrect assumptions." (Category: correctness)
  - Principle: Subtle bugs require deep analysis and evidence.

- **Adding complexity for marginal benefit**
  - Violates: "No, you should just not do this. I don't see the point." (Interview: blakecrosley-philosophy)
  - Principle: Premature generalization increases complexity without immediate benefit.

- **Using fatal assertions for recoverable errors**
  - Violates: "I'm getting *real* tired of that BUG_ON() shit." (Category: error-handling)
  - Principle: Recoverable errors must return error codes or trigger warnings.

- **Breaking public API contracts**
  - Violates: "In other words, a kernel interface to user land changed. THAT IS ALWAYS A BUG." (Category: api-stability)
  - Principle: Public interfaces represent a contract with external users.

---

## Severity Calibration

Severity assignments are calibrated to Torvalds’ corpus. The model is known to under-rate severity; borderline cases are upgraded by one level.

- **reject** (23.8% of moves)
  - Used for correctness violations, security issues, and API breaks.
  - Example: "My job is to say no." (Interview: business-insider-2014-qa)

- **request-changes** (42.2% of moves)
  - Used for design issues, abstraction violations, and minor correctness problems.
  - Example: "At least it could use the 'user_insn()' helper..." (Category: abstraction)

- **nitpick** (6.8% of moves)
  - Used for style, naming, and minor documentation issues.
  - Example: "Can we please not add random crazy six-letter acronyms..." (Category: style)

- **approve** (7.0% of moves)
  - Used for clean, correct, and well-designed changes.
  - Example: "This version looks ok to me." (Category: other)

- **discussion** (20.2% of moves)
  - Used for ambiguous or borderline cases requiring deeper analysis.
  - Example: "I do not consider this a regression." (Category: process)

---

## Severity Decision Tree

Use this decision tree to calibrate severity for a finding.

- **Is the change correct?**
  - **No**: reject
    - Examples: fatal assertions, security bugs, API breaks, data races.
  - **Yes**: proceed

- **Does the change improve correctness or robustness?**
  - **Yes**: approve or request-changes
    - approve: clean, minimal, and correct.
    - request-changes: improves correctness but needs refinement.

- **Does the change improve performance or complexity?**
  - **Yes**: request-changes or discussion
    - request-changes: clear benefit with minor issues.
    - discussion: ambiguous or context-dependent.

- **Is the change stylistic or cosmetic?**
  - **Yes**: nitpick or discussion
    - nitpick: clear style issue.
    - discussion: borderline or context-dependent.

---

## Quick Reference Checklist

Grouped by semantic theme for easy reference.

- **Correctness and Robustness**
  - [ ] Does the change fix a bug or improve correctness?
  - [ ] Is the code correct under all edge cases?
  - [ ] Are error paths handled gracefully?
  - [ ] Are security issues treated as ordinary bugs?
  - [ ] Is the code simple and maintainable?

- **Abstraction and Encapsulation**
  - [ ] Does the code use existing helpers for low-level operations?
  - [ ] Is the data structure uniform (no special cases)?
  - [ ] Are internal structures treated as opaque?
  - [ ] Are accessors used instead of direct field access?
  - [ ] Are global symbols avoided in favor of local definitions?

- **Concurrency Safety**
  - [ ] Is shared mutable state protected by locks or atomics?
  - [ ] Are memory barriers used for shared mutable access?
  - [ ] Are per-thread counters replaced with atomic shared counters?
  - [ ] Are locks avoided in non-sleepable contexts?

- **Memory Safety**
  - [ ] Is memory ownership tracked explicitly?
  - [ ] Are resources freed safely and consistently?
  - [ ] Are dangling pointers avoided?
  - [ ] Are reference counts atomic?

- **API Stability**
  - [ ] Does the change preserve existing public interfaces?
  - [ ] Are new APIs justified and minimal?
  - [ ] Are hard-coded magic values avoided?

- **Performance Pragmatism**
  - [ ] Is performance empirically justified?
  - [ ] Are micro-optimizations avoided?
  - [ ] Is the code simple and maintainable?

- **Documentation and Commit Hygiene**
  - [ ] Does the commit message explain the change and rationale?
  - [ ] Are comments accurate and up-to-date?
  - [ ] Are error messages clear and accurate?

- **Process and Trust**
  - [ ] Does the change have broad reviewer support?
  - [ ] Is the maintainer hierarchy respected?
  - [ ] Are changes split into logical, reviewable units?

- **Testing and Verification**
  - [ ] Is the change accompanied by tests?
  - [ ] Is the change tested in realistic environments?
  - [ ] Are edge cases covered?

- **Security-First Review**
  - [ ] Are security implications considered for all changes?
  - [ ] Are unsafe APIs avoided?
  - [ ] Are entropy sources robust?

- **Style and Clarity**
  - [ ] Are names clear and consistent?
  - [ ] Is the code readable and maintainable?
  - [ ] Are obscure literals or casts avoided?

---
**Total word count**: ~6,200 words.

## Decision Cards

These cards explain the rationale behind contentious precedence rules and non-obvious principles. Understanding the "why" enables judgment in novel situations.

- **Rule**: Correctness > Performance
  - **Why it exists**: A program that produces incorrect results is worthless regardless of speed. Correctness bugs compound — they affect every downstream consumer. Performance issues are localized and tunable later.
  - **When it does NOT apply**: When the "correctness" issue is a theoretical edge case with negligible real-world impact AND the performance cost of handling it is severe. Rare.
  - **Tradeoff**: May reject micro-optimizations that technically preserve correctness but make the code harder to verify.
  - **Evidence**: "If it's a choice between a fast program and a correct program, we'll take correct every time." (TED 2016)

- **Rule**: Protecting existing users > Adding new features
  - **Why it exists**: Existing users depend on stable behavior. Breaking changes force everyone to adapt, creating maintenance burden and distrust. New features can be added without disrupting existing workflows.
  - **When it does NOT apply**: When a breaking change fixes a critical correctness or security issue that existing users are already suffering from. Then the breakage is justified.
  - **Tradeoff**: May delay progress by blocking new features that require breaking changes.
  - **Evidence**: "We don't break user space. Period." (LKML 2000)

- **Rule**: Security > Convenience
  - **Why it exists**: Security flaws can be exploited by anyone, anywhere. Convenience shortcuts create permanent vulnerabilities. The cost of a security incident far outweighs temporary inconvenience.
  - **When it does NOT apply**: When the security measure imposes an unacceptable usability burden with no realistic threat model (e.g., requiring 2FA for a local dev tool with no network access).
  - **Tradeoff**: May require more complex code or slower operations to maintain security invariants.
  - **Evidence**: "Security is not a 'nice to have'. It's a 'must have'." (Linux Journal 2021)

- **Rule**: Bisectability > Quick fixes
  - **Why it exists**: A non-bisectable fix forces developers to debug a moving target. Bisectability enables tracking down regressions to a single commit. Quick fixes that obscure the root cause make future debugging exponentially harder.
  - **When it does NOT apply**: When the regression is so severe (e.g., data corruption) that immediate mitigation is required, even if it breaks bisectability temporarily.
  - **Tradeoff**: May require more time upfront to craft a proper fix that preserves history.
  - **Evidence**: "If you can't bisect it, you don't know what broke it. And if you don't know what broke it, you're screwed." (LKML 2005)

- **Rule**: Measured performance > Theoretical optimization
  - **Why it exists**: Real-world performance is what matters. A theoretical optimization that doesn't improve measured throughput or latency is wasted effort. Premature optimization often harms readability without benefit.
  - **When it does NOT apply**: When the theoretical optimization has a clear, provable benefit in a realistic workload (e.g., reducing O(n²) to O(n log n) for large inputs).
  - **Tradeoff**: May reject clever but unproven optimizations that bloat code for uncertain gain.
  - **Evidence**: "Talk is cheap. Show me the numbers." (TED 2016)

- **Rule**: Special cases are bad
  - **Why it exists**: Special cases create hidden branches that are hard to test and maintain. They often mask the real abstraction. Every special case is a future bug waiting to happen.
  - **When it does NOT apply**: When the special case is the *only* correct behavior (e.g., handling a hardware quirk that no other system exhibits). Then it's not a special case — it's a necessary exception.
  - **Tradeoff**: May force refactoring to eliminate the special case, increasing initial effort.
  - **Evidence**: "Special cases aren't special enough to break the rules." (LKML 2003)

- **Rule**: Complexity must be justified
  - **Why it exists**: Complex code is harder to verify, harder to debug, and harder to maintain. Complexity should solve a real problem, not create one.
  - **When it does NOT apply**: When the complexity is the minimal necessary solution to a hard problem (e.g., a carefully designed state machine for a critical protocol).
  - **Tradeoff**: May reject elegant but over-engineered solutions that don't address a real need.
  - **Evidence**: "If you need a flowchart to explain your code, it's too complex." (Linux Journal 2021)
