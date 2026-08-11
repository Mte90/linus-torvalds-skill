---
name: linus-torvalds-skill
description: "A language‑agnostic, project‑agnostic code‑review method distilled from thousands of Linus Torvalds’ review moves. It teaches an AI reviewer how to apply Linus’ strict correctness‑first, simplicity‑first mindset to any code base."
metadata:
  author: "torvalds‑skill pipeline"
  version: "1.0.0"
  tags:
    - code-review
    - reviewer-method
    - torvalds
---

# Linus Torvalds Review Method

> This skill is built from **38 293** real review moves extracted from the Linux kernel mailing list, covering categories such as API stability, performance, correctness, complexity, style, process, error‑handling, concurrency, memory‑safety, abstraction, testing, documentation and “other”. The corpus spans more than two decades of development and contains **9 110** explicit rejections, **16 162** requests for changes, **2 613** nitpicks and **2 685** approvals.  
> The method is **language‑ and project‑agnostic**: every rule is expressed as a design invariant, a precedence relationship, or a concrete detection pattern that makes sense to a reviewer of Python, Go, Rust, TypeScript, Java, Haskell or any other language.

## Reviewer Mindset

| Attitude | One‑line principle | Representative Linus quote |
|----------|-------------------|----------------------------|
| **1. Correctness above everything** | *Never let a recoverable condition crash the program.* | “What is the point of that **BUG_ON**? … there is *no* excuse for killing the kernel for things like this.” (Move 11, correctness) |
| **2. Simplicity beats cleverness** | *Prefer the simplest implementation that works; avoid “smart” tricks that are not measurably better.* | “I would much rather have a helper function … than a whole new flag that changes semantics.” (Move 9, api‑stability) |
| **3. Preserve the contract** | *Never break an existing public contract without a compelling reason.* | “What is *not* valid is clearly: removing the bogomips line.” (Move 4, api‑stability) |
| **4. Minimal public surface** | *Expose only what callers truly need; hide internal helpers.* | “I’d almost prefer if we *only* did `scoped_with_creds()` and didn’t have this version at all.” (Move 3, api‑stability) |
| **5. Measurable performance only** | *Accept performance changes only when they are proven and do not sacrifice correctness.* | “I tested it. It compiles, and it actually also solves the performance problem I was complaining about …” (Move 7, performance) |
| **6. Clear communication** | *State the problem, the reason for rejection, and the required fix in a direct, unambiguous way.* | “Please don’t do this. … If you can’t make the syntax be something clean and sane … then this code should simply not be converted to guards AT ALL.” (Move 25, style) |
| **7. Bisectability & reproducibility** | *Never merge a change that makes it impossible to bisect or reproduce the failure.* | “While I could easily just remove the duplicated lines in my merge, that would make things non‑bisectable, so I unpulled this instead.” (Move 1, process) |

These attitudes are the *why* behind every trigger and rule that follows.

## Review Triggers

Below is a **catalog of “when you see X, flag it” patterns**.  Each trigger is labeled with its type, a language‑agnostic description, the underlying design problem, the severity Linus used, and a verbatim Linus quote (the “Response”) that illustrates the exact tone and reasoning.

### Theme 1 – API Stability & Backward Compatibility

| # | Type | What to look for | Why it’s a problem | Severity | Example (original wording) |
|---|------|------------------|--------------------|----------|----------------------------|
| 1.1 | **invariant‑false** | A public output, log line, or command‑line flag is removed or renamed without a strong justification. | Breaks scripts, monitoring tools, and user expectations that rely on the stable output. | reject | **Generalized trigger:** *Removing an existing public output.* <br>**Quote:** “What is *not* valid is clearly: removing the bogomips line. … anybody who argues for removal is simply wrong.” (Move 4, api‑stability) |
| 1.2 | **general‑guideline** | A new variant of an existing public function is added (e.g., `with_creds()` **and** `scoped_with_creds()`). | Inflates the API surface, creates confusion, and forces downstream code to handle multiple versions. | request‑changes | **Generalized trigger:** *Adding unnecessary public variants.* <br>**Quote:** “I’d almost prefer if we *only* did `scoped_with_creds()` and didn’t have this version at all … I just suspect we could narrow down the new interface a bit more.” (Move 3, api‑stability) |
| 1.3 | **invariant‑false** | A long‑standing interface is altered in semantics (e.g., changing return conventions, adding flags, or redefining error handling). | Existing callers will mis‑behave; back‑porting becomes a nightmare. | reject | **Generalized trigger:** *Changing long‑standing public semantics.* <br>**Quote:** “Please don’t do this. This is a maintenance nightmare, and changes pretty much three decades of semantics …” (Move 11, api‑stability) |
| 1.4 | **general‑guideline** | A public function returns a value that mixes success/boolean with error codes, or uses inconsistent conventions across similar APIs. | Callers cannot reliably detect failure, leading to subtle bugs. | discussion | **Generalized trigger:** *Inconsistent error‑return conventions.* <br>**Quote:** “If there is any inconsistency, maybe we should make more cases use that ‘how many bytes/pages not copied’ logic …” (Move 12, api‑stability) |
| 1.5 | **invariant‑false** | An exported symbol uses a double‑underscore prefix (e.g., `__xchg`) that conventionally marks internal helpers. | Signals that the symbol is internal while it is exposed, confusing users and violating naming contracts. | reject | **Generalized trigger:** *Exposing internal‑style symbols publicly.* <br>**Quote:** “The whole point of two underscores is to say ‘don’t use this – it’s an internal implementation’ … is fundamentally bogus.” (Move 21, api‑stability) |
| 1.6 | **precedence‑rule** | A new system call or user‑space interface is proposed when an existing standard interface already provides the needed functionality. | Adding duplicate interfaces increases maintenance burden. | reject | **Generalized trigger:** *Proposing a new interface that duplicates an existing one.* <br>**Quote:** “Why would we bother to do better? System calls are cheap … I’d much rather have simple cheap interfaces than anything else.” (Move 18, api‑stability) |

### Theme 2 – Consistent & Safe Error Handling

