"""Tests for field key sanitization and validation"""

import pytest

from src.core.field_keys import field_key_error, sanitize_field_key


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Name", "name"),
        ("Order Date", "order_date"),
        ("first-name", "first_name"),
        ("Price ($)", "price_"),
        ("E.mail", "email"),
        ("1st Name", "field_1st_name"),
        ("Café", "café"),
        ("", "field"),
        ("$$$", "field"),
        # SQL keywords
        ("Order", "order_field"),
        ("Group", "group_field"),
        ("Select", "select_field"),
        # Built-in record columns
        ("ID", "id_field"),
        ("Created At", "created_at_field"),
        ("RowID", "rowid_field"),
        # Reserved FTS5 column name
        ("Rank", "rank_field"),
    ],
)
def test_sanitize_field_key(text, expected):
    assert sanitize_field_key(text) == expected


@pytest.mark.parametrize(
    "text",
    ["Order", "ID", "Price ($)", "1st", "rank", "where", "Updated-At", "__row_tag_name", "   "],
)
def test_sanitized_keys_are_valid(text):
    assert field_key_error(sanitize_field_key(text)) is None


@pytest.mark.parametrize("key", ["name", "order_date", "_private", "café", "key"])
def test_valid_keys(key):
    assert field_key_error(key) is None


@pytest.mark.parametrize(
    "key",
    ["", "my key", "1st", "e.mail", "name;drop", "order", "ORDER", "id", "Created_At", "rowid", "rank"],
)
def test_invalid_keys(key):
    assert field_key_error(key) is not None
