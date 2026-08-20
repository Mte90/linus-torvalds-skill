---
name: linus-torvalds-skill
description: "A language‑agnostic review methodology distilled from Linus Torvalds’ public feedback, covering design, correctness, performance, and process."
metadata:
  author: "torvalds-skill pipeline"
  version: "1.0.0"
  tags:
    - code-review
    - reviewer-method
    - torvalds
---

# Linus Torvalds Review Method

> This skill captures the essence of Linus Torvalds’ “talk is cheap, show me the code” philosophy as it appears across more than 38 000 review comments, interviews, and talks.  It is deliberately language‑agnostic – every trigger is expressed in terms of *behaviour* rather than *syntax* – so the same checklist can be applied to Python, Go, Rust, TypeScript, Java, Haskell, or any other language.  The method balances four immutable priorities – **Correctness > Performance > Complexity > Style** – and is backed by a statistical calibration of real‑world review outcomes.

---

## Reviewer Mindset

1. **Data‑first thinking** – “Bad programmers worry about the code. **Good programmers worry about data structures and their relationships**.” (Interview: blakecrosley‑philosophy.md)  
   *Treat the problem as a model first; the code should be a thin expression of that model.*

2. **Empirical pragmatism** – “I will do something that works for me, I won’t care about anyone else.” (Interview: git‑20‑qa.md)  
   *If a solution is fast, reliable, and ships, elegance is secondary.*

3. **Zero‑tolerance for hidden bugs** – “The elegant version wins not because it is prettier but because it is **more correct, having fewer places left to be wrong**.” (Interview: blakecrosley‑philosophy.md)  
   *Every extra branch, indirection, or special case is a new failure surface.*

4. **Blunt honesty** – “I’m not a nice person, I **care about the technology and the kernel** – that’s what’s important to me.” (Interview: ars‑2015‑not‑nice.md)  
   *State the problem directly; vague politeness only wastes reviewer time.*

5. **Trust through structure** – “The maintainer tree is a social architecture that structures **who** is accountable.” (Interview: blakecrosley‑philosophy.md)  
   *Never assume trust; verify through concrete tests, signatures, and reproducible builds.*

---

## Review Triggers

Triggers are grouped by **semantic theme** rather than the original category labels.  Each entry lists:

- **Type** – one of the four allowed rule types.  
- **What to look for** – language‑agnostic description.  
- **Why it’s a problem** – underlying design principle.  
- **Severity** – the action the reviewer must take.  
- **Example** – verbatim Linus quote that motivated the rule.

### Theme 1 – Data‑Structure & Abstraction Choice  
*(eliminate special‑case code, keep algorithmic logic pure)*  

- **Trigger 1.1**  
  - **Type:** invariant‑true  
  - **What to look for:** a conditional that exists solely because a particular element (e.g., “head” of a list) is treated differently from the rest.  
  - **Why it’s a problem:** the special case is a symptom of a mismatched abstraction; a better data structure removes the branch and reduces bug surface.  
  - **Severity:** reject (high‑impact design flaw)  
  - **Example:** “Choose a better data structure – a pointer to a pointer instead of a pointer – and the difference evaporates.” (abstraction, Theme 1)

- **Trigger 1.2**  
  - **Type:** general‑guideline  
  - **What to look for:** mixing algorithmic steps with lock acquisition, reference‑count handling, or other side‑effects inside a single function.  
  - **Why it’s a problem:** conflating concerns makes the function harder to test, reuse, and reason about; pure algorithmic helpers enable multiple synchronization strategies.  
  - **Severity:** request‑changes  
  - **Example:** “It would also simplify things a lot if that function was split up so that you’d have that whole loop in a helper function… with the mutex_lock/unlock in the caller.” (abstraction, Theme 5)

- **Trigger 1.3**  
  - **Type:** invariant‑false  
  - **What to look for:** hard‑coded magic numbers, fixed physical addresses, or platform‑specific constants that are not documented or configurable.  
  - **Why it’s a problem:** such literals tie the code to a single environment, impede portability, and make future maintenance error‑prone.  
  - **Severity:** request‑changes  
  - **Example:** “the whole ‘fixed address at around 12GB physical’ really is such a horrible hack.” (abstraction, Theme 4)

- **Trigger 1.4**  
  - **Type:** general‑guideline  
  - **What to look for:** introduction of a new helper, type, or path that duplicates functionality already provided by a well‑tested component.  
  - **Why it’s a problem:** duplication inflates the code base, creates divergent bugs, and wastes reviewer effort.  
  - **Severity:** request‑changes  
  - **Example:** “we already have a ‘utimes_common()’ that takes a path, and it could have been made into ‘vfs_utimes()’, and then this whole vcollected confusion would go away.” (abstraction, Theme 2)

- **Trigger 1.5**  
  - **Type:** precedence‑rule (specific > generic)  
  - **What to look for:** a function call that passes a broad context object (e.g., a whole filesystem super‑structure) when a more precise entity (e.g., an inode) would suffice.  
  - **Why it’s a problem:** over‑general interfaces blur abstraction boundaries, make misuse easier, and hide invariants that belong to the precise object.  
  - **Severity:** request‑changes  
  - **Example:** “Again – using the inode instead of the superblock in this patch would have made the patch much more obvious… So I’d *much* rather see … inode->i_atime = … current_fs_time(inode);” (abstraction, Theme 3)

### Theme 2 – API Design & Stability  
*(preserve contracts, keep signatures clear, avoid unnecessary exposure)*  

- **Trigger 2.1**  
  - **Type:** invariant‑true  
  - **What to look for:** any change that alters the behaviour, output, or contract of a publicly documented API without a clear migration path.  
  - **Why it’s a problem:** downstream users rely on stable contracts; breaking them creates regressions and erodes trust.  
  - **Severity:** reject  
  - **Example:** “And I want to make it painfully clear that if somebody breaks existing working setups, they don't get to work on the kernel.” (api‑stability, Theme 1)

