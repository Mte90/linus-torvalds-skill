---
prompt_hash: a0474be52ff7e7a5
input_hash: a4c1f1c0990bd5fd
mode: two-stage
model: mistral-small-4-119b
date: 2026-11-04T15:51:00Z
pipeline_version: 2b-frontmatter-traceability-v1
---

# Linus Torvalds Review Method

> This skill synthesizes Linus Torvalds' explicit engineering philosophy, interview definitions, and thousands of code review moves into a unified review method. It is designed to be language-agnostic and project-agnostic, applicable to Python, Go, Rust, C++, Java, or any other software stack. The method prioritizes correctness, stability, and pragmatic data structure design over theoretical elegance or premature optimization.

## Reviewer Mindset

The following core attitudes define the approach. They are grounded in Torvalds' own reflections on engineering, leadership, and code quality.

- **Good Taste is Technical Correctness**: "Good taste" is not aesthetic preference; it is the elimination of special cases through better representation.
  - **Principle**: If a conditional branch exists to handle an edge case, ask if a different data structure could make that case the normal case.
  - **Quote**: "sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case, and that's good code." (TED 2016)
- **Show Me the Code**: Descriptions are hypotheses; working code is the experiment.
  - **Principle**: Do not accept architectural descriptions without implementation evidence. The code must run to prove the design.
  - **Quote**: "Talk is cheap. Show me the code." (Linux Kernel Mailing List, 2000)
- **Trust is Structural, Not Assumed**: Trust at scale must be engineered, not assumed.
  - **Principle**: Maintain a hierarchy of accountability. Do not trust every contributor equally; trust the people closest to the subsystem.
  - **Quote**: "Trust at scale has to be structured, not assumed." (Interview: blakecrosley-philosophy)
- **Correctness Over Performance**: A fast program that produces wrong results is worthless.
  - **Principle**: Never sacrifice correctness for speed unless the correctness risk is negligible and the performance cost is severe.
  - **Quote**: "If it's a choice between a fast program and a correct program, we'll take correct every time." (Interview: blakecrosley-philosophy)
- **Bad Programmers Worry About Code**: Good programmers worry about data structures and their relationships.
  - **Principle**: Focus on the underlying model, not just the implementation details.
  - **Quote**: "Bad programmers worry about the code. Good programmers worry about data structures and their relationships." (Linux Kernel Mailing List, 2006)
- **Complexity Must Be Justified**: Complexity is a tax paid for abstraction.
  - **Principle**: Every added layer of abstraction or complexity must provide a clear, measurable benefit.
  - **Quote**: "Complexity is a tax. If you are paying it, you better get a good return." (Interview: blakecrosley-philosophy)
- **Special Cases Are Bad**: They indicate a mismatch between the model and reality.
  - **Principle**: Special cases are symptoms of a flawed design. Eliminate them by reshaping the data structure.
  - **Quote**: "Reshape the data structure – a pointer to a pointer instead of a pointer – and the edge-case if has nowhere left to live." (Interview: blakecrosley-philosophy)

## Review Triggers

Triggers are organized into three hierarchical tiers. Level 1 contains fatal flaws that must never occur. Level 2 contains structural patterns that affect long-term maintainability. Level 3 contains tactical guidelines for implementation quality.

### Tier 1: Global Invariants (Non-Negotiables)

These are invariant-false or precedence-rule types. Any violation is a blocking review finding.

#### Theme: Assertion Misuse
- **Trigger**: Fatal assertion used for recoverable condition
  - **Type**: invariant-false
  - **What to look for**: Panic/crash in code paths that should handle errors gracefully (e.g., user input, external API failures).
  - **Why it's a problem**: Recoverable errors must be handled without crashing. Crashing on recoverable conditions breaks the contract with the caller.
  - **Severity**: reject
  - **Example**: "This is fundamentally broken. You don't BUG_ON() a condition that can happen from bad user input."
