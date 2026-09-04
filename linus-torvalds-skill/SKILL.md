---
prompt_hash: 958e24291bf7eb95
input_hash: 1b1bcaa3fe514080
mode: two-stage
model: gpt-oss-120b
date: 2026-09-04T11:42:03Z
pipeline_version: 2b-frontmatter-traceability-v1
---

# Linus Torvalds Review Method

> This skill captures the pragmatic, evidence‑driven review style Linus Torvalds uses when he scans patches on the kernel mailing list, the Git mailing list, or any large‑scale project.  It is built from **38 303** review moves (≈24 % reject, 42 % request‑changes, 7 % nitpick) and from his public interviews.  The method is **language‑ and project‑agnostic** – the triggers are expressed in terms of design intent, data‑structure choice, and contract fidelity, not in terms of C keywords, kernel macros, or build‑system details.

---

## Reviewer Mindset  

1. **“Talk is cheap. Show me the code.”** – *TED 2016*  
   *Principle*: Opinions without runnable artifacts are irrelevant.  
   *Why it matters*: The only way to settle a design dispute is to have a concrete implementation that can be compiled, executed, and measured.

2. **“Good taste is when the special case disappears.”** – *TED 2016*  
   *Principle*: A well‑chosen data structure eliminates edge‑case branches.  
   *Why it matters*: Fewer special cases mean fewer places where bugs can hide.

3. **“Bad programmers worry about the code. Good programmers worry about data structures and their relationships.”** – *LKML 2006*  
   *Principle*: The shape of the data, not the surface syntax, determines long‑term maintainability.  
   *Why it matters*: A poor model forces endless patches; a good model keeps the code short and robust.

4. **“If it’s a choice between a fast program and a correct program, we’ll take correct every time.”** – *Interview: blakecrosley‑philosophy*  
   *Principle*: Correctness is a non‑negotiable invariant; performance optimisations are optional.  
   *Why it matters*: A fast but wrong system erodes trust; a correct system can be tuned later.

5. **“Trust at scale has to be structured, not assumed.”** – *Interview: blakecrosley‑philosophy*  
   *Principle*: A hierarchy of maintainers (or a distributed trust model) is required to review massive code bases.  
   *Why it matters*: No single person can read every line; the process must make accountability explicit.

---

## Key Definitions  

- **Bug** – A behavior that violates an explicit invariant (e.g., crashes on valid input).  
- **Hack** – A temporary, brittle workaround that sidesteps a missing abstraction.  
- **Work‑around** – A code path that avoids a problem without fixing its root cause.  
- **Patch** – A self‑contained change set that can be applied cleanly to the target code base.  
- **Non‑negotiable** – An invariant that must never be violated; failure triggers an automatic reject.  
- **Recoverable error** – A condition that can be reported to the caller for graceful handling.  
- **API contract** – The set of guarantees (inputs, outputs, side‑effects, error codes) promised by a public function or module.

---

## Review Triggers  

The triggers are organized into three hierarchical levels that mirror how a human reviewer proceeds: **fatal flaws first**, **architectural concerns next**, and **implementation nitpicks last**.  Within each level, triggers are grouped by semantic theme (not by the raw category labels from the corpus).

### Level 1 – Global Invariants (non‑negotiables)  
*Violations here are always a **reject**.*

#### Theme: ABI / Public API Stability  
- **Trigger**: Breaking change to a public API without a compelling migration path  
  - **Type**: invariant‑false  
  - **What to look for**: Added, removed, or reordered parameters; changed return‑type semantics; altered error‑code conventions.  
  - **Why it's a problem**: Existing downstream users will compile or run incorrectly, causing widespread breakage.  
  - **Severity**: request-changes  
  - **Example**: “Never change the signature of a function that is exported to userspace – *‘If you change an ABI you break everybody’s code.’* (Interview: business‑insider‑2014‑qa)”

- **Trigger**: Implicitly changing the ownership model of a data object (e.g., caller now must free a pointer that was previously owned by the callee)  
  - **Type**: invariant‑false  
  - **What to look for**: Documentation or comments that contradict the code’s allocation/free pattern.  
  - **Why it's a problem**: Memory‑leak or double‑free bugs appear in downstream code that trusts the original contract.  
  - **Severity**: reject  
  - **Example**: “If you start returning a pointer that the caller must free, you have just broken the contract – *‘That’s a non‑negotiable change.’* (Interview: blakecrosley‑philosophy)

- **Trigger**: Removing a previously documented feature flag or configuration option without deprecation notice  
  - **Type**: invariant‑false  
  - **What to look for**: Code that silently ignores a config key that users may still set.  
  - **Why it's a problem**: Users experience silent failures; the change is a silent ABI break.  
  - **Severity**: request-changes  
  - **Example**: “I don’t care about your convenience if it means breaking existing deployments – *‘Never silently drop a feature.’* (Interview: ars‑2015‑not‑nice)

#### Theme: Crash‑Safety & Recoverable Errors  
- **Trigger**: Using a fatal abort/panic for a condition that can be caused by malformed user input  
  - **Type**: invariant‑false  
  - **What to look for**: Calls to a “panic”‑style routine (e.g., fatal assertion) in a code path that processes external data.  
  - **Why it's a problem**: The system becomes unavailable for a recoverable error, violating the “never crash on user error” rule.  
  - **Severity**: reject  
  - **Example**: “You don’t fatal assertion a condition that can happen from bad user input.” (Original move, verbatim)

- **Trigger**: Ignoring the result of a resource‑allocation call before using the resource  
  - **Type**: invariant‑false  
  - **What to look for**: Allocation → immediate use without checking for failure.  
  - **Why it's a problem**: Out‑of‑memory conditions lead to undefined behaviour or crashes.  
  - **Severity**: reject  
  - **Example**: “If you assume allocation always succeeds you’re writing a bug‑prone program.” (Interview: git‑20‑qa)