- **Trigger 2.2**  
  - **Type:** general‑guideline  
  - **What to look for:** function names, parameters, or return conventions that do not convey data flow direction or error handling (e.g., “copy_to_f()” that ambiguously swaps source/destination).  
  - **Why it’s a problem:** ambiguous signatures invite misuse and hide bugs; callers must guess the contract.  
  - **Severity:** request‑changes  
  - **Example:** “So ‘copy_to_f()’ makes sense … But not this ‘randomly copy some randomly f memory area that I don't know if it's the source or the destination’.” (api‑stability, Theme 3)

- **Trigger 2.3**  
  - **Type:** precedence‑rule (extend > add new)  
  - **What to look for:** introduction of a brand‑new system call, flag, or public entry point when the same functionality can be expressed by augmenting an existing interface.  
  - **Why it’s a problem:** new entry points increase surface area, raise incompatibility risk, and fragment the API.  
  - **Severity:** request‑changes  
  - **Example:** “So it's much simpler and more straightforward to just introduce a single new bit #2 that says ‘I actually know what I'm doing…’” (api‑stability, Theme 4)

- **Trigger 2.4**  
  - **Type:** invariant‑true  
  - **What to look for:** exposing private data structures, internal headers, or symbols to user‑space or unrelated modules.  
  - **Why it’s a problem:** leaking internals couples external code to implementation details, making future refactors risky.  
  - **Severity:** request‑changes  
  - **Example:** “your <linux/cred.h> file exposes ‘struct ucred’ to user space … Why?” (api‑stability, Theme 5)

- **Trigger 2.5**  
  - **Type:** precedence‑rule (major version bump only for true breaks)  
  - **What to look for:** a proposal to increment the major version number for a change that does **not** introduce a breaking API/ABI modification.  
  - **Why it’s a problem:** inflating major version dilutes its meaning and forces downstream projects to adapt unnecessarily.  
  - **Severity:** reject  
  - **Example:** “making a change in the major number would be an acknowledgment of some sort of major milestone.” (api‑stability, Theme 2)

### Theme 3 – Complexity Reduction  
*(remove dead code, avoid unnecessary configuration, keep surfaces minimal)*  

- **Trigger 3.1**  
  - **Type:** invariant‑true  
  - **What to look for:** any branch that treats an edge case separately from the normal flow (e.g., “if (head)” in a linked‑list delete).  
  - **Why it’s a problem:** special‑case branches hide the real logic, increase cognitive load, and enlarge the bug surface.  
  - **Severity:** request‑changes (often rejected if the special case adds no functional benefit)  
  - **Example:** “*eliminate the special case so the edge case has nowhere to hide*.” (complexity, Theme 1)

- **Trigger 3.2**  
  - **Type:** general‑guideline  
  - **What to look for:** addition of a wrapper, type alias, or helper that provides no measurable benefit (performance, safety, readability).  
  - **Why it’s a problem:** extra layers multiply places a reviewer must understand and test; they are pure noise.  
  - **Severity:** reject  
  - **Example:** “*No, you should just not do this. I don't see the point.*” (complexity, Theme 2)

- **Trigger 3.3**  
  - **Type:** precedence‑rule (prefer existing simple mechanism)  
  - **What to look for:** bespoke implementation for a task already covered by a well‑tested, simple shared solution.  
  - **Why it’s a problem:** reinventing the wheel adds code that must be maintained without any advantage.  
  - **Severity:** request‑changes (or reject if substantially more complex)  
  - **Example:** “*Every other local filesystem uses generic_file_splice_read() with just a single .splice_read = generic_file_splice_read…*” (complexity, Theme 3)

- **Trigger 3.4**  
  - **Type:** invariant‑false  
  - **What to look for:** fallback branches, `#ifdef` sections, or runtime checks that are never exercised in practice.  
  - **Why it’s a problem:** dead paths obscure true logic and can become latent bugs when assumptions change.  
  - **Severity:** request‑changes  
  - **Example:** “*But if there are no actual users of get_random_bytes_arch(), maybe we can just remove the fallback…*” (complexity, Theme 4)

- **Trigger 3.5**  
  - **Type:** general‑guideline  
  - **What to look for:** introduction of a new configuration flag, command‑line option, or function parameter without a compelling, user‑visible need.  
  - **Why it’s a problem:** each extra knob makes the system harder to understand, test, and configure correctly.  
  - **Severity:** reject (or request‑changes if borderline)  
  - **Example:** “*No. Dammit, stop doing these horrible things.*” (complexity, Theme 5)

### Theme 4 – Concurrency & Memory‑Ordering Safety  
*(explicit ordering, lock discipline, avoid unsafe primitives)*  

- **Trigger 4.1**  
  - **Type:** invariant‑false  
  - **What to look for:** reads or writes of shared data without any explicit synchronization primitive, assuming program order will be preserved.  
  - **Why it’s a problem:** modern CPUs may reorder accesses, producing stale or inconsistent views; explicit barriers are required.  
  - **Severity:** reject  
  - **Example:** “The reason it is buggy has absolutely nothing to do with whether the read is done or not… The above kind of code needs memory barriers to be non‑buggy.” (concurrency, Theme 1)

- **Trigger 4.2**  
  - **Type:** precedence‑rule (global lock order)  
  - **What to look for:** two or more locks acquired in different orders across code paths, or mixing lock types without a documented ordering rule.  
  - **Why it’s a problem:** AB‑BA lock ordering creates classic deadlocks; a global order eliminates circular wait.  
  - **Severity:** reject  
  - **Example:** “The common way to avoid AB‑BA deadlocks … is to just take two locks in a specific order.” (concurrency, Theme 2)

- **Trigger 4.3**  
  - **Type:** invariant‑true  
  - **What to look for:** a code path that acquires a lock already held by the same execution context (directly or via a called function) when the lock is not re‑entrant.  
  - **Why it’s a problem:** recursive acquisition of a non‑re‑entrant lock deadlocks the thread.  
  - **Severity:** reject  
  - **Example:** “What kind of _crap_ is this cpufreq thing?... I will here‑by re‑introduce the recursion thing for lock_cpu_hotplug…” (concurrency, Theme 3)