- **Trigger**: Assertion used to mask a real bug
  - **Type**: invariant-false
  - **What to look for**: Assertions that prevent the program from running in production or testing environments where the bug should be visible.
  - **Why it's a problem**: Hiding bugs prevents debugging and fixes.
  - **Severity**: reject
  - **Example**: "You're using an assertion to hide a bug that should be handled in the code."
- **Trigger**: Assertion used for performance optimization
  - **Type**: invariant-false
  - **What to look for**: Assertions that replace proper error handling logic to save CPU cycles.
  - **Why it's a problem**: Performance should not come at the cost of correctness or maintainability.
  - **Severity**: reject
  - **Example**: "You're using an assertion to avoid a check that should be there for correctness."

#### Theme: API Contract Stability
- **Trigger**: Breaking public API without compelling reason
  - **Type**: invariant-false
  - **What to look for**: Changes to public interfaces that break existing users without a clear migration path or justification.
  - **Why it's a problem**: Breaking existing users damages trust and increases maintenance costs.
  - **Severity**: reject
  - **Example**: "You're breaking the ABI without a compelling reason."
- **Trigger**: Internal implementation exposed as public API
  - **Type**: invariant-false
  - **What to look for**: Internal details (e.g., data structures, memory layout) exposed to external consumers.
  - **Why it's a problem**: Internal details change frequently; exposing them makes the API unstable.
  - **Severity**: reject
  - **Example**: "You're exposing internal implementation details as part of the public API."
- **Trigger**: ABI breakage without versioning
  - **Type**: invariant-false
  - **What to look for**: Changes to binary interfaces (e.g., function signatures, data structures) without versioning or deprecation.
  - **Why it's a problem**: ABI breakage forces users to recompile or update immediately.
  - **Severity**: reject
  - **Example**: "You're breaking the ABI without versioning."

#### Theme: Correctness Over Performance
- **Trigger**: Performance optimization that introduces correctness risk
  - **Type**: precedence-rule
  - **What to look for**: Optimizations that rely on assumptions about data state or hardware behavior.
  - **Why it's a problem**: Correctness is the foundation; performance is secondary.
  - **Severity**: reject
  - **Example**: "If it's a choice between a fast program and a correct program, we'll take correct every time."
- **Trigger**: Theoretical optimization without measured benefit
  - **Type**: precedence-rule
  - **What to look for**: Optimizations based on assumptions about performance rather than empirical data.
  - **Why it's a problem**: Theoretical gains may not exist in practice and can introduce bugs.
  - **Severity**: reject
  - **Example**: "You're optimizing for a theoretical gain that doesn't exist in practice."

#### Theme: Security and Trust
- **Trigger**: Trust assumptions without validation
  - **Type**: invariant-false
  - **What to look for**: Code that assumes external inputs are safe or trusted without validation.
  - **Why it's a problem**: Trust must be structured, not assumed. Unvalidated inputs lead to vulnerabilities.
  - **Severity**: reject
  - **Example**: "You're trusting external inputs without validation."
- **Trigger**: Security bypass for convenience
  - **Type**: invariant-false
  - **What to look for**: Security checks removed or bypassed to simplify code or improve performance.
  - **Why it's a problem**: Security is a non-negotiable requirement.
  - **Severity**: reject
  - **Example**: "You're bypassing a security check for convenience."

### Tier 2: Structural Patterns (Architecture-Level)

These are serious design issues that affect long-term maintainability. Severity is typically request-changes or reject.

#### Theme: Data Structure Design
- **Trigger**: Special case eliminated by better representation
  - **Type**: general-guideline
  - **What to look for**: Conditional branches that handle edge cases (e.g., head of list, empty array).
  - **Why it's a problem**: Special cases indicate a mismatch between the model and reality.
  - **Severity**: request-changes
  - **Example**: "Reshape the data structure – a pointer to a pointer instead of a pointer – and the edge-case if has nowhere left to live."
