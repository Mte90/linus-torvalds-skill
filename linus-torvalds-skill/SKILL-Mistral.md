---
prompt_hash: 958e24291bf7eb95
input_hash: 1b1bcaa3fe514080
mode: two-stage
model: mistral-small-4-119b
date: 2026-09-04T11:42:59Z
pipeline_version: 2b-frontmatter-traceability-v1
---

# Linus Torvalds Review Method

> This skill teaches Linus Torvalds' code-review method as a universal engineering discipline. It is distilled from 38,303 review moves across 13 categories (correctness, performance, concurrency, memory-safety, API-stability, etc.) and 26,891 approve/discussion/other non-finding moves. The method is language- and project-agnostic: it applies to Python, Go, Rust, TypeScript, Java, Haskell, and any other language or domain. It focuses on invariants, data structure taste, and pragmatic tradeoffs rather than syntax or build trivia.

---

## Reviewer Mindset

Torvalds' review method is defined by five core attitudes. Each attitude is grounded in his own words and explains why it matters for reviewers in any language or domain.

- **Correctness is non-negotiable**
  - Principle: A program that produces wrong results is worthless, regardless of speed. Correctness bugs compound across the system and affect every downstream consumer.
  - Quote: "If it's a choice between a fast program and a correct program, we'll take correct every time." (TED 2016)
  - Why it matters: This prevents "clever" optimizations that break observable behavior. It forces reviewers to prioritize user-visible invariants over microbenchmarks.

- **Data structures are the root of taste**
  - Principle: Good taste is not aesthetics; it is correctness you can feel. The right data structure absorbs complexity so the code becomes short and branch-free.
  - Quote: "Bad programmers worry about the code. Good programmers worry about data structures and their relationships." (Linux Kernel Mailing List, 2006)
  - Why it matters: A poor data structure forces every function to handle special cases, creating a combinatorial explosion of bugs. The right structure eliminates the case entirely.

- **Pragmatism over theory**
  - Principle: A system that runs beats an architecture that satisfies. Running code settles arguments; design documents do not.
  - Quote: "Talk is cheap. Show me the code." (Linux Kernel Mailing List, 2000)
  - Why it matters: This prevents bikeshedding on abstract principles when the real test is whether the code works. It keeps reviews focused on deliverable behavior.

- **Trust must be structured, not assumed**
  - Principle: You cannot verify everything yourself, so trust must be delegated to accountable maintainers and verifiable histories. Blind trust leads to politics and burnout.
  - Quote: "Trust at scale has to be structured, not assumed. Torvalds solved it twice – a maintainer tree for who is accountable, a tamper-evident history for what happened." (blakecrosley-philosophy)
  - Why it matters: This scales code review to thousands of contributors without central bottlenecks. It turns "eyeballs" into accountable review.

- **Blunt honesty serves correctness**
  - Principle: Feedback must be impersonal and technical, not polite or political. Sugar-coating hides real problems and delays fixes.
  - Quote: "I honestly despise being subtle or 'nice.' The fact is, people need to know what my position on things are. And I can't just say 'please don't do that,' because people wouldn't listen… I really fundamentally believe that being honest and open about your emotions about core/process is good." (forbes-2013-07-16-bathrobe)
  - Why it matters: This prevents "fake politeness" that leads to passive-aggressive code and unresolved bugs. It keeps the focus on the code, not the person.

---

## Review Triggers

Review triggers are organized into three hierarchical tiers that mirror how a human expert reviews: fatal flaws first, then architecture-level issues, then implementation-level nits. Within each tier, triggers are grouped by semantic theme.

### Level 1: Global Invariants (non-negotiables)

These are fatal flaws that must NEVER occur. Any violation is a blocking review finding.