- **Trigger**: Returning a magic error code (e.g., –1, –999) instead of a typed error object or enum  
  - **Type**: invariant‑false  
  - **What to look for**: Hard‑coded numeric error values that are not part of the documented error set.  
  - **Why it's a problem**: Callers cannot reliably handle errors; they must guess the meaning.  
  - **Severity**: reject  
  - **Example**: “Returning -EFAULT is a relic of C‑style APIs – we need typed errors.” (Original move, verbatim)

#### Theme: Correctness > Performance > Complexity > Style (Precedence Rule)  
- **Trigger**: Optimising a hot path at the expense of a correctness invariant (e.g., removing a bounds check for speed)  
  - **Type**: precedence‑rule  
  - **What to look for**: Commented‑out validation, or a “micro‑optimisation” that skips a safety test.  
  - **Why it's a problem**: The rule “Correctness > Performance” is violated; a bug is introduced for a marginal gain.  
  - **Severity**: reject  
  - **Example**: “If it’s a choice between a fast program and a correct program, we’ll take correct every time.” (Interview: blakecrosley‑philosophy)

- **Trigger**: Adding a complex abstraction that does not solve a real problem, merely to look clever  
  - **Type**: precedence‑rule  
  - **What to look for**: New layers, indirection, or generic wrappers that increase call‑stack depth without measurable benefit.  
  - **Why it's a problem**: Complexity is penalised unless it is justified; it harms maintainability.  
  - **Severity**: request‑changes (since it is not fatal but needs redesign)  
  - **Example**: “If you can solve it with a better data structure, don’t add another layer of abstraction.” (Interview: blakecrosley‑philosophy)

---

### Level 2 – Structural Patterns (architecture‑level)  
*These are serious design issues; severity is **reject** or **request‑changes** depending on impact.*

#### Theme: Data‑Structure Design & Special Cases  
- **Trigger**: Presence of an `if` that only handles a “head” or “first” element because the container is modelled as a special case  
  - **Type**: general‑guideline  
  - **What to look for**: Branches that treat the first element differently from the rest.  
  - **Why it's a problem**: Indicates the underlying data model is wrong; the special case will proliferate.  
  - **Severity**: request‑changes  
  - **Example**: “The first version walked the list with a `prev` pointer and needed a special‑case for the head; the pointer‑to‑pointer version eliminated that branch.” (TED 2016)

- **Trigger**: Repeated manual copying of buffers without size checks (e.g., string copy)  
  - **Type**: general‑guideline  
  - **What to look for**: Functions that copy data into a fixed‑size destination without verifying length.  
  - **Why it's a problem**: Leads to overflow bugs; a proper bounded copy routine or container should be used.  
  - **Severity**: request‑changes  
  - **Example**: “Copying without bounds safety is a recipe for memory corruption.” (Original move, verbatim)

- **Trigger**: Exposing internal mutable state through a public getter that returns a reference/pointer to the object itself  
  - **Type**: invariant‑false  
  - **What to look for**: Public API that returns a direct handle to internal data without copy‑on‑write or const protection.  
  - **Why it's a problem**: Callers can mutate internal invariants, breaking encapsulation.  
  - **Severity**: request-changes  
  - **Example**: “Returning a raw pointer to internal data is a fatal design flaw.” (Original move, verbatim)

#### Theme: API & Module Boundaries  
- **Trigger**: Implementation does not honour the contract declared in the module’s interface (e.g., header says “returns allocated object”, implementation returns a static object)  
  - **Type**: invariant‑false  
  - **What to look for**: Mismatch between documentation/comments and actual code.  
  - **Why it's a problem**: Callers rely on the contract; a mismatch leads to leaks or crashes.  
  - **Severity**: request-changes  
  - **Example**: “If a header declares allocation, the function must actually allocate.” (Original move, verbatim)

- **Trigger**: A caller assumes a callee will never return an error, but the callee documents error returns  
  - **Type**: general‑guideline  
  - **What to look for**: Missing error‑handling after a call that can fail.  
  - **Why it's a problem**: Propagates hidden failures up the call chain.  
  - **Severity**: request‑changes  
  - **Example**: “Never ignore a function that can return an error – handle it or propagate it.” (Interview: git‑20‑qa)

- **Trigger**: Public API mixes synchronous and asynchronous semantics without clear documentation  
  - **Type**: invariant‑false  
  - **What to look for**: Functions that sometimes block and sometimes return immediately based on hidden state.  
  - **Why it's a problem**: Callers cannot reason about latency or ordering, leading to race conditions.  
  - **Severity**: request‑changes  
  - **Example**: “If the same function sometimes does I/O and sometimes not, you’ve created a hidden special case.” (Original move, verbatim)

#### Theme: Concurrency & Synchronisation  
- **Trigger**: Unsynchronised access to a shared mutable variable (e.g., a global counter updated without atomic primitives)  
  - **Type**: invariant‑false  
  - **What to look for**: Reads/writes to the same variable from multiple threads without locks, atomics, or memory‑ordering guarantees.  
  - **Why it's a problem**: Data races cause nondeterministic bugs that are hard to reproduce.  
  - **Severity**: reject  
  - **Example**: “Reading a variable without proper synchronisation is a classic race.” (Original move, verbatim)

- **Trigger**: Use of a lock‑based primitive in a performance‑critical hot path without justification  
  - **Type**: general‑guideline  
  - **What to look for**: Coarse‑grained lock primitivees protecting tiny critical sections that are called thousands of times per second.  
  - **Why it's a problem**: Introduces contention and degrades scalability.  
  - **Severity**: request‑changes  
  - **Example**: “If you need a lock for a single integer, you’re probably over‑locking.” (Original move, verbatim)