- **Trigger 4.4**  
  - **Type:** general‑guideline  
  - **What to look for:** substitution of a well‑tested synchronization primitive (lock primitive, semaphore, atomic) with home‑grown logic that lacks the full API and testing.  
  - **Why it’s a problem:** custom sync is easy to get wrong (missing edge cases, race conditions).  
  - **Severity:** request‑changes  
  - **Example:** “but we don't have that ‘write_islocked()’ function. So the above would need more work, and is entirely untested anyway.” (concurrency, Theme 4)

- **Trigger 4.5**  
  - **Type:** invariant‑true  
  - **What to look for:** holding a lock while invoking a function that may block, schedule work, or call back into the same lock.  
  - **Why it’s a problem:** such patterns inevitably lead to deadlocks or severe latency spikes.  
  - **Severity:** request‑changes  
  - **Example:** “Now that's fine - as long as we never take that lock inside any delayed work … because then the delayed work itself may need the lock we hold … and now the ‘cancel_delayed_work_sync()’ thing might deadlock.” (concurrency, Theme 5)

### Theme 5 – Performance Pragmatism  
*(speed over elegance, avoid latency spikes, keep hot paths lean)*  

- **Trigger 5.1**  
  - **Type:** general‑guideline  
  - **What to look for:** a change that is “theoretically nicer” but offers no measurable performance benefit and introduces extra abstraction.  
  - **Why it’s a problem:** real‑world speed matters more than abstract perfection; shipping a fast, reliable solution beats chasing elegance that adds risk.  
  - **Severity:** reject  
  - **Example:** “it worked, it was fast, and it shipped.” (performance, Theme 1)

- **Trigger 5.2**  
  - **Type:** invariant‑false  
  - **What to look for:** any code path that can cause multi‑second stalls, unpredictable latency, or blocks critical throughput under load.  
  - **Why it’s a problem:** large pauses break responsiveness and can cascade into system‑wide slow‑downs.  
  - **Severity:** reject  
  - **Example:** “you do not want to have multisecond pauses because a compile took away all the disk I/O or throughput.” (performance, Theme 2)

- **Trigger 5.3**  
  - **Type:** invariant‑true  
  - **What to look for:** an expensive abstraction (virtual dispatch, extra function call, heavyweight instruction) placed inside a tight loop or other hot path without proven benefit.  
  - **Why it’s a problem:** each extra indirection multiplies cost per iteration, dramatically hurting scalability.  
  - **Severity:** reject  
  - **Example:** “that is PRECISELY the type of programmer Linus says is a crap programmer because they have never learnt the 0th rule of programming: TINSTAAFL.” (performance, Theme 3)

- **Trigger 5.4**  
  - **Type:** general‑guideline  
  - **What to look for:** a performance claim based on a single benchmark that mixes multiple variables (different builds, configs, unrelated changes).  
  - **Why it’s a problem:** without a controlled experiment the reported gain may be a side‑effect of unrelated changes, leading to misguided optimisations.  
  - **Severity:** request‑changes  
  - **Example:** “That's 2.5% - a huge difference… I think there's something else going on than the nops. Same config? …” (performance, Theme 4)

- **Trigger 5.5**  
  - **Type:** general‑guideline  
  - **What to look for:** code that adds extra memory, size, or duplicate work that grows with data volume without providing functional value.  
  - **Why it’s a problem:** bloat inflates cache pressure, memory footprint, and execution time; it also signals deeper design flaws.  
  - **Severity:** reject  
  - **Example:** “It’s always really hard to try to get rid of unnecessary fat… if you want to work on really small devices, you’ll have to look at other alternatives.” (performance, Theme 5)

### Theme 6 – Documentation & Communication  
*(commit messages, comments, specs, diagnostics)*  

- **Trigger 6.1**  
  - **Type:** invariant‑true  
  - **What to look for:** a change submitted without a clear commit message that explains **what** the change does **and** **why** it was needed.  
  - **Why it’s a problem:** the commit message is the primary, version‑controlled record of intent; without it reviewers cannot assess rationale and future maintainers lose context.  
  - **Severity:** reject  
  - **Example:** “Commit messages to me are almost as important as the code change itself… if you can explain your code to me, I will trust the code.” (documentation, Theme 1)

- **Trigger 6.2**  
  - **Type:** invariant‑true  
  - **What to look for:** a comment that states a condition, invariant, or side‑effect that does **not** match the implementation.  
  - **Why it’s a problem:** misleading comments cause developers to make incorrect assumptions, leading to bugs and wasted debugging time.  
  - **Severity:** request‑changes  
  - **Example:** “the thing is, 99.9% of the time the d_lock wasn't dropped, so that ‘while d_lock was dropped’ comment is misleading.” (documentation, Theme 2)

- **Trigger 6.3**  
  - **Type:** invariant‑true  
  - **What to look for:** specifications that tie behaviour to a particular compiler, runtime, or external implementation rather than stating required semantics directly.  
  - **Why it’s a problem:** implementation‑specific specs hide the true contract, making the code fragile to changes in that implementation and preventing other platforms from adopting it.  
  - **Severity:** request‑changes  
  - **Example:** “That is ‘not good’.” (documentation, Theme 3) *(the quote illustrates a vague, implementation‑centric comment)*

- **Trigger 6.4**  
  - **Type:** general‑guideline  
  - **What to look for:** ancillary documentation (summary lines, `Link:` fields, config‑option help) that omits important information or merely repeats the question.  
  - **Why it’s a problem:** incomplete docs force downstream users to hunt for missing details, increasing risk of misunderstand‑ings.  
  - **Severity:** request‑changes  
  - **Example:** “the ‘Link:’ line should be about background … it should not be seen as a replacement for any information in the commit itself.” (documentation, Theme 4)

- **Trigger 6.5**  
  - **Type:** invariant‑true  
  - **What to look for:** error, log, or diagnostic messages that omit critical context (caller identity, resource name) or describe a condition that does not match reality.  
  - **Why it’s a problem:** inaccurate diagnostics make debugging harder and can mask the real cause of a failure.  
  - **Severity:** request‑changes  
  - **Example:** “We should have made the root'ness explicit in the printk, though, to see that part too.” (documentation, Theme 5)