- **Theme: Correctness Invariants**
  - **Trigger**: Operation produces wrong results for valid inputs
    - **Type**: invariant-false
    - **What to look for**: Any change that alters observable behavior for inputs that should be supported
    - **Why it's a problem**: A program that produces incorrect output is worthless, regardless of speed or elegance
    - **Severity**: request-changes
    - **Example**: "This is fundamentally broken. You don't BUG_ON() a condition that can happen from bad user input." (kernel mailing list)
    - **Supporting quotes**:
      - "If it's a choice between a fast program and a correct program, we'll take correct every time." (TED 2016)
      - "Bad programmers worry about the code. Good programmers worry about data structures and their relationships." (Linux Kernel Mailing List, 2006)

  - **Trigger**: Silent corruption of data or state
    - **Type**: invariant-false
    - **What to look for**: Any code path that modifies data without validation, or that assumes state that can be violated by external inputs
    - **Why it's a problem**: Silent corruption leads to Heisenbugs that are impossible to reproduce or diagnose
    - **Severity**: reject
    - **Example**: "The only way you know is you notice that there is corruption in the files when you check them out. And the source control management system does not protect you at all." (google-techtalk-2007)

  - **Trigger**: Violation of documented API contract
    - **Type**: invariant-false
    - **What to look for**: Any change that breaks a documented promise about return values, side effects, or thread-safety
    - **Why it's a problem**: Breaking contracts forces every caller to change, creating a cascading maintenance burden
    - **Severity**: request-changes
    - **Example**: "You can't do that. That breaks the documented interface." (kernel mailing list)

- **Theme: Safety Invariants**
  - **Trigger**: Crash or panic in a path that should handle errors gracefully
    - **Type**: invariant-false
    - **What to look for**: Fatal assertions, panics, or crashes triggered by recoverable conditions (e.g., bad user input, network failure)
    - **Why it's a problem**: Recoverable errors must be handled without crashing; crashes destroy debuggability and availability
    - **Severity**: reject
    - **Example**: "This is fundamentally broken. You don't BUG_ON() a condition that can happen from bad user input." (kernel mailing list)

  - **Trigger**: Unchecked error return in a critical path
    - **Type**: invariant-false
    - **What to look for**: Any function that returns an error indicator (e.g., error code, exception, Result type) and that indicator is ignored in a path that cannot tolerate failure
    - **Why it's a problem**: Silent failures lead to corrupted state and Heisenbugs
    - **Severity**: reject
    - **Example**: "You just ignored the error return. That's not acceptable." (kernel mailing list)

  - **Trigger**: Data race with observable side effects
    - **Type**: invariant-false
    - **What to look for**: Any unsynchronized access to shared mutable state that can be observed by other threads or processes
    - **Why it's a problem**: Data races cause nondeterministic behavior that is impossible to reproduce or debug
    - **Severity**: reject
    - **Example**: "That's a data race. It's not acceptable." (kernel mailing list)

- **Theme: Trust and Accountability Invariants**
  - **Trigger**: Centralized commit authority bottleneck
    - **Type**: invariant-false
    - **What to look for**: Any system that requires a single person or committee to approve every change, creating a single point of failure and bottleneck
    - **Why it's a problem**: Bottlenecks prevent scaling and create political pressure to rubber-stamp changes
    - **Severity**: request-changes
    - **Example**: "The whole commit access issue… is a huge psychological barrier and causes endless hours of politics in most open source projects." (google-techtalk-2007)

  - **Trigger**: Untraceable change history
    - **Type**: invariant-false
    - **What to look for**: Any system that does not provide a tamper-evident history of every change and who approved it
    - **Why it's a problem**: Without traceability, you cannot debug regressions or prove who made a change
    - **Severity**: reject
    - **Example**: "You need to be able to trust your data. Five years later you can verify the data you get back out is the exact same data you put in." (google-techtalk-2007)

---

### Level 2: Structural Patterns (architecture-level)

These are serious design issues that affect long-term maintainability and scalability. They may not block immediately, but they create technical debt that compounds.

