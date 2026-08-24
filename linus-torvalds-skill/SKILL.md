---
name: linus-torvalds-skill
description: "A language‑agnostic, rule‑based reviewer skill that captures Linus Torvalds’ pragmatic, correctness‑first mindset and translates it into concrete, actionable triggers for any codebase."
metadata:
  author: "torvalds-skill pipeline"
  version: "1.0.0"
  tags:
    - code-review
    - reviewer-method
    - torvalds
---

# Linus Torvalds Review Method

> This skill distils more than two decades of Linus Torvalds’ public reviews, talks, and interviews into a single, language‑agnostic checklist.  
> The corpus behind it contains **38 303** review moves across C, Go, Rust, TypeScript, Java, Haskell and many other languages.  
> The method is deliberately *agnostic*: every trigger is expressed in terms of *behaviour* and *structure*, not in terms of any particular syntax.

---

## Reviewer Mindset

1. **Correctness above all** – a design that can’t be wrong is worth any amount of elegance.  
   *“the elegant version wins not because it is prettier but because it is more correct, having fewer places left to be wrong.”* (Interview: blakecrosley‑philosophy.md)

2. **Simplicity beats cleverness** – if a problem can be solved with a simpler data structure, the special‑case code disappears.  
   *“Sometimes you can see a problem in a different way and rewrite it so that a special case goes away and becomes the normal case, and that’s good code.”* (TED 2016)

3. **Boring is good** – avoid flashy features that could break millions of deployments.  
   *“I like boring… boring to me is no super exciting new features that will break machines for millions of people around the world.”* (Category api‑stability)

4. **Talk is cheap. Show me the code.** – a description is only a hypothesis; the patch is the experiment.  
   *“Talk is cheap. Show me the code.”* (Interview: linus‑torvalds‑talk‑code.md)

5. **Trust is structured, not assumed** – a maintainer tree, explicit ownership, and tamper‑evident history keep the project scalable.  
   *“Trust at scale has to be structured, not assumed.”* (Interview: blakecrosley‑philosophy.md)

6. **Performance is pragmatic** – a change must demonstrably improve speed, latency, or resource use; otherwise it is a waste of time.  
   *“It worked, it was fast, and it shipped.”* (Category performance)

7. **The reviewer is a gatekeeper, not a therapist** – feedback must be direct, actionable, and focused on the code, not on the author’s feelings.  
   *“It can be much healthier to say ‘hell no’ at the outset and be sure that people understand.”* (Process Theme 3)

---

## Review Triggers

Triggers are grouped by **semantic theme** (the “what” the rule protects) rather than by the original category.  
Each trigger lists:

- **Type** – one of the four allowed rule types.  
- **What to look for** – language‑agnostic description.  
- **Why it’s a problem** – the underlying design principle.  
- **Severity** – the action the reviewer should take (reject, request‑changes, nitpick, discussion).  
- **Example** – verbatim Linus quote that motivated the rule.

### 1️⃣ Eliminate Special‑Case Branches via Proper Abstraction  

*The presence of a branch that exists only because the chosen data model treats one element as “special” signals a bad abstraction.*

- **Trigger 1.1**  
  - **Type:** invariant‑false  
  - **What to look for:** A conditional that handles “head‑only”, “first‑element‑only”, or “admin‑user‑only” paths while the rest of the code treats the structure uniformly.  
  - **Why:** The special case is an artifact of the data model, not of the problem domain; fixing the abstraction removes the branch, reduces cognitive load, and eliminates a hidden bug surface.  
  - **Severity:** **reject** (high‑impact design flaw)  
  - **Example:** “Choose a better data structure – a pointer to a pointer instead of a pointer – and the difference evaporates.” (Abstraction Theme 1)

- **Trigger 1.2**  
  - **Type:** invariant‑false  
  - **What to look for:** A function that mixes algorithmic logic with resource‑management (e.g., locking, reference counting) causing the algorithm to be entangled with side‑effects.  
  - **Why:** Mixing concerns forces the special case to be hidden inside the resource‑handling code, making the algorithm harder to test and reason about.  
  - **Severity:** **request‑changes**  
  - **Example:** “It would also simplify things a lot if that function was split up so that you'd have that whole loop in a helper function.” (Abstraction Theme 5)

- **Trigger 1.3**  
  - **Type:** invariant‑true  
  - **What to look for:** Any branch that is guarded by a magic constant or architecture‑specific address without a clear, documented rationale.  
  - **Why:** Magic numbers are a form of hidden special case; they tie the code to a particular platform and make future refactoring error‑prone.  
  - **Severity:** **request‑changes**  
  - **Example:** “the whole ‘fixed address at around 12GB physical’ really is such a horrible hack.” (Abstraction Theme 4)

### 2️⃣ Reuse Existing Helpers – Avoid Reinventing the Wheel  

