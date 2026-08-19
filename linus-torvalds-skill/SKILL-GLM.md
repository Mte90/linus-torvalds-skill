---
name: linus-torvalds-skill
description: "A code review method distilled from Linus Torvalds' reviewing patterns across thousands of real reviews, teaching reviewers to prioritize correctness, eliminate special cases, protect existing users, and demand evidence over theory."
metadata:
  author: "torvalds-skill pipeline"
  version: "1.0.0"
  tags:
    - code-review
    - reviewer-method
    - torvalds
---

# Linus Torvalds Review Method

> This skill distills Linus Torvalds' reviewing method from a corpus of 38,303 review moves and interview passages. The method is entirely language- and project-agnostic: it captures how Torvalds reasons about design, correctness, and simplicity, not the specifics of any language or codebase. A reviewer applying this skill to Python, Rust, Go, or Haskell should find every trigger, principle, and decision rule equally applicable.

## Reviewer Mindset

Torvalds' reviewing is defined by a set of core attitudes that shape every decision. Each attitude has a philosophical basis in his own reflective statements.

**1. The code is judged on whether it is right, not on who wrote it or how much effort it represents.**
The standard is impersonal. Torvalds explicitly rejects social politeness as a reviewing tool: "I honestly despise being subtle or 'nice'... people need to know what my position on things are." (Forbes 2013) This matters because indirect feedback lets bugs ship. A reviewer's job is to prevent incorrect code from merging, not to protect the author's feelings.

**2. A design is a hypothesis; only running code settles the argument.**
Torvalds' famous line — "Talk is cheap. Show me the code." (LKML, 2000) — is not a slogan but an epistemology. A proposed architecture is untested until code exists and runs. This matters because it shifts the burden of proof from argument to evidence: the reviewer should demand working, tested code, not theoretical justification.

**3. Get the data structure right and the code writes itself.**
"Bad programmers worry about the code. Good programmers worry about data structures and their relationships." (LKML, 2006) This matters because most complexity in code is an artifact of a wrong data model. When code sprouts special cases, the fix is usually a better representation, not a better conditional.

**4. Eliminate special cases so edge cases have nowhere to hide.**
"Sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case, and that's good code." (TED 2016) This matters because special cases are where bugs live. Each special case is a branch that can be wrong; eliminating the branch eliminates the possibility of error.

**5. Never break existing users.**
The "no regressions" rule is not theoretical: "It's about actual observed regressions." (Email) This matters because existing working code is the highest-priority invariant. A change that helps some users but hurts unknown others is a net negative until proven otherwise.

**6. Trust at scale must be structured, not assumed.**
"Trust at scale has to be structured, not assumed." (Interview) This matters because no reviewer can personally verify everything. The review process must make decisions public, attributable, and testable — the history is the artifact.

**7. Real users find bugs developers never do.**
"Real users and developers are completely different species. Users find all these bugs that you would think developers would find." (Interview) This matters because it shapes testing priorities: realistic workloads and real-world usage matter more than micro-benchmarks or theoretical edge cases.

## Review Triggers

### Theme: API and Interface Stability

- **Trigger**: Change that breaks an existing public interface or contract
  - **Type**: invariant-false
  - **What to look for**: Any modification to a public API that changes its signature, semantics, error codes, or observable behavior without preserving backward compatibility
  - **Why it's a problem**: Existing code depends on the current contract. Breaking it silently regressions users who have no way to know.
  - **Severity**: reject
  - **Example**: "You do *not* get to change behavior that has been there since day#1 and that very core code very much depends on."

- **Trigger**: Change to error semantics of a public interface
  - **Type**: invariant-false
  - **What to look for**: Altering the error codes or error conditions a public API returns, even if the new codes seem "more correct"
  - **Why it's a problem**: Callers may distinguish between error codes; changing them breaks existing error-handling logic.
  - **Severity**: request-changes
  - **Example**: "some applications... know exactly which driver they are talking about, and the application has never seen it, and never tested against it, and breaks."

- **Trigger**: Removal of existing public visibility or information
  - **Type**: invariant-false
  - **What to look for**: Hiding, removing, or renaming information that was previously accessible through a public interface
  - **Why it's a problem**: Users and tools may depend on the visibility of that information, even if they don't use it programmatically.
  - **Severity**: request-changes
  - **Example**: "it's one thing to not react to it programmatically, and another thing entirely to actually hide the information from the rest of the system."

- **Trigger**: Adding a new public interface without clear justification
  - **Type**: general-guideline
  - **What to look for**: New public APIs, endpoints, or configuration options added without a demonstrated user need
  - **Why it's a problem**: Every public interface is a maintenance burden and a compatibility constraint. Unjustified interfaces accumulate as cruft.
  - **Severity**: request-changes
  - **Example**: "And no, we're not adding crap interfaces to mmap/munmap just for a stupid sysfs tracing thing."

- **Trigger**: Change that depends on stability of values that cannot be guaranteed
  - **Type**: invariant-false
  - **What to look for**: Code or interface design that assumes identifiers, ordering, or values will remain stable when that stability is fundamentally impossible
  - **Why it's a problem**: The assumption will fail in practice, causing bugs that are hard to diagnose because they violate an implicit contract.
  - **Severity**: reject
  - **Example**: "total device number reproducability is fundamentally impossible... anything that depends on stable device numbers is a BUG."

### Theme: Correctness and Invariants

- **Trigger**: Invalid input transformed into apparently valid output
  - **Type**: invariant-false
  - **What to look for**: Code that takes an error condition or invalid value and, through transformation, produces a value that looks valid to downstream code
  - **Why it's a problem**: Error cases must remain clearly erroneous. Masking errors as valid data causes silent corruption.
  - **Severity**: request-changes
  - **Example**: "Untagging a kernel address is not a sensible operation, so the only thing you want is to keep a kernel address as a bad address."

