# Model Divergence Analysis

Per-category analysis of what each model kept, dropped, or re-weighted from the same corpus (38,293 review moves).

## Shared Core (All Four Models Agree)

### Reviewer Mindsets
All four variants capture the same 7 core attitudes:
1. **Data-structure first** — "Good programmers worry about data structures, not code"
2. **Special-case elimination** — "Eliminate the special case so the edge case has nowhere to hide"
3. **Talk is cheap, show me the code** — Concrete patches over speculation
4. **Protect existing users** — "I like boring... no features that break machines for millions"
5. **Correctness > Performance** — "If it's a choice between fast and correct, we'll take correct every time"
6. **Trust is structured** — Maintainer trees, not blind trust
7. **Security is bugs** — Security issues are ordinary bugs, not a separate category

### Level 1 Invariants (Non-Negotiables)
All four variants include these fatal flaws:
- **Fatal assertions for recoverable errors** — `panic()`/`BUG_ON()` on user input
- **Breaking public API/ABI without migration** — "We don't change UI. That is ALWAYS a bug"
- **Unvalidated boundary crossings** — Copying from user space without bounds checks
- **Dead code that holds locks** — `goto err` while ctx locked
- **Stack pointer escapes** — Returning pointers to local variables

### Precedence Chain
All four variants enforce: **Correctness > Performance > Complexity > Style**

---

## Model-Specific Emphases

### gpt-oss-120b (`SKILL.md`) — Balanced, Comprehensive

**Structure**: 10 thematic groupings (A-J) with 3-6 triggers each

**Unique emphases**:
- **Theme J: Process & Governance** — Out-of-tree code dictating core changes, merging without testing evidence
- **Cross-File Review section** — Explicit checklist for header vs implementation, caller vs callee contracts
- **Decision Cards** — 6 detailed cards with "when it does NOT apply" clauses
- **Severity Calibration** — Corpus-wide statistics with category breakdowns (reject/request-changes/nitpick percentages)

**What it dropped**:
- Less detailed on memory lifetime specifics (refcounting rules are compressed)
- No explicit "Root Cause Over Symptom Treatment" theme

**Severity calibration**:
- API-stability: 37.9% reject (highest)
- Correctness: 28.7% reject
- Style: 12.6% reject, 35.5% nitpick

---

### glm5.2 (`SKILL-GLM.md`) — Most Detailed, Reasoning-Heavy

**Structure**: 15 numbered themes, each with 3-4 detailed triggers

**Unique emphases**:
- **Theme 6: Root Cause Over Symptom Treatment** — "The fix must be applied at the point where bad data is produced, not at every consumption site"
- **Theme 7: Interface Honesty and Misuse Resistance** — "An interface that lies corrupts every downstream consumer"
- **Theme 9: Trust Delegation and Review Structure** — "His real job is curating who he trusts, not auditing every line"
- **Theme 13: Testing and Verification** — Detailed triggers for unverified code, incomplete test coverage, missing reproducers
- **Theme 14: Performance Discipline** — "TINSTAAFL" (There Is No Such Thing As A Free Lunch), controlled measurement requirements

**What it dropped**:
- No explicit "Process & Governance" theme (merged into other categories)
- No Decision Cards section (principles are embedded in triggers)

**Severity calibration**:
- More aggressive on concurrency: lock upgrade = reject (vs request-changes in others)
- More lenient on style: fewer nitpick assignments
- Higher reject rate for "speculative generality" (Theme 11)

**Notable detail**:
- GLM's triggers are 2-3x longer, with more verbatim quotes and explicit "why it's a problem" explanations
- Includes a "Critical" warning: "Never issue a finding based on surface-level pattern matching"

---

### mistral-small-4-119b (`SKILL-Mistral.md`) — Concise, YAML-Formatted

**Structure**: 3 tiers (Level 1/2/3) with thematic subsections

**Unique emphases**:
- **YAML frontmatter** — Machine-readable metadata (name, description, tags)
- **Compact trigger format** — Bullet points instead of detailed paragraphs
- **Level 3: Tactical Guidelines** — Naming, comments, code organization (missing in other variants)
- **Anti-Patterns section** — 10 anti-patterns with governing principles and quotes

