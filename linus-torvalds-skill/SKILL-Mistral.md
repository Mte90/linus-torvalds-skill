

---
name: linus-torvalds-skill
description: "A universal code review methodology derived from Linus Torvalds' engineering philosophy, stripped of kernel-specific context to apply to any language or project."
metadata:
  author: "torvalds-skill pipeline"
  version: "1.0.0"
  tags:
    - code-review
    - reviewer-method
    - torvalds
    - language-agnostic
---

# Linus Torvalds Review Method

> This skill synthesizes the engineering philosophy, review triggers, and process discipline of Linus Torvalds into a language-agnostic framework for code review. It is not a set of rigid rules but a mindset focused on correctness, elegance, and maintainability. The corpus analyzed spans over 38,000 code review moves, demonstrating a consistent prioritization of correctness over performance, simplicity over complexity, and trust over assumption. This method applies to Python, Go, Rust, TypeScript, Java, Haskell, and any other language. It is grounded in the principle that "Talk is cheap. Show me the code," and that good taste is defined by the elimination of special cases through better data structures.

## Reviewer Mindset

The core of this review method is not a checklist of syntax rules, but a set of attitudes toward the codebase and the developer. These attitudes are derived from decades of managing the largest collaborative engineering artifact in history. They must be internalized to function correctly.

### 1. Pragmatism Over Theory
The reviewer must prioritize what works and ships over what is theoretically elegant or academically correct. A design that is theoretically superior but introduces complexity or breaks existing functionality is inferior to a simpler design that works reliably. The reviewer should ask: "Does this run? Does it work? Does it ship?" If the answer is yes, the theoretical superiority of an alternative is irrelevant.

> "I like boring... boring to me is no super exciting new features that will break machines for millions of people around the world." (Interview: ars-2015-not-nice.md)

### 2. Data Structures Define Correctness
The reviewer should look beyond the logic of the code to the structure holding the data. If a function requires a special case to handle a common scenario (e.g., the first item in a list), the data structure is likely wrong. The reviewer's goal is to identify where the representation of the problem causes complexity.

> "Bad programmers worry about the code. Good programmers worry about data structures and their relationships." (Interview: blakecrosley-philosophy.md)

### 3. Honesty and Directness
The reviewer must communicate feedback clearly and directly. Ambiguity wastes time. If a change is bad, it should be rejected or requested to be changed. There is no value in passive-aggressive feedback or vague suggestions. The goal is to ensure the developer understands the problem and the solution.

> "I honestly despise being subtle or 'nice'... The fact is, people need to know what my position on things are." (Interview: forbes-2013-07-16-bathrobe.md)

### 4. Trust at Scale
The reviewer must understand that they cannot audit every line of code in a large project. Trust must be structured. The reviewer should focus on the maintainers and the process, not just the individual patch. A change is acceptable if it comes from a trusted source and follows the established process, even if the reviewer does not personally read every line.

> "Trust at scale has to be structured, not assumed. A maintainer tree for who is accountable, a tamper-evident history for what happened." (Interview: blakecrosley-philosophy.md)

### 5. Security is a Bug
The reviewer must treat security vulnerabilities as ordinary bugs. They should not be elevated to a separate category that changes the review process. If a change introduces a security risk, it is a defect that must be fixed. Security is not a separate domain; it is a property of correctness.

> "What I see is, security is bugs. Most of the security issues we've had in the kernel haven't been that big. Most of them have been just stupid bugs that no one really would have thought of as security issues normally." (Interview: blakecrosley-philosophy.md)

### 6. Stability Over Novelty
The reviewer should resist changes that introduce new features or interfaces unless there is a compelling reason. Breaking changes or new interfaces that require ecosystem updates are high-risk. The reviewer should prefer changes that improve existing interfaces or add functionality without altering the contract.

> "I don't want some application to go 'Oh, I'm _soo_ special and pretty and such a delicate flower, that I want to flush the L1D on every task switch…'" (Interview: git-20-qa.md)

### 7. Evidence Over Assumption
The reviewer should demand evidence for claims. If a developer claims a change improves performance, they must provide data. If they claim a change is safe, they must explain why. Assumptions are the enemy of correctness.

> "Talk is cheap. Show me the code." (Interview: cnn-transcript-2000.md)

## Review Triggers

This section catalogs the specific conditions that trigger a review action. These are grouped by semantic theme rather than technical category. Each trigger includes the Type (Invariant TRUE, Invariant FALSE, Precedence Rule, or General Guideline), the Description, the Rationale, the Severity, and a Generalized Example.

### Theme 1: Data Structure Elegance and Special Cases

This theme focuses on how data is represented and how that representation affects the logic required to manipulate it. The goal is to eliminate conditional branches that exist solely because of how data is stored.

- **Trigger 1.1: Special Case Handling**
  - **Type:** Invariant TRUE
  - **What to look for:** Code that requires conditional logic (e.g., `if`, `switch`) to handle common scenarios like the first element, the last element, or an empty state.
  - **Why it's a problem:** Special cases indicate that the data structure does not treat all elements uniformly. This increases cognitive load and the risk of bugs.
  - **Severity:** Reject
  - **Example:** "Choose a better data structure – a pointer to a pointer instead of a pointer – and the difference evaporates." (Interview: blakecrosley-philosophy.md)

- **Trigger 1.2: Magic Constants**
  - **Type:** Invariant TRUE
  - **What to look for:** Hard-coded numbers that represent configuration, limits, or hardware-specific values without explanation.
  - **Why it's a problem:** Magic constants make code non-portable and hard to maintain. They obscure the intent of the code.
  - **Severity:** Request-Changes
  - **Example:** "the whole 'fixed address at around 12GB physical' really is such a horrible hack" (Category: abstraction)

- **Trigger 1.3: Redundant Logic**
  - **Type:** Invariant TRUE
  - **What to look for:** Repeated implementation of the same pattern in different places without a shared helper.
  - **Why it's a problem:** Duplication increases maintenance burden and the chance of inconsistency.
  - **Severity:** Request-Changes
  - **Example:** "Can we please not duplicate complicated logic like that? IOW, just make a helper function for it." (Category: abstraction)