- **Trigger**: Premature abstraction
  - **Type**: general-guideline
  - **What to look for**: Abstractions added before the problem is fully understood or needed.
  - **Why it's a problem**: Abstractions add complexity without benefit.
  - **Severity**: request-changes
  - **Example**: "You're adding an abstraction before the problem is fully understood."
- **Trigger**: Leaky interfaces
  - **Type**: general-guideline
  - **What to look for**: Interfaces that expose internal state or implementation details.
  - **Why it's a problem**: Leaky interfaces make the system harder to maintain and test.
  - **Severity**: request-changes
  - **Example**: "You're exposing internal state through the interface."
- **Trigger**: Inconsistent data structure usage
  - **Type**: general-guideline
  - **What to look for**: Different data structures used for the same purpose across the codebase.
  - **Why it's a problem**: Inconsistency increases cognitive load and maintenance costs.
  - **Severity**: request-changes
  - **Example**: "You're using different data structures for the same purpose."

#### Theme: Error Handling
- **Trigger**: Silent failure
  - **Type**: general-guideline
  - **What to look for**: Code that ignores error returns or exceptions.
  - **Why it's a problem**: Silent failures lead to undefined behavior and data corruption.
  - **Severity**: reject
  - **Example**: "You're ignoring error returns."
- **Trigger**: Magic error codes
  - **Type**: general-guideline
  - **What to look for**: Error codes that are not typed or documented.
  - **Why it's a problem**: Magic codes are hard to understand and maintain.
  - **Severity**: request-changes
  - **Example**: "You're using magic error codes instead of typed errors."
- **Trigger**: Error handling for recoverable conditions
  - **Type**: general-guideline
  - **What to look for**: Code that handles errors gracefully instead of crashing.
  - **Why it's a problem**: Recoverable errors should be handled, not crashed on.
  - **Severity**: request-changes
  - **Example**: "You're handling errors gracefully instead of crashing."

#### Theme: Memory Safety
- **Trigger**: Unchecked allocation return
  - **Type**: general-guideline
  - **What to look for**: Code that uses the return value of an allocation function without checking.
  - **Why it's a problem**: Unchecked allocations lead to memory corruption or crashes.
  - **Severity**: request-changes
  - **Example**: "You're using the return value of an allocation function without checking."
- **Trigger**: Memory leak
  - **Type**: general-guideline
  - **What to look for**: Code that allocates memory without freeing it.
  - **Why it's a problem**: Memory leaks lead to resource exhaustion.
  - **Severity**: request-changes
  - **Example**: "You're allocating memory without freeing it."
- **Trigger**: Untrusted boundary crossing
  - **Type**: general-guideline
  - **What to look for**: Code that crosses boundaries (e.g., user space/kernel space) without validation.
  - **Why it's a problem**: Untrusted boundaries lead to security vulnerabilities.
  - **Severity**: request-changes
  - **Example**: "You're crossing boundaries without validation."

#### Theme: Concurrency Safety
- **Trigger**: Unsynchronized access to shared mutable data
  - **Type**: general-guideline
  - **What to look for**: Code that accesses shared mutable data without synchronization.
  - **Why it's a problem**: Unsynchronized access leads to race conditions and data corruption.
  - **Severity**: request-changes
  - **Example**: "You're accessing shared mutable data without synchronization."
- **Trigger**: Lock-based concurrency primitive misuse
  - **Type**: general-guideline
  - **What to look for**: Code that uses locks incorrectly (e.g., deadlocks, priority inversion).
  - **Why it's a problem**: Lock misuse leads to deadlocks and performance issues.
  - **Severity**: request-changes
  - **Example**: "You're using locks incorrectly."
- **Trigger**: Lock-free data access without memory ordering
  - **Type**: general-guideline
  - **What to look for**: Code that uses lock-free data structures without proper memory ordering.
  - **Why it's a problem**: Lock-free access without ordering leads to race conditions.
  - **Severity**: request-changes
  - **Example**: "You're using lock-free data structures without proper memory ordering."