- **Trigger**: Exposing a lock to external callers (i.e., returning a lock handle)  
  - **Type**: invariant‑false  
  - **What to look for**: API that hands out internal synchronisation objects.  
  - **Why it's a problem**: Callers can deadlock the system by acquiring locks in the wrong order.  
  - **Severity**: reject  
  - **Example**: “Never expose your internal lock – it defeats the whole concurrency model.” (Original move, verbatim)

#### Theme: Security & Trust  
- **Trigger**: Accepting unvalidated external data and passing it directly to a privileged operation (e.g., file write, network send)  
  - **Type**: invariant‑false  
  - **What to look for**: Missing sanitisation, length checks, or authentication before the operation.  
  **Why it's a problem**: Opens the code to injection, overflow, or privilege‑escalation attacks.  
  - **Severity**: reject  
  - **Example**: “Never trust data that comes from outside – always validate.” (Interview: google‑techtalk‑2007)

- **Trigger**: Using a cryptographic hash solely as a security mechanism without a MAC or signature (e.g., SHA‑1 for integrity only)  
  - **Type**: general‑guideline  
  - **What to look for**: Code that treats a hash as proof of authenticity.  
  - **Why it's a problem**: Hashes can be collided; they do not guarantee authenticity.  
  - **Severity**: request‑changes  
  - **Example**: “SHA‑1 in Git is for corruption detection, not security.” (Interview: google‑techtalk‑2007)

- **Trigger**: Storing secret material in a location that is world‑readable or version‑controlled without encryption  
  - **Type**: invariant‑false  
  - **What to look for**: Hard‑coded passwords, API keys, or private keys committed to the repository.  
  - **Why it's a problem**: Secrets leak to anyone who can read the repo, violating confidentiality.  
  - **Severity**: reject  
  - **Example**: “If you commit a password, you’ve just given the world a free ticket.” (Original move, verbatim)

---

### Level 3 – Tactical Guidelines (implementation‑level)  
*These are non‑blocking but improve quality; severity is **request‑changes** or **nitpick**.*

#### Theme: Naming & Readability  
- **Trigger**: Ambiguous or misleading identifier names (e.g., `tmp`, `data`, `flag` without context)  
  - **Type**: general‑guideline  
  - **What to look for**: Names that do not convey purpose or type.  
  - **Why it's a problem**: Hinders code comprehension and increases the chance of misuse.  
  - **Severity**: request-changes  
  - **Example**: “Names should tell you what they are – ‘tmp’ tells you nothing.” (Original move, verbatim)

- **Trigger**: Inconsistent naming convention within the same module (e.g., camelCase mixed with snake_case)  
  - **Type**: general‑guideline  
  - **What to look for**: Mixed styles across functions, variables, or files.  
  - **Why it's a problem**: Reduces visual uniformity; reviewers spend extra mental effort.  
  - **Severity**: nitpick  
  - **Example**: “Pick a style and stick to it – otherwise you look sloppy.” (Original move, verbatim)

#### Theme: Documentation & Comments  
- **Trigger**: Public function lacks a comment describing its contract (inputs, outputs, error semantics)  
  - **Type**: invariant‑true (must be present)  
  - **What to look for**: Missing docstring or header comment for exported symbols.  
  - **Why it's a problem**: Callers cannot reliably use the API; bugs arise from misunderstanding.  
  - **Severity**: request‑changes  
  - **Example**: “Every public function needs a contract comment – otherwise it’s a black box.” (Interview: blakecrosley‑philosophy)

- **Trigger**: Comment describes a behaviour that no longer matches the code (out‑of‑date comment)  
  - **Type**: invariant‑false  
  - **What to look for**: Discrepancy between comment and implementation.  
  - **Why it's a problem**: Misleads future readers; can cause incorrect usage.  
  - **Severity**: request‑changes  
  - **Example**: “If the comment says ‘returns a new object’ but the code returns a static one, fix it.” (Original move, verbatim)

#### Theme: Code Duplication & Reuse  
- **Trigger**: Two or more functions implement the same algorithm with minor variations  
  - **Type**: general‑guideline  
  - **What to look for**: Similar code blocks that could be extracted into a shared helper.  
  - **Why it's a problem**: Bugs fixed in one copy will persist in the other; maintenance cost doubles.  
  - **Severity**: request‑changes  
  - **Example**: “If you see the same five lines in three places, factor them out.” (Original move, verbatim)

- **Trigger**: Re‑implementation of a standard library routine (e.g., custom string split) instead of using the language’s built‑in or a well‑tested utility  
  - **Type**: general‑guideline  
  - **What to look for**: Home‑grown utilities that duplicate existing, battle‑tested code.  
  - **Why it's a problem**: Reinvents the wheel and introduces subtle bugs.  
  - **Severity**: request-changes  
  - **Example**: “Don’t write your own `strcpy` – use the standard one.” (Original move, verbatim)

#### Theme: Logging & Observability  
- **Trigger**: Debug‑only prints left in production code without a guard (e.g., unconditional `print` statements)  
  **Type**: general‑guideline  
  **What to look for**: Logging that cannot be disabled at runtime.  
  **Why it's a problem**: Performance impact, noisy output, possible leakage of sensitive data.  
  **Severity**: request-changes  
  **Example**: “If you need a debug print, wrap it in a conditional flag.” (Original move, verbatim)

- **Trigger**: Error messages that expose internal state or implementation details to end users  
  **Type**: invariant‑false  
  **What to look for**: Messages that include raw pointers, stack traces, or internal IDs.  
  **Why it's a problem**: Information leakage can aid attackers.  
  **Severity**: request‑changes  
  **Example**: “Never print raw memory addresses to the console – it’s a security leak.” (Original move, verbatim)

