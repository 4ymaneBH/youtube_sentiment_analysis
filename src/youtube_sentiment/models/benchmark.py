import argparse
import json
import platform
from pathlib import Path
from statistics import mean, quantiles
from time import perf_counter

import joblib
from threadpoolctl import threadpool_limits

from youtube_sentiment.data.prepare import read_split


def benchmark(model, comments: list[str], repetitions: int = 30) -> dict:
    batch_size = 50
    if len(comments) < batch_size:
        raise ValueError("Benchmark requires at least 50 comments")
    samples = []
    with threadpool_limits(limits=2):
        model.predict_proba(comments[:batch_size])
        for i in range(repetitions):
            start = (i * batch_size) % (len(comments) - batch_size + 1)
            batch = comments[start:start + batch_size]
            begin = perf_counter()
            model.predict_proba(batch)
            samples.append((perf_counter() - begin) * 1000)
    return {
        "batch_size": batch_size,
        "repetitions": repetitions,
        "mean_ms": round(mean(samples), 3),
        "p95_ms": round(quantiles(samples, n=20, method="inclusive")[-1], 3),
        "platform": platform.platform(),
        "cpu": platform.processor(),
        "thread_limit": 2,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark warmed batch inference")
    parser.add_argument("--model", type=Path, default=Path("models/sentiment_pipeline.joblib"))
    parser.add_argument("--data", type=Path, default=Path("data/processed/test.csv"))
    args = parser.parse_args()
    comments, _ = read_split(args.data)
    print(json.dumps(benchmark(joblib.load(args.model), comments), indent=2))


if __name__ == "__main__":
    main()