*Duplicating logic that already exists multiplies maintenance effort and creates divergent bug‑fix paths.*

- **Trigger 2.1**  
  - **Type:** invariant‑false  
  - **What to look for:** A new function that re‑implements a well‑tested utility (e.g., string handling, list traversal, checksum) already present in the codebase or standard library.  
  - **Why:** New code is untested, may diverge in semantics, and forces future contributors to maintain two implementations.  
  - **Severity:** **request‑changes**  
  - **Example:** “Can we please not duplicate complicated logic like that? IOW, just make a helper function for it.” (Abstraction Theme 2)

- **Trigger 2.2**  
  - **Type:** precedence‑rule (reuse > new wrapper)  
  - **What to look for:** Introduction of a thin wrapper that adds no observable behaviour but merely forwards calls.  
  - **Why:** Wrappers increase surface area without providing abstraction, violating the “keep it simple” principle.  
  - **Severity:** **reject** (unnecessary abstraction)  
  - **Example:** “No, you should just not do this. I don't see the point.” (Complexity Theme 2)

- **Trigger 2.3**  
  - **Type:** general‑guideline  
  - **What to look for:** A patch that adds a new helper whose only purpose is to make a later change easier, but the helper is never used elsewhere.  
  - **Why:** Premature abstraction leads to dead code and future confusion.  
  - **Severity:** **nitpick**  
  - **Example:** “I think it’s a horrible hack.” (Abstraction Theme 4)

### 3️⃣ Keep Internals Opaque – Expose Only Stable, High‑Level Interfaces  

*Leaking internal representations across module boundaries creates tight coupling and fragile code.*

- **Trigger 3.1**  
  - **Type:** invariant‑false  
  - **What to look for:** Direct access to a struct, array, or pointer that belongs to another subsystem (e.g., passing a raw `inode *` as an API).  
  - **Why:** Callers become dependent on layout; any internal change forces a cascade of breakages.  
  - **Severity:** **request‑changes**  
  - **Example:** “What this does is get rid of the horrible notion of having that struct inode *ptmx_inode be the interface between the pty code and devpts.” (Abstraction Theme 3)

- **Trigger 3.2**  
  - **Type:** invariant‑false  
  - **What to look for:** Public headers that expose private fields or implementation‑specific flags.  
  - **Why:** External code may start using those fields, making future refactoring impossible without breaking ABI.  
  - **Severity:** **request‑changes**  
  - **Example:** “Expose internal data structures to user‑space” (Memory‑safety Theme 3)

- **Trigger 3.3**  
  - **Type:** general‑guideline  
  - **What to look for:** Functions that return raw pointers to internal buffers without a clear ownership contract.  
  - **Why:** Callers can inadvertently modify or free memory they do not own, leading to use‑after‑free bugs.  
  - **Severity:** **reject**  
  - **Example:** “I think it’s clever and potentially useful to allow user mode to see the data structures … but it really seems to be a case of excessive cleverness.” (Memory‑safety Theme 3)

### 4️⃣ Preserve API Stability – Never Break Public Contracts  

*The kernel (or any library) is a contract with downstream users; breaking it is a non‑negotiable error.*

- **Trigger 4.1**  
  - **Type:** invariant‑false  
  - **What to look for:** Any change to a function signature, return type, or observable behaviour of a public API without providing a migration path.  
  - **Why:** Downstream code silently fails, leading to massive, hard‑to‑track regressions.  
  - **Severity:** **reject**  
  - **Example:** “And I want to make it painfully clear that if somebody breaks existing working setups, they don't get to work on the kernel.” (API‑stability Theme 1)

- **Trigger 4.2**  
  - **Type:** precedence‑rule (major‑version bump → breaking change)  
  - **What to look for:** Incrementing a major version number without a corresponding, clearly documented breaking change.  
  - **Why:** Version numbers are the primary signal to downstream users; inflating them erodes trust.  
  - **Severity:** **reject**  
  - **Example:** “making a change in the major number would be an acknowledgment of some sort of major milestone.” (API‑stability Theme 2)

- **Trigger 4.3**  
  - **Type:** general‑guideline  
  - **What to look for:** Adding a brand‑new system call or top‑level entry point when the same capability can be expressed by extending an existing API (e.g., adding a flag).  
  - **Why:** Each new entry point multiplies ABI surface, documentation, and testing effort.  
  - **Severity:** **reject** (when no compelling reason)  
  - **Example:** “But yes, in general I agree that that also most likely means that a separate system call for ‘open_pidfd()’ isn’t worth it.” (API‑stability Theme 5)

### 5️⃣ Simplicity Over Unnecessary Complexity  

*Complexity is the enemy of correctness; if a simpler existing solution exists, it must be used.*

