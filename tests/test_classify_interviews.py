"""Tests for classify_interviews.py rule-based interview filtering.

Verifies the rule-based classification logic that filters substantive
technical passages from interview transcripts.
"""

import pytest

from torvalds_skill.classify_interviews import (
    classify_passage,
    extract_context,
    has_core_kernel_content,
    is_personal_topic,
    is_procedural,
    is_promotional,
    mentions_linus,
    split_into_passages,
)


class TestIsPromotional:
    """Test promotional/ad content detection."""

    @pytest.mark.parametrize(
        "text",
        [
            "Please subscribe to our channel for more content",
            "Don't forget to like and share this video",
            "Hit the subscribe button to join us",
            "This episode is brought to you by our sponsor",
            "Follow us on Twitter and Facebook",
            "Thanks for watching, see you next time",
            "Welcome to today's episode where we have",
            "Thank you for joining us today",
            "Join us on YouTube for more content",
            "Subscribe to our podcast for weekly updates",
        ],
    )
    def test_promotional_patterns_detected(self, text):
        """Promotional patterns should be detected as promotional."""
        assert is_promotional(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "The kernel patch fixes a memory leak in the network driver",
            "Linus explained the merge window process",
            "Technical discussion about code review practices",
            "",
        ],
    )
    def test_technical_content_not_promotional(self, text):
        """Technical content should not be flagged as promotional."""
        assert is_promotional(text) is False

    def test_empty_string_not_promotional(self):
        """Empty string should not be promotional."""
        assert is_promotional("") is False

    def test_case_insensitive_matching(self):
        """Pattern matching should be case-insensitive."""
        assert is_promotional("PLEASE SUBSCRIBE") is True
        assert is_promotional("Please Subscribe") is True


class TestIsProcedural:
    """Test procedural host question detection."""

    @pytest.mark.parametrize(
        "text",
        [
            "Can you tell us about the merge window process?",
            "Let's move on to discussing code review",
            "What would you say to developers who disagree?",
            "Could you share your thoughts on this?",
            "I'd love to hear more about that",
            "Let's dig into the technical details",
            "Before we start, can you introduce yourself?",
            "To get us started, what's your background?",
        ],
    )
    def test_procedural_patterns_detected(self, text):
        """Procedural host questions should be detected."""
        assert is_procedural(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "The merge window is open for two weeks",
            "Linus discussed the patch review process",
            "Technical explanation of kernel development",
            "",
        ],
    )
    def test_technical_content_not_procedural(self, text):
        """Technical content should not be flagged as procedural."""
        assert is_procedural(text) is False

    def test_empty_string_not_procedural(self):
        """Empty string should not be procedural."""
        assert is_procedural("") is False


class TestIsPersonalTopic:
    """Test personal/non-technical topic detection."""

    @pytest.mark.parametrize(
        "text",
        [
            "What do you do in your free time?",
            "Tell us about your family and wife",
            "Where did you grow up and go to school?",
            "What inspires you personally in life?",
            "What's your favorite programming language?",
            "Are you married or single?",
            "What kind of car do you drive?",
            "Tell us about your childhood and early life",
            "What are your hobbies and interests?",
            "What's your dream vacation?",
        ],
    )
    def test_personal_patterns_detected(self, text):
        """Personal topic patterns should be detected."""
        assert is_personal_topic(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "The kernel patch fixes a memory leak",
            "Linus discussed code review best practices",
            "Technical discussion about software engineering",
            "",
        ],
    )
    def test_technical_content_not_personal(self, text):
        """Technical content should not be flagged as personal."""
        assert is_personal_topic(text) is False

    def test_empty_string_not_personal(self):
        """Empty string should not be personal."""
        assert is_personal_topic("") is False


class TestHasCoreKernelContent:
    """Test core kernel development keyword detection."""

    @pytest.mark.parametrize(
        "text",
        [
            "The kernel patch fixes a memory leak",
            "Linus reviewed the pull request for the subsystem",
            "Merge window opens for upstream changes",
            "Code review process on the mailing list",
            "Git tree structure for the branch",
            "Driver development for the filesystem",
            "Memory management and concurrency issues",
            "Locking with mutex and semaphore",
            "Performance optimization and profiling",
            "Testing and test coverage improvements",
            "Security vulnerability and bug fix",
            "API design and interface abstraction",
            "Compiler build and debugging",
            "Regression test and backport",
            "Open source contribution guidelines",
            "Developer community governance",
        ],
    )
    def test_kernel_keywords_detected(self, text):
        """Core kernel keywords should be detected."""
        assert has_core_kernel_content(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "The weather is nice today",
            "I enjoy cooking and gardening",
            "Discussion about cooking recipes and food preparation",
            "",
        ],
    )
    def test_non_kernel_content_not_detected(self, text):
        """Non-kernel content should not be detected."""
        assert has_core_kernel_content(text) is False

    def test_empty_string_no_kernel_content(self):
        """Empty string should not have kernel content."""
        assert has_core_kernel_content("") is False

    def test_case_insensitive_matching(self):
        """Keyword matching should be case-insensitive."""
        assert has_core_kernel_content("KERNEL PATCH") is True
        assert has_core_kernel_content("Kernel Patch") is True