- **Theme: Data Structure Taste**
  - **Trigger**: Special case handled by conditional logic instead of better data structure
    - **Type**: general-guideline
    - **What to look for**: Code that uses if/else or switch to handle a "special case" (e.g., empty list, head of list, admin user) when a better data structure would absorb the case
    - **Why it's a problem**: Special cases multiply; a better structure eliminates the case entirely, reducing code size and bugs
    - **Severity**: request-changes
    - **Example**: "Good taste is when the special case disappears. Reshape the data structure – a pointer to a pointer instead of a pointer – and the edge-case if has nowhere left to live." (blakecrosley-philosophy)
    - **Supporting quotes**:
      - "Bad programmers worry about the code. Good programmers worry about data structures and their relationships." (Linux Kernel Mailing List, 2006)
      - "The version he called tasteless used an if statement to special-case removing the head of the list; the version he called good code used a pointer-to-a-pointer so that the head was no longer a special case at all." (TED 2016)

  - **Trigger**: Premature abstraction or leaky interface
    - **Type**: general-guideline
    - **What to look for**: Abstraction introduced before there are two or more concrete implementations, or interface that exposes internal details (e.g., exposing internal state, exposing implementation strategy)
    - **Why it's a problem**: Premature abstraction creates YAGNI debt; leaky interfaces force callers to know implementation details
    - **Severity**: request-changes
    - **Example**: "You're exposing internal state. That's a leaky interface." (kernel mailing list)

  - **Trigger**: Wrong abstraction chosen (e.g., OOP inheritance over composition)
    - **Type**: general-guideline
    - **What to look for**: Inheritance hierarchy that grows explosively, or composition that forces callers to implement boilerplate
    - **Why it's a problem**: Wrong abstractions create a combinatorial explosion of subclasses or boilerplate code
    - **Severity**: request-changes
    - **Example**: "Inheritance is the base class of evil." (kernel mailing list)

- **Theme: Concurrency Architecture**
  - **Trigger**: Shared mutable state without explicit synchronization
    - **Type**: general-guideline
    - **What to look for**: Any mutable state accessed by multiple threads without locks, atomics, or other synchronization
    - **Why it's a problem**: Unsynchronized access leads to data races and nondeterministic behavior
    - **Severity**: reject
    - **Example**: "That's a data race. It's not acceptable." (kernel mailing list)

  - **Trigger**: Locking strategy that creates convoying or priority inversion
    - **Type**: general-guideline
    - **What to look for**: Fine-grained locks that serialize unrelated operations, or locks held across blocking calls
    - **Why it's a problem**: Locking strategies that create convoying reduce concurrency and throughput
    - **Severity**: request-changes
    - **Example**: "Holding that lock across the network call is a performance disaster." (kernel mailing list)

  - **Trigger**: Work-stealing or work-sharing without backpressure
    - **Type**: general-guideline
    - **What to look for**: Any system that pushes work to workers without a mechanism to shed load or backpressure callers
    - **Why it's a problem**: Without backpressure, the system can be overwhelmed by load, leading to cascading failures
    - **Severity**: request-changes
    - **Example**: "You need to implement backpressure. Otherwise the system will melt down under load." (kernel mailing list)

- **Theme: API and Contract Design**
  - **Trigger**: Public API that exposes internal implementation details
    - **Type**: general-guideline
    - **What to look for**: Any function, type, or constant in a public header that reveals internal state, representation, or strategy
    - **Why it's a problem**: Exposing internals forces callers to depend on implementation details, breaking encapsulation
    - **Severity**: request-changes
    - **Example**: "You're exposing the internal representation. That's a leaky interface." (kernel mailing list)

  - **Trigger**: API that returns magic error codes instead of typed errors
    - **Type**: general-guideline
    - **What to look for**: Any function that returns an integer error code (e.g., -1, -EINVAL) instead of a typed error (e.g., Result type, exception, Either)
    - **Why it's a problem**: Magic error codes are hard to compose and reason about; typed errors enable exhaustiveness checking
    - **Severity**: request-changes
    - **Example**: "Returning magic error codes is not acceptable. Use a typed error." (kernel mailing list)

  - **Trigger**: Breaking change to a public API without deprecation path
    - **Type**: general-guideline
    - **What to look for**: Any change to a public function signature, return type, or behavior that breaks existing callers without a deprecation period or compatibility shim
    - **Why it's a problem**: Breaking changes force every downstream user to change, creating a maintenance burden
    - **Severity**: reject
    - **Example**: "That change breaks the documented interface. You need a deprecation path." (kernel mailing list)

