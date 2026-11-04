import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from sklearn.model_selection import train_test_split

from youtube_sentiment.data.download import LABELS, RAW_DATA, read_source
from youtube_sentiment.preprocessing import clean_text

SEED = 42
PROCESSED = Path("data/processed")


def unique_comments(rows: list[tuple[str, int]]) -> tuple[list[tuple[str, int]], dict]:
    groups = defaultdict(dict)
    empty = 0
    for text, label in rows:
        normalized = clean_text(text)
        if not normalized:
            empty += 1
            continue
        groups[normalized].setdefault(label, text)
    cleaned = [(next(iter(group.values())), next(iter(group))) for group in groups.values()
               if len(group) == 1]
    return cleaned, {
        "empty_after_cleaning": empty,
        "conflicting_text_groups": sum(len(group) > 1 for group in groups.values()),
        "duplicates_or_conflicts_removed": len(rows) - len(cleaned) - empty,
    }


def prepare(source: Path, output: Path) -> dict:
    rows, removals = unique_comments(read_source(source))
    counts = Counter(label for _, label in rows)
    if len(rows) < 1000 or any(counts[label] < 300 for label in LABELS):
        raise ValueError("Need at least 1,000 usable rows and 300 per class")
    train, test = train_test_split(
        rows, test_size=0.2, random_state=SEED, stratify=[label for _, label in rows]
    )
    output.mkdir(parents=True, exist_ok=True)
    for name, split in [("train", train), ("test", test)]:
        with (output / f"{name}.csv").open("w", encoding="utf-8", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["text", "label"])
            writer.writerows(split)
    metadata = {
        "dataset_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "seed": SEED,
        "usable_rows": len(rows),
        "class_counts": dict(counts),
        "train_rows": len(train),
        "test_rows": len(test),
        **removals,
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def read_split(path: Path) -> tuple[list[str], list[int]]:
    with path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    return [row["text"] for row in rows], [int(row["label"]) for row in rows]


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and split Reddit comments")
    parser.add_argument("--source", type=Path, default=RAW_DATA)
    parser.add_argument("--output", type=Path, default=PROCESSED)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.output), indent=2))


if __name__ == "__main__":
    main()
