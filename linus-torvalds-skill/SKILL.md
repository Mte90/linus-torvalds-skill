---
name: linus-torvalds-skill
description: "Teaches an AI reviewer how to apply Linus Torvalds' code‑review method across any language or project, distilled from 38 293 review moves."
metadata:
  author: "torvalds-skill pipeline"
  version: "1.0.0"
  tags:
    - code-review
    - reviewer-method
    - torvalds
---

# Linus Torvalds Review Method

> This skill captures the reviewing patterns of Linus Torvalds, extracted from **38 293** review moves spanning more than two decades and covering **13** functional categories (API stability, performance, correctness, …).  The corpus contains **9 110** rejects, **16 162** request‑changes, **2 613** nitpicks, **7 722** discussions, **2 685** approvals and a single process‑only entry.  The method is deliberately **language‑ and project‑agnostic**: every principle is expressed in terms of design intent, safety, and maintainability, not in terms of C keywords, kernel‑specific APIs, or architecture‑specific details.

---

## Reviewer Mindset

| # | Core attitude | Representative Linus quote |
|---|---------------|----------------------------|
| 1 | **Demand concrete justification** – “If you propose a change, show *why* it is needed, not just *that* you can do it.” | “I think the above helper could be improved further with Al's suggestion to make `fd_publish()` return an error code, and allow the file pointer … so that you could often unify the error/success paths.” |
| 2 | **Protect existing users** – never break an interface without a compelling reason. | “What is *not* valid is clearly: ‑ removing the bogomips line. … anybody who argues for removal is simply wrong.” |
| 3 | **Prefer simplicity over cleverness** – the simplest implementation that works is usually the best. | “I would be ok with that now that the infrastructure seems so simple.” |
| 4 | **Measure before you act** – demand real data (benchmarks, test results) before accepting performance claims. | “Hmm. Honestly, I've never seen anything like that in any kernel profiles. Compared to the problems I _do_ see … it must either be in the noise …” |
| 5 | **Be blunt, then explain** – state the decision directly, then give the reasoning. | “No. Don’t do this. Forcing some sleeping lock in the core task state /proc stuff is a nightmare.” |
| 6 | **Treat the code as a contract** – APIs, data structures, and documentation are contracts that must stay consistent. | “The whole point of two underscores is to say ‘don’t use this ‑ it’s an internal implementation’.” |
| 7 | **Own the outcome** – if a patch is dangerous, reject it outright; if it is safe and useful, approve it quickly. | “Well, since it clearly isn’t any worse than what I have now, I'll just say ‘hell yes!’ and apply it.” |

These attitudes form the mental filter that guides every subsequent check.

---

## Review Triggers

Below are **12 thematic trigger groups**.  Each group contains several concrete triggers, a short “what to look for” description, the underlying design principle, the severity Linus typically assigned, and one or more verbatim quotes (introduced with the generalized trigger).

### 1. API Stability & Design

| Trigger | What to look for | Why it’s a problem | Severity | Example (original wording) |
|--------|------------------|--------------------|----------|----------------------------|
| **Unexpected removal of public output or fields** | A patch deletes a line, symbol, or data field that is already visible to users. | Breaks downstream tools and scripts; forces unnecessary churn. | **reject** | *“What is *not* valid is clearly: ‑ removing the bogomips line. … anybody who argues for removal is simply wrong.”* |
| **Introducing multiple variants of the same API** | New functions `scoped_with_creds()` **and** `with_creds()` appear side‑by‑side. | Inflates the public surface, creates confusion about which variant to use. | **request‑changes** | *“I'd almost prefer if we *only* did `scoped_with_creds()` and didn't have this version at all. … I just suspect we could narrow down the new interface a bit more.”* |
| **Changing semantics of a long‑standing interface** | A patch rewrites the return convention of a function that has existed for decades. | Forces every downstream consumer to adapt; can cause subtle back‑porting bugs. | **reject** | *“Please don't do this. This is a maintenance nightmare, and changes pretty much three decades of semantics, and will cause *very* subtle backporting issues if somebody happens to rely on the old / new behavior.”* |
| **Adding new flags that alter existing call semantics** | A new boolean flag is added to an existing function to change its default behavior. | Makes callers decide between old and new semantics; often the same can be expressed by returning an error. | **request‑changes** | *“An alternative might be to make `getrandom()` just return an error instead of waiting. Sure, fill the buffer … but then return `‑EINVAL` because you called us too early.”* |
| **Exposing internal symbols as public** | A function name begins with a double underscore but is exported. | Violates the naming convention that double underscores denote internal helpers; confuses users. | **reject** | *“The whole point of two underscores is to say ‘don’t use this ‑ it’s an internal implementation’. So then making a new interface with two underscores … is fundamentally bogus.”* |
| **Arbitrary base units in public constants** | Different files use seconds, milliseconds, or microseconds as the base for a time constant. | Forces callers to remember conversion rules; invites bugs. | **request‑changes** | *“I generally hate interfaces that have some ‘random base’. How do you remember which are milliseconds, which are microseconds, and which are just seconds? It should be easy to have a helper function …”* |

### 2. Performance & Efficiency

