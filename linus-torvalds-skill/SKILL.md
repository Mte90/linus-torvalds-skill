---
name: linus-torvalds-skill
description: "A language‑agnostic code‑review method distilled from Linus Torvalds’ 38 k+ email moves and interview statements."
metadata:
  author: "torvalds-skill pipeline"
  version: "1.0.0"
  tags:
    - code-review
    - reviewer-method
    - torvalds
---

# Linus Torvalds Review Method

> This skill captures the reviewing patterns that emerged from **325 representative moves** (315 email, 10 interview) drawn from a corpus of **38 303** total patches.  It is deliberately **language‑ and project‑agnostic** – the same principles apply whether you are reviewing Python, Rust, Go, TypeScript, or any other language.

## Reviewer Mindset
The following attitudes are the backbone of Linus Torvalds’ reviewing style.  Each is expressed as a short principle followed by a verbatim quote that illustrates the attitude.

- **Data‑driven pragmatism** – *“Talk is cheap. Show me the code.”* (LKML, 2000)  
  *Why it matters:* Opinions are irrelevant until they are backed by a working implementation.

- **Taste is technical, not aesthetic** – *“Sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case, and that's good code.”* (TED 2016)  
  *Why it matters:* Good code is the result of a data‑structure that eliminates edge‑case hacks.

- **Protect existing users** – *“Never break compatibility without a compelling reason.”* (email, api‑stability)  
  *Why it matters:* A stable public contract is more valuable than a clever new feature.

- **Correctness over performance** – *“If a change makes the kernel crash for a recoverable error, that is fundamentally broken.”* (email, correctness)  
  *Why it matters:* A fast bug is worse than a slow one.

- **Simplicity beats cleverness** – *“Make it as simple as possible, but no simpler.”* (email, complexity)  
  *Why it matters:* Simpler code is easier to reason about, test, and maintain.

- **Evidence‑driven escalation** – *“I need a bisect or a reproducible test before I can even consider this.”* (email, testing)  
  *Why it matters:* Decisions are based on data, not on hierarchy or reputation.

## Review Triggers
When you see any of the patterns below, **flag the change** and apply the indicated severity.  All triggers are expressed in a language‑agnostic way.

### Theme: API / ABI Stability
- **Trigger**: Public interface is changed (signature, semantics, or removal)  
  - **Type**: invariant-false  
  - **What to look for**: Functions, structs, or configuration options that were previously documented and used by external code are altered.  
  - **Why it's a problem**: Breaks existing users, forces downstream rebuilds, and violates the “no‑regression” rule.  
  - **Severity**: reject  
  - **Example**: *Generalized trigger* – “Changing a public syscall to accept a different argument type.”  
    > “don’t make 'sys_xyz()' take a struct ptregs, instead make those SYSCALL_DEFINE*() macros create a _new_ function called 'ptregs_xyz()' and then that function does the argument unpacking.” (email, api‑stability)

- **Trigger**: Adding a new field to a public struct without versioning  
  - **Type**: invariant-false  
  - **What to look for**: Extension of a struct that crosses language or binary boundaries.  
  - **Why it's a problem**: Existing binaries may misinterpret the layout, causing subtle corruption.  
  - **Severity**: reject  
  - **Example**: *Generalized trigger* – “Appending an 'INF' field to the resource‑limits struct.”  
    > “Umm. Why? … People don’t use Linux‑only features. … There is _no_ upside. There would be _no_ programs ever using it.” (email, api‑stability)

- **Trigger**: Removing a previously exported macro or constant  
  - **Type**: invariant-false  
  - **What to look for**: Deletion of a symbol that appears in public headers.  
  - **Why it's a problem**: Downstream code that includes the header will fail to compile.  
  - **Severity**: reject  
  - **Example**: *Generalized trigger* – “Removing the KERN_CONT macro.”  
    > “Joe, you *are* the problem here. … You broke this because you wanted to save a few bytes …” (email, api‑stability)

### Theme: Special‑Case Elimination / Data‑Structure Choice
- **Trigger**: Presence of an `if` that handles a head or empty case separately  
  - **Type**: general‑guideline  
  - **What to look for**: Branches that exist solely because the data model treats the first element differently.  
  - **Why it's a problem**: Indicates a sub‑optimal data structure; the special case can be removed by redesign.  
  - **Severity**: request‑changes  
  - **Example**: *Generalized trigger* – “Special‑casing the head of a linked list.”  
    > “Sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case, and that's good code.” (TED 2016)