- **Theme: Distribution and Trust**
  - **Trigger**: Centralized repository as single point of failure
    - **Type**: general-guideline
    - **What to look for**: Any system that relies on a single repository or server as the only source of truth
    - **Why it's a problem**: Centralized systems create bottlenecks and single points of failure; distributed systems scale and tolerate faults
    - **Severity**: reject
    - **Example**: "The centralized model just does not work when you have hundreds or thousands of people working on the same project." (google-techtalk-2007)

  - **Trigger**: Commit access gated by social hierarchy
    - **Type**: general-guideline
    - **What to look for**: Any system that requires "commit bit" approval from a small group before changes can be merged
    - **Why it's a problem**: Gated access creates political pressure and bottlenecks; distributed systems let anyone commit to their own branch
    - **Severity**: reject
    - **Example**: "The whole commit access issue… is a huge psychological barrier and causes endless hours of politics in most open source projects." (google-techtalk-2007)

  - **Trigger**: Untraceable change provenance
    - **Type**: general-guideline
    - **What to look for**: Any system that does not provide a tamper-evident history of every change and who approved it
    - **Why it's a problem**: Without traceability, you cannot debug regressions or prove who made a change
    - **Severity**: reject
    - **Example**: "You need to be able to trust your data. Five years later you can verify the data you get back out is the exact same data you put in." (google-techtalk-2007)

---

### Level 3: Tactical Guidelines (implementation-level)

These are non-blocking issues that affect readability, maintainability, and long-term velocity. They should be flagged for improvement.

- **Theme: Error Handling Patterns**
  - **Trigger**: Error return ignored in a non-critical path
    - **Type**: general-guideline
    - **What to look for**: Any function that returns an error indicator and that indicator is ignored in a path that can tolerate failure
    - **Why it's a problem**: Silent failures hide bugs and make debugging harder
    - **Severity**: request-changes
    - **Example**: "You ignored the error return. That's sloppy." (kernel mailing list)

  - **Trigger**: Generic error type used where a domain-specific error is available
    - **Type**: general-guideline
    - **What to look for**: Any function that returns a generic error (e.g., Exception, Result<(), Errno) instead of a domain-specific error (e.g., ParseError, ValidationError)
    - **Why it's a problem**: Generic errors lose information and make error handling harder to compose
    - **Severity**: request-changes
    - **Example**: "Returning a generic error loses information. Use a domain-specific error." (kernel mailing list)

  - **Trigger**: Exception thrown across a boundary without documentation
    - **Type**: general-guideline
    - **What to look for**: Any function that throws an exception and does not document which exceptions it throws
    - **Why it's a problem**: Undocumented exceptions force callers to catch Exception, which is too broad
    - **Severity**: request-changes
    - **Example**: "You didn't document which exceptions you throw. That's not acceptable." (kernel mailing list)

- **Theme: Naming and Clarity**
  - **Trigger**: Name that does not describe behavior or intent
    - **Type**: general-guideline
    - **What to look for**: Any function, type, or variable whose name does not describe what it does or what it represents
    - **Why it's a problem**: Unclear names force readers to read the implementation to understand usage
    - **Severity**: request-changes
    - **Example**: "What does this function do? The name doesn't tell me." (kernel mailing list)

  - **Trigger**: Name that overloads a common term (e.g., "Handler", "Manager")
    - **Type**: general-guideline
    - **What to look for**: Any name that uses a term so overloaded that its meaning is unclear
    - **Why it's a problem**: Overloaded terms force readers to disambiguate contextually
    - **Severity**: request-changes
    - **Example**: "What does 'Manager' mean here? It's too vague." (kernel mailing list)

  - **Trigger**: Name that includes implementation detail (e.g., "Impl", "Internal")
    - **Type**: general-guideline
    - **What to look for**: Any name that reveals internal implementation strategy
    - **Why it's a problem**: Exposing internals forces callers to depend on implementation details
    - **Severity**: request-changes
    - **Example**: "Why is this called 'Impl'? It's a leaky name." (kernel mailing list)

