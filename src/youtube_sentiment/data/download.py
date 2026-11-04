import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen

DATASET_URL = (
    "https://raw.githubusercontent.com/Himanshu-1703/reddit-sentiment-analysis/"
    "refs/heads/main/data/reddit.csv"
)
RAW_DATA = Path("data/raw/reddit.csv")
LABELS = {-1: "negative", 0: "neutral", 1: "positive"}


def read_source(path: Path) -> list[tuple[str, int]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if set(reader.fieldnames or []) != {"clean_comment", "category"}:
            raise ValueError("Expected source columns clean_comment and category")
        rows = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"Malformed CSV record at line {reader.line_num}")
            try:
                label = int(row["category"])
                if label not in LABELS:
                    raise ValueError
            except ValueError as exc:
                raise ValueError(f"Invalid label at CSV line {reader.line_num}") from exc
            rows.append((row["clean_comment"], label))
    if not rows:
        raise ValueError("The dataset is empty")
    return rows


def acquire(output: Path, local: Path | None = None, force: bool = False) -> dict:
    manifest = output.with_suffix(".metadata.json")
    if local is not None or not output.exists() or force:
        if local is not None:
            content = local.read_bytes()
        else:
            with urlopen(DATASET_URL, timeout=30) as response:
                content = response.read()
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(".part")
        try:
            temp.write_bytes(content)
            rows = read_source(temp)
            temp.replace(output)
        finally:
            temp.unlink(missing_ok=True)
        origin = str(local.resolve()) if local is not None else DATASET_URL
        acquired_at = datetime.now(UTC).isoformat()
    else:
        rows = read_source(output)
        previous = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
        origin = previous.get("source", "existing local file")
        acquired_at = previous.get("acquired_at")
    stats = {
        "source": origin,
        "assignment_url": DATASET_URL,
        "acquired_at": acquired_at,
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "rows": len(rows),
        "blank_comments": sum(not text.strip() for text, _ in rows),
        "class_counts": dict(Counter(label for _, label in rows)),
    }
    manifest.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Acquire the assignment Reddit dataset")
    parser.add_argument("--output", type=Path, default=RAW_DATA)
    parser.add_argument("--local", type=Path, help="Use a local source CSV")
    parser.add_argument("--force", action="store_true", help="Download a fresh copy")
    args = parser.parse_args()
    try:
        print(json.dumps(acquire(args.output, args.local, args.force), indent=2))
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Dataset acquisition failed: {exc}\n")


if __name__ == "__main__":
    main()
