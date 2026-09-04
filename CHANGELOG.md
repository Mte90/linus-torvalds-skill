# Changelog

All changes to the torvalds-skill project, organized by day.

## 2026-09-04

- **Chore (ci):** Deleted `.github/workflows/ci.yml` (workflow never ran on main; project is local-only). Dev checks stay in `pyproject.toml [dev]`; secret scan via pre-commit gitleaks.
- **Feature (metrics):** `report/trigger_patterns.py` extracts 57/44/65 triggers across variants; title+description matching; baseline prompt symmetric (two-pass); trigger-format contract shared with `verify_skill.py`; benchmark-coverage test (43/43); comparison regenerated with real coverage.
- **Refactor (prompts):** Prompt blocks componentized once in `distill_prompts.py` (651 lines); `MODEL_SEVERITY_BIAS` removed from prompt path; frontmatter traceability (6 fields, verified); repair grounded in `calibration.json`; doc counts unified at 350 patterns.
- **Refactor (profiles):** New `src/torvalds_skill/profiles.py` — `get_profile()` is the only model-name matcher; auto-chunking by prompt budget for both arms (CHUNKED_MODELS deleted); unified `max_tokens`; `distill.py` 1074→844 lines via `distill_data.py`.
- **Cleanup:** `_detect_truncation` takes explicit `doc_type`; fallback chain + workers + tokens from profile.
- **Docs (agents):** `AGENTS.md` gains Local Checks section + 5 rule bullets (model matching, prompt centralization, trigger contract, validation symmetry, generated stats).

## 2026-09-03

- **Feature (triage):** Enforced two-pass review triage in `report/run_review.py` — Pass 1 reports correctness/memory-safety only, Pass 2 may report style/build only for files with zero Pass-1 findings (cap 2/file). Findings carry `Pass: 1|2` labels and the chunked-merge step drops Pass-2 findings wherever Pass-1 exists, so precedence is structural instead of decorative. 10 new tests. Full suite 897 passed.
- **Feature (distill):** Severity-weighted distill sampling in `src/torvalds_skill/distill.py` + `distill_prompts.py` (reject 3x, request-changes 2x, nitpick 1x; nitpick-sourced triggers capped ~15%), binding per-category severity quotas in the prompt, and a "Never block on" non-fire section (build trivia). `verify_skill.py --strict` now fails trivia-blessing triggers and over-style (>20%) skills.
- **Feature (report):** Focus gate in `report/build_comparison.py` + `comparison_render.py` — core-vs-trivia classifier, per-model CORE% rows with FOCUS DRIFT (<50% core) and CRITICAL FOCUS FAILURE gates; renamed misleading "out of scope" to "unmatched".
- **Feature (calibration):** `rebalance_severities()` now returns a delta report (before/after, share movement, relabeled ids), emits SEVERITY REBALANCE ALERT past 10pts movement, and supports `strict=True` to raise instead of silently rewriting.
- **Review (rereview):** Regenerated all 3 skills (weighted sampling, quotas, non-fire list) and re-ran SmallChat with two-pass triage + focus gate. All models focused (83-100% CORE, trivia gone). Verdicts: gpt-oss neutral (1 found/1 lost), mistral +12 (13 CRITICAL vs baseline 1 — likely quota-driven inflation, benchmark recall best at 18.6%), glm5.2 -4 (0 CRITICAL vs baseline 4 — severity downgrade, not focus drift). Benchmark: gpt P83.3/R11.6, mistral P36.4/R18.6, glm P9.1/R2.3. Baseline variance (glm 9→27 findings across runs) still dominates comparisons.

## 2026-09-01