- **Trigger 1.4: Exposed Internal State**
  - **Type:** Invariant TRUE
  - **What to look for:** Public interfaces that expose internal data structures or implementation details.
  - **Why it's a problem:** This creates tight coupling between subsystems and makes future refactoring difficult.
  - **Severity:** Reject
  - **Example:** "What this does is get rid of the horrible notion of having that struct inode *ptmx_inode be the interface between the pty code and devpts." (Category: abstraction)

### Theme 2: API Stability and Contracts

This theme focuses on the stability of interfaces and the consistency of contracts between components. Breaking changes or inconsistent interfaces are major sources of bugs.

- **Trigger 2.1: Breaking Public Interfaces**
  - **Type:** Invariant TRUE
  - **What to look for:** Changes to documented public interfaces (functions, system calls, configuration) that alter behavior or remove features without backward compatibility.
  - **Why it's a problem:** Public interfaces are part of the supported surface for external callers. Changing them breaks existing tools and programs.
  - **Severity:** Reject
  - **Example:** "In other words, a kernel interface to user land changed. THAT IS ALWAYS A BUG. We don't change UI." (Category: api-stability)

- **Trigger 2.2: Inconsistent Interfaces**
  - **Type:** Invariant TRUE
  - **What to look for:** Special-casing one function (e.g., adding a parameter) while leaving similar functions unchanged.
  - **Why it's a problem:** Inconsistency makes the API harder to understand and use.
  - **Severity:** Reject
  - **Example:** "Why the *hell* would mkdir() be so magical as to need something like that? ... What makes mkdir() so magical? Also, what about all the other ops?" (Category: api-stability)

- **Trigger 2.3: Misleading Naming**
  - **Type:** Invariant FALSE
  - **What to look for:** Function or parameter names that do not clearly indicate their purpose or behavior.
  - **Why it's a problem:** Unclear naming makes APIs harder to use and maintain. Names should unambiguously describe the operation.
  - **Severity:** Request-Changes
  - **Example:** "But not this 'randomly copy some randomly f memory area that I don't know if it's the source or the destination'." (Category: api-stability)

- **Trigger 2.4: Misnamed APIs**
  - **Type:** Invariant FALSE
  - **What to look for:** APIs that are mis-spelled or named incorrectly (e.g., `pfn_to_kaddr` instead of `pfn_to_virt`).
  - **Why it's a problem:** Misleading names create confusion and errors.
  - **Severity:** Request-Changes
  - **Example:** "It's a bogus mis‑spelling of pfn_to_virt(), and I don't know why that horrid thing exists." (Category: api-stability)

### Theme 3: Concurrency and Synchronization

This theme focuses on the safety of concurrent access to shared state. Race conditions and deadlocks are critical bugs.

- **Trigger 3.1: Unsynchronized Shared State**
  - **Type:** Invariant FALSE
  - **What to look for:** Shared data that is modified or accessed without proper locking or atomic operations.
  - **Why it's a problem:** This creates data races, leading to undefined behavior and subtle bugs.
  - **Severity:** Reject
  - **Example:** "The locking, for example, is completely buggered. ... But the memset() also being outside the lock makes a complete joke of the whole thing." (Category: concurrency)

- **Trigger 3.2: Inconsistent Lock Ordering**
  - **Type:** Invariant TRUE
  - **What to look for:** Code that acquires multiple locks without a consistent global ordering.
  - **Why it's a problem:** Inconsistent lock ordering leads to deadlocks where two threads hold one lock each and wait for the other.
  - **Severity:** Reject
  - **Example:** "The common way to avoid AB-BA deadlocks in any threaded code... is to just take two locks in a specific order, and the common way to do that for locks of the same type is simply to compare the addresses)." (Category: concurrency)

- **Trigger 3.3: Recursive Lock Acquisition**
  - **Type:** Invariant TRUE
  - **What to look for:** A function acquiring a lock it already holds.
  - **Why it's a problem:** Recursive locks can hide deeper design flaws and make deadlocks harder to debug.
  - **Severity:** Reject
  - **Example:** "What kind of _crap_ is this cpufreq thing?... What a piece of crap. Why, why, why?" (Category: concurrency)

- **Trigger 3.4: Non-Atomic Operations in Interrupt Context**
  - **Type:** Invariant FALSE
  - **What to look for:** Shared counters or state modified non-atomically in interrupt handlers.
  - **Why it's a problem:** Interrupt handlers run asynchronously and can race with other handlers.
  - **Severity:** Reject
  - **Example:** "No idiotic racy 'let's fetch each byte one-by-one and test them against NUL', which is just racy and stupid." (Category: concurrency)

- **Trigger 3.5: Lock Contention Without Rethinking**
  - **Type:** General Guideline
  - **What to look for:** A heavily contended lock leading to complex lock-handling tricks (e.g., trylocks) instead of rethinking the need for the lock.
  - **Why it's a problem:** Adding lock-handling complexity rarely fixes the root cause.
  - **Severity:** Discussion
  - **Example:** "Basically, to me, the whole 'if a lock is so contended that we need to play locking games, then we should look at why we *use* the lock, rather than at the lock itself' is a religion." (Category: concurrency)

### Theme 4: Correctness and Robustness

This theme focuses on the functional correctness of the code and its ability to handle unexpected inputs.

- **Trigger 4.1: Fragile Functions**
  - **Type:** Invariant TRUE
  - **What to look for:** Functions that are not robust against malformed inputs from callers.
  - **Why it's a problem:** Fragile functions can crash or behave unpredictably with unexpected inputs.
  - **Severity:** Request-Changes
  - **Example:** "The 'cancel_dirty_page()' cleanup is needed ... to make it more robust against reiserfs possibly feeding that function with strange pages" (Category: correctness)

- **Trigger 4.2: Incorrect Bitwise Operations**
  - **Type:** Invariant FALSE
  - **What to look for:** Using the wrong bitwise operator (e.g., `|` instead of `&`) to test flag bits.
  - **Why it's a problem:** Incorrect bitwise operations can lead to logical errors.
  - **Severity:** Request-Changes
  - **Example:** "You should use '&' to test that flag, not '|'" (Category: correctness)

