"""
extract_interviews.py — LLM extraction: interview passages → review moves.

Calls an OpenAI-compatible chat completions endpoint.
One passage per call. Returns structured JSON.

The prompt asks the LLM to extract "review moves" from interview transcripts:
  trigger  — what specific moment or statement prompted the principle
  principle — the general reviewing rule (language-agnostic)
  response  — how Torvalds phrases it (tone/voice preserved)
  severity  — low | medium | high | critical
  category  — one of the 13 categories from models.py
"""

from __future__ import annotations

import json
import random
import time
import urllib.request
import urllib.error
from pathlib import Path

from . import config
from .models import CATEGORIES, SEVERITIES


SYSTEM_PROMPT = """\
You are analyzing an interview passage where Linus Torvalds discusses code review,
engineering principles, or technical decision-making.

Your job: extract the "review moves" — the actionable reviewing principles expressed
in this passage.

A review move has five fields:
- trigger: what specific moment, statement, or question in the interview prompted this principle (specific, concrete)
- principle: the general reviewing rule being applied (abstract it away from C/kernel specifics — make it language-agnostic so it applies to any code review)
- response: how Torvalds phrases his feedback (use his actual words where possible — the tone IS the signal)
- severity: one of "low", "medium", "high", "critical"
- category: one of: api-stability, performance, correctness, complexity, style, process, error-handling, concurrency, memory-safety, abstraction, testing, documentation, other

Rules:
- One passage may contain zero, one, or many review moves.
- If the passage has no review content (e.g., it's just a question without a substantive answer, or pure discussion with no reviewing principle), return an empty moves array.
- The principle MUST be abstracted away from C/kernel specifics. "Don't change a public struct without updating callers" becomes "Don't change a public interface without updating all callers".
- Keep the response field in Torvalds' own words — do not paraphrase the tone away.
- Be conservative: only extract a move if there is a clear, identifiable reviewing principle.
- Severity in interviews reflects the importance Linus places on the principle:
  - critical: fundamental principles that cannot be compromised (e.g., correctness, API stability)
  - high: important principles that should rarely be violated (e.g., performance, concurrency safety)
  - medium: guidelines that matter but have exceptions (e.g., style, complexity)
  - low: nice-to-have considerations (e.g., documentation, minor style points)

Return ONLY valid JSON, no markdown fences, in this exact format:
{"moves": [{"trigger": "...", "principle": "...", "response": "...", "severity": "...", "category": "..."}]}"""


def _call_llm(passage_text: str, passage_id: str, retries: int = None) -> dict:
    """Call the LLM API for one passage. Returns parsed JSON dict."""
    retries = retries if retries is not None else config.MAX_RETRIES

    user_content = (
        f"Passage ID: {passage_id}\n\n"
        f"{passage_text[:8000]}"
    )

    payload = {
        "model": config.MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.1,
    }

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        config.CHAT_URL,
        data=body,
        headers=config.headers(),
        method="POST",
    )

    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=config.REQUEST_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"]
                return _parse_json_response(content)
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429:
                wait = config.RETRY_DELAY * (attempt + 1) * 2 + random.uniform(0, config.RETRY_DELAY)
                time.sleep(wait)
            elif e.code >= 500:
                time.sleep(config.RETRY_DELAY * (attempt + 1) + random.uniform(0, config.RETRY_DELAY))
            else:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = e
            time.sleep(config.RETRY_DELAY * (attempt + 1) + random.uniform(0, config.RETRY_DELAY))
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            last_err = e
            time.sleep(config.RETRY_DELAY)

    raise RuntimeError(f"LLM call failed after {retries} retries: {last_err}")


def _parse_json_response(content: str) -> dict:
    """Parse JSON from LLM response, handling markdown fences."""
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    text = text.strip()
    return json.loads(text)


def extract_moves_from_passage(passage: dict) -> dict:
    """Extract review moves from one interview passage. Returns a dict with moves list."""
    passage_id = passage["passage_id"]
    source_file = passage["source_file"]
    text = passage["text"]

    try:
        result = _call_llm(text, passage_id)
        moves = result.get("moves", [])
        return {
            "passage_id": passage_id,
            "source_file": source_file,
            "moves": moves,
        }
    except Exception as e:
        return {
            "passage_id": passage_id,
            "source_file": source_file,
            "moves": [],
            "error": str(e),
        }