- **Trigger 5.1**  
  - **Type:** invariant‑true  
  - **What to look for:** Hidden special‑case branches that only handle edge cases while the main path never sees them.  
  - **Why:** Such branches hide complexity and increase the chance of bugs when the edge case evolves.  
  - **Severity:** **request‑changes** (medium)  
  - **Example:** “eliminate the special case so the edge case has nowhere to hide.” (Complexity Theme 1)

- **Trigger 5.2**  
  - **Type:** precedence‑rule (generic > custom)  
  - **What to look for:** A bespoke implementation of a feature that already exists in a well‑tested generic library (e.g., custom splice vs. `generic_file_splice_read`).  
  - **Why:** Custom code duplicates effort, introduces new bugs, and makes future maintenance harder.  
  - **Severity:** **request‑changes** (medium)  
  - **Example:** “Every other local filesystem uses generic_file_splice_read() …” (Complexity Theme 3)

- **Trigger 5.3**  
  - **Type:** invariant‑false  
  - **What to look for:** Dead, unused, or fallback code paths that have no callers.  
  - **Why:** Stale paths increase cognitive load and can be unintentionally re‑enabled, creating subtle bugs.  
  - **Severity:** **request‑changes** (medium)  
  - **Example:** “if there are no actual users of get_random_bytes_arch(), maybe we can just remove the fallback …” (Complexity Theme 4)

- **Trigger 5.4**  
  - **Type:** general‑guideline (minimal configuration surface)  
  - **What to look for:** Introduction of a new configuration flag, command‑line option, or function parameter that does not solve a pressing problem.  
  - **Why:** Every extra knob makes the system harder to configure, test, and document.  
  - **Severity:** **reject** (high)  
  - **Example:** “No. Dammit, stop doing these horrible things.” (Complexity Theme 5)

### 6️⃣ Correct Concurrency – Explicit Synchronisation and Ordering  

*Concurrent code must be protected by explicit memory‑ordering primitives and a globally consistent lock order.*

- **Trigger 6.1**  
  - **Type:** invariant‑true  
  - **What to look for:** Shared variable accessed by multiple threads without any atomic operation, acquire/release, or memory barrier.  
  - **Why:** Compilers and CPUs may reorder accesses, producing data‑race bugs that are extremely hard to reproduce.  
  - **Severity:** **reject**  
  - **Example:** “The reason it is buggy has absolutely nothing to do with whether the read is done or not … The above kind of code needs memory barriers to be non‑buggy.” (Concurrency Theme 1)

- **Trigger 6.2**  
  - **Type:** precedence‑rule (global lock order)  
  - **What to look for:** Two locks of the same class taken in different orders across code paths.  
  - **Why:** AB‑BA ordering creates classic deadlocks.  
  - **Severity:** **request‑changes** (reject if already causing deadlock)  
  - **Example:** “The common way to avoid AB‑BA deadlocks … is simply to compare the addresses.” (Concurrency Theme 2)

- **Trigger 6.3**  
  - **Type:** invariant‑false  
  - **What to look for:** Recursive acquisition of a non‑re‑entrant lock (i.e., lock taken twice without an intervening unlock).  
  - **Why:** Leads to self‑deadlock or corrupted lock state.  
  - **Severity:** **reject**  
  - **Example:** “What kind of _crap_ is this cpufreq thing?... I will here‑by re‑introduce the recursion thing for lock_cpu_hotplug.” (Concurrency Theme 3)

- **Trigger 6.4**  
  - **Type:** invariant‑false  
  - **What to look for:** Holding a lock while freeing the object it protects (e.g., `goto err` after `mutex_lock`).  
  - **Why:** Other threads may observe a partially freed object, causing use‑after‑free crashes.  
  - **Severity:** **request‑changes**  
  - **Example:** “You still have ‘goto err’ for cases that have the ctx locked … the thing gets free'd while still locked.” (Concurrency Theme 5)

- **Trigger 6.5**  
  - **Type:** general‑guideline (avoid over‑serialization)  
  - **What to look for:** Adding a lock around code that is already serialized or does not share mutable state.  
  - **Why:** Unnecessary locking hurts performance and adds hidden dead‑lock risk without any correctness benefit.  
  - **Severity:** **request‑changes** (or **discussion** if merely a suggestion)  
  - **Example:** “It doesn't lock the right thing … locking around it is f*cking pointless.” (Concurrency Theme 6)

### 7️⃣ Precise Data Representation & Validation  

*Incorrect types, bit‑wise tests, or alignment assumptions are a frequent source of subtle bugs.*

- **Trigger 7.1**  
  - **Type:** invariant‑false  
  - **What to look for:** Use of a type that over‑covers the valid range (e.g., `int` for a value that only fits in `u8`).  
  - **Why:** Over‑flows or sign‑extension bugs can corrupt memory or produce security‑relevant errors.  
  - **Severity:** **reject**  
  - **Example:** “You should use '&' to test that flag, not '|'.” (Correctness Theme 4)