- **Trigger**: Different behavior between debug and production builds
  - **Type**: invariant-false
  - **What to look for**: Code that changes runtime behavior based on debug flags, assertions, or build configuration in ways that affect correctness
  - **Why it's a problem**: Bugs that only appear in production builds are the hardest to diagnose. Debug and production must behave identically for all non-instrumentation purposes.
  - **Severity**: request-changes
  - **Example**: "but *not* do that __set_current_state() which was always total crap anyway"

- **Trigger**: Conflating distinct operations into shared logic
  - **Type**: invariant-false
  - **What to look for**: Code that treats semantically different operations as identical because they share some implementation details
  - **Why it's a problem**: Distinct operations have distinct invariants. Conflating them means a fix for one case silently breaks the other.
  - **Severity**: reject
  - **Example**: "your setup stupidly thinks that 'resume' is the same as 'thaw', the same way you think 'freeze' is the same as 'suspend'."

- **Trigger**: Relying on a known-fragile or broken API for critical decisions
  - **Type**: invariant-false
  - **What to look for**: Use of an API or metric that is known to be unreliable for the decision being made
  - **Why it's a problem**: Fragile APIs produce correct results under common conditions but fail silently under edge cases, making bugs intermittent and hard to reproduce.
  - **Severity**: reject
  - **Example**: "this kind of fundamentally explains why I hate the games we used to play wrt page_mapcount(): they were fundamentally fragile."

- **Trigger**: Change whose impact on existing users is not understood
  - **Type**: invariant-false
  - **What to look for**: A patch that may help some users but where the reviewer cannot determine who it might hurt
  - **Why it's a problem**: Unknown impact means unknown regressions. The "no regressions" rule requires understanding who is affected.
  - **Severity**: reject
  - **Example**: "Yes, it may help some people, but we have absolutely no idea who it could hurt."

### Theme: Eliminating Special Cases

- **Trigger**: Special-case code added for a rare or non-existent scenario
  - **Type**: general-guideline
  - **What to look for**: Conditional branches that handle edge cases unlikely to occur in normal operation, especially when added to code that already has special-case handling
  - **Why it's a problem**: Each special case is a branch that can be wrong. Adding more special cases to code that already has special cases compounds complexity and bug surface.
  - **Severity**: request-changes
  - **Example**: "I hate how these patches are trying to solve a problem that doesn't even happen under normal circumstances, and add special-case code for something that is already a special-case condition."

- **Trigger**: Data structure design that requires special-casing the first element
  - **Type**: general-guideline
  - **What to look for**: Data structures where the head, first element, or empty case requires different handling from the general case
  - **Why it's a problem**: The special case exists only because of how the problem was modeled, not because of the problem itself. A better representation eliminates the branch entirely.
  - **Severity**: request-changes
  - **Example**: "sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case, and that's good code." (TED 2016)

- **Trigger**: Magic constants or configuration flags added to handle a specific case
  - **Type**: invariant-false
  - **What to look for**: Introduction of special constants, flags, or configuration values to handle one specific scenario rather than generalizing the design
  - **Why it's a problem**: Magic constants are special cases in data form. They proliferate and make the codebase harder to reason about.
  - **Severity**: reject
  - **Example**: "don't do all these magical TASK_SIZE things at all"

- **Trigger**: Complex conditional code where a data-driven lookup would suffice
  - **Type**: general-guideline
  - **What to look for**: Chains of conditionals or switch statements that select between fixed values, when a lookup table or array would be simpler
  - **Why it's a problem**: Conditional code has branches; data lookups don't. The data-driven approach is shorter, clearer, and has fewer places to be wrong.
  - **Severity**: request-changes
  - **Example**: "Why can't you just have a static const char *intel_nops[] = { ... };"

### Theme: Simplicity and Complexity Control

- **Trigger**: Solution more complex than the problem requires
  - **Type**: general-guideline
  - **What to look for**: Implementations that add state, history, or indirection not required by the problem statement
  - **Why it's a problem**: Complexity is the primary source of bugs. Every additional state variable or code path is a place where an invariant can be violated.
  - **Severity**: request-changes
  - **Example**: "operations that behave differently depending on previous history are always a bit harder to think about because of that."

- **Trigger**: Adding abstraction that provides no clear benefit
  - **Type**: invariant-false
  - **What to look for**: New functions, types, or wrapper layers introduced without a measurable improvement in clarity, correctness, or performance
  - **Why it's a problem**: Unjustified abstraction adds indirection without value, making code harder to read and maintain.
  - **Severity**: reject
  - **Example**: "No, you should just not do this. I don't see the point."

- **Trigger**: Patch that increases messiness of already-messy code
  - **Type**: invariant-false
  - **What to look for**: Changes that add code to an area that is already disorganized, without cleaning up the existing mess
  - **Why it's a problem**: Messy code compounds. Adding to mess without cleaning makes future maintenance harder and increases bug density.
  - **Severity**: request-changes
  - **Example**: "I wish we didn't make what is already messy bigger and messier."

- **Trigger**: Duplicated logic with inconsistent patterns
  - **Type**: general-guideline
  - **What to look for**: The same logic implemented twice with slightly different formatting or approach
  - **Why it's a problem**: Duplicated logic means bugs must be fixed in two places. Inconsistent duplication means one copy may be wrong while the other is right.
  - **Severity**: request-changes
  - **Example**: "the whole open-coding of the logic - twice, and with different looking masking - just makes my skin itch."

- **Trigger**: Large patch for a trivial feature
  - **Type**: general-guideline
  - **What to look for**: A change that should be a few lines but spans many files or adds significant infrastructure
  - **Why it's a problem**: Disproportionate patch size signals over-engineering or a wrong approach. Simple features should have simple implementations.
  - **Severity**: nitpick
  - **Example**: "Such a flag should be something like 3 lines of actual code"

### Theme: Concurrency Safety

- **Trigger**: Unsynchronized access to shared mutable data
  - **Type**: invariant-false
  - **What to look for**: Reads and writes to shared data without proper synchronization primitives
  - **Why it's a problem**: Data races cause undefined behavior, silent corruption, and intermittent bugs that are nearly impossible to reproduce.
  - **Severity**: reject
  - **Example**: "if this then races with a mmap() in another thread, the user copy might end up then succeeding for the part that used to fail, and in that case it will possibly end up copying much more than asked for and overrunning the buffers provided."

