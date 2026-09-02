"""
Language-agnostic sanitization for the distillation process.

Contains sanitization helpers, regex patterns, and the translation table
for generalizing C/kernel-specific terms.
"""

import re
import sys

# Translation table for generalizing C/kernel-specific terms
SANITIZE_REPLACEMENTS = {
    "BUG_ON": "fatal assertion",
    "WARN_ON": "warning assertion",
    "READ_ONCE": "unsynchronized read",
    "WRITE_ONCE": "unsynchronized write",
    "spin_lock": "lock primitive",
    "mutex": "lock primitive",
    "volatile": "implicit language semantics",
    "sysfs": "system interface",
    "procfs": "system interface",
    "debugfs": "system interface",
    "ioctl": "interface call",
    "kmalloc": "manual allocation",
    "kfree": "manual deallocation",
    "#ifdef": "compile-time conditional",
    "#ifndef": "compile-time conditional",
    "#define": "compile-time definition",
    "typedef": "type alias",
    "noinline": "no-optimization attribute",
    "inline": "premature optimization hint",
    "copy_to_user": "boundary crossing",
    "copy_from_user": "boundary crossing",
    "rcu_dereference": "lock-free access",
    "strlcpy": "string copy",
    "strscpy": "string copy",
    "IS_ERR": "error check",
    "ERR_PTR": "error pointer",
    "GFP_KERNEL": "allocation flag",
    "module_alloc": "module allocation",
}

# Regex patterns for sanitization
_QUOTE_SPAN_RE = re.compile(r'("[^"]*"|"[^"]*"|`[^`]*`)')
_TABLE_SEP_RE = re.compile(r"^\s*\|[\s:|-]+\|?\s*$")


def generalize_trigger(trigger: str) -> str:
    """Apply SANITIZE_REPLACEMENTS to generalize C-specific terms in triggers.

    This pre-generalizes triggers before they're formatted into the prompt,
    ensuring C-specific terms are removed at the source.
    """
    if not trigger:
        return trigger
    result = trigger
    for term, replacement in SANITIZE_REPLACEMENTS.items():
        result = result.replace(term, replacement)
    return result


def sanitize_skill(text: str) -> str:
    """Replace forbidden C/kernel terms in unquoted text, preserving quotes and inline code."""
    lines = text.splitlines(keepends=True)
    out = []
    for line in lines:
        if line.lstrip().startswith("> "):
            out.append(line)
            continue
        parts = _QUOTE_SPAN_RE.split(line)
        for i, part in enumerate(parts):
            if i % 2 == 1:
                continue
            for term, repl in SANITIZE_REPLACEMENTS.items():
                part = part.replace(term, repl)
            parts[i] = part
        out.append("".join(parts))
    return "".join(out)