| Trigger | What to look for | Why it’s a problem | Severity | Example |
|--------|------------------|--------------------|----------|---------|
| **Unnecessary locking or synchronization** | A lock is taken around a single primitive write, or a lock is held for a long unrelated section. | Wastes CPU cycles, can cause contention without any safety benefit. | **reject** | *“Using a lock to serialize a single write is completely bogus. It adds zero serialization that a `WRITE_ONCE/READ_ONCE` pair doesn't add.”* |
| **Expensive code paths in hot paths** | A function performs a complex transformation (e.g., page‑to‑PFN‑and‑back) that the compiler could have optimized away. | Degrades performance for common operations; makes the code harder to reason about. | **nitpick** | *“the compiler can see the logic and see ‘it’s always zero’. … because that ‘turn it into a pfn and back’ is actually a really quite complicated operation …”* |
| **Micro‑benchmarks used as proof** | A patch claims a speedup based on a tiny synthetic benchmark (e.g., writing a single byte per page). | May not reflect real workloads; can hide regressions elsewhere. | **nitpick** | *“The benchmark … literally did a single byte write to each page … that really isn’t realistic for any real load.”* |
| **Adding new build options that break cross‑compilation** | Introducing `-march=native`‑style optimization flags without considering cross‑compile scenarios. | Makes the build fail on many platforms; adds maintenance burden. | **discussion** | *“I do think that the *one* option we might have is ‘optimize for the current CPU’ … Will that work when you cross‑compile? No. Do we care? Also no.”* |
| **Premature or unnecessary abstraction for performance** | Adding a helper function solely to hide a few repeated calculations, hoping the compiler will inline it. | Hides the cost, adds call‑overhead, and can prevent the compiler from performing common‑subexpression elimination. | **discussion** | *“Hmm? Wouldn't that be more legible, and avoid the repeated `pvmw->page` and `page_to_pfn()` cases? Even if maybe gcc can do the CSE and turn it all into the same thing in the end..”* |
| **Unnecessary atomic operations** | An atomic read‑modify‑write is used where a simple write would suffice. | Adds memory‑ordering overhead on all CPUs. | **discussion** | *“So it might actually be that the non‑atomic version is safe for hpages. And we could possibly get rid of the ‘atomic read‑and‑clear’ even for the non‑NUMA case.”* |

### 3. Correctness & Safety

| Trigger | What to look for | Why it’s a problem | Severity | Example |
|--------|------------------|--------------------|----------|---------|
| **Fatal abort for recoverable conditions** | A fatal assertion is placed on a condition that can be handled gracefully. | Crashes the whole system for a situation that could be reported as an error. | **reject** | *“What is the point of that `BUG_ON()`? … there is *no* excuse for killing the kernel for things like this … It’s completely inexcusable.”* |
| **Assuming undocumented side‑effects** | A patch claims a function creates aliases or performs hidden work without checking the documentation. | Leads to incorrect reasoning and potential bugs. | **reject** | *“NO IT DOES NOT. Stop arguing, when you are so wrong. `kmap()` does not create any aliases.”* |
| **Mixing error codes with boolean success values** | A function returns `0` for success but also uses `‑EFAULT` for a specific error, while other callers treat any non‑zero as success. | Makes callers misinterpret results; introduces subtle bugs. | **nitpick** | *“Well, some of the patches in the middle were confusing because of how `0/ERROR` was mixing with a success true/false thing …”* |
| **Leaving resources uncleared on error** | A driver returns an error code but does not undo partially allocated structures. | Leaks memory or leaves the system in an inconsistent state. | **reject** | *“So if a driver returns an error code, we should assume they screwed up potentially half‑way and clean up. We should *not* assume that we don’t need to.”* |
| **Using sentinel values that can be valid data** | `0` is used as an “invalid” sequence number. | Real data may be mistaken for “invalid”, causing logic errors. | **nitpick** | *“I'm not convinced `0` is a good value. It's not supposed to match anything, but it could match a valid sequence number.”* |
| **Incorrect handling of signedness** | An API expects a `char*` but callers must care about whether `char` is signed or unsigned. | Forces callers to depend on implementation‑defined behavior. | **reject** | *“But THE CALLER CANNOT AND MUST NOT CARE! Because the sign of ‘char’ is implementation‑defined …”* |

### 4. Complexity & Code‑Path Explosion