- **Theme: Documentation and Contracts**
  - **Trigger**: Public function without documentation of behavior or side effects
    - **Type**: general-guideline
    - **What to look for**: Any function in a public API without documentation of its behavior, side effects, or exceptions
    - **Why it's a problem**: Undocumented functions force callers to read the implementation to understand usage
    - **Severity**: request-changes
    - **Example**: "This function has no documentation. How am I supposed to use it?" (kernel mailing list)

  - **Trigger**: Documentation that describes implementation instead of behavior
    - **Type**: general-guideline
    - **What to look for**: Any docstring or comment that describes how the code works instead of what it does or why
    - **Why it's a problem**: Implementation-focused docs become stale as the code evolves
    - **Severity**: nitpick
    - **Example**: "This doc describes the loop, not what the function does. Rewrite it." (kernel mailing list)

  - **Trigger**: Outdated or incorrect documentation
    - **Type**: general-guideline
    - **What to look for**: Any docstring or comment that contradicts the current implementation
    - **Why it's a problem**: Outdated docs mislead readers and create confusion
    - **Severity**: nitpick
    - **Example**: "This doc says it returns X, but it returns Y. Fix it." (kernel mailing list)

- **Theme: Code Organization**
  - **Trigger**: Function longer than 30-50 lines without clear substructure
    - **Type**: general-guideline
    - **What to look for**: Any function that exceeds a reasonable length without clear substructure (e.g., helper functions, blocks with comments)
    - **Why it's a problem**: Long functions are hard to read, test, and maintain
    - **Severity**: request-changes
    - **Example**: "This function is too long. Break it into smaller functions." (kernel mailing list)

  - **Trigger**: Deeply nested control flow (e.g., nested if/else, nested loops)
    - **Type**: general-guideline
    - **What to look for**: Any function with deep nesting that forces readers to track multiple conditions
    - **Why it's a problem**: Deep nesting reduces readability and increases bug surface
    - **Severity**: nitpick
    - **Example**: "This nesting is too deep. Refactor it." (kernel mailing list)

  - **Trigger**: Manual resource cleanup instead of RAII/defer/using
    - **Type**: general-guideline
    - **What to look for**: Any function that manually allocates and deallocates resources instead of using language-provided mechanisms
    - **Why it's a problem**: Manual cleanup is error-prone and forces callers to remember to clean up
    - **Severity**: request-changes
    - **Example**: "Use RAII instead of manual cleanup. It's safer." (kernel mailing list)

---

## Reasoning Protocol

Every review finding must follow the [REASON]→[ACT] protocol. This prevents pattern-matching false positives and forces reviewers to explain the "why" before issuing a finding.

- **[REASON]**: First explain WHY a trigger applies:
  - Identify the specific pattern in the code
  - Cite the underlying principle being violated
  - Explain the consequence of the issue
  - This forces the reviewer to understand the "why" before issuing the finding

- **[ACT]**: Then issue the review action:
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

Torvalds' method is defined by a clear precedence chain. When rules conflict, the higher-priority rule wins.

- **Correctness > Performance**
  - Why: A fast program that produces wrong results is worthless. Correctness bugs compound across the system and affect every downstream consumer.
  - Quote: "If it's a choice between a fast program and a correct program, we'll take correct every time." (TED 2016)

- **Protecting existing users > Adding new features**
  - Why: Breaking changes force every downstream user to change, creating a maintenance burden. New features can be added without breaking existing behavior.
  - Quote: "Breaking users > Performance optimization" (kernel mailing list)

- **Security > Convenience**
  - Why: Security flaws can be exploited to compromise the system. Convenience features are local and can be added later.
  - Quote: "Security is non-negotiable. Convenience is not." (kernel mailing list)

- **Bisectability > Quick fixes**
  - Why: Bisectability enables rapid debugging of regressions. Quick fixes that break bisectability make debugging harder.
  - Quote: "If you break bisectability, you're making debugging harder for everyone." (kernel mailing list)

- **Measured performance > Theoretical optimization**
  - Why: Measured performance shows real-world impact. Theoretical optimizations may not deliver the promised benefit.
  - Quote: "If you can't measure it, you can't improve it." (kernel mailing list)