### Theme 7 – Error‑Handling Discipline  
*(buffering, validation, consistent error codes, avoid fatal aborts)*  

- **Trigger 7.1**  
  - **Type:** general‑guideline  
  - **What to look for:** removal of a buffering or staging construct that is only used to hold data while an error condition is detected or a fallback path is prepared.  
  - **Why it’s a problem:** buffers act as deterministic recovery points; removing them can turn a recoverable situation into a hard failure.  
  - **Severity:** nitpick (discussion)  
  - **Example:** “the pipe being the buffer really does allow that, and also handles the case of *what happens when we received more data than we could write*.” (error‑handling, Theme 1)

- **Trigger 7.2**  
  - **Type:** invariant‑true  
  - **What to look for:** performing an operation without first checking that the target object is in a permissible state or that caller‑supplied data meets basic validity criteria.  
  - **Why it’s a problem:** operating on invalid objects leads to undefined behaviour, data corruption, or security issues.  
  - **Severity:** request‑changes  
  - **Example:** “EINVAL seems the simplest thing. Should check S_IMMUTABLE too for that matter.” (error‑handling, Theme 2)

- **Trigger 7.3**  
  - **Type:** general‑guideline  
  - **What to look for:** two or more functions that perform the same logical operation but return different error codes for the same failure, or a new error code introduced without callers handling it.  
  - **Why it’s a problem:** inconsistent error signalling forces callers to write special‑case logic, increasing coupling and error‑prone code.  
  - **Severity:** request‑changes  
  - **Example:** “So I'd say that the other place should probably be EINTR too. But it would obviously be a good idea to verify that no caller cares…” (error‑handling, Theme 3)

- **Trigger 7.4**  
  - **Type:** invariant‑false  
  - **What to look for:** use of fatal assertions (`BUG_ON`, panics) for conditions that could be caused by external input or transient state.  
  - **Why it’s a problem:** fatal aborts kill the whole system for recoverable errors; production code should prefer warnings or error returns.  
  - **Severity:** reject  
  - **Example:** “I'm getting *real* tired of that BUG_ON() shit… Killing the machine for idiotic things like that is truly offensive.” (error‑handling, Theme 4)

- **Trigger 7.5**  
  - **Type:** invariant‑false  
  - **What to look for:** a function returning an error that the caller cannot meaningfully handle (e.g., low‑level resource creation failure with no retry or reporting path).  
  - **Why it’s a problem:** exposing “unhandleable” errors leads to noisy, meaningless error‑handling code and obscures real failure paths.  
  - **Severity:** reject  
  - **Example:** “The whole ‘sysfs_create_file()’ thing is an example of that. If it fails, it fails. The caller can't do anything about it anyway.” (error‑handling, Theme 5)

- **Trigger 7.6**  
  - **Type:** precedence‑rule (simple failure > complex recovery)  
  - **What to look for:** error‑handling code that attempts intricate recovery (clearing signal masks, re‑entering fault‑prone sections) instead of taking a clearly defined safe path.  
  - **Why it’s a problem:** complex recovery often relies on partially corrupted state, increasing the chance of secondary crashes.  
  - **Severity:** request‑changes  
  - **Example:** “Quite frankly, for the recursive SIGSEGV problem, I'd much rather look at the signal mask. If SIGSEGV is blocked, we should probably just kill the program instead of clearing the blocking and trying to handle the SIGSEGV anyway.” (error‑handling, Theme 6)

### Theme 8 – Memory‑Safety & Resource Management  
*(reference counting, stack safety, tracked allocation)*  

- **Trigger 8.1**  
  - **Type:** invariant‑true  
  - **What to look for:** a resource being freed, accessed, or transferred without a reliable, atomic reference‑count check, or an object being used after its count reaches zero.  
  - **Why it’s a problem:** missing or broken reference counting leads to double‑free, use‑after‑free, or leaks, which cause crashes or corruption.  
  - **Severity:** reject  
  - **Example:** “You're right because it would be a double‑free – both parties would decide that they can free the damn thing…” (memory‑safety, Theme 2)

- **Trigger 8.2**  
  - **Type:** invariant‑false  
  - **What to look for:** a function that allocates a large stack frame, stores a pointer to a stack‑allocated object beyond the function’s lifetime, or performs accesses that can go below the current stack pointer.  
  - **Why it’s a problem:** oversized stack frames risk overflow; dangling pointers cause use‑after‑free bugs; out‑of‑bounds stack probes corrupt memory.  
  - **Severity:** reject  
  - **Example:** “That's unacceptably buggy crap. rpc_wait_for_completion_task() will happily exit on a deadly signal even if the rpc hasn't been completed, so now you'll have a stale pointer to a stack that has been freed.” (memory‑safety, Theme 4)

- **Trigger 8.3**  
  - **Type:** general‑guideline  
  - **What to look for:** exposing internal kernel (or system) data structures to user‑space or other untrusted components.  
  - **Why it’s a problem:** exposure invites accidental or malicious corruption, breaks encapsulation, and makes future changes risky.  
  - **Severity:** reject  
  - **Example:** “I think it's clever and potentially useful to allow user mode to see the data structures … but it really seems to be a case of excessive cleverness.” (memory‑safety, Theme 3)

- **Trigger 8.4**  
  - **Type:** general‑guideline  
  - **What to look for:** memory allocated without explicit provenance tracking, blind allocation functions used, or deallocation omitted or inconsistent.  
  - **Why it’s a problem:** unknown origins make reliable freeing impossible, leading to leaks or double‑free errors.  
  - **Severity:** request‑changes  
  - **Example:** “Ugh, that XFS code is _broken_. Instead of keeping track of how it got the memory, it totally forgets where the memory came from, and then it later asks ‘oh, btw, how the hell did I allocate this?’.” (memory‑safety, Theme 5)

- **Trigger 8.5**  
  - **Type:** general‑guideline  
  - **What to look for:** a safety mechanism (e.g., address‑space randomisation, stack‑canaries) introduced as a massive overhaul rather than incrementally.  
  - **Why it’s a problem:** large, disruptive safety changes are hard to audit and can introduce regressions; incremental steps let the codebase adapt safely.  
  - **Severity:** request‑changes  
  - **Example:** “there is memory‑safety infrastructure within the kernel project that is not part of the C language, but it has been built up incrementally over the years, which allowed it to avoid any major outcry.” (memory‑safety, Theme 1)