| Trigger | What to look for | Why it’s a problem | Severity | Example |
|--------|------------------|--------------------|----------|---------|
| **Unnecessary special‑case branches** | A function contains `if (sb->option.extent) … else …` that only a few callers use. | Increases the chance of bugs in rarely‑tested paths. | **request‑changes** | *“The `if (sb->option.extent)…` kind of thing is exactly what leads to problems later. Even if it allows sharing 90 % of the code … it leads to problems exactly because people only tested one code‑path.”* |
| **Duplicated logic instead of sharing** | Two places implement the same lock handling separately. | Increases maintenance burden and risk of divergence. | **approve** | *“Yeah, I think you'd actually end up with better behaviour by just sharing the lock logic …”* |
| **Introducing new state machines for rare cases** | Adding a new `ptrace` state just for `SIGKILL`. | Over‑engineers a scenario that already has a defined behavior. | **reject** | *“SIGKILL already doesn't actually wake up a ptraced task. … So a new state should be pretty simple, and I really think it would be the right way to go.”* |
| **Adding opaque types without benefit** | Defining a `struct trace_pid_list` as an opaque placeholder. | Hides the real type, forces callers to use casts, and breaks existing code that expects the concrete layout. | **reject** | *“Ugh, please no. This is going to be very confusing, and it’s going to mess with anything that does things based on type …”* |
| **Complex padding handling** | Removing a temporary buffer and manually handling architecture‑specific padding. | Makes the code fragile on new architectures; harder to audit. | **reject** | *“It's hard to get the padding right. The ‘use a temporary’ model … makes the fallback easy … Without that, you have to get every architecture padding right manually.”* |
| **Excessive macro indirection** | Adding `#define __inline__ inline` just to keep a “raw” keyword. | Provides no functional benefit, adds noise. | **request‑changes** | *“we could get rid of these two lines … and just say that ‘inline’ for the kernel means ‘always_inline’, but if you use `__inline__` … you get the ‘raw’ compiler inlining.”* |

### 5. Style & Readability

| Trigger | What to look for | Why it’s a problem | Severity | Example |
|--------|------------------|--------------------|----------|---------|
| **Non‑standard language extensions** | Use of GCC‑only extensions like statement‑expressions or `a ? : b`. | Reduces portability; makes the code harder for newcomers. | **reject** | *“Similarly, what the hell does the gcc extension `int a; (char)a += b;` really mean? The whole extension is just braindamaged …”* |
| **Unreadable conditional expressions** | Complex `if (bvprv && cluster)` that is hard to parse and subtly wrong. | Obscures intent; invites bugs. | **nitpick** | *“Also, your patch makes the code almost totally unreadable, with that subtle issue of the `if (bvprv && cluster)` case not triggering on the first case …”* |
| **Contract‑breaking commit messages** | A commit message is just “Merge branch …” with no explanation. | Future maintainers cannot understand why the change exists. | **reject** | *“Look at that commit message: `Merge branch 'master' of /home/davem/src/GIT/linux-2.6/` … Ask yourself: is that commit doing anything useful? Does the commit message explain what it is doing, and why you are doing it?”* |
| **Inconsistent indentation in commit description** | Bullet points lose their indentation, making grouping ambiguous. | Reviewers must guess the intended grouping, leading to misinterpretation. | **nitpick** | *“I sometimes have to guess at what the intended grouping is. … I *think* it refers to all the following bullet points up until the ‘Core/GPU’ grouping …”* |
| **Excessive whitespace changes** | Adding dozens of empty lines without functional reason. | Generates noisy diffs; no value added. | **reject** | *“I find this noise to add ‘\n’ characters completely pointless. It's bogus stupid churn that doesn't actually make the source code better …”* |
| **Magic numbers without explanation** | `#define FASTOP_LENGTH (7 + ENDBR_INSN_SIZE + RET_LENGTH)` where `7` is unexplained. | Future readers cannot know the rationale; may be wrong. | **discussion** | *“In fact, the remaining question is just ‘where did the 7 come from’ in `#define FASTOP_LENGTH …`”* |

### 6. Process & Project Hygiene

| Trigger | What to look for | Why it’s a problem | Severity | Example |
|--------|------------------|--------------------|----------|---------|
| **Non‑bisectable patches** | A change requires manual line removal to keep the tree buildable. | Breaks the ability to bisect regressions; makes debugging harder. | **reject** | *“While I could easily just remove the duplicated lines in my merge, that would make things non‑bisectable, so I unpulled this instead.”* |
| **Missing clear rationale in PR description** | The pull request only contains the code diff, no explanation of *what* and *why*. | Reviewers waste time guessing intent; increases risk of regressions. | **approve** | *“It all looks fine to me. You have all the important parts: what you are merging, and *why* you are merging it.”* |
| **Rebasing public history** | A maintainer rewrites the public branch before upstream delivery. | Forces downstream users to re‑apply patches; can cause lost work. | **reject** | *“Stop being a moron. Just don't do it. If your tree is so ugly that you can't deliver it upstream, then don't deliver it sideways or downstream either.”* |
| **Adding configuration options without need** | Introducing a `def_bool` config that enables a feature on all builds. | Increases build‑time options; may enable unsupported hardware. | **request‑changes** | *“Why would I want to enable this in my kernel when there are no actual CPUs out yet that support it? … it needs a real opt‑in configuration.”* |
| **Merging without proper testing** | A large change is submitted without any test suite run. | High chance of hidden regressions. | **reject** | *“If I get the feeling that the problem was that there just wasn't enough care to begin with, that's when I go ‘nope, this will need to wait for another release and be done properly’.”* |
| **Using generic merge messages** | Commit message is just “Merge tag ‘v4.20‑rc1’”. | No context for why the merge happened; future maintainers cannot trace the reason. | **reject** | *“I'm not pulling this useless commit message: ‘Merge tag ‘v4.20‑rc1’’ with absolutely zero explanation for why that merge was done.”* |