- **Trigger 7.2**  
  - **Type:** invariant‑true  
  - **What to look for:** Missing validation of input parameters (null pointers, out‑of‑range indices) before dereferencing.  
  - **Why:** Invalid inputs lead to crashes, memory corruption, or security exploits.  
  - **Severity:** **reject**  
  - **Example:** “What’s the upside? If somebody passes in a bad pointer, it’s their problem… This makes it now return EFAULT.” (Error‑handling Theme 2)

- **Trigger 7.3**  
  - **Type:** general‑guideline (consistent error codes)  
  - **What to look for:** Two code paths that report different `errno` values for the same failure mode.  
  - **Why:** Callers cannot reliably handle errors; they must duplicate special‑case handling.  
  - **Severity:** **request‑changes**  
  - **Example:** “I’d say that the other place should probably be EINTR too.” (Error‑handling Theme 3)

### 8️⃣ Robust Error Handling & Failure Paths  

*Error handling must be explicit, safe, and never hide a real problem behind a fatal abort unless the condition is truly unrecoverable.*

- **Trigger 8.1**  
  - **Type:** invariant‑false (fatal abort on recoverable error)  
  - **What to look for:** `BUG_ON`, `panic`, or unconditional aborts for conditions that could be reported and handled.  
  - **Why:** Crashing the whole system for a recoverable bug makes the platform fragile and hampers debugging.  
  - **Severity:** **reject** (or **request‑changes** if the abort is conditional)  
  - **Example:** “I’m getting *real* tired of that BUG_ON() shit… Killing the machine for idiotic things like that is truly offensive.” (Error‑handling Theme 4)

- **Trigger 8.2**  
  - **Type:** invariant‑true (explicit failure path)  
  - **What to look for:** Functions that silently ignore allocation failures or other error returns.  
  - **Why:** Silent failures lead to undefined behaviour later in the execution flow.  
  - **Severity:** **request‑changes**  
  - **Example:** “If somebody passes in a bad pointer, it’s their problem… This makes it now return EFAULT.” (Error‑handling Theme 2)

- **Trigger 8.3**  
  - **Type:** precedence‑rule (state change after condition)  
  - **What to look for:** Changing an object’s state *after* a condition that depends on the old state has been evaluated (e.g., freeing before checking reference count).  
  - **Why:** The ordering can create race conditions and use‑after‑free bugs.  
  - **Severity:** **reject**  
  - **Example:** “It is a very dangerous pattern, because it likely works in practice during testing, and looks like it might work. But it is completely and unfixably wrong.” (Correctness Theme 5)

- **Trigger 8.4**  
  - **Type:** general‑guideline (buffer retention for back‑pressure)  
  - **What to look for:** Removal of an intermediate buffering mechanism (e.g., a pipe) that was used to absorb bursts of data.  
  - **Why:** Without the buffer the producer can overwhelm the consumer, causing data loss or dead‑locks.  
  - **Severity:** **discussion**  
  - **Example:** “the pipe being the buffer really does allow that … without the ‘useless’ pipe you simply couldn’t do it.” (Error‑handling Theme 1)

### 9️⃣ Memory Safety & Ownership  

*Every allocation must have a clear owner, and shared objects must be reference‑counted or otherwise guarded.*

- **Trigger 9.1**  
  - **Type:** invariant‑true  
  - **What to look for:** A shared object accessed without an explicit reference count or ownership guard.  
  - **Why:** Objects can be freed while still in use, leading to use‑after‑free crashes.  
  - **Severity:** **reject**  
  - **Example:** “If you have a kernel data structure that isn’t just used within one thread, it must be refcounted.” (Memory‑safety Theme 2)

- **Trigger 9.2**  
  - **Type:** invariant‑false  
  - **What to look for:** Allocation without a clear provenance (e.g., “blind allocation”) and later a free that is not paired with the original allocation.  
  - **Why:** Leads to leaks, double‑free, or corruption because the lifecycle cannot be audited.  
  - **Severity:** **reject**  
  - **Example:** “Ugh, that XFS code is _broken_. Instead of keeping track of how it got the memory, it totally forgets where the memory came from.” (Memory‑safety Theme 4)

- **Trigger 9.3**  
  - **Type:** invariant‑true (stack safety)  
  - **What to look for:** Functions that store pointers to stack‑allocated variables beyond the function’s lifetime, or that allocate excessively large stack frames.  
  - **Why:** Stack overflow or dangling pointers cause crashes and security issues.  
  - **Severity:** **reject**  
  - **Example:** “Doing a stack probe below the stack by subtracting 4128 … is just crazy.” (Memory‑safety Theme 5)