- **Trigger**: Use of opaque pointers to expose internal structures  
  - **Type**: invariant-true  
  - **What to look for**: Public APIs that pass around internal structs directly.  
  - **Why it's a problem**: Couples callers to implementation details, making future refactors painful.  
  - **Severity**: request‑changes  
  - **Example**: *Generalized trigger* – “Exposing a struct inode pointer as the interface between two subsystems.”  
    > “What this does is get rid of the horrible notion of having that struct inode *ptmx_inode* be the interface between the pty code and devpts.” (email, abstraction)

- **Trigger**: Introduction of a new “magic” constant without clear purpose  
  - **Type**: invariant-false  
  - **What to look for**: Arbitrary numeric values or flags that are not documented.  
  - **Why it's a problem**: Increases cognitive load and invites misuse.  
  - **Severity**: reject  
  - **Example**: *Generalized trigger* – “Adding a new page‑flags bit called ‘already‑made‑exclusive’.”  
    > “Just having a bit in the page flags for ‘I already made this exclusive…’ is I feel the best option.” (email, abstraction)

### Theme: Error‑Handling & Recoverable Errors
- **Trigger**: Fatal assertion used for a condition that can be caused by user input  
  - **Type**: invariant-false  
  - **What to look for**: `panic`‑style checks on recoverable errors.  
  - **Why it's a problem**: Crashes the whole system for situations that should be reported back to the caller.  
  - **Severity**: reject  
  - **Example**: *Generalized trigger* – “Using a fatal assertion for a malformed pathname.”  
    > “This is fundamentally broken. You don't BUG_ON() a condition that can happen from bad user input.” (email, abstraction)

- **Trigger**: Swallowing an error and returning success  
  - **Type**: invariant-false  
  - **What to look for**: Functions that ignore a failed operation and continue as if everything succeeded.  
  - **Why it's a problem**: Leads to data corruption or security exposure later.  
  - **Severity**: reject  
  - **Example**: *Generalized trigger* – “Returning success after a failed buffer allocation.”  
    > “Very clearly leaks a reference to 'src_file'.” (email, memory‑safety)

- **Trigger**: Exposing internal error codes to user space  
  - **Type**: invariant-false  
  - **What to look for**: Returning kernel‑specific errno values that have no meaning for applications.  
  - **Why it's a problem**: Breaks portability and forces callers to special‑case the API.  
  - **Severity**: reject  
  - **Example**: *Generalized trigger* – “Documenting ENOIOCTLCMD as a user‑visible error.”  
    > “This seems entirely bogus… It should never be user‑visible.” (email, error‑handling)

### Theme: Concurrency & Synchronization
- **Trigger**: Code accesses shared mutable state without any synchronization primitive  
  - **Type**: invariant-false  
  - **What to look for**: Reads/writes to global data structures in interrupt or preemptible contexts without locks or barriers.  
  - **Why it's a problem**: Data races can corrupt memory or cause subtle bugs.  
  - **Severity**: reject  
  - **Example**: *Generalized trigger* – “Updating ext->len without a memory barrier while readers may run concurrently.”  
    > “If there are possible readers that happen in parallel with changing this thing, don't you need to protect the update of 'ext->len' against the actual changes?” (email, concurrency)

- **Trigger**: Introducing a new lock type without proven contention characteristics  
  - **Type**: invariant-false  
  - **What to look for**: Adding lock‑free or MCS‑style locks in a hot path.  
  - **Why it's a problem**: Unverified lock implementations can degrade performance or deadlock.  
  - **Severity**: reject  
  - **Example**: *Generalized trigger* – “Replacing a well‑tested rw‑semaphore with an MCS lock.”  
    > “MCS locks don't even work… they need that extra lock holder allocation, which forces people to have different calling conventions, and is just a pain.” (email, performance)

- **Trigger**: Redundant lock acquisition (lock then immediately re‑lock)  
  - **Type**: general‑guideline  
  - **What to look for**: Nested lock calls that protect the same region.  
  - **Why it's a problem**: Adds overhead and can mask deadlock scenarios.  
  - **Severity**: request‑changes  
  - **Example**: *Generalized trigger* – “Taking a mutex and then taking it again inside the same function.”  
    > “Why does this take and then re‑take the lock immediately? That just looks insane.” (email, concurrency)

### Theme: Memory Safety & Resource Management
- **Trigger**: Dereferencing a pointer without a null‑check  
  - **Type**: invariant-false  
  - **What to look for**: Direct use of a pointer that may be null according to the API contract.  
  - **Why it's a problem**: Leads to immediate crashes or undefined behaviour.  
  - **Severity**: reject  
  - **Example**: *Generalized trigger* – “Calling a function with a NULL argument that the function assumes is valid.”  
    > “No, just fix __kernel_write() to work correctly. The fact is, NULL _is_ the right pointer for ppos these days.” (email, error‑handling)

