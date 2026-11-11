"""Pin auto-detect routing per skill variant (Trigger Contract).

Regression: auto-dispatch once misrouted GLM and Mistral files to the
gpt-oss extractor (all-General output) because the What-to-look-for marker
exists in every variant. Routing keys on theme heading SHAPE, which is
variant-distinctive. These tests pin both the route and the outcome.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "report"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trigger_patterns import detect_style, extract_triggers

from torvalds_skill.skill_paths import skill_path

# variant file -> (expected style, min triggers, max General allowed)
# qwen uses ### Tier N: headings (model non-compliance fallback);
# detect_style routes it to the tier extractor, not glm.
EXPECTED = {
    "gpt-oss": ("glm", 30, 5),
    "glm": ("glm", 40, 2),
    "mistral": ("glm", 30, 0),
    "qwen": ("tier", 30, 0),
}


def _load(variant):
    model_map = {
        "gpt-oss": "gpt-oss-120b",
        "glm": "glm5.2",
        "mistral": "mistral-small-4-119b",
        "qwen": "qwen3.8-27b",
    }
    return skill_path(model_map[variant]).read_text(encoding="utf-8")


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
    # 3-hash colon themes (Mistral output uses glm trigger format)
    content = "### Theme: Something\n\n- **Trigger**: do the thing\n"
    assert detect_style(content) == "glm"


def test_four_hash_colon_themes_route_glm():
    # 4-hash colon themes (GLM two-stage output with **Trigger**:)
    content = "#### Theme: Something\n\n- **Trigger**: do the thing\n"
    assert detect_style(content) == "glm"


def test_level_bullets_without_themes_route_mistral():
    content = "### Level 1 – Things\n\n- **Do the thing**\n"
    assert detect_style(content) == "mistral"


def test_trigger_colon_inside_bold_extracted():
    # gpt-oss sometimes places the colon inside the bold markers
    # (**Trigger:** instead of **Trigger**:); both must extract.
    content = "#### Theme 1 – Something\n\n- **Trigger:** do the thing\n"
    triggers = extract_triggers(content)
    assert len(triggers) == 1
    assert triggers[0][0] == "Something"
    assert triggers[0][1] == "do the thing"


def test_trigger_colon_outside_bold_extracted():
    # canonical format (**Trigger**:); regression guard
    content = "#### Theme 1 – Something\n\n- **Trigger**: do the thing\n"
    triggers = extract_triggers(content)
    assert len(triggers) == 1
    assert triggers[0][1] == "do the thing"


def test_bare_numbered_headings_extract_themes():
    # SKILL-Qwen.md uses bare numbered sub-headings (#### N. Title) without
    # (Theme: name) suffix — these must be recognized as theme delimiters.
    # Must include a Level heading for detect_style to route to glm extractor.
    content = (
        "### Level 1 – Global Invariants\n\n"
        "#### 1. Data-Structure Hygiene\n\n"
        "- **Trigger**: special case handling\n"
    )
    triggers = list(extract_triggers(content))
    assert len(triggers) == 1
    assert triggers[0][0] == "Data-Structure Hygiene"
    assert triggers[0][1] == "special case handling"


def test_level_headings_as_themes():
    # Level headings (### Level N – Name) should also act as theme delimiters
    # for triggers directly under a Level (with no #### N. sub-heading).
    content = "### Level 1 – Global Invariants\n\n- **Trigger**: breaking API\n"
    triggers = list(extract_triggers(content))
    assert len(triggers) == 1
    assert triggers[0][0] == "Global Invariants"
    assert triggers[0][1] == "breaking API"


def test_tier_headings_route_tier():
    # ### Tier N: headings (model non-compliance fallback) route to tier extractor
    content = "### Tier 1: Global Invariants\n\n- **Breaking API** – changes signatures\n"
    assert detect_style(content) == "tier"


def test_tier_bullets_extracted_with_theme():
    content = (
        "### Tier 1: Global Invariants\n\n- **Breaking public behavior** – changes to signatures.\n"
    )
    triggers = list(extract_triggers(content))
    assert len(triggers) == 1
    assert triggers[0][0] == "Global Invariants"
    assert triggers[0][1] == "Breaking public behavior"


def test_tier_subsection_updates_theme():
    content = (
        "### Tier 1: Global Invariants\n\n"
        "#### API Stability\n\n"
        "- **Breaking API** – changes signatures\n"
    )
    triggers = list(extract_triggers(content))
    assert len(triggers) == 1
    assert triggers[0][0] == "API Stability"
    assert triggers[0][1] == "Breaking API"


def test_tier_exits_on_h2_heading():
    # Bullets after a ## (non-###) heading must NOT be captured
    content = (
        "### Tier 1: Global Invariants\n\n"
        "- **In tier** – desc\n\n"
        "## Severity Scale\n\n"
        "- **After tier** – should not appear\n"
    )
    triggers = list(extract_triggers(content))
    assert len(triggers) == 1
    assert triggers[0][1] == "In tier"


def test_tier_skips_indented_field_labels():
    # Indented **Type:**/**Severity:**/**Example:** field labels must not be
    # extracted as triggers — only column-0 bullets count.
    content = (
        "### Tier 1: Global Invariants\n\n"
        "- **Breaking API** – changes signatures\n"
        "  **Type:** invariant-false  **Severity:** reject\n"
    )
    triggers = list(extract_triggers(content))
    assert len(triggers) == 1
    assert triggers[0][1] == "Breaking API"


def test_tier_en_dash_and_ascii_hyphen_both_match():
    en = "### Tier 1: T\n\n- **A** \u2013 desc\n"
    asc = "### Tier 1: T\n\n- **A** - desc\n"
    assert len(list(extract_triggers(en))) == 1
    assert len(list(extract_triggers(asc))) == 1