- **Security:** Removed the last hardcoded Regolo API key (`sk-1ZXgFKoLcq8oZfKozQIpew`) from `src/torvalds_skill/config.py`, `report/llm_review.py`, and `docs/ARCHITECTURE.md`. All credentials now come exclusively from environment variables. Added `.env.example` as the configuration template and a `No Committed Secrets` rule to `AGENTS.md` documenting the env-var contract (`OPENAI_API_KEY` / `REGOLO_API_KEY` / `LLM_API_KEY` for the key; `OPENAI_BASE_URL` / `LLM_HOST` for the endpoint) and the `git filter-repo` purge procedure if a key is ever committed.
- **Bugfix (config):** Fixed OpenAI-compatibility precedence bug in `config.py` — `REGOLO_API_KEY` and `LLM_HOST` were checked first in the `or` chain, so when `.env` set them, shell-exported `OPENAI_API_KEY` / `OPENAI_BASE_URL` were never read. Reordered precedence so `OPENAI_*` vars take priority, then `REGOLO_*` / `LLM_*`, then the Regolo default. Verified both directions: OpenAI env vars override `.env`, and Regolo fallback still works when no OpenAI vars are set. Full suite 720 passed.

- **Feature (calibration):** Extended severity rebalancer with promotion logic — the inverse of the existing demotion ladder. When a severity is under-represented relative to the corpus target, triggers from the next-lower rung are promoted up (nitpick → request-changes → reject), preferring the hardest-language triggers first. The promotion pass iterates until stable so a trigger can climb multiple rungs in one rebalance. This fixes the mistral skill's nitpick excess (17.1% → 8.6%, target 9.3%) that demotion alone couldn't address. Added 3 promotion tests (`test_promotes_over_represented_nitpick`, `test_promotion_prefers_hard_language`, `test_demotion_then_promotion`). Re-ran the rebalancer on all three skill files: gpt-oss-120b and GLM5.2 unchanged (already at target), mistral 3 nitpicks promoted to request-changes. Full suite 720 passed.
- **Bugfix (comparison):** Fixed three matching bugs in `report/build_comparison.py` that produced incorrect overlap metrics. (1) `_title_similarity()` replaced `difflib.SequenceMatcher` (character-sequence) with token-based Jaccard similarity on content words — the old method scored 0.35-0.43 for *different* bugs sharing domain terms like "createClient", inflating false matches. (2) Added `_dedup_findings()` to collapse duplicate findings within a single review (draft headings without line numbers followed by full report headings for the same bug were double-counted). (3) `_parse_location()` now handles bare filenames (`smallchat-server.c` without `:line`) so draft findings get `file` set, enabling dedup. Added 2 regression tests (`test_dedup_collapses_draft_and_full_report_duplicates`, `test_dedup_preserves_different_bugs_in_same_file`). Full suite 707 passed. Rebuilt `report/comparison.md` — GLM5.2 baseline CRITICAL corrected from 6 (duplicate-counted) to 4 distinct bugs; all three models now show net positive critical impact.
- **Feature (calibration):** Added model-agnostic post-generation severity rebalancer (`rebalance_severities()` in `distill_sanitize.py`) that adjusts trigger severity labels to match the corpus distribution from `calibration.json` (reject ≈ 33%, request-changes ≈ 58%, nitpick ≈ 9%). The rebalancer parses trigger blocks, scores each trigger's language softness, and demotes over-represented severities down the ladder (reject → request-changes → nitpick), preferring the softest-worded triggers first. Handles three skill format variants: `**Severity:**`/`**Severity**:` colon placement, `- ` prefix presence, and non-breaking hyphen (U+2011) in `request‑changes`. Normalizes severity aliases (`request` → `request-changes`, `critical` → `reject`, etc.) for cross-model consistency. Hooked into `distill.py` after `sanitize_skill()`. Applied to all three existing skill files: gpt-oss-120b (13 relabelled), GLM5.2 (5 relabelled), mistral (6 relabelled). Full suite 717 passed.
- **Feature (cluster):** Replaced lexical Jaccard similarity in `cluster.py` with TF-IDF + cosine similarity. Pure-Python implementation (`_tokenize`, `_compute_tf/idf`, `_cosine_similarity`, `TFIDFClustering` class) with no heavy dependencies. Reduces fragmentation from 7,434 Jaccard clusters to 53-60% fewer coherent clusters on sample data. 27 new tests. Full suite 747 passed.
- **Feature (report):** Added trigger effectiveness metrics to `report/build_comparison.py` + `report/comparison_render.py` — `analyze_trigger_effectiveness()` computes per-trigger fires, true positives, precision and recall by fuzzy-matching skill findings against baseline. New "Trigger Effectiveness" section in `comparison.md` per model. 4 new tests. Full suite 747 passed.
- **Feature (verify):** Added automated skill quality scoring to `scripts/verify_skill.py` — `score_skill_quality()` returns 0-100 across four dimensions: trigger diversity (0-25), severity distribution vs `calibration.json` (0-25), language-agnosticism (0-25), section coverage (0-25). New `--score` CLI flag prints formatted report. SKILL.md scores 95/100. 39 new tests. Full suite 747 passed.
- **Feature (extract):** Added rule-based severity consistency validation to `src/torvalds_skill/extract.py` — `_validate_severity_consistency()` flags mismatches between severity label and language (hard words like "crash"/"broken" vs soft words like "consider"/"perhaps"). Logs warnings and increments `severity_warnings` counter without rejecting moves. 16 new tests. Full suite 763 passed.
- **Feature (distill):** Added model-specific severity calibration to `src/torvalds_skill/distill.py` — `MODEL_SEVERITY_BIAS` dict + `_format_model_calibration_note()` injects per-model bias guidance into the distill prompt (glm5.2 over-rates → downgrade borderline, mistral under-rates → upgrade borderline, gpt-oss-120b balanced). Wired through `_format_calibration_for_prompt(model)` → `_synthesize_skill()` / `_distill_single_call()`. 11 new tests. Full suite 774 passed.
- **Feature (extract):** Added batched LLM extraction with retry to `src/torvalds_skill/extract.py` + `extract_async.py` — `--batch-size` (default 1, sequential) and `--batch-retry` flags, `BATCH_SYSTEM_PROMPT`, `_parse_batch_response()` with length validation and fallback to sequential on failure. Preserves checkpoint/resume semantics. 12 new tests. Full suite 786 passed.
- **Feature (benchmark):** Added ground-truth benchmark dataset `data/benchmark.jsonl` (43 bugs, SC-001…SC-043, 8 files, 3 severities, 10 categories) derived from SmallChat consensus findings, plus `data/benchmark.schema.json` and `scripts/validate_benchmark.py` CLI validator. Enables real precision/recall measurement instead of baseline-as-proxy. 21 new tests. Full suite 813 passed.
- **Feature (test):** Added end-to-end pipeline integration test `tests/test_pipeline_e2e.py` (6 tests: classify→extract, extract→cluster, cluster→distill→verify, severity-consistency flagging, batch mode, malformed-batch fallback). Uses `tmp_path` isolation and mocked LLM calls, no network. Full suite 813 passed.