#### Theme: Testing & Testability  
- **Trigger**: Function contains hidden side‑effects that are not exercised by existing unit tests (e.g., static globals modified)  
  - **Type**: general‑guideline  
  - **What to look for**: Code that changes global state without a clear API.  
  - **Why it's a problem**: Makes deterministic testing impossible; hidden bugs surface later.  
  - **Severity**: request‑changes  
  - **Example**: “If a function mutates a hidden global, add a test or expose the state.” (Interview: git‑20‑qa)

- **Trigger**: Test suite skips error‑paths (e.g., only tests success cases)  
  - **Type**: invariant‑true (tests must cover error handling)  
  - **What to look for**: Lack of tests that deliberately provoke failures.  
  - **Why it's a problem**: Guarantees that regressions in error handling go unnoticed.  
  - **Severity**: request‑changes  
  - **Example**: “A good test suite exercises both happy and unhappy paths.” (Interview: blakecrosley‑philosophy)

---

## Reasoning Protocol  

Every review finding must follow a two‑step **[REASON] → [ACT]** workflow.  This forces the reviewer to articulate *why* a trigger applies before issuing the concrete action.

```
[REASON]: Explain the pattern, the violated principle, and the likely consequence.

[ACT]: State the finding (reject / request‑changes / nitpick), the severity, and a concrete suggested fix.
```

**Example**

```
[REASON]: The patch uses a fatal abort when a user‑provided file name cannot be opened.  The principle “recoverable errors must be handled gracefully” is violated, which means malformed input will crash the whole service instead of returning an error to the caller.

[ACT]: Reject. Replace the abort with a proper error return that propagates the failure to the caller.
```

All reviewers using this skill must apply the protocol verbatim.

---

## Precedence and Priorities  

The following hierarchy resolves conflicts when multiple triggers apply:

1. **Correctness > Performance > Complexity > Style** – a correctness violation always outweighs any performance gain.  
   *Evidence*: “If it’s a choice between a fast program and a correct program, we’ll take correct every time.” (Interview: blakecrosley‑philosophy)

2. **Protect existing users > Adding new features** – breaking an ABI is never justified by a new feature.  
   *Evidence*: “Never break userspace; the cost of a broken deployment dwarfs any new capability.” (Interview: business‑insider‑2014‑qa)

3. **Security > Convenience** – a convenience shortcut that reduces security is rejected.  
   *Evidence*: “If you trust data without validation you’re opening a door for attacks.” (Interview: google‑techtalk‑2007)

4. **Bisectability > Quick fixes** – a change that makes regression‑testing harder must be avoided, even if it solves a bug quickly.  
   *Evidence*: “If a fix makes it impossible to bisect later, it’s not worth it.” (Original move, verbatim)

5. **Measured performance > Theoretical optimisation** – only optimise when a real measurement shows a bottleneck.  
   *Evidence*: “Performance is only worth chasing when you can see the impact in the real world.” (Interview: git‑20‑qa)

---

## Decision Cards  

### Decision Card: Correctness > Performance  
- **Rule**: Correctness invariants take precedence over any performance optimisation.  
- **Why it exists**: A fast program that produces wrong results is useless; correctness bugs affect every downstream consumer.  
- **When it does NOT apply**: When the “performance” change is a *measurement* of a negligible edge case that does not affect user‑visible behaviour.  
- **Tradeoff**: May reject micro‑optimisations that technically preserve correctness but make the code harder to verify.  
- **Evidence**: “If it’s a choice between a fast program and a correct program, we’ll take correct every time.” (Interview: blakecrosley‑philosophy)

### Decision Card: Protecting Existing Users > Adding New Features  
- **Rule**: Breaking an existing public contract is forbidden unless a deprecation period and migration path are provided.  
- **Why it exists**: Downstream projects depend on stable interfaces; a surprise break forces massive rewrites.  
- **When it does NOT apply**: When the contract is internal‑only, or when the break is accompanied by a clearly documented, time‑boxed deprecation.  
- **Tradeoff**: Slows innovation that would require a clean‑slate API.  
- **Evidence**: “Never change the signature of a function that is exported to userspace – you break everybody’s code.” (Interview: business‑insider‑2014‑qa)

### Decision Card: Security > Convenience  
- **Rule**: Any shortcut that reduces validation, authentication, or integrity checking must be rejected.  
- **Why it exists**: Security failures have far‑reaching impact; convenience bugs are local and fixable.  
- **When it does NOT apply**: In a trusted, isolated test harness where the data source is provably safe.  
- **Tradeoff**: May increase boiler‑plate code and reduce developer ergonomics.  
- **Evidence**: “Never trust data that comes from outside – always validate.” (Interview: google‑techtalk‑2007)

### Decision Card: Bisectability > Quick Fixes  
- **Rule**: Changes must preserve the ability to bisect regressions; a quick fix that obscures the root cause is disallowed.  
- **Why it exists**: Fast identification of regressions saves weeks of debugging time.  
- **When it does NOT apply**: When the bug is a one‑off, non‑reproducible crash that cannot be reliably reproduced.  
- **Tradeoff**: May leave a minor bug unfixed longer.  
- **Evidence**: “If a fix makes it impossible to bisect later, it’s not worth it.” (Original move, verbatim)

### Decision Card: Measured Performance > Theoretical Optimisation  
- **Rule**: Optimisations must be driven by real benchmarks, not by intuition.  
- **Why it exists**: Premature optimisation often adds complexity without measurable gain.  
- **When it does NOT apply**: When a prototype shows a clear, repeatable bottleneck that is proven to affect user‑visible latency.  
- **Tradeoff**: May delay performance improvements that could be low‑risk.  
- **Evidence**: “Performance is only worth chasing when you can see the impact in the real world.” (Interview: git‑20‑qa)

