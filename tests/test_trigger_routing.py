"""Pin auto-detect routing per skill variant (Trigger Contract).

Regression: auto-dispatch once misrouted GLM and Mistral files to the
gpt-oss extractor (all-General output) because the What-to-look-for marker
exists in every variant. Routing keys on theme heading SHAPE, which is
variant-distinctive. These tests pin both the route and the outcome.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "report"))

from trigger_patterns import detect_style, extract_triggers

SKILL_DIR = Path(__file__).parent.parent / "linus-torvalds-skill"

# variant file -> (expected style, min triggers, max General allowed)
EXPECTED = {
    "SKILL.md": ("gpt-oss", 50, 5),
    "SKILL-GLM.md": ("glm", 40, 2),
    "SKILL-Mistral.md": ("mistral", 15, 2),
    "SKILL-Qwen.md": ("glm", 50, 5),
}


def _load(name):
    return (SKILL_DIR / name).read_text(encoding="utf-8")


def test_detect_style_per_variant():
    for name, (style, _, _) in EXPECTED.items():
        assert detect_style(_load(name)) == style, name


def test_auto_counts_and_themes():
    for name, (_, min_count, max_general) in EXPECTED.items():
        triggers = extract_triggers(_load(name))  # auto mode
        general = sum(1 for theme, _ in triggers if theme == "General")
        assert len(triggers) >= min_count, (name, len(triggers))
        assert general <= max_general, (name, general)


def test_numbered_dash_themes_route_glm():
    content = "#### Theme\u202f1 – Something\n\n- **Trigger**: do the thing\n"
    assert detect_style(content) == "glm"
    triggers = extract_triggers(content)
    assert len(triggers) == 1 and triggers[0][0] == "Something"


def test_three_hash_colon_themes_route_glm():
    content = "### Theme: Something\n\n- **Trigger**: do the thing\n"
    assert detect_style(content) == "glm"


def test_four_hash_colon_themes_route_gpt_oss():
    content = "#### Theme: Something\n\n  - **What to look for**: look here\n"
    assert detect_style(content) == "gpt-oss"


def test_level_bullets_without_themes_route_mistral():
    content = "### Level 1 – Things\n\n- **Do the thing**\n"
    assert detect_style(content) == "mistral"
