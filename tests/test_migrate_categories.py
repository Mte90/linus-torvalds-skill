"""Tests for migrate_categories.py category migration logic.

Verifies the category remapping and field-swap bug fix logic.
"""

import pytest

from scripts.migrate_categories import migrate_record, CATEGORY_REMAP


class TestMigrateRecord:
    """Test single record migration."""

    def test_no_changes_needed(self):
        """Already migrated record should return copy with no changes."""
        record = {
            "email_message_id": "<test@example.com>",
            "moves": [
                {"category": "testing", "severity": "reject"}
            ]
        }
        migrated, changes = migrate_record(record)
        assert migrated == record
        assert changes == []

    def test_category_remapped(self):
        """Non-canonical category should be remapped."""
        record = {
            "email_message_id": "<test@example.com>",
            "moves": [
                {"category": "debugging", "severity": "reject"}
            ]
        }
        migrated, changes = migrate_record(record)
        assert migrated["moves"][0]["category"] == "correctness"
        assert len(changes) == 1
        assert "category 'debugging' → 'correctness'" in changes[0]

    def test_all_category_remaps(self):
        """All category remappings should work correctly."""
        test_cases = [
            ("debugging", "correctness"),
            ("design", "abstraction"),
            ("compatibility", "api-stability"),
            ("api-design", "api-stability"),
            ("stability", "api-stability"),
            ("api", "api-stability"),
            ("maintainability", "complexity"),
            ("redundancy", "complexity"),
            ("reliability", "error-handling"),
            ("readability", "style"),
        ]
        
        for old_cat, expected_new_cat in test_cases:
            record = {
                "email_message_id": "<test@example.com>",
                "moves": [{"category": old_cat, "severity": "reject"}]
            }
            migrated, changes = migrate_record(record)
            assert migrated["moves"][0]["category"] == expected_new_cat, f"Failed for {old_cat}"
            assert len(changes) == 1, f"No change recorded for {old_cat}"

    def test_field_swap_bug_fix(self):
        """Field-swap bug should be fixed for specific move."""
        record = {
            "email_message_id": "<Pine.LNX.4.58.0409251513290.2317@ppc970.osdl.org>",
            "moves": [
                {"category": "process", "severity": "process"},
                {"category": "testing", "severity": "reject"},
                {"category": "correctness", "severity": "process"},  # move 3 (index 2)
            ]
        }
        migrated, changes = migrate_record(record)
        # Move 3 (index 2) should have severity fixed
        assert migrated["moves"][2]["severity"] == "discussion"
        assert len(changes) == 1
        assert "move 3: severity 'process' → 'discussion'" in changes[0]

    def test_field_swap_only_affects_correct_move(self):
        """Field-swap fix should only affect move 3 with severity='process'."""
        record = {
            "email_message_id": "<Pine.LNX.4.58.0409251513290.2317@ppc970.osdl.org>",
            "moves": [
                {"category": "process", "severity": "process"},  # move 1 - should NOT change
                {"category": "testing", "severity": "process"},  # move 2 - should NOT change
                {"category": "correctness", "severity": "process"},  # move 3 - SHOULD change
            ]
        }
        migrated, changes = migrate_record(record)
        # Only move 3 should be changed
        assert migrated["moves"][0]["severity"] == "process"  # unchanged
        assert migrated["moves"][1]["severity"] == "process"  # unchanged
        assert migrated["moves"][2]["severity"] == "discussion"  # changed
        assert len(changes) == 1

    def test_field_swap_wrong_email_not_fixed(self):
        """Field-swap fix should not apply to different email."""
        record = {
            "email_message_id": "<different@example.com>",
            "moves": [
                {"category": "correctness", "severity": "process"},  # move 3 but wrong email
            ]
        }
        migrated, changes = migrate_record(record)
        # Should NOT be fixed
        assert migrated["moves"][0]["severity"] == "process"
        assert changes == []

    def test_field_swap_wrong_severity_not_fixed(self):
        """Field-swap fix should not apply if severity is not 'process'."""
        record = {
            "email_message_id": "<Pine.LNX.4.58.0409251513290.2317@ppc970.osdl.org>",
            "moves": [
                {"category": "correctness", "severity": "reject"},  # move 3 but severity != 'process'
            ]
        }
        migrated, changes = migrate_record(record)
        # Should NOT be fixed
        assert migrated["moves"][0]["severity"] == "reject"
        assert changes == []

    def test_multiple_moves_with_changes(self):
        """Multiple moves with different changes should all be recorded."""
        record = {
            "email_message_id": "<Pine.LNX.4.58.0409251513290.2317@ppc970.osdl.org>",
            "moves": [
                {"category": "debugging", "severity": "reject"},  # category change
                {"category": "testing", "severity": "process"},   # no change
                {"category": "correctness", "severity": "process"},  # severity fix
            ]
        }
        migrated, changes = migrate_record(record)
        assert migrated["moves"][0]["category"] == "correctness"
        assert migrated["moves"][2]["severity"] == "discussion"
        assert len(changes) == 2

    def test_change_log_format(self):
        """Change log entries should have correct format."""
        record = {
            "email_message_id": "<test@example.com>",
            "moves": [
                {"category": "design", "severity": "reject"},
            ]
        }
        migrated, changes = migrate_record(record)
        assert len(changes) == 1
        # Format: "move N: category 'old' → 'new'"
        assert changes[0].startswith("move 1: category 'design' → 'abstraction'")

    def test_empty_moves_list(self):
        """Record with empty moves list should return copy with no changes."""
        record = {
            "email_message_id": "<test@example.com>",
            "moves": []
        }
        migrated, changes = migrate_record(record)
        assert migrated["moves"] == []
        assert changes == []

    def test_record_without_moves_key(self):
        """Record without moves key should handle gracefully."""
        record = {
            "email_message_id": "<test@example.com>"
        }
        migrated, changes = migrate_record(record)
        assert migrated == record
        assert changes == []

    def test_record_without_category(self):
        """Move without category should not cause errors."""
        record = {
            "email_message_id": "<test@example.com>",
            "moves": [
                {"severity": "reject"}  # no category key
            ]
        }
        migrated, changes = migrate_record(record)
        # Should not crash, no category change
        assert len(migrated["moves"]) == 1
        assert changes == []