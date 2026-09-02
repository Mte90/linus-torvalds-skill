"""Tests for classify.py rule-based email filtering.

Verifies the rule-based classification logic that filters code reviews
from announcements, git-pull requests, patch submissions, and RFC discussions.
"""

import pytest

from torvalds_skill.classify import is_review
from torvalds_skill.models import EmailRecord


def _make_email(
    message_id: str = "test@example.com",
    subject: str = "Re: Some patch",
    in_reply_to: str | None = "parent@example.com",
    body: str = "This is a substantive review comment that has enough length to pass the minimum body length requirement of one hundred characters.",
    from_name: str = "Linus Torvalds",
    from_email: str = "torvalds@linux.org",
    date: str = "2024-01-01",
) -> EmailRecord:
    return EmailRecord(
        message_id=message_id,
        from_name=from_name,
        from_email=from_email,
        date=date,
        subject=subject,
        in_reply_to=in_reply_to,
        body=body,
    )


class TestReviewFiltering:
    """Test that reviews are correctly identified."""

    def test_review_with_reply_and_substance(self):
        """A reply with substantive body should be classified as review."""
        email = _make_email(
            subject="Re: Fix memory leak in network driver",
            body="The issue is that the buffer is allocated but never freed. "
            "You need to add a kfree() call in the error path. "
            "This is a critical bug that needs to be fixed before merging.",
        )
        assert is_review(email) is True

    def test_review_without_reply_but_patch_reference(self):
        """A non-reply with patch reference and substance should be review."""
        email = _make_email(
            subject="Patch review: network driver fixes",
            in_reply_to=None,
            body="This patch series has good overall structure but the error handling "
            "in the second patch needs work. The cleanup path should be more "
            "consistent with the rest of the kernel.",
        )
        assert is_review(email) is True


class TestAnnouncementFiltering:
    """Test that announcements are filtered out."""

    @pytest.mark.parametrize(
        "subject",
        [
            "Linux 6.7 release",
            "Linux 6.8-rc1",
            "git pull request",
            "Pull request for networking",
            "merge branch topic",
            "merge tag v6.7",
        ],
    )
    def test_announcement_subjects_filtered(self, subject):
        """Announcement subjects should not be classified as reviews."""
        email = _make_email(subject=subject, in_reply_to=None)
        assert is_review(email) is False

    def test_release_announcement_not_reply(self):
        """Release announcements without Re: should be filtered."""
        email = _make_email(
            subject="Linux 6.7 release",
            in_reply_to=None,
            body="This is the 6.7 release with many new features.",
        )
        assert is_review(email) is False


class TestGitPullFiltering:
    """Test that [GIT PULL] requests are filtered out."""

    @pytest.mark.parametrize(
        "subject",
        [
            "[GIT PULL] networking updates",
            "[git pull] power management",
            "Re: [GIT PULL] driver updates",
            "Some text [GIT PULL] more text",
        ],
    )
    def test_git_pull_subjects_filtered(self, subject):
        """[GIT PULL] subjects should be filtered regardless of position."""
        email = _make_email(subject=subject)
        assert is_review(email) is False


class TestPatchFiltering:
    """Test that [PATCH] submissions are filtered out."""

    @pytest.mark.parametrize(
        "subject",
        [
            "[PATCH] fix memory leak",
            "[PATCH 1/5] networking fix",
            "Re: [PATCH] driver update",
            "Re: [PATCH v2 0/3] series",
        ],
    )
    def test_patch_subjects_filtered(self, subject):
        """[PATCH] subjects should be filtered."""
        email = _make_email(subject=subject)
        assert is_review(email) is False


class TestRFCFiltering:
    """Test that [RFC] discussions are filtered out."""

    @pytest.mark.parametrize(
        "subject",
        [
            "[RFC] proposed API change",
            "Re: [RFC] design question",
        ],
    )
    def test_rfc_subjects_filtered(self, subject):
        """[RFC] subjects should be filtered."""
        email = _make_email(subject=subject)
        assert is_review(email) is False

    def test_rfc_v2_not_filtered(self):
        """[RFC v2] format is not matched by current RFC_RE regex."""
        # Current RFC_RE = r"\[RFC\]" doesn't match "[RFC v2]"
        # This is a limitation of the current implementation
        email = _make_email(subject="[RFC v2] new subsystem")
        assert is_review(email) is True  # Not filtered due to regex limitation


