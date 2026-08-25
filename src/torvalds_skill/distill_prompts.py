"""
Prompt templates for the distillation process.

Contains all large prompt string constants used in the distillation pipeline.
"""

DISTILL_SYSTEM_PROMPT = """\
You are writing a code review skill based on the reviewing patterns of Linus Torvalds, \
distilled from thousands of his real code reviews on the Linux kernel mailing list.

═══════════════════════════════════════════════════════════════════════
INTERVIEW-DERIVED DEFINITIONS (from INTERVIEW DATA)
═══════════════════════════════════════════════════════════════════════

The INTERVIEW DATA section contains Linus Torvalds' explicit, reflective
statements about engineering philosophy — drawn from interviews and talks.
These are NOT code-review moves; they are his own definitions and mindset.

You MUST use interview quotes in these sections:

1. The "Key Definitions" section MUST contain at least 3 definitions grounded
   in interview quotes, cited as (Interview: filename) or (TED 2016) etc.
   Define: "good taste", "good code", "bad code", "special case", "data structure"
   using his own explanations.

2. The "Reviewer Mindset" section MUST reference at least 2 interview quotes
   about his philosophy. Explain WHY each attitude matters.

Quote interviews verbatim with attribution like: (TED 2016) or (Linux Journal 2021).
These quotes are EVIDENCE for definitions, not triggers. They do NOT replace
the moves-based triggers.

- Distinguish between his code-review voice (moves corpus) and his reflective
  voice (interviews) — both inform the method

═══════════════════════════════════════════════════════════════════════
CRITICAL RULE: TOTAL LANGUAGE AND PROJECT AGNOSTICISM
═══════════════════════════════════════════════════════════════════════

The skill must work for a reviewer reading Python, Go, Rust, TypeScript, Java, Haskell, \
or any other language. Torvalds reviews C kernel code, but his REVIEWING METHOD is \
universal. You must strip ALL C-specific and kernel-specific content from triggers \
and principles, keeping ONLY the underlying reviewing method.

TRIGGERS and PRINCIPLES must NEVER contain:
  - C types or keywords: int, char, void, struct, union, enum, typedef, const, volatile, \
    static, inline, register, auto
  - C macros or functions: BUG_ON, WARN_ON, READ_ONCE, WRITE_ONCE, copy_to_user, \
    copy_from_user, get_user, put_user, kmalloc, kfree, spin_lock, mutex, \
    rcu_dereference, smp_load_acquire, smp_store_release, mb(), wmb(), rmb()
  - C preprocessor directives: #ifdef, #ifndef, #define, #if, #endif, #pragma, #include
  - C control flow: goto (as a concept, not in quotes)
  - NULL (as a concept, not in quotes)
  - Kernel concepts: syscall, inode, dentry, superblock, sk_buff, task_struct, \
    file_operations, module_init, module_exit, __init, __exit
  - Kernel-specific identifiers: strlcpy, strscpy, kstrtol, kstrtoul, IS_ERR, \
    ERR_PTR, GFP_KERNEL, GFP_ATOMIC, pagefault_disable, preempt_disable
  - Linux-specific APIs: procfs, sysfs, debugfs, ioctl, ioctl numbers, \
    set_memory_x, module_alloc
  - Architecture-specific terms: x86, ARM, riscv, SMP, BKL, RCU (as a C macro), \
    barrier, smp

QUOTES (the "Response" field) are Torvalds' VERBATIM words and MUST be preserved \
exactly as written, including any C-specific terms they contain. The quotes \
ILLUSTRATE the voice and tone — they are evidence, not the trigger itself. Always \
introduce a quote with the generalized trigger, then show the original wording as \
an example.

CRITICAL: The translation table applies to TRIGGER DESCRIPTIONS ONLY. Quotes and
examples preserve verbatim wording. Over-generalization is as bad as under-generalization
— if you strip too much specificity, the trigger loses its diagnostic power. A trigger
that says "check for errors" is useless; "check allocation return before use" is actionable.

TRANSLATION TABLE — when you encounter these in the data, generalize as shown:

  C/Kernel specific                           → Language-agnostic trigger
  ──────────────────────────────────────────────→────────────────────────────────────
  BUG_ON() / BUG()                            → Fatal assertion/panic used for a recoverable condition
  WARN_ON()                                   → Warning assertion that masks a real bug
  READ_ONCE / WRITE_ONCE                      → Unsynchronized access to shared mutable data
  volatile                                     → Relying on language semantics instead of explicit sync
  copy_to_user / copy_from_user               → Untrusted/external boundary crossing without validation
  spin_lock / mutex                            → Lock-based concurrency primitive
  rcu_dereference                              → Lock-free data access without memory ordering
  kmalloc / kfree                             → Manual memory allocation/deallocation
  strlcpy / strscpy                            → String/buffer copy without bounds safety
  __user annotation                            → Missing type-level ownership/safety annotation
  returning -EFAULT / -EINVAL                  → Returning magic error codes instead of typed errors
  #ifdef CONFIG_X                              → Compile-time conditional logic instead of runtime config
  goto cleanup                                 → Manual resource cleanup instead of RAII/defer/using
  struct file_operations                       → Interface/API contract change
  syscall ABI change                            → Public API/ABI breakage
  inline function                              → Premature optimization hint
  typedef struct                                → Type aliasing that hides the real type

This table is NOT exhaustive. Apply the SAME generalization logic to EVERY C/kernel \
term you encounter. If a trigger mentions ANY language-specific construct, rewrite it \
in terms of the BEHAVIOR or DESIGN problem it represents.

SELF-CHECK before writing each trigger:
  1. Does the trigger mention a type, function, macro, or keyword from a specific language?
     → If YES, rewrite it.
  2. Would this trigger make sense to a Python reviewer? A Rust reviewer? A Go reviewer?
     → If NO, rewrite it.
  3. Does the trigger describe a DESIGN problem (not a syntax problem)?
     → It should. Syntax problems are language-specific; design problems are universal.
  4. Does the trigger cover more than 3 distinct bug types?
     → If YES, split it into specific sub-triggers. Broad triggers like "Operation
       without checking target state" should become: "unchecked allocation return",
       "unchecked boundary-crossing return", "unchecked conversion return",
       "unchecked array index bounds". Specificity beats catch-all categories.

═══════════════════════════════════════════════════════════════════════
SKILL QUALITIES
═══════════════════════════════════════════════════════════════════════

1. Language-agnostic — see the critical rule above. This is non-negotiable.
2. Four qualities of review rules — EVERY trigger must be ONE of these four types:
   a) **Invariant TRUE**: A condition that MUST always be true (e.g., "API must not break existing users without compelling reason"). State it as a verifiable condition.
   b) **Invariant FALSE**: A condition that MUST NEVER be true (e.g., "Never crash the system for a recoverable error"). State it as something to reject outright.
   c) **Precedence rule**: An explicit ordering when rules conflict (e.g., "Correctness > Performance > Complexity > Style", "Breaking users > Performance optimization", "Security > Convenience").
   d) **General guideline for identifiable pattern**: A concrete pattern that can be detected (e.g., "When you see X, flag it because Y"). Must have clear detection criteria, not vague advice.
3. Explicit precedence chain — state the hierarchy early in the skill:
   - Correctness (invariants, safety, no crashes) > Performance > Complexity > Style
   - Protecting existing users > Adding new features
   - Security > Convenience
   - Bisectability > Quick fixes
4. Concrete definitions — define key terms explicitly:
   - "Bug": A condition that causes incorrect behavior, crashes, data corruption, or security vulnerabilities.
   - "Hack" / "Workaround": A temporary fix that masks the root cause without addressing it.
   - "Patch": A code change (neutral term).
   - "Non-negotiable": A rule that has no exceptions (e.g., "Never break existing APIs without compelling reason").
5. Actionable. Every principle must tell the reviewer WHAT to do and WHEN. Not "be careful" but "when X appears, flag it because Y."
6. Grounded in real examples. Use the provided quotes — they show the voice and tone that IS part of the method. Preserve them verbatim.
7. Honest about what the data shows. Use the actual counts. Don't invent statistics.
8. Comprehensive. The skill should be a thorough reference, not a summary. Aim for 4000-7000 words total. Cover each theme in depth with multiple examples.

═══════════════════════════════════════════════════════════════════════
YOUR TASK
═══════════════════════════════════════════════════════════════════════

You will receive raw review moves sampled from the corpus, grouped by category. \
The corpus combines 38,000+ email review moves and 500+ interview passages, sampled into 350 representative patterns. \
Each pattern has a `source` field indicating whether it comes from email ("source: email") or interview ("source: interview"). \
Treat interview-sourced patterns with equal weight to email-sourced patterns — both are valid evidence of Torvalds' reviewing method. \

ADDITIONAL TRIGGER THEMES TO CONSIDER:
   - Copy-paste code detection: duplicate blocks, cargo-cult patterns where code is
   - Magic numbers in error messages: undocumented status codes, bare integers in error
     paths that lack context
   - Format-string vulnerabilities: snprintf destination size vs format expansion,
     unchecked format-string arguments, integer overflow in size calculation
   - Array/index bounds: unchecked array index operations, boundary-crossing returns
     without bounds validation, conversion operations without range checks
   - Inconsistent error code conventions: mixed return-value conventions within the
     same module (some functions return -1 on error, others return NULL, others
     throw exceptions)
Each move has: trigger (what prompted the review), principle (the underlying rule), \
response (Torvalds' actual words), severity, and date.

1. READ all the moves across all categories.
2. FIND recurring themes — principles that appear in multiple moves, even if phrased \
differently. Group them semantically, not lexically. "Don't break userspace" and \
"we don't break existing setups" are the same principle.
3. For each theme, pick the most representative quotes and triggers. Use multiple quotes \
per theme when they show different facets. GENERALIZE every trigger using the \
translation table and the self-check rules above.
4. LABEL each trigger with its type: invariant-true, invariant-false, precedence-rule, \
or general-guideline. Every trigger MUST be one of these four types — no soft guidelines.
5. ENFORCE the precedence chain: when rules conflict, correctness > performance > \
complexity > style. Make this explicit in the Precedence and Priorities section.
6. DEFINE key terms concretely: bug, hack, workaround, patch, non-negotiable. No \
vague language — each definition must be verifiable.
7. SYNTHESIZE the themes into the skill structure below.

The output MUST start with YAML frontmatter enclosed in --- fences, then the markdown body.

Output exactly this structure (replace the bracketed parts with real content):

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
  | Trigger | Severity | Principle |
  |---------|----------|----------|
  | foo     | high     | bar      |
  ```

---
name: linus-torvalds-skill
description: "[1-2 sentence description of what this skill teaches]"
metadata:
  author: "torvalds-skill pipeline"
  version: "1.0.0"
  tags:
    - code-review
    - reviewer-method
    - torvalds
---

# Linus Torvalds Review Method

> [Brief description: what this skill is, what corpus it was distilled from, \
and the corpus size (use the provided stats). 2-3 sentences. State explicitly \
that the method is language- and project-agnostic.]

## Reviewer Mindset
[The 5-7 core attitudes that define the approach. Each with a one-line principle \
and a real Torvalds quote. Explain WHY each attitude matters.]

## Review Triggers
[Comprehensive catalog of "when you see X, flag it" patterns, organized into THREE 
hierarchical tiers that mirror how a human expert reviews: fatal flaws first, then 
design issues, then nitpicks. Group triggers by semantic theme within each tier 
(not by the raw category labels — use themes you discover across categories).

### Tier Structure

Organize all triggers into these three levels with clear section headers:

**Level 1: Global Invariants (non-negotiables)**
- Fatal flaws that must NEVER occur — any violation is a blocking review finding
- Examples: "never break userspace", "never break ABI", "correctness over performance"
- These are invariant-false or precedence-rule types
- Severity: always reject

**Level 2: Structural Patterns (architecture-level)**
- Data structure design, encapsulation, layering, API design issues
- Wrong abstractions, leaky interfaces, premature abstraction
- These are serious design issues that affect long-term maintainability
- Severity: reject or request-changes depending on impact

**Level 3: Tactical Guidelines (implementation-level)**
- Naming, comments, documentation, code organization, error handling patterns
- Style nits, minor inconsistencies
- These are non-blocking but should be flagged for improvement
- Severity: request-changes or nitpick

For EACH trigger provide:
- **Type**: invariant-true / invariant-false / precedence-rule / general-guideline
- **What to look for**: generalized, language-agnostic description of the pattern
- **Why it's a problem**: the underlying design principle being violated
- **Severity**: reject / request-changes / nitpick
- **Example (original wording)**: a real Torvalds quote showing how he handles it — 
introduce it with the generalized trigger, then show the verbatim quote
- 1-2 additional supporting quotes when available

FORMAT REQUIREMENT: Use structured nested bullet lists for all triggers. DO NOT use \
markdown tables. Example of correct format:

```
### Theme: Assertion Misuse
- **Trigger**: Fatal assertion used for recoverable condition
  - **Type**: invariant-false
  - **What to look for**: panic/crash in code paths that should handle errors gracefully
  - **Why it's a problem**: Recoverable errors must be handled without crashing
  - **Severity**: reject
  - **Example**: "This is fundamentally broken. You don't BUG_ON() a condition that \
    can happen from bad user input."
```

EVERY trigger must pass the self-check: no language-specific terms, makes sense to \
reviewers in any language, describes a design problem. Cover at least 12 distinct \
trigger themes. Each theme should have 3-6 specific triggers. Label each trigger \
with its type (invariant-true, invariant-false, precedence-rule, or general-guideline).]

## Reasoning Protocol
[Instructions for the [REASON]→[ACT] workflow that prevents pattern-matching false 
positives. Every review finding MUST follow this two-step process:

**[REASON]**: First explain WHY a trigger applies:
- Identify the specific pattern in the code
- Cite the underlying principle being violated
- Explain the consequence of the issue
- This forces the reviewer to understand the "why" before issuing the finding

**[ACT]**: Then issue the review action:
- The finding (what is wrong)
- The severity (reject / request-changes / nitpick)
- The suggested fix or improvement

Example format:
```
[REASON]: This code uses a fatal assertion (panic/crash) in a path that handles 
external input. The principle is "recoverable errors must be handled gracefully". 
The consequence is that malformed input will crash the system instead of returning 
a proper error.

[ACT]: Reject. Replace the assertion with proper error handling that returns a 
clear error message to the caller.
```

This protocol is language-agnostic — no C/kernel-specific examples. It ensures 
every finding is grounded in reasoning, not keyword matching. Agents must explain 
the design problem before proposing a fix.]

## Precedence and Priorities
[Explicit hierarchy of rules when they conflict. State clearly:
- Correctness (invariants, safety, no crashes) > Performance > Complexity > Style
- Protecting existing users > Adding new features
- Security > Convenience
- Bisectability > Quick fixes
- Measured performance > Theoretical optimization

For each priority rule, explain WHY it takes precedence and give a real quote \
showing Torvalds making that tradeoff. This section is CRITICAL — it resolves \
ambiguity when multiple rules apply.]

## Decision Cards
[For each contentious precedence rule or non-obvious principle, provide a \
"decision card" that explains the RATIONALE — not just the rule, but WHY it \
exists. A reviewer who understands the why can apply judgment in novel situations; \
one who only knows the what cannot. Cover at minimum these contentious rules: \
  - Why Correctness > Performance (when is performance worth a correctness risk?) \
  - Why Protecting existing users > Adding new features (when is a breaking change justified?) \
  - Why Security > Convenience (when is convenience worth a security tradeoff?) \
  - Why Bisectability > Quick fixes (when is a non-bisectable fix acceptable?) \
  - Why Measured performance > Theoretical optimization (when does theoretical win?) \
  - Why Special cases are bad (when is a special case actually correct?) \
  - Why Complexity must be justified (when is complexity warranted?) \

FORMAT REQUIREMENT: Use structured nested bullet lists. DO NOT use markdown tables. \
Each decision card MUST contain: \
  - **Rule**: the precedence or principle stated concisely \
  - **Why it exists**: the underlying engineering or economic reason \
  - **When it does NOT apply**: the legitimate exception conditions \
  - **Tradeoff**: what is sacrificed by following this rule \
  - **Evidence**: a real Torvalds quote showing him making (or explaining) this tradeoff \

Example of correct format: \
\
```
### Decision Card: Correctness > Performance
- **Rule**: Correctness invariants take precedence over performance optimization
- **Why it exists**: A fast program that produces wrong results is worthless. \
  Correctness bugs compound — they affect every downstream consumer. Performance \
  issues are localized and tunable later.
- **When it does NOT apply**: When the "correctness" issue is a theoretical edge \
  case with negligible real-world impact AND the performance cost of handling it \
  is severe. Rare.
- **Tradeoff**: May reject micro-optimizations that technically preserve correctness \
  but make the code harder to verify.
- **Evidence**: "If it's a choice between a fast program and a correct program, \
  we'll take correct every time."
```
\
Each card must be grounded in a real quote from the data. Do not invent rationale — \
derive it from what Torvalds actually said. If the data does not support a card \
for a listed rule, omit that card rather than fabricate one.]

## Key Definitions
[Define key terms explicitly so there is no ambiguity. FORMAT: use a structured \
bullet list (NOT a markdown table). For each term: bold the term name, then give \
the definition, then a real Torvalds quote showing how he uses it.
- "Bug": A condition that causes incorrect behavior, crashes, data corruption, or security vulnerabilities.
- "Hack" / "Workaround": A temporary fix that masks the root cause without addressing it.
- "Patch": A code change (neutral term).
- "Non-negotiable": A rule that has no exceptions (e.g., "Never break existing APIs without compelling reason").
    - "Recoverable error": A condition that can be handled gracefully without crashing.
    - "API contract": The documented or implied behavior that external code depends on.
    - "Format-string vulnerability": A condition where snprintf size calculation or format arguments can overflow the destination buffer.

## Cross-File Review
Triggers must be applied across ALL reviewed files, not just within a single file. Cross-file
contract violations must be checked:
- Header vs implementation: A contract defined in a header must be honored in the implementation
- Caller vs callee: A caller's assumptions about a callee's behavior must be validated
- Module boundaries: State transitions across module boundaries must be consistent
- Public API vs internal usage: Internal changes must not break public API contracts

Example: If a header declares a function returns an allocated pointer, the implementation
must actually allocate. If a module documents a state machine, all files implementing that
module must follow the state transitions.]

## Voice and Tone
[How Torvalds phrases feedback. The tone IS part of the method — certainty, directness, \
explaining the "why" after the "no". With real quotes. Cover:
- When to be blunt vs. when to explain
- How to phrase a rejection
- How to explain the reasoning
- When humor or analogy is appropriate
- How to handle repeated mistakes]

## Anti-Patterns
[Anti-patterns Torvalds rejects, with the principle each violates. Present as a \
structured list (NOT a markdown table): pattern name, why it's wrong, the governing \
principle, and a real quote. Cover: special-case branching, abstraction for its \
own sake, breaking APIs without reason, silent error swallowing, premature \
optimization, complexity without justification, ignoring memory safety, \
undocumented workarounds, and process violations.]

## Severity Calibration
[Use the provided calibration statistics to GROUND severity assignments in the \
real corpus. For each category, state the empirical reject rate, request-changes \
rate, and nitpick rate as percentages. Explain what the data says about how \
Torvalds actually calibrates severity — e.g., "API-stability issues are rejected \
37.9% of the time, the highest of any category" or "style issues are nitpicked \
35.5% of the time but rarely rejected." Do NOT invent statistics — use the exact \
numbers provided in the calibration data. Group categories by their dominant \
severity and explain the pattern: which categories Torvalds treats as \
reject-first, which as fix-first, and which as discuss-only.

FORMAT REQUIREMENT: Use structured nested bullet lists for category statistics. \
DO NOT use markdown tables. Example of correct format:

```
- **Category: api-stability** (n=42)
  - reject: 37.9%
  - request-changes: 45.2%
  - nitpick: 16.9%
  - dominant: reject
  - Pattern: Highest reject rate — API breaks are non-negotiable
```
]

## Severity Decision Tree
[A category-based decision tree derived from the calibration statistics. \
Present it as nested if/then rules using ONLY the category names and the \
empirical severity rates: "IF the issue is in category {category} AND it \
breaks existing users/APIs THEN reject (corpus reject rate: {X}%)" or "IF \
the issue is in category {category} AND it is a style/readability concern \
THEN nitpick (corpus nitpick rate: {X}%." Synthesize the rules into a \
simplified decision procedure: "To assign severity, check in order: (1) does \
the change break existing users/APIs? → reject; (2) does it introduce a \
correctness or memory-safety bug? → reject or request-changes depending on \
severity; (3) is it a style issue? → nitpick; etc." The decision tree must be \
language-agnostic — no C/kernel identifiers, no type names, no macro names.

FORMAT REQUIREMENT: Use structured nested bullet lists for decision rules. \
DO NOT use markdown tables. Example of correct format:

```
### Severity Decision Procedure
1. Check for API/ABI breaks
   - IF breaks existing users/APIs → reject (37.9% reject rate for api-stability)
   - IF adds new public symbols without justification → request-changes
2. Check for correctness issues
   - IF introduces bug/crash → reject
   - IF potential bug (uninitialized data, off-by-one) → request-changes
3. Check for style/readability
   - IF style inconsistency → nitpick (35.5% nitpick rate for style)
```

NON-EXHAUSTIVE CATALOG: The triggers you list are a STARTING SET, NOT A CEILING. The
reviewer must still apply general code-review judgment beyond the listed triggers. This
is explicitly NOT an exhaustive catalog of every possible bug — it captures recurring
themes from the corpus. When reviewing code, ask: "What else could be wrong here?"
beyond the specific triggers listed. The triggers highlight common patterns; they do
NOT authorize ignoring bug classes that aren't listed. A reviewer using this skill
should find as many bugs as they would without it, not fewer.
]

## Quick Reference Checklist
[A one-page checklist a reviewer can scan: "Before approving, verify:" with 15-20 \
concrete items grouped by theme. Every item must be language-agnostic.]

Keep the total output between 4000-7000 words. Be concise — every section must have real
quotes from the data, but do not pad. Do not invent quotes — only use what is provided.
If you need more examples for a theme, use the quotes you have and note the pattern.
Prioritize completing ALL required sections over depth in any single section.

REMEMBER: The final test is simple — if a reviewer reading this skill could NOT tell \
whether it was distilled from C kernel reviews, Python web framework reviews, or Rust \
systems programming reviews, you have succeeded. The METHOD must shine through; the \
LANGUAGE must be invisible.
"""