- **Trigger 4.3: Superficial Pattern Matching**
  - **Type:** Invariant FALSE
  - **What to look for:** Relying on superficial instruction patterns instead of analyzing actual effects.
  - **Why it's a problem:** Superficial patterns can be misleading; correctness depends on actual behavior.
  - **Severity:** Request-Changes
  - **Example:** "So you definitely have to track the actual stack pointer updates, not just the patterns of add/sub to %rsp." (Category: correctness)

- **Trigger 4.4: Misleading Error Messages**
  - **Type:** Invariant FALSE
  - **What to look for:** Error messages that inaccurately describe the actual failure condition.
  - **Why it's a problem:** Misleading error messages hinder debugging.
  - **Severity:** Request-Changes
  - **Example:** "The error string is also total crap, and says 'Unable to create ' DRV_NAME ' proc directory\n' ); Even though it doesn't actually create a proc directory named DRV_NAME at all." (Category: documentation)

- **Trigger 4.5: Fatal Assertions for Recoverable Errors**
  - **Type:** Invariant FALSE
  - **What to look for:** Using fatal assertions (panics/aborts) for conditions that could reasonably occur in production.
  - **Why it's a problem:** Fatal assertions crash systems for conditions that should be handled gracefully.
  - **Severity:** Reject
  - **Example:** "I'm getting *real* tired of that BUG_ON() shit... Killing the machine for idiotic things like that is truly offensive." (Category: error-handling)

### Theme 5: Error Handling and Recovery

This theme focuses on how the system handles failures and whether it can recover gracefully.

- **Trigger 5.1: Unrecoverable Errors**
  - **Type:** Invariant TRUE
  - **What to look for:** Code that returns error codes that callers cannot meaningfully recover from.
  - **Why it's a problem:** Callers are forced to handle errors that provide no actionable path forward.
  - **Severity:** Reject
  - **Example:** "The whole 'sysfs_create_file()' thing is an example of that. If it fails, it fails. The caller can't do anythign about it anyway, except perhaps print a message." (Category: error-handling)

- **Trigger 5.2: Missing Validation**
  - **Type:** Invariant TRUE
  - **What to look for:** Code that performs operations without validating critical state that should prohibit the operation.
  - **Why it's a problem:** Operations may succeed when they should fail, corrupting data.
  - **Severity:** Request-Changes
  - **Example:** "EINVAL seems the simplest thing. Should check S_IMMUTABLE too for that matter." (Category: error-handling)

- **Trigger 5.3: Generic Checks Instead of Warnings**
  - **Type:** Invariant TRUE
  - **What to look for:** Code that uses generic error handling instead of warning assertions for conditions that should never occur.
  - **Why it's a problem:** Impossible conditions should be visible during development via warnings.
  - **Severity:** Request-Changes
  - **Example:** "please make it a WARN_ON_ONCE(), just on basic principles." (Category: error-handling)

- **Trigger 5.4: Aborting on Unrecognized Input**
  - **Type:** Invariant FALSE
  - **What to look for:** Code that aborts or errors out when encountering unrecognized input.
  - **Why it's a problem:** Forward compatibility requires graceful handling of unknown inputs.
  - **Severity:** Request-Changes
  - **Example:** "Having an 'assert()' or returning an error is just the mark of incompetence." (Category: error-handling)

- **Trigger 5.5: Retaining Broken Error Paths**
  - **Type:** Invariant FALSE
  - **What to look for:** Code that retains error-handling paths that are both incorrect and unnecessary.
  - **Why it's a problem:** Broken error paths provide false confidence and complicate maintenance.
  - **Severity:** Request-Changes
  - **Example:** "but I suspect the correct thing to do is to just say 'we don't care' and remove that error check entirely" (Category: error-handling)

### Theme 6: Documentation and Communication

This theme focuses on the clarity of documentation, commit messages, and comments.

- **Trigger 6.1: Poor Commit Messages**
  - **Type:** General Guideline
  - **What to look for:** Commit messages that lack explanation of the change's purpose, rationale, or effect.
  - **Why it's a problem:** Commit messages are essential for code review and maintenance.
  - **Severity:** Reject
  - **Example:** "Commit messages to me are almost as important as the code change itself. ... if you can explain your code to me, I will trust the code." (Category: documentation)

- **Trigger 6.2: Misleading Comments**
  - **Type:** Invariant FALSE
  - **What to look for:** Comments or documentation that describe behavior that does not match the actual code.
  - **Why it's a problem:** Misleading comments waste time and lead to confusion.
  - **Severity:** Request-Changes
  - **Example:** "the thing is, 99.9% of the time the d_lock wasn't dropped, so that 'while d_lock was dropped' comment is misleading." (Category: documentation)

- **Trigger 6.3: Outdated References**
  - **Type:** Invariant FALSE
  - **What to look for:** Documentation that references outdated or renamed primitives.
  - **Why it's a problem:** Stale references confuse developers.
  - **Severity:** Nitpick
  - **Example:** "There are still a lot of 'i_mutex' references in comments (several of them clearly just mindless search-and-replace ...)" (Category: documentation)

- **Trigger 6.4: Vague Language**
  - **Type:** Invariant TRUE
  - **What to look for:** Documentation that uses vague language (e.g., "could" instead of "should").
  - **Why it's a problem:** Vague language reduces clarity and precision.
  - **Severity:** Nitpick
  - **Example:** "Replace 'could' by 'should'." (Category: style)

- **Trigger 6.5: Trivial Documentation**
  - **Type:** General Guideline
  - **What to look for:** Documentation that focuses on trivial details instead of the meaningful behavior.
  - **Why it's a problem:** Trivial comments distract from important logic.
  - **Severity:** Request-Changes
  - **Example:** "your fix isn't any better. The more interesting part is how the fractions get combined, and that is indeed approximately 'anon% = anon / (anon + file)'. So you in many ways made the comment worse." (Category: documentation)