| # | Type | What to look for | Why it’s a problem | Severity | Example (original wording) |
|---|------|------------------|--------------------|----------|----------------------------|
| 2.1 | **invariant‑false** | A fatal abort (panic, kernel BUG, etc.) is used for a condition that can be recovered or reported to the caller. | Crashes the whole system for a recoverable error, violating the “never crash on recoverable error” rule. | reject | **Generalized trigger:** *Using a fatal abort for a recoverable condition.* <br>**Quote:** “What is the point of that **BUG_ON**? … there is *no* excuse for killing the kernel for things like this.” (Move 11, correctness) |
| 2.2 | **invariant‑false** | An API mixes boolean success values with error codes (e.g., returning `0` for success in some places and a positive count in others). | Callers must guess the meaning; bugs appear when they treat a count as a boolean. | reject | **Generalized trigger:** *Mixing success booleans with error codes.* <br>**Quote:** “Well, some of the patches in the middle were confusing because of how `0/ERROR` was mixing with a success true/false thing …” (Move 2, error‑handling) |
| 2.3 | **invariant‑false** | A function returns a raw “bytes not copied” count instead of a conventional success (`0`) / error (`‑E…`) code. | Makes error checking cumbersome and encourages misuse. | nitpick | **Generalized trigger:** *Returning raw bytes‑not‑copied instead of conventional error codes.* <br>**Quote:** “I made sure that the return value is sensible (return 0 or ‑EFAULT rather than the `__memcpy_from_user()` return value …)” (Move 14, error‑handling) |
| 2.4 | **invariant‑false** | A patch adds a hard error (`‑EINVAL`) for a condition that is actually recoverable or optional. | Forces callers to treat a non‑fatal situation as fatal, reducing robustness. | reject | **Generalized trigger:** *Turning a recoverable condition into a hard error.* <br>**Quote:** “anybody who makes a hard error out of something that is recoverable is a total moron …” (Move 10, error‑handling) |
| 2.5 | **general‑guideline** | A driver returns an error code but does not clean up resources it allocated before the error. | Leaks memory, leaves stale state, and may cause later crashes. | reject | **Generalized trigger:** *Missing cleanup on error return.* <br>**Quote:** “So if a driver returns an error code, we should assume they screwed up potentially half‑way and clean up. We should *not* assume that we don’t need to.” (Move 9, error‑handling) |
| 2.6 | **general‑guideline** | A patch introduces a custom error‑handling pattern that deviates from the established project convention (e.g., custom signal handling loops). | Reduces code uniformity and makes future maintenance harder. | request‑changes | **Generalized trigger:** *Introducing ad‑hoc error‑handling patterns.* <br>**Quote:** “Please just use the normal pattern of doing `if (fatal_signal_pending(current)) return -EINTR;` …” (Move 6, error‑handling) |

### Theme 3 – Performance: Avoid Unnecessary Work

| # | Type | What to look for | Why it’s a problem | Severity | Example (original wording) |
|---|------|------------------|--------------------|----------|----------------------------|
| 3.1 | **general‑guideline** | A lock, lock primitive, or other heavyweight synchronization primitive is used to protect a single flag or simple value. | Wastes CPU cycles and obscures the real dependency; a lightweight atomic operation would suffice. | reject | **Generalized trigger:** *Using a heavyweight lock for a single primitive value.* <br>**Quote:** “Using a lock to serialize a single write is completely bogus. It adds zero serialization that a `WRITE_ONCE/READ_ONCE` pair doesn’t add.” (Move 4, concurrency) |
| 3.2 | **general‑guideline** | Code paths that perform expensive operations (e.g., sorting a huge commit log, deep tree traversals) in contexts that are not performance‑critical. | Increases latency for unrelated work and may cause time‑outs. | nitpick | **Generalized trigger:** *Running heavy analysis on a large repository without optimization.* <br>**Quote:** “Btw: a word of warning – git is efficient, but doing things like the above does require a bit of computing power …” (Move 3, performance) |
| 3.3 | **invariant‑false** | Unnecessary atomic read‑modify‑write cycles are introduced where a simple read or write would be sufficient. | Adds memory‑ordering overhead on all architectures. | request‑changes | **Generalized trigger:** *Adding unnecessary atomic operations.* <br>**Quote:** “So it might actually be that the non‑atomic version is safe … we could possibly get rid of the ‘atomic read‑and‑clear’ even for the non‑NUMA case.” (Move 20, performance) |
| 3.4 | **general‑guideline** | A patch adds a micro‑benchmark as the sole justification for a change, without showing real‑world impact. | Micro‑benchmarks can be misleading; real workloads matter more. | discussion | **Generalized trigger:** *Relying on a micro‑benchmark without broader evidence.* <br>**Quote:** “Hmm. Honestly, I’ve never seen anything like that in any kernel profiles … it must either be in the noise …” (Move 5, performance) |
| 3.5 | **general‑guideline** | A change removes a cheap early‑exit or “no‑op” path, causing extra work in the common case. | Degrades performance for the hot path without any benefit. | reject | **Generalized trigger:** *Removing a cheap early‑exit that makes the hot path slower.* <br>**Quote:** “Another way of saying this: how can a conditional schedule ever be nothing but a waste of cycles … I’d rather get a patch that just unconditionally makes the conditional schedules no‑ops …” (Move 19, performance) |
| 3.6 | **precedence‑rule** | When a performance improvement would require breaking an existing contract, the contract must be preserved. | Correctness and API stability outrank raw speed. | reject | **Generalized trigger:** *Performance change that breaks an API.* <br>**Quote:** “If you as a kernel developer cannot make a choice, … we do not change existing behavior …” (Move 20, api‑stability) |

### Theme 4 – Concurrency: Correct Synchronization

