"""Tests for scripts/generate_variant_table.py."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_word_count_matches_wc():
    """Verify word counts match wc -w output."""
    from scripts.generate_variant_table import word_count

    # Test SKILL.md
    skill_path = ROOT / "linus-torvalds-skill/SKILL.md"
    count = word_count(skill_path)

    # Run wc -w and compare
    result = subprocess.run(
        ["wc", "-w", str(skill_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    expected = int(result.stdout.split()[0])
    assert count == expected, f"SKILL.md: expected {expected}, got {count}"

    # Test SKILL-GLM.md
    glm_path = ROOT / "linus-torvalds-skill/SKILL-GLM.md"
    count = word_count(glm_path)
    result = subprocess.run(["wc", "-w", str(glm_path)], capture_output=True, text=True, check=True)
    expected = int(result.stdout.split()[0])
    assert count == expected, f"SKILL-GLM.md: expected {expected}, got {count}"

    # Test SKILL-Mistral.md
    mistral_path = ROOT / "linus-torvalds-skill/SKILL-Mistral.md"
    count = word_count(mistral_path)
    result = subprocess.run(
        ["wc", "-w", str(mistral_path)], capture_output=True, text=True, check=True
    )
    expected = int(result.stdout.split()[0])
    assert count == expected, f"SKILL-Mistral.md: expected {expected}, got {count}"


def test_variant_stats_populated():
    """Verify variant stats are populated with correct models."""
    from scripts.generate_variant_table import get_variant_stats

    stats = get_variant_stats()

    assert len(stats) == 4
    models = {s["model"] for s in stats}
    assert models == {"gpt-oss-120b", "glm5.2", "mistral-small-4-119b", "qwen3.8-27b"}

    # Verify word counts are positive for existing skill files
    # qwen3.8-27b may have 0 words if SKILL-Qwen.md doesn't exist yet (graceful skip)
    for s in stats:
        if s["model"] == "qwen3.8-27b":
            # Allow 0 words for qwen if skill file is absent (pending state)
            assert s["skill_words"] >= 0, f"{s['model']} skill words should be non-negative"
            assert s["soul_words"] >= 0, f"{s['model']} soul words should be non-negative"
        else:
            assert s["skill_words"] > 0, f"{s['model']} skill words should be positive"
            assert s["soul_words"] > 0, f"{s['model']} soul words should be positive"


def test_profile_table_matches_profiles_py():
    """Verify profile table matches profiles.py values."""
    from scripts.generate_variant_table import profile_table
    from torvalds_skill.profiles import get_profile

    table = profile_table()

    # Check that table contains expected models
    assert "glm5.2" in table
    assert "gpt-oss-120b" in table
    assert "mistral-small-4-119b" in table

    # Verify timeout values match profiles
    for model_name in ["glm5.2", "gpt-oss-120b", "mistral-small-4-119b"]:
        profile = get_profile(model_name)
        assert str(profile.timeout) in table, f"{model_name} timeout {profile.timeout} not in table"
        assert str(profile.max_tokens) in table, (
            f"{model_name} max_tokens {profile.max_tokens} not in table"
        )


def test_skill_table_format():
    """Verify skill table is valid markdown."""
    from scripts.generate_variant_table import skill_table

    table = skill_table()
    lines = table.strip().split("\n")

    # Check header
    assert lines[0] == "| Model | Words | Notes |"
    assert lines[1] == "|---|---|---|"

    # Check data rows
    assert len(lines) == 6  # header + separator + 4 data rows
    for line in lines[2:]:
        assert line.startswith("|")
        assert line.endswith("|")
        assert line.count("|") == 4  # 3 columns + 2 borders


def test_soul_table_format():
    """Verify soul table is valid markdown."""
    from scripts.generate_variant_table import soul_table

    table = soul_table()
    lines = table.strip().split("\n")

    # Check header
    assert lines[0] == "| Model | Words |"
    assert lines[1] == "|---|---|"

    # Check data rows
    assert len(lines) == 6  # header + separator + 4 data rows
    for line in lines[2:]:
        assert line.startswith("|")
        assert line.endswith("|")
        assert line.count("|") == 3  # 2 columns + 2 borders


def test_script_executes_without_error():
    """Verify the script runs without errors."""
    result = subprocess.run(
        [sys.executable, "scripts/generate_variant_table.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Script failed: {result.stderr}"
    assert "Skill Variant Table" in result.stdout
    assert "Soul Variant Table" in result.stdout
    assert "Model Profile Table" in result.stdout


def test_script_section_args():
    """Verify section arguments work."""
    for section in ["skill-table", "soul-table", "profile-table"]:
        result = subprocess.run(
            [sys.executable, "scripts/generate_variant_table.py", section],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Section {section} failed: {result.stderr}"