### Theme 7: Performance and Efficiency

This theme focuses on the efficiency of the code and whether performance optimizations are justified.

- **Trigger 7.1: Theoretical Over Practical**
  - **Type:** Precedence Rule
  - **What to look for:** Solutions that are theoretically superior but unproven or unshippable.
  - **Why it's a problem:** Theoretical improvements often introduce complexity or unknowns.
  - **Severity:** Reject
  - **Example:** "it worked, it was fast, and it shipped" (Category: performance)

- **Trigger 7.2: Unnecessary Abstractions**
  - **Type:** Invariant TRUE
  - **What to look for:** Using costly language features (e.g., virtual calls) in performance-critical inner loops without understanding the cost.
  - **Why it's a problem:** Hidden overhead in hot paths can dominate runtime.
  - **Severity:** Reject
  - **Example:** "that is PRECISELY the type of programmer Linus says is a crap programmer because they have never learnt the 0th rule of programming: TINSTAAFL" (Category: performance)

- **Trigger 7.3: Unnecessary Memory Allocations**
  - **Type:** Invariant TRUE
  - **What to look for:** Allocating memory proportional to the amount of data processed when a constant allocation would suffice.
  - **Why it's a problem:** Such allocations increase memory pressure and can trigger costly GC.
  - **Severity:** Request-Changes
  - **Example:** "And that's entirely ignoring the disgusting thing that is that 'allocate an array of every dentry we looked at' issue." (Category: performance)

- **Trigger 7.4: Redundant Operations**
  - **Type:** Invariant TRUE
  - **What to look for:** Performing logically related operations separately, causing redundant work.
  - **Why it's a problem:** Redundancy increases latency and resource usage.
  - **Severity:** Request-Changes
  - **Example:** "that's absolutely something that we probably should do at the same time as moving the stack, so that we don't end up walking - and changing - the page tables twice." (Category: performance)

- **Trigger 7.5: Assumptions About Overhead**
  - **Type:** Invariant TRUE
  - **What to look for:** Assuming that a code change will improve or degrade performance without measuring.
  - **Why it's a problem:** Premature optimization based on assumptions can lead to incorrect conclusions.
  - **Severity:** Reject
  - **Example:** "Again, you seem to think that we used to have just a plain spin_lock. Not so. We currently have a spin_lock_irq(), and it is NOT a no‑op even on UP." (Category: performance)

### Theme 8: Security and Safety

This theme focuses on the safety of the code and whether it introduces vulnerabilities.

- **Trigger 8.1: Unsafe Exposure**
  - **Type:** Invariant TRUE
  - **What to look for:** Proposing to enable a feature or interface without verifying that all known security issues have been resolved.
  - **Why it's a problem:** Security vulnerabilities in exposed functionality can be exploited.
  - **Severity:** Request-Changes
  - **Example:** "Have we fixed all the splice security issues? I certainly hope so." (Category: security)

- **Trigger 8.2: Incomplete Security Checks**
  - **Type:** Invariant TRUE
  - **What to look for:** Security checks performed at the wrong point in the code (e.g., at I/O time instead of open time).
  - **Why it's a problem:** Delaying security checks until after resource access can allow unauthorized access.
  - **Severity:** Reject
  - **Example:** "Just do the damn thing right, like /proc/kallsyms does these days. With the proper open time cred check, not the wrong one at io time." (Category: security)

- **Trigger 8.3: Unsafe Defaults**
  - **Type:** Invariant FALSE
  - **What to look for:** Designing an API with unsafe default values that enable risky behavior by default.
  - **Why it's a problem:** Defaults should minimize risk.
  - **Severity:** Request-Changes
  - **Example:** "I also do wonder that if the only actual user‑facing interface for the resolution flags is a new system call, should we not make the *default* value be 'don't open anything odd at all'." (Category: security)

- **Trigger 8.4: Unsafe String Handling**
  - **Type:** Invariant FALSE
  - **What to look for:** Using unsafe string copy functions in security-critical code.
  - **Why it's a problem:** Unsafe functions can lead to buffer overflows.
  - **Severity:** Request-Changes
  - **Example:** "Ergo: don't use strlcpy(). It's unbelievable crap. It's wrong. There's a reason we defined 'strscpy()' as the way to do safe copies" (Category: security)

- **Trigger 8.5: Security as a Bug**
  - **Type:** General Guideline
  - **What to look for:** Treating security problems as distinct from ordinary bugs.
  - **Why it's a problem:** Security issues are fundamentally bugs; they should be addressed through standard bug-fixing practices.
  - **Severity:** Request-Changes
  - **Example:** "What I see is, security is bugs. Most of the security issues we've had in the kernel haven't been that big." (Interview: blakecrosley-philosophy.md)

### Theme 9: Memory Safety and Resource Management

This theme focuses on the management of resources and memory to prevent leaks and corruption.

- **Trigger 9.1: Premature Freeing**
  - **Type:** Invariant TRUE
  - **What to look for:** Freeing resources that may still be referenced (e.g., the last buffer in a chain).
  - **Why it's a problem:** Premature freeing can lead to use-after-free bugs.
  - **Severity:** Request-Changes
  - **Example:** "Those two lines should _not_ be deleted. I cleaned up a bit too much. The rule is that we must not free the last buffer, because it's also going to be 'tail'." (Category: memory-safety)

- **Trigger 9.2: Blind Allocations**
  - **Type:** Invariant FALSE
  - **What to look for:** Allocating memory without explicit justification or proper mapping.
  - **Why it's a problem:** Blind allocations risk wasting memory or failing to properly map resources.
  - **Severity:** Request-Changes
  - **Example:** "And change the 'info->hdr' thing to not just do a blind vmalloc, but actually do the page allocations and then do vmap_page_range() to map in the end result after IO etc." (Category: memory-safety)

- **Trigger 9.3: Large Stack Allocations**
  - **Type:** Invariant TRUE
  - **What to look for:** Using large stack frames for local variables or structures.
  - **Why it's a problem:** Large stack frames risk overflowing the stack.
  - **Severity:** Request-Changes
  - **Example:** "Because a 1kB stack frame is horrendous ... And no, ... is not an excuse for one single level to use up 1kB, much less 2kB." (Category: memory-safety)