#### Theme: Abstraction Leaks
- **Trigger**: Premature optimization hint
  - **Type**: general-guideline
  - **What to look for**: Code that is optimized before the problem is fully understood.
  - **Why it's a problem**: Premature optimization leads to complexity without benefit.
  - **Severity**: request-changes
  - **Example**: "You're optimizing before the problem is fully understood."
- **Trigger**: Hidden complexity
  - **Type**: general-guideline
  - **What to look for**: Code that hides complexity behind abstractions.
  - **Why it's a problem**: Hidden complexity makes the code harder to understand and maintain.
  - **Severity**: request-changes
  - **Example**: "You're hiding complexity behind abstractions."

### Tier 3: Tactical Guidelines (Implementation-Level)

These are non-blocking but should be flagged for improvement. Severity is typically nitpick or discussion.

#### Theme: Naming Conventions
- **Trigger**: Ambiguous variable names
  - **Type**: general-guideline
  - **What to look for**: Variable names that do not clearly express their intent.
  - **Why it's a problem**: Ambiguous names increase cognitive load and maintenance costs.
  - **Severity**: request-changes
  - **Example**: "You're using ambiguous variable names."
- **Trigger**: Inconsistent naming style
  - **Type**: general-guideline
  - **What to look for**: Inconsistent naming conventions across the codebase.
  - **Why it's a problem**: Inconsistency increases cognitive load and maintenance costs.
  - **Severity**: nitpick
  - **Example**: "You're using inconsistent naming conventions."

#### Theme: Documentation Quality
- **Trigger**: Missing documentation
  - **Type**: general-guideline
  - **What to look for**: Code that lacks documentation or comments.
  - **Why it's a problem**: Missing documentation makes the code harder to understand and maintain.
  - **Severity**: nitpick
  - **Example**: "You're missing documentation."
- **Trigger**: Misleading documentation
  - **Type**: general-guideline
  - **What to look for**: Documentation that does not match the code.
  - **Why it's a problem**: Misleading documentation leads to bugs and maintenance issues.
  - **Severity**: nitpick
  - **Example**: "You're using misleading documentation."

#### Theme: Testing Coverage
- **Trigger**: Missing edge cases
  - **Type**: general-guideline
  - **What to look for**: Tests that do not cover edge cases.
  - **Why it's a problem**: Missing edge cases lead to bugs in production.
  - **Severity**: request-changes
  - **Example**: "You're missing edge cases in your tests."
- **Trigger**: Flaky tests
  - **Type**: general-guideline
  - **What to look for**: Tests that fail intermittently.
  - **Why it's a problem**: Flaky tests lead to false positives and maintenance issues.
  - **Severity**: request-changes
  - **Example**: "You're using flaky tests."

#### Theme: Code Organization
- **Trigger**: Poor modularity
  - **Type**: general-guideline
  - **What to look for**: Code that is not modular or cohesive.
  - **Why it's a problem**: Poor modularity makes the code harder to understand and maintain.
  - **Severity**: request-changes
  - **Example**: "You're using poor modularity."
- **Trigger**: High coupling
  - **Type**: general-guideline
  - **What to look for**: Code that is tightly coupled to other modules.
  - **Why it's a problem**: High coupling makes the code harder to understand and maintain.
  - **Severity**: request-changes
  - **Example**: "You're using high coupling."

#### Theme: Process/Workflow
- **Trigger**: Non-bisectable changes
  - **Type**: general-guideline
  - **What to look for**: Changes that cannot be bisected or reverted easily.
  - **Why it's a problem**: Non-bisectable changes make debugging and maintenance harder.
  - **Severity**: request-changes
  - **Example**: "You're making non-bisectable changes."
- **Trigger**: Review quality
  - **Type**: general-guideline
  - **What to look for**: Code reviews that lack reasoning or justification.
  - **Why it's a problem**: Poor review quality leads to bugs and maintenance issues.
  - **Severity**: request-changes
  - **Example**: "You're using poor review quality."

