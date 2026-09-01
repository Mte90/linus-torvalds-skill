#!/usr/bin/env python3
"""
Programmatic diff of the three SKILL variants.

Analyzes SKILL.md, SKILL-GLM.md, and SKILL-Mistral.md to report:
- Section counts per variant
- Trigger counts per variant
- Severity label distributions
- Sections unique to one variant
- Severity discrepancies (same trigger, different severity)

Usage:
    python3 report/variant_divergence.py
"""

import re
import sys
from pathlib import Path
from collections import defaultdict


def read_skill_file(path: str) -> str:
    """Read a skill file and return its contents."""
    with open(path, 'r') as f:
        return f.read()


def count_sections(content: str) -> int:
    """Count markdown sections (## headers)."""
    return len(re.findall(r'^## ', content, re.MULTILINE))


def count_subsections(content: str) -> int:
    """Count subsections (### headers)."""
    return len(re.findall(r'^### ', content, re.MULTILINE))


def count_triggers(content: str) -> int:
    """Count trigger definitions (lines starting with '- **Trigger:**' or '- **Trigger**')."""
    # Match various trigger patterns across different variants
    # GLM/Mistral use "- **Trigger**:" (colon outside bold)
    # gpt-oss uses "- **Trigger:**" (colon inside bold)
    # Use a single pattern that matches both
    return len(re.findall(r'- \*\*Trigger[:\*]?\*\*[:\s]', content))


def count_themes(content: str) -> int:
    """Count theme definitions."""
    # Match various theme patterns
    patterns = [
        r'#### Theme \d+:',  # GLM style
        r'#### Theme [A-Z]',  # gpt-oss style
        r'#### Theme ',  # Mistral style (without colon to avoid regex error)
        r'- \*\*Theme\*\*:',  # Alternative
    ]
    count = 0
    for pattern in patterns:
        count += len(re.findall(pattern, content))
    return count


def extract_severity_labels(content: str) -> dict:
    """Extract severity label distribution."""
    severities = defaultdict(int)
    # Match both "- **Severity:** value" and "- **Severity** : value" formats
    for match in re.findall(r'- \*\*Severity[:\*]?\*\*[:\s]+(\S+)', content):
        severities[match] += 1
    return dict(severities)


def extract_severity_by_trigger(content: str) -> list:
    """Extract (trigger text, severity) pairs."""
    triggers = []
    # Find trigger blocks
    blocks = re.split(r'- \*\*Trigger:\*', content)[1:]  # Skip first split
    for block in blocks:
        # Extract trigger name (first line)
        trigger_match = re.match(r'\s*(.+?)(?:\n|$)', block)
        severity_match = re.search(r'- \*\*Severity:\*\* (\S+)', block)
        if trigger_match and severity_match:
            trigger_name = trigger_match.group(1).strip()[:50]  # Truncate for readability
            severity = severity_match.group(1)
            triggers.append((trigger_name, severity))
    return triggers


def find_unique_sections(content: str, variant_name: str) -> list:
    """Find sections that appear to be unique to this variant."""
    # Check for specific content patterns unique to each variant
    unique_patterns = {
        'gpt-oss': [
            ('Decision Cards', '## Decision Cards'),
            ('Severity Calibration', '## Severity Calibration'),
            ('Cross-File Review', '## Cross-File Review'),
        ],
        'GLM': [
            ('Root Cause Theme', 'Theme 6: Root Cause'),
            ('Interface Honesty Theme', 'Theme 7: Interface Honesty'),
            ('Testing Theme', 'Theme 13: Testing'),
        ],
        'mistral': [
            ('Anti-Patterns', '## Anti-Patterns'),
            ('YAML Frontmatter', '```yaml'),
        ],
    }
    unique = []
    patterns = unique_patterns.get(variant_name, [])
    for name, pattern in patterns:
        if pattern in content:
            unique.append(name)
    return unique


def find_severity_discrepancies(triggers_a: list, triggers_b: list, name_a: str, name_b: str) -> list:
    """Find triggers with different severity labels between two variants."""
    discrepancies = []
    # Simple fuzzy matching on trigger names
    for trigger_a, sev_a in triggers_a:
        for trigger_b, sev_b in triggers_b:
            # Check if triggers are similar (simple substring match)
            if trigger_a.lower() in trigger_b.lower() or trigger_b.lower() in trigger_a.lower():
                if sev_a != sev_b:
                    discrepancies.append({
                        'trigger': trigger_a,
                        f'{name_a}_severity': sev_a,
                        f'{name_b}_severity': sev_b,
                    })
    return discrepancies