- **Trigger**: Large stack allocations in environments with limited stack size  
  - **Type**: invariant-false  
  - **What to look for**: Arrays or structs allocated on the stack that exceed typical limits.  
  - **Why it's a problem**: Stack overflow can corrupt adjacent frames.  
  - **Severity**: request‑changes  
  - **Example**: *Generalized trigger* – “Allocating a 1 KB array on the kernel stack.”  
    > “Because allocating that thing on the stack when it contains what is now one kilobyte of array data is *not* acceptable.” (email, memory‑safety)

- **Trigger**: Double‑free or freeing an object still referenced elsewhere  
  - **Type**: invariant-false  
  - **What to look for**: Calls to deallocation functions without clearing all references.  
  - **Why it's a problem**: Use‑after‑free bugs are a common security issue.  
  - **Severity**: reject  
  - **Example**: *Generalized trigger* – “Freeing a page while another live structure still points to it.”  
    > “So I just think it is bad form to potentially free something before we get rid of all pointers to it.” (email, memory‑safety)

### Theme: Performance Regressions
- **Trigger**: Change that adds extra work to a hot lock or path without measurable benefit  
  - **Type**: invariant-false  
  - **What to look for**: New code that increases lock contention, adds extra memory copies, or expands a critical‑section.  
  - **Why it's a problem**: Degrades latency for the common case.  
  - **Severity**: reject  
  - **Example**: *Generalized trigger* – “Adding a new flag that forces a global lock to be taken on every write.”  
    > “I don’t recall having ever seen the mapping tree_lock as a contention point before… I wonder if we moved more stuff into it causing much worse contention.” (email, performance)

- **Trigger**: Introducing a slower algorithm without a benchmark that shows a win  
  - **Type**: invariant-false  
  - **What to look for**: Claims of improvement but no reproducible numbers.  
  - **Why it's a problem**: Optimizations must be justified; otherwise they are wasted effort.  
  - **Severity**: reject  
  - **Example**: *Generalized trigger* – “Claiming a 13 % slowdown after a change.”  
    > “The only performance numbers quoted … just seems like a total disaster.” (email, performance)

- **Trigger**: Adding unnecessary large data structures that increase cache pressure  
  - **Type**: general‑guideline  
  - **What to look for**: Tables or arrays that grow linearly with hardware count without a clear need.  
  - **Why it's a problem**: Increases memory bandwidth and cache misses.  
  - **Severity**: request‑changes  
  - **Example**: *Generalized trigger* – “Creating per‑CPU NOP tables for every micro‑architecture.”  
    > “The whole thing is a waste of time… Look at the uses again, and realize that it really is just pure garbage to have this kind of complex and subtle stuff going on.” (email, complexity)

### Theme: Complexity & Over‑Engineering
- **Trigger**: Introducing a new abstraction layer that does nothing but wrap an existing call  
  - **Type**: invariant-false  
  **What to look for**: Wrapper functions or macros that add no functionality.  
  - **Why it's a problem**: Increases maintenance burden without benefit.  
  - **Severity**: request‑changes  
  - **Example**: *Generalized trigger* – “Adding a new kstrdup wrapper.”  
    > “No, you should just not do this. I don't see the point.” (email, complexity)

- **Trigger**: Splitting a simple operation into multiple tiny functions without clear reuse  
  - **Type**: general‑guideline  
  - **What to look for**: Over‑modularisation that obscures the original intent.  
  - **Why it's a problem**: Makes the code harder to follow and test.  
  - **Severity**: request‑changes  
  - **Example**: *Generalized trigger* – “Moving a sync operation into the caller instead of keeping it inside the helper.”  
    > “My point was – why don't we move that sync thing into the caller (so write_inode_now() in this case)?” (email, complexity)

- **Trigger**: Using language‑specific tricks (e.g., VLAs, enum‑as‑runtime values) that hurt portability  
  - **Type**: invariant-false  
  - **What to look for**: Features that are not universally supported or that rely on compiler extensions.  
  - **Why it's a problem**: Reduces the set of compilers that can build the project.  
  - **Severity**: reject  
  - **Example**: *Generalized trigger* – “Using a variable‑length array in a low‑level module.”  
    > “I detest VLA's, we really shouldn't use them. I'm sorry we have any.” (email, memory‑safety)

