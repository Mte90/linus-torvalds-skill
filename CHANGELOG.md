# Changelog

All changes to the torvalds-skill project, organized by day.

## 2026-08-21

- **Documentation:** Finalized the README with a Quick Start guide, an environment variable table, a documentation index, and the CC0 license note — making the project usable in under 60 seconds for a new reader.
- **Report:** Rebuilt `build_comparison.py` to generate the full comparison automatically — consensus matrix, accuracy scoring, severity-disagreement analysis, trigger-coverage summary, and a data-driven qualitative analysis section — replacing the placeholder that was overwritten on every run.
- **Report:** Fixed the consensus-matrix grouping: added `normalize_filename()` to collapse `server.c`, `smallchat-server.c`, and `unspecified` into one canonical key, and taught the mistral parser to track `### filename.c` section headings so findings retain file context. The matrix now shows real cross-model overlaps (3/3 agree on the fd-bounds and nickname null-termination bugs).
- **Report:** Fixed the baseline parser to accept both `###` and `####` severity headings, and made the field regexes tolerant of `**Location:**` vs `**Location**:` colon placement — gpt-oss-120b and mistral had switched to 3-hash headings, causing zero findings to be extracted.
- **Report:** Added honest skill-vs-baseline analysis: the "Skill Added Value" column now reports net critical impact (`skill_only_critical - baseline_only_critical`) instead of a yes/no, plus a tradeoff table and per-model read bullets. The verdict scoring penalizes baseline-only critical findings (`confirmed + skill_only - baseline_only - disagreements`).
- **Report:** Made `build_comparison.py` tolerant of missing baseline files — passes `None` to `compare_skill_vs_baseline` which renders "N/A" instead of zeroing out the table, so the script no longer crashes or overwrites good data when baselines are absent.
- **Pipeline:** Rewrote `run_review.sh` into a self-contained pipeline: generates all six reviews (three baseline + three with-skill), calls `build_comparison.py` to produce `comparison.md`, then deletes the intermediate baseline files after the comparison is safely written.
- **Pipeline:** Removed the `build_comparison.sh` wrapper and pointed all docs and scripts at `python3 report/build_comparison.py` directly.
- **Pipeline:** Built a chunked, resumable review pipeline for GLM5.2 — splits the review into one call per source file (five chunks) plus a summary call, writes each chunk to `report/chunks/`, skips existing chunks on retry, and merges into `review-glm5.2.md`. This fixed the repeated GLM5.2 API timeouts caused by feeding all five source files in a single call.
- **Pipeline:** Removed the soul file from GLM5.2 review prompts — the 10K-word skill plus the 5K-word soul exceeded GLM5.2's context budget and caused API aborts. gpt-oss-120b and mistral reviews also regenerated without the soul for consistency.
- **Report:** Final three-model comparison regenerated with real baseline data. Results: gpt-oss-120b wins (score 7, +1 net critical — baseline found nothing, skill unlocked 14 findings); glm5.2 follows (score 6, -1 net critical); mistral last (score 0, -1 net critical). The skill helps gpt-oss-120b but narrows focus too aggressively for glm5.2 and mistral, suppressing one critical finding each.

## 2026-08-20

Final assembly day: generated all user artifacts (skill + soul), wired the CLI, wrote the reference docs, and built the review infrastructure.

- **Pipeline:** Wired all stages into a single CLI driving the full mbox-to-skill chain, with one subcommand per stage and flags for resume, workers, model, and output.
- **Pipeline:** Finalized the distillation stage — detects and recovers from output truncation with a fallback model chain, adds streaming mode for reasoning models to keep connections alive during long thinking phases, injects severity statistics, and strips forbidden C/kernel terms outside quotes.
- **Skill:** Generated three skill variants from the same patterns and calibration — a balanced default, the most detailed (reasoning model), and the fastest — each covering mindset, triggers, precedence, definitions, voice, severity, and a checklist.
- **Soul:** Generated three persona variants defining the AI's identity, values, and voice rather than rules; added a soul explainer and a synthesis document.
- **Documentation:** Wrote the three reference docs — pipeline architecture, model variants and tradeoffs, and the validation methodology.
- **Report:** Added review infrastructure — scripts to run a model against a codebase with skill and soul, build a cross-model comparison, and per-model reports.
- **Test:** Added a skill-quality verifier checking required sections, quotes, placeholders, forbidden terms, and category and severity coverage.

## 2026-08-19

Intensive build day: interview pipeline, data models, validation, checksums, taxonomy cleanup, and the first three-model comparison.

- **Pipeline:** Built the interview pipeline, treating interviews like emails — rule-based classification keeps only passages where Linus discusses code review, LLM extraction with checkpointing, stratified sampling fuses interview moves with email moves into a unified patterns file, and interview calibration. The interview corpus grew from 6 to 67 sources.
- **Pipeline:** Defined shared data types for emails, review moves, and patterns, plus streaming iterators that process JSONL line-by-line without loading corpora into memory, preventing OOM on large corpora.
- **Pipeline:** Made stratified sampling deterministic with a fixed seed, distributing samples across category, severity, and year uniformly to avoid recency bias — re-running produces identical output.
- **Pipeline:** Added JSON schema validation between stages that fails immediately on corrupt output — missing fields, invalid categories, or coverage gaps.
- **Pipeline:** Added SHA256 checksums for intermediate files with generate, verify, and update commands to detect silent corruption before the next stage runs.
- **Refactoring:** Fixed vocabulary drift and a field-swap bug in the moves file — remapped non-canonical categories to the standard taxonomy; supports dry-run with automatic backup.
- **Report:** First three-model comparison on a real C codebase — all three models agreed on FAIL; synthesized shared defects and single-model findings with per-model metrics.
- **Documentation:** Added a 17-task improvement plan across five priorities with dependencies and regeneration gates.
- **Configuration:** Added the Python package configuration.

## 2026-08-18

- **Pipeline:** Added LLM extraction of interlocutor context per email — relationship type, tone shift, and delegation signal — so the review voice can be modulated by audience.
- **Pipeline:** Added context-dimension extraction (thread phase, urgency, stakes, risk), partly rule-based and partly LLM, to modulate tone by discussion context.
- **Pipeline:** Added fetching of interview transcripts from configured sources; downloaded the first six.

## 2026-08-12

- **Pipeline:** Added rule-based severity calibration (no LLM) computing per-category reject rates and temporal trends from the corpus, anchoring generated severity to Torvalds' real distribution rather than the LLM's judgment.

## 2026-08-04

- **Pipeline:** Added a rule-based classifier (no LLM) separating real code reviews from administrative messages, keeping the first stage cost-free.
- **Pipeline:** Added LLM extraction of review moves — one call per email — capturing trigger, abstract principle, Torvalds' actual words, severity, and category, with jittered retry on rate-limit and server errors.
- **Configuration:** Persisted message IDs that produced zero moves so resume skips them, saving thousands of API calls.
- **Configuration:** Released the repository to the public domain under CC0 1.0.
- **Test:** Added coverage for stratified sampling and skip-list handling.

## 2026-08-03

Kickoff day: raw data fetch and package scaffolding.

- **Pipeline:** Downloaded all of Torvalds' LKML emails (2002–2026, ~31K messages, ~192 MB) via NNTP with a resumable two-phase fetch — discovery then message download — and reconnect handling.
- **Pipeline:** Converted the mbox archive to structured JSONL and verified its integrity (separators, message count, parseable headers).
- **Pipeline:** Generated a provenance manifest with source, counts, and checksums.
- **Configuration:** Loaded LLM credentials and endpoints from the local environment and wired the package entry point.