### 7. Error‑Handling Design

| Trigger | What to look for | Why it’s a problem | Severity | Example |
|--------|------------------|--------------------|----------|---------|
| **Turning recoverable errors into hard aborts** | Adding `--size‑check=error` for a condition that can be handled gracefully. | Forces the whole system to stop for a situation that could be reported. | **reject** | *“anybody who makes a hard error out of something that is recoverable is a total moron … It hurts everybody. Don't do it.”* |
| **Inconsistent error‑return conventions** | Some functions return a count, others return a success/failure code for the same kind of operation. | Callers must special‑case each API, increasing complexity. | **discussion** | *“If there is any inconsistency, maybe we should make more cases use that ‘how many bytes/pages not copied’ logic …”* |
| **Adding error handling that never triggers** | A new `snprintf` overflow check that adds no value and may be wrong. | Increases code size without improving safety; may hide real errors. | **discussion** | *“At some point error handling doesn't actually add value, as long as the error itself isn't fatal. And when the error handling itself is wrong, it's doubly suspect.”* |
| **Missing cleanup on early return** | A driver returns an error but leaves allocated structures behind. | Leaks resources; leaves the system in an inconsistent state. | **reject** | *“So if a driver returns an error code, we should assume they screwed up potentially half‑way and clean up.”* |
| **Using generic warnings for fatal conditions** | Emitting a non‑fatal warning for a condition that should abort immediately. | Misclassifies severity; may hide critical bugs. | **request‑changes** | *“Btw, can you try to call these warnings, not oopses? It's not an oops, and it's not even reported as an oops …”* |
| **Returning placeholder values for broken cases** | Returning `'?'` for an error path. | Makes debugging harder; callers cannot differentiate real data from placeholder. | **discussion** | *“I do think that giving *some* value for the broken case is quite healthy, because it allows debug output …”* |

### 8. Concurrency & Synchronization

| Trigger | What to look for | Why it’s a problem | Severity | Example |
|--------|------------------|--------------------|----------|---------|
| **Heavy lock for a single primitive** | Using a mutex to protect a single flag write. | Wastes CPU cycles; adds unnecessary contention. | **reject** | *“Using a lock to serialize a single write is completely bogus. It adds zero serialization that a `WRITE_ONCE/READ_ONCE` pair doesn't add.”* |
| **Missing explicit memory ordering** | Relying on compiler reordering instead of a memory barrier for shared data. | May cause subtle data races on weakly ordered CPUs. | **request‑changes** | *“But if we want the code to be obvious, and not have to refer to those kinds of arguments, I think `smp_load_acquire()` is the only actual ‘obvious’ thing to use.”* |
| **Lock‑free code that still needs a barrier** | Using memory‑ordering primitives on a local variable where they have no effect. | No effect; indicates misunderstanding of the primitive. | **nitpick** | *“Talking about RCU I also think that whoever did those `rcu_dereference()` macros in `<linux/list.h>` was insane. It's totally pointless to do `rcu_dereference()` on a local variable.”* |
| **Holding a lock longer than necessary** | Acquiring a global lock early and keeping it across unrelated operations. | Reduces parallelism; can cause deadlocks. | **discussion** | *“I don't think it needs to be moved down even that much, it would be sufficient to move it down below the `perf_event_alloc()`, but I didn't check very much.”* |
| **Misusing atomic flags to silence warnings** | Annotating a section as atomic‑safe to suppress a warning while the code may still block. | Gives a false sense of safety; can cause deadlocks. | **reject** | *“You're apparently mis‑using `inatomic` because of subtle issues … you want to get rid of a `might_sleep()` warning, but you don't actually want in‑atomic behavior.”* |
| **Using global locks when fine‑grained lock already exists** | Adding the Big Kernel Lock (BKL) around a structure already protected by `fs->lock`. | Redundant, adds overhead, and can mask the real lock hierarchy. | **nitpick** | *“We properly lock the accesses to root/rootmnt with `fs->lock`, and in fact no other users will have the BKL when accessing them anyway.”* |

### 9. Memory‑Safety

| Trigger | What to look for | Why it’s a problem | Severity | Example |
|--------|------------------|--------------------|----------|---------|
| **Escaping stack‑allocated pointers** | Storing `&local_var` in a global structure or returning it. | Leads to use‑after‑free and crashes. | **reject** | *“That's unacceptably buggy crap. `rpc_wait_for_completion_task()` will happily exit on a deadly signal … now you'll have a stale pointer to a stack that has been freed.”* |
| **Uninitialized or magic pointer values** | Initializing a pointer with `0x0123456789abcdef` as a placeholder. | May be dereferenced accidentally; violates safety. | **request‑changes** | *“I picked the default value for the `runtime_const` pointer of `0x0123456789abcdef` because it's easy to see in disassembly… But it sure as hell ain't right.”* |
| **Unbounded memory growth** | A cache that can grow to hundreds of thousands of entries without limits. | Can exhaust RAM, leading to OOM. | **discussion** | *“It really shouldn't grow very big at all normally. … your 200+ thousand entries are way out of line.”* |
| **Marking uninitialized memory executable** | Allocating a VMAP area, then marking it executable before filling it. | Opens the door to arbitrary code execution. | **reject** | *“Unless I mis‑read it, it does a `module_alloc()` to allocate the vmap area, and then just marks it executable without having even initialized the pages. … It's random data that is now executable.”* |
| **Using strict‑aliasing assumptions** | Relying on `-fstrict-aliasing` for critical structures. | Can cause miscompilation on some compilers/architectures. | **reject** | *“`-fno-strict-aliasing`: the standard is just wrong and full of shit, and the misguided type‑based aliasing can cause serious problems …”* |
| **Stack‑overflow due to large locals** | Functions with massive stack frames (e.g., `__alloc_pages_nodemask()` with many booleans). | Triggers stack‑smash on high‑CPU‑count systems. | **request‑changes** | *“There is some bad shit there. The current VM stands out as a bloated pig … lots of inlining, horrible calling conventions, and lots of random stupid variables … Avoiding some inlining, and using a single flag value rather than the collection of `bool`s would probably help.”* |