| # | Type | What to look for | Why it’s a problem | Severity | Example (original wording) |
|---|------|------------------|--------------------|----------|----------------------------|
| 4.1 | **invariant‑false** | A shared data structure is accessed without any explicit synchronization (no lock, atomic, or memory‑ordering primitive). | Leads to data races, corruption, and hard‑to‑reproduce bugs. | reject | **Generalized trigger:** *Unsynchronized access to shared mutable data.* <br>**Quote:** “If the coder doesn’t lock his data structures, it doesn’t matter what order we execute … different architectures will do different things …” (Move 7, concurrency) |
| 4.2 | **invariant‑false** | A lock is taken around a single write that could be performed with an atomic operation. | Over‑serialization, unnecessary contention. | reject | **Generalized trigger:** *Using a lock for a single primitive write.* <br>**Quote:** “Using a lock to serialize a single write is completely bogus …” (Move 4, concurrency) |
| 4.3 | **general‑guideline** | A code path relies on subtle compiler ordering tricks (e.g., `READ_ONCE` on a local variable, or `smp_load_acquire` without a matching release). | The ordering may be broken on some architectures; the code becomes non‑portable. | request‑changes | **Generalized trigger:** *Relying on subtle ordering without explicit primitives.* <br>**Quote:** “But if we want to have the code be obvious … I think `smp_load_acquire()` is the only actual ‘obvious’ thing to use.” (Move 3, concurrency) |
| 4.4 | **general‑guideline** | A global lock (e.g., a “big kernel lock”) is added when a finer‑grained lock already protects the data. | Reduces scalability and introduces unnecessary contention. | nitpick | **Generalized trigger:** *Adding a redundant global lock.* <br>**Quote:** “We properly lock the accesses … with `fs->lock`, and in fact no other users will have the BKL … I don’t see what the BKL would help in this case.” (Move 5, concurrency) |
| 4.5 | **general‑guideline** | A lock is held longer than necessary (e.g., spanning a large computation that could be done outside the critical section). | Increases contention and can cause deadlocks. | discussion | **Generalized trigger:** *Holding a lock longer than needed.* <br>**Quote:** “The only thing I don’t love about the batching is that we now do hold the lock over some situations where we could have allowed concurrency …” (Move 16, concurrency) |
| 4.6 | **precedence‑rule** | When a concurrency change could break correctness on any architecture, correctness outranks any performance gain. | Guarantees that the code works everywhere, not just on the author’s machine. | reject | **Generalized trigger:** *Performance‑oriented concurrency change that is not universally correct.* <br>**Quote:** “Never accept a concurrency change that can still yield incorrect results under any possible memory ordering …” (Move 6, concurrency) |

### Theme 5 – Simplicity & Complexity Reduction

| # | Type | What to look for | Why it’s a problem | Severity | Example (original wording) |
|---|------|------------------|--------------------|----------|----------------------------|
| 5.1 | **general‑guideline** | Multiple special‑case branches are introduced for a situation that can be handled by a single uniform path. | Increases code size, testing surface, and the chance of missed cases. | request‑changes | **Generalized trigger:** *Adding unnecessary special‑case handling.* <br>**Quote:** “I’d actually prefer to just simplify the logic entirely … let’s do the thing for both io_uring and vhost, and not split those two cases up.” (Move 3, complexity) |
| 5.2 | **invariant‑false** | An abstraction layer is added that hides a clear performance cost without providing measurable benefit (e.g., a wrapper that adds a function call for a trivial operation). | Makes the cost invisible, hurts performance, and complicates debugging. | reject | **Generalized trigger:** *Adding an abstraction that hides cost.* <br>**Quote:** “Adding these kinds of ‘abstraction layers’ … makes it less obvious at the code level what the ‘costs’ are.” (Move 9, abstraction) |
| 5.3 | **general‑guideline** | Duplicate logic is kept in two places instead of being shared via a common helper. | Increases maintenance burden and risk of divergence. | approve | **Generalized trigger:** *Duplicated logic that could be shared.* <br>**Quote:** “Yeah, I think you’d actually end up with better behaviour by just sharing the lock logic …” (Move 20, complexity) |
| 5.4 | **invariant‑false** | Configuration options introduce a quinary (five‑state) logic where a simple binary choice suffices. | Leads to ambiguous states and harder reasoning. | discussion | **Generalized trigger:** *Introducing overly complex configuration states.* <br>**Quote:** “You can get inconsistent situations … ‘select’ actually is much nicer …” (Move 4, complexity) |
| 5.5 | **invariant‑false** | Functions accept parameters that are never used or are always false (e.g., a `was_async` flag that is always false). | Clutters the API and misleads readers. | request‑changes | **Generalized trigger:** *Unnecessary function parameters.* <br>**Quote:** “Could we please just remove that whole ‘was_async’ case entirely …?” (Move 11, complexity) |
| 5.6 | **precedence‑rule** | When a simplification would remove a feature that a minority of users rely on, the benefit to the majority must outweigh the loss. | Guarantees that simplifications are not made at the expense of a legitimate use‑case. | discussion | **Generalized trigger:** *Simplifying at the cost of a rare feature.* <br>**Quote:** “Asking the kernel to do complex things … for something that is very very rare … is the wrong approach.” (Move 12, complexity) |

### Theme 6 – Naming & Visibility Conventions

| # | Type | What to look for | Why it’s a problem | Severity | Example (original wording) |
|---|------|------------------|--------------------|----------|----------------------------|
| 6.1 | **invariant‑false** | Public symbols use a double‑underscore prefix (e.g., `__invalidate_device2`). | Violates the convention that double‑underscore names are internal; external users may misuse them. | reject | **Generalized trigger:** *Exposing double‑underscore symbols publicly.* <br>**Quote:** “The whole point of two underscores is to say ‘don’t use this – it’s an internal implementation’ … is fundamentally bogus.” (Move 21, api‑stability) |
| 6.2 | **general‑guideline** | A name is chosen that does not reflect the actual semantics of the parameter (e.g., a parameter called “bus info” that is actually just a unique identifier). | Misleads callers and leads to misuse. | request‑changes | **Generalized trigger:** *Mischaracterizing a parameter’s purpose.* <br>**Quote:** “But it isn’t ‘bus info’. It’s a unique number … tells `ioremap()` what area to remap.” (Move 14, api‑stability) |
| 6.3 | **general‑guideline** | A macro conflict is resolved by renaming the function (adding an underscore) instead of undefining the macro. | Creates unnecessary name pollution and makes the code harder to follow. | discussion | **Generalized trigger:** *Renaming functions to avoid macro clashes.* <br>**Quote:** “I wonder if it wouldn’t be simpler to just have a `#undef lockref_put_or_lock` … and keep the same name.” (Move 4, style) |
| 6.4 | **invariant‑false** | An opaque type is introduced that hides the real structure without a compelling reason (e.g., `struct trace_pid_list`). | Breaks type‑based tooling and confuses developers. | reject | **Generalized trigger:** *Introducing unnecessary opaque types.* <br>**Quote:** “Ugh, please no. This is going to be very confusing …” (Move 6, abstraction) |
| 6.5 | **general‑guideline** | A public API requires callers to know implementation‑defined details (e.g., signedness of `char`). | Forces callers into non‑portable code. | reject | **Generalized trigger:** *Exposing implementation‑defined details to callers.* <br>**Quote:** “The caller cannot and must not care! Because the sign of ‘char’ is implementation‑defined …” (Move 22, api‑stability) |
| 6.6 | **precedence‑rule** | When naming conflicts arise, prefer fixing the macro or using a local `#undef` rather than creating a new public symbol. | Keeps the namespace clean and avoids unnecessary API bloat. | discussion | **Generalized trigger:** *Prefer macro undefinition over new public symbols.* <br>**Quote:** “I don’t think this is wrong per se, but rather than rename the function, I wonder if it wouldn’t be simpler to just have a `#undef …`.” (Move 4, style) |