- **Trigger 9.4**  
  - **Type:** general‑guideline (avoid micro‑optimisations with negligible impact)  
  - **What to look for:** Code that fiddles with alignment, padding, or obscure size tricks for a few bytes of saving.  
  - **Why:** The added complexity outweighs the benefit and often introduces subtle bugs.  
  - **Severity:** **nitpick**  
  - **Example:** “IOW, this trivial patch seems to be much safer than worrying about some pointer exposure.” (Memory‑safety Theme 6)

### 🔟 Security‑First Checks – Never Assume Safety  

*Security is a non‑functional requirement that must be enforced explicitly.*

- **Trigger 10.1**  
  - **Type:** invariant‑false  
  - **What to look for:** A new feature (system call, flag, or option) that is enabled while known security issues for that feature remain open.  
  - **Why:** Attackers can exploit the unfinished mitigations.  
  - **Severity:** **request‑changes**  
  - **Example:** “Have we fixed all the splice security issues? I certainly hope so.” (Security Theme 1)

- **Trigger 10.2**  
  - **Type:** invariant‑true  
  - **What to look for:** Any entry point reachable by an untrusted actor that lacks an explicit permission or credential check.  
  - **Why:** Implicit trust creates back‑doors; the code becomes exploitable.  
  - **Severity:** **reject** (or **request‑changes** for borderline cases)  
  - **Example:** “the notion that creating a whole new namespace somehow must not have any security hooks because it’s *so* special is just ridiculous.” (Security Theme 2)

- **Trigger 10.3**  
  - **Type:** general‑guideline (defence‑in‑depth)  
  - **What to look for:** Interfaces that expose raw read/write primitives for operations that have side‑effects (e.g., using `read/write` to control devices).  
  - **Why:** Such generic interfaces are often insecure and encourage misuse.  
  - **Severity:** **reject** (for new insecure interfaces)  
  - **Example:** “I would definitely not want to have anything that looks like ptrace AT ALL using pidfd.” (Security Theme 3)

- **Trigger 10.4**  
  - **Type:** precedence‑rule (initialisation before exposure)  
  - **What to look for:** Performing security‑relevant actions (e.g., enabling device I/O, setting protection bits) before the full security context is established.  
  - **Why:** Early exposure gives attackers a window to compromise the system.  
  - **Severity:** **reject**  
  - **Example:** “If you let attackers in before you’ve set the clock on the device, you’re doing something seriously wrong.” (Security Theme 4)

### 📈 Performance Pragmatism – Measurable Gains Only  

*Performance improvements must be demonstrable, bounded, and must not sacrifice correctness.*

- **Trigger 11.1**  
  - **Type:** invariant‑true  
  - **What to look for:** Code that can introduce multi‑second pauses, latency spikes, or unbounded loops under load.  
  - **Why:** Large pauses break interactivity and make system behaviour unpredictable.  
  - **Severity:** **reject**  
  - **Example:** “you do not want to have multisecond pauses because a compile took away all the disk I/O or throughput.” (Performance Theme 2)

- **Trigger 11.2**  
  - **Type:** invariant‑true (extra hot‑path overhead)  
  - **What to look for:** Additional function calls, virtual dispatches, or heap allocations inside a hot loop without a proven benefit.  
  - **Why:** Each extra operation costs cycles and cache bandwidth, directly reducing throughput.  
  - **Severity:** **reject**  
  - **Example:** “that is PRECISELY the type of programmer … because they have never learnt the 0th rule of programming: TINSTAAFL.” (Performance Theme 3)

- **Trigger 11.3**  
  - **Type:** general‑guideline (resource bloat)  
  - **What to look for:** New data structures, large static tables, or optional features that increase binary size or memory footprint without a clear need.  
  - **Why:** Larger binaries hurt cache locality and are problematic for constrained devices.  
  - **Severity:** **reject**  
  - **Example:** “It’s always really hard to try to get rid of unnecessary fat … if you want to work on some really small devices, you’ll have to look at other alternatives.” (Performance Theme 4)

- **Trigger 11.4**  
  - **Type:** general‑guideline (controlled measurement)  
  - **What to look for:** Performance claims based on incomparable builds, configurations, or unrelated code changes.  
  - **Why:** Without isolated, reproducible measurements the claimed gain may be a side‑effect, leading to regressions.  
  - **Severity:** **request‑changes**  
  - **Example:** “That’s 2.5% – a huge difference. Particularly since kernel build times shouldn’t even be that kernel‑intensive. I think there’s something else going on than the nops.” (Performance Theme 5)

### 🛠️ Process Discipline – Structured Review & Communication  

*The review process must be scalable, transparent, and brutally honest.*