## 2026-09-02

- **Fix (distill):** Tightened `MODEL_SEVERITY_BIAS` for `glm5.2` in `src/torvalds_skill/distill.py` — previous guidance "downgrade borderline" suppressed 3 CRITICAL error-handling bugs (`SIGPIPE`, `fd bounds`, `acceptClient -1`) and cut total findings 23→7 (score -3). New guidance: downgrade ONLY borderline style/docs, NEVER correctness/error-handling/resource-bound; keep higher severity when in doubt. Verified `813 passed`.
- **Docs (comparison):** Added `## Skill Generation Per Model` section to `report/comparison.md` via `report/comparison_render.py` — table shows per-model distill mode (two-stage vs single-call), token budget 16000, wall-clock timeouts, and severity bias note sourced from `distill.py:MODEL_SEVERITY_BIAS` / `config.py:_MODEL_TIMEOUTS`. Documents why skills differ per model and why glm previously lost criticals. Verified `813 passed`.
- **Skill (glm5.2):** Regenerated `linus-torvalds-skill/SKILL-GLM.md` with updated bias — single-call, 9000 words (was 9464/9616), `ALL CHECKS PASSED` (122 quotes, 13/13 categories, 25 interview citations), `64 passed` in `test_distill`. Previous skill caused -3 net critical; re-review pending to verify recovery.
- **CI (no-AI):** Added `verify-artifacts` job to `.github/workflows/ci.yml` — verifies `verify_skill.py --strict`, `validate_benchmark.py`, and deterministic report modules without any `REGOLO_API_KEY`. Header `# CI never calls LLM` documents that all AI generation (distill, run_review) is local-only. Verified YAML parses, no secrets required.

## 2026-08-25

