# Model Variants

Three model variants generate the skill and soul files. Each has different characteristics based on its training and reasoning style.

## Regeneration Commands

### gpt-oss-120b (balanced, recommended default)

```bash
# Skill generation
python -m torvalds_skill distill --model gpt-oss-120b --out linus-torvalds-skill/SKILL.md

# Soul generation
python -m torvalds_skill soul --model gpt-oss-120b --out soul/soul.md
```

**Token cost** (approximate):
- Skill: ~9,600 tokens input, ~9,600 tokens output (~$0.02-0.04)
- Soul: ~2,400 tokens input, ~1,900 tokens output (~$0.005)

**Wall-clock time**:
- Skill: 3-5 minutes
- Soul: 1-2 minutes

### glm5.2 (most detailed, reasoning model)

```bash
# Skill generation (mode determined by model profile)
python -m torvalds_skill distill --model glm5.2 --out linus-torvalds-skill/SKILL-GLM.md

# Soul generation
python -m torvalds_skill soul --model glm5.2 --out soul/soul-glm.md
```

**Token cost** (approximate):
- Skill: ~16,000 tokens input, ~12,800 tokens output (~$0.05-0.08)
- Soul: ~5,500 tokens input, ~5,500 tokens output (~$0.015)

**Wall-clock time**:
- Skill: 10-15 minutes (reasoning model, slow)
- Soul: 10-15 minutes

**Model-specific constraints**:
- See `src/torvalds_skill/profiles.py` for per-model `max_tokens`, `timeout`, and `distill_mode` settings
- GLM5.2 uses `distill_mode="single"` by default (1 LLM call instead of 15)
- Auto-chunking in review pipeline applies to all models when prompt > `profile.prompt_budget_chars`

### mistral-small-4-119b (concise, fast)

```bash
# Skill generation
python -m torvalds_skill distill --model mistral-small-4-119b --out linus-torvalds-skill/SKILL-Mistral.md

# Soul generation
python -m torvalds_skill soul --model mistral-small-4-119b --out soul/soul-mistral.md
```

**Token cost** (approximate):
- Skill: ~8,400 tokens input, ~8,400 tokens output (~$0.015-0.03)
- Soul: ~2,600 tokens input, ~2,600 tokens output (~$0.005)

**Wall-clock time**:
- Skill: 2-4 minutes
- Soul: 1-2 minutes

---

## Model Comparison

| Model | Skill words | Soul words | Strictness | Verbosity | Tonal aggression | Best for |
|---|---|---|---|---|---|---|
| gpt-oss-120b | 7,355 | 1,440 | Medium | Medium | Medium | Production code review (recommended default) |
| glm5.2 | 9,616 | 4,128 | High | High | High | Detailed reasoning, complex architecture reviews |
| mistral-small-4-119b | 6,357 | 1,970 | Medium | Medium | Medium | Quick checks, fast iteration cycles |

**Tradeoffs:**

- **gpt-oss-120b** (balanced, recommended default): Provides the best balance between thoroughness and speed. The skill captures all 13 review categories with clear triggers and the soul replicates Torvalds' tone without excessive aggression. Use this for most production code reviews.

- **glm5.2** (most detailed, reasoning model): Generates the most comprehensive skill with deeper explanations for each trigger and more nuanced escalation rules. The soul file includes detailed interlocutor modeling and Communication Style section with inline citations. Best for complex architecture reviews where reasoning matters more than speed. Longer generation time due to the larger output.

- **mistral-small-4-119b** (concise, fast): Produces compact skill files with YAML formatting for easier parsing. The soul is direct and efficient. Ideal for quick checks, CI integration, or when you need fast feedback without sacrificing accuracy.

All three models reach the same verdicts on critical issues (correctness bugs, API breaks, memory safety). The differences are in depth of explanation and generation speed, not fundamental review quality.

## What you get

**Skill files** (`linus-torvalds-skill/`) — the *rules*: triggers, precedence, definitions. Clean, no profanity.

| File | Model | Words | Notes |
|---|---|---|---|
| `SKILL.md` | gpt-oss-120b | ~7,355 | Default. Best balance. |
| `SKILL-GLM.md` | glm5.2 | ~9,616 | Reasoning model. Most thorough. |
| `SKILL-Mistral.md` | mistral-small-4-119b | ~6,357 | Fastest. |

**Soul files** (`soul/`) — the *persona*: identity, values, voice. **Includes profanity** — replicates Torvalds' actual tone, swearing only when a defect is dangerous or feedback is ignored.

| File | Model | Words |
|---|---|---|
| `soul.md` | gpt-oss-120b | ~1,440 |
| `soul-glm.md` | glm5.2 | ~4,128 |
| `soul-mistral.md` | mistral-small-4-119b | ~1,970 |

All skills and souls were generated with [regolo.ai](https://regolo.ai) using gpt-oss-120b (default), glm5.2, and mistral-small-4-119b.