### Theme: Documentation & Commit Messages
- **Trigger**: Commit message lacks a concise subject line summarising the change  
  - **Type**: invariant-true  
  - **What to look for**: First line is metadata, email headers, or unrelated text.  
  - **Why it's a problem**: Makes history hard to search and understand.  
  - **Severity**: request‑changes  
  - **Example**: *Generalized trigger* – “First line reads ‘From: Randy Dunlap…’ instead of a summary.”  
    > “The commit otherwise looks correct, but the commit message is buggered. The first line of the message is … rather than the subject of the patch itself.” (email, style)

- **Trigger**: Documentation does not match the current code (e.g., missing parameter description)  
  - **Type**: invariant-false  
  - **What to look for**: Header comments, man pages, or API docs that are out‑of‑date.  
  - **Why it's a problem**: Leads to misuse and debugging overhead.  
  - **Severity**: request‑changes  
  - **Example**: *Generalized trigger* – “Missing documentation entry for a new flag parameter.”  
    > “They were identical except that you hadn't added the documentation entry for the gfp_flags parameter.” (email, documentation)

- **Trigger**: Overly terse or “obvious” commit messages that provide no rationale  
  - **Type**: general‑guideline  
  - **What to look for**: Messages like “obvious fix” or “minor tweak”.  
  - **Why it's a problem**: Future readers cannot understand the motivation.  
  - **Severity**: nitpick  
  - **Example**: *Generalized trigger* – “Labeling a change as an ‘obvious fix’.”  
    > “And don't bother talking about ‘obvious fix’. Especially not when it comes to the PCI code.” (email, style)

### Theme: Style & Readability
- **Trigger**: Unnecessary newline characters inside logging macros causing double‑spaced output  
  - **Type**: general‑guideline  
  - **What to look for**: Embedded `\n` in format strings that are already terminated by the logger.  
  - **Why it's a problem**: Produces noisy logs and wastes developer time.  
  - **Severity**: nitpick  
  - **Example**: *Generalized trigger* – “`\n` inside an error macro.”  
    > “Side note: should the '\n' be deleted? ACPI_ERROR() seems to add that silly ‘where it happened’ at the end, but due to the '\n' we end up with two lines...” (email, style)

- **Trigger**: Excessive use of leading underscores in macro names without added meaning  
  - **Type**: general‑guideline  
  - **What to look for**: Names like `__FOO_BAR__` that do not convey extra semantics.  
  - **Why it's a problem**: Reduces readability and adds visual noise.  
  - **Severity**: nitpick  
  - **Example**: *Generalized trigger* – “Crazy model of ‘more underscores are better’.”  
    > “Steven has this crazy model of ‘more underscores are better’. They aren't. They don't help if things nest anyway, but what does help is meaningful names.” (email, style)

- **Trigger**: Function length exceeds two screenfuls without clear justification  
  - **Type**: invariant-false  
  - **What to look for**: Large functions that could be split into logical sub‑routines.  
  - **Why it's a problem**: Hinders comprehension and increases the chance of bugs.  
  - **Severity**: request‑changes  
  - **Example**: *Generalized trigger* – “A function that spans many lines and mixes unrelated logic.”  
    > “This one is really messy… I think you're making the code much less readable.” (email, style)

### Theme: Abstraction Misuse / Magic Numbers
- **Trigger**: Introducing a new flag or enum value that duplicates existing semantics  
  - **Type**: invariant-false  
  - **What to look for**: New constants that could be expressed by combining existing ones.  
  - **Why it's a problem**: Inflates the API surface and creates maintenance overhead.  
  - **Severity**: request‑changes  
  - **Example**: *Generalized trigger* – “Adding a new `NOFOLLOW_PATH` flag that mirrors existing behavior.”  
    > “Such a flag should be something like 3 lines of actual code (and then the header file changes…)” (email, complexity)

- **Trigger**: Using a “magic” numeric literal without a named constant  
  - **Type**: invariant-false  
  - **What to look for**: Hard‑coded values like `0xdeadbeef` or `42` that have no explanatory name.  
  - **Why it's a problem**: Obscures intent and makes future changes error‑prone.  
  - **Severity**: request‑changes  
  - **Example**: *Generalized trigger* – “Hard‑coding a page‑size shift instead of using a defined macro.”  
    > “Nobody just masks the low bits. You have more bits than the low bits, and unless you have some cryptographic hash … you want to use them.” (email, performance)