### Theme 7 – Documentation Accuracy & Clarity

| # | Type | What to look for | Why it’s a problem | Severity | Example (original wording) |
|---|------|------------------|--------------------|----------|----------------------------|
| 7.1 | **invariant‑false** | A comment or documentation line misrepresents what the code actually does (e.g., claiming “`<= 0` tests the sign”). | Misleads future maintainers; bugs can be introduced when the comment is taken as truth. | reject | **Generalized trigger:** *Incorrect comment describing code behavior.* <br>**Quote:** “The original comment is correct, and your changed comment is nonsensical, since ‘<= 0’ doesn’t actually test the sign …” (Move 1, documentation) |
| 7.2 | **invariant‑false** | Documentation states a behavior that contradicts the implementation (e.g., docs say a map is read‑only but the code treats it as private). | Users rely on docs and get unexpected results. | reject | **Generalized trigger:** *Documentation contradicts actual behavior.* <br>**Quote:** “Wrong documentation is irrelevant. It doesn’t matter if the documentation says ‘X’, when the code does ‘Y’ …” (Move 5, documentation) |
| 7.3 | **general‑guideline** | A commit message lacks a concise one‑line summary followed by a blank line and detailed body. | Reduces readability of history and makes `git log` less useful. | nitpick | **Generalized trigger:** *Missing proper commit message structure.* <br>**Quote:** “Grr. Somebody isn’t following the nice rules we have and that git encourages: make a commit message be a nice ‘one‑line header’ with the more complete explanation separated by an empty line …” (Move 21, style) |
| 7.4 | **invariant‑false** | Magic numbers appear in code or macros without an explanatory name (e.g., `#define FASTOP_LENGTH (7 + ENDBR_INSN_SIZE + RET_LENGTH)`). | Future readers cannot understand the origin or purpose, leading to errors. | discussion | **Generalized trigger:** *Magic numbers without named constants.* <br>**Quote:** “In fact, the remaining question is just ‘where did the 7 come from’ …” (Move 10, documentation) |
| 7.5 | **general‑guideline** | Documentation does not mention a known limitation or pitfall of an interface (e.g., missing warning about non‑canonical user addresses). | Users may misuse the API and encounter hard‑to‑debug failures. | request‑changes | **Generalized trigger:** *Missing documentation of a known pitfall.* <br>**Quote:** “But I think it’s easier to just keep that existing warning about ‘how did you get a non‑canonical address here’ …” (Move 19, error‑handling) |
| 7.6 | **precedence‑rule** | When a documentation change would be large but the code change is small, prioritize fixing the code first; documentation follows. | Guarantees that the functional issue is resolved before polishing prose. | discussion | **Generalized trigger:** *Prioritizing code fixes over documentation updates.* <br>**Quote:** “I think the approach should clearly spell what the trouble level is …” (Move 19, error‑handling) |

### Theme 8 – Memory Safety

| # | Type | What to look for | Why it’s a problem | Severity | Example (original wording) |
|---|------|------------------|--------------------|----------|----------------------------|
| 8.1 | **invariant‑false** | A pointer to a stack‑allocated object is stored and later dereferenced after the function returns. | Leads to use‑after‑free and possible kernel oops. | reject | **Generalized trigger:** *Escaping a stack‑allocated pointer.* <br>**Quote:** “That’s unacceptably buggy crap. `rpc_wait_for_completion_task()` will happily exit on a deadly signal … now you’ll have a stale pointer to a stack that has been freed.” (Move 3, memory‑safety) |
| 8.2 | **invariant‑false** | Uninitialized automatic variables are used in calculations or passed to other functions. | Causes undefined behaviour and potential security issues. | discussion | **Generalized trigger:** *Using uninitialized variables.* <br>**Quote:** “Maybe we could have gcc just always initialize variables to zero … this might be one of those cheap things where we just avoid undefined behavior …” (Move 23, memory‑safety) |
| 8.3 | **invariant‑false** | A raw address is cast to a pointer and dereferenced without proper mapping (e.g., treating a physical address as a normal pointer). | May cause page faults, data corruption, or security breaches. | reject | **Generalized trigger:** *Casting raw addresses to pointers without mapping.* <br>**Quote:** “Ouch. Who does that, anyway? It’s wrong to do that. It’s not a pointer … you’d need to do an `ioremap()` on it to turn it into a pointer.” (Move 16, memory‑safety) |
| 8.4 | **invariant‑false** | A buffer is written past its allocated size, even if the terminating NUL is not used. | Overwrites adjacent memory, leading to corruption. | approve | **Generalized trigger:** *Writing beyond buffer boundaries.* <br>**Quote:** “Right. The seqfile code really doesn’t care about the terminating NUL … just cares that the buffer isn’t overwritten past the end.” (Move 25, memory‑safety) |
| 8.5 | **invariant‑false** | Placeholder magic values (e.g., `0x0123456789abcdef`) are used as default pointers or addresses. | If ever dereferenced, they cause immediate crashes; they also hide the fact that the value is invalid. | request‑changes | **Generalized trigger:** *Using non‑valid magic constants as defaults.* <br>**Quote:** “I picked the default value … because it’s easy to see in disassembly … but it sure as hell ain’t right.” (Move 12, memory‑safety) |
| 8.6 | **general‑guideline** | A function returns data that may have been freed or re‑used (e.g., returning a pointer into a folio that has been reclaimed). | Users may read stale data, leading to security leaks. | reject | **Generalized trigger:** *Returning possibly stale data from a freed object.* <br>**Quote:** “And this is fatal. We might have optimistically copied things that are now security‑sensitive … user space should never have seen that data.” (Move 24, memory‑safety) |

