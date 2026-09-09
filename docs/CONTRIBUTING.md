# Contributing to Torvalds Skill

This guide outlines the conventions and procedures for contributing to the project.

## Git Discipline

This project follows a strict local-only git workflow.

- **Local-only**: No `git push`, `git pull`, `git rebase`, or `git merge`. Humans push manually.
- **Commit Messages**: Must be terse and factual. Do NOT reference internal task numbers, plan phases, or scaffolding.

## Reproducibility & Generated Files

All `.md` artifacts in this repository are produced by scripts. **Do not edit them directly.** Edit the script that generates them, then re-run the generator. This keeps the project replicable: anyone can regenerate every artifact from source.

### Generated Artifacts and Their Generators

| Artifact | Generator | Regeneration command |
|----------|-----------|---------------------|
| `linus-torvalds-skill/SKILL.md` | `src/torvalds_skill/distill.py` | `python -m torvalds_skill distill --model gpt-oss-120b --out linus-torvalds-skill/SKILL.md` |
| `linus-torvalds-skill/SKILL-GLM.md` | `src/torvalds_skill/distill.py` | `python -m torvalds_skill distill --model glm5.2 --out linus-torvalds-skill/SKILL-GLM.md` |
| `linus-torvalds-skill/SKILL-Mistral.md` | `src/torvalds_skill/distill.py` | `python -m torvalds_skill distill --model mistral-small-4-119b --out linus-torvalds-skill/SKILL-Mistral.md` |
| `soul/soul.md` | `src/torvalds_skill/soul.py` | `python -m torvalds_skill soul --model gpt-oss-120b --out soul/soul.md` |
| `soul/soul-glm.md` | `src/torvalds_skill/soul.py` | `python -m torvalds_skill soul --model glm5.2 --out soul/soul-glm.md` |
| `soul/soul-mistral.md` | `src/torvalds_skill/soul.py` | `python -m torvalds_skill soul --model mistral-small-4-119b --out soul/soul-mistral.md` |
| `linus-torvalds-skill/SKILL-Qwen.md` | `src/torvalds_skill/distill.py` | `python -m torvalds_skill distill --model qwen3.8-27b --out linus-torvalds-skill/SKILL-Qwen.md` |
| `soul/soul-qwen.md` | `src/torvalds_skill/soul.py` | `python -m torvalds_skill soul --model qwen3.8-27b --out soul/soul-qwen.md` |
| `report/review-*.md` | `report/run_review.py` | `python3 report/run_review.py` |
| `report/comparison.md` | `report/build_comparison.py` | `python3 report/build_comparison.py` |
| `data/patterns.json` | `src/torvalds_skill/cluster.py` | `python -m torvalds_skill cluster` |
| `data/calibration.json` | `scripts/calibrate_interviews.py` | `python -m torvalds_skill calibrate-interviews` |

### How to Update Generated Files

When a generated file needs to change:
1. Identify the script that generates it (see table above).
2. Edit the script.
3. Re-run the generator.
4. Verify the output.

Manual edits are overwritten on the next run and break replicability.

## Source Files (Hand-Editable)

These files are not generated and should be edited directly:
- `src/torvalds_skill/*.py` — pipeline source code
- `scripts/*.py` — standalone scripts
- `report/run_review.py` — review orchestration
- `report/build_comparison.py` — comparison generator
- `data/interviews/*.md` — interview transcripts (source data)
- `README.md`, `docs/*.md` — documentation
- `todo.md` — task tracking
- `CHANGELOG.md` — changelog

## Running the Project

### Full Pipeline
To run the entire distillation pipeline:
```bash
python -m torvalds_skill run --sample 2000 --workers 10
```

To resume after a crash (checkpoints every 1000 emails):
```bash
python -m torvalds_skill extract --resume
```

### Verification Commands

Use these commands to verify the state of the project:

| Check | Command |
|-------|---------|
| Skill language-agnostic | `python3 scripts/verify_skill.py` |
| Comparison regenerates | `python3 report/build_comparison.py` |
| Review pipeline syntax | `python3 -m py_compile report/run_review.py` |
| Full review run | `python3 report/run_review.py --force` |
| Pipeline data valid | `python -m torvalds_skill validate` |