def build_category_system_prompt(category: str) -> str:
    """Build category-specific system prompt for single-category distillation.
    
    Stage 1 of two-stage distillation: focuses the LLM's attention on
    patterns within one category (~25 patterns) rather than all 350.
    """
    return f"""\
You are writing a section of a code review skill document, focusing on ONE category of review patterns.

═══════════════════════════════════════════════════════════════════════
CRITICAL RULE: TOTAL LANGUAGE AND PROJECT AGNOSTICISM
═══════════════════════════════════════════════════════════════════════

The skill must work for a reviewer reading Python, Go, Rust, TypeScript, Java, Haskell, 
or any other language. Torvalds reviews C kernel code, but his REVIEWING METHOD is 
universal. You must strip ALL C-specific and kernel-specific content from triggers 
and principles, keeping ONLY the underlying reviewing method.

TRIGGERS and PRINCIPLES must NEVER contain:
  - C types or keywords: int, char, void, struct, union, enum, typedef, const, volatile, static, inline
  - C macros or functions: BUG_ON, WARN_ON, READ_ONCE, WRITE_ONCE, copy_to_user, kmalloc, kfree
  - Kernel concepts: syscall, inode, dentry, superblock, sk_buff, task_struct
  - Linux-specific APIs: procfs, sysfs, debugfs, ioctl
  - Architecture-specific terms: x86, ARM, riscv, SMP, RCU

QUOTES (the "Response" field) are Torvalds' VERBATIM words and MUST be preserved 
exactly as written, including any C-specific terms they contain. The quotes 
ILLUSTRATE the voice and tone — they are evidence, not the trigger itself.

TRANSLATION TABLE — when you encounter these in the data, generalize as shown:

  C/Kernel specific                           → Language-agnostic trigger
  ──────────────────────────────────────────────→────────────────────────────────────
  BUG_ON() / BUG()                            → Fatal assertion/panic used for a recoverable condition
  WARN_ON()                                   → Warning assertion that masks a real bug
  READ_ONCE / WRITE_ONCE                      → Unsynchronized access to shared mutable data
  volatile                                     → Relying on language semantics instead of explicit sync
  copy_to_user / copy_from_user               → Untrusted/external boundary crossing without validation
  spin_lock / mutex                            → Lock-based concurrency primitive
  rcu_dereference                              → Lock-free data access without memory ordering
  kmalloc / kfree                             → Manual memory allocation/deallocation
  strlcpy / strscpy                            → String/buffer copy without bounds safety
  __user annotation                            → Missing type-level ownership/safety annotation
  returning -EFAULT / -EINVAL                  → Returning magic error codes instead of typed errors
  #ifdef CONFIG_X                              → Compile-time conditional logic instead of runtime config
  goto cleanup                                 → Manual resource cleanup instead of RAII/defer/using
  struct file_operations                       → Interface/API contract change
  syscall ABI change                            → Public API/ABI breakage
  inline function                              → Premature optimization hint
  typedef struct                                → Type aliasing that hides the real type

═══════════════════════════════════════════════════════════════════════
YOUR TASK
═══════════════════════════════════════════════════════════════════════

You will receive review moves from the category: {category}

Generate a skill fragment that:
1. Identifies the recurring themes within this category
2. For each theme, provides:
   - A clear trigger (language-agnostic)
   - The underlying principle
   - Severity level (reject / request-changes / nitpick)
   - A representative Torvalds quote (verbatim)
3. Labels each trigger with its type: invariant-true, invariant-false, precedence-rule, or general-guideline

Output format (markdown):

## Category: {category}

### Theme 1: [Theme Name]
- **Trigger**: [language-agnostic description]
  - **Type**: [invariant-true / invariant-false / precedence-rule / general-guideline]
  - **Why it's a problem**: [underlying design principle]
  - **Severity**: [reject / request-changes / nitpick]
  - **Example**: "[Torvalds quote]"

[Continue with 3-6 triggers for this category]

Remember: Every trigger must be language-agnostic. If it mentions C keywords or kernel
concepts, generalize it to the underlying design problem.
"""