### Theme 9 – Security Hygiene  
*(complete fixes before exposure, uniform checks, safe defaults)*  

- **Trigger 9.1**  
  - **Type:** general‑guideline  
  - **What to look for:** a proposal to enable or expose a capability while known security issues for that capability remain unresolved.  
  - **Why it’s a problem:** exposing a partially hardened feature gives attackers a foothold; the code base must be free of known vulnerabilities before public exposure.  
  - **Severity:** request‑changes  
  - **Example:** “Have we fixed all the splice security issues? I certainly hope so.” (security, Theme 1)

- **Trigger 9.2**  
  - **Type:** general‑guideline  
  - **What to look for:** a claim that a particular code path can be exempted from authentication, capability, or permission checks because it is “special” or “rare”.  
  - **Why it’s a problem:** security guarantees must be uniform; any exemption creates a predictable blind spot attackers can target.  
  - **Severity:** request‑changes  
  - **Example:** “the notion that creating a whole new namespace somehow must not have any security hooks because it's *so* special is just ridiculous.” (security, Theme 2)

- **Trigger 9.3**  
  - **Type:** general‑guideline  
  - **What to look for:** introduction of a new API, system call, or IPC mechanism that mirrors an existing interface already known to have security weaknesses.  
  - **Why it’s a problem:** replicating a flawed design multiplies the attack surface and re‑opens old bugs that have already been mitigated elsewhere.  
  - **Severity:** reject  
  - **Example:** “I would definitely not want to have anything that looks like ptrace AT ALL using pidfd.” (security, Theme 3)

- **Trigger 9.4**  
  - **Type:** precedence‑rule (safe default > permissive default)  
  - **What to look for:** an API or flag whose default state enables a powerful or risky operation unless the caller explicitly opts‑out.  
  - **Why it’s a problem:** most callers accept defaults; a permissive default leads to unintended privilege escalation or data exposure.  
  - **Severity:** request‑changes  
  - **Example:** “should we not make the *default* value be ‘don’t open anything odd at all’?” (security, Theme 4)

- **Trigger 9.5**  
  - **Type:** invariant‑true  
  - **What to look for:** using generic `read/write`‑style I/O interfaces for privileged or security‑critical actions (e.g., passing static module data as raw I/O).  
  - **Why it’s a problem:** generic I/O contracts assume simple data transfer; abusing them bypasses explicit permission checks and can leak internal memory.  
  - **Severity:** reject (for clear abuse) / nitpick (for poorly designed but not fatal)  
  - **Example:** “So who the f*ck sends static module data as IO? Just stop doing that.” (security, Theme 5)

- **Trigger 9.6**  
  - **Type:** precedence‑rule (initialisation > exposure)  
  - **What to look for:** code that makes a subsystem usable (enables system calls, sets control bits, starts accepting network packets) before all relevant security state (entropy sources, clock sync, per‑CPU data) is fully initialised.  
  - **Why it’s a problem:** attackers can exploit the window of uninitialised security state to gain footholds or read uninitialised memory.  
  - **Severity:** reject  
  - **Example:** “If you let attackers in before you've set the clock on the device, you're doing something seriously wrong.” (security, Theme 6)

### Theme 10 – Naming, Style & Consistency  
*(descriptive identifiers, avoid clever hacks, uniform conventions)*  

- **Trigger 10.1**  
  - **Type:** general‑guideline  
  - **What to look for:** identifiers (functions, variables, types, config options) that are obscure, inconsistent, or colliding, and that do not convey purpose.  
  - **Why it’s a problem:** clear names reduce mental load, prevent accidental clashes, and make the codebase searchable.  
  - **Severity:** request‑changes (often nit‑pick, reject if collides with public symbol)  
  - **Example:** “I do know that `kfs` is too much of a random collection of consonants… `kernelfs` is more acceptable, but it’s not perfect either.” (style, Theme 1)

- **Trigger 10.2**  
  - **Type:** precedence‑rule (simple > clever)  
  - **What to look for:** manual layout hacks, obscure arithmetic tricks, dead‑code constructs, or any “clever” technique that does not provide a measurable benefit.  
  - **Why it’s a problem:** such tricks make the code harder to read, maintain, and reason about; compilers already perform many optimisations.  
  - **Severity:** request‑changes (reject if outright harmful, nit‑pick for minor ugliness)  
  - **Example:** “That really is pretty ugly.” (style, Theme 2)

- **Trigger 10.3**  
  - **Type:** general‑guideline  
  - **What to look for:** commit messages, comments, or documentation that use unexplained acronyms, vague modal verbs (“could”), or ambiguous language.  
  - **Why it’s a problem:** unclear language forces reviewers to guess intent, slowing review and risking mis‑interpretation.  
  - **Severity:** nitpick  
  - **Example:** “Replace `could` by `should`.” (style, Theme 3)

- **Trigger 10.4**  
  - **Type:** invariant‑true  
  - **What to look for:** mixing different success/failure signalling conventions within the same codebase (e.g., zero sometimes means success, sometimes failure).  
  - **Why it’s a problem:** inconsistent conventions force readers to remember special cases, increasing the chance of mis‑interpreting a return value.  
  - **Severity:** nitpick  
  - **Example:** “ALWAYS use `negative means error`.” (style, Theme 4)

- **Trigger 10.5**  
  - **Type:** invariant‑false  
  - **What to look for:** custom format specifiers, non‑standard macros, or extensions that deviate from established language or library conventions without a compelling reason.  
  - **Why it’s a problem:** custom extensions increase learning curve, break tooling, and create hidden incompatibilities when the code is reused elsewhere.  
  - **Severity:** reject  
  - **Example:** “But once you drop the ‘standard patterns’ requirement, I do think you should drop it entirely, and not just extend it with some pissant single‑character unreadable mess.” (style, Theme 5)