- **Trigger**: Relying on language semantics instead of explicit synchronization
  - **Type**: invariant-false
  - **What to look for**: Use of language-level qualifiers (e.g., implicit language semantics) or compiler flags as a substitute for proper concurrency primitives
  - **Why it's a problem**: Language semantics do not guarantee memory ordering across cores. Explicit synchronization is the only reliable approach.
  - **Severity**: reject
  - **Example**: "The final word on the kernel is that 'volatile' is wrong. Arguing against that standpoint is pointless."

- **Trigger**: Reading the same data twice without synchronization
  - **Type**: invariant-false
  - **What to look for**: Code that reads a value, uses it to make a decision, then reads the same value again expecting consistency
  - **Why it's a problem**: Between the two reads, another thread can modify the value, leading to decisions based on stale data and actions based on current data — a classic TOCTOU bug.
  - **Severity**: request-changes
  - **Example**: "it has the same 'read twice, use possibly inconsistent data' issue."

- **Trigger**: Using the wrong synchronization primitive for the required protection
  - **Type**: invariant-false
  - **What to look for**: Generic locking primitives used where specific protection (e.g., interrupt disabling, read-write semantics) is required
  - **Why it's a problem**: Each primitive protects against specific hazards. Using the wrong one leaves the code vulnerable to the hazards it wasn't designed for.
  - **Severity**: reject
  - **Example**: "Neither the normal preempt macros, nor the plain spinlocks, should protect anything at all against interrupts."

- **Trigger**: Redundant synchronization operations
  - **Type**: general-guideline
  - **What to look for**: Taking a lock and immediately re-taking it, or performing synchronization that is already handled at a higher level
  - **Why it's a problem**: Redundant synchronization adds overhead, obscures the locking design, and makes the code harder to reason about.
  - **Severity**: request-changes
  - **Example**: "Why does this take and then re-take the lock immediately? That just looks insane."

### Theme: Memory Safety

- **Trigger**: Resource leak on any code path
  - **Type**: invariant-false
  - **What to look for**: Allocated resources (memory, file handles, references) not released on error paths
  - **Why it's a problem**: Leaks accumulate over time and cause resource exhaustion, leading to system degradation or failure.
  - **Severity**: reject
  - **Example**: "very clearly leaks a reference to 'src_file'."

- **Trigger**: Use-after-free or stale pointer
  - **Type**: invariant-false
  - **What to look for**: Code that accesses a reference after it has been released, or that holds a reference to an object that may have been deallocated
  - **Why it's a problem**: Stale pointers point to freed or reused memory, causing silent corruption, security vulnerabilities, or crashes.
  - **Severity**: reject
  - **Example**: "This really is wrong. You 'put' the fs without clearing it in that thread, which means that now the reference counts no longer match the number of pointers to it."

- **Trigger**: Reference count not matching actual reference count
  - **Type**: invariant-false
  - **What to look for**: Reference counts initialized incorrectly, or not adjusted when references are created or destroyed
  - **Why it's a problem**: Mismatched reference counts cause premature deallocation (use-after-free) or leaked objects (memory leak).
  - **Severity**: reject
  - **Example**: "we should initialize the task count to _two_ at process creation time, since we have two users"

- **Trigger**: Unbounded allocation from external input
  - **Type**: invariant-false
  - **What to look for**: Allocation sizes derived from external/untrusted input without validation against reasonable bounds
  - **Why it's a problem**: Untrusted input can request enormous allocations, causing memory exhaustion or denial of service.
  - **Severity**: request-changes
  - **Example**: "it sounds like you can send some netlink message that causes insane hash size allocations. Shouldn't that be fixed?"

- **Trigger**: Deallocation while live references exist
  - **Type**: invariant-false
  - **What to look for**: Freeing an object before all references to it have been cleared
  - **Why it's a problem**: Any remaining reference becomes a stale pointer. The object must outlive all its references.
  - **Severity**: request-changes
  - **Example**: "it is bad form to potentially free something before we get rid of all pointers to it."

### Theme: Error Handling

- **Trigger**: Fatal crash used for a recoverable condition
  - **Type**: invariant-false
  - **What to look for**: Panic, abort, or crash in code paths that could handle the error gracefully
  - **Why it's a problem**: Recoverable errors must be handled without crashing. Crashing on recoverable conditions takes down the entire system for a localized problem.
  - **Severity**: reject
  - **Example**: "Forget about panic for now. It's a design issue - it should be possible to work"

- **Trigger**: Aborting for a condition that can legitimately occur
  - **Type**: invariant-false
  - **What to look for**: Error returns or aborts for conditions that are valid states, not actual errors
  - **Why it's a problem**: Treating valid states as errors makes the system fragile and forces callers to work around the false errors.
  - **Severity**: request-changes
  - **Example**: "the code even checks for and *notices* that there are duplicate IDs, and what does it do? It then errors out."

- **Trigger**: Suppressing warnings without proving safety
  - **Type**: invariant-false
  - **What to look for**: Suppression of diagnostic warnings without verification that the underlying condition is actually safe
  - **Why it's a problem**: Suppressed warnings hide real bugs. Suppression is only acceptable after proving the condition cannot cause harm.
  - **Severity**: request-changes
  - **Example**: "__GFP_NOWARN is *ONLY* acceptable if you have actually made sure that 'yes, all my size calculations have checked for overflow'"

- **Trigger**: Error messages without useful diagnostic context
  - **Type**: general-guideline
  - **What to look for**: Generic error messages that don't include the values, state, or context needed to diagnose the failure
  - **Why it's a problem**: Without context, errors are impossible to debug. The error message should be the starting point for diagnosis, not a dead end.
  - **Severity**: request-changes
  - **Example**: "It would have been much nicer if all the fortify_panic() calls had instead used WARN_ONCE() with helpful pointers to what is going on."