def _strip_markdown_tables(text: str) -> str:
    """Convert markdown tables to structured bullet lists."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if (
            stripped.startswith("|")
            and i + 1 < len(lines)
            and _TABLE_SEP_RE.match(lines[i + 1].strip())
        ):
            header_cells = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                row_cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                for h, val in zip(header_cells, row_cells, strict=False):
                    out.append(f"- **{h}**: {val}\n")
                out.append("\n")
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return "".join(out)


# ---- Severity rebalancing ----

_SOFT_WORDS = {
    "should",
    "consider",
    "prefer",
    "may",
    "might",
    "could",
    "typically",
    "usually",
    "often",
    "generally",
    "common",
    "convention",
    "style",
    "readability",
    "clarity",
    "consistency",
    "cleaner",
    "simpler",
    "better",
    "naming",
    "comment",
    "documentation",
    "optional",
    "minor",
}
_HARD_WORDS = {
    "must",
    "never",
    "always",
    "crash",
    "corrupt",
    "overflow",
    "leak",
    "null",
    "deref",
    "race",
    "deadlock",
    "undefined",
    "unsafe",
    "critical",
    "security",
    "loss",
    "silent",
    "corruption",
    "double",
    "free",
    "buffer",
    "bounds",
    "injection",
    "dangling",
    "stale",
    "uninitialized",
    "atomic",
    "lifetime",
    "use-after",
}

_SEVERITY_LADDER = ["reject", "request-changes", "nitpick"]

_SEVERITY_ALIASES = {
    "request": "request-changes",
    "request_change": "request-changes",
    "requestchanges": "request-changes",
    "critical": "reject",
    "blocker": "reject",
    "must-fix": "reject",
    "cosmetic": "nitpick",
    "style": "nitpick",
    "minor": "nitpick",
    "trivial": "nitpick",
    "optional": "nitpick",
}


def _soft_language_score(text: str) -> int:
    """Higher = more likely over-rated as reject (softer language)."""
    words = set(re.findall(r"\b\w+(?:-\w+)?\b", text.lower()))
    return len(words & _SOFT_WORDS) - len(words & _HARD_WORDS)


def rebalance_severities(skill_text: str, calibration: dict) -> str:
    """Rebalance severity labels to match the corpus distribution.

    Model-agnostic post-processor: works on any model's output.  When a
    severity bucket is over-represented relative to the corpus baseline,
    triggers are demoted through the severity ladder (reject →
    request-changes → nitpick).  Triggers with softer language are demoted
    first; triggers with hard-language terms (crash, overflow, race, …) are
    kept at their original severity.

    Returns the skill text unchanged when calibration data is missing, when
    fewer than two triggers are found, or when the distribution is already
    within tolerance.
    """
    if not calibration:
        return skill_text

    lines = skill_text.splitlines()

    # Parse trigger blocks: each entry is a mutable dict tracking the
    # current severity, the line index of the **Severity** label, and a
    # soft-language score derived from the full block text.
    triggers: list[dict] = []
    i = 0
    while i < len(lines):
        if re.match(r"^\s*- \*\*Trigger[:*]+", lines[i]):
            block_text = lines[i]
            j = i + 1
            sev_line = None
            severity = None
            while j < len(lines):
                if re.match(r"^\s*- \*\*Trigger[:*]+", lines[j]):
                    break
                if re.match(r"^#{2,4}\s", lines[j]):
                    break
                block_text += "\n" + lines[j]
                sm = re.match(r"^\s*-?\s*\*\*Severity[:*]+\s*(\w+(?:[-_\u2011]\w+)*)", lines[j])
                if sm:
                    severity = sm.group(1).lower().replace("\u2011", "-")
                    severity = _SEVERITY_ALIASES.get(severity, severity)
                    sev_line = j
                    break
                j += 1
            if severity and sev_line is not None:
                triggers.append(
                    {
                        "sev_line": sev_line,
                        "severity": severity,
                        "raw_original": sm.group(1).lower().replace("\u2011", "-"),
                        "score": _soft_language_score(block_text),
                    }
                )
            i = j + 1 if severity else j
        else:
            i += 1

    if len(triggers) < 2:
        return skill_text

    # Current distribution
    current: dict[str, int] = {}
    for t in triggers:
        current[t["severity"]] = current.get(t["severity"], 0) + 1

    # Target distribution from calibration, normalised to the three
    # severities the skill actually uses.
    corpus_dist = calibration.get("corpus_stats", {}).get("severity_distribution", {})
    total_corpus_pct = sum(corpus_dist.get(s, {}).get("percentage", 0) for s in _SEVERITY_LADDER)
    if total_corpus_pct == 0:
        return skill_text

    total_triggers = len(triggers)
    target: dict[str, int] = {}
    for s in _SEVERITY_LADDER:
        ratio = corpus_dist.get(s, {}).get("percentage", 0) / total_corpus_pct
        target[s] = round(total_triggers * ratio)

    # Fix rounding so the counts sum to total_triggers.
    _fix_target_rounding(target, total_triggers, _SEVERITY_LADDER)

    if all(current.get(s, 0) == target.get(s, 0) for s in _SEVERITY_LADDER):
        return skill_text

    # Demote through the ladder.  For each severity from harshest to mildest,
    # if it is over target, demote the excess to the next-lower rung.
    # Triggers demoted in one step become candidates for further demotion in
    # the next, so the softest reject triggers can travel all the way to
    # nitpick — which is correct: they were the most over-rated.
    for idx in range(len(_SEVERITY_LADDER) - 1):
        sev = _SEVERITY_LADDER[idx]
        next_sev = _SEVERITY_LADDER[idx + 1]
        excess = sum(1 for t in triggers if t["severity"] == sev) - target.get(sev, 0)
        if excess <= 0:
            continue
        candidates = sorted(
            [t for t in triggers if t["severity"] == sev],
            key=lambda t: -t["score"],
        )
        for t in candidates[:excess]:
            t["severity"] = next_sev

    # Promote through the ladder, iterating until stable.  Each
    # iteration moves triggers up one rung; multiple iterations let a
    # trigger climb from nitpick all the way to reject when both higher
    # rungs are under target.  Triggers with harder language (lower
    # score) are promoted first — they were the most likely under-rated.
    for _ in range(len(_SEVERITY_LADDER)):
        promoted = False
        for idx in range(len(_SEVERITY_LADDER) - 1):
            sev = _SEVERITY_LADDER[idx]
            lower_sev = _SEVERITY_LADDER[idx + 1]
            deficit = target.get(sev, 0) - sum(1 for t in triggers if t["severity"] == sev)
            if deficit <= 0:
                continue
            candidates = sorted(
                [t for t in triggers if t["severity"] == lower_sev],
                key=lambda t: t["score"],
            )
            for t in candidates[:deficit]:
                t["severity"] = sev
                promoted = True
        if not promoted:
            break

    # Apply changes to the text: rewrite any label whose final severity
    # differs from the raw original (covers both demotion and alias
    # normalisation, e.g.  request → request-changes).
    result_lines = list(lines)
    changed = 0
    for t in triggers:
        if t["severity"] != t["raw_original"]:
            result_lines[t["sev_line"]] = re.sub(
                r"(\*\*Severity[:*]+\s*)[\w\u2011-]+",
                f"\\g<1>{t['severity']}",
                result_lines[t["sev_line"]],
            )
            changed += 1

    if changed:
        print(
            f"  rebalance: {changed} trigger(s) relabelled ({current} → {target})",
            file=sys.stderr,
        )

    result = "\n".join(result_lines)
    if skill_text.endswith("\n") and not result.endswith("\n"):
        result += "\n"
    return result


def _fix_target_rounding(target: dict[str, int], total: int, sevs: list[str]) -> None:
    """Adjust target counts in-place so they sum to *total*."""
    while sum(target.values()) < total:
        deficits = {
            s: target[s] - total * target.get(s, 0) / max(sum(target.values()), 1) for s in sevs
        }
        target[max(deficits, key=lambda s: -deficits[s])] += 1
    while sum(target.values()) > total:
        surpluses = {s: target[s] for s in sevs}
        target[max(surpluses, key=surpluses.get)] -= 1
