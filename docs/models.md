# Model Variants

Three model variants generate the skill and soul files. Each has different characteristics based on its training and reasoning style.

## Model Comparison

| Model | Skill words | Soul words | Strictness | Verbosity | Tonal aggression | Best for |
|---|---|---|---|---|---|---|
| gpt-oss-120b | 7,474 | 1,440 | Medium | Medium | Medium | Production code review (recommended default) |
| glm5.2 | 10,103 | 4,128 | High | High | High | Detailed reasoning, complex architecture reviews |
| mistral-small-4-119b | 7,853 | 1,970 | Medium | Medium | Medium | Quick checks, fast iteration cycles |

**Tradeoffs:**

- **gpt-oss-120b** (balanced, recommended default): Provides the best balance between thoroughness and speed. The skill captures all 13 review categories with clear triggers and the soul replicates Torvalds' tone without excessive aggression. Use this for most production code reviews.

- **glm5.2** (most detailed, reasoning model): Generates the most comprehensive skill with deeper explanations for each trigger and more nuanced escalation rules. The soul file includes detailed interlocutor modeling and Communication Style section with inline citations. Best for complex architecture reviews where reasoning matters more than speed. Longer generation time due to the larger output.

- **mistral-small-4-119b** (concise, fast): Produces compact skill files with YAML formatting for easier parsing. The soul is direct and efficient. Ideal for quick checks, CI integration, or when you need fast feedback without sacrificing accuracy.

All three models reach the same verdicts on critical issues (correctness bugs, API breaks, memory safety). The differences are in depth of explanation and generation speed, not fundamental review quality.

## What you get

**Skill files** (`linus-torvalds-skill/`) — the *rules*: triggers, precedence, definitions. Clean, no profanity.

| File | Model | Words | Notes |
|---|---|---|---|
| `SKILL.md` | gpt-oss-120b | ~7,474 | Default. Best balance. |
| `SKILL-GLM.md` | glm5.2 | ~10,103 | Reasoning model. Most thorough. |
| `SKILL-Mistral.md` | mistral-small-4-119b | ~7,853 | Fastest. |

**Soul files** (`soul/`) — the *persona*: identity, values, voice. **Includes profanity** — replicates Torvalds' actual tone, swearing only when a defect is dangerous or feedback is ignored.

| File | Model | Words |
|---|---|---|
| `soul.md` | gpt-oss-120b | ~1,440 |
| `soul-glm.md` | glm5.2 | ~4,128 |
| `soul-mistral.md` | mistral-small-4-119b | ~1,970 |

All skills and souls were generated with [regolo.ai](https://regolo.ai) using gpt-oss-120b (default), glm5.2, and mistral-small-4-119b.