class TestShortBodyFiltering:
    """Test that short bodies are filtered out."""

    def test_short_body_filtered(self):
        """Body under MIN_BODY_LEN should be filtered."""
        email = _make_email(body="Looks good.")
        assert is_review(email) is False

    def test_signoff_only_filtered(self):
        """Pure sign-off lines should be filtered."""
        email = _make_email(
            body="Reviewed-by: John Doe <john@example.com>",
        )
        assert is_review(email) is False

    def test_ack_only_filtered(self):
        """Pure ack lines should be filtered."""
        email = _make_email(
            body="Acked-by: Jane Smith <jane@example.com>",
        )
        assert is_review(email) is False


class TestSubstantiveBodyFiltering:
    """Test that bodies without technical substance are filtered."""

    def test_no_substantive_lines_filtered(self):
        """Body with only short lines and signoffs should be filtered."""
        email = _make_email(
            body="Agreed.\n\nReviewed-by: John Doe <john@example.com>",
        )
        assert is_review(email) is False

    def test_substantive_line_passes(self):
        """Body with at least one long substantive line should pass."""
        email = _make_email(
            body="The issue is that the buffer handling is incorrect in the error path. "
            "We need to ensure proper cleanup.\n\n"
            "Reviewed-by: John Doe <john@example.com>",
        )
        assert is_review(email) is True


class TestEdgeCases:
    """Test edge cases and malformed inputs."""

    def test_empty_subject(self):
        """Empty subject should be handled gracefully."""
        email = _make_email(subject="", in_reply_to=None)
        assert is_review(email) is False

    def test_empty_body(self):
        """Empty body should be filtered."""
        email = _make_email(subject="Re: test", body="")
        assert is_review(email) is False

    def test_whitespace_only_body(self):
        """Whitespace-only body should be filtered."""
        email = _make_email(subject="Re: test", body="   \n\n   ")
        assert is_review(email) is False

    def test_no_reply_to_and_no_re_prefix(self):
        """Email without In-Reply-To and without Re: prefix should be checked for patch reference."""
        email = _make_email(
            subject="Some random subject",
            in_reply_to=None,
        )
        assert is_review(email) is False

    def test_no_reply_but_patch_in_subject(self):
        """Email without In-Reply-To but with patch in subject should be checked for substance."""
        email = _make_email(
            subject="Review of patch series",
            in_reply_to=None,
            body="This is a substantive review comment that has enough length to pass the minimum body length requirement of one hundred characters.",
        )
        assert is_review(email) is True


class TestBoundaryCases:
    """Test boundary and variant cases."""

    def test_git_pull_embedded_mid_sentence(self):
        """[GIT PULL] embedded mid-sentence should still be filtered."""
        email = _make_email(
            subject="Regarding the [GIT PULL] request for networking",
        )
        assert is_review(email) is False

    def test_git_pull_with_spaces(self):
        """[GIT  PULL] with extra spaces should be filtered."""
        email = _make_email(
            subject="[GIT  PULL] networking updates",
        )
        assert is_review(email) is False

    def test_patch_with_varying_formats(self):
        """Various [PATCH] formats should be filtered."""
        for subject in ["[PATCH]", "[PATCH 1/10]", "[PATCH v2]", "Re: [PATCH]"]:
            email = _make_email(subject=subject)
            assert is_review(email) is False, f"Failed for subject: {subject}"

    def test_case_insensitive_matching(self):
        """Pattern matching should be case-insensitive."""
        for subject in ["[git pull]", "[Git Pull]", "[RFC]", "[patch]"]:
            email = _make_email(subject=subject)
            assert is_review(email) is False, f"Failed for subject: {subject}"