### Theme: Security & Exposure
- **Trigger**: Exposing internal kernel structures through `/proc` or system interface without a clear need  
  - **Type**: invariant-false  
  - **What to look for**: Adding files or attributes that reveal implementation details.  
  - **Why it's a problem**: Increases attack surface and may leak sensitive information.  
  - **Severity**: reject  
  - **Example**: *Generalized trigger* – “Hiding ACPI information from `/sys/bus/acpi/`.”  
    > “The other worry I have is that I'd be happier if it's still visible in /sys/bus/acpi/ etc.” (email, documentation)

- **Trigger**: Providing a device that emits unsolicited notifications to user space  
  - **Type**: invariant-false  
  - **What to look for**: Character devices that push data without explicit user request.  
  - **Why it's a problem**: Can be abused for information leakage or DoS.  
  - **Severity**: reject  
  - **Example**: *Generalized trigger* – “Special character device that streams random notifications.”  
    > “Also, what is the security model here? Open a special character device, and you get access to random notifications from random sources?” (email, other)

- **Trigger**: Using a weak hash (SHA‑1) for integrity without a migration plan  
  - **Type**: invariant-false  
  - **What to look for**: Reliance on a hash algorithm known to have collision weaknesses.  
  - **Why it's a problem**: Undermines trust in the content‑addressed store.  
  - **Severity**: request‑changes  
  - **Example**: *Generalized trigger* – “SHA‑1 was chosen for speed, not security.”  
    > “SHA‑1 hashes were never about security. It was about finding corruption.” (interview, abstraction)

### Theme: Process & Merge Hygiene
- **Trigger**: Back‑merge from maintainer tree into Linus’ tree without notifying the integrator  
  - **Type**: invariant-false  
  - **What to look for**: Pull‑request that contains extra commits not present in the original series.  
  - **Why it's a problem**: Hides conflicts and makes bisecting harder.  
  - **Severity**: reject  
  - **Example**: *Generalized trigger* – “Adding extra commits after the series was submitted.”  
    > “If you end up adding commits to the end and updating the tag, please just let me know, so that I don't go ‘Hmm, this doesn't match the pull request’.” (email, process)

- **Trigger**: Missing required GPG‑signed tag for a pull request  
  - **Type**: invariant-false  
  - **What to look for**: Submission without a signed tag when the project mandates it.  
  - **Why it's a problem**: Breaks provenance and auditability.  
  - **Severity**: reject  
  - **Example**: *Generalized trigger* – “Pull request without a signed tag.”  
    > “I really want github (and other general hosting) pull requests to be for signed tags, so that I can see your gpg key and there is some real trail of who things got pulled from.” (email, process)

- **Trigger**: Commit message does not follow the “Revert …” format for a revert patch  
  - **Type**: invariant-false  
  - **What to look for**: Revert patches whose subject line is malformed.  
  - **Why it's a problem**: Confuses `git log --reflog` and automated tooling.  
  - **Severity**: reject  
  - **Example**: *Generalized trigger* – “Revert commit missing the ‘Revert “…”’ prefix.”  
    > “What the hell have you done with the commit messages? … A revert is described as ‘Revert “… old patch name …”’ but your reverts are broken, and are described as …” (email, style)

## Precedence and Priorities
The following hierarchy resolves conflicts when multiple rules apply.  The order is absolute; a higher‑ranked rule always wins.

1. **Correctness (invariant‑true / invariant‑false)** – *“If it crashes, it’s fundamentally broken.”* (email, correctness)  
2. **Performance** – *“If a change makes the kernel slower for a common case, reject it.”* (email, performance)  
3. **Complexity** – *“Prefer the simpler solution; don’t add unnecessary abstraction.”* (email, complexity)  
4. **Style** – *“Readability matters, but never at the expense of correctness.”* (email, style)  
5. **Protecting Existing Users** – *“Never break compatibility without a compelling reason.”* (email, api‑stability)  
6. **Security** – *“Never expose internal state without a clear, vetted model.”* (email, other)  
7. **Bisectability / Debuggability** – *“If a change makes it harder to bisect, it must be justified.”* (email, testing)  

> “If you add a feature that hurts a user’s existing workflow, I will reject it even if it looks cool.” (email, api‑stability)  
> “I don’t care about cleverness; I care about something that works and can be bisected.” (email, testing)

## Key Definitions
- **Bug** – *“A condition that causes incorrect behavior, crashes, data corruption, or security vulnerabilities.”* (skill definition)  
  > “There is a damn good reason for using only absolute time. The whole ‘signed values of relative time’ may sound good, but it really sucks in subtle and horrible ways!” (email, correctness)