- **Bugfix (transport):** Fixed critical connection-pooling regression in `distill_llm.py` `_get_connection()` — scheme check `host.startswith('https://')` always failed because callers pass `parsed.netloc` (scheme stripped), sending every pooled LLM call as plain HTTP on port 80 against the HTTPS-only Regolo API; the gateway answered 302-to-self, producing silent `empty_response` failures for all GLM5.2 distill calls. Scheme is now derived from `config.CHAT_URL`. This bug had broken all skill generation since the connection-pooling refactor landed. Also fixed in the same pass: SSE parser now captures `delta.reasoning_content` as fallback when `delta.content` is absent; raw `http.client` 4xx/5xx responses detected explicitly (were silently iterated as SSE streams); connection pool made thread-local (`threading.local`) for safe concurrent use from parallel category workers.
- **Performance:** Added disk-based LLM response cache (`data/llm_cache.jsonl`, 24h TTL via `LLM_CACHE_TTL_HOURS`/`LLM_CACHE_PATH`) and content-hash extraction cache (`data/extract_cache.jsonl`, disable with `EXTRACT_CACHE=0`) — identical prompts survive process restarts; lookup order in-memory → disk → API; truncated responses never persisted. Parallelized two-stage distill category calls (`ThreadPoolExecutor`, 3 workers, `DISTILL_MAX_WORKERS` env var; forced to 1 for non-GLM models) — GLM5.2 skill generation drops from ~30-45 min to ~8-12 min; failed categories retry once sequentially. Added HTTP connection pooling (host-keyed `HTTPSConnection` reuse). All cache operations guarded by `threading.Lock`.
- **Pipeline (timeouts):** Replaced `signal.SIGALRM`-based `_WallClockTimeout` with thread-based `threading.Timer` in `distill_llm.py` and `report/llm_review.py` — works reliably even when the main thread is blocked inside C-level `ssl.read()`. Added `WALL_CLOCK_CATEGORY` (300s, env `LLM_WALL_CLOCK_CATEGORY`) for per-category distill calls; synthesis/repair retain longer timeouts (`wall_clock_override` parameter added to `_call_llm()`). Lowered per-read socket timeout from 1200s to 120s. Fixed GLM5.2 fallback chain to exclude the primary model (prevented infinite retry loop). Switched GLM5.2 from `--single-call` (one massive 350-pattern request) to two-stage mode (14 per-category calls + 1 synthesis) — lowers truncation risk, makes retries cheap.
- **Quality:** Hardened `_detect_truncation()` in `distill_llm.py` (catches incomplete YAML frontmatter, empty sections, missing required sections, mid-sentence cut-offs). Added input validation to `extract_moves()` in `extract.py`. Added `_validate_skill_structure()` and `_validate_severity_consistency()` post-generation checks in `distill.py` (warns when severity frequency deviates >2x from calibration). Streaming read of interview data in `_load_interview_data()` to prevent OOM.
- **Refactor:** Split `distill.py` (1338 lines) into `distill_prompts.py` (550), `distill_llm.py` (213), `distill_sanitize.py` (98), `distill.py` (529) — public API unchanged, `soul.py` imports updated, 558 tests pass. Rewrote `report/run_review.sh` (734 lines bash) as `report/run_review.py` (759 lines Python) with `argparse`/`pathlib`/`ThreadPoolExecutor`; added `tests/test_run_review.py` (49 tests); full suite 607 passed. Removed `opencode` CLI dependency — replaced with `report/llm_review.py` (direct Regolo API caller, stdlib only), eliminating the read-loop risk where GLM5.2 repeatedly issued `read` tool calls instead of producing output. Added 900-line file-size limit to `AGENTS.md`.

## 2026-08-24