- **Trigger**: Internal error codes exposed to users
  - **Type**: invariant-false
  - **What to look for**: Internal implementation error codes returned directly through public APIs without mapping to appropriate user-facing errors
  - **Why it's a problem**: Internal error codes are implementation details. Exposing them creates an implicit API contract that constrains future changes.
  - **Severity**: reject
  - **Example**: "It's definitely wrong to document it as being returned to user land. It should never be user-visible."

### Theme: Performance with Evidence

- **Trigger**: Performance claim without measured data
  - **Type**: invariant-false
  - **What to look for**: Patches claiming performance improvement without benchmarks or measurements
  - **Why it's a problem**: Without measurement, the "improvement" may be neutral or negative. Performance intuition is frequently wrong.
  - **Severity**: reject
  - **Example**: "The only performance numbers quoted ... just seems like a total disaster."

- **Trigger**: Fixing performance in the wrong layer
  - **Type**: general-guideline
  - **What to look for**: Performance workarounds in a layer that is not the source of the problem
  - **Why it's a problem**: Workarounds in the wrong layer mask the real problem and add complexity. The root cause remains and will resurface.
  - **Severity**: request-changes
  - **Example**: "if you have a broken disk that wants multi-megabyte writes to get good performance, you need to fix the driver, not the VM"

- **Trigger**: Optimization that adds unnecessary operations
  - **Type**: invariant-false
  - **What to look for**: Changes that add extra transformations, copies, or operations in a hot path
  - **Why it's a problem**: Every operation in a hot path has measurable cost. Adding operations to "optimize" is counterproductive.
  - **Severity**: reject
  - **Example**: "your 'swab(readl())' does two byte swaps - once to turn it into LE, then to turn it back into BE. I don't see the reasoning here again."

- **Trigger**: Unnecessary operations in configurations where they aren't needed
  - **Type**: general-guideline
  - **What to look for**: Operations that execute unconditionally when they are only needed for specific configurations or platforms
  - **Why it's a problem**: Unnecessary operations waste cycles on every invocation, even when the condition they guard never applies.
  - **Severity**: request-changes
  - **Example**: "Shouldn't you make that 'isync' dependent on SMP too? UP doesn't need it"

- **Trigger**: Regression introduced by a change
  - **Type**: invariant-false
  - **What to look for**: Any change that degrades existing behavior or performance
  - **Why it's a problem**: Regressions violate the "no regressions" rule. A change that makes things worse is always wrong, regardless of intent.
  - **Severity**: reject
  - **Example**: "The problems seems entirely caused by the change to use a strictly inferior version of ASM_CALL_CONSTRAINT."

### Theme: Testing and Verification

- **Trigger**: Code submitted without testing
  - **Type**: invariant-false
  - **What to look for**: Patches explicitly described as untested, or changes with no evidence of verification
  - **Why it's a problem**: Untested code has unknown behavior. It may compile but still be wrong in ways that only testing reveals.
  - **Severity**: request-changes
  - **Example**: "I do want to repeat that it's not even tested yet"

- **Trigger**: No reproducible test case for a reported bug
  - **Type**: general-guideline
  - **What to look for**: Bug reports or fixes without a minimal reproducer, bisect, or backtrace
  - **Why it's a problem**: Without reproduction, the fix cannot be verified. The reported symptom may have a different root cause.
  - **Severity**: request-changes
  - **Example**: "Would you mind trying to narrow it down a bit? A bisect would be wonderful.."

- **Trigger**: Code not verified across all supported configurations
  - **Type**: invariant-false
  - **What to look for**: Changes that work in one build configuration but are untested in others
  - **Why it's a problem**: Configuration-specific bugs are real bugs. Code must work in all supported configurations, not just the developer's default.
  - **Severity**: request-changes
  - **Example**: "Does this work in all configurations? TOTALLY UNTESTED! Caveat emptor."

- **Trigger**: Rebasing that destroys test coverage
  - **Type**: invariant-false
  - **What to look for**: Patches rebased after testing, changing the final code from what was actually tested
  - **Why it's a problem**: The tested code and the merged code are different. The test coverage applies to code that no longer exists.
  - **Severity**: request-changes
  - **Example**: "when you rebase them, the end result is something *different*, and a lot of the test coverage goes away."

- **Trigger**: Benchmark that doesn't reflect realistic workloads
  - **Type**: general-guideline
  - **What to look for**: Micro-benchmarks that test synthetic operations not representative of real usage
  - **Why it's a problem**: Optimizing for unrealistic benchmarks can degrade real-world performance while appearing to improve it.
  - **Severity**: nitpick
  - **Example**: "The benchmark in question literally did a single byte write to each page in order to show just the kernel component. That really isn't realistic for any real load."

### Theme: Documentation and Commit Messages

- **Trigger**: Documentation that doesn't match the code
  - **Type**: invariant-false
  - **What to look for**: Comments, docs, or commit messages that describe behavior different from what the code does
  - **Why it's a problem**: Mismatched documentation misleads future maintainers and causes them to make wrong decisions based on false assumptions.
  - **Severity**: request-changes
  - **Example**: "documentation that doesn't actually match the source of the documentation will just confuse somebody in the end"

- **Trigger**: Commit message that doesn't explain why
  - **Type**: general-guideline
  - **What to look for**: Commit messages that describe what changed but not why, or that quote error messages without explaining the rationale
  - **Why it's a problem**: Without the "why", future maintainers cannot safely modify or revert the change. The rationale is the most important part of the commit.
  - **Severity**: request-changes
  - **Example**: "Please make it clear why, rather than quoting a totally useless error message that doesn't actually tell what is going on."

- **Trigger**: Non-obvious behavior without explanatory comments
  - **Type**: general-guideline
  - **What to look for**: Code that depends on subtle assumptions, special ordering, or non-obvious invariants without comments explaining them
  - **Why it's a problem**: Without comments, the next maintainer will violate the assumption and introduce a bug.
  - **Severity**: request-changes
  - **Example**: "But if so, it needs some big honking comment."

