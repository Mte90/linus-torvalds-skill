#!/usr/bin/env python3
"""Generate variant tables for README and docs.

Reads word counts from skill/soul files and token/timeout values from profiles.py.
Outputs markdown tables for documentation.

Usage:
    python scripts/generate_variant_table.py
    python scripts/generate_variant_table.py --section skill-table
    python scripts/generate_variant_table.py --section soul-table
    python scripts/generate_variant_table.py --section profile-table
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from torvalds_skill.profiles import get_profile, get_profile_table


def word_count(path: Path) -> int:
    """Count words in a file."""
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8").split())


ROOT = Path(__file__).resolve().parent.parent


def get_variant_stats() -> list[dict]:
    """Get word counts for all skill/soul variants."""
    variants = [
        ("gpt-oss-120b", "linus-torvalds-skill/SKILL.md", "soul/soul.md"),
        ("glm5.2", "linus-torvalds-skill/SKILL-GLM.md", "soul/soul-glm.md"),
        ("mistral-small-4-119b", "linus-torvalds-skill/SKILL-Mistral.md", "soul/soul-mistral.md"),
        ("qwen3.8-27b", "linus-torvalds-skill/SKILL-Qwen.md", "soul/soul-qwen.md"),
    ]

    stats = []
    for model, skill_path, soul_path in variants:
        stats.append(
            {
                "model": model,
                "skill_words": word_count(ROOT / skill_path),
                "soul_words": word_count(ROOT / soul_path),
            }
        )
    return stats


def skill_table() -> str:
    """Generate skill variant table."""
    stats = get_variant_stats()
    lines = [
        "| Model | Words | Notes |",
        "|---|---|---|",
    ]
    for s in stats:
        notes = {
            "gpt-oss-120b": "Balanced, recommended default",
            "glm5.2": "Reasoning model, most thorough",
            "mistral-small-4-119b": "Fastest, YAML formatted",
            "qwen3.8-27b": "Balanced, practical",
        }
        lines.append(f"| {s['model']} | {s['skill_words']} | {notes[s['model']]} |")
    return "\n".join(lines)


def soul_table() -> str:
    """Generate soul variant table."""
    stats = get_variant_stats()
    lines = [
        "| Model | Words |",
        "|---|---|",
    ]
    for s in stats:
        lines.append(f"| {s['model']} | {s['soul_words']} |")
    return "\n".join(lines)


def profile_table() -> str:
    """Generate model profile table from profiles.py."""
    profiles = get_profile_table()
    lines = [
        "| Model | Timeout (s) | Max tokens | Parallel workers | Distill mode |",
        "|---|---|---|---|---|",
    ]
    for name, profile in profiles:
        lines.append(
            f"| {name} | {profile.timeout} | {profile.max_tokens} | "
            f"{profile.parallel_workers} | {profile.distill_mode} |"
        )
    return "\n".join(lines)


def full_table() -> str:
    """Generate complete variant comparison table."""
    stats = get_variant_stats()
    profiles = {name: get_profile(name) for name, _, _ in stats}

    lines = [
        "| Model | Skill words | Soul words | Timeout (s) | Distill mode |",
        "|---|---|---|---|---|",
    ]
    for s in stats:
        p = profiles[s["model"]]
        lines.append(
            f"| {s['model']} | {s['skill_words']} | {s['soul_words']} | "
            f"{p.timeout} | {p.distill_mode} |"
        )
    return "\n".join(lines)


def main() -> None:
    """Generate tables based on command-line args."""
    section = sys.argv[1] if len(sys.argv) > 1 else "all"

    if section == "all":
        print("=== Skill Variant Table ===")
        print(skill_table())
        print()
        print("=== Soul Variant Table ===")
        print(soul_table())
        print()
        print("=== Model Profile Table ===")
        print(profile_table())
    elif section == "skill-table":
        print(skill_table())
    elif section == "soul-table":
        print(soul_table())
    elif section == "profile-table":
        print(profile_table())
    elif section == "full-table":
        print(full_table())
    else:
        print(f"Unknown section: {section}", file=sys.stderr)
        print(
            "Usage: generate_variant_table.py [all|skill-table|soul-table|profile-table|full-table]",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