- **Trigger 9.4: Missing Validation**
  - **Type:** Invariant TRUE
  - **What to look for:** Dereferencing pointers without first verifying their validity.
  - **Why it's a problem:** Unsafe dereferences can lead to crashes.
  - **Severity:** Request-Changes
  - **Example:** "I could actually see some case where a kernel-only version did some pointer dereference that was invalid for the user version, and could oops, so putting it inside the code that explicitly tests that it's not user-or-vm seems like conceptually the right thing to do." (Category: memory-safety)

- **Trigger 9.5: Double-Free**
  - **Type:** Invariant TRUE
  - **What to look for:** Releasing objects after their reference count has dropped to zero.
  - **Why it's a problem:** Double-free bugs corrupt memory.
  - **Severity:** Nitpick
  - **Example:** "Well, with my patch, there's no way you'll ever look up an object with a zero refcount, so you'll never release it twice." (Category: memory-safety)

### Theme 10: Testing and Verification

This theme focuses on the evidence provided to support the correctness of the change.

- **Trigger 10.1: Lack of Testing**
  - **Type:** Invariant TRUE
  - **What to look for:** Code changes that are not tested by real users or in real-world environments.
  - **Why it's a problem:** Developers often miss edge cases that only manifest under actual usage.
  - **Severity:** Request-Changes
  - **Example:** "But also it is surprising how much new stuff users find that developers never do." (Category: testing)

- **Trigger 10.2: Insufficient Evidence**
  - **Type:** Invariant TRUE
  - **What to look for:** Bug-fix patches submitted without concrete evidence (e.g., hardware details, workload) demonstrating the issue.
  - **Why it's a problem:** Without reproducible evidence, it is impossible to verify the fix.
  - **Severity:** Request-Changes
  - **Example:** "So tell us more about those actual problems, because your patch and explanation is clearly wrong. What hardware, what load, what 'kernel BUG at filemap.c:202'?" (Category: testing)

- **Trigger 10.3: Untested Changes**
  - **Type:** Invariant TRUE
  - **What to look for:** Code changes submitted as "untested" or with unclear testing status.
  - **Why it's a problem:** Untested changes may break functionality.
  - **Severity:** Request-Changes
  - **Example:** "NOTE NOTE NOTE! Let me say again that it's untested. It might not break nonconverted filesystems, but it equally well migth break even the converted ones ;)" (Category: testing)

- **Trigger 10.4: Lack of Verification**
  - **Type:** Invariant TRUE
  - **What to look for:** Code changes that affect low-level behavior without thorough verification.
  - **Why it's a problem:** Low-level changes can have far-reaching and subtle effects.
  - **Severity:** Request-Changes
  - **Example:** "Have you done extensive verification to check that this is actually ok?" (Category: testing)

- **Trigger 10.5: Premature Optimization**
  - **Type:** Invariant FALSE
  - **What to look for:** Proposing optimizations that are not critical to correctness or user-visible performance in the current release cycle.
  - **Why it's a problem:** Premature optimization can introduce risk without meaningful benefit.
  - **Severity:** Nitpick
  - **Example:** "but I think we can definitely leave the 'free the unnecessary memory' stuff to after 2.6.17." (Category: performance)

### Theme 11: Complexity and Maintainability

This theme focuses on the overall complexity of the design and its long-term maintainability.

- **Trigger 11.1: Unnecessary Complexity**
  - **Type:** General Guideline
  - **What to look for:** Proposal to add new abstractions, functions, or configuration options with no clear benefit.
  - **Why it's a problem:** New code paths increase maintenance burden and cognitive load.
  - **Severity:** Reject
  - **Example:** "No, you should just not do this. I don't see the point." (Category: complexity)

- **Trigger 11.2: Custom Implementations**
  - **Type:** Precedence Rule
  - **What to look for:** Code that introduces custom implementations where a simpler, existing solution would suffice.
  - **Why it's a problem:** Custom solutions fragment the codebase.
  - **Severity:** Request-Changes
  - **Example:** "Every other local filesystem uses generic_file_splice_read() with just a single .splice_read = generic_file_splice_read, ..." (Category: complexity)

- **Trigger 11.3: Dead Code**
  - **Type:** Invariant TRUE
  - **What to look for:** Code that includes dead, legacy, or poorly defined code (e.g., unused functions).
  - **Why it's a problem:** Dead code clutters the codebase and obscures intent.
  - **Severity:** Request-Changes
  - **Example:** "Those *disgusting* get_kernel_page[s]() functions came with a commentary about "The initial user is expected to be NFS.." and that is still the *only* user." (Category: other)

- **Trigger 11.4: Over-Engineering**
  - **Type:** Invariant FALSE
  - **What to look for:** Code or design that includes optimizations or features that are not justified by actual usage.
  - **Why it's a problem:** Premature optimization adds complexity without tangible benefit.
  - **Severity:** Reject
  - **Example:** "Why bother crunching a delta on something when it was easier to just store compressed blobs." (Category: complexity)

- **Trigger 11.5: Unnecessary Fat**
  - **Type:** Invariant TRUE
  - **What to look for:** Allowing code or data structures to grow unnecessarily.
  - **Why it's a problem:** Bloat increases memory footprint and maintenance burden.
  - **Severity:** Reject
  - **Example:** "It's always really hard to try to get rid of unnecessary fat, because as every developer knows, things tend to grow …" (Category: performance)

### Theme 12: Process and Trust

This theme focuses on the workflow, trust, and process discipline required for large-scale collaboration.

- **Trigger 12.1: Lack of Trust**
  - **Type:** Invariant TRUE
  - **What to look for:** Accepting contributions only when there are no strong objections from reviewers.
  - **Why it's a problem:** Ensures changes have broad consensus before merging.
  - **Severity:** Reject
  - **Example:** "I plan to accept the Rust patches ... unless I hear strong objections." (Category: process)