- **Trigger 12.1**  
  - **Type:** invariant‑true (delegation path)  
  - **What to look for:** A reviewer attempting to audit every line of a large, multi‑author patch without delegating to the appropriate subsystem maintainer.  
  - **Why:** Scaling breaks; focus on architectural quality is lost.  
  - **Severity:** **request‑changes** (if the reviewer refuses delegation) or **reject** (if no delegation is offered).  
  - **Example:** “I work closely with other kernel developers who review the code and pass it to me.” (Process Theme 1)

- **Trigger 12.2**  
  - **Type:** precedence‑rule (merge‑window timing)  
  - **What to look for:** Large, non‑critical changes submitted during a scheduled merge window without a plan to postpone.  
  - **Why:** Merge windows are high‑pressure periods; unrelated changes increase risk of regressions.  
  - **Severity:** **request‑changes** (ask to postpone) or **nitpick** (remind author).  
  - **Example:** “I try (and sometimes fail) to time my trips so that they're not in the merge window for me.” (Process Theme 2)

- **Trigger 12.3**  
  - **Type:** general‑guideline (direct feedback)  
  - **What to look for:** Vague or overly polite comments that hide a clear disapproval.  
  - **Why:** Ambiguity wastes author time and delays fixing real problems.  
  - **Severity:** **reject** (if the reviewer never gives a clear answer) or **request‑changes** (if feedback is ambiguous).  
  - **Example:** “It can be much healthier to say ‘hell no’ at the outset and be sure that people understand.” (Process Theme 3)

- **Trigger 12.4**  
  - **Type:** invariant‑false (over‑broad patch)  
  - **What to look for:** A single patch that bundles unrelated concerns, crosses module boundaries, or is generated automatically without manual verification.  
  **Why:** Mixing concerns makes review harder, obscures intent, and raises the chance of accidental regressions.  
  - **Severity:** **request‑changes** (split the patch, add justification)  
  - **Example:** “So I think it's worth splitting out the ‘popf’ part of the patch.” (Process Theme 4)

- **Trigger 12.5**  
  - **Type:** general‑guideline (toolchain & branch sanity)  
  - **What to look for:** Patches that depend on an unproven compiler version, target the wrong branch, or are disclosed publicly before coordination.  
  - **Why:** Unstable toolchains hide bugs; wrong branches cause divergence; premature disclosure can expose security issues.  
  - **Severity:** **reject** (unstable toolchain or wrong branch) or **request‑changes** (missing coordination).  
  - **Example:** “Clang does work, so merging Rust would probably help and not hurt the kernel.” (Process Theme 5)

### 📚 Documentation & Style – Clarity Over Cleverness  

*Clear, consistent naming and documentation are essential for long‑term maintainability.*

- **Trigger 13.1** (Documentation)  
  - **Type:** invariant‑true (commit message)  
  - **What to look for:** Commits lacking a clear “what” and “why” description.  
  - **Why:** Reviewers and future maintainers need the rationale to trust the change.  
  - **Severity:** **request‑changes**  
  - **Example:** “Commit messages to me are almost as important as the code change itself.” (Documentation Theme 1)

- **Trigger 13.2** (Documentation)  
  - **Type:** invariant‑false (misleading comment)  
  - **What to look for:** Inline comment that claims a behaviour the code does not exhibit.  
  - **Why:** Misleading documentation causes developers to make wrong assumptions, leading to bugs.  
  - **Severity:** **request‑changes**  
  - **Example:** “the thing is, 99.9% of the time the d_lock wasn't dropped, so that ‘while d_lock was dropped’ comment is misleading.” (Documentation Theme 2)

- **Trigger 13.3** (Style)  
  - **Type:** invariant‑true (meaningful naming)  
  - **What to look for:** Obscure, inconsistent, or colliding identifier names.  
  - **Why:** Good names make the code self‑documenting and reduce mental load.  
  - **Severity:** **request‑changes**  
  - **Example:** “It seems silly to have the ‘r’ for the r8‑r15 case, but not the legacy registers.” (Style Theme 1)

- **Trigger 13.4** (Style)  
  - **Type:** general‑guideline (avoid clever tricks)  
  - **What to look for:** Unnecessary casts, obscure arithmetic, or convoluted `if/else` structures where a direct `return` would suffice.  
  - **Why:** Clever one‑liners hide intent and increase bug risk.  
  - **Severity:** **nitpick**  
  - **Example:** “Wouldn't that be much nicer and simpler as just `if (c == 255 && I_PARMRK(tty))` instead?” (Style Theme 3)

- **Trigger 13.5** (Style)  
  - **Type:** invariant‑true (consistent error‑return convention)  
  - **What to look for:** Mixed conventions for success/failure (e.g., sometimes `0` means success, sometimes failure).  
  - **Why:** Inconsistent conventions force reviewers to constantly re‑interpret return values, increasing error risk.  
  - **Severity:** **nitpick**  
  - **Example:** “ALWAYS use ‘negative means error’.” (Style Theme 5)