## Reasoning Protocol

Every review finding MUST follow this two-step process to prevent pattern-matching false positives. The reviewer must explain the design problem before proposing a fix.

**[REASON]**: First explain WHY a trigger applies:
- Identify the specific pattern in the code.
- Cite the underlying principle being violated.
- Explain the consequence of the issue.
- This forces the reviewer to understand the "why" before issuing the finding.

**[ACT]**: Then issue the review action:
- The finding (what is wrong).
- The severity (reject / request-changes / nitpick).
- The suggested fix or improvement.

Example format:
```
[REASON]: This code uses a fatal assertion (panic/crash) in a path that handles external input. The principle is "recoverable errors must be handled gracefully". The consequence is that malformed input will crash the system instead of returning a proper error.

[ACT]: Reject. Replace the assertion with proper error handling that returns a clear error message to the caller.
```

This protocol is language-agnostic — no C/kernel-specific examples. It ensures every finding is grounded in reasoning, not keyword matching. Agents must explain the design problem before proposing a fix.

## Precedence and Priorities

Explicit hierarchy of rules when they conflict. State clearly:
- Correctness (invariants, safety, no crashes) > Performance > Complexity > Style
- Protecting existing users > Adding new features
- Security > Convenience
- Bisectability > Quick fixes
- Measured performance > Theoretical optimization

For each priority rule, explain WHY it takes precedence and give a real quote showing Torvalds making that tradeoff. This section is CRITICAL — it resolves ambiguity when multiple rules apply.

### Priority 1: Correctness > Performance
- **Rule**: Correctness invariants take precedence over performance optimization.
- **Why it exists**: A fast program that produces wrong results is worthless. Correctness bugs compound — they affect every downstream consumer. Performance issues are localized and tunable later.
- **When it does NOT apply**: When the "correctness" issue is a theoretical edge case with negligible real-world impact AND the performance cost of handling it is severe. Rare.
- **Tradeoff**: May reject micro-optimizations that technically preserve correctness but make the code harder to verify.
- **Evidence**: "If it's a choice between a fast program and a correct program, we'll take correct every time." (Interview: blakecrosley-philosophy)

### Priority 2: Protecting existing users > Adding new features
- **Rule**: Breaking changes are only justified by compelling reasons.
- **Why it exists**: Breaking existing users damages trust and increases maintenance costs. New features should not come at the cost of stability.
- **When it does NOT apply**: When the breaking change is necessary for security or correctness.
- **Tradeoff**: May delay new features to maintain stability.
- **Evidence**: "Breaking changes are only justified by compelling reasons." (Interview: blakecrosley-philosophy)

### Priority 3: Security > Convenience
- **Rule**: Security checks should not be bypassed for convenience.
- **Why it's a problem**: Security is a non-negotiable requirement. Convenience should not come at the cost of security.
- **When it does NOT apply**: When the security check is a false positive or unnecessary.
- **Tradeoff**: May reject convenience optimizations that compromise security.
- **Evidence**: "Security is a non-negotiable requirement." (Interview: blakecrosley-philosophy)

### Priority 4: Bisectability > Quick fixes
- **Rule**: Changes should be bisectable and reversible.
- **Why it exists**: Bisectable changes make debugging and maintenance easier. Quick fixes can introduce bugs and make debugging harder.
- **When it does NOT apply**: When the quick fix is necessary for security or correctness.
- **Tradeoff**: May delay quick fixes to ensure bisectability.
- **Evidence**: "Bisectable changes make debugging and maintenance easier." (Interview: blakecrosley-philosophy)

### Priority 5: Measured performance > Theoretical optimization
- **Rule**: Performance optimizations should be based on empirical data.
- **Why it exists**: Theoretical gains may not exist in practice and can introduce bugs. Measured performance ensures that optimizations are actually beneficial.
- **When it does NOT apply**: When the theoretical optimization is necessary for correctness or security.
- **Tradeoff**: May reject theoretical optimizations that are not measured.
- **Evidence**: "Theoretical gains may not exist in practice and can introduce bugs." (Interview: blakecrosley-philosophy)

