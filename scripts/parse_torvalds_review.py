#!/usr/bin/env python3
"""
parse_torvalds_review.py — Parse Linus Torvalds' free-form review emails into structured findings.

Uses GLM5.2 via the project's LLM infrastructure to extract structured findings from held-out
review records. Strips quoted email content, builds parse prompts, calls the LLM, and writes
JSON findings to output.

Usage:
    python3 scripts/parse_torvalds_review.py [--input data/heldout_reviews.jsonl] [--output data/heldout_findings.jsonl] [--model glm5.2]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Add project paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "report"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from typing import Any


def strip_quotes(text: str) -> str:
    """Remove quoted email content from Torvalds' review text.

    Strips:
    - Lines starting with '>' (quoted content from original email)
    - The 'On ... wrote:' preamble line

    Returns only Torvalds' actual prose.
    """
    lines = text.split("\n")
    cleaned_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        # Skip quoted lines (start with >)
        if stripped.startswith(">"):
            continue
        # Skip "On ... wrote:" preamble — can span two lines:
        #   On Tue, 13 Oct 2026 at 13:16, Laurent Pinchart
        #   <laurent.pinchart@ideasonboard.com> wrote:
        if re.match(r"^On\s+.*\bwrote:.*$", stripped):
            continue
        if re.match(r"^<.*@.*>\s*wrote:.*$", stripped):
            continue
        # First line of two-line preamble: "On <date> at <time>, <Name>"
        if re.match(r"^On\s+\w+,\s+\d+\s+\w+", stripped) and "wrote" not in stripped:
            continue
        # Keep Torvalds' actual text
        cleaned_lines.append(line)

    # Collapse multiple blank lines and strip trailing whitespace
    result = "\n".join(cleaned_lines)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def build_parse_prompt(review_text: str, patch_diff: str, patch_files: list[str]) -> str:
    """Construct a prompt asking the LLM to extract structured findings from the review.

    The prompt provides:
    - Cleaned review text (quotes stripped)
    - Patch diff and file list for context
    - Instructions for JSON output format

    Returns a prompt string ready for LLM consumption.
    """
    # Build file list context
    files_context = "\n".join(f"- {f}" for f in patch_files) if patch_files else "No files listed"

    prompt = f"""You are parsing Linus Torvalds' code review emails into structured findings.

TASK:
Extract technical code findings from Torvalds' review. For each issue, concern, or request he raises about the patch, create a finding object.

INPUT:

--- Review Text (Torvalds' actual words) ---
{review_text}
--- End Review ---

--- Patch Files ---
{files_context}
--- End Files ---

--- Patch Diff (context only) ---
{patch_diff[:3000]}
--- End Diff ---

OUTPUT FORMAT:
Return a JSON array of findings. Each finding must have:
- file: filename from the patch files list that the finding relates to, or null if general
- line_hint: line number or function name mentioned in the finding, or null
- issue: concise description of the issue Torvalds raised (1-2 sentences)
- severity: one of "reject" (Torvalds says don't apply), "request_changes" (wants changes), "discussion" (raises concern), "nitpick" (minor)
- quote: direct quote from Torvalds' text (max 200 characters)

RULES:
1. If the review contains NO technical code findings (e.g., it's a process/philosophy discussion), return an empty array []
2. Return ONLY the JSON array — no markdown fences, no prose, no explanations
3. Be faithful to Torvalds' actual words in the quote field
4. Map severity based on tone:
   - "reject" for explicit rejections ("I am *NOT* a fan", "don't apply", "broken setup")
   - "request_changes" for clear requests ("should probably be", "would also have to be fixed")
   - "discussion" for concerns/questions ("odd going on", "Maybe there's some reason")
   - "nitpick" for minor style/format issues

EXAMPLE OUTPUT:
[
  {{
    "file": "net/core/dev.c",
    "line_hint": null,
    "issue": "Torvalds agrees that local KASLR attacks are not a serious concern and suggests filename hashing should not use real secrets",
    "severity": "discussion",
    "quote": "Correct: local KASLR on its own is pretty much a nothing-burger."
  }}
]

Now parse the review above and return ONLY the JSON array."""

    return prompt


def parse_findings_json(response: str) -> list[dict[str, Any]]:
    """Extract the JSON array from the LLM response.

    Handles:
    - Markdown fences (```json ... ```)
    - Trailing prose after the JSON
    - Validation of required keys

    Returns empty list on parse failure with a warning to stderr.
    """
    # Strip markdown fences if present
    response = re.sub(r"^```json\s*", "", response.strip(), flags=re.MULTILINE)
    response = re.sub(r"\s*```$", "", response.strip(), flags=re.MULTILINE)

    # Try to find a JSON array in the response
    # Look for [...] pattern, handling nested braces
    array_match = re.search(r"\[.*\]", response, re.DOTALL)
    if array_match:
        json_str = array_match.group(0)
    else:
        print("Warning: No JSON array found in response", file=sys.stderr)
        return []

    try:
        findings = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"Warning: Failed to parse JSON: {e}", file=sys.stderr)
        return []

    # Validate structure
    if not isinstance(findings, list):
        print("Warning: Response is not an array", file=sys.stderr)
        return []

    required_keys = {"file", "line_hint", "issue", "severity", "quote"}
    valid_severities = {"reject", "request_changes", "discussion", "nitpick"}

    validated: list[dict[str, Any]] = []
    for i, finding in enumerate(findings):
        if not isinstance(finding, dict):
            print(f"Warning: Finding {i} is not an object", file=sys.stderr)
            continue

        # Check required keys
        missing = required_keys - set(finding.keys())
        if missing:
            print(f"Warning: Finding {i} missing keys: {missing}", file=sys.stderr)
            continue

        # Validate severity
        if finding["severity"] not in valid_severities:
            print(
                f"Warning: Finding {i} has invalid severity: {finding['severity']}", file=sys.stderr
            )
            continue

        # Type checks
        if finding["file"] is not None and not isinstance(finding["file"], str):
            print(f"Warning: Finding {i} file is not string or null", file=sys.stderr)
            continue
        if finding["line_hint"] is not None and not isinstance(finding["line_hint"], (str, int)):
            print(f"Warning: Finding {i} line_hint is not string/int or null", file=sys.stderr)
            continue
        if not isinstance(finding["issue"], str):
            print(f"Warning: Finding {i} issue is not a string", file=sys.stderr)
            continue
        if not isinstance(finding["quote"], str):
            print(f"Warning: Finding {i} quote is not a string", file=sys.stderr)
            continue

        validated.append(finding)

    return validated


def main() -> None:
    """Main entry point: process held-out reviews and extract findings."""
    parser = argparse.ArgumentParser(
        description="Parse Linus Torvalds' review emails into structured findings"
    )
    parser.add_argument(
        "--input",
        default="data/heldout_reviews.jsonl",
        help="Input JSONL file with review records (default: data/heldout_reviews.jsonl)",
    )
    parser.add_argument(
        "--output",
        default="data/heldout_findings.jsonl",
        help="Output JSONL file for findings (default: data/heldout_findings.jsonl)",
    )
    parser.add_argument(
        "--model",
        default="glm5.2",
        help="LLM model to use (default: glm5.2)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Import LLM infrastructure
    from llm_review import call_llm

    # Read input records
    records: list[dict[str, Any]] = []
    with open(input_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    total = len(records)

    # Open output for incremental writes so a crash mid-run keeps partial results
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as out_f:
        for i, record in enumerate(records):
            review_subject = record.get("review_subject", "unknown")
            review_text = record.get("review_text", "")
            patch_diff = record.get("patch_diff", "")
            patch_files = record.get("patch_files", [])

            # Strip quoted content
            cleaned_text = strip_quotes(review_text)

            # Build prompt
            prompt = build_parse_prompt(cleaned_text, patch_diff, patch_files)

            # Progress message
            print(f"[{i + 1}/{total}] Parsing review for {review_subject}...", file=sys.stderr)

            # Call LLM with error handling — GLM5.2 can return reasoning_only_response
            findings: list[dict[str, Any]] = []
            try:
                response = call_llm(args.model, prompt, timeout=2400)
                findings = parse_findings_json(response)
            except RuntimeError as e:
                print(f"  -> ERROR: LLM call failed: {e}", file=sys.stderr)
                findings = []
            except Exception as e:
                print(f"  -> ERROR: unexpected: {e}", file=sys.stderr)
                findings = []

            # Build output record
            result = {
                "review_message_id": record.get("review_message_id"),
                "review_subject": review_subject,
                "patch_subject": record.get("patch_subject"),
                "findings": findings,
                "finding_count": len(findings),
            }

            # Write incrementally
            out_f.write(json.dumps(result, ensure_ascii=False) + "\n")
            out_f.flush()

            # Report findings count
            print(f"  -> found {len(findings)} findings", file=sys.stderr)

            # Rate limit delay (2 seconds between calls)
            if i < total - 1:
                import time

                time.sleep(2)

    print(f"Wrote {total} records to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