**What it dropped**:
- No Decision Cards section
- No Severity Calibration statistics (only qualitative patterns)
- No Cross-File Review section
- Compressed Reasoning Protocol (2 steps vs 6 steps in GLM)

**Severity calibration**:
- More lenient on error-handling: "fatal assertion" = request-changes (vs reject in gpt-oss)
- Style issues: 35.5% nitpick (same as gpt-oss)
- Memory-safety: 28.3% reject (same as gpt-oss)

**Notable detail**:
- YAML formatting makes it easier to parse programmatically
- Shortest word count (see [docs/models.md](models.md) for current values) but covers all core triggers
- Uses "invariant-false" and "invariant-true" consistently

### qwen3.8-27b (`SKILL-Qwen.md`) — Balanced, Practical

**Structure**: 8 thematic sections with 3-5 triggers each

**Unique emphases**:
- **Practical examples** — Each trigger includes a concrete code example
- **Severity decision tree** — Flowchart-style guidance for edge cases
- **Cross-reference table** — Links related triggers across categories

**What it dropped**:
- No explicit "Process & Governance" theme
- Less detailed on severity calibration statistics

**Severity calibration**:
- Balanced approach: aligns with gpt-oss on most categories
- Slightly more lenient on style issues

**Notable detail**:
- Well-structured for both human reading and programmatic parsing
- Good middle ground between gpt-oss comprehensiveness and mistral conciseness

---

## Severity Calibration Drift

Same triggers, different severity assignments:

| Trigger | gpt-oss-120b | glm5.2 | mistral | qwen3.8-27b |
|---|---|---|---|
| Fatal assertion on user input | reject | reject | request-changes |
| Breaking public API | reject | reject | request-changes |
| Lock upgrade (read → write) | reject | reject | reject |
| Exposing internal structs | request-changes | request-changes | request-changes |
| Magic constants | request-changes | reject | request-changes | request-changes |
| Duplicated logic | nitpick | request-changes | request-changes |
| Missing commit rationale | request-changes | request-changes | request-changes |
| Unvalidated boundary crossing | reject | reject | reject | reject |

**Key observations**:
- **qwen3.8-27b is balanced** — Aligns with gpt-oss on most categories, practical for general use
- **GLM is most aggressive** — Higher reject rate for complexity issues (magic constants, speculative generality)
- **Mistral is most lenient** — Downgrades "fatal assertion" from reject to request-changes
- **gpt-oss is balanced** — Splits the difference, aligns with corpus statistics

---

## Structural Divergence

| Aspect | gpt-oss-120b | glm5.2 | mistral |
|---|---|---|---|
| **Sections** | 12 major sections | 10 major sections | 9 major sections |
| **Themes** | 10 (A-J) | 15 (numbered) | 6 (tiered) |
| **Triggers** | ~45 detailed | ~55 detailed | ~35 compact | ~40 balanced |
| **Decision Cards** | 6 cards | 0 cards | 7 cards |
| **Anti-Patterns** | 13 patterns | 0 patterns | 10 patterns |
| **Severity Stats** | Full table | Embedded | Qualitative only |
| **Cross-File Review** | Yes | No | Yes | Yes |

---

## What This Means for Users

1. **Pick gpt-oss-120b** if you want the recommended default — balanced coverage, readable, aligns with corpus statistics

2. **Pick glm5.2** if you need deep reasoning — complex architecture reviews, detailed explanations, aggressive on complexity debt

3. **Pick mistral** if you need speed or small context — CI integration, quick checks, YAML parsing

4. **Pick qwen3.8-27b** if you want balanced practicality — good for general reviews, clear examples, structured format

**All four variants will catch the same critical bugs** (memory safety, concurrency, API breaks). The differences are in:
- Depth of explanation
- Severity calibration for edge cases
- Structural organization (affects prompt engineering)

---

## Methodology Note

This analysis compares the four skill files generated from the **same corpus** (38,293 moves, 350 sampled patterns from `data/patterns.json`) using the **same pipeline** (`distill.py`) but **four different LLMs**. The divergence is not a bug — it's evidence of how much the generation model shapes the distillation output.

To regenerate and verify, see [docs/CONTRIBUTING.md](CONTRIBUTING.md) for the canonical regeneration commands.