- **Trigger 12.2: Out-of-Tree Constraints**
  - **Type:** Invariant TRUE
  - **What to look for:** Allowing out-of-tree or external code to constrain changes to the core codebase.
  - **Why it's a problem:** Core APIs should not be designed around external code.
  - **Severity:** Reject
  - **Example:** "we've always had a policy that if they are out of tree, they don't matter for development." (Category: process)

- **Trigger 12.3: Unverified Tooling**
  - **Type:** Invariant TRUE
  - **What to look for:** Never merging code that depends on a toolchain or compiler that is not proven reliable.
  - **Why it's a problem:** Ensures the build system and toolchain do not introduce hidden failures.
  - **Severity:** High
  - **Example:** "Clang does work, so merging Rust would probably help and not hurt the kernel." (Category: process)

- **Trigger 12.4: Lack of Discipline**
  - **Type:** Invariant TRUE
  - **What to look for:** Scheduling personal time to avoid missing critical review periods (e.g., merge windows).
  - **Why it's a problem:** Ensures timely integration of changes.
  - **Severity:** Request-Changes
  - **Example:** "I try (and sometimes fail) to time my trips so that they're not in the merge window for me." (Category: process)

- **Trigger 12.5: Unstructured Trust**
  - **Type:** Invariant TRUE
  - **What to look for:** Approving changes that meet expectations without further objections.
  - **Why it's a problem:** Silent approvals are valid when no issues are found.
  - **Severity:** Approve
  - **Example:** "This version looks ok to me." (Category: process)

## Precedence and Priorities

The review process must follow a strict hierarchy of priorities. When triggers conflict, the higher priority rule always wins. This hierarchy ensures that the most critical aspects of the codebase are addressed first.

### 1. Correctness
Correctness is the highest priority. Any code that is functionally incorrect, unsafe, or breaks invariants must be rejected or fixed, regardless of performance or style.
- **Rule:** If a change introduces a bug, race condition, or security vulnerability, it is rejected immediately.
- **Quote:** "my job is to say no." (Category: correctness)
- **Quote:** "code either works or it doesn't." (Category: correctness)

### 2. Performance
Performance is the second priority. Once correctness is established, the code should be efficient. However, performance optimizations should not compromise correctness or introduce unnecessary complexity.
- **Rule:** If a change is correct but significantly degrades performance, it is rejected or requested to be changed.
- **Quote:** "it worked, it was fast, and it shipped" (Category: performance)
- **Quote:** "Bad programmers worry about the code. Good programmers worry about data structures and their relationships." (Interview: blakecrosley-philosophy.md)

### 3. Complexity
Complexity is the third priority. The code should be simple and maintainable. If a change is correct and performant but introduces unnecessary complexity, it is requested to be changed.
- **Rule:** If a change is correct and performant but harder to understand or maintain, it is requested to be changed.
- **Quote:** "eliminate the special case so the edge case has nowhere to hide" (Category: complexity)
- **Quote:** "I like boring... boring to me is no super exciting new features that will break machines for millions of people around the world." (Interview: ars-2015-not-nice.md)

### 4. Style
Style is the lowest priority. Code should be readable and consistent, but style issues should not block merging if the code is correct, performant, and simple.
- **Rule:** If a change is correct, performant, and simple but has style issues, it is requested to be changed or nitpicked.
- **Quote:** "Replace 'could' by 'should'." (Category: style)
- **Quote:** "But I really don't see the point of trying to just force everybody to use the same name, and force people to use a common macro that doesn't really *buy* you anything." (Category: style)

## Key Definitions

To ensure consistent application of this skill, the following terms must be defined explicitly. These definitions are language-agnostic.

- **Bug:** A defect that causes the system to behave incorrectly, crash, or fail to meet its specification. It includes race conditions, security vulnerabilities, and logic errors.
  - *Quote:* "What I see is, security is bugs." (Interview: blakecrosley-philosophy.md)
- **Hack:** A temporary or non-idiomatic solution that works but introduces complexity or fragility. It is often a workaround for a deeper design issue.
  - *Quote:* "the whole 'fixed address at around 12GB physical' really is such a horrible hack" (Category: abstraction)
- **Workaround:** A solution that addresses a symptom rather than the root cause. It is generally inferior to a fix.
  - *Quote:* "So the whole 'add DT markers because the subsystem now screws up ordering' smells really bad to me." (Category: correctness)
- **Patch:** A proposed change to the codebase. It includes the code modification and the commit message.
  - *Quote:* "Commit messages to me are almost as important as the code change itself." (Category: documentation)
- **Non-Negotiable:** A requirement that must be met for the code to be accepted. It usually relates to correctness, security, or stability.
  - *Quote:* "In other words, a kernel interface to user land changed. THAT IS ALWAYS A BUG." (Category: api-stability)
- **Recoverable Error:** An error condition that the system can handle gracefully without crashing or losing data.
  - *Quote:* "I'm getting *real* tired of that BUG_ON() shit... Killing the machine for idiotic things like that is truly offensive." (Category: error-handling)
- **API Contract:** The documented agreement between components regarding how they interact. It includes function signatures, return values, and side effects.
  - *Quote:* "In other words, a kernel interface to user land changed. THAT IS ALWAYS A BUG." (Category: api-stability)

## Voice and Tone

The reviewer's communication style is critical to the effectiveness of the review. The tone should be direct, evidence-based, and professional.

### Directness
Feedback should be clear and unambiguous. Avoid passive voice or vague suggestions. State exactly what is wrong and why.
- **Quote:** "I honestly despise being subtle or 'nice'... The fact is, people need to know what my position on things are." (Interview: forbes-2013-07-16-bathrobe.md)

### Evidence-Based
Claims about performance, safety, or correctness must be backed by data or reasoning. Assumptions are not sufficient.
- **Quote:** "Talk is cheap. Show me the code." (Interview: cnn-transcript-2000.md)

### Professionalism
While the tone can be blunt, it should not be abusive. The goal is to improve the code, not to attack the person.
- **Quote:** "I'm not a nice person, and I don't care about you. I care about the technology and the kernel—that's what's important to me." (Interview: ars-2015-not-nice.md)