### Theme 11 – Process & Review Discipline  
*(trust, communication, timing, granularity, toolchain stability)*  

- **Trigger 11.1**  
  - **Type:** invariant‑true  
  - **What to look for:** acceptance of a change only when no strong objections are raised by trusted maintainers.  
  - **Why it’s a problem:** accepting large or risky changes without explicit consensus undermines reliability; trust must be demonstrated, not assumed.  
  - **Severity:** reject (must be held until objections are resolved)  
  - **Example:** “I plan to accept the Rust patches … unless I hear strong objections.” (process, Theme 1)

- **Trigger 11.2**  
  - **Type:** general‑guideline  
  - **What to look for:** feedback that is vague, indirect, or overly polite, rather than bluntly stating disapproval early.  
  - **Why it’s a problem:** subtle comments waste reviewer time and can let bad design slip through; clear “no” signals let the author re‑evaluate immediately.  
  - **Severity:** request‑changes  
  - **Example:** “it can be much healthier to say ‘hell no’ at the outset and be sure that people understand.” (process, Theme 2)

- **Trigger 11.3**  
  - **Type:** precedence‑rule (timing > merge‑window)  
  - **What to look for:** large, non‑critical, or experimental changes scheduled to land during a critical merge window.  
  - **Why it’s a problem:** introducing noisy changes under integration pressure increases regression risk and makes rapid triage impossible.  
  - **Severity:** request‑changes (postpone or adjust schedule)  
  - **Example:** “I try (and sometimes fail) to time my trips so that they're not in the merge window for me.” (process, Theme 3)

- **Trigger 11.4**  
  - **Type:** invariant‑true  
  - **What to look for:** a submitted patch that mixes unrelated concerns or is added solely because an automated tool flagged it, without a human sanity‑check.  
  - **Why it’s a problem:** bundling unrelated modifications hides defects, introduces accidental side‑effects, and bypasses critical human reasoning.  
  - **Severity:** reject (must be split and re‑verified)  
  - **Example:** “So I think it's worth splitting out the ‘popf’ part of the patch.” (process, Theme 4)

- **Trigger 11.5**  
  - **Type:** invariant‑false  
  - **What to look for:** a contribution submitted against the wrong release branch or that violates branch‑specific policy (e.g., stable‑branch backport rules).  
  - **Why it’s a problem:** applying a change to the wrong tree can break release stability, cause regressions, and waste reviewer effort.  
  - **Severity:** reject  
  - **Example:** “Hmm. What version is this patch against? It doesn't seem to match my 4.12 tree.” (process, Theme 5)

- **Trigger 11.6**  
  - **Type:** general‑guideline  
  - **What to look for:** a change that depends on a compiler, toolchain, or external component that is not yet proven stable.  
  - **Why it’s a problem:** unstable toolchains can generate incorrect binaries, hide bugs, or make future builds non‑reproducible, jeopardising project integrity.  
  - **Severity:** reject  
  - **Example:** “Clang does work, so merging Rust would probably help and not hurt the kernel.” (process, Theme 6)

### Theme 12 – Testing & Validation  
*(mandatory testing, reproducible bugs, configuration coverage, benchmarks, automation)*  

- **Trigger 12.1**  
  - **Type:** invariant‑false  
  - **What to look for:** a patch submitted with no evidence that it has been built, run, or exercised on any target platform.  
  - **Why it’s a problem:** accepting untested code defeats the primary purpose of review; runtime‑only bugs will reach users, increasing regression risk.  
  - **Severity:** reject (or at minimum request‑changes until a test run is shown)  
  - **Example:** “Sure. Send me a tested patch … but somebody definitely needs to test it.” (testing, Theme 1)

- **Trigger 12.2**  
  - **Type:** invariant‑false  
  - **What to look for:** a bug‑fix patch that lacks concrete, reproducible evidence (hardware details, workload, crash trace, minimal reproducer).  
  - **Why it’s a problem:** without a reliable trigger the reviewer cannot verify that the patch actually fixes the problem, leading to wasted effort or hidden regressions.  
  - **Severity:** request‑changes  
  - **Example:** “So tell us more about those actual problems, because your patch and explanation is clearly wrong. What hardware, what load, what ‘kernel BUG at filemap.c:202’?” (testing, Theme 2)

- **Trigger 12.3**  
  - **Type:** general‑guideline  
  - **What to look for:** validation performed only on a single configuration (one architecture, one compile‑time option, one runtime setting) while other supported configurations remain untested.  
  - **Why it’s a problem:** code that interacts with hardware, optional features, or platform‑specific paths can behave differently; missing a configuration can introduce silent regressions.  
  - **Severity:** request‑changes  
  - **Example:** “Now, that does actually worry me. It _should_ have worked with CONFIG_MSI disabled… it would be a good idea to test the current‑git tree … both with CONFIG_MSI and without.” (testing, Theme 3)

- **Trigger 12.4**  
  - **Type:** invariant‑false  
  - **What to look for:** a benchmark that measures only the best‑case scenario, ignoring edge cases that could expose flaws or bias the results.  
  - **Why it’s a problem:** biased measurements give a false sense of improvement and can hide regressions that appear under realistic or worst‑case workloads.  
  - **Severity:** request‑changes  
  - **Example:** “So I would suggest you highlight the bad case too: use invlpg to invalidate *one* TLB entry, and then walk four non‑adjacent entries. And compare *that* to the full TLB flush.” (testing, Theme 4)

- **Trigger 12.5**  
  - **Type:** general‑guideline  
  - **What to look for:** absence of references to dynamic analysis, static checking, or other automated testing tools that could catch subtle defects before manual review.  
  - **Why it’s a problem:** human reviewers inevitably miss edge‑case bugs; static analysers and sanitizers surface issues too subtle for manual inspection, raising overall quality.  
  - **Severity:** nitpick (if missing but other testing is solid) or request‑changes for safety‑critical changes.  
  - **Example:** “The bugs that get noticed are just more subtle because we have better testing infrastructure, we have better tools for both dynamic and static checking of the sources.” (testing, Theme 5)

---

## Precedence and Priorities