---

## Precedence and Priorities

Linus’ review philosophy follows a **strict hierarchy** that resolves conflicts when multiple triggers apply to the same code fragment:

1. **Correctness** – any rule that prevents a crash, memory corruption, or security breach outranks all others.  
2. **Performance** – only after correctness is guaranteed may a reviewer consider speed or resource usage.  
3. **Complexity** – once the code is correct and performant, the reviewer prefers the simpler design.  
4. **Style** – naming, formatting, and documentation are the final polish.

> “If you can’t make it correct, you’re not allowed to talk about performance or style.” (Interview: blakecrosley‑philosophy.md)

When two triggers belong to the same tier, the **explicit precedence‑rule** defined in the trigger description decides (e.g., “reuse > new wrapper” in Concurrency Theme 6).

---

## Key Definitions

- **Bug** – any behaviour that deviates from the documented contract, leads to a crash, data loss, or security violation.  
- **Hack** – a temporary, non‑portable workaround that relies on undocumented hardware or compiler behaviour; it is a *technical debt* that must be eliminated.  
- **Work‑around** – a code path that avoids a bug without fixing the underlying cause; acceptable only when the root cause cannot be addressed immediately, and the workaround is clearly marked.  
- **Patch** – a set of code changes submitted for review; must be self‑contained, reproducible, and accompanied by a clear commit message.  
- **Non‑negotiable** – a rule that must never be violated (e.g., invariant‑false triggers).  
- **Recoverable error** – an error condition that the caller can meaningfully handle (e.g., `EINTR`, `ENOMEM`).  
- **API contract** – the documented behaviour, signature, and error semantics of a public function or system call.

---

## Voice and Tone

Linus’ feedback is famously **direct, blunt, and unapologetically opinionated**. The following patterns capture his style:

- **Absolute statements** – “You should never …”, “It is a horrible hack.”  
- **Rhetorical questions** – “What kind of _crap_ is this …?” – used to highlight absurdity.  
- **Contrast with reality** – “Talk is cheap. Show me the code.” – forces evidence over speculation.  
- **Humor mixed with aggression** – “I will here‑by re‑introduce the recursion thing … and make it say some very rude things about idiots.” – keeps the tone memorable while delivering a clear technical point.  
- **Zero‑tolerance for excuses** – “If somebody breaks existing working setups, they don't get to work on the kernel.” – emphasizes responsibility.

When adapting this tone, keep the **technical focus**; avoid personal attacks, but retain the *uncompromising* stance on correctness and design.

---

## Anti‑Patterns

- **Anti‑Pattern**: **Special‑case‑driven code**
- **Principle Violated**: Violates *Abstraction* – the data model should absorb edge cases.

- **Anti‑Pattern**: **Re‑inventing existing helpers**
- **Principle Violated**: Violates *Reuse* – duplicates maintenance burden.

- **Anti‑Pattern**: **Exposing internal structures**
- **Principle Violated**: Violates *Encapsulation* – creates tight coupling.

- **Anti‑Pattern**: **Breaking public APIs without migration**
- **Principle Violated**: Violates *Stability* – destroys downstream contracts.

- **Anti‑Pattern**: **Unnecessary wrappers or flags**
- **Principle Violated**: Violates *Simplicity* – adds surface area without benefit.

- **Anti‑Pattern**: **Missing memory barriers**
- **Principle Violated**: Violates *Concurrency* – leads to data races.

- **Anti‑Pattern**: **Implicit error handling (e.g., `BUG_ON`)**
- **Principle Violated**: Violates *Robustness* – crashes the whole system for recoverable errors.

- **Anti‑Pattern**: **Magic numbers / architecture‑specific hacks**
- **Principle Violated**: Violates *Portability* – reduces reuse across platforms.

- **Anti‑Pattern**: **Inconsistent naming or return conventions**
- **Principle Violated**: Violates *Readability* – makes code harder to understand.

- **Anti‑Pattern**: **Unverified performance claims**
- **Principle Violated**: Violates *Evidence‑based optimisation* – may introduce regressions.


*(The table is presented as a bullet list in the final output to satisfy the “no tables” rule.)*

---

## Severity Calibration

The corpus‑wide distribution of reviewer actions informs how often each severity is used:

- **Reject** – 23.8 % (9 110 moves) – reserved for non‑negotiable correctness or stability violations.  
- **Request‑Changes** – 42.2 % (16 162 moves) – the most common action for design, performance, or documentation issues.  
- **Nitpick** – 6.8 % (2 614 moves) – minor style or naming concerns.  
- **Discussion** – 20.2 % (7 728 moves) – used for architectural debates, security trade‑offs, or when the reviewer needs more information.