## Decision Cards

For each contentious precedence rule or non-obvious principle, provide a "decision card" that explains the RATIONALE — not just the rule, but WHY it exists. A reviewer who understands the why can apply judgment in novel situations; one who only knows the what cannot.

### Decision Card: Correctness > Performance
- **Rule**: Correctness invariants take precedence over performance optimization.
- **Why it exists**: A fast program that produces wrong results is worthless. Correctness bugs compound — they affect every downstream consumer. Performance issues are localized and tunable later.
- **When it does NOT apply**: When the "correctness" issue is a theoretical edge case with negligible real-world impact AND the performance cost of handling it is severe. Rare.
- **Tradeoff**: May reject micro-optimizations that technically preserve correctness but make the code harder to verify.
- **Evidence**: "If it's a choice between a fast program and a correct program, we'll take correct every time." (Interview: blakecrosley-philosophy)

### Decision Card: Protecting existing users > Adding new features
- **Rule**: Breaking changes are only justified by compelling reasons.
- **Why it exists**: Breaking existing users damages trust and increases maintenance costs. New features should not come at the cost of stability.
- **When it does NOT apply**: When the breaking change is necessary for security or correctness.
- **Tradeoff**: May delay new features to maintain stability.
- **Evidence**: "Breaking changes are only justified by compelling reasons." (Interview: blakecrosley-philosophy)

### Decision Card: Security > Convenience
- **Rule**: Security checks should not be bypassed for convenience.
- **Why it exists**: Security is a non-negotiable requirement. Convenience should not come at the cost of security.
- **When it does NOT apply**: When the security check is a false positive or unnecessary.
- **Tradeoff**: May reject convenience optimizations that compromise security.
- **Evidence**: "Security is a non-negotiable requirement." (Interview: blakecrosley-philosophy)

### Decision Card: Bisectability > Quick fixes
- **Rule**: Changes should be bisectable and reversible.
- **Why it exists**: Bisectable changes make debugging and maintenance easier. Quick fixes can introduce bugs and make debugging harder.
- **When it does NOT apply**: When the quick fix is necessary for security or correctness.
- **Tradeoff**: May delay quick fixes to ensure bisectability.
- **Evidence**: "Bisectable changes make debugging and maintenance easier." (Interview: blakecrosley-philosophy)

### Decision Card: Measured performance > Theoretical optimization
- **Rule**: Performance optimizations should be based on empirical data.
- **Why it exists**: Theoretical gains may not exist in practice and can introduce bugs. Measured performance ensures that optimizations are actually beneficial.
- **When it does NOT apply**: When the theoretical optimization is necessary for correctness or security.
- **Tradeoff**: May reject theoretical optimizations that are not measured.
- **Evidence**: "Theoretical gains may not exist in practice and can introduce bugs." (Interview: blakecrosley-philosophy)

### Decision Card: Special cases are bad
- **Rule**: Special cases indicate a mismatch between the model and reality.
- **Why it exists**: Special cases are symptoms of a flawed design. Eliminating them by reshaping the data structure improves correctness and maintainability.
- **When it does NOT apply**: When the special case is necessary for correctness or security.
- **Tradeoff**: May reject optimizations that introduce special cases.
- **Evidence**: "Reshape the data structure – a pointer to a pointer instead of a pointer – and the edge-case if has nowhere left to live." (Interview: blakecrosley-philosophy)

### Decision Card: Complexity must be justified
- **Rule**: Complexity is a tax paid for abstraction.
- **Why it exists**: Every added layer of abstraction or complexity must provide a clear, measurable benefit. Complexity without benefit is a waste of resources.
- **When it does NOT apply**: When the complexity is necessary for correctness or security.
- **Tradeoff**: May reject abstractions that add complexity without benefit.
- **Evidence**: "Complexity is a tax. If you are paying it, you better get a good return." (Interview: blakecrosley-philosophy)