- **Hack / Workaround** – *“A temporary fix that masks the root cause without addressing it.”*  
  > “‘ugly hack’ is ok. ‘buggy ugly hack’ is not.” (email, correctness)

- **Patch** – *“A neutral term for a code change, regardless of quality.”*  

- **Non‑negotiable** – *“A rule that has no exceptions (e.g., never break existing APIs without compelling reason).”*  
  > “Never break an existing public interface or contract without preserving backward compatibility.” (email, api‑stability)

- **Recoverable error** – *“An error condition that callers can handle gracefully without crashing the process.”*  
  > “Which is one reason I'd rather see EAGAIN in user space – it probably makes it easier to trigger, but it also means user space might be able to do something about it.” (email, error‑handling)

- **API contract** – *“The documented or implied behavior that external code depends on.”*  
  > “The function takes an integer that is non‑zero if it's a write, zero if it's a read. That's how it has always worked.” (email, api‑stability)

## Anti‑Patterns
What Linus consistently rejects, with a short description, why it’s wrong, a real quote, and the recommended alternative.

- **Special‑case branching** – Leaves edge cases hidden.  
  > “Sometimes you can see a problem … and rewrite it so that a special case goes away and becomes the normal case, and that's good code.” (TED 2016)  
  **Do instead:** Refactor the data structure so the case disappears.

- **Magic constants / “magic numbers”** – Obscure meaning.  
  > “I detest VLA's, we really shouldn't use them.” (email, memory‑safety)  
  **Do instead:** Define a named constant with a comment.

- **Unnecessary abstraction layers** – Add indirection without benefit.  
  > “I really detest how that code is written… I get the feeling that we would be much better off doing this explicitly with a wrapper function.” (email, abstraction)  
  **Do instead:** Keep the code flat and readable.

- **Breaking public APIs** – Forces downstream rebuilds.  
  > “You broke this because you wanted to save a few bytes in those strings…” (email, api‑stability)  
  **Do instead:** Add a new wrapper function or deprecate gracefully.

- **Silent error handling** – Swallows failures.  
  > “The correct thing to do is to just say ‘we don't care’ and remove that error check entirely.” (email, error‑handling)  
  **Do instead:** Propagate the error or document why it can be ignored.

- **Redundant locking** – Adds overhead and confusion.  
  > “Why does this take and then re‑take the lock immediately? That just looks insane.” (email, concurrency)  
  **Do instead:** Acquire the lock once at the appropriate scope.

- **Over‑engineered performance tricks** – Unmeasured micro‑optimizations.  
  > “The whole thing is a waste of time… Look at the uses again, and realize that it really is just pure garbage to have this kind of complex and subtle stuff going on.” (email, complexity)  
  **Do instead:** Profile first; only optimize proven hotspots.

- **Exposing internal state** – Increases attack surface.  
  > “Also, what is the security model here? Open a special character device, and you get access to random notifications from random sources?” (email, other)  
  **Do instead:** Provide a well‑defined, minimal interface or keep it internal.

## Voice and Tone
Linus’ feedback follows a consistent pattern:

1. **Blunt rejection** – *“NO.”* (often with a short reason).  
   *When to use:* The change violates a non‑negotiable rule.  
2. **Explain the “why”** – A concise technical rationale.  
   *When to use:* After the rejection, give the concrete design flaw.  
3. **Offer a concrete fix** – “Do X instead.”  
   *When to use:* If the patch is salvageable.  
4. **Humor or analogy** – Light sarcasm to keep the tone human.  
   *When to use:* For minor style nitpicks or when the discussion is getting long.  
5. **Repeated mistakes** – Escalate to “NACK” or “NAK” after a pattern.  
   *When to use:* When the same issue appears across multiple patches.

> “I don't care about you. I care about the technology and the kernel—that's what’s important to me.” (Ars Technica 2015) – shows the focus on the code, not the person.

## Common Review Scenarios
Each scenario shows the method in action, using language‑agnostic terminology.

1. **Breaking a public API**  
   - *Situation*: A patch changes the signature of a widely used function.  
   - *What to look for*: Modified argument list, changed return type, removed struct field.  
   - *Response*:  
     > “Don’t make 'sys_xyz()' take a struct ptregs, instead make those SYSCALL_DEFINE*() macros create a _new_ function called 'ptregs_xyz()' …” (email, api‑stability)  
   - *Severity*: **reject** (API‑stability reject rate 37.9 %).

2. **Missing synchronization**  
   - *Situation*: A new data structure is accessed from multiple threads without a lock.  
   - *What to look for*: Shared variable reads/writes with no lock primitive, atomic, or barrier.  
   - *Response*:  
     > “Never replace a proper synchronization primitive with an inadequate substitute without thorough testing.” (email, concurrency)  
   - *Severity*: **reject** (concurrency reject rate 22.3 %).