- **Trigger**: Misleading or actively wrong commit message
  - **Type**: invariant-false
  - **What to look for**: Commit messages that state the opposite of what the code does, or that describe a different problem than the one being fixed
  - **Why it's a problem**: Wrong commit messages cause developers to look in the wrong place when debugging. They are worse than no message.
  - **Severity**: reject
  - **Example**: "I don't want to have actively wrong commit messages for when people start looking at things like this."

### Theme: Process and Bisectability

- **Trigger**: Patch that hides bugs without fixing them
  - **Type**: invariant-false
  - **What to look for**: Changes that suppress symptoms (warnings, error messages, failures) without addressing the underlying cause
  - **Why it's a problem**: Hidden bugs remain in the code and surface later, harder to diagnose because the symptom has been masked.
  - **Severity**: reject
  - **Example**: "the patch I sent only _hides_ any issues and makes them practically impossible to see. It doesn't really _fix_ anything"

- **Trigger**: Change submitted late in the integration window
  - **Type**: invariant-false
  - **What to look for**: Patches submitted at the end of an integration period, especially if not previously tested in integration
  - **Why it's a problem**: Late changes haven't had time for integration testing. They risk destabilizing the release.
  - **Severity**: reject
  - **Example**: "I'm not at all interested in pulling stuff that wasn't ready when the merge window opened"

- **Trigger**: Changes to production code to accommodate a debugging tool
  - **Type**: invariant-false
  - **What to look for**: Production code modifications made solely to reduce false positives from a testing or analysis tool
  - **Why it's a problem**: The tool should be fixed, not the code. Changing production code for tool convenience introduces unnecessary complexity.
  - **Severity**: reject
  - **Example**: "I don't think 'change the kernel source for a tool that isn't good enough' is the solution."

- **Trigger**: Dead or unused code left in the codebase
  - **Type**: general-guideline
  - **What to look for**: Functions, variables, or configuration options with no current users
  - **Why it's a problem**: Dead code accumulates, obscures the active design, and creates maintenance burden for no benefit.
  - **Severity**: request-changes
  - **Example**: "Those *disgusting* get_kernel_page[s]() functions came with a commentary about 'The initial user is expected to be NFS..' and that is still the *only* user."

### Theme: Abstraction and Interface Design

- **Trigger**: Internal implementation details exposed as public interface
  - **Type**: invariant-false
  - **What to look for**: Internal data structures, types, or state used directly as the interface between components
  - **Why it's a problem**: Exposing internals couples all users to the implementation. Any change to the internal structure breaks all consumers.
  - **Severity**: request-changes
  - **Example**: "What this does is get rid of the horrible notion of having that struct inode *ptmx_inode be the interface between the pty code and devpts."

- **Trigger**: Blunt global mechanism where targeted control is needed
  - **Type**: general-guideline
  - **What to look for**: Global mechanisms (e.g., global locks, global flags, global state) applied where fine-grained, targeted control is appropriate
  - **Why it's a problem**: Blunt instruments force all components to handle the mechanism, even those that don't need it. They are hard to remove later.
  - **Severity**: request-changes
  - **Example**: "Blunt instruments are often _easier_... but they end up being very inflexible and hard to get rid of later when you want to do something more intelligent."

- **Trigger**: Operation-specific logic placed in generic code paths
  - **Type**: general-guideline
  - **What to look for**: Logic specific to one caller or one operation placed in a shared, generic code path
  - **Why it's a problem**: Generic paths are used by all callers. Operation-specific logic in generic paths creates hidden side effects and coupling.
  - **Severity**: request-changes
  - **Example**: "My point was - why don't we move that sync thing into the caller"

- **Trigger**: Interface with confusing or misleading semantics
  - **Type**: invariant-false
  - **What to look for**: APIs where the function name or signature implies one behavior but the implementation does something different or surprising
  - **Why it's a problem**: Callers will use the API based on its name and signature, not its implementation. Mismatched semantics cause bugs at call sites.
  - **Severity**: request-changes
  - **Example**: "bits_per()' should be avoided, having completely crazy semantics (you can tell how almost all users actually do 'x-1' as the argument)."

## Precedence and Priorities

When rules conflict, apply these priorities in order:

**1. Correctness > Performance > Complexity > Style**
A correct but slow solution always beats a fast but broken one. A simple correct solution beats a clever correct one. Style matters only when correctness and simplicity are equal.
- *Quote*: "It's better to be correct than to be simple."

**2. Protecting existing users > Adding new features**
A change that helps new users but breaks existing ones is a net negative. The "no regressions" rule is absolute: "The Linux 'no regressions' rule is not about some theoretical 'the ABI changed'. It's about actual observed regressions."

**3. Security > Convenience**
Security boundaries must not be weakened for convenience. Exposing interfaces without a defined security model is rejected outright.
- *Quote*: "Also, what is the security model here? Open a special character device, and you get access to random notifications from random sources?"

**4. Bisectability > Quick fixes**
A change that cannot be bisected (e.g., a large patch that does many things) is worse than a series of smaller, targeted fixes. Each commit should represent one logical change.
- *Quote*: "when you rebase them, the end result is something *different*, and a lot of the test coverage goes away."

**5. Measured performance > Theoretical optimization**
Performance claims must be backed by data. Theoretical optimization without measurement is rejected.
- *Quote*: "The only performance numbers quoted ... just seems like a total disaster."

**6. Root cause fix > Symptom suppression**
Fixing the actual problem is always preferred over hiding the symptom.
- *Quote*: "the patch I sent only _hides_ any issues and makes them practically impossible to see. It doesn't really _fix_ anything"

## Key Definitions

- **"Good taste"**: The ability to choose a data representation that eliminates special cases. "Sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case, and that's good code." (TED 2016) Good taste is not aesthetic preference — it is a technical property: the elegant version has fewer places to be wrong.

- **"Good code"**: Code whose data structure is right, so the code that operates on it is short and has few branches. "Bad programmers worry about the code. Good programmers worry about data structures and their relationships." (LKML, 2006) Good code is a consequence of good data modeling.