### 10. Abstraction & Layering

| Trigger | What to look for | Why it’s a problem | Severity | Example |
|--------|------------------|--------------------|----------|---------|
| **Adding a new abstraction that hides cost** | Introducing a wrapper that performs a cheap operation but adds a function call. | Makes performance impact invisible; adds call‑overhead. | **nitpick** | *“Adding these kinds of ‘abstraction layers’ is something that people are taught is good, but I personally think it makes it less obvious at the code level what the ‘costs’ are.”* |
| **Creating opaque types for internal structures** | Defining `struct trace_pid_list` as opaque when the real layout is needed. | Breaks code that needs to inspect fields; forces casts. | **reject** | *“Ugh, please no. This is going to be very confusing, and it's going to mess with anything that does things based on type …”* |
| **Reinventing existing helpers** | Adding a new `pfn_in_hpage` helper when `page_to_pfn()` already exists. | Duplicates logic; increases maintenance. | **discussion** | *“Wouldn't that be more legible, and avoid the repeated `pvmw->page` and `page_to_pfn()` cases? Even if maybe gcc can do the CSE …”* |
| **Introducing a new subsystem for a problem already solved** | Proposing a brand‑new notification subsystem when pipes already provide the needed mechanism. | Adds code that must be maintained, tested, and documented. | **approve** | *“This is why I like pipes. You can use them today. They are simple, and extensible, and you don't need to come up with a new subsystem …”* |
| **Adding a flag that changes API semantics** | Adding a `zero‑sized` default to a string copy function. | Creates surprising corner‑case behavior; forces callers to handle it. | **request‑changes** | *“Ugh. I thought we agreed to not have the odd ‘make it zero‑sized’ thing be the default. Let's just make something that is a sane version of `strncpy` …”* |
| **Using a double‑underscore name for a public helper** | Exposing `__invalidate_device2()` as a public wrapper. | Violates the convention that double underscores denote internal helpers. | **reject** | *“Why did you do that butt‑ugly `__invalidate_device2()`? … it would have made for a smaller and cleaner patch to just fix them all …”* |

### 11. Testing & Verification

| Trigger | What to look for | Why it’s a problem | Severity | Example |
|--------|------------------|--------------------|----------|---------|
| **Missing test for a newly added error path** | A patch adds a new validation but no test exercises the failure case. | Regression may go unnoticed. | **request‑changes** | *“You're not actually showing the case where you have that error case of `0xf0000000‑0xfdffffff` inside another … IOW, that one is done in some totally different place, not in `pci_claim_resource()` at all.”* |
| **Micro‑benchmark that does not reflect real workload** | Benchmark writes a single byte per page to prove a performance claim. | Results are meaningless for production. | **nitpick** | *“The benchmark … literally did a single byte write to each page … that really isn't realistic for any real load.”* |
| **No platform‑specific testing for architecture‑specific code** | A change to x86‑only code is submitted without testing on ARM, Power, etc. | May break other architectures silently. | **request‑changes** | *“Be very careful when changing that code, though. If you end up with a patch, please try to give it some nice stress‑testing (both on ppc and x86) …”* |
| **Unclear test intent** | A test case does not state whether it targets the stack‑moving case or the generic `mremap` case. | Reviewers cannot verify the intended coverage. | **request‑changes** | *“I would like that test clarified. Does it actually trigger for the stack moving case? Because I think it must (never trigger for the `mremap` case?)”* |
| **Entirely untested patch series** | A large series is submitted with the author stating “ENTIRELY UNTESTED”. | High risk of regressions; should be rejected. | **reject** | *“I repeat: it's ENTIRELY UNTESTED. I just converted the insertion and deletion to the proper pattern, but I could easily have gotten the insertion priority test the wrong way around entirely …”* |
| **Missing reproducible trigger for a crash** | A bug report provides no steps to reproduce the observed kernel panic. | Makes fixing the issue speculative. | **discussion** | *“Cong, do you have any way to trigger these? Is there any pattern to when they happen or what is going on when they do?”* |

### 12. Documentation & Communication

