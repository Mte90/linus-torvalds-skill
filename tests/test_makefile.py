#!/usr/bin/env python3
"""
Test Makefile targets and state-hash skip logic.

Tests:
1. Makefile dry-run shows correct command chain
2. State-hash skip: identical inputs skip, changed skill re-runs
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = ROOT / "report"


def test_makefile_dry_run():
    """Test that make -n regen-all shows the full ordered chain."""
    print("Test 1: Makefile dry-run shows correct command chain")

    result = subprocess.run(
        ["make", "-n", "regen-all"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"  FAIL: make -n regen-all failed with exit code {result.returncode}")
        print(f"  stderr: {result.stderr}")
        return False

    output = result.stdout

    # Check ordered chain
    expected_stages = [
        "scripts/calibrate.py",
        "-m torvalds_skill distill",
        "scripts/verify_skill.py",
        "-m torvalds_skill soul",
        "run_review.py",
        "build_comparison.py",
        "generate_variant_table.py",
    ]

    # Verify order
    last_pos = -1
    for stage in expected_stages:
        pos = output.find(stage)
        if pos == -1:
            print(f"  FAIL: Stage not found: {stage}")
            return False
        if pos <= last_pos:
            print(f"  FAIL: Stage out of order: {stage}")
            return False
        last_pos = pos

    print("  PASS: All stages present in correct order")
    return True


def test_state_hash_skip():
    """Test state-hash skip logic: identical inputs skip, changed skill re-runs."""
    print("Test 2: State-hash skip logic")

    # Import the module under test
    sys.path.insert(0, str(REPORT_DIR))
    from run_review import (
        BASELINE_DIR,
        MODELS,
        compute_input_hash,
        record_checkpoint,
        should_skip_model,
    )
    from run_review import (
        REPORT_DIR as RR_DIR,
    )

    model = "gpt-oss-120b"
    mode = "with-skill"
    key = f"{model}:{mode}"

    # Create temp state file
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_state = Path(tmpdir) / ".review_state.json"

        # Mock state functions to use temp file
        import run_review

        original_load_state = run_review.load_state
        original_save_state = run_review.save_state
        original_STATE_FILE = run_review.STATE_FILE

        run_review.STATE_FILE = tmp_state

        def mock_load_state():
            if tmp_state.exists():
                try:
                    return json.loads(tmp_state.read_text())
                except (json.JSONDecodeError, OSError):
                    return {}
            return {}

        def mock_save_state(state):
            try:
                tmp_state.write_text(json.dumps(state, indent=2))
            except OSError:
                pass

        run_review.load_state = mock_load_state
        run_review.save_state = mock_save_state

        try:
            # Test 2a: No checkpoint → should not skip
            should_skip, reason = should_skip_model(model, mode, force=False)
            if should_skip:
                print("  FAIL: Should not skip when no checkpoint exists")
                return False
            print(f"  PASS: No checkpoint → no skip ({reason})")

            # Test 2b: Create checkpoint with input hash → should skip
            skill_file = MODELS.get(model)
            if not skill_file or not skill_file.exists():
                print(f"  SKIP: Skill file not found: {skill_file}")
                return True

            # Compute input hash
            input_hash = compute_input_hash(model, mode)
            if input_hash is None:
                print("  SKIP: Could not compute input hash (missing inputs)")
                return True

            # Create mock output file
            out_file = RR_DIR / f"review-{model}.md"
            out_file.write_text("mock review output")

            # Record checkpoint
            record_checkpoint(model, mode, out_file, "ok")

            # Verify checkpoint has input_hash
            state = mock_load_state()
            if key not in state:
                print("  FAIL: Checkpoint not recorded")
                return False

            if "input_hash" not in state[key]:
                print("  FAIL: Checkpoint missing input_hash")
                return False

            if state[key]["input_hash"] != input_hash:
                print("  FAIL: Input hash mismatch in checkpoint")
                return False

            print("  PASS: Checkpoint recorded with input_hash")

            # Test 2c: Identical inputs → should skip
            should_skip, reason = should_skip_model(model, mode, force=False)
            if not should_skip:
                print(f"  FAIL: Should skip with identical inputs ({reason})")
                return False
            print(f"  PASS: Identical inputs → skip ({reason})")

            # Test 2d: Changed input hash → should not skip
            state[key]["input_hash"] = "fake_hash_that_does_not_match"
            mock_save_state(state)

            should_skip, reason = should_skip_model(model, mode, force=False)
            if should_skip:
                print("  FAIL: Should not skip when input hash changed")
                return False
            print(f"  PASS: Changed input hash → no skip ({reason})")

            # Test 2e: Baseline mode (no skill file in input hash)
            baseline_key = f"{model}:baseline"
            baseline_out = BASELINE_DIR / f"review-baseline-{model}.md"
            baseline_out.parent.mkdir(parents=True, exist_ok=True)
            baseline_out.write_text("mock baseline output")

            input_hash_baseline = compute_input_hash(model, "baseline")
            if input_hash_baseline is not None:
                record_checkpoint(model, "baseline", baseline_out, "ok")

                state = mock_load_state()
                if baseline_key not in state:
                    print("  FAIL: Baseline checkpoint not recorded")
                    return False

                if state[baseline_key].get("input_hash") != input_hash_baseline:
                    print("  FAIL: Baseline input hash mismatch")
                    return False

                print("  PASS: Baseline mode computes input hash (source files only)")

            print("  PASS: All state-hash skip tests passed")
            return True

        finally:
            # Restore original functions
            run_review.load_state = original_load_state
            run_review.save_state = original_save_state
            run_review.STATE_FILE = original_STATE_FILE


def main():
    """Run all tests."""
    print("=" * 60)
    print("Makefile and State-Hash Skip Tests")
    print("=" * 60)
    print()

    results = []

    # Test 1: Makefile dry-run
    results.append(("Makefile dry-run", test_makefile_dry_run()))
    print()

    # Test 2: State-hash skip logic
    results.append(("State-hash skip", test_state_hash_skip()))
    print()

    # Summary
    print("=" * 60)
    print("Summary")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")

    print()
    print(f"Total: {passed}/{total} tests passed")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