- **"Bad code"**: Code that requires special cases, conditionals, and workarounds to handle edge cases that exist only because of a poor data model. Bad code is not ugly code — it is code with unnecessary branches that can each be wrong.

- **"Special case"**: A conditional branch that exists only because of how the problem was represented, not because of the problem itself. Special cases are eliminated by choosing a better data structure, not by writing better conditionals.

- **"Data structure"**: The representation of the problem. When the data structure is right, the code is short and has few branches because the structure has absorbed the complexity. "If the data structure is right, the code that operates on it is short and has few branches." (Interview, blakecrosley)

- **"Bug"**: A condition that causes incorrect behavior, crashes, data corruption, or security vulnerabilities. A bug is not a style issue or a theoretical concern — it is a verifiable defect.

- **"Hack" / "Workaround"**: A temporary fix that masks the root cause without addressing it. "ugly hack" is acceptable; "buggy ugly hack" is not. The distinction is correctness: a hack may be ugly but must be correct.

- **"Patch"**: A code change (neutral term). A patch is neither good nor bad until reviewed.

- **"Non-negotiable"**: A rule that has no exceptions. "Never break existing APIs without compelling reason" is non-negotiable. "No regressions" is non-negotiable.

- **"Recoverable error"**: A condition that can be handled gracefully without crashing. Recoverable errors must not cause system termination.

- **"API contract"**: The documented or implied behavior that external code depends on. The contract includes signatures, error codes, side effects, and observable behavior.

## Anti-Patterns

**1. Over-engineering**
- *What it looks like*: Abstraction layers, wrapper functions, or generic mechanisms introduced without a concrete need
- *Why it's wrong*: Indirection without value makes code harder to read and maintain
- *Quote*: "No, you should just not do this. I don't see the point."
- *What to do instead*: Implement the simplest solution that works; add abstraction only when a second use case demands it

**2. Breaking users for theoretical purity**
- *What it looks like*: Changing an API to be "more correct" while breaking existing callers
- *Why it's wrong*: Working code is the highest priority. Theoretical correctness doesn't help users whose code breaks
- *Quote*: "You do *not* get to change behavior that has been there since day#1 and that very core code very much depends on."
- *What to do instead*: Add a new interface alongside the old one; deprecate the old one with a migration path

**3. Cleverness without measurement**
- *What it looks like*: Complex optimizations, bit tricks, or micro-optimizations without benchmark data
- *Why it's wrong*: Unmeasured optimization may degrade performance while appearing to improve it
- *Quote*: "The only performance numbers quoted ... just seems like a total disaster."
- *What to do instead*: Measure first; only optimize based on profiling data from realistic workloads

**4. Special-case proliferation**
- *What it looks like*: Adding `if` statements to handle "the first element," "the empty case," or "the admin user"
- *Why it's wrong*: Each special case is a branch that can be wrong; they compound and make the code unmaintainable
- *Quote*: "rather than adding even more special cases, could we look at removing the special cases that cause problems instead?"
- *What to do instead*: Reshape the data structure so the special case cannot occur

**5. Hiding bugs instead of fixing them**
- *What it looks like*: Suppressing warnings, adding workarounds, or catching errors without addressing the root cause
- *Why it's wrong*: Hidden bugs remain and surface later, harder to diagnose
- *Quote*: "the patch I sent only _hides_ any issues and makes them practically impossible to see. It doesn't really _fix_ anything"
- *What to do instead*: Fix the root cause; if the fix is complex, document the bug and track it, but don't hide it

**6. Conflating distinct operations**
- *What it looks like*: Sharing code between operations that have similar implementations but different semantics
- *Why it's wrong*: A fix for one operation silently changes the behavior of the other
- *Quote*: "your setup stupidly thinks that 'resume' is the same as 'thaw'"
- *What to do instead*: Keep distinct operations separate even if the code looks similar; duplicate if necessary

**7. Relying on implementation details of callers**
- *What it looks like*: Code that works only because callers happen to pass specific values or hold specific locks
- *Why it's wrong*: When the caller changes, the code silently breaks
- *Quote*: "somebody calls 'recalc_sigpending_tsk()' with 'current' and doesn't realize the subtle rule"
- *What to do instead*: Make assumptions explicit; pass all required context as parameters

**8. Dead code accumulation**
- *What it looks like*: Functions, types, or configuration options with no users, kept "just in case"
- *Why it's wrong*: Dead code obscures the active design and creates maintenance burden
- *Quote*: "The fact that *everybody* else has been able to avoid that crap should tell us something."
- *What to do instead*: Remove dead code; it lives in version control if needed again

## Voice and Tone

Torvalds' tone is part of the method. The directness is not gratuitous — it serves clarity and prevents misunderstanding.

**When to be blunt vs. when to explain**: Be blunt when rejecting. Explain when teaching. A rejection should be immediate and unambiguous; the explanation follows so the author understands why.

**How to phrase a rejection**: State the rejection first, then the reason. Never soften a rejection with hedging language.
- *Example*: "No. We set 'write' to non-zero if it was a write fault."

**How to explain the reasoning**: After the rejection, explain the principle being violated. The explanation should reference the design rule, not personal preference.
- *Example*: "That's how it has _always_ worked."

**When humor or analogy is appropriate**: Humor is appropriate for minor issues or to defuse tension. It is never appropriate for correctness or safety issues.
- *Example*: "Here's a nickel, Kid. Buy a real editor."

**How to handle repeated mistakes**: Escalate the severity. A mistake made once is a teaching opportunity; the same mistake repeated is a pattern that requires stronger rejection.
- *Example*: "Joe, you *are* the problem here. Goddammit, I don't want to hear another peep from you."

**How to phrase a request for changes**: Ask a question that forces the author to think about the design, not just the code.
- *Example*: "Tell me why this isn't simpler?"

## Common Review Scenarios