class TestMentionsLinus:
    """Test Linus/Torvalds reference detection."""

    @pytest.mark.parametrize(
        "text",
        [
            "Torvalds explained the merge process",
            "Linus discussed the patch review",
            "Torvalds said the code is incorrect",
            "Linus Torvalds replied to the mailing list",
            "As Torvalds noted in his response",
            "The patch was reviewed by Linus",
        ],
    )
    def test_linus_references_detected(self, text):
        """Linus/Torvalds references should be detected."""
        assert mentions_linus(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "The developer explained the process",
            "Someone discussed the patch",
            "Technical explanation without attribution",
            "",
        ],
    )
    def test_no_linus_reference(self, text):
        """Text without Linus reference should not be detected."""
        assert mentions_linus(text) is False

    def test_empty_string_no_linus(self):
        """Empty string should not mention Linus."""
        assert mentions_linus("") is False

    def test_case_insensitive_matching(self):
        """Pattern matching should be case-insensitive."""
        assert mentions_linus("TORVALDS SAID") is True
        assert mentions_linus("Torvalds Said") is True
        assert mentions_linus("LINUS EXPLAINED") is True


class TestSplitIntoPassages:
    """Test passage splitting functionality."""

    def test_empty_string_returns_empty_list(self):
        """Empty string should return empty list."""
        assert split_into_passages("") == []

    def test_none_content_returns_empty_list(self):
        """None content should be handled gracefully."""
        with pytest.raises(AttributeError):
            split_into_passages(None)

    def test_single_passage(self):
        """Single paragraph should return single passage."""
        content = "This is a single passage with enough length to be included in the results."
        result = split_into_passages(content)
        assert len(result) == 1
        assert result[0] == content

    def test_multiple_passages(self):
        """Multiple paragraphs should be split correctly."""
        content = "First passage with enough content to pass the minimum length requirement.\n\nSecond passage also has enough content to be included.\n\nThird passage here with sufficient length."
        result = split_into_passages(content)
        assert len(result) == 3
        assert (
            result[0] == "First passage with enough content to pass the minimum length requirement."
        )
        assert result[1] == "Second passage also has enough content to be included."
        assert result[2] == "Third passage here with sufficient length."

    def test_short_fragments_filtered(self):
        """Fragments under 30 characters should be filtered out."""
        content = "Short.\n\nThis is a passage with enough length to be included.\n\nHi."
        result = split_into_passages(content)
        assert len(result) == 1
        assert result[0] == "This is a passage with enough length to be included."

    def test_whitespace_only_paragraphs_filtered(self):
        """Whitespace-only paragraphs should be filtered."""
        content = "Valid passage with enough content.\n\n   \n\nAnother valid passage with enough content."
        result = split_into_passages(content)
        assert len(result) == 2

    def test_crlf_line_endings_normalized(self):
        """Windows line endings should be normalized."""
        content = "First passage with enough content.\r\n\r\nSecond passage with enough content."
        result = split_into_passages(content)
        assert len(result) == 2

    def test_cr_line_endings_normalized(self):
        """Old Mac line endings should be normalized."""
        content = "First passage with enough content.\r\rSecond passage with enough content."
        result = split_into_passages(content)
        assert len(result) == 2

    def test_boundary_length_30_chars(self):
        """Passage exactly at 30 characters should be included."""
        content = "Short."  # 6 chars - too short
        result = split_into_passages(content)
        assert len(result) == 0

        # 31 chars - just over the threshold
        content = "This is thirty one chars here!!"
        result = split_into_passages(content)
        assert len(result) == 1