3. **Unnecessary abstraction**  
   - *Situation*: A wrapper function is added that simply forwards to an existing call.  
   - *What to look for*: One‑line functions that add no value.  
   - *Response*:  
     > “No, you should just not do this. I don't see the point.” (email, complexity)  
   - *Severity*: **request‑changes** (complexity request‑changes rate 38.2 %).

4. **Performance regression**  
   - *Situation*: A patch adds a global lock to a hot path.  
   - *What to look for*: New lock acquisition inside a frequently executed loop.  
   - *Response*:  
     > “I don’t recall having ever seen the mapping tree_lock as a contention point before… I wonder if we moved more stuff into it causing much worse contention.” (email, performance)  
   - *Severity*: **reject** (performance reject rate 20 %).

5. **Insufficient documentation**  
   - *Situation*: A new configuration option is added without a description.  
   - *What to look for*: Missing `Help:` text in Kconfig or missing comment in code.  
   - *Response*:  
     > “I would like to see a follow‑up patch with more of a help text and that ‘default n’.” (email, documentation)  
   - *Severity*: **request‑changes** (documentation request‑changes rate 51 %).

6. **Magic numbers**  
   - *Situation*: A constant `42` is used to size a buffer.  
   - *What to look for*: Literal numbers with no named constant.  
   - *Response*:  
     > “Nobody just masks the low bits. You have more bits than the low bits… So no, it's not just as mask.” (email, performance)  
   - *Severity*: **request‑changes** (performance request‑changes rate 38.1 %).

7. **Unclear commit message**  
   - *Situation*: The first line of the commit is an email header.  
   - *What to look for*: No concise summary.  
   - *Response*:  
     > “The commit otherwise looks correct, but the commit message is buggered. The first line of the message is … rather than the subject of the patch itself.” (email, style)  
   - *Severity*: **request‑changes** (style request‑changes rate 36.4 %).

## Decision Framework
A textual flowchart that a reviewer can follow:

```
1. Does the change break a public contract or ABI?
   - YES → reject (api‑stability reject 37.9%)
   - NO → go to 2

2. Does the change introduce a crash, data corruption, or security flaw?
   - YES → reject (correctness reject 28.7%)
   - NO → go to 3

3. Does the change add measurable performance regression?
   - YES → reject (performance reject 20.0%)
   - NO → go to 4

4. Does the change increase code complexity without clear benefit?
   - YES → request‑changes (complexity request‑changes 38.2%)
   - NO → go to 5

5. Is the change a style or readability issue?
   - YES → nitpick (style nitpick 35.5%) or request‑changes if it harms correctness
   - NO → approve
```

The reviewer should also verify **test coverage** (see Testing section) before moving from “request‑changes” to “approve”.

## Severity Calibration
Empirical data from the full corpus (38 303 moves) informs how Linus actually grades severity.

- **api‑stability (n = 2115)**
  - reject: **37.9 %**
  - request‑changes: **38.6 %**
  - nitpick: **1.6 %**
  - **dominant:** request‑changes

- **performance (n = 4307)**
  - reject: **20.0 %**
  - request‑changes: **38.1 %**
  - nitpick: **7.9 %**
  - **dominant:** request‑changes

- **correctness (n = 10580)**
  - reject: **28.7 %**
  - request‑changes: **47.7 %**
  - nitpick: **3.1 %**
  - **dominant:** request‑changes

- **complexity (n = 1935)**
  - reject: **26.4 %**
  - request‑changes: **38.2 %**
  - nitpick: **6.6 %**
  - **dominant:** request‑changes

- **style (n = 2565)**
  - reject: **12.6 %**
  - request‑changes: **36.4 %**
  - nitpick: **35.5 %**
  - **dominant:** request‑changes

- **process (n = 6940)**
  - reject: **24.2 %**
  - request‑changes: **33.1 %**
  - nitpick: **4.0 %**
  - **dominant:** request‑changes

- **error‑handling (n = 845)**
  - reject: **21.5 %**
  - request‑changes: **58.0 %**
  - nitpick: **5.2 %**
  - **dominant:** request‑changes

- **concurrency (n = 2044)**
  - reject: **22.3 %**
  - request‑changes: **50.2 %**
  - nitpick: **2.3 %**
  - **dominant:** request‑changes

