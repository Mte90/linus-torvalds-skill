# Validation: antirez/smallchat

The skill was tested on [antirez/smallchat](https://github.com/antirez/smallchat) (706 LOC, C) — a minimal TCP chat server. Six independent reviews were generated: each of the three models reviewed the codebase twice, once with the Torvalds skill loaded and once without (baseline).

## Validation Methodology

Each model reviews the same test codebase twice: once with the Torvalds skill loaded, once without any skill (baseline). The baseline shows the model's native code review capability, while the with-skill review shows how the skill enhances its review behavior.

To validate the skill's effectiveness, we ran six code reviews (two per model) against the same codebase. This approach tests:
1. **Consistency**: Do all models reach the same verdict on critical issues?
2. **Depth**: How does model choice affect finding severity and explanation quality?
3. **Practical utility**: Can the skill be applied to real-world codebases outside the kernel?

## Results

The authoritative results are in [`report/comparison.md`](../report/comparison.md), which cross-references findings at the issue level — not just counts. It includes the stakeholder scorecard, finding consensus matrix, severity disagreement table, with-skill vs baseline comparison, per-model bug comparison, and verdict.

The six review files:

| Review | Mode | Model |
|---|---|---|
| [`review-gpt-oss-120b.md`](../report/review-gpt-oss-120b.md) | with skill | gpt-oss-120b |
| [`review-baseline-gpt-oss-120b.md`](../report/baseline/review-baseline-gpt-oss-120b.md) | baseline | gpt-oss-120b |
| [`review-glm5.2.md`](../report/review-glm5.2.md) | with skill | glm5.2 |
| [`review-baseline-glm5.2.md`](../report/baseline/review-baseline-glm5.2.md) | baseline | glm5.2 |
| [`review-mistral-small-4-119b.md`](../report/review-mistral-small-4-119b.md) | with skill | mistral-small-4-119b |
| [`review-baseline-mistral-small-4-119b.md`](../report/baseline/review-baseline-mistral-small-4-119b.md) | baseline | mistral-small-4-119b |

## Key Findings

- All three models reached the same verdict: **FAIL** (the codebase has real bugs)
- **glm5.2** gained +2 net critical findings with the skill (4 new, 2 lost) — the only model where the skill added net critical value
- **gpt-oss-120b** and **mistral** showed net negative critical coverage — the skill narrowed focus too aggressively and suppressed criticals the baseline caught
- The trigger-coverage column in `comparison.md` distinguishes skill gaps (trigger exists, model didn't fire it) from out-of-scope bugs (no trigger covers that type)

Replicate with `python3 report/run_review.py && python3 report/build_comparison.py`.