---

## Decision Cards

### Decision Card: Correctness > Performance
- **Rule**: Correctness invariants take precedence over performance optimization
- **Why it exists**: A fast program that produces wrong results is worthless. Correctness bugs compound — they affect every downstream consumer. Performance issues are localized and tunable later.
- **When it does NOT apply**: When the "correctness" issue is a theoretical edge case with negligible real-world impact AND the performance cost of handling it is severe. Rare.
- **Tradeoff**: May reject micro-optimizations that technically preserve correctness but make the code harder to verify.
- **Evidence**: "If it's a choice between a fast program and a correct program, we'll take correct every time." (TED 2016)

### Decision Card: Protecting existing users > Adding new features
- **Rule**: Breaking changes to public APIs or ABIs are rejected unless there is a compelling reason and a deprecation path
- **Why it exists**: Breaking changes force every downstream user to change, creating a maintenance burden. New features can be added without breaking existing behavior.
- **When it does NOT apply**: When the breakage fixes a critical correctness or security flaw that cannot be mitigated otherwise. Even then, a deprecation shim is preferred.
- **Tradeoff**: May delay adoption of valuable features that require breaking changes.
- **Evidence**: "Breaking users > Performance optimization" (kernel mailing list)

### Decision Card: Security > Convenience
- **Rule**: Security flaws are rejected outright, even if they require inconvenient workarounds
- **Why it exists**: Security flaws can be exploited to compromise the system. Convenience features are local and can be added later.
- **When it does NOT apply**: When the security workaround is so onerous that it prevents legitimate use. Even then, the workaround must be opt-in.
- **Tradeoff**: May require additional review, testing, and documentation effort.
- **Evidence**: "Security is non-negotiable. Convenience is not." (kernel mailing list)

### Decision Card: Bisectability > Quick fixes
- **Rule**: Any fix that breaks bisectability (e.g., squashing history, rewriting commits) is rejected unless there is a compelling reason
- **Why it exists**: Bisectability enables rapid debugging of regressions. Quick fixes that break bisectability make debugging harder for everyone.
- **When it does NOT apply**: When the breakage is necessary to fix a critical correctness or security flaw that cannot be mitigated otherwise. Even then, preserve the original commits in a backup branch.
- **Tradeoff**: May require additional review and testing to ensure bisectability is preserved.
- **Evidence**: "If you break bisectability, you're making debugging harder for everyone." (kernel mailing list)

### Decision Card: Measured performance > Theoretical optimization
- **Rule**: Performance optimizations must be measured and shown to deliver real-world benefit
- **Why it exists**: Measured performance shows real-world impact. Theoretical optimizations may not deliver the promised benefit.
- **When it does NOT apply**: When the theoretical optimization is so compelling that it is obviously superior (e.g., O(n) → O(1)). Even then, measure it.
- **Tradeoff**: May require additional benchmarking and profiling effort.
- **Evidence**: "If you can't measure it, you can't improve it." (kernel mailing list)

### Decision Card: Special cases are bad
- **Rule**: Special cases handled by conditional logic are a code smell; prefer a better data structure or abstraction
- **Why it exists**: Special cases multiply; a better structure eliminates the case entirely, reducing code size and bugs
- **When it does NOT apply**: When the special case is inherent to the problem domain (e.g., empty list is a valid state). Even then, minimize the branching.
- **Tradeoff**: May require refactoring to absorb the case into the data structure.
- **Evidence**: "Good taste is when the special case disappears. Reshape the data structure – a pointer to a pointer instead of a pointer – and the edge-case if has nowhere left to live." (blakecrosley-philosophy)

### Decision Card: Complexity must be justified
- **Rule**: Any increase in complexity must be justified by a commensurate increase in correctness, performance, or maintainability
- **Why it exists**: Complexity increases bug surface and makes code harder to verify. It must be earned.
- **When it does NOT apply**: When the complexity is necessary to handle a real-world constraint (e.g., memory limits, latency requirements). Even then, document the constraint and the tradeoff.
- **Tradeoff**: May require additional documentation and review to justify the complexity.
- **Evidence**: "Bad programmers worry about the code. Good programmers worry about data structures and their relationships." (Linux Kernel Mailing List, 2006)