def main():
    """Main entry point."""
    base_path = Path(__file__).parent.parent / 'linus-torvalds-skill'
    
    files = {
        'gpt-oss-120b': base_path / 'SKILL.md',
        'glm5.2': base_path / 'SKILL-GLM.md',
        'mistral': base_path / 'SKILL-Mistral.md',
    }
    
    # Check files exist
    for name, path in files.items():
        if not path.exists():
            print(f"Error: {path} not found", file=sys.stderr)
            sys.exit(1)
    
    # Read all files
    contents = {name: read_skill_file(path) for name, path in files.items()}
    
    # Print header
    print("=" * 80)
    print("TORVALDS SKILL VARIANT DIVERGENCE REPORT")
    print("=" * 80)
    print()
    
    # Section counts
    print("## Section Counts")
    print()
    print(f"| Variant | Sections | Subsections | Triggers | Themes |")
    print(f"|---|---|---|---|---|")
    for name, content in contents.items():
        sections = count_sections(content)
        subsections = count_subsections(content)
        triggers = count_triggers(content)
        themes = count_themes(content)
        print(f"| {name} | {sections} | {subsections} | {triggers} | {themes} |")
    print()
    
    # Word counts
    print("## Word Counts")
    print()
    print(f"| Variant | Words |")
    print(f"|---|---|")
    for name, content in contents.items():
        words = len(content.split())
        print(f"| {name} | {words:,} |")
    print()
    
    # Severity distributions
    print("## Severity Distributions")
    print()
    for name, content in contents.items():
        severities = extract_severity_labels(content)
        print(f"**{name}**:")
        for sev, count in sorted(severities.items(), key=lambda x: -x[1]):
            print(f"  - {sev}: {count}")
        print()
    
    # Unique sections
    print("## Unique Sections by Variant")
    print()
    for name, content in contents.items():
        unique = find_unique_sections(content, name)
        if unique:
            print(f"**{name}** has:")
            for item in unique:
                print(f"  - {item}")
            print()
    
    # Severity discrepancies
    print("## Severity Discrepancies")
    print()
    print("Triggers with different severity assignments:")
    print()
    
    all_triggers = {name: extract_severity_by_trigger(content) for name, content in contents.items()}
    
    # Compare pairs
    pairs = [
        ('gpt-oss-120b', 'glm5.2', all_triggers['gpt-oss-120b'], all_triggers['glm5.2']),
        ('gpt-oss-120b', 'mistral', all_triggers['gpt-oss-120b'], all_triggers['mistral']),
        ('glm5.2', 'mistral', all_triggers['glm5.2'], all_triggers['mistral']),
    ]
    
    for name_a, name_b, triggers_a, triggers_b in pairs:
        discrepancies = find_severity_discrepancies(triggers_a, triggers_b, name_a, name_b)
        if discrepancies:
            print(f"**{name_a} vs {name_b}** ({len(discrepancies)} discrepancies):")
            for d in discrepancies[:5]:  # Show first 5
                print(f"  - '{d['trigger']}': {d[f'{name_a}_severity']} vs {d[f'{name_b}_severity']}")
            if len(discrepancies) > 5:
                print(f"  ... and {len(discrepancies) - 5} more")
            print()
    
    # Markdown table output
    print("=" * 80)
    print("SUMMARY TABLE (Markdown)")
    print("=" * 80)
    print()
    print("| Variant | Words | Sections | Triggers | Themes | Unique Features |")
    print("|---|---|---|---|---|---|")
    for name, content in contents.items():
        words = len(content.split())
        sections = count_sections(content)
        triggers = count_triggers(content)
        themes = count_themes(content)
        unique = ', '.join(find_unique_sections(content, name)[:3])
        if not unique:
            unique = '-'
        print(f"| {name} | {words:,} | {sections} | {triggers} | {themes} | {unique} |")
    print()
    
    print("Done.")


if __name__ == '__main__':
    main()