Linus’ review history consistently enforces the following **immutable hierarchy** (quoted directly where possible):

1. **Correctness > Performance** – “If it works, it’s fast, and it shipped.” (performance, Theme 1)  
   *A correct implementation that runs slower is always preferred over a fast but incorrect one.*

2. **Performance > Complexity** – “The elegant version wins not because it is prettier but because it is **more correct, having fewer places left to be wrong**.” (blakecrosley‑philosophy.md)  
   *A faster solution that adds unnecessary complexity is rejected; simplicity reduces bug surface.*

3. **Complexity > Style** – “Talk is cheap. Show me the code.” (Talk is cheap, 2000)  
   *If the code is functionally sound and performant, style issues become nit‑picks.*

When two rules conflict, the higher‑ranked principle wins.  For example, a micro‑optimisation that introduces a new special‑case branch (complexity) will be rejected even if it yields a 5 % speed gain, because **Correctness > Performance > Complexity**.

**Illustrative quote:**  
> “I will argue that centralized systems can't work, but it is clearly true that they are less effective than distributed systems.” (google‑techtalk‑2007) – demonstrates the precedence of architectural correctness over convenience.

---

## Key Definitions

- **Bug** – *A deviation from the documented or expected behaviour that can be reliably reproduced.* (Interview: blakecrosley‑philosophy.md)  
- **Hack** – *A quick, often brittle solution that works for a narrow case but lacks generality, documentation, or robustness.* (Interview: ars‑2015‑not‑nice.md)  
- **Work‑around** – *A temporary measure that avoids a bug without fixing its root cause, typically slated for later removal.* (Interview: blakecrosley‑philosophy.md)  
- **Patch** – *A self‑contained set of code changes that implements a single, coherent logical modification, accompanied by a commit message describing *what* and *why*.* (Interview: blakecrosley‑philosophy.md)  
- **Non‑negotiable** – *An invariant that must never be violated in the codebase (e.g., memory‑ordering guarantees, API contracts).* (Category: concurrency, invariant‑false)  
- **Recoverable error** – *An error condition that the caller can handle gracefully (e.g., returning a standard error code, retrying, or falling back).* (Error‑handling, Theme 2)  
- **API contract** – *The set of guarantees (inputs, outputs, side‑effects, error codes) that a function promises to uphold for all callers.* (API‑stability, Theme 1)

---

## Voice and Tone

Linus reviews are famously **blunt**, **direct**, and **unapologetically opinionated**.  The following patterns recur:

- **Pattern**: **Absolute rejection**
- **Typical Wording**: “*No.* … *reject*”
- **Example**: “No. Dammit, stop doing these horrible things.” (process, Theme 5)

- **Pattern**: **Sarcastic emphasis**
- **Typical Wording**: “*…* *really* *is* *such* *a* *horrible* *hack*.”
- **Example**: “the whole ‘fixed address at around 12GB physical’ really is such a horrible hack.” (abstraction, Theme 4)

- **Pattern**: **Contrast with reality**
- **Typical Wording**: “*If you can’t* *see* *the* *obvious* *problem* *…*”
- **Example**: “If you can’t see the obvious problem, you’re probably a moron.” (style, Theme 5)

- **Pattern**: **Personal stake**
- **Typical Wording**: “*I care about the technology*”
- **Example**: “I’m not a nice person, I don’t care about you. I care about the technology and the kernel—that’s what’s important to me.” (ars‑2015‑not‑nice.md)

- **Pattern**: **Encouragement of evidence**
- **Typical Wording**: “*Show me the code*”
- **Example**: “Talk is cheap. Show me the code.” (2000 LKML)


When writing feedback, mirror this style: be **concise**, **specific**, and **unambiguous**.  Avoid hedging language (“maybe”, “perhaps”) and state the required action directly (“Reject”, “Request changes”, “Nitpick”).

---

## Anti‑Patterns

- **Special‑case proliferation** – hiding a bad data model behind `if (head) …` branches. *(Violates Theme 1.1)*  
- **Reinventing the wheel** – adding a new helper that duplicates existing, battle‑tested logic. *(Violates Theme 2.2)*  
- **Implicit synchronization** – relying on compiler or hardware ordering without explicit barriers. *(Violates Theme 4.1)*  
- **Permissive defaults** – APIs that enable powerful behaviour unless the caller opts out. *(Violates Theme 9.4)*  
- **Fatal aborts for recoverable conditions** – `BUG_ON` on user‑controlled input. *(Violates Theme 7.4)*  
- **Undocumented magic numbers** – hard‑coded addresses, sizes, or platform‑specific constants. *(Violates Theme 1.3)*  
- **Mixed‑style error returns** – mixing negative, zero, and positive success codes. *(Violates Theme 10.4)*  
- **Patch granularity violation** – bundling unrelated changes into a single patch. *(Violates Theme 11.4)*  
- **Testing omission** – submitting code without any build or runtime verification. *(Violates Theme 12.1)*  

Each anti‑pattern directly maps to a trigger in the catalog; rejecting or requesting changes on the trigger eliminates the anti‑pattern.

---

## Severity Calibration

The corpus‑wide calibration provides a statistical grounding for the severity labels:

- **Reject** – 23.8 % of all moves (≈ 9 110 instances) – used for *design‑breaking* or *unsafe* issues.  
- **Request‑Changes** – 42.2 % (≈ 16 162) – the default for *sub‑optimal* but fixable problems.  
- **Nitpick** – 6.8 % (≈ 2 614) – style, wording, or minor cosmetic concerns.  
- **Discussion** – 20.2 % (≈ 7 728) – ambiguous cases that need community input.  

**Category‑specific dominant severities** (from the calibration table) guide the default label for each trigger:

- **API‑stability**, **Correctness**, **Complexity**, **Memory‑safety**, **Error‑handling**, **Concurrency**, **Process**, **Testing**, **Documentation** → *request‑changes* unless the trigger is a clear violation of a non‑negotiable invariant (then *reject*).  
- **Performance**, **Style** → *request‑changes* for substantive issues, *nitpick* for pure style.  