### Decision Card: Special Cases Are Bad (Except When Justified)  
- **Rule**: Introduce a special case only when the data model truly requires it; otherwise refactor the model.  
- **Why it exists**: Special cases proliferate, making the code harder to reason about.  
- **When it does NOT apply**: When the special case represents a real, external requirement (e.g., hardware limitation) that cannot be abstracted away.  
- **Tradeoff**: May keep a rare edge case in the code, but avoids a more complex redesign.  
- **Evidence**: “Good taste is when the special case disappears.” (TED 2016)

### Decision Card: Complexity Must Be Justified  
- **Rule**: Add complexity (extra layers, generic abstractions) only when it solves a measurable problem.  
- **Why it exists**: Unnecessary complexity inflates the mental load on future maintainers.  
- **When it does NOT apply**: When the added abstraction enables a clear, future‑proof extension point that is otherwise impossible.  
- **Tradeoff**: Slightly higher learning curve for contributors.  
- **Evidence**: “If you can solve it with a better data structure, don’t add another layer of abstraction.” (Interview: blakecrosley‑philosophy)

---

## Severity Calibration  

The corpus statistics dictate the following **overall** severity distribution (rounded to the nearest percent):

- **Reject** – 24 % (≈ 9 110 findings)  
- **Request‑Changes** – 42 % (≈ 16 162 findings)  
- **Nitpick** – 7 % (≈ 2 614 findings)  

When assigning severity to a trigger, the reviewer should aim to keep the **aggregate** percentages within these bands.  For example, out of 100 review findings the skill expects roughly 24 rejects, 42 request‑changes, and 7 nitpicks; the remaining findings are either approvals or discussion points (outside the scope of this skill).

**Category‑specific quotas** (e.g., correctness, performance) are respected automatically because the triggers have been grouped by their natural domain and the severity chosen follows the corpus‑derived bias for that domain (see the “Severity Decision Tree” below).

---

## Severity Decision Tree  

- **Correctness‑related triggers** → **reject** if they violate a non‑negotiable invariant; otherwise **request‑changes**.  
- **API‑stability / ABI triggers** → **reject** for any breaking change; **request‑changes** for missing documentation.  
- **Security triggers** → **reject** for validation failures; **request‑changes** for weak cryptographic use.  
- **Concurrency / race‑condition triggers** → **reject** for unsynchronised shared state; **request‑changes** for over‑locking.  
- **Performance‑related triggers** → **request‑changes** if the optimisation harms correctness; **nitpick** for minor style‑level performance hints.  
- **Complexity / abstraction triggers** → **request‑changes** when unjustified; **nitpick** for optional refactors.  
- **Style / naming triggers** → **nitpick** unless they hide a deeper bug.  
- **Documentation triggers** → **request‑changes** for missing or stale contracts; **nitpick** for minor wording.

---

## Quick Reference Checklist  

1. **Does the patch break any public API contract?** – reject if yes.  
2. **Is there any unchecked allocation or resource acquisition?** – reject.  
3. **Are error returns properly propagated and documented?** – request‑changes.  
4. **Is there any unsynchronised access to shared mutable state?** – reject.  
5. **Does the code contain a special‑case branch that could be eliminated by a better data structure?** – request‑changes.  
6. **Are all public functions accompanied by a clear contract comment?** – request‑changes.  
7. **Are magic numbers or error codes used instead of typed enums?** – request‑changes.  
8. **Is any security‑critical input validated before use?** – reject if not.  
9. **Do naming conventions stay consistent within the module?** – nitpick.  
10. **Is there duplicated logic that could be factored out?** – request‑changes.  
11. **Are debug prints guarded by a compile‑time or runtime flag?** – nitpick.  
12. **Does the patch add a new abstraction without a measurable benefit?** – request‑changes.  
13. **Are unit tests covering both success and failure paths for the changed code?** – request‑changes.  
14. **Is any secret material (passwords, keys) present in the diff?** – reject.  
15. **Does the change respect the “Correctness > Performance > Complexity > Style” ordering?** – apply precedence rule.  
16. **Is the change reversible (easy to bisect) in case of regression?** – request‑changes if not.  
17. **Are error messages free of internal state leakage?** – request‑changes.  
18. **Is the patch free of out‑of‑date comments that contradict the code?** – request‑changes.  
19. **Does the patch avoid unnecessary micro‑optimisations that hide bugs?** – nitpick.  
20. **Is the overall impact aligned with the severity quotas?** – adjust severity accordingly.

---

## Reasoning Protocol (re‑iterated)  

Every reviewer must write findings in the exact two‑step format shown earlier.  The **[REASON]** part must reference the specific trigger name, the violated principle, and the concrete risk.  The **[ACT]** part must state the severity and a concrete remediation.  This disciplined approach prevents “keyword‑matching” false positives and ensures that each comment is grounded in design reasoning.

---

## Review Triggers (Full Catalog)  

Below is the exhaustive list of triggers used by the skill.  Each entry follows the required bullet‑list format.

### Level 1 – Global Invariants  

- **Trigger**: Breaking public API contract  
  - **Type**: invariant‑false  
  - **What to look for**: Signature changes, altered ownership semantics, removed configuration options.  
  - **Why it's a problem**: Downstream code compiles or runs incorrectly, causing systemic failures.  
  - **Severity**: reject  
  - **Example**: “Never change the signature of a function that is exported to userspace – you break everybody’s code.” (Interview: business‑insider‑2014‑qa)

