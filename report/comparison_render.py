"""Markdown rendering for comparison report."""

from datetime import datetime, timezone
from pathlib import Path


def generate_scorecard(models_data: list[dict]) -> str:
    """Generate stakeholder scorecard table and summary.
    
    Args:
        models_data: List of dicts with keys: model, skill_total, skill_critical, 
                    skill_only_critical, baseline_only_critical (from skill_vs_baseline comparisons)
    
    Returns:
        Markdown string with scorecard table and 1-2 sentence summary
    """
    lines = []
    
    # Scorecard table
    lines.append("## Stakeholder Scorecard")
    lines.append("")
    lines.append("Quick summary for non-technical readers:")
    lines.append("")
    lines.append("| Model | Total Findings | Critical Findings | Skill-Only Critical | Verdict |")
    lines.append("|-------|---------------|-------------------|---------------------|---------|")
    
    for data in models_data:
        model = data["model"]
        total = data["skill_total"]
        critical = data["skill_critical"]
        skill_only = data["skill_only_critical"]
        baseline_only = data["baseline_only_critical"]
        
        # Determine verdict
        if not isinstance(skill_only, int) or not isinstance(baseline_only, int):
            verdict = "Baseline pending"
        elif skill_only > 0 and baseline_only == 0:
            verdict = "Skill adds value"
        elif skill_only == 0 and baseline_only == 0:
            verdict = "No change"
        elif baseline_only > skill_only:
            verdict = "Skill reduces coverage"
        else:
            verdict = "Skill adds value"
        
        lines.append(f"| {model} | {total} | {critical} | {skill_only} | {verdict} |")
    
    lines.append("")
    
    # Generate summary sentence
    # Find model with most skill-only criticals
    best_model = None
    best_count = -1
    for data in models_data:
        skill_only = data["skill_only_critical"]
        if isinstance(skill_only, int) and skill_only > best_count:
            best_count = skill_only
            best_model = data["model"]
    
    if best_model and best_count > 0:
        summary = f"The skill adds the most value for {best_model}, which gained {best_count} critical finding(s) exclusive to the with-skill review."
    elif best_model and best_count == 0:
        summary = "The skill provides neutral critical coverage across all models, with no model gaining exclusive critical findings."
    else:
        summary = "Baseline comparisons not yet available for all models."
    
    lines.append(summary)
    lines.append("")
    
    return "\n".join(lines)