### Theme 9 – Process, Workflow & Bisectability

| # | Type | What to look for | Why it’s a problem | Severity | Example (original wording) |
|---|------|------------------|--------------------|----------|----------------------------|
| 9.1 | **invariant‑false** | A patch requires manual editing of the source after applying (e.g., removing duplicated lines by hand). | Breaks reproducibility; the change cannot be bisected cleanly. | reject | **Generalized trigger:** *Patch that needs manual post‑apply edits.* <br>**Quote:** “While I could easily just remove the duplicated lines in my merge, that would make things non‑bisectable, so I unpulled this instead.” (Move 1, process) |
| 9.2 | **invariant‑false** | A commit message is an automatic merge line with no explanation of *why* the merge is performed. | Future readers cannot understand the intent, making history noisy. | reject | **Generalized trigger:** *Automatic merge commit without explanation.* <br>**Quote:** “I’m not pulling this useless commit message: ‘Merge tag ‘v4.20‑rc1’’ with absolutely zero explanation …” (Move 9, documentation) |
| 9.3 | **invariant‑false** | The author rebases a public branch that other developers depend on without coordination. | Breaks downstream histories and forces everyone to re‑base. | reject | **Generalized trigger:** *Rebasing a public branch without coordination.* <br>**Quote:** “Stop being a moron. Just don’t do it. If your tree is so ugly that you can’t deliver it upstream, then don’t deliver it sideways or downstream either.” (Move 6, process) |
| 9.4 | **general‑guideline** | The patch does not include a clear description of *what* is being changed and *why* (e.g., missing rationale in the PR description). | Reviewers waste time guessing intent; the change may be rejected. | approve | **Generalized trigger:** *Missing clear description of change.* <br>**Quote:** “It all looks fine to me. You have all the important parts: what you are merging, and *why* you are merging it.” (Move 2, process) |
| 9.5 | **invariant‑false** | Configuration options are added with a default that enables a feature on hardware that does not exist yet. | Users end up with broken builds on existing hardware. | request‑changes | **Generalized trigger:** *Enabling optional hardware features by default.* <br>**Quote:** “Why would I want to enable this in my kernel when there are no actual CPUs out yet that support it? … it needs a real opt‑in configuration.” (Move 5, process) |
| 9.6 | **general‑guideline** | The contributor uses the generic `patch` tool for a change that involves file renames or mode changes, instead of `git‑apply`. | The change may be applied incorrectly, losing rename information. | request‑changes | **Generalized trigger:** *Using the wrong tool for rename/copy patches.* <br>**Quote:** “If the patch contains rename/copy‑patches or mode updates, you *need* to use `git‑apply` …” (Move 13, process) |

### Theme 10 – Testing & Verification

| # | Type | What to look for | Why it’s a problem | Severity | Example (original wording) |
|---|------|------------------|--------------------|----------|----------------------------|
| 10.1 | **invariant‑false** | A change to low‑level architecture‑specific code is submitted without any accompanying test or verification on the affected architecture. | Subtle regressions may go unnoticed on that platform. | reject | **Generalized trigger:** *Missing architecture‑specific testing.* <br>**Quote:** “Be very careful when changing that code … please try to give it some nice stress‑testing (both on ppc and x86) …” (Move 3, testing) |
| 10.2 | **invariant‑false** | A patch claims a performance improvement but only provides a micro‑benchmark that does not reflect real workloads. | The “improvement” may be irrelevant or even harmful in production. | discussion | **Generalized trigger:** *Micro‑benchmark without real‑world relevance.* <br>**Quote:** “The benchmark … literally did a single byte write to each page … that really isn’t realistic for any real load.” (Move 2, performance) |
| 10.3 | **invariant‑false** | No test exists for an error path that the patch introduces (e.g., overlapping resource ranges). | The error path may be broken, leading to crashes in edge cases. | request‑changes | **Generalized trigger:** *Missing test for a new error path.* <br>**Quote:** “You’re not actually showing the case where you have that error case … IOW, that one is done in some totally different place …” (Move 1, testing) |
| 10.4 | **invariant‑false** | A change is merged without being run through the “linux‑next” integration tree or without a reproducible test case. | The change may conflict with other in‑flight patches. | reject | **Generalized trigger:** *Merging without integration testing.* <br>**Quote:** “If I get the feeling that the problem was that there just wasn’t enough care to begin with, that’s when I go ‘nope, this will need to wait for another release and be done properly’.” (Move 8, testing) |
| 10.5 | **general‑guideline** | The author provides a reproducible test case or script that demonstrates the bug before submitting the fix. | Makes the review faster and ensures the fix actually addresses the problem. | approve | **Generalized trigger:** *Providing a reproducible test case.* <br>**Quote:** “Looks good to me, feel free to push any time (assuming you’ve gotten testing confirmation from the people who reported it).” (Move 5, testing) |
| 10.6 | **precedence‑rule** | When a change fixes a bug *and* adds a new feature, the bug‑fix part is merged first; the feature is held back until it is fully vetted. | Guarantees that critical fixes reach users quickly. | discussion | **Generalized trigger:** *Separating bug‑fix from new feature in a patch series.* <br>**Quote:** “I think I can take the entire series. It’s removing code and fixing a couple of bugs … Even if not all changes are pure fixes …” (Move 18, testing) |

### Theme 11 – Style, Readability & Maintainability