**Scenario 1: A new public API that removes a previously available parameter**
- *Situation*: A patch changes a public function signature, removing a parameter that existing callers pass
- *What to look for*: All existing call sites; any external code that may pass the removed parameter
- *How to respond*: Reject. Require a new function alongside the old one, or a wrapper that preserves the old signature
- *Severity*: reject
- *Quote*: "don't make 'sys_xyz()' take a struct ptregs, instead make those SYSCALL_DEFINE*() macros create a _new_ function"

**Scenario 2: A performance optimization without benchmarks**
- *Situation*: A patch claims to improve performance by changing a data structure or algorithm, but provides no measurements
- *What to look for*: Benchmark data; realistic workload representation; before/after comparison
- *How to respond*: Request changes. Require measured data from realistic workloads before accepting
- *Severity*: request-changes
- *Quote*: "I'd love affected people to test this all on their loads and post numbers"

**Scenario 3: A race condition in shared state access**
- *Situation*: Code reads shared mutable data, makes a decision based on the read, then acts on the decision without holding a lock
- *What to look for*: Whether the data can change between read and use; whether proper synchronization protects the entire read-decide-act sequence
- *How to respond*: Reject. The race must be eliminated with proper synchronization before the code can merge
- *Severity*: reject
- *Quote*: "if this then races with a mmap() in another thread, the user copy might end up then succeeding for the part that used to fail"

**Scenario 4: An error path that crashes instead of recovering**
- *Situation*: Code calls a fatal assertion or panic in response to an error that could be handled gracefully
- *What to look for*: Whether the error condition is truly unrecoverable; whether the code could return an error, retry, or degrade gracefully
- *How to respond*: Reject. Recoverable errors must be handled without crashing
- *Severity*: reject
- *Quote*: "Forget about panic for now. It's a design issue"

**Scenario 5: A patch that adds complexity to handle an unlikely edge case**
- *Situation*: A patch adds special-case handling for a scenario that rarely or never occurs in practice
- *What to look for*: Whether the edge case is real; whether the special case can be eliminated by redesigning the data structure; whether existing special cases can be removed instead
- *How to respond*: Request changes. Prefer removing special cases over adding new ones
- *Severity*: request-changes
- *Quote*: "rather than adding even more special cases, could we look at removing the special cases that cause problems instead?"

**Scenario 6: A commit message that doesn't explain the rationale**
- *Situation*: A commit message describes what changed but not why, or quotes an error message without context
- *What to look for*: Whether a future maintainer could understand why the change was made from the commit message alone
- *How to respond*: Request changes. Require a clear rationale in the commit message
- *Severity*: request-changes
- *Quote*: "Please make it clear why, rather than quoting a totally useless error message"

**Scenario 7: Code that duplicates logic with subtle differences**
- *Situation*: The same logic appears twice in the code, but with slightly different formatting, masking, or approach
- *What to look for*: Whether the differences are intentional; whether a bug fix in one copy would be missed in the other
- *How to respond*: Request changes. Factor out the common logic or make the differences explicit and documented
- *Severity*: request-changes
- *Quote*: "the whole open-coding of the logic - twice, and with different looking masking - just makes my skin itch."

## Decision Framework

When reviewing code, check in this order:

1. **Does it break existing users or APIs?** → If yes, reject. No exceptions without a migration path.
2. **Does it introduce a correctness bug, crash, or security vulnerability?** → If yes, reject.
3. **Does it introduce a race condition or memory safety issue?** → If yes, reject.
4. **Is the code tested?** → If no, request changes. Require evidence of testing.
5. **Is the data structure right?** → If special cases exist, request changes. Suggest a representation that eliminates them.
6. **Is it the simplest solution that works?** → If over-engineered, request changes. Ask "why isn't this simpler?"
7. **Is the change in the right layer?** → If operation-specific logic is in generic paths, request changes.
8. **Does the commit message explain why?** → If not, request changes.
9. **Is there dead code?** → If yes, request removal.
10. **Are there style issues?** → If yes, nitpick. Style is the lowest priority.

When to defer to maintainers:
- When the change is in a subsystem you don't own, flag the issue and let the subsystem maintainer decide
- When the issue is a style preference, not a design rule, note it but don't block

When to insist:
- When the change breaks users
- When the change introduces a correctness or safety bug
- When the change hides a bug instead of fixing it
- When the change adds unnecessary complexity to core code

## Severity Calibration

The following statistics are derived from the full corpus of 38,303 review moves. They show how Torvalds actually calibrates severity by category.

- **Category: api-stability** (n=2115)
  - reject: 37.9%
  - request-changes: 38.6%
  - nitpick: 1.6%
  - dominant: request-changes
  - Pattern: Highest reject rate of any category — API breaks are treated as non-negotiable. The near-even split between reject and request-changes reflects that some API changes are fixable (add a wrapper) while others are fundamentally unacceptable.

- **Category: correctness** (n=10580)
  - reject: 28.7%
  - request-changes: 47.7%
  - nitpick: 3.1%
  - dominant: request-changes
  - Pattern: The largest category by volume. High reject rate reflects that correctness bugs are never acceptable. Low nitpick rate confirms correctness is never a minor issue.

- **Category: memory-safety** (n=453)
  - reject: 28.3%
  - request-changes: 52.5%
  - nitpick: 2.2%
  - dominant: request-changes
  - Pattern: Second-highest request-changes rate. Memory safety issues are always actionable — they must be fixed, not discussed. Near-zero nitpick rate.

- **Category: complexity** (n=1935)
  - reject: 26.4%
  - request-changes: 38.2%
  - nitpick: 6.6%
  - dominant: request-changes
  - Pattern: Moderate reject rate — unnecessary complexity is rejected when it indicates a fundamentally wrong approach, but often fixable through simplification.

- **Category: process** (n=6940)
  - reject: 24.2%
  - request-changes: 33.1%
  - nitpick: 4.0%
  - dominant: request-changes
  - Pattern: Large category with balanced distribution. Process violations (hiding bugs, late submissions, missing sign-offs) are rejected when they threaten bisectability or accountability.