def generate_markdown(
    report_dir: Path,
    metrics: dict,
    matched_groups: list[dict],
    severity_disagreements: list[dict],
    trigger_coverage: dict,
    skill_vs_baseline: list[dict],
    missing_files: list[str],
    model_names: list[str] | None = None,
    trigger_effectiveness: dict | None = None,
) -> str:
    """Generate the complete comparison.md content.
    
    Args:
        model_names: List of model names. If None, defaults to hardcoded list.
        trigger_effectiveness: Dict mapping model_name -> trigger effectiveness metrics
            (from analyze_trigger_effectiveness). If None, skips this section.
    """
    # Generate stakeholder scorecard
    scorecard = generate_scorecard(skill_vs_baseline)
    
    lines = []
    
    # Default model names for backward compatibility
    if model_names is None:
        model_names = ["gpt-oss-120b", "glm5.2", "mistral"]
    lines = []

    # YAML frontmatter
    lines.append("---")
    lines.append("title: Model Comparison — SmallChat Review")
    lines.append(f"date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")
    lines.append("codebase: antirez/smallchat")
    lines.append("models: " + ", ".join(model_names))
    lines.append("skill: linus-torvalds-skill (language-agnostic)")
    lines.append("method: static review, skill triggers applied per source file")
    lines.append("---")
    lines.append("")

    # Title and intro
    lines.append("# Model Comparison — SmallChat Review")
    lines.append("")
    
    # Insert scorecard after title
    lines.append(scorecard)
    
    # Skill Generation Per Model section
    lines.append("## Skill Generation Per Model")
    lines.append("")
    lines.append("Skills are NOT identical — each variant is distilled from the same 350 patterns but with model-specific prompt calibration, token budgets, and execution mode.")
    lines.append("")
    lines.append("| Model | Skill file | Distill mode | Token budget | Wall-clock timeout | Severity bias note |")
    lines.append("|-------|------------|--------------|--------------|-------------------|-------------------|")
    lines.append("| gpt-oss-120b | `linus-torvalds-skill/SKILL.md` | two-stage (14 categories + synthesis) | 16000 | 120s (WALL_CLOCK_DEFAULT) | balanced |")
    lines.append("| glm5.2 | `linus-torvalds-skill/SKILL-GLM.md` | single-call | 16000 (GLM_MAX_TOKENS) | 600s / 1800s (WALL_CLOCK_GLM) | downgrade ONLY style/docs borderline, never correctness/error-handling (see `MODEL_SEVERITY_BIAS` in `distill.py`) |")
    lines.append("| mistral-small-4-119b | `linus-torvalds-skill/SKILL-Mistral.md` | two-stage | 16000 | 120s | under-rates → upgrade borderline |")
    lines.append("")
    lines.append("**Source:** `src/torvalds_skill/distill.py:MODEL_SEVERITY_BIAS`, `src/torvalds_skill/config.py:_MODEL_TIMEOUTS` and `GLM_MAX_TOKENS`. Regenerate per `docs/CONTRIBUTING.md`.")
    lines.append("")
    lines.append("This explains why glm5.2 previously lost 3 criticals (over-filtering style) and why trigger coverage differs across models.")
    lines.append("")
    
    lines.append(f"{len(model_names)} models reviewed the same C codebase (antirez/smallchat, ~706 LOC) using the same language-agnostic Linus Torvalds skill. This document cross-references their findings at the issue level — not just counts — to measure consensus, accuracy, and severity calibration.")
    lines.append("")

    # Metrics Summary table
    lines.append("## Metrics Summary")
    lines.append("")
    header = "| Metric | " + " | ".join(model_names) + " |"
    lines.append(header)
    lines.append("|" + "|".join(["--------"] + [":---:"] * len(model_names)) + "|")

    for metric_name in ["findings", "CRITICAL", "HIGH", "MEDIUM", "LOW", "words"]:
        row = [metric_name.replace("_", " ").title()]
        for model_key in model_names:
            m = metrics.get(model_key, {})
            skill_metrics = m.get("skill", {})
            val = skill_metrics.get(metric_name, "N/A")
            row.append(str(val))
        lines.append(f"| {' | '.join(row)} |")

    lines.append("")
    lines.append("**Key insight:** Finding count is a poor quality signal. The consensus matrix below shows which models caught which bugs — and that is where the real signal lives.")
    lines.append("")

    # Warning about missing files
    if missing_files:
        lines.append("⚠️ **Note:** The following review files were missing and skipped:")
        for f in missing_files:
            lines.append(f"- {f}")
        lines.append("")

    # Consensus Matrix
    lines.append("---")
    lines.append("")
    lines.append("## Finding Consensus Matrix")
    lines.append("")
    lines.append("Every finding from all three reviews, mapped to the underlying issue. ✓ = found, ✗ = missed. Severity shown in parentheses.")
    lines.append("")

    # Group by file
    files_in_matrix = set(g["file"] for g in matched_groups if g["file"] != "unspecified")
    if "unspecified" in set(g["file"] for g in matched_groups):
        files_in_matrix = list(files_in_matrix) + ["unspecified"]

    row_num = 1
    for file in sorted(files_in_matrix):
        lines.append(f"### {file}")
        lines.append("")
        # Build dynamic header based on model names
        header_cols = ["#", "Issue"] + model_names + ["Consensus"]
        lines.append("| " + " | ".join(header_cols) + " |")
        sep_cols = ["---"] + [":---:"] * len(model_names) + [":---:"]
        lines.append("|" + "|".join(sep_cols) + "|")

        file_groups = [g for g in matched_groups if g["file"] == file]
        for group in file_groups:
            # Build dynamic marks based on model names
            marks = []
            for model_name in model_names:
                finding = group.get(model_name)
                if finding:
                    marks.append(f"✓ ({finding.severity})")
                else:
                    marks.append("✗")

            # Determine consensus
            found_count = sum(1 for model_name in model_names if group.get(model_name))
            if found_count == len(model_names):
                consensus = f"{len(model_names)}/{len(model_names)}"
            elif found_count == len(model_names) - 1:
                consensus = f"{len(model_names)-1}/{len(model_names)}"
            elif found_count == 1:
                for model_name in model_names:
                    if group.get(model_name):
                        consensus = f"{model_name} only"
                        break
            else:
                consensus = "—"

            title = group["title"][:50] + "..." if len(group["title"]) > 50 else group["title"]
            lines.append(f"| {row_num} | {title} | {' | '.join(marks)} | {consensus} |")
            row_num += 1

        lines.append("")

    # Severity Disagreement Table
    lines.append("---")
    lines.append("")
    lines.append("## Severity Disagreement Table")
    lines.append("")
    lines.append("Cases where 2+ models found the same issue but assigned different severities:")
    lines.append("")

    if severity_disagreements:
        header_cols = ["Issue"] + model_names
        lines.append("| " + " | ".join(header_cols) + " |")
        lines.append("|" + "|".join(["-------"] + [":---:"] * len(model_names)) + "|")
        for d in severity_disagreements:
            title = d["title"][:40] + "..." if len(d["title"]) > 40 else d["title"]
            sev_row = []
            for model in model_names:
                found = next((s for m, s in d["severities"] if m == model), None)
                sev_row.append(found if found else "—")
            lines.append(f"| {title} | {' | '.join(sev_row)} |")
    else:
        lines.append("*No severity disagreements found.*")
    lines.append("")

    # Trigger Coverage Table
    lines.append("---")
    lines.append("")
    lines.append("## Trigger Coverage Comparison")
    lines.append("")
    lines.append("Which skill triggers fired in each review:")
    lines.append("")

    # Get all unique triggers
    all_triggers = set()
    for model_data in trigger_coverage.values():
        all_triggers.update(model_data.keys())

    if all_triggers:
        header_cols = ["Trigger theme"] + model_names
        lines.append("| " + " | ".join(header_cols) + " |")
        lines.append("|" + "|".join(["---------------"] + [":---:"] * len(model_names)) + "|")

        for trigger in sorted(all_triggers):
            marks = []
            for model_name in model_names:
                count = trigger_coverage.get(model_name, {}).get(trigger, 0)
                marks.append(f"✓ ({count})" if count > 0 else "✗")

            # Truncate trigger name for display
            trigger_display = trigger[:30] + "..." if len(trigger) > 30 else trigger
            lines.append(f"| {trigger_display} | {' | '.join(marks)} |")
    else:
        lines.append("*No trigger data available.*")
    lines.append("")

    # With-Skill vs Baseline Comparison
    lines.append("---")
    lines.append("")
    lines.append("## With-Skill vs Baseline Comparison")
    lines.append("")
    lines.append("For each model, comparing findings with the skill vs without (baseline):")
    lines.append("")

    lines.append("| Model | Baseline Total | With-Skill Total | Baseline CRITICAL | With-Skill CRITICAL | Critical Overlap | Skill-Only CRITICAL | Baseline-Only CRITICAL | Skill Added Value |")
    lines.append("|-------|----------------|------------------|-------------------|---------------------|------------------|---------------------|------------------------|-------------------|")

    for comparison in skill_vs_baseline:
        model = comparison["model"]
        baseline_total = comparison["baseline_total"]
        skill_total = comparison["skill_total"]
        baseline_crit = comparison["baseline_critical"]
        skill_crit = comparison["skill_critical"]
        overlap = comparison["critical_overlap"]
        skill_only = comparison["skill_only_critical"]
        baseline_only = comparison["baseline_only_critical"]

        if baseline_total == "N/A":
            value = "baseline not yet generated"
        elif not isinstance(skill_only, int) or not isinstance(baseline_only, int):
            value = "N/A"
        else:
            net = skill_only - baseline_only
            if net > 0:
                value = f"yes (+{net} net critical: {skill_only} found, {baseline_only} lost)"
            elif net == 0:
                value = f"neutral (0 net: {skill_only} found, {baseline_only} lost)"
            else:
                value = f"no ({net} net critical: {skill_only} found, {baseline_only} lost)"

        lines.append(f"| {model} | {baseline_total} | {skill_total} | {baseline_crit} | {skill_crit} | {overlap} | {skill_only} | {baseline_only} | {value} |")

    lines.append("")

    # Qualitative analysis — generated from data
    lines.append("---")
    lines.append("")
    lines.append("## Per-Model Bug Comparison (Baseline vs With-Skill)")
    lines.append("")
    lines.append("Bug-by-bug comparison for each model: which bugs were found by both, only baseline, or only skill.")
    lines.append("")

    for comparison in skill_vs_baseline:
        model = comparison["model"]
        lines.append(f"### {model}")
        lines.append("")
        
        # Check if baseline is available
        if comparison["baseline_total"] == "N/A":
            lines.append("*Baseline not available for this model.*")
            lines.append("")
            continue
        
        matched_pairs = comparison.get("matched_pairs", [])
        baseline_only = comparison.get("baseline_only_all", [])
        skill_only = comparison.get("skill_only_all", [])
        
        # Table 1: Same bugs (found in both)
        lines.append("**Same bugs (found in both):**")
        lines.append("")
        if matched_pairs:
            lines.append("| Issue | File | Baseline | Skill | Severity changed? |")
            lines.append("|-------|------|----------|-------|-------------------|")
            for pair in matched_pairs:
                skill_f = pair["skill"]
                baseline_f = pair["baseline"]
                if skill_f and baseline_f:
                    issue = skill_f.title[:60] + "..." if len(skill_f.title) > 60 else skill_f.title
                    file = skill_f.file or "—"
                    baseline_sev = baseline_f.severity
                    skill_sev = skill_f.severity
                    if baseline_sev != skill_sev:
                        sev_changed = f"YES: {baseline_sev}→{skill_sev}"
                    else:
                        sev_changed = "no"
                    lines.append(f"| {issue} | {file} | {baseline_sev} | {skill_sev} | {sev_changed} |")
        else:
            lines.append("*None.*")
        lines.append("")
        
        # Table 2: Baseline-only (skill missed)
        lines.append("**Baseline-only (skill missed):**")
        lines.append("")
        if baseline_only:
            lines.append("| Issue | File | Severity | Skill trigger covers? |")
            lines.append("|-------|------|----------|-----------------------|")
            # Use new coverage data if available
            coverage_data = {item["finding"].title: item for item in comparison.get("baseline_only_with_coverage", [])}
            for f in baseline_only:
                issue = f.title[:60] + "..." if len(f.title) > 60 else f.title
                file = f.file or "—"
                # Look up coverage data
                cov = coverage_data.get(f.title)
                if cov and cov["matched_trigger"]:
                    trigger_display = cov["matched_trigger"][:50] + "..." if len(cov["matched_trigger"]) > 50 else cov["matched_trigger"]
                else:
                    trigger_display = "out of scope"
                lines.append(f"| {issue} | {file} | {f.severity} | {trigger_display} |")
        else:
            lines.append("*None.*")
        lines.append("")
        
        # Table 3: Skill-only (skill added)
        lines.append("**Skill-only (skill added):**")
        lines.append("")
        if skill_only:
            lines.append("| Issue | File | Severity | Trigger |")
            lines.append("|-------|------|----------|---------|")
            for f in skill_only:
                issue = f.title[:60] + "..." if len(f.title) > 60 else f.title
                file = f.file or "—"
                trigger = f.trigger[:40] + "..." if f.trigger and len(f.trigger) > 40 else (f.trigger or "—")
                lines.append(f"| {issue} | {file} | {f.severity} | {trigger} |")
        else:
            lines.append("*None.*")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Qualitative Analysis")
    lines.append("")

    # --- Accuracy Scoring (consensus-based) ---
    # A finding found by 2+ models is treated as a confirmed real bug.
    # A finding found by only 1 model is "unverified" (could be real or false positive).
    confirmed_per_model = {k: 0 for k in model_names}
    confirmed_critical_per_model = {k: 0 for k in model_names}
    unverified_per_model = {k: 0 for k in model_names}
    unique_per_model = {k: 0 for k in model_names}

    for group in matched_groups:
        found_count = sum(1 for model_name in model_names if group.get(model_name))
        if found_count >= 2:
            # Count all confirmed findings
            for model_name in model_names:
                if group.get(model_name):
                    confirmed_per_model[model_name] += 1
            # Also count CRITICAL-only confirmed findings for scoring
            for model_name in model_names:
                finding = group.get(model_name)
                if finding and finding.severity == "CRITICAL":
                    confirmed_critical_per_model[model_name] += 1
        elif found_count == 1:
            for model_name in model_names:
                if group.get(model_name):
                    unverified_per_model[model_name] += 1
                    unique_per_model[model_name] += 1
                    break

    lines.append("### Consensus-Based Accuracy")
    lines.append("")
    lines.append("Findings confirmed by 2+ models are treated as real bugs. Findings reported by only one model are unverified (could be real or false positive).")
    lines.append("")
    header_cols = ["Model", "Total Findings", "Confirmed (2+ models)", "Unverified (1 model only)", "Consensus Rate"]
    lines.append("| " + " | ".join(header_cols) + " |")
    lines.append("|" + "|".join(["-------", ":--------------:", ":---------------------:", ":--------------------------:", ":--------------:"]) + "|")
    for mk in model_names:
        total = confirmed_per_model[mk] + unverified_per_model[mk]
        rate = f"{confirmed_per_model[mk] / total * 100:.0f}%" if total > 0 else "N/A"
        lines.append(f"| {mk} | {total} | {confirmed_per_model[mk]} | {unverified_per_model[mk]} | {rate} |")
    lines.append("")

    # --- Severity Calibration ---
    lines.append("### Severity Calibration")
    lines.append("")
    if severity_disagreements:
        lines.append("Cases where 2+ models found the same issue but assigned different severities:")
        lines.append("")
        header_cols = ["Issue"] + model_names
        lines.append("| " + " | ".join(header_cols) + " |")
        lines.append("|" + "|".join(["-------"] + [":---:"] * len(model_names)) + "|")
        for d in severity_disagreements:
            title = d["title"][:40] + "..." if len(d["title"]) > 40 else d["title"]
            sev_map = dict(d["severities"])
            sev_row = []
            for model_name in model_names:
                sev_row.append(sev_map.get(model_name, "—"))
            lines.append(f"| {title} | {' | '.join(sev_row)} |")
        lines.append("")
        lines.append(f"Total severity disagreements: {len(severity_disagreements)}. Lower is better — it means the model's severity assessment aligns with the consensus.")
        lines.append("")
    else:
        lines.append("No severity disagreements detected — all models that found the same issue assigned the same severity.")
        lines.append("")

    # --- Unique Findings ---
    lines.append("### Unique Findings (Single-Model Discoveries)")
    lines.append("")
    lines.append("Findings reported by only one model. These represent either unique insight or false positives:")
    lines.append("")
    lines.append("| Model | Unique Findings |")
    lines.append("|-------|:--------------:|")
    for mk in model_names:
        lines.append(f"| {mk} | {unique_per_model[mk]} |")
    lines.append("")
    lines.append("A high unique count with a low consensus rate suggests false positives. A high unique count with a high consensus rate suggests the model found real bugs others missed.")
    lines.append("")

    # --- With-Skill vs Baseline Impact ---
    lines.append("### With-Skill vs Baseline: Skill Impact")
    lines.append("")
    lines.append("How the skill changed each model's review:")
    lines.append("")
    for svb in skill_vs_baseline:
        model = svb["model"]
        bt, st = svb["baseline_total"], svb["skill_total"]
        bc, sc = svb["baseline_critical"], svb["skill_critical"]
        soc = svb["skill_only_critical"]
        boc = svb["baseline_only_critical"]
        lines.append(f"**{model}:** Baseline {bt} findings ({bc} CRITICAL) → With-skill {st} findings ({sc} CRITICAL). "
                     f"Skill found {soc} critical bug(s) the baseline missed; baseline found {boc} critical bug(s) the skill missed.")
        lines.append("")

    # Honest tradeoff analysis: does the skill narrow focus at the cost of coverage?
    lines.append("#### Skill Tradeoff Analysis")
    lines.append("")
    lines.append("The skill narrows reviewer focus toward memory-safety and correctness (Linus's priorities). "
                 "This filters noise but can also suppress valid findings. Net critical impact per model:")
    lines.append("")
    lines.append("| Model | Skill-Only CRITICAL | Baseline-Only CRITICAL | Net Critical Impact | Total Finding Delta |")
    lines.append("|-------|:-------------------:|:----------------------:|:-------------------:|:-------------------:|")
    for svb in skill_vs_baseline:
        model = svb["model"]
        soc = svb["skill_only_critical"]
        boc = svb["baseline_only_critical"]
        bt, st = svb["baseline_total"], svb["skill_total"]
        if isinstance(soc, int) and isinstance(boc, int):
            net = soc - boc
            net_str = f"{net:+d}" if net != 0 else "0"
        else:
            net_str = "N/A"
        if isinstance(bt, int) and isinstance(st, int):
            delta = st - bt
            delta_str = f"{delta:+d}" if delta != 0 else "0"
        else:
            delta_str = "N/A"
        lines.append(f"| {model} | {soc} | {boc} | {net_str} | {delta_str} |")
    lines.append("")
    lines.append("**Interpretation:** A positive net critical impact means the skill found real bugs the baseline missed. "
                 "A negative value means the skill suppressed critical findings the baseline caught — a coverage gap. "
                 "A large negative total finding delta with neutral critical impact means the skill filtered noise without losing signal.")
    lines.append("")

    # Per-model read: dynamic narrative based on net critical and finding delta
    lines.append("**Per-model read:**")
    for svb in skill_vs_baseline:
        model = svb["model"]
        soc = svb["skill_only_critical"]
        boc = svb["baseline_only_critical"]
        bt, st = svb["baseline_total"], svb["skill_total"]
        if not isinstance(soc, int) or not isinstance(boc, int):
            lines.append(f"- **{model}:** Baseline not available for comparison.")
            continue
        net = soc - boc
        if isinstance(bt, int) and isinstance(st, int):
            delta = st - bt
        else:
            delta = None
        if bt == 0 and net > 0:
            lines.append(f"- **{model}:** Clear win. Baseline found nothing; skill added {net} critical bug(s). The skill unlocked review capability this model didn't have without it.")
        elif net > 0:
            cut = f"cut {abs(delta)} findings" if delta is not None and delta < 0 else "added findings"
            lines.append(f"- **{model}:** Net positive. The skill {cut} and added {net} critical bug(s) the baseline missed.")
        elif net < 0:
            cut = f"cut {abs(delta)} findings" if delta is not None and delta < 0 else "changed finding count"
            lines.append(f"- **{model}:** Net negative on critical coverage. The skill {cut} and suppressed {boc} critical(s) the baseline caught, while only adding {soc} new critical. The skill narrowed focus too aggressively — the {boc} lost critical(s) are a real coverage gap worth investigating.")
        else:
            if delta is not None and delta < 0:
                lines.append(f"- **{model}:** Neutral on criticals. The skill filtered noise (cut {abs(delta)} findings) without losing critical coverage.")
            else:
                lines.append(f"- **{model}:** Neutral. No net change in critical coverage.")
    lines.append("")

    # --- Trigger Coverage Analysis ---
    lines.append("### Trigger Coverage Analysis")
    lines.append("")
    lines.append("Which skill triggers each model fired:")
    lines.append("")
    for mk in model_names:
        tc = trigger_coverage.get(mk, {})
        trigger_count = sum(tc.values()) if tc else 0
        distinct_triggers = len(tc) if tc else 0
        lines.append(f"**{mk}:** {distinct_triggers} distinct triggers fired, {trigger_count} total trigger firings.")
        if tc:
            top_triggers = sorted(tc.items(), key=lambda x: -x[1])[:3]
            trigger_summary = ", ".join(f"{t} ({c}x)" for t, c in top_triggers)
            lines.append(f"  Top triggers: {trigger_summary}")
        lines.append("")

    # --- Verdict ---
    lines.append("### Verdict")
    lines.append("")
    # Score: confirmed findings + skill-only criticals - severity disagreements
    # Precompute per-model disagreement counts from the severities list
    model_disagreements = {mk: 0 for mk in model_names}
    for d in severity_disagreements:
        sev_map = dict(d["severities"])
        unique_sevs = set(sev_map.values())
        if len(unique_sevs) > 1:
            for mk in model_names:
                if mk in sev_map:
                    model_disagreements[mk] += 1

    scores = {}
    for mk in model_names:
        confirmed_critical = confirmed_critical_per_model[mk]
        soc = 0
        boc = 0
        for svb in skill_vs_baseline:
            if svb["model"] == mk:
                soc = svb["skill_only_critical"]
                boc = svb["baseline_only_critical"]
                break
        soc_score = soc if isinstance(soc, int) else 0
        boc_score = boc if isinstance(boc, int) else 0
        # Net critical impact: reward skill-only discoveries, penalize baseline-only (coverage gaps)
        # Use confirmed_critical to match units with soc/boc (all CRITICAL-only)
        scores[mk] = confirmed_critical + soc_score - boc_score - model_disagreements[mk]

    winner = max(scores, key=scores.get)
    lines.append(f"Based on consensus-confirmed CRITICAL findings, net critical impact (skill-only minus baseline-only), and severity calibration:")
    lines.append("")
    header_cols = ["Model", "Confirmed CRITICAL", "Skill-Only CRITICAL", "Baseline-Only CRITICAL", "Net Critical", "Severity Disagreements", "Score"]
    lines.append("| " + " | ".join(header_cols) + " |")
    lines.append("|" + "|".join(["-------", ":------------------:", ":-------------------:", ":----------------------:", ":-------------:", ":----------------------:", ":-----:"]) + "|")
    for mk in model_names:
        confirmed_critical = confirmed_critical_per_model[mk]
        soc = 0
        boc = 0
        for svb in skill_vs_baseline:
            if svb["model"] == mk:
                soc = svb["skill_only_critical"]
                boc = svb["baseline_only_critical"]
                break
        soc_int = soc if isinstance(soc, int) else 0
        boc_int = boc if isinstance(boc, int) else 0
        net = soc_int - boc_int
        net_str = f"{net:+d}" if net != 0 else "0"
        lines.append(f"| {mk} | {confirmed_critical} | {soc} | {boc} | {net_str} | {model_disagreements[mk]} | {scores[mk]} |")
    lines.append("")
    lines.append("**Scoring:** `confirmed_critical + skill_only_critical - baseline_only_critical - severity_disagreements`. "
                 "All terms are CRITICAL-only for unit consistency. The baseline-only penalty makes coverage gaps visible: "
                 "a model that suppresses real bugs the baseline caught scores lower, even if it found other bugs the baseline missed.")
    lines.append("")

    # Honest read: dynamic narrative based on scores
    sorted_scores = sorted(scores.items(), key=lambda x: -x[1])
    winner_model, winner_score = sorted_scores[0]
    lines.append("**Honest read:** ", )
    # Build per-model summary for the honest read
    model_summaries = []
    for mk in model_names:
        confirmed = confirmed_per_model[mk]
        soc = 0
        boc = 0
        for svb in skill_vs_baseline:
            if svb["model"] == mk:
                soc = svb["skill_only_critical"] if isinstance(svb["skill_only_critical"], int) else 0
                boc = svb["baseline_only_critical"] if isinstance(svb["baseline_only_critical"], int) else 0
                break
        net = soc - boc
        if net > 0:
            model_summaries.append(f"{mk} gained {net} critical coverage")
        elif net < 0:
            model_summaries.append(f"{mk} lost {abs(net)} critical coverage")
        else:
            model_summaries.append(f"{mk} broke even on criticals")
    # Determine if there's a clear winner or a tie
    if len(sorted_scores) > 1 and sorted_scores[0][1] == sorted_scores[1][1]:
        tied = [m for m, s in sorted_scores if s == sorted_scores[0][1]]
        lines.append(f"{', '.join(tied)} tie for the top score ({winner_score}). "
                     "The skill helps differently per model — see the per-model read above for the tradeoff details.")
    else:
        lines.append(f"{winner_model} wins clearly with score {winner_score}. ")
        # Describe runner-up situation
        runner_up, runner_score = sorted_scores[1]
        if runner_score == winner_score:
            lines.append(f"Tied with {runner_up}.")
        else:
            lines.append(f"{runner_up} follows at {runner_score}.")
        lines.append(" The skill helps differently per model — see the per-model read above for the tradeoff details.")
    lines.append("")

    return "\n".join(lines)