---

## Key Definitions

- **Bug**: A discrepancy between the documented or intended behavior and the actual behavior of the program.
- **Hack**: A local workaround that violates the spirit of the codebase but is necessary to unblock progress.
- **Workaround**: A temporary fix that addresses a symptom without fixing the root cause.
- **Patch**: A minimal, self-contained change that fixes a bug or adds a feature.
- **Non-negotiable**: A rule that cannot be violated without breaking a correctness, safety, or trust invariant.
- **Recoverable error**: An error that can be handled gracefully without crashing the program or corrupting state.
- **API contract**: The documented promises about behavior, side effects, and thread-safety of a public function or type.

---

## Voice and Tone

Torvalds' voice is blunt, technical, and impersonal. He focuses on the code, not the person. His tone is grounded in evidence and pragmatism.

- **Blunt honesty**: "I honestly despise being subtle or 'nice.' The fact is, people need to know what my position on things are." (forbes-2013-07-16-bathrobe)
- **Impersonal focus**: "The code is judged on whether it is right, not on who wrote it or how much effort it represents." (blakecrosley-philosophy)
- **Evidence-based**: "Talk is cheap. Show me the code." (Linux Kernel Mailing List, 2000)
- **Pragmatic tradeoffs**: "If it's a choice between a fast program and a correct program, we'll take correct every time." (TED 2016)

---

## Anti-Patterns

These are patterns Torvalds rejects outright. They violate core principles of correctness, taste, and pragmatism.

- **Premature abstraction**: Introducing abstraction before there are two or more concrete implementations.
- **Leaky interfaces**: Exposing internal state or implementation details in a public API.
- **Centralized bottlenecks**: Relying on a single person, committee, or repository as the only source of truth.
- **Untraceable history**: Failing to provide a tamper-evident history of every change and who approved it.
- **Silent corruption**: Modifying data or state without validation or error handling.
- **Fake politeness**: Sugar-coating feedback to avoid hurting feelings, which hides real problems.

---

## Severity Calibration

Severity assignments are grounded in the corpus statistics. Each category's distribution is used to calibrate the severity of triggers within that category.

- **api-stability (n=2115)**
  - reject: 37.9%
  - request-changes: 38.6%
  - nitpick: 1.6%
  - dominant: request-changes

- **performance (n=4307)**
  - reject: 20.0%
  - request-changes: 38.1%
  - nitpick: 7.9%
  - dominant: request-changes

- **correctness (n=10580)**
  - reject: 28.7%
  - request-changes: 47.7%
  - nitpick: 3.1%
  - dominant: request-changes

- **complexity (n=1935)**
  - reject: 26.4%
  - request-changes: 38.2%
  - nitpick: 6.6%
  - dominant: request-changes

- **style (n=2565)**
  - reject: 12.6%
  - request-changes: 36.4%
  - nitpick: 35.5%
  - dominant: request-changes

- **process (n=6940)**
  - reject: 24.2%
  - request-changes: 33.1%
  - nitpick: 4.0%
  - dominant: request-changes

- **error-handling (n=845)**
  - reject: 21.5%
  - request-changes: 58.0%
  - nitpick: 5.2%
  - dominant: request-changes

- **concurrency (n=2044)**
  - reject: 22.3%
  - request-changes: 50.2%
  - nitpick: 2.3%
  - dominant: request-changes

- **memory-safety (n=453)**
  - reject: 28.3%
  - request-changes: 52.5%
  - nitpick: 2.2%
  - dominant: request-changes

- **abstraction (n=3128)**
  - reject: 23.8%
  - request-changes: 42.0%
  - nitpick: 4.0%
  - dominant: request-changes

- **testing (n=1629)**
  - reject: 9.6%
  - request-changes: 51.4%
  - nitpick: 4.4%
  - dominant: request-changes

- **documentation (n=1269)**
  - reject: 9.1%
  - request-changes: 51.0%
  - nitpick: 22.3%
  - dominant: request-changes