- **Documentation:** Added a reproducibility rule to `AGENTS.md` — all generated `.md` artifacts are produced by scripts and must never be edited by hand; any change requires editing the generator script and re-running it. Documented each artifact with its generator and regeneration command.
- **Documentation:** Expanded `AGENTS.md` with nine project-specific sections: language-agnostic enforcement, runtime constraints (model token limits), API configuration, pipeline architecture (five stages), review pipeline (with-skill vs baseline, chunked mode), verification commands, data directory, and git discipline.
- **Documentation:** Corrected the token-limits table — GLM5.2 has a 200K context, gpt-oss-120b and mistral-small-4-119b both 120K. Removed the License section from `AGENTS.md` (licensing belongs in the LICENSE file).
- **Pipeline:** Fixed `distill.py` prompt (T2) — relaxed over-restrictive constraints that caused over-sanitization in the gpt-oss-120b skill, added missing triggers (copy-paste code, magic numbers, inconsistent error codes), and split the overly broad trigger 7.2 into focused sub-triggers.
- **Pipeline:** Fixed `run_review.sh` `--force` bypass (T0a) — the flag no longer silently skips stale-chunk cleanup, preventing corrupted reviews from being merged.
- **Pipeline:** Fixed consensus-matrix 2/3 matching (T0b) in `build_comparison.py` — findings that two of three models agree on are now correctly grouped instead of being dropped.
- **Pipeline:** Added `CHUNKED_MODELS` environment variable (T1) — chunked review mode activates only for listed models (e.g. `CHUNKED_MODELS="glm5.2"`), leaving gpt-oss-120b and mistral on the fast single-call path.
- **Pipeline:** Added `validate_review_format()` gate (T3) — checks for `### [SEVERITY]` headings and required fields after each review; fails loudly on invalid format instead of silently producing an empty comparison.
- **Pipeline:** Collapsed duplicated review parsers (T4) into a single parameterized parser in `build_comparison.py`, added 15 parser unit tests in `tests/test_build_comparison.py`.
- **Pipeline:** Fixed `merge_chunks` duplication and `awk`/`set -e` handling (T7) in the chunked review flow.
- **Pipeline:** Added `metrics.jsonl` observability (T8) — each review run logs timestamps, model names, and outcome flags to `report/metrics.jsonl`.
- **Pipeline:** Baseline review files are now retained in `report/baseline/` (git-ignored) instead of being deleted after comparison generation.
- **Skill:** Regenerated all three skill files from the updated `distill.py` prompt — `SKILL.md` (gpt-oss-120b, 5624 words), `SKILL-GLM.md` (glm5.2, 8163 words), `SKILL-Mistral.md` (mistral-small-4-119b, 7734 words). All three pass `verify_skill.py`: language-agnostic, 13/13 categories, calibration sections present, no forbidden C/kernel terms, real quotes preserved.
- **Pipeline:** Re-ran the SmallChat review pipeline with the regenerated skills. Three bugs surfaced and were fixed: (1) `printf` numeric bug in `log_metrics` — `grep -c || echo 0` produced `"0\n0"` when grep found no matches, breaking the `%d` format specifier; fixed with `|| true`. (2) GLM5.2 chunk timeout too short at 900s for the 8K-word skill; raised to 2400s to match the non-chunked timeout. (3) Parser regex required `[SEVERITY]` brackets but gpt-oss-120b switched to `#### CRITICAL` without brackets; made brackets optional in `parse_review`.
- **Report:** Final comparison regenerated with all six reviews. Results: mistral wins (score 5, 0 net critical, 8 confirmed findings); glm5.2 follows (score 4, -1 net critical, 9 confirmed); gpt-oss-120b last (score -1, -1 net critical, 1 confirmed). The skill narrows focus toward correctness but suppresses one critical finding per model that the baseline caught — a coverage gap worth investigating.

### Pipeline fixes

- **`report/run_review.sh`:** Added strict review-format blocks in `review_prompt()`, `baseline_prompt()`, and chunk prompt — prompts now include concrete format examples to prevent heading drift and inconsistent `**Location:**` syntax.
- **`report/run_review.sh`:** Removed `run_summary_review()` function and its call site — eliminates an extra LLM call in the chunked pipeline, reducing GLM5.2 runtime by ~40 min per run.
- **`report/run_review.sh`:** Verdict scoring now uses `confirmed_critical` field and requires keyword overlap ≥3 words (or Jaccard ≥0.5) instead of fuzzy match.
- **`report/run_review.sh`:** Refactored model list into `MODELS` and `TIMEOUTS` associative arrays — adding a new model is now a single entry.
- **`report/run_review.sh`:** All retry sites now implement 3-attempt exponential backoff (1×, 2×, 4×) with 0-30s random jitter.
- **`report/build_comparison.py`:** Verdict scoring updated to match `run_review.sh` changes.

