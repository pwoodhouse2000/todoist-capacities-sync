"""Unit tests for utility functions."""

import pytest
from datetime import datetime, timezone

from app.utils import (
    compute_payload_hash,
    get_current_timestamp,
    parse_iso_timestamp,
    has_capsync_label,
    format_markdown_comments,
    safe_get,
    build_todoist_task_url,
    build_todoist_project_url,
)


class TestComputePayloadHash:
    """Test payload hashing for idempotency."""

    def test_same_data_produces_same_hash(self):
        data = {"key": "value", "number": 42}
        hash1 = compute_payload_hash(data)
        hash2 = compute_payload_hash(data)
        assert hash1 == hash2

    def test_different_data_produces_different_hash(self):
        data1 = {"key": "value1"}
        data2 = {"key": "value2"}
        hash1 = compute_payload_hash(data1)
        hash2 = compute_payload_hash(data2)
        assert hash1 != hash2

    def test_key_order_does_not_matter(self):
        """Test that dictionary key order doesn't affect hash."""
        data1 = {"a": 1, "b": 2, "c": 3}
        data2 = {"c": 3, "a": 1, "b": 2}
        hash1 = compute_payload_hash(data1)
        hash2 = compute_payload_hash(data2)
        assert hash1 == hash2

    def test_nested_data(self):
        data = {
            "outer": {"inner": "value"},
            "list": [1, 2, 3],
        }
        hash_result = compute_payload_hash(data)
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64  # SHA-256 produces 64 hex chars


class TestTimestampFunctions:
    """Test timestamp utility functions."""

    def test_get_current_timestamp_format(self):
        timestamp = get_current_timestamp()
        # Should be ISO format
        assert "T" in timestamp
        assert timestamp.endswith("Z") or "+" in timestamp

    def test_get_current_timestamp_is_utc(self):
        timestamp = get_current_timestamp()
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        assert parsed.tzinfo is not None

    def test_parse_iso_timestamp_with_z(self):
        timestamp_str = "2025-10-09T18:00:00Z"
        parsed = parse_iso_timestamp(timestamp_str)
        assert isinstance(parsed, datetime)
        assert parsed.year == 2025
        assert parsed.month == 10
        assert parsed.day == 9

    def test_parse_iso_timestamp_with_offset(self):
        timestamp_str = "2025-10-09T18:00:00+00:00"
        parsed = parse_iso_timestamp(timestamp_str)
        assert isinstance(parsed, datetime)
        assert parsed.tzinfo is not None


class TestHasCapsyncLabel:
    """Test capsync label detection."""

    def test_with_at_symbol(self):
        labels = ["@capsync", "work"]
        assert has_capsync_label(labels) is True

    def test_without_at_symbol(self):
        labels = ["capsync", "personal"]
        assert has_capsync_label(labels) is True

    def test_no_capsync(self):
        labels = ["work", "urgent"]
        assert has_capsync_label(labels) is False

    def test_empty_list(self):
        labels = []
        assert has_capsync_label(labels) is False

    def test_case_sensitive(self):
        """Capsync detection should be case-sensitive."""
        labels = ["CapsSync", "CAPSYNC"]
        # Current implementation is case-sensitive
        assert has_capsync_label(labels) is False


class TestFormatMarkdownComments:
    """Test comment formatting."""

    def test_empty_comments(self):
        comments = []
        result = format_markdown_comments(comments)
        assert result == ""

    def test_single_comment(self):
        comments = [
            {"content": "Test comment", "posted_at": "2025-10-09T12:00:00Z"}
        ]
        result = format_markdown_comments(comments)
        assert "Test comment" in result
        assert "**Comment**" in result
        assert "2025-10-09" in result

    def test_multiple_comments(self):
        comments = [
            {"content": "First", "posted_at": "2025-10-09T12:00:00Z"},
            {"content": "Second", "posted_at": "2025-10-09T13:00:00Z"},
        ]
        result = format_markdown_comments(comments)
        assert "First" in result
        assert "Second" in result
        assert "---" in result  # Separator between comments

    def test_missing_fields(self):
        """Test handling of comments with missing fields."""
        comments = [{"content": "Test"}]  # Missing posted_at
        result = format_markdown_comments(comments)
        assert "Test" in result
        # Should handle gracefully


class TestSafeGet:
    """Test safe dictionary access."""

    def test_existing_key(self):
        data = {"key": "value"}
        result = safe_get(data, "key")
        assert result == "value"

    def test_missing_key_default_none(self):
        data = {"key": "value"}
        result = safe_get(data, "missing")
        assert result is None

    def test_missing_key_custom_default(self):
        data = {"key": "value"}
        result = safe_get(data, "missing", default="fallback")
        assert result == "fallback"

    def test_nested_data(self):
        """Test that safe_get only works on top level."""
        data = {"outer": {"inner": "value"}}
        result = safe_get(data, "outer")
        assert result == {"inner": "value"}


class TestURLBuilders:
    """Test URL building functions."""

    def test_build_todoist_task_url(self):
        task_id = "12345678"
        url = build_todoist_task_url(task_id)
        assert url == "https://todoist.com/showTask?id=12345678"
        assert task_id in url

    def test_build_todoist_project_url(self):
        project_id = "98765"
        url = build_todoist_project_url(project_id)
        assert url == "https://todoist.com/app/project/98765"
        assert project_id in url

    def test_url_builder_with_special_chars(self):
        """Test that IDs with special chars are included as-is."""
        task_id = "test-123-abc"
        url = build_todoist_task_url(task_id)
        assert task_id in url

