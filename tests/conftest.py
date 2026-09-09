"""Pytest configuration for torvalds-skill tests."""

import sys
from pathlib import Path

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(autouse=True)
def _isolate_report_dir(tmp_path, monkeypatch):
    """Redirect audit REPORT_DIR to a temp dir so tests never pollute report/decisions.jsonl."""
    monkeypatch.setenv("TORVALDS_REPORT_DIR", str(tmp_path))
    import importlib

    import torvalds_skill.audit as audit_module

    importlib.reload(audit_module)
    yield
    importlib.reload(audit_module)