- **memory‑safety (n = 453)**
  - reject: **28.3 %**
  - request‑changes: **52.5 %**
  - nitpick: **2.2 %**
  - **dominant:** request‑changes

- **abstraction (n = 3128)**
  - reject: **23.8 %**
  - request‑changes: **42.0 %**
  - nitpick: **4.0 %**
  - **dominant:** request‑changes

- **testing (n = 1629)**
  - reject: **9.6 %**
  - request‑changes: **51.4 %**
  - nitpick: **4.4 %**
  - **dominant:** request‑changes

- **documentation (n = 1269)**
  - reject: **9.1 %**
  - request‑changes: **51.0 %**
  - nitpick: **22.3 %**
  - **dominant:** request‑changes

- **other (n = 493)**
  - reject: **23.1 %**
  - request‑changes: **26.2 %**
  - nitpick: **2.8 %**
  - **dominant:** discussion (no hard reject)

**Interpretation:**  
- **Reject‑first** categories are those where a violation is a clear deal‑breaker (API stability, correctness, concurrency).  
- **Request‑changes‑first** categories are those where the patch can be salvaged with a reasonable fix (performance, complexity, documentation).  
- **Nitpick‑first** appears mainly in style, where the change is harmless but undesirable.

## Severity Decision Tree
A concise, language‑agnostic decision procedure derived from the calibration data.

```
### Severity Decision Procedure
1. API/ABI break?
   - IF yes → reject (37.9% reject rate for api‑stability)
   - IF no → continue

2. Correctness violation (crash, memory safety, security)?
   - IF yes → reject (28.7% reject rate for correctness)
   - IF no → continue

3. Performance regression (measurable slowdown, added contention)?
   - IF yes → reject (20.0% reject rate for performance)
   - IF no → continue

4. Concurrency / synchronization issue?
   - IF yes → reject (22.3% reject rate for concurrency)
   - IF no → continue

5. Complexity / over‑engineering?
   - IF yes → request‑changes (38.2% request‑changes rate for complexity)
   - IF no → continue

6. Documentation mismatch or missing?
   - IF yes → request‑changes (51.0% request‑changes rate for documentation)
   - IF no → continue

7. Style / readability problem?
   - IF yes → nitpick (35.5% nitpick rate for style) or request‑changes if it hides a bug
   - IF no → approve
```

## Quick Reference Checklist
> Before approving any change, scan this list.  Items are grouped by the themes above.

- **API/ABI**
  - No changed signatures or removed symbols without a compatibility shim.
  - No new magic constants that replace existing flags.
  - No public struct layout changes without versioning.

- **Correctness**
  - No fatal assertions on recoverable conditions.
  - No unchecked pointer dereferences.
  - No hidden data races.

- **Performance**
  - No added lock contention in hot paths.
  - No unmeasured micro‑optimizations (e.g., extra branches, larger tables).
  - No regression in benchmark numbers.

- **Complexity**
  - No wrapper functions that add no value.
  - No duplicated logic across branches.
  - No special‑case code for rare scenarios.

- **Concurrency**
  - All shared mutable state protected by appropriate primitives.
  - No redundant lock/unlock pairs.
  - No use of lock‑free primitives where a lock is required.

- **Memory Safety**
  - No null pointer usage without checks.
  - No large stack allocations without justification.
  - No double‑free or use‑after‑free patterns.

- **Error Handling**
  - All error paths return meaningful, documented codes.
  - Recoverable errors are exposed to callers (e.g., EAGAIN).
  - No suppression of allocator warnings without proof.

- **Security**
  - No exposure of internal structures via system interface/proc.
  - No device that emits unsolicited data.
  - No reliance on weak hashes without migration plan.

- **Documentation**
  - Commit message starts with a concise subject line.
  - All new symbols have up‑to‑date docs/comments.
  - Kconfig/help strings are present and accurate.

- **Style**
  - No stray newline in logging macros.
  - No excessive underscores in identifiers.
  - Functions fit within two screenfuls unless justified.

- **Process**
  - No back‑merges without notification.
  - Pull requests contain signed tags if required.
  - Revert patches follow the “Revert …” format.

- **Testing**
  - Patch includes a test case or clear verification steps.
  - Reproducer or bisect instructions are provided for regressions.
  - Build succeeds on all supported configurations.

- **General**
  - “Talk is cheap. Show me the code.” – verify that the patch compiles and runs.  
  - “Good taste is when the special case disappears.” – look for data‑structure improvements.  
  - “If you can't bisect it, you can't trust it.” – ensure reproducibility.

Use this checklist as a **first pass**; any violation triggers the corresponding severity from the decision tree.