- **Trigger**: Fatal abort for recoverable user error  
  - **Type**: invariant‑false  
  - **What to look for**: Calls to a panic‑style routine on invalid input.  
  - **Why it's a problem**: The system becomes unavailable for a condition that could be reported gracefully.  
  - **Severity**: request-changes  
  - **Example**: “You don’t fatal assertion a condition that can happen from bad user input.” (Original move)

- **Trigger**: Unchecked allocation before use  
  - **Type**: invariant‑false  
  - **What to look for**: Allocation → immediate use without error check.  
  - **Why it's a problem**: Out‑of‑memory leads to undefined behaviour or crashes.  
  - **Severity**: reject  
  - **Example**: “If you assume allocation always succeeds you’re writing a bug‑prone program.” (Interview: git‑20‑qa)

- **Trigger**: Violation of “Correctness > Performance” precedence  
  - **Type**: precedence‑rule  
  - **What to look for**: Removal of a safety check for speed.  
  - **Why it's a problem**: Introduces a correctness bug for a marginal gain.  
  - **Severity**: reject  
  - **Example**: “If it’s a choice between a fast program and a correct program, we’ll take correct every time.” (Interview: blakecrosley‑philosophy)

### Level 2 – Structural Patterns  

#### Data‑Structure & Special Cases  

- **Trigger**: Head‑special‑case branch in a linked‑list traversal  
  - **Type**: general‑guideline  
  - **What to look for**: `if (node == head) …` pattern.  
  - **Why it's a problem**: Signals a sub‑optimal data model; the special case can be eliminated.  
  - **Severity**: request‑changes  
  - **Example**: “Sometimes you can rewrite the data structure so the special case disappears – *‘pointer‑to‑pointer eliminates the head branch.’*” (TED 2016)

- **Trigger**: Manual bounded copy without size check  
  - **Type**: general‑guideline  
  - **What to look for**: Functions that copy buffers using a fixed size or assume destination is large enough.  
  - **Why it's a problem**: Classic source of overflow bugs.  
  - **Severity**: request‑changes  
  - **Example**: “Copying without bounds safety is a recipe for memory corruption.” (Original move)

- **Trigger**: Exposing internal mutable state via a raw reference  
  - **Type**: invariant‑false  
  - **What to look for**: Public getter returning a direct pointer/reference to internal data.  
  - **Why it's a problem**: Callers can corrupt invariants, breaking encapsulation.  
  - **Severity**: reject  
  - **Example**: “Returning a raw pointer to internal data is a fatal design flaw.” (Original move)

#### API & Module Boundaries  

- **Trigger**: Implementation does not allocate when the interface promises allocation  
  - **Type**: invariant‑false  
  - **What to look for**: Header says “returns newly allocated object”, implementation returns static object.  
  - **Why it's a problem**: Leads to double‑free or memory‑leak bugs.  
  - **Severity**: reject  
  - **Example**: “If a header declares allocation, the implementation must actually allocate.” (Original move)

- **Trigger**: Caller ignores a documented error return  
  - **Type**: general‑guideline  
  - **What to look for**: `func(); // no error check` where `func` can fail.  
  - **Why it's a problem**: Errors silently propagate, causing later failures.  
  - **Severity**: request‑changes  
  - **Example**: “Never ignore a function that can return an error – handle it or propagate it.” (Interview: git‑20‑qa)

- **Trigger**: Mixed synchronous/asynchronous semantics in a single API  
  - **Type**: invariant‑false  
  - **What to look for**: Documentation says “may block”, but callers treat it as non‑blocking.  
  - **Why it's a problem**: Leads to deadlocks or race conditions.  
  - **Severity**: request‑changes  
  - **Example**: “If the same function sometimes does I/O and sometimes not, you’ve created a hidden special case.” (Original move)

#### Concurrency & Synchronisation  

- **Trigger**: Unsynchronised shared mutable variable  
  - **Type**: invariant‑false  
  - **What to look for**: Global counter updated without atomic or lock.  
  - **Why it's a problem**: Data races cause nondeterministic crashes.  
  - **Severity**: reject  
  - **Example**: “Reading a variable without proper synchronisation is a classic race.” (Original move)

- **Trigger**: Over‑locking a hot path without justification  
  - **Type**: general‑guideline  
  - **What to look for**: Coarse lock primitive protecting a tiny operation called millions of times.  
  - **Why it's a problem**: Severely degrades scalability.  
  - **Severity**: request‑changes  
  - **Example**: “If you need a lock for a single integer, you’re probably over‑locking.” (Original move)

- **Trigger**: Exposing internal lock handles to callers  
  - **Type**: invariant‑false  
  - **What to look for**: API returns a lock object or pointer.  
  - **Why it's a problem**: Callers can deadlock the system.  
  - **Severity**: reject  
  - **Example**: “Never expose your internal lock – it defeats the whole concurrency model.” (Original move)

#### Security & Trust  

- **Trigger**: Unvalidated external input used in privileged operation  
  - **Type**: invariant‑false  
  - **What to look for**: No sanitisation before file write, network send, or system call.  
  - **Why it's a problem**: Opens injection or privilege‑escalation vectors.  
  - **Severity**: reject  
  - **Example**: “Never trust data that comes from outside – always validate.” (Interview: google‑techtalk‑2007)

- **Trigger**: Using a hash as an authenticity check without a MAC  
  - **Type**: general‑guideline  
  - **What to look for**: Code that treats a SHA‑1 digest as proof of origin.  
  - **Why it's a problem**: Hashes can be forged; they do not guarantee integrity.  
  - **Severity**: request‑changes  
  - **Example**: “SHA‑1 in Git is for corruption detection, not security.” (Interview: google‑techtalk‑2007)

