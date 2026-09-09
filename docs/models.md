# Model Variants
Four model variants generate the skill and soul files. Each has different characteristics based on its training and reasoning style.

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
| gpt-oss-120b | 6,780 | 2,448 | Medium | Medium | Medium | Production code review (recommended default) |
| glm5.2 | 8,890 | 7,155 | High | High | High | Detailed reasoning, complex architecture reviews |
| mistral-small-4-119b | 5,410 | 3,476 | Medium | Medium | Medium | Quick checks, fast iteration cycles |
| qwen3.8-27b | 8,473 | 6,990 | Medium | Medium | Medium | Balanced, practical reviews |

**Tradeoffs:**

- **gpt-oss-120b** (balanced, recommended default): Provides the best balance between thoroughness and speed. The skill captures all 13 review categories with clear triggers and the soul replicates Torvalds' tone without excessive aggression. Use this for most production code reviews.

- **glm5.2** (most detailed, reasoning model): Generates the most comprehensive skill with deeper explanations for each trigger and more nuanced escalation rules. The soul file includes detailed interlocutor modeling and Communication Style section with inline citations. Best for complex architecture reviews where reasoning matters more than speed. Longer generation time due to the larger output.

- **mistral-small-4-119b** (concise, fast): Produces compact skill files with YAML formatting for easier parsing. The soul is direct and efficient. Ideal for quick checks, CI integration, or when you need fast feedback without sacrificing accuracy.

- **qwen3.8-27b** (balanced, practical): Produces well-structured skill files with clear triggers and practical examples. The soul is balanced and professional. Good for general code reviews where clarity and completeness matter.

All four models reach the same verdicts on critical issues (correctness bugs, API breaks, memory safety). The differences are in depth of explanation and generation speed, not fundamental review quality.

## What you get

**Skill files** (`linus-torvalds-skill/`) — the *rules*: triggers, precedence, definitions. Clean, no profanity.

| File | Model | Words | Notes |
|---|---|---|---|
| `SKILL.md` | gpt-oss-120b | ~6,780 | Default. Best balance. |
| `SKILL-GLM.md` | glm5.2 | ~8,890 | Reasoning model. Most thorough. |
| `SKILL-Mistral.md` | mistral-small-4-119b | ~5,410 | Fastest. |
| `SKILL-Qwen.md` | qwen3.8-27b | ~8,473 | Balanced. |

**Soul files** (`soul/`) — the *persona*: identity, values, voice. **Includes profanity** — replicates Torvalds' actual tone, swearing only when a defect is dangerous or feedback is ignored.

| File | Model | Words |
|---|---|---|
| `soul.md` | gpt-oss-120b | ~2,448 |
| `soul-glm.md` | glm5.2 | ~7,155 |
| `soul-mistral.md` | mistral-small-4-119b | ~3,476 |
| `soul-qwen.md` | qwen3.8-27b | ~6,990 |

All skills and souls were generated with [regolo.ai](https://regolo.ai) using gpt-oss-120b (default), glm5.2, mistral-small-4-119b, and qwen3.8-27b.

## Review-phase costs

The review pipeline (`report/run_review.py`) performs 8 LLM calls per full comparison (4 models × 2 arms: with-skill + baseline). Each review processes the codebase in chunks, typically 3-5 chunks depending on file size. Based on recent metrics.jsonl data:

| Model | Avg duration (s) | Est. cost per review |
|---|---|---|
| gpt-oss-120b | ~40-60 | ~$0.02-0.04 |
| glm5.2 | ~500-1000 | ~$0.10-0.20 |
| mistral-small-4-119b | ~15-30 | ~$0.01-0.02 |
| qwen3.8-27b | ~20-40 | ~$0.015-0.03 |

**Total for 4-model comparison**: ~$0.35-0.65, 20-40 minutes wall-clock time.

Cost estimation method: Parse `report/metrics.jsonl` for recent successful reviews, compute average tokens from word_count × 1.3 (avg tokens/word ratio), apply model pricing from regolo.ai. Keep .env cache enabled to avoid re-reviewing unchanged codebases.

## End-to-End Pipeline Costs

Full regeneration from raw mbox (not including data download):

| Phase | LLM calls | Est. cost | Wall-clock |
|---|---|---|---|
| classify | 0 (rule-based) | $0 | 5 min |
| extract (2000 emails) | 2000 | $2-4 | 2-3 hours |
| cluster | 0 (deterministic) | $0 | 1 min |
| calibrate | 0 (deterministic) | $0 | 1 min |
| distill | 1 (single-call) | $0.02-0.08 | 3-15 min |
| soul | 1 | $0.005-0.015 | 1-15 min |
| review (8 reviews) | 8 | $0.25-0.50 | 15-30 min |
| **Total** | ~2022 | **$2.30-4.60** | **3-4 hours** |

**Cost formula**: extract dominates at ~$0.001-0.002 per email. Distill and soul are negligible (<2% of total). Review phase is ~10% of total cost.

**Budget optimization**: Use `CACHE_ENABLED=1` (default) to skip re-extraction via the unified cache. Cache expires after `CACHE_TTL_HOURS=168h` (7d). Download pre-built data from releases to skip extract phase entirely (~$3-4 savings).