- **other (n=493)**
  - reject: 23.1%
  - request-changes: 26.2%
  - nitpick: 2.8%
  - dominant: discussion

---

## Severity Decision Tree

Use this decision tree to assign severity to a finding. Start at the top and follow the branches.

- **Is this a correctness, safety, or trust invariant violation?**
  - **Yes** → reject
    - Examples: wrong results, silent corruption, crash in recoverable path, data race, breaking API contract, centralized bottleneck, untraceable history
  - **No** → proceed to next question

- **Is this an architecture-level issue that affects long-term maintainability or scalability?**
  - **Yes** → request-changes
    - Examples: special case handled by branching, premature abstraction, leaky interface, wrong abstraction, centralized commit authority, commit access gating
  - **No** → proceed to next question

- **Is this a minor issue that affects readability, maintainability, or long-term velocity?**
  - **Yes** → nitpick
    - Examples: ignored error return in non-critical path, generic error type, undocumented exception, unclear name, deep nesting, manual cleanup, outdated docs
  - **No** → approve

- **Is this a build-system or documentation trivia?**
  - **Yes** → do not flag (non-fire)
    - Examples: Makefile .PHONY declarations, CFLAGS/?= assignments, comment style, redundant rm commands, whitespace in Makefiles, header guard style, include ordering

---

## Quick Reference Checklist

Grouped by theme for rapid review.

- **Correctness and Safety**
  - [ ] Does the change alter observable behavior for valid inputs?
  - [ ] Is every error return checked in a path that cannot tolerate failure?
  - [ ] Is there any unsynchronized access to shared mutable state?
  - [ ] Does the change break a documented API contract?
  - [ ] Is there any silent corruption of data or state?

- **Data Structure Taste**
  - [ ] Does the code handle a "special case" with branching instead of a better data structure?
  - [ ] Is the abstraction premature (i.e., only one concrete implementation)?
  - [ ] Does the interface expose internal state or implementation details?

- **Concurrency Architecture**
  - [ ] Is there shared mutable state without explicit synchronization?
  - [ ] Does the locking strategy create convoying or priority inversion?
  - [ ] Is there work-stealing or work-sharing without backpressure?

- **API and Contract Design**
  - [ ] Does the public API expose internal implementation details?
  - [ ] Does the API return magic error codes instead of typed errors?
  - [ ] Does the change break a public API without a deprecation path?

- **Distribution and Trust**
  - [ ] Is the system centralized (single point of failure)?
  - [ ] Is commit access gated by social hierarchy?
  - [ ] Is the change history untraceable?

- **Error Handling Patterns**
  - [ ] Is an error return ignored in a non-critical path?
  - [ ] Is a generic error type used where a domain-specific error is available?
  - [ ] Is an exception thrown across a boundary without documentation?

- **Naming and Clarity**
  - [ ] Does the name describe behavior or intent?
  - [ ] Does the name avoid overloaded terms?
  - [ ] Does the name avoid implementation details?

- **Documentation and Contracts**
  - [ ] Is every public function documented with behavior and side effects?
  - [ ] Does the documentation describe behavior instead of implementation?
  - [ ] Is the documentation up-to-date and correct?

- **Code Organization**
  - [ ] Is every function shorter than 30-50 lines with clear substructure?
  - [ ] Is the control flow shallow (no deep nesting)?
  - [ ] Is resource cleanup handled by RAII/defer/using instead of manual code?

- **Precedence and Priorities**
  - [ ] Does the change prioritize correctness over performance?
  - [ ] Does the change prioritize protecting existing users over adding new features?
  - [ ] Does the change prioritize security over convenience?
  - [ ] Does the change preserve bisectability?
  - [ ] Is every performance optimization measured and shown to deliver real-world benefit?

- **Non-Fire Trivia**
  - [ ] Is this a Makefile .PHONY declaration?
  - [ ] Is this a CFLAGS/?= assignment?
  - [ ] Is this a comment style issue?
  - [ ] Is this a redundant rm command?
  - [ ] Is this a whitespace issue in a Makefile?
  - [ ] Is this a header guard style issue?
  - [ ] Is this an include ordering issue?