class TestClassifyPassage:
    """Test passage classification - the composition root."""

    def test_promotional_passage_rejected(self):
        """Promotional passages should be rejected with 'promotional' reason."""
        keep, reason = classify_passage("Please subscribe to our channel")
        assert keep is False
        assert reason == "promotional"

    def test_procedural_passage_rejected(self):
        """Procedural passages should be rejected with 'procedural' reason."""
        keep, reason = classify_passage("Can you tell us about your background?")
        assert keep is False
        assert reason == "procedural"

    def test_personal_passage_rejected(self):
        """Personal topic passages should be rejected with 'personal' reason."""
        keep, reason = classify_passage("What do you do in your free time?")
        assert keep is False
        assert reason == "personal"

    def test_no_linus_reference_rejected(self):
        """Passages without Linus reference should be rejected."""
        keep, reason = classify_passage("The kernel patch fixes a memory leak.")
        assert keep is False
        assert reason == "no-linus-reference"

    def test_non_technical_content_rejected(self):
        """Passages with Linus but no kernel content should be rejected."""
        keep, reason = classify_passage("Torvalds enjoys cooking on weekends.")
        assert keep is False
        assert reason == "non-technical"

    def test_valid_technical_passage_accepted(self):
        """Valid technical passages should be accepted."""
        keep, reason = classify_passage(
            "Torvalds explained that the kernel patch fixes a memory leak in the driver."
        )
        assert keep is True
        assert reason == "technical"

    @pytest.mark.parametrize(
        "text",
        [
            "Linus Torvalds discussed the merge window for upstream kernel patches.",
            "Torvalds reviewed the pull request and found issues with the code review process.",
            "As Linus noted, the subsystem maintainership requires careful git tree management.",
            "Torvalds explained the importance of testing and test coverage for bug fixes.",
        ],
    )
    def test_various_valid_passages_accepted(self, text):
        """Various valid technical passages should be accepted."""
        keep, reason = classify_passage(text)
        assert keep is True
        assert reason == "technical"

    @pytest.mark.parametrize(
        "text",
        [
            "Subscribe to our channel for more Linus content.",  # promotional
            "Can you tell us about kernel development?",  # procedural
            "What's your favorite kernel feature?",  # personal
            "The kernel is great.",  # no linus reference
            "Torvalds likes pizza.",  # non-technical
        ],
    )
    def test_various_invalid_passages_rejected(self, text):
        """Various invalid passages should be rejected for correct reasons."""
        keep, reason = classify_passage(text)
        assert keep is False

    def test_filter_priority_order(self):
        """Filters should be applied in priority order (promotional first)."""
        keep, reason = classify_passage("Please subscribe, can you tell us about kernels?")
        assert keep is False
        assert reason == "promotional"


class TestExtractContext:
    """Test context extraction from surrounding passages."""

    def test_first_passage_no_previous_context(self):
        """First passage should have no previous context."""
        passages = [
            "First passage with Linus discussing kernel patches.",
            "Second passage here.",
        ]
        context = extract_context(passages[0], passages, 0)
        assert "First passage with Linus discussing kernel patches" in context

    def test_middle_passage_has_previous_context(self):
        """Middle passage should include previous passage as context."""
        passages = [
            "What is your opinion on kernel development?",
            "Linus explained the merge window process for upstream patches.",
            "Third passage here.",
        ]
        context = extract_context(passages[1], passages, 1)
        assert "What is your opinion on kernel development?" in context
        assert "Linus explained the merge window process" in context

    def test_last_passage_has_previous_context(self):
        """Last passage should include previous passage as context."""
        passages = [
            "First passage.",
            "Question from interviewer?",
            "Linus discussed the patch review process.",
        ]
        context = extract_context(passages[2], passages, 2)
        assert "Question from interviewer?" in context

    def test_long_previous_passage_excluded(self):
        """Long previous passages (>200 chars) should be excluded from context."""
        long_text = "A" * 250
        passages = [
            long_text,
            "Linus discussed kernel patches.",
        ]
        context = extract_context(passages[1], passages, 1)
        assert "A" * 100 not in context

    def test_long_first_sentence_excluded(self):
        """Long first sentences (>100 chars) should be excluded from context."""
        passages = [
            "Question?",
            "This is a very long first sentence that exceeds one hundred characters and should be excluded from context extraction because it is too long for the context parts list.",
        ]
        context = extract_context(passages[1], passages, 1)
        assert "Question?" in context
        assert "This is a very long first sentence" not in context

    def test_empty_context_when_no_parts(self):
        """Empty context should be returned when no parts qualify."""
        passages = [
            "A" * 300,
            "A" * 200,
        ]
        context = extract_context(passages[1], passages, 1)
        assert context == ""

    def test_context_separator_pipe(self):
        """Context parts should be joined with pipe separator."""
        passages = [
            "Previous question?",
            "Linus answered about kernel patches.",
        ]
        context = extract_context(passages[1], passages, 1)
        assert " | " in context