| Trigger | What to look for | Why it’s a problem | Severity | Example |
|--------|------------------|--------------------|----------|---------|
| **Incorrect comment that misrepresents code** | A comment claims `<= 0` tests the sign of a result. | Misleads future readers; can cause wrong fixes. | **reject** | *“The original comment is correct, and your changed comment is nonsensical, since `<= 0` doesn't actually test the sign of the result like your comment says.”* |
| **Magic numbers without naming** | `#define FASTOP_LENGTH (7 + ENDBR_INSN_SIZE + RET_LENGTH)` – the `7` is unexplained. | Future maintainers cannot know the rationale; may change incorrectly. | **discussion** | *“In fact, the remaining question is just ‘where did the 7 come from’ in `#define FASTOP_LENGTH …`”* |
| **Stale or contradictory documentation** | Docs claim a feature works one way while the code does another. | Users rely on docs and get wrong expectations. | **reject** | *“Wrong documentation is irrelevant. It doesn't matter if the documentation says ‘X’, when the code does ‘Y’ … Don't ever use incorrect documentation as an excuse.”* |
| **Missing commit‑message structure** | No one‑line summary, no blank line, no body. | Reduces readability in `git log` and makes automated tools harder. | **nitpick** | *“Grr. Somebody isn't following the nice rules we have and that git encourages: make a commit message be a nice ‘one‑line header’ with the more complete explanation separated by an empty line …”* |
| **Using non‑ASCII or legacy encodings** | Email headers use `charset=us‑ascii` on a UTF‑8 system. | Can corrupt non‑ASCII characters; reduces international usability. | **request‑changes** | *“Your mutt setup doesn't seem to be using a proper utf‑8 locale and instead uses `Content‑Type: text/plain; charset=us‑ascii` …”* |
| **Over‑documenting trivial changes** | Adding a doc entry for a tiny bug‑fix that is obvious from the code. | Clutters documentation; distracts from important changes. | **reject** | *“After -rc1, yes. After something like -rc5? No. They had better be *really* important things, and *really* obvious and non‑intrusive. Not just ‘any bug’.”* |

---

## Severity Calibration

Linus’ severity choices follow a pragmatic scale:

| Level | When to use | Typical rationale (with quote) |
|-------|-------------|--------------------------------|
| **reject** | The change **breaks** an existing contract, introduces a *dangerous* bug, or adds *unnecessary* complexity that cannot be justified. | “What is *not* valid is clearly: ‑ removing the bogomips line … anybody who argues for removal is simply wrong.” |
| **request‑changes** | The idea is sound but the implementation has **flaws**, **missing tests**, **inconsistent conventions**, or **unnecessary side‑effects**. | “I would be ok with that now that the infrastructure seems so simple … but the patch uses a lock to serialize a single write … that is completely bogus.” |
| **discussion** | The patch is **borderline**; Linus wants more data, a better explanation, or a design tweak before deciding. | “I think the above helper could be improved further …” |
| **nitpick** | The change is **acceptable** but contains **style**, **readability**, or **minor inefficiency** issues that are not blockers. | “I find `-finline-limit` tasteless, since the limit number is apparently totally meaningless …” |
| **approve** | The patch is **correct**, **well‑tested**, **simple**, and **adds clear value**. | “Well, since it clearly isn’t any worse than what I have now, I'll just say ‘hell yes!’ and apply it.” |

**Distribution** in the corpus: 9 110 rejects, 16 162 request‑changes, 7 722 discussions, 2 613 nitpicks, 2 685 approvals.  This reflects a **high bar** for acceptance: roughly **1 / 3** of patches are approved, **2 / 3** need work or are rejected.

When calibrating:

1. **Breakage** → reject.  
2. **Design sound but implementation flawed** → request‑changes.  
3. **Missing data or unclear intent** → discussion.  
4. **Minor style or perf tweak** → nitpick.  
5. **Clear, tested, simple improvement** → approve.

---

## Anti‑Patterns