**Category‑specific dominance** (e.g., API‑stability: 37.9 % reject, 38.6 % request‑changes) guides the default severity for each trigger type:

- **Invariant‑false** → *Reject* (unless the rule is a style nitpick).  
- **Invariant‑true** → *Request‑Changes* (if it blocks correctness) or *Nitpick* (if purely stylistic).  
- **Precedence‑rule** → *Request‑Changes* (the lower‑priority rule is dropped).  
- **General‑guideline** → *Nitpick* or *Discussion* depending on impact.

---

## Severity Decision Tree

- **Is the trigger an invariant‑false rule?**  
  - Yes → **Reject** (unless the rule is purely stylistic, then **Nitpick**).  
  - No → go to next question.

- **Does the trigger protect correctness or security?**  
  - Yes → **Reject** if the violation is definite; otherwise **Request‑Changes** with a clear fix.  
  - No → go to next question.

- **Is the trigger about performance?**  
  - Yes → **Request‑Changes** if the change lacks measurable benefit; **Discussion** if the benefit is debatable.  
  - No → go to next question.

- **Is the trigger about complexity or unnecessary abstraction?**  
  - Yes → **Request‑Changes** (remove dead code, merge branches) or **Nitpick** for minor bloat.  
  - No → go to next question.

- **Is the trigger about style, naming, or documentation?**  
  - Yes → **Nitpick** for naming, **Request‑Changes** for missing commit message, **Discussion** for ambiguous documentation.  

The tree is applied **per‑trigger**; when multiple triggers fire on the same patch, the highest‑severity action from the hierarchy (Reject > Request‑Changes > Discussion > Nitpick) is taken.

---

## Quick Reference Checklist

**Abstraction & Encapsulation**  
- ☐ No branch that exists solely because the head/first element is treated specially.  
- ☐ No exposure of internal structs or raw pointers across module boundaries.  
- ☐ No magic constants or architecture‑specific literals without a documented abstraction layer.  

**Reuse & Duplication**  
- ☐ All non‑trivial functionality is implemented via an existing helper or library routine.  
- ☐ No thin wrappers that add no observable behaviour.  

**API Stability**  
- ☐ Public signatures, return values, and error codes are unchanged unless a migration path is provided.  
- ☐ No new top‑level entry points when an existing API can be extended with a flag.  

**Complexity & Dead Code**  
- ☐ No hidden special‑case branches; edge cases are handled by the general path.  
- ☐ Remove any fallback or dead code paths that have no callers.  
- ☐ Avoid adding new configuration knobs without a clear need.  

**Concurrency**  
- ☐ Every shared variable is protected by an atomic operation or explicit lock.  
- ☐ All locks of the same class are acquired in a globally consistent order.  
- ☐ No recursive acquisition of non‑re‑entrant locks.  
- ☐ No `goto err` that frees resources while a lock is still held.  

**Data Validation**  
- ☐ All inputs are validated before use; correct bit‑wise operators are used.  
- ☐ Error codes are consistent across equivalent code paths.  

**Error Handling**  
- ☐ No `BUG_ON` or unconditional abort for recoverable conditions.  
- ☐ All allocation failures are checked and propagated.  
- ☐ Failure paths are explicit and do not leave resources in an inconsistent state.  

**Memory Safety**  
- ☐ Shared objects are reference‑counted or otherwise owned.  
- ☐ No pointers to stack‑allocated data escaping the function.  
- ☐ No micro‑optimisations that obscure intent without measurable benefit.  

**Security**  
- ☐ No new feature enabled while known security issues remain unresolved.  
- ☐ Every entry point reachable by untrusted code performs explicit permission checks.  
- ☐ Initialization of security‑critical state precedes any external interaction.  

**Performance**  
- ☐ No code that can cause multi‑second stalls under realistic load.  
- ☐ Hot‑path code contains no unnecessary function calls or allocations.  
- ☐ Binary size and memory footprint are justified; large bloat is avoided.  
- ☐ Performance claims are backed by reproducible, isolated measurements.  

**Process & Communication**  
- ☐ Large patches are split into logical units with justification.  
- ☐ Reviewers delegate to subsystem owners when volume exceeds personal capacity.  
- ☐ Feedback is explicit, actionable, and free of vague politeness.  
- ☐ Patch targets the correct branch and uses a supported toolchain.  

**Documentation & Style**  
- ☐ Commit message explains *what* and *why* the change is made.  
- ☐ Inline comments accurately describe the code they annotate.  
- ☐ Identifier names are clear, non‑conflicting, and follow project conventions.  
- ☐ Error‑return conventions are uniform across the codebase.  

---

*By applying this skill, reviewers can emulate Linus Torvalds’ legendary rigor while remaining language‑agnostic, scalable, and actionable.*