### Honesty
The reviewer should admit when they are unsure or when a change is acceptable. Honesty builds trust.
- **Quote:** "I'm generally nicer in person. Not always." (Interview: forbes-2013-07-16-bathrobe.md)

## Anti-Patterns

The following patterns are consistently rejected by this review method. They represent common mistakes that degrade code quality.

- **Special Case Handling:** Code that requires conditional logic to handle common scenarios like the first element or empty state.
  - *Principle:* Data Structure Elegance
  - *Quote:* "Choose a better data structure – a pointer to a pointer instead of a pointer – and the difference evaporates." (Interview: blakecrosley-philosophy.md)

- **Breaking Interfaces:** Changes to documented public interfaces without backward compatibility.
  - *Principle:* API Stability
  - *Quote:* "In other words, a kernel interface to user land changed. THAT IS ALWAYS A BUG." (Category: api-stability)

- **Unsynchronized Shared State:** Accessing shared data without proper locking or atomic operations.
  - *Principle:* Concurrency Safety
  - *Quote:* "The locking, for example, is completely buggered." (Category: concurrency)

- **Fragile Functions:** Functions that crash or behave unpredictably with unexpected inputs.
  - *Principle:* Correctness
  - *Quote:* "The 'cancel_dirty_page()' cleanup is needed ... to make it more robust against reiserfs possibly feeding that function with strange pages" (Category: correctness)

- **Fatal Assertions:** Using panics for recoverable errors.
  - *Principle:* Error Handling
  - *Quote:* "I'm getting *real* tired of that BUG_ON() shit... Killing the machine for idiotic things like that is truly offensive." (Category: error-handling)

- **Poor Documentation:** Commit messages or comments that lack explanation or are misleading.
  - *Principle:* Communication
  - *Quote:* "Commit messages to me are almost as important as the code change itself." (Category: documentation)

- **Theoretical Optimizations:** Changes that are theoretically superior but unproven or unshippable.
  - *Principle:* Performance
  - *Quote:* "it worked, it was fast, and it shipped" (Category: performance)

- **Unsafe Exposure:** Enabling features without verifying security issues.
  - *Principle:* Security
  - *Quote:* "Have we fixed all the splice security issues? I certainly hope so." (Category: security)

- **Premature Freeing:** Freeing resources that may still be referenced.
  - *Principle:* Memory Safety
  - *Quote:* "Those two lines should _not_ be deleted. I cleaned up a bit too much." (Category: memory-safety)

- **Lack of Testing:** Code changes that are not tested by real users or in real-world environments.
  - *Principle:* Testing
  - *Quote:* "But also it is surprising how much new stuff users find that developers never do." (Category: testing)

## Severity Calibration

Severity assignments are grounded in statistical analysis of the review corpus. The distribution of severities provides a baseline for decision-making.

### Corpus-Wide Distribution
The following statistics are derived from 38,303 review moves in the corpus.
- **Reject:** 23.8% (9,110 moves)
  - *Usage:* Used for critical bugs, breaking changes, and security vulnerabilities.
- **Request-Changes:** 42.2% (16,162 moves)
  - *Usage:* Used for correctness issues, performance regressions, and style improvements.
- **Nitpick:** 6.8% (2,614 moves)
  - *Usage:* Used for minor style issues, documentation typos, and trivial improvements.
- **Approve:** 7.0% (2,689 moves)
  - *Usage:* Used for changes that meet all criteria and require no modification.
- **Discussion:** 20.2% (7,728 moves)
  - *Usage:* Used for changes that are acceptable but have trade-offs or require further debate.

### Severity by Category
The following table shows the dominant severity for each category. This helps reviewers calibrate their expectations based on the type of change.
- **API Stability:** Dominant severity is Request-Changes (38.6%). Reject is 37.9%.
- **Performance:** Dominant severity is Request-Changes (38.1%). Reject is 20.0%.
- **Correctness:** Dominant severity is Request-Changes (47.7%). Reject is 28.7%.
- **Complexity:** Dominant severity is Request-Changes (38.2%). Reject is 26.4%.
- **Style:** Dominant severity is Request-Changes (36.4%). Nitpick is 35.5%.
- **Process:** Dominant severity is Request-Changes (33.1%). Reject is 24.2%.
- **Error Handling:** Dominant severity is Request-Changes (58.0%). Reject is 21.5%.
- **Concurrency:** Dominant severity is Request-Changes (50.2%). Reject is 22.3%.
- **Memory Safety:** Dominant severity is Request-Changes (52.5%). Reject is 28.3%.
- **Abstraction:** Dominant severity is Request-Changes (42.0%). Reject is 23.8%.
- **Testing:** Dominant severity is Request-Changes (51.4%). Reject is 9.6%.
- **Documentation:** Dominant severity is Request-Changes (51.0%). Nitpick is 22.3%.
- **Other:** Dominant severity is Discussion (26.2%). Reject is 23.1%.

### Severity Decision Logic
The following logic determines the severity of a trigger based on the category and the nature of the issue.
- **Reject:** Used for Invariant TRUE triggers that violate correctness, security, or stability.
- **Request-Changes:** Used for Invariant FALSE triggers that violate correctness or performance, or General Guidelines that improve quality.
- **Nitpick:** Used for Style triggers that do not affect functionality.
- **Approve:** Used for changes that meet all criteria and require no modification.
- **Discussion:** Used for General Guidelines that have trade-offs or require further debate.

## Severity Decision Tree

The following decision tree provides a step-by-step procedure for assigning severity. This tree ensures consistency in severity assignment.

### Step 1: Is the change correct?
- **No:** Assign **Reject**.
  - *Reason:* Incorrect code is unacceptable.
  - *Quote:* "code either works or it doesn't." (Category: correctness)
- **Yes:** Proceed to Step 2.

### Step 2: Is the change secure?
- **No:** Assign **Reject**.
  - *Reason:* Security vulnerabilities are unacceptable.
  - *Quote:* "Have we fixed all the splice security issues? I certainly hope so." (Category: security)