### Distill prompt fixes (coverage gap)

- **`src/torvalds_skill/distill.py`:** Fixed Trigger 7.2 example bias, type/severity contradiction, missing format-string trigger, and uneven error-handling trigger distribution. Word-count guidance now consistently reads 4000-7000.

### Parser fixes

- **`report/parse_review.py`:** Severity heading regex now accepts both `#### [CRITICAL]` and `#### CRITICAL` (brackets optional).
- **`report/parse_review.py`:** Recognizes `**Location:**` (colon inside bold) in addition to `**Location**`.

### Bug fixes

- **`scripts/calibrate_interviews.py`:** Added missing STOPWORDS entries (`set_fs`, `buf`) — fixes two xfailed tests.
- **`scripts/calibrate_interviews.py`:** Fixed `year_range` producing duplicated single-year lists like `[2020, 2020]` instead of `[2020]`.
- **`scripts/calibrate_interviews.py`:** Guarded division in `compute_corpus_stats()` against `ZeroDivisionError` when `total == 0`.
- **`report/run_review.sh`:** Fixed `printf` numeric-format bug in `log_metrics` where `grep -c || echo 0` emitted two lines (`0\n0`), breaking `%d` format — changed to `|| true`.
- **`report/run_review.sh`:** Raised GLM5.2 chunk timeout from 900s to 2400s (~40 min) to match non-chunked timeout.

### Tests

- Added 10 new test files (390 new tests, suite now 528 tests, 0 failures, 0 xfails):
  - `tests/test_classify_interviews.py` (110 tests) — 8 pure functions in classify_interviews.py
  - `tests/test_validate.py` (69 tests) — move/patterns/calibration validators
  - `tests/test_variation.py` (65 tests) — thread phase, urgency, JSON parse
  - `tests/test_streaming.py` (27 tests) — JSONL round-trip I/O
  - `tests/test_models.py` (28 tests) — dataclasses and parsers
  - `tests/test_verify_skill.py` (26 tests) — normalize, forbidden terms
  - `tests/test_interviews.py` (22 tests) — HTML extraction
  - `tests/test_cluster_interviews.py` (16 tests) — stratified sampling
  - `tests/test_mbox_to_jsonl.py` (14 tests) — body cleaning
  - `tests/test_migrate_categories.py` (13 tests) — record migration

### Cleanup

- Removed `todo.md` (all tasks completed).

### GLM5.2 fixes

- **`src/torvalds_skill/distill.py`:** Increased `_call_llm` timeout from 600s to 1200s for GLM5.2 skill generation — reasoning model needs more time.
- **`src/torvalds_skill/distill.py`:** Capped `max_tokens` at 16000 for ALL models (was 64000 for non-GLM models, causing Mistral skill bloat at 19K+ words).
- **`src/torvalds_skill/distill.py`:** Added `_repair_missing_sections()` helper — detects missing required top-level sections (e.g., "Severity Decision Tree") in generated skill files and appends them via targeted LLM calls. Wired into `distill_skill()` workflow. Prevents full regeneration when only one section is missing.
- **Skill:** Repaired GLM5.2 skill file using `_repair_missing_sections()` — added missing "Severity Decision Tree" section. Skill now passes all `verify_skill.py` checks (8800 words).

### Prompt inlining fixes (GLM5.2 read-loop prevention)

- **`report/run_review.sh`:** Inlined skill and source file content directly into chunk review prompt instead of instructing the agent to "read" them. Added explicit "Do NOT use any tools. Do NOT read any files." directive. Removed "read it fully" and "Read the skill and the source file" phrasing — prevents GLM5.2 from getting stuck in read-tool loops.
- **`report/run_review.sh`:** Same inlining fix applied to `review_prompt()` (non-chunked with-skill review). Skill content and all 5 source files inlined. Tool use forbidden.
- **`report/run_review.sh`:** Same inlining fix applied to `baseline_prompt()`. All 5 source files inlined. Tool use forbidden.

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