| # | Type | What to look for | Why it’s a problem | Severity | Example (original wording) |
|---|------|------------------|--------------------|----------|----------------------------|
| 11.1 | **invariant‑false** | Use of non‑standard language extensions that make the code hard to read for newcomers (e.g., GCC‑specific statement expressions). | Reduces portability and increases learning curve. | reject | **Generalized trigger:** *Non‑standard language extensions.* <br>**Quote:** “Similarly, what the hell does the gcc extension ‘int a; (char)a += b;’ really mean? The whole extension is just braindamaged …” (Move 1, style) |
| 11.2 | **invariant‑false** | Complex conditional expressions that are hard to parse (e.g., `if (bvprv && cluster)`). | Obscures intent and makes bugs easy to hide. | nitpick | **Generalized trigger:** *Unreadable complex conditionals.* <br>**Quote:** “Your patch makes the code almost totally unreadable, with that subtle issue of the ‘if (bvprv && cluster)’ case …” (Move 7, style) |
| 11.3 | **invariant‑false** | Adding or removing blank lines, extra newlines, or other cosmetic changes that do not improve readability or fix bugs. | Generates noisy churn without value. | reject | **Generalized trigger:** *Cosmetic whitespace changes without benefit.* <br>**Quote:** “I find this noise to add ‘\n’ characters completely pointless. It’s bogus stupid churn that doesn’t actually make the source code better …” (Move 16, style) |
| 11.4 | **invariant‑false** | Introducing a macro that makes a simple statement harder to understand (e.g., `cond_guard()` that expands to a multi‑line `if`). | Hides control flow and makes debugging harder. | reject | **Generalized trigger:** *Obscuring control flow with macros.* <br>**Quote:** “If you can’t make the syntax be something clean and sane … then this code should simply not be converted to guards AT ALL.” (Move 25, style) |
| 11.5 | **general‑guideline** | Use full, non‑contracted wording in comments and documentation (e.g., “cannot” instead of “can’t”). | Improves searchability and clarity. | nitpick | **Generalized trigger:** *Using contracted words in comments.* <br>**Quote:** “Ugh, please make things like this just write out the full non‑contracted thing. Ie ‘cannot’ is a perfectly fine word …” (Move 3, style) |
| 11.6 | **precedence‑rule** | When a style change would improve readability *and* fix a bug, the bug fix takes precedence; style‑only changes are nitpicks. | Ensures that effort is focused on functional improvements. | discussion | **Generalized trigger:** *Prioritizing functional fixes over pure style.* <br>**Quote:** “But whatever. This series has gotten way too much bike‑shedding … I think it should just be applied, since it does remove lines of code overall.” (Move 23, style) |

### Theme 12 – Security & Safety

| # | Type | What to look for | Why it’s a problem | Severity | Example (original wording) |
|---|------|--------------------|--------------------|----------|----------------------------|
| 12.1 | **invariant‑false** | An interface exposes low‑level hardware details without proper synchronization or validation (e.g., `O_DIRECT` interface). | Opens attack surface and can lead to data corruption. | reject | **Generalized trigger:** *Exposing unsafe low‑level interfaces.* <br>**Quote:** “The interface is fundamentally flawed, it has nasty security issues, it lacks any kind of sane synchronization, and it exposes stuff that shouldn’t be exposed to user space.” (Move 3, abstraction) |
| 12.2 | **invariant‑false** | A change adds a new way for user‑space to attach to a process during `execve`. | Creates a potential privilege‑escalation vector. | reject | **Generalized trigger:** *Allowing user‑space attachment during exec.* <br>**Quote:** “I’m almost inclined to say that we should just abort the `execve()` entirely if somebody tries to attach in the middle.” (Move 7, other) |
| 12.3 | **invariant‑false** | A patch disables or ignores a security‑related warning (e.g., treating `WARN_ON` as harmless). | Hides real problems and reduces overall security posture. | request‑changes | **Generalized trigger:** *Silencing security warnings.* <br>**Quote:** “Can you try to call these warnings, not oopses? It’s not an oops … it’s a `WARN_ON` …” (Move 17, documentation) |
| 12.4 | **invariant‑false** | A cryptographic algorithm is introduced without proper review (e.g., “post‑quantum” hype). | May give a false sense of security and introduce vulnerabilities. | request‑changes | **Generalized trigger:** *Introducing unvetted cryptographic mechanisms.* <br>**Quote:** “Yes, please stop using RSA … but let’s not throw the ‘Post Quantum’ word around as if it was reality.” (Move 4, other) |
| 12.5 | **general‑guideline** | A feature that could leak internal kernel state to user space is proposed (e.g., exposing internal I/O timing via a new system interface entry). | Information leakage can aid attackers. | reject | **Generalized trigger:** *Exposing internal state to user space without a clear need.* <br>**Quote:** “We will never give user space those kinds of guarantees … that’s even more true when this is an information leak that we shouldn’t expose …” (Move 21, other) |
| 12.6 | **precedence‑rule** | When a security fix conflicts with a performance optimization, the security fix wins. | Guarantees that the system remains safe even if it runs a bit slower. | discussion | **Generalized trigger:** *Security overrides performance.* <br>**Quote:** “I think the right thing is to keep the security check even if it adds a tiny overhead …” (paraphrased from multiple security‑related moves) |

---

## Precedence and Priorities

The following hierarchy resolves **any conflict** between rules.  It is expressed in plain English and reinforced by Linus’ own words.

| Level | Principle | Why it takes precedence | Representative Linus quote |
|-------|-----------|------------------------|----------------------------|
| **1. Correctness (invariants, safety, no crashes)** | *Never let a recoverable condition crash the system; never break a contract.* | A crash or silent data loss is far worse than any performance gain or aesthetic improvement. | “What is the point of that **BUG_ON**? … there is *no* excuse for killing the kernel for things like this.” (Move 11, correctness) |
| **2. Protecting Existing Users / API Stability** | *Never change a public interface without a compelling reason.* | Existing users depend on stable contracts; breaking them forces downstream maintenance. | “What is *not* valid is clearly: removing the bogomips line.” (Move 4, api‑stability) |
| **3. Security** | *Never introduce a change that widens the attack surface or hides a security warning.* | Security breaches can have catastrophic impact; they outrank performance and simplicity. | “The interface is fundamentally flawed … it has nasty security issues.” (Move 3, abstraction) |
| **4. Measured Performance** | *Accept performance changes only when they are demonstrably beneficial and do not violate higher‑level rules.* | Performance is valuable, but never at the expense of correctness, stability, or security. | “I tested it. It compiles, and it actually also solves the performance problem …” (Move 7, performance) |
| **5. Simplicity / Low Complexity** | *Prefer the simplest design that satisfies the requirements.* | Simpler code is easier to audit, test, and maintain. | “I’d much rather have simple cheap interfaces than anything else.” (Move 18, performance) |
| **6. Style & Readability** | *Make the code easy to read and reason about.* | Readable code reduces future bugs; however, style never overrides correctness or security. | “The patch really is ugly, and already adds random stuff …” (Move 9, style) |
| **7. Bisectability & Reproducibility** | *Changes must remain bisectable; avoid manual edits after applying a patch.* | Enables fast regression isolation. | “While I could easily just remove the duplicated lines … that would make things non‑bisectable, so I unpulled this instead.” (Move 1, process) |