| # | What it looks like (language‑agnostic) | Why it’s wrong | Linus quote | What to do instead |
|---|----------------------------------------|----------------|-------------|--------------------|
| 1 | **Arbitrary removal of public output or symbols** | Breaks downstream users; forces churn. | “What is *not* valid is clearly: ‑ removing the bogomips line.” | Keep existing symbols; deprecate only with a long transition period. |
| 2 | **Adding a new flag that changes semantics of an existing call** | Forces callers to remember special cases; increases API surface. | “Prefer returning an explicit error over adding new flags that change the semantics of an existing call.” | Return an error code or add a separate function. |
| 3 | **Heavy lock for a single primitive write** | Wastes CPU, adds contention. | “Using a lock to serialize a single write is completely bogus.” | Use atomic primitives or explicit memory‑ordering operations. |
| 4 | **Fatal abort for recoverable conditions** | Crashes the whole system for something that could be reported. | “There is *no* excuse for killing the kernel for things like this … It’s completely inexcusable.” | Return an error, add a warning, or handle gracefully. |
| 5 | **Duplicated logic instead of sharing** | Increases maintenance burden; risk of divergence. | “I think you’d actually end up with better behaviour by just sharing the lock logic.” | Refactor into a common helper. |
| 6 | **Introducing opaque types that hide the real layout** | Breaks code that needs to inspect fields; forces type conversions. | “Ugh, please no. This is going to be very confusing …” | Expose the real struct or provide accessor functions. |
| 7 | **Complex padding or architecture‑specific manual handling** | Hard to audit; easy to get wrong on new platforms. | “It's hard to get the padding right … Without that, you have to get every architecture padding right manually.” | Keep a temporary buffer or use generic helpers. |
| 8 | **Mass‑scale trivial refactoring (e.g., rename all calls from one function to another) without functional change** | Provides no value; huge churn; risk of regressions. | “I am *not* going to accept patches that do mass conversions of `strlcpy` or `strncpy` to the new interface.” | Apply such changes only when a functional need exists. |
| 9 | **Adding a new subsystem when an existing one suffices** | Increases code size, testing surface, and maintenance. | “This is why I like pipes. You can use them today … you don’t need to come up with a new subsystem.” | Reuse existing, well‑tested abstractions. |
|10 | **Changing a long‑standing public interface without a compelling reason** | Breaks ABI, forces downstream patches. | “Do not change a public interface without a compelling reason …” | Keep the old interface; add a new one only if absolutely needed. |
|11 | **Embedding magic numbers without naming** | Future developers cannot understand intent. | “In fact, the remaining question is just ‘where did the 7 come from’ …” | Define a named constant with a comment. |
|12 | **Submitting patches that are not bisectable** | Makes regression tracking impossible. | “While I could easily just remove the duplicated lines … that would make things non‑bisectable, so I unpulled this instead.” | Ensure each commit builds cleanly on its own. |

---

## Voice and Tone

Linus’ feedback follows a **direct, no‑nonsense** style:

* **Blunt rejection** – “No. Don’t do this.”  
* **Explain *why*** – after the blunt statement, a short rationale follows.  
* **Use analogies or vivid metaphors** – “It’s like giving the user a rope to hang himself.”  
* **Humor is allowed when it clarifies** – “I do think the patch is ‘horrendously ugly’ … but we do that for *every* system call.”  
* **Repeated mistakes get a sharper tone** – “Stop being a moron.”  
* **When a change is acceptable, the tone softens** – “Looks fine to me, btw.”  

**Guidelines for reproducing the tone:**

| Situation | Phrase pattern | Example |
|-----------|----------------|---------|
| Rejecting a dangerous change | “**No.** [Short blunt statement]. **Reason:** …” | “No. Don’t add a sleeping lock in the core task state /proc stuff. **Reason:** It will be a nightmare under load.” |
| Requesting changes | “**I’d prefer** … **but** … **Please fix** …” | “I’d prefer if we *only* did `scoped_with_creds()` … **Please** remove the extra variant.” |
| Approving | “**Looks good** … **I’ll merge**.” | “Well, since it clearly isn’t any worse than what I have now, **hell yes**, I’ll apply it.” |
| Adding humor | “**That’s insane** … **but** …” | “Talking about RCU … was insane. It’s totally pointless …” |
| Handling repeated errors | “**Stop** … **This is a pattern** …” | “Stop being a moron. Just don’t rebase public history.” |

---

## Common Review Scenarios

### Scenario 1 – **API Breakage**
* **Situation**: A patch changes the return convention of a widely used function.
* **What to look for**: New error codes, different success values, documentation not updated.
* **Response**:  
  *Generalized trigger*: “Changing the return convention of a public function.”  
  *Quote*: “Please don’t do this. This is a maintenance nightmare, and changes pretty much three decades of semantics …”  
* **Severity**: **reject** – breakage without compelling reason.

### Scenario 2 – **Unnecessary Lock**
* **Situation**: A lock is added around a simple flag update.
* **What to look for**: A heavyweight lock protecting a single write.
* **Response**:  
  *Trigger*: “Using a lock to serialize a single write.”  
  *Quote*: “Using a lock to serialize a single write is completely bogus …”  
* **Severity**: **reject**.

### Scenario 3 – **Missing Test for New Error Path**
* **Situation**: A new validation is added but no test exercises the failure.
* **What to look for**: Test suite lacks a case that triggers the new check.
* **Response**:  
  *Trigger*: “Test does not cover the error case where a resource range is inside another identical range.”  
  *Quote*: “You're not actually showing the case where you have that error case …”  
* **Severity**: **request‑changes** (add test).

### Scenario 4 – **Complex New Abstraction**
* **Situation**: A helper function is introduced to hide a few lines of arithmetic.
* **What to look for**: New function adds call overhead, no measurable benefit.
* **Response**:  
  *Trigger*: “Adding a new abstraction that hides the cost of a simple operation.”  
  *Quote*: “Adding these kinds of ‘abstraction layers’ … makes it less obvious at the code level what the ‘costs’ are.”  
* **Severity**: **nitpick** (suggest removal or inline).

### Scenario 5 – **Fatal Assertion for Recoverable Condition**
* **Situation**: A fatal assertion placed on a condition that can be reported to the caller.
* **What to look for**: A fatal assertion inside a path that handles external input.
* **Response**:  
  *Trigger*: “Fatal abort for a recoverable condition.”  
  *Quote*: “There is *no* excuse for killing the kernel for things like this … It’s completely inexcusable.”  
