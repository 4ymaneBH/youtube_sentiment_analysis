import argparse
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from youtube_sentiment.data.download import LABELS
from youtube_sentiment.data.prepare import PROCESSED, read_split
from youtube_sentiment.preprocessing import clean_comments


def explore(data: Path, output: Path) -> None:
    comments, labels = read_split(data / "train.csv")
    test_comments, test_labels = read_split(data / "test.csv")
    counts = Counter(labels + test_labels)
    lengths = [len(text.split()) for text in clean_comments(comments + test_comments)]
    palette = ["#aa4336", "#697486", "#2d785c"]
    output.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    bars = axes[0].bar(list(LABELS.values()), [counts[key] for key in LABELS], color=palette)
    axes[0].bar_label(bars, fmt="{:,.0f}")
    axes[0].set(title="Usable comments by class", ylabel="Comments", ylim=(0, max(counts.values()) * 1.16))
    axes[1].hist(lengths, bins=range(1, 102, 4), color="#546a8f")
    axes[1].set(title="Comment lengths (first 100 words)", xlabel="Words after cleaning", ylabel="Comments")
    fig.savefig(output / "dataset.png", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot the prepared dataset")
    parser.add_argument("--data", type=Path, default=PROCESSED)
    parser.add_argument("--output", type=Path, default=Path("reports/figures"))
    args = parser.parse_args()
    explore(args.data, args.output)