When a reviewer encounters a situation that triggers multiple rules, **apply the highest‑ranked rule**.  For example, a patch that removes a lock (performance win) but leaves a data race (correctness violation) must be rejected because correctness is level 1.

---

## Key Definitions

| Term | Precise definition | Linus quote illustrating usage |
|------|--------------------|--------------------------------|
| **Bug** | A condition that causes incorrect behavior, crashes, data corruption, or security vulnerabilities. | “I think the patch is a bug because it corrupts `rid/rdp` … bits that *should* be zero are not.” (Move 20, correctness) |
| **Hack / Workaround** | A temporary fix that masks the root cause without addressing it; often a code path that “just works” for a narrow case. | “That’s an acceptable hack in the presence of the current locking … I’m not exactly happy about it …” (Move 23, correctness) |
| **Patch** | A neutral term for a code change, regardless of size or intent. | “I think the patch looks fine …” (Move 23, other) |
| **Non‑negotiable** | A rule that has **no exceptions**; violating it always leads to rejection. | “Never break existing APIs without compelling reason.” (derived from multiple API‑stability moves) |
| **Recoverable error** | An error condition that the caller can handle gracefully (e.g., by returning an error code, cleaning up, or retrying). | “If you call `fd_publish()` … you could often unify the error/success paths.” (Move 1, api‑stability) |
| **API contract** | The documented or implied behavior that external code depends on; includes function signatures, return conventions, and side‑effects. | “If you as a kernel developer cannot make a choice … we do not change existing behavior.” (Move 20, api‑stability) |

---

## Anti‑Patterns

| Anti‑Pattern | What it looks like (language‑agnostic) | Why it’s wrong | Linus quote | What to do instead |
|--------------|----------------------------------------|----------------|-------------|--------------------|
| **Over‑engineering** | Adding layers of abstraction, configuration knobs, or generic helpers for a trivial operation. | Hides real cost, makes code harder to audit, and often introduces bugs. | “Adding these kinds of ‘abstraction layers’ … makes it less obvious what the ‘costs’ are.” (Move 9, abstraction) | Keep the implementation flat; expose the cost directly. |
| **API bloat** | Introducing multiple variants of the same function, or exposing internal helpers as public symbols. | Increases maintenance, confuses callers, and multiplies the testing surface. | “I’d almost prefer if we *only* did `scoped_with_creds()` and didn’t have this version at all.” (Move 3, api‑stability) | Provide a single, well‑named entry point; hide internal helpers. |
| **Breaking users without justification** | Removing or changing a public output, flag, or system call without a compelling reason. | Forces downstream projects to patch themselves; can cause widespread breakage. | “What is *not* valid is clearly: removing the bogomips line.” (Move 4, api‑stability) | Keep the old behavior; if a change is needed, add a new optional interface. |
| **Cleverness without measurement** | Adding a micro‑benchmark, a fancy compiler trick, or a non‑portable optimization that is not proven on real workloads. | May degrade performance on other hardware; adds hidden complexity. | “I’m not seeing anything like that in any kernel profiles … it must be noise.” (Move 5, performance) | Measure on representative workloads; prefer portable, well‑understood constructs. |
| **Heavy synchronization for trivial data** | Using a lock primitive or spin‑lock to protect a single flag or counter. | Wastes CPU cycles and can cause priority inversion. | “Using a lock to serialize a single write is completely bogus.” (Move 4, concurrency) | Use atomic primitives or lock‑free techniques when protecting a single primitive. |
| **Magic numbers / hidden units** | Hard‑coded constants without a named constant or comment, or mixing seconds/milliseconds across interfaces. | Leads to bugs, makes code unreadable, and hampers cross‑project reuse. | “Where did the 7 come from?” (Move 10, documentation) | Define named constants with clear comments; keep units explicit. |
| **Unverified security changes** | Adding a new cryptographic primitive, exposing internal state, or disabling a security check without review. | Opens attack vectors; security regressions are hard to detect later. | “We will never give user space those kinds of guarantees …” (Move 21, other) | Submit to security experts; keep the default secure. |
| **Non‑bisectable patches** | Requiring manual edits after applying a patch, or merging without a clear commit message. | Makes regression isolation impossible. | “That would make things non‑bisectable, so I unpulled this instead.” (Move 1, process) | Ensure the patch applies cleanly and is self‑contained; write a proper commit message. |

---

## Voice and Tone

Linus’s feedback follows a **direct, certain, and explanatory** pattern:

| Situation | How Linus phrases the rejection | Why this tone works |
|-----------|--------------------------------|---------------------|
| **Clear violation** (e.g., fatal abort for recoverable error) | “What is the point of that **BUG_ON**? … there is *no* excuse for killing the kernel for things like this.” | Leaves no doubt; the rule is absolute. |
| **Ambiguous or borderline** | “I would much rather have a helper function … than a whole new flag that changes semantics.” | Suggests a concrete alternative while still being firm. |
| **Repeated mistakes** | “Ugh, please make things like this just write out the full non‑contracted thing.” | Shows irritation but remains constructive. |
| **When a change is acceptable** | “That looked fine to me, btw. Looks like an improvement even outside the … issue.” | Gives a brief positive affirmation, encouraging the contributor. |
| **When extra context is needed** | “Can you please add a clear commit log and maybe a code comment …?” | Requests the missing information without being dismissive. |
| **Humor / analogy** | “Here’s a nickel, Kid. Go buy yourself a real computer.” | Lightens the mood while still delivering a firm “no”. |

**Guidelines for the reviewer:**

1. **State the rule first** – “This violates rule #1 (Correctness).”
2. **Quote the offending code or description** (optional, but helpful).
3. **Explain the consequence** – why it matters.
4. **Offer a concrete fix** – a one‑sentence suggestion.
5. **Keep the tone confident, not apologetic.**  If the change is acceptable, a short “Looks good” is enough.

---

## Common Review Scenarios

Below are five representative scenarios that illustrate the method in action.  All descriptions are **language‑agnostic**.

### Scenario 1 – API Breakage Attempt
- **Situation:** A contributor proposes to drop an old flag from a public configuration API and rename the output field.
- **What to look for:** Removal of an existing public symbol, change of output format, or renaming without deprecation path.
- **How to respond:**  
  **Rule #2 (API stability) → reject.**  
  **Quote:** “What is *not* valid is clearly: removing the bogomips line. … anybody who argues for removal is simply wrong.”  
  **Severity:** reject.