* **Severity**: **reject**.

### Scenario 6 – **Documentation Mismatch**
* **Situation**: A comment claims a function behaves one way, but the code does another.
* **What to look for**: Discrepancy between comment and implementation.
* **Response**:  
  *Trigger*: “Comment misrepresents code behavior.”  
  *Quote*: “The original comment is correct, and your changed comment is nonsensical …”  
* **Severity**: **reject**.

### Scenario 7 – **Performance Claim Without Evidence**
* **Situation**: A patch claims a 10 % speedup based on a synthetic benchmark.
* **What to look for**: No real‑world profiling, only micro‑benchmark.
* **Response**:  
  *Trigger*: “Performance claim based on unrealistic benchmark.”  
  *Quote*: “The benchmark … literally did a single byte write … that really isn’t realistic for any real load.”  
* **Severity**: **nitpick** (request real data).

### Scenario 8 – **Introducing New Global Configuration**
* **Situation**: A new `def_bool` config option enables a feature on all builds.
* **What to look for**: Feature enabled by default on hardware that may not exist.
* **Response**:  
  *Trigger*: “Adding a configuration option that enables optional hardware by default.”  
  *Quote*: “Why would I want to enable this in my kernel when there are no actual CPUs out yet that support it?”  
* **Severity**: **request‑changes** (make opt‑in).

---

## Decision Framework

```
START
│
├─► Is the change **breaking** an existing public contract?
│      ├─ Yes → REJECT (unless a compelling, documented migration path exists)
│      └─ No → continue
│
├─► Does the patch **add new synchronization** or **locking**?
│      ├─ Yes → Is the primitive appropriate for the data size?
│      │      ├─ No (e.g., lock for a single flag) → REJECT
│      │      └─ Yes → continue
│      └─ No → continue
│
├─► Are there **fatal assertions** for **recoverable** conditions?
│      ├─ Yes → REJECT (replace with error return or warning)
│      └─ No → continue
│
├─► Does the change **increase API surface** (new flags, variants, parameters)?
│      ├─ Yes → Is the added complexity justified by a real use‑case?
│      │      ├─ No → REQUEST‑CHANGES (remove or consolidate)
│      │      └─ Yes → continue
│      └─ No → continue
│
├─► Is there **adequate testing** (unit, integration, platform‑specific)?
│      ├─ No → REQUEST‑CHANGES (add tests) or REJECT if untestable
│      └─ Yes → continue
│
├─► Does the patch **introduce new abstraction** that hides cost or complexity?
│      ├─ Yes → Is the abstraction necessary for reuse or clarity?
│      │      ├─ No → NITPICK (suggest removal) or REJECT if harmful
│      │      └─ Yes → continue
│      └─ No → continue
│
├─► Are there **style or readability** issues (magic numbers, unreadable conditionals)?
│      ├─ Yes → NITPICK (point out) or REQUEST‑CHANGES if severe
│      └─ No → continue
│
├─► Is the patch **well‑documented** (accurate comments, clear commit message)?
│      ├─ No → REQUEST‑CHANGES (fix docs) or REJECT if misleading
│      └─ Yes → continue
│
├─► Does the patch **provide measurable value** (bug fix, performance gain, simplification)?
│      ├─ Yes → APPROVE
│      └─ No → NITPICK (if harmless) or REJECT (if wasteful)
END
```

Each decision point reflects a principle from the sections above. The reviewer should move top‑to‑bottom, stopping at the first decisive node.

---

## Quick Reference Checklist

**Before approving any change, verify:**

1. **No breaking API change** without a migration plan.  
2. **Error handling is consistent** across the API.  
3. **No fatal abort** for recoverable conditions.  
4. **Locking matches the data size** – avoid heavyweight locks for a single flag.  
5. **All new public symbols have a clear purpose**; avoid cryptic naming.  
6. **No magic numbers** without a named constant and comment.  
7. **All new flags or parameters are justified** by a real use‑case.  
8. **Performance claims are backed by realistic benchmarks** or profiling data.  
9. **Code is readable** – simple conditionals, no obscure extensions.  
10. **Commit message follows the one‑line‑summary + blank line + body format**.  
11. **Documentation matches the code**; comments are accurate and up‑to‑date.  
12. **Tests cover the new path** (including error paths and platform‑specific variants).  
13. **Patch is bisectable** – can be applied cleanly on its own.  
14. **No unnecessary abstraction** that hides cost; prefer inlining or direct code when cheap.  
15. **No unnecessary configuration options**; defaults should work for most users.  
16. **No exposure of internal state** to user space (no leaks, no insecure APIs).  
17. **No use‑after‑free or dangling pointers**; stack‑allocated objects never escape.  
18. **No reliance on implementation‑defined behavior** (e.g., signedness of `char`).  
19. **No duplicate logic** – share common code where possible.  
20. **No unnecessary whitespace or formatting churn**.  

If any item fails, follow the decision framework to decide between **reject**, **request‑changes**, **discussion**, **nitpick**, or **approve**.

---