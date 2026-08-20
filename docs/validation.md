# Validation: antirez/smallchat

The skill was tested on [antirez/smallchat](https://github.com/antirez/smallchat) (706 LOC, C) — a minimal TCP chat server. Six independent reviews were generated: each of the three models reviewed the codebase twice, once with the Torvalds skill loaded and once without (baseline).

## Validation Methodology

Each model reviews the same test codebase twice: once with the Torvalds skill loaded, once without any skill (baseline). The baseline shows the model's native code review capability, while the with-skill review shows how the skill enhances its review behavior. The comparison (`report/comparison.md`) shows the delta—how many additional findings the skill enables. This demonstrates the skill's concrete value: it's not just stylistic, it finds more issues.

To validate the skill's effectiveness, we ran six code reviews (two per model) against the same codebase. This approach tests:
1. **Consistency**: Do all models reach the same verdict on critical issues?
2. **Depth**: How does model choice affect finding severity and explanation quality?
3. **Practical utility**: Can the skill be applied to real-world codebases outside the kernel?

## Results
| Review | Mode | Model | Words | Findings |
|---|---|---|---|---|
| [`review-gpt-oss-120b.md`](../report/review-gpt-oss-120b.md) | with skill | gpt-oss-120b | 855 | 13 (2 CRIT) |
| [`review-baseline-gpt-oss-120b.md`](../report/review-baseline-gpt-oss-120b.md) | baseline | gpt-oss-120b | — | — |
| [`review-glm5.2.md`](../report/review-glm5.2.md) | with skill | glm5.2 | 3,069 | 18 (2 CRIT) |
| [`review-baseline-glm5.2.md`](../report/review-baseline-glm5.2.md) | baseline | glm5.2 | — | — |
| [`review-mistral.md`](../report/review-mistral.md) | with skill | mistral-small-4-119b | 1,527 | 8 (1 CRIT) |
| [`review-baseline-mistral.md`](../report/review-baseline-mistral.md) | baseline | mistral-small-4-119b | — | — |
| [`comparison.md`](../report/comparison.md) | — | — | ~2,000 | synthesis + delta |

## Key Findings

- All three models reached the same verdict: **FAIL**
- **glm5.2** found both accept-path memory corruption bugs (`acceptClient(-1)` and missing fd bounds check) that no other model caught
- **gpt-oss-120b** has the widest HIGH coverage (8 findings) — catches `socketSetNonBlockNoDelay` and `IB_MAX` that glm5.2 misses
- **Mistral** is the only model that flags the `/nick` embedded null-byte memory safety issue
- Run after expanding the interview corpus from 6 to 67 sources and wiring interview data into both pipelines
- Replicate with `bash report/run_review.sh`