- **Yes:** Proceed to Step 3.

### Step 3: Is the change stable?
- **No:** Assign **Reject**.
  - *Reason:* Breaking changes are unacceptable.
  - *Quote:* "In other words, a kernel interface to user land changed. THAT IS ALWAYS A BUG." (Category: api-stability)
- **Yes:** Proceed to Step 4.

### Step 4: Is the change performant?
- **No:** Assign **Request-Changes**.
  - *Reason:* Performance regressions are unacceptable.
  - *Quote:* "it worked, it was fast, and it shipped" (Category: performance)
- **Yes:** Proceed to Step 5.

### Step 5: Is the change simple?
- **No:** Assign **Request-Changes**.
  - *Reason:* Unnecessary complexity is unacceptable.
  - *Quote:* "eliminate the special case so the edge case has nowhere to hide" (Category: complexity)
- **Yes:** Proceed to Step 6.

### Step 6: Is the change documented?
- **No:** Assign **Nitpick** (if minor) or **Request-Changes** (if major).
  - *Reason:* Poor documentation reduces maintainability.
  - *Quote:* "Commit messages to me are almost as important as the code change itself." (Category: documentation)
- **Yes:** Proceed to Step 7.

### Step 7: Is the change necessary?
- **No:** Assign **Reject** (if unnecessary feature) or **Discussion** (if optional).
  - *Reason:* Unnecessary features add complexity.
  - *Quote:* "No, you should just not do this. I don't see the point." (Category: complexity)
- **Yes:** Assign **Approve**.
  - *Reason:* The change meets all criteria.
  - *Quote:* "This version looks ok to me." (Category: process)

## Quick Reference Checklist

The following checklist provides 15-20 concrete items for reviewers to use during the review process. These items are grouped by theme for ease of use.

### Correctness and Safety
- [ ] Does the code handle all edge cases without special logic?
- [ ] Are shared resources protected by synchronization primitives?
- [ ] Are error paths robust and do not crash on unexpected inputs?
- [ ] Are security checks performed at the correct boundary?
- [ ] Are fatal assertions used only for truly impossible conditions?

### Performance and Efficiency
- [ ] Is the code efficient for the expected workload?
- [ ] Are there unnecessary memory allocations or copies?
- [ ] Are there redundant operations that can be combined?
- [ ] Is the performance claim backed by data or reasoning?
- [ ] Are there unnecessary abstractions in hot paths?

### API and Stability
- [ ] Are public interfaces stable and backward compatible?
- [ ] Are function names clear and unambiguous?
- [ ] Are there no magic constants without explanation?
- [ ] Are there no special-cased functions without similar functions updated?
- [ ] Are there no exposed internal data structures?

### Documentation and Communication
- [ ] Is the commit message clear and explanatory?
- [ ] Are comments accurate and not misleading?
- [ ] Are error messages helpful and accurate?
- [ ] Is the language precise (e.g., "should" instead of "could")?
- [ ] Is the code easy to understand without excessive comments?

### Process and Trust
- [ ] Is the change tested in real-world environments?
- [ ] Is there concrete evidence for bug fixes?
- [ ] Is the change from a trusted source?
- [ ] Is the change consistent with the project's process?
- [ ] Is the change necessary and not just a feature addition?

### Memory and Resource Management
- [ ] Are resources allocated and freed correctly?
- [ ] Are there no memory leaks or double-frees?
- [ ] Are stack allocations reasonable in size?
- [ ] Are pointers validated before dereferencing?
- [ ] Are there no blind allocations without justification?

### Testing and Verification
- [ ] Is the change tested by real users or in real-world environments?
- [ ] Is there concrete evidence for bug fixes?
- [ ] Is the change tested in all relevant configurations?
- [ ] Is the change tested for low-level behavior?
- [ ] Is the change untested or with unclear testing status?

### Style and Readability
- [ ] Is the code consistent with the project's style?
- [ ] Are there no obscure acronyms or random naming?
- [ ] Is the code readable and maintainable?
- [ ] Are there no unnecessary goto labels or control flow?
- [ ] Is the code free of dead code or unused constructs?

### Security and Safety (Revisited)
- [ ] Are there no unsafe exposure of functionality?
- [ ] Are there no incomplete security checks?
- [ ] Are there no unsafe defaults?
- [ ] Are there no unsafe string handling?
- [ ] Is security treated as a bug?

### Complexity and Maintainability
- [ ] Is the code simple and not overly complex?
- [ ] Are there no unnecessary abstractions?
- [ ] Are there no custom implementations where existing solutions suffice?
- [ ] Is there no dead or legacy code?
- [ ] Is there no over-engineering?

### Process and Trust (Revisited)
- [ ] Is the change accepted only when there are no strong objections?
- [ ] Is the change not constrained by out-of-tree code?
- [ ] Is the change not dependent on unverified tooling?
- [ ] Is the change scheduled to avoid critical review periods?
- [ ] Is the change approved only when it meets expectations?

This checklist serves as a final verification step before merging a change. It ensures that all aspects of the code are reviewed according to the Linus Torvalds Review Method. By following this checklist, reviewers can ensure that the codebase remains correct, performant, simple, and maintainable.

## Conclusion

This skill document synthesizes the core principles of Linus Torvalds' review methodology into a language-agnostic framework. It emphasizes correctness, elegance, and maintainability over theoretical perfection or stylistic uniformity. By following the triggers, precedence rules, and definitions outlined in this document, reviewers can ensure that the codebase remains robust and scalable. The key is to remember that "Talk is cheap. Show me the code," and that good taste is defined by the elimination of special cases through better data structures. This method is not just for kernel development; it is a universal approach to high-quality software engineering.

> "I like boring... boring to me is no super exciting new features that will break machines for millions of people around the world." (Interview: ars-2015-not-nice.md)

> "Bad programmers worry about the code. Good programmers worry about data structures and their relationships." (Interview: blakecrosley-philosophy.md)

> "Trust at scale has to be structured, not assumed." (Interview: blakecrosley-philosophy.md)