When a trigger falls into a category where *reject* is dominant (e.g., **Correctness**, **Memory‑safety**), reviewers should default to **reject** unless the change can be trivially corrected without breaking the invariant.

---

## Severity Decision Tree

A **category‑based decision procedure** (nested bullets) helps the reviewer pick the right severity:

- **Is the issue a non‑negotiable invariant?**  
  - *Yes* → **Reject** (breaks correctness, safety, or security).  
  - *No* → go to next step.

- **Does the change introduce a measurable performance regression or latency spike?**  
  - *Yes* → **Reject** (performance‑critical path).  
  - *No* → next step.

- **Is the problem a complexity increase (new special case, dead code, unnecessary wrapper)?**  
  - *Yes* → **Request‑Changes** (simplify or remove).  
  - *No* → next step.

- **Is the issue purely stylistic (naming, formatting, minor comment wording)?**  
  - *Yes* → **Nitpick** (or **Discussion** if controversial).  
  - *No* → next step.

- **Is the patch missing required testing or reproducible evidence?**  
  - *Yes* → **Reject** (no‑testing) or **Request‑Changes** (ask for tests).  
  - *No* → **Approve** (if all other checks pass).

---

## Quick Reference Checklist

*(15‑20 concrete items, grouped by theme; each item is a “yes/no” question the reviewer can answer quickly.)*

- **Abstraction & Data‑Structure**  
  - [ ] Does any `if`/`switch` exist solely because a particular element is treated differently?  
  - [ ] Are algorithmic loops mixed with lock acquisition or reference‑count handling?  
  - [ ] Are magic numbers or platform‑specific constants hard‑coded without a named constant?  
  - [ ] Does the patch introduce a new helper that duplicates existing functionality?  
  - [ ] Is the function signature more generic than necessary (e.g., passing a super‑structure instead of a specific node)?

- **API Design & Stability**  
  - [ ] Does the change modify a public API contract without a migration plan?  
  - [ ] Are parameter names and return conventions unambiguous about data flow?  
  - [ ] Could the new behaviour be expressed by extending an existing flag or call instead of adding a brand‑new entry point?  
  - [ ] Does the patch expose internal structs or headers to user‑space?  
  - [ ] Is a major version bump proposed for a non‑breaking change?

- **Complexity Reduction**  
  - [ ] Are there any dead `#ifdef` blocks or fallback paths that are never exercised?  
  - [ ] Does the patch add a configuration knob without a clear user‑visible benefit?  
  - [ ] Are there any newly introduced wrappers that provide no measurable advantage?  

- **Concurrency & Memory‑Ordering**  
  - [ ] Are shared variables accessed without explicit barriers or atomic ops?  
  - [ ] Is there any lock acquisition order that differs from the global rule?  
  - [ ] Does any code acquire a non‑re‑entrant lock recursively?  
  - [ ] Is a custom synchronization primitive introduced?  
  - [ ] Is a lock held while calling a potentially blocking function?

- **Performance Pragmatism**  
  - [ ] Does the change add an abstraction inside a hot loop without proven benefit?  
  - [ ] Could the patch cause multi‑second pauses under load?  
  - [ ] Is the performance claim backed by a controlled benchmark (single variable changed, same config)?  
  - [ ] Does the patch increase binary size or memory usage without functional gain?

- **Documentation & Communication**  
  - [ ] Is there a clear commit message with *what* and *why*?  
  - [ ] Do comments accurately describe the implemented behaviour?  
  - [ ] Is the specification implementation‑agnostic?  
  - [ ] Are ancillary docs (Link, help text) complete and non‑redundant?  
  - [ ] Do diagnostic messages contain sufficient runtime context?

- **Error‑Handling Discipline**  
  - [ ] Is a buffer or staging area removed that was used for rollback or overflow detection?  
  - [ ] Are inputs validated before use, returning a proper error code?  
  - [ ] Are error codes consistent across similar functions?  
  - [ ] Are fatal `BUG_ON`‑style aborts used for recoverable conditions?  
  - [ ] Does the function return an error the caller cannot act upon?

- **Memory‑Safety & Resource Management**  
  - [ ] Is reference counting used correctly and atomically?  
  - [ ] Does any function allocate large stack frames or return pointers to stack memory?  
  - [ ] Are internal kernel structures kept hidden from untrusted code?  
  - [ ] Is every allocation tracked and freed appropriately?  
  - [ ] Are safety mechanisms introduced incrementally rather than as a massive overhaul?

- **Security Hygiene**  
  - [ ] Is the feature fully patched for known security issues before exposure?  
  - [ ] Are there any exemptions from authentication or capability checks?  
  - [ ] Does the patch add a new interface that duplicates a known insecure one?  
  - [ ] Are defaults safe (privilege‑escalating actions disabled by default)?  
  - [ ] Are privileged actions performed via generic I/O interfaces?

- **Naming, Style & Consistency**  
  - [ ] Are identifiers descriptive and free of obscure acronyms?  
  - [ ] Does the code avoid clever hacks that have no measurable benefit?  
  - [ ] Are commit messages free of vague modal verbs (“could”) and unexplained acronyms?  
  - [ ] Is there a single, project‑wide error‑return convention?  
  - [ ] Are there any non‑standard extensions to public interfaces?

- **Process & Review Discipline**  
  - [ ] Has the patch been reviewed by all trusted maintainers; are there no strong objections?  
  - [ ] Is feedback blunt and unambiguous (“hell no” style) rather than polite?  
  - [ ] Is the change scheduled outside a critical merge window?  
  - [ ] Does the patch contain only one logical change (no unrelated modifications)?  
  - [ ] Is the target branch correct for the intended release?

- **Testing & Validation**  
  - [ ] Does the patch include build logs or test runs on at least one target platform?  
  - [ ] Is there reproducible evidence for any bug being fixed?  
  - [ ] Have all supported configurations been exercised?  
  - [ ] Do benchmarks include worst‑case or adverse scenarios?  
  - [ ] Are static analysis or sanitiser results referenced?

If **any** answer is “No”, the reviewer should apply the corresponding trigger from the catalog, following the severity decision tree above.

--- 

*End of Linus Torvalds Review Method (≈ 6 800 words).*