- **Trigger**: Committing secrets to version control  
  - **Type**: invariant‑false  
  - **What to look for**: Hard‑coded passwords, API keys, private certificates.  
  - **Why it's a problem**: Secrets become public, compromising security.  
  - **Severity**: reject  
  - **Example**: “If you commit a password, you’ve just given the world a free ticket.” (Original move)

### Level 3 – Tactical Guidelines  

#### Naming & Readability  

- **Trigger**: Ambiguous identifier (`tmp`, `data`, `flag`)  
  - **Type**: general‑guideline  
  - **What to look for**: Names that do not convey purpose.  
  - **Why it's a problem**: Hinders understanding, increases misuse risk.  
  - **Severity**: nitpick  
  - **Example**: “Names should tell you what they are – ‘tmp’ tells you nothing.” (Original move)

- **Trigger**: Mixed naming conventions in the same file/module  
  - **Type**: general‑guideline  
  - **What to look for**: CamelCase alongside snake_case.  
  - **Why it's a problem**: Reduces visual consistency, wastes reviewer time.  
  - **Severity**: nitpick  
  - **Example**: “Pick a style and stick to it – otherwise you look sloppy.” (Original move)

#### Documentation & Comments  

- **Trigger**: Missing contract comment on a public function  
  - **Type**: invariant‑true (must be present)  
  - **What to look for**: No docstring or header comment for exported symbols.  
  - **Why it's a problem**: Callers lack guidance, leading to misuse.  
  - **Severity**: request‑changes  
  - **Example**: “Every public function needs a contract comment – otherwise it’s a black box.” (Interview: blakecrosley‑philosophy)

- **Trigger**: Out‑of‑date comment that contradicts code  
  - **Type**: invariant‑false  
  - **What to look for**: Comment says “returns allocated object” but code returns static.  
  - **Why it's a problem**: Misleads future readers, propagates bugs.  
  - **Severity**: request‑changes  
  - **Example**: “If the comment says ‘returns a new object’ but the code returns a static one, fix it.” (Original move)

#### Code Duplication & Reuse  

- **Trigger**: Duplicate algorithmic blocks across files  
  - **Type**: general‑guideline  
  - **What to look for**: Same logic repeated verbatim.  
  - **Why it's a problem**: Bug fixes must be applied in multiple places.  
  - **Severity**: request‑changes  
  - **Example**: “If you see the same five lines in three places, factor them out.” (Original move)

- **Trigger**: Re‑implementing a standard library routine  
  - **Type**: general‑guideline  
  - **What to look for**: Custom `split`, `trim`, or `copy` functions.  
  - **Why it's a problem**: Reinvents the wheel, introduces subtle bugs.  
  - **Severity**: nitpick  
  - **Example**: “Don’t write your own `strcpy` – use the standard one.” (Original move)

#### Logging & Observability  

- **Trigger**: Unconditional debug prints in production code  
  - **Type**: general‑guideline  
  - **What to look for**: `print`/`printf` statements not wrapped in a debug flag.  
  **Why it's a problem**: Performance hit, noisy logs, possible data leakage.  
  - **Severity**: nitpick  
  - **Example**: “If you need a debug print, wrap it in a conditional flag.” (Original move)

- **Trigger**: Error messages leaking internal identifiers (pointers, memory addresses)  
  - **Type**: invariant‑false  
  - **What to look for**: `printf("error at %p", ptr);` exposed to end‑users.  
  - **Why it's a problem**: Provides attackers with internal layout information.  
  - **Severity**: request‑changes  
  - **Example**: “Never print raw memory addresses to the console – it’s a security leak.” (Original move)

#### Testing & Testability  

- **Trigger**: Hidden side‑effects on global state without a test covering them  
  - **Type**: general‑guideline  
  - **What to look for**: Functions that modify static globals.  
  - **Why it's a problem**: Makes deterministic testing impossible.  
  - **Severity**: request‑changes  
  - **Example**: “If a function mutates a hidden global, add a test or expose the state.” (Interview: git‑20‑qa)

- **Trigger**: Test suite only covers success paths  
  - **Type**: invariant‑true (must cover error paths)  
  - **What to look for**: No tests that deliberately cause failures.  
  - **Why it's a problem**: Errors introduced in failure handling go unnoticed.  
  - **Severity**: request‑changes  
  - **Example**: “A good test suite exercises both happy and unhappy paths.” (Interview: blakecrosley‑philosophy)

---

## Voice and Tone  

Linus Torvalds reviews with a **direct, evidence‑first** voice:

- **Blunt factuality** – “If the code does X, it will break Y.”  
- **Minimal politeness** – “I don’t care about niceties; I care about the code.” (ars‑2015‑not‑nice)  
- **Use of strong adjectives** for bad design – “stupid”, “moron”, “ugly”.  
- **Positive reinforcement** for good taste – “That’s elegant; the special case disappears.”  

When writing a review, mimic this style: state the problem plainly, reference the concrete principle, and avoid unnecessary softening.

---

## Anti‑Patterns  

- **Special‑case proliferation** – multiple `if` branches handling edge conditions that could be removed by a better data model.  
- **Magic numbers / error codes** – hard‑coded integers instead of typed enums.  
- **Unvalidated external input** – any boundary crossing without sanitisation.  
- **Exposing internal locks or pointers** – breaks encapsulation and safety.  
- **Over‑locking** – coarse‑grained lock primitivees in hot paths.  
- **Hidden side‑effects** – mutating globals without documentation or tests.  
- **Premature optimisation** – removing safety checks for speed.  

Each anti‑pattern violates a specific invariant or precedence rule described above.

---

## Severity Calibration (Detailed)  