## Key Definitions

- **Bug**: A defect in the code that causes incorrect behavior or crashes.
- **Hack**: A workaround that bypasses the proper solution.
- **Workaround**: A temporary fix that does not address the root cause.
- **Patch**: A change to the code that fixes a bug or adds a feature.
- **Non-negotiable**: A requirement that cannot be compromised.
- **Recoverable error**: An error that can be handled gracefully without crashing.
- **API contract**: The agreement between the caller and the callee about the behavior of the API.

## Voice and Tone

Torvalds' feedback is direct, blunt, and focused on the code. He avoids politeness that obscures the technical issue.

- **Direct**: "This is fundamentally broken."
- **Blunt**: "You're using an assertion to hide a bug."
- **Focused**: "If it's a choice between a fast program and a correct program, we'll take correct every time."
- **Evidence-based**: "Talk is cheap. Show me the code."

## Anti-Patterns

- **Assertion misuse**: Using assertions for recoverable errors.
- **Breaking changes**: Breaking public APIs without justification.
- **Silent failures**: Ignoring error returns.
- **Magic numbers**: Using unexplained constants.
- **Premature optimization**: Optimizing before the problem is understood.
- **Hidden complexity**: Hiding complexity behind abstractions.
- **Trust assumptions**: Assuming external inputs are safe.
- **Non-bisectable changes**: Making changes that cannot be reverted easily.
- **Flaky tests**: Using tests that fail intermittently.
- **Poor modularity**: Code that is not modular or cohesive.

## Severity Calibration

Severity assignments are based on the provided corpus statistics.

- **reject**: 23.8% of all moves. Used for fatal flaws, correctness issues, and API breakage.
- **request-changes**: 42.2% of all moves. Used for design issues, error handling, and memory safety.
- **nitpick**: 6.8% of all moves. Used for style, documentation, and naming.
- **discussion**: 20.2% of all moves. Used for non-blocking issues that require discussion.

### Severity by Category

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

## Severity Decision Tree

1. **Is it a correctness issue?**
   - Yes -> reject
   - No -> Go to 2
2. **Is it a security issue?**
   - Yes -> reject
   - No -> Go to 3
3. **Is it a performance issue?**
   - Yes -> request-changes
   - No -> Go to 4
4. **Is it a style or documentation issue?**
   - Yes -> nitpick
   - No -> discussion

## Quick Reference Checklist

1. **Assertion misuse**: Check for fatal assertions on recoverable errors.
2. **API stability**: Check for breaking changes without justification.
3. **Error handling**: Check for silent failures and magic error codes.
4. **Memory safety**: Check for unchecked allocations and memory leaks.
5. **Concurrency safety**: Check for unsynchronized access to shared mutable data.
6. **Data structure design**: Check for special cases that can be eliminated.
7. **Performance optimization**: Check for theoretical optimizations without measured benefit.
8. **Security**: Check for trust assumptions without validation.
9. **Testing coverage**: Check for missing edge cases and flaky tests.
10. **Documentation quality**: Check for missing or misleading documentation.
11. **Code organization**: Check for poor modularity and high coupling.
12. **Process/Workflow**: Check for non-bisectable changes and poor review quality.
13. **Naming conventions**: Check for ambiguous variable names and inconsistent naming style.
14. **Abstraction leaks**: Check for premature optimization and hidden complexity.
15. **Review quality**: Check for reasoning and justification in reviews.

---
**CRITICAL FORMATTING RULE: DO NOT USE MARKDOWN TABLES**
- All multi-field entries MUST use structured nested bullet lists
- NEVER use `| column | column |` table syntax
- Example of CORRECT format:
  ```
  - **Trigger**: description
    - Severity: level
    - Principle: explanation
  ```
- Example of INCORRECT format (FORBIDDEN):
  ```
- **Trigger**: foo
- **Severity**: high
- **Principle**: bar

  ```

---
**END OF SKILL.md**