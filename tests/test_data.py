from pathlib import Path

import pytest

from youtube_sentiment.data.download import acquire
from youtube_sentiment.data.prepare import unique_comments
from youtube_sentiment.preprocessing import clean_text


def test_deduplication_prevents_normalized_text_leakage():
    rows = [("I love this", 1), ("I love this @name", 1), ("I love this!", 1),
            ("same", -1), ("SAME", 0), ("https://example.com", 0)]
    unique, removals = unique_comments(rows)
    assert unique == [("I love this", 1), ("I love this!", 1)]
    assert removals == {
        "empty_after_cleaning": 1, "conflicting_text_groups": 1,
        "duplicates_or_conflicts_removed": 3,
    }


def test_cleaning_preserves_negation_and_emoji():
    assert clean_text("I don't like it 😡 https://example.com @someone") == "i don't like it pouting face"
    assert clean_text("Très bien") == "très bien"


def test_invalid_download_keeps_prior_dataset(tmp_path: Path):
    valid = tmp_path / "valid.csv"
    valid.write_text("clean_comment,category\nexample,1\n", encoding="utf-8")
    invalid = tmp_path / "invalid.csv"
    invalid.write_text("clean_comment,category\nexample,42\n", encoding="utf-8")
    output = tmp_path / "raw" / "reddit.csv"
    stats = acquire(output, local=valid)
    assert stats["rows"] == 1
    with pytest.raises(ValueError, match="Invalid label"):
        acquire(output, local=invalid)
    assert output.read_bytes() == valid.read_bytes()
    assert not output.with_suffix(".part").exists()