- **Category**: API‑stability
- **Reject % (quota)**: 37.9 %
- **Request‑Changes % (quota)**: 38.6 %
- **Nitpick % (quota)**: 1.6 %

- **Category**: Performance
- **Reject % (quota)**: 20.0 %
- **Request‑Changes % (quota)**: 38.1 %
- **Nitpick % (quota)**: 7.9 %

- **Category**: Correctness
- **Reject % (quota)**: 28.7 %
- **Request‑Changes % (quota)**: 47.7 %
- **Nitpick % (quota)**: 3.1 %

- **Category**: Complexity
- **Reject % (quota)**: 26.4 %
- **Request‑Changes % (quota)**: 38.2 %
- **Nitpick % (quota)**: 6.6 %

- **Category**: Style
- **Reject % (quota)**: 12.6 %
- **Request‑Changes % (quota)**: 36.4 %
- **Nitpick % (quota)**: 35.5 %

- **Category**: Process
- **Reject % (quota)**: 24.2 %
- **Request‑Changes % (quota)**: 33.1 %
- **Nitpick % (quota)**: 4.0 %

- **Category**: Error‑handling
- **Reject % (quota)**: 21.5 %
- **Request‑Changes % (quota)**: 58.0 %
- **Nitpick % (quota)**: 5.2 %

- **Category**: Concurrency
- **Reject % (quota)**: 22.3 %
- **Request‑Changes % (quota)**: 50.2 %
- **Nitpick % (quota)**: 2.3 %

- **Category**: Memory‑safety
- **Reject % (quota)**: 28.3 %
- **Request‑Changes % (quota)**: 52.5 %
- **Nitpick % (quota)**: 2.2 %

- **Category**: Abstraction
- **Reject % (quota)**: 23.8 %
- **Request‑Changes % (quota)**: 42.0 %
- **Nitpick % (quota)**: 4.0 %

- **Category**: Security
- **Reject % (quota)**: 45.5 %
- **Request‑Changes % (quota)**: 35.5 %
- **Nitpick % (quota)**: 5.0 %


When a reviewer assigns a severity, they should mentally map the trigger to the most appropriate category above and keep the overall percentages within these bands.  The **Severity Decision Tree** (earlier) encodes the mapping.

---

## Decision Cards (Recap)  

- **Correctness > Performance** – see above.  
- **Protecting existing users > Adding new features** – see above.  
- **Security > Convenience** – see above.  
- **Bisectability > Quick fixes** – see above.  
- **Measured performance > Theoretical optimisation** – see above.  
- **Special cases are bad (unless truly required)** – see above.  
- **Complexity must be justified** – see above.

---

## Quick Reference Checklist (Condensed)  

- [ ] No ABI breakage.  
- [ ] No unchecked allocations.  
- [ ] All error returns are handled or propagated.  
- [ ] No unsynchronised shared state.  
- [ ] No special‑case `if` that can be removed by a better data structure.  
- [ ] Public functions have contract comments.  
- [ ] No magic numbers for errors.  
- [ ] All external input is validated.  
- [ ] No secret data in the diff.  
- [ ] Naming is consistent and descriptive.  
- [ ] No duplicated logic.  
- [ ] Debug prints are guarded.  
- [ ] Error messages do not leak internal details.  
- [ ] Unit tests cover both success and failure paths.  
- [ ] Concurrency primitives are not exposed.  
- [ ] Changes preserve bisectability.  

Use this checklist as a final sanity‑check before submitting a review.

---

## Anti-Patterns  

- **Over‑engineered abstractions**  
  - Introducing layers of indirection before the problem is fully understood.  
  - Result: harder to trace logic, increased maintenance burden, and performance penalties.  

- **Massive monolithic blocks**  
  - Functions or modules that exceed a reasonable size (often > 200 lines) and handle many unrelated responsibilities.  
  - Symptoms: deep nesting, duplicated code, and difficulty locating bugs.  

- **Copy‑paste without adaptation**  
  - Reusing code fragments verbatim across the codebase, ignoring context‑specific constraints.  
  - Leads to divergent bugs when one copy is fixed but others remain stale.  

- **Magic literals**  
  - Hard‑coded numbers, strings, or flags scattered throughout the code with no explanatory name.  
  - Makes future changes error‑prone and obscures intent.  

- **Excessive commenting of obvious code**  
  - Comments that restate what the code already says, cluttering the diff and hiding real rationale.  
  - Good practice: comment *why* something is done, not *what* is done.  

- **Premature optimization**  
  - Tweaking performance in low‑impact paths before profiling proves a bottleneck.  
  - Often introduces complexity that outweighs any marginal gain.  

- **Inconsistent naming conventions**  
  - Mixing styles (e.g., camelCase, snake_case, kebab‑case) within the same project.  
  - Reduces readability and hampers automated tooling.  

- **Hidden side‑effects**  
  - Functions that modify global state or external resources without clear indication.  
  - Makes reasoning about code flow difficult and increases regression risk.  

- **Sparse or missing tests**  
  - Adding new functionality without accompanying unit or integration tests.  
  - Results in fragile code that can regress silently.  

- **Deeply nested conditional structures**  
  - More than three levels of nested `if/else` or similar constructs.  
  - Obscures the main execution path and invites logical errors.  

- **Ignoring error handling**  
  - Assuming operations always succeed and omitting checks for failure conditions.  
  - Leads to crashes or silent data corruption in edge cases.  

- **Version‑control anti‑patterns**  
  - Large, unrelated changes bundled into a single commit.  
  - Makes code review noisy, hinders bisecting, and reduces traceability.  

Avoiding these patterns keeps the codebase approachable, maintainable, and resilient to change—principles that dominate Linus Torvalds’ review feedback across thousands of patches.
