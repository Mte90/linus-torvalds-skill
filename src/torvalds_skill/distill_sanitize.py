"""
Language-agnostic sanitization for the distillation process.

Contains sanitization helpers, regex patterns, and the translation table
for generalizing C/kernel-specific terms.
"""

import re

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
_TABLE_SEP_RE = re.compile(r'^\s*\|[\s:|-]+\|?\s*$')


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
        if line.lstrip().startswith('> '):
            out.append(line)
            continue
        parts = _QUOTE_SPAN_RE.split(line)
        for i, part in enumerate(parts):
            if i % 2 == 1:
                continue
            for term, repl in SANITIZE_REPLACEMENTS.items():
                part = part.replace(term, repl)
            parts[i] = part
        out.append(''.join(parts))
    return ''.join(out)


def _strip_markdown_tables(text: str) -> str:
    """Convert markdown tables to structured bullet lists."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith('|') and i + 1 < len(lines) and _TABLE_SEP_RE.match(lines[i + 1].strip()):
            header_cells = [c.strip() for c in stripped.strip('|').split('|')]
            i += 2
            while i < len(lines) and lines[i].strip().startswith('|'):
                row_cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                for h, val in zip(header_cells, row_cells):
                    out.append(f"- **{h}**: {val}\n")
                out.append("\n")
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return ''.join(out)