def _load_checkpoint(checkpoint_path: Path) -> set[str]:
    """Load passage IDs that have already been processed."""
    if not checkpoint_path.exists():
        return set()

    processed = set()
    with open(checkpoint_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                processed.add(record["passage_id"])
            except (json.JSONDecodeError, KeyError):
                continue
    return processed


def _load_skip_list(skip_list_path: Path) -> set[str]:
    """Load passage IDs that had zero moves (skip list)."""
    if not skip_list_path.exists():
        return set()

    skipped = set()
    with open(skip_list_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            skipped = set(data.get("skipped_passages", []))
        except (json.JSONDecodeError, KeyError):
            pass
    return skipped


def extract_interviews(input_path: str, output_path: str, model: str = "gpt-oss-120b") -> int:
    """
    Extract review moves from interview passages.

    Args:
        input_path: Path to JSONL file with classified passages
        output_path: Path to write JSONL output (one JSON object per line)
        model: Model name to use (default: gpt-oss-120b)

    Returns:
        Count of extracted moves
    """
    input_file = Path(input_path)
    output_file = Path(output_path)
    checkpoint_path = output_file.parent / "interview_checkpoint.jsonl"
    skip_list_path = output_file.parent / "interview_skip_list.json"

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Load checkpoint and skip list for resume logic
    processed_ids = _load_checkpoint(checkpoint_path)
    skipped_ids = _load_skip_list(skip_list_path)

    # Read all passages
    passages = []
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                passage = json.loads(line)
                passages.append(passage)
            except json.JSONDecodeError:
                continue

    total = len(passages)
    done = 0
    errors = 0
    moves_count = 0
    checkpoint_batch = []

    # Open output file in append mode to support resume
    with open(output_file, "a", encoding="utf-8") as f:
        for passage in passages:
            passage_id = passage["passage_id"]

            # Skip already processed passages (resume logic)
            if passage_id in processed_ids:
                done += 1
                continue

            # Skip passages that had zero moves previously (skip list)
            if passage_id in skipped_ids:
                done += 1
                continue

            result = extract_moves_from_passage(passage)
            f.write(json.dumps(result, ensure_ascii=False) + "\n")
            f.flush()
            done += 1

            if result.get("error"):
                errors += 1
            else:
                moves = result.get("moves", [])
                if moves:
                    moves_count += len(moves)
                else:
                    # Add to skip list for zero-move passages
                    checkpoint_batch.append(passage_id)

            # Checkpoint every 10 passages
            if done % 10 == 0:
                # Write checkpoint
                with open(checkpoint_path, "a", encoding="utf-8") as cf:
                    for pid in checkpoint_batch:
                        cf.write(json.dumps({"passage_id": pid}) + "\n")
                checkpoint_batch = []

                print(f"  {done}/{total} — {moves_count} moves, {errors} errors")

    # Final checkpoint for remaining passages
    if checkpoint_batch:
        with open(checkpoint_path, "a", encoding="utf-8") as cf:
            for pid in checkpoint_batch:
                cf.write(json.dumps({"passage_id": pid}) + "\n")

    # Update skip list with zero-move passages
    if checkpoint_batch:
        existing_skips = list(skipped_ids)
        existing_skips.extend(checkpoint_batch)
        with open(skip_list_path, "w", encoding="utf-8") as sf:
            json.dump({"skipped_passages": existing_skips}, sf, indent=2)

    print(f"done: {done} passages, {moves_count} moves, {errors} errors")
    return moves_count


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract review moves from interview passages"
    )
    parser.add_argument(
        "--input",
        default="data/interviews_classified.jsonl",
        help="Input JSONL file with classified passages (default: data/interviews_classified.jsonl)"
    )
    parser.add_argument(
        "--output",
        default="data/interview_moves.jsonl",
        help="Output JSONL file path (default: data/interview_moves.jsonl)"
    )
    parser.add_argument(
        "--model",
        default="gpt-oss-120b",
        help="Model name to use (default: gpt-oss-120b)"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint, skipping already-processed passages"
    )

    args = parser.parse_args()

    count = extract_interviews(args.input, args.output, args.model)
    print(f"Extracted {count} moves total")