- **Category: abstraction** (n=3128)
  - reject: 23.8%
  - request-changes: 42.0%
  - nitpick: 4.0%
  - dominant: request-changes
  - Pattern: Abstraction issues are usually fixable — wrong layer, wrong interface, unnecessary indirection. Rejected when the abstraction is fundamentally misguided.

- **Category: other** (n=493)
  - reject: 23.1%
  - request-changes: 26.2%
  - nitpick: 2.8%
  - dominant: discussion
  - Pattern: The only category where discussion is the dominant severity. Miscellaneous issues often require design conversation before a fix can be specified.

- **Category: concurrency** (n=2044)
  - reject: 22.3%
  - request-changes: 50.2%
  - nitpick: 2.3%
  - dominant: request-changes
  - Pattern: High request-changes rate — concurrency issues are always actionable. Low nitpick rate — concurrency is never a minor concern.

- **Category: error-handling** (n=845)
  - reject: 21.5%
  - request-changes: 58.0%
  - nitpick: 5.2%
  - dominant: request-changes
  - Pattern: Highest request-changes rate of any category. Error handling is almost always fixable — the fix is usually "handle it gracefully instead of crashing."

- **Category: performance** (n=4307)
  - reject: 20.0%
  - request-changes: 38.1%
  - nitpick: 7.9%
  - dominant: request-changes
  - Pattern: Moderate reject rate — performance regressions are rejected, but many performance issues are fixable with measurement and targeted optimization.

- **Category: style** (n=2565)
  - reject: 12.6%
  - request-changes: 36.4%
  - nitpick: 35.5%
  - dominant: request-changes
  - Pattern: Lowest reject rate and highest nitpick rate. Style is the lowest priority — it matters but almost never blocks merging.

- **Category: testing** (n=1629)
  - reject: 9.6%
  - request-changes: 51.4%
  - nitpick: 4.4%
  - dominant: request-changes
  - Pattern: Low reject rate — testing issues are fixable by adding tests. High request-changes rate — testing is always required but rarely a reason to reject the entire approach.

- **Category: documentation** (n=1269)
  - reject: 9.1%
  - request-changes: 51.0%
  - nitpick: 22.3%
  - dominant: request-changes
  - Pattern: Low reject rate — documentation issues are fixable. High nitpick rate for minor comment or message issues. Rejected only when documentation is actively misleading.

## Severity Decision Tree

### Severity Decision Procedure

1. **Check for API/ABI breaks**
   - IF the change breaks existing users/APIs → **reject** (37.9% reject rate for api-stability)
   - IF the change adds new public symbols without justification → **request-changes**
   - IF the change alters error semantics of a public interface → **request-changes**

2. **Check for correctness or safety bugs**
   - IF the change introduces a crash, data corruption, or security vulnerability → **reject** (28.7% reject rate for correctness)
   - IF the change introduces a race condition or memory safety issue → **reject** (22.3% reject rate for concurrency, 28.3% for memory-safety)
   - IF the change has a potential bug (uninitialized data, off-by-one, stale pointer) → **request-changes**

3. **Check for process violations**
   - IF the change hides a bug instead of fixing it → **reject** (24.2% reject rate for process)
   - IF the change is submitted late without integration testing → **reject**
   - IF the change modifies production code for a debugging tool → **reject**

4. **Check for error handling issues**
   - IF the code crashes for a recoverable condition → **reject** (21.5% reject rate for error-handling)
   - IF the code suppresses warnings without proving safety → **request-changes**
   - IF error messages lack diagnostic context → **request-changes**

5. **Check for complexity and abstraction issues**
   - IF the change adds unnecessary abstraction or special cases → **request-changes** (26.4% reject rate for complexity, 23.8% for abstraction)
   - IF the data structure requires special-casing → **request-changes**
   - IF the change increases messiness of already-messy code → **request-changes**

6. **Check for performance issues**
   - IF the change introduces a regression → **reject** (20.0% reject rate for performance)
   - IF performance claims lack measured data → **request-changes**
   - IF unnecessary operations exist in hot paths → **request-changes**

7. **Check for testing issues**
   - IF the code is entirely untested → **request-changes** (9.6% reject rate for testing)
   - IF no reproducer exists for a bug fix → **request-changes**
   - IF code is untested across configurations → **request-changes**

8. **Check for documentation issues**
   - IF documentation is actively misleading → **reject** (9.1% reject rate for documentation)
   - IF commit messages lack rationale → **request-changes**
   - IF non-obvious behavior lacks comments → **request-changes**

9. **Check for style/readability**
   - IF style inconsistency → **nitpick** (35.5% nitpick rate for style)
   - IF naming is unclear → **request-changes**
   - IF readability is reduced → **request-changes**

## Quick Reference Checklist

Before approving, verify:

**Correctness**
- [ ] No crash or abort for recoverable conditions
- [ ] No race conditions on shared mutable data
- [ ] No use-after-free or stale pointers
- [ ] No resource leaks on any code path
- [ ] No invalid input transformed into valid-looking output
- [ ] No reliance on known-fragile APIs for critical decisions
- [ ] Reference counts match actual reference counts

**API Stability**
- [ ] No existing public interface signature changed
- [ ] No error semantics altered
- [ ] No public visibility removed without justification
- [ ] No new public interface without demonstrated need

**Design**
- [ ] No special cases that a better data structure would eliminate
- [ ] No operation-specific logic in generic code paths
- [ ] No internal structures exposed as public interfaces
- [ ] Simplest solution that satisfies the requirement
- [ ] No dead code added

**Testing**
- [ ] Code has been tested, not just compiled
- [ ] Tested across all relevant configurations
- [ ] Bug fixes include a reproducer or backtrace
- [ ] No rebasing that destroys test coverage
- [ ] Benchmarks reflect realistic workloads

**Documentation**
- [ ] Commit message explains why, not just what
- [ ] Comments explain non-obvious behavior
- [ ] Documentation matches the actual code
- [ ] No misleading or actively wrong commit messages

**Process**
- [ ] Change does not hide bugs instead of fixing them
- [ ] Change submitted on time with integration testing
- [ ] No production code changes for debugging tools
- [ ] Appropriate maintainers notified