def build_synthesis_system_prompt() -> str:
    """Build synthesis system prompt for combining category fragments."""
    return """\
You are synthesizing category-specific skill fragments into a unified SKILL.md document.

═══════════════════════════════════════════════════════════════════════
CRITICAL RULE: TOTAL LANGUAGE AND PROJECT AGNOSTICISM
═══════════════════════════════════════════════════════════════════════

The final skill must work for a reviewer reading Python, Go, Rust, TypeScript, Java, Haskell, 
or any other language. All C-specific and kernel-specific content must be generalized.

═══════════════════════════════════════════════════════════════════════
SKILL QUALITIES
═══════════════════════════════════════════════════════════════════════

1. Language-agnostic — triggers must work for any language
2. Four qualities of review rules — every trigger must be ONE of these:
   a) Invariant TRUE: A condition that MUST always be true
   b) Invariant FALSE: A condition that MUST NEVER be true
   c) Precedence rule: An explicit ordering when rules conflict
   d) General guideline: A concrete pattern with clear detection criteria
3. Explicit precedence chain: Correctness > Performance > Complexity > Style
4. Concrete definitions — define key terms explicitly
5. Actionable — tell the reviewer WHAT to do and WHEN
6. Grounded in real examples — use the provided quotes
7. Comprehensive — aim for 4000-7000 words total

═══════════════════════════════════════════════════════════════════════
OUTPUT STRUCTURE
═══════════════════════════════════════════════════════════════════════

Output exactly this structure (replace the bracketed parts with real content):

**CRITICAL FORMATTING RULE: DO NOT USE MARKDOWN TABLES**
- Use structured nested bullet lists, NOT `| column | column |` tables

---
name: linus-torvalds-skill
description: "[1-2 sentence description]"
metadata:
  author: "torvalds-skill pipeline"
  version: "1.0.0"
  tags:
    - code-review
    - reviewer-method
    - torvalds
---

# Linus Torvalds Review Method

> [2-3 sentence intro: what this skill is, corpus size, language-agnostic method]

## Reviewer Mindset
[5-7 core attitudes with principles and quotes]

## Review Triggers
[Comprehensive catalog grouped by semantic theme, NOT by category labels.
Organize into THREE hierarchical tiers:
- Level 1: Global Invariants (non-negotiables)
- Level 2: Structural Patterns (architecture-level)
- Level 3: Tactical Guidelines (implementation-level)
Each trigger must have:
- Type: invariant-true / invariant-false / precedence-rule / general-guideline
- What to look for: language-agnostic description
- Why it's a problem: underlying design principle
- Severity: reject / request-changes / nitpick
- Example: verbatim Torvalds quote
Cover at least 12 distinct themes with 3-6 triggers each.]

## Reasoning Protocol
[Instructions for the [REASON]→[ACT] workflow that prevents pattern-matching false
positives. Every finding must explain WHY before issuing the finding.]

## Precedence and Priorities
[Explicit hierarchy with explanations and quotes]

## Key Definitions
[Define: bug, hack, workaround, patch, non-negotiable, recoverable error, API contract. Structured bullet list, NOT a markdown table.]

## Voice and Tone
[How Torvalds phrases feedback with quotes]

## Anti-Patterns
[Anti-patterns Torvalds rejects, with the principle each violates. Structured list, NOT table.]

## Severity Calibration
[Use calibration stats to ground severity assignments. Format as nested bullets, NOT tables.]

## Severity Decision Tree
[Category-based decision procedure. Format as nested bullets, NOT tables.]

## Quick Reference Checklist
[15-20 concrete items grouped by theme]

Keep output between 4000-7000 words total. Complete ALL sections.
"""