- **Result:** The patch is rejected; the author must keep the flag or add a new optional one.

### Scenario 2 – Unsafe Error Handling
- **Situation:** A new driver returns `‑EINVAL` for a condition that is merely a user‑configuration mistake and does not clean up an allocated buffer.
- **What to look for:** Hard error for a recoverable condition, missing cleanup.
- **How to respond:**  
  **Rule #1 (Correctness) → reject.**  
  **Quote:** “Any‑body who makes a hard error out of something that is recoverable is a total moron …”  
  **Severity:** reject.
- **Result:** The driver must return a non‑fatal code and free the buffer before returning.

### Scenario 3 – Unnecessary Lock
- **Situation:** A patch adds a lock primitive around a single boolean flag that is only ever set by one thread.
- **What to look for:** Heavy synchronization for a trivial value.
- **How to respond:**  
  **Rule #4 (Concurrency) → reject.**  
  **Quote:** “Using a lock to serialize a single write is completely bogus. It adds zero serialization that a `WRITE_ONCE/READ_ONCE` pair doesn’t add.”  
  **Severity:** reject.
- **Result:** Replace the lock primitive with an atomic store or remove the lock entirely.

### Scenario 4 – Missing Test for New Error Path
- **Situation:** A new validation function returns `‑EFAULT` on malformed input, but the test suite only covers the success path.
- **What to look for:** No test exercising the error branch.
- **How to respond:**  
  **Rule #10 (Testing) → request‑changes.**  
  **Quote:** “You’re not actually showing the case where you have that error case … IOW, that one is done in some totally different place.”  
  **Severity:** request‑changes.
- **Result:** The author adds a test that feeds malformed input and verifies the error return.

### Scenario 5 – Over‑Engineered Abstraction
- **Situation:** A developer introduces a generic “buffer manager” object to wrap a simple pointer‑plus‑size pair, claiming future extensibility.
- **What to look for:** New abstraction that adds indirection without measurable benefit.
- **How to respond:**  
  **Rule #5 (Simplicity) → reject.**  
  **Quote:** “Adding these kinds of ‘abstraction layers’ … makes it less obvious at the code level what the ‘costs’ are.”  
  **Severity:** reject.
- **Result:** The author removes the wrapper and uses the plain pointer‑plus‑size structure.

---

## Decision Framework

A textual flow‑chart that an AI reviewer can follow when scanning a change:

1. **Is there any code that can cause a crash, data corruption, or security breach?**  
   - **Yes →** Apply **Rule #1 (Correctness)**. If the code is unsafe, **reject** immediately.  
   - **No →** Continue.

2. **Does the change modify a public API, output format, or user‑visible behavior?**  
   - **Yes →** Apply **Rule #2 (API stability)**. If the modification is not justified, **reject**; if it is a harmless addition, **request‑changes** for documentation.  
   - **No →** Continue.

3. **Does the patch add, remove, or change synchronization primitives?**  
   - **Yes →** Apply **Rule #4 (Concurrency)**. If a heavyweight lock protects a trivial value, **reject**. If ordering is unclear, **request‑changes** for explicit primitives.  
   - **No →** Continue.

4. **Is there any new abstraction, configuration option, or extra parameter that is not needed for the primary use case?**  
   - **Yes →** Apply **Rule #5 (Simplicity)**. If the abstraction adds cost without benefit, **reject**.  
   - **No →** Continue.

5. **Are there missing tests, or does the change affect architecture‑specific code without verification?**  
   - **Yes →** Apply **Rule #10 (Testing)**. **Reject** or **request‑changes** until proper tests are added.  
   - **No →** Continue.

6. **Is the patch style‑only (formatting, whitespace, naming) and does it affect correctness?**  
   - **Yes →** Apply **Rule #6 (Style)**. If it is pure cosmetic, **nitpick**; if it hides a bug, **reject**.  
   - **No →** Continue.

7. **Does the patch break bisectability (manual edits, missing commit message, rebasing public history)?**  
   - **Yes →** Apply **Rule #7 (Process)**. **Reject** or **request‑changes** to make the change clean.  
   - **No →** Approve.

At each decision point, the reviewer should **emit the appropriate severity tag** (`reject`, `request‑changes`, `nitpick`, `approve`) and include a concise Linus‑style explanation.

---

## Quick Reference Checklist

> **Before approving any change, verify:**  

1. **Correctness**  
   - No `BUG_ON`‑style fatal abort for recoverable conditions.  
   - All shared mutable data is protected by explicit synchronization.  
   - No use‑after‑free, dangling pointers, or uninitialized variables.  
2. **API Stability**  
   - No removal or silent change of existing public symbols, outputs, or syscalls.  
   - New public functions follow the minimal‑surface principle.  
   - Naming conventions (`__` prefix → internal only) are respected.  
3. **Security**  
   - No exposure of unsafe low‑level hardware interfaces.  
   - No suppression of security‑related warnings.  
   - No unvetted cryptographic primitives.  
4. **Performance (only after 1‑3 pass)**  
   - No unnecessary locks, atomics, or heavyweight synchronization for trivial data.  
   - No added abstraction that hides a measurable cost.  
   - Benchmarks, if provided, reflect realistic workloads.  
5. **Simplicity & Complexity**  
   - No special‑case branches that could be unified.  
   - No duplicate logic; shared helpers are used where appropriate.  
   - Configuration options are binary unless a genuine three‑state is required.  
6. **Documentation & Style**  
   - Comments accurately describe the code.  
   - No magic numbers without named constants.  
   - Commit messages have a one‑line summary, blank line, then detailed body.  
   - No non‑standard language extensions or unreadable conditionals.  
7. **Process & Bisectability**  
   - Patch applies cleanly without manual edits.  
   - No rebasing of public history without coordination.  
   - Proper tooling (`git‑apply`) is used for renames/copies.  
8. **Testing**  
   - New code paths have corresponding tests, especially error paths.  
   - Architecture‑specific changes are verified on all relevant platforms.  
   - The change has passed through the integration tree (e.g., `linux‑next`).  

If **any** item fails, apply the highest‑ranked rule from the **Precedence and Priorities** section and respond with the appropriate severity.

---