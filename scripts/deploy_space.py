import argparse
from pathlib import Path

from huggingface_hub import CommitOperationAdd, HfApi, get_token

SPACE_README = """---
title: Spectrum for YouTube API
emoji: 📊
colorFrom: red
colorTo: yellow
sdk: docker
app_port: 7860
---

# Spectrum for YouTube API

This Space serves the YouTube comment sentiment model. Open `/docs` on the
Space's API origin for interactive documentation.

The [GitHub project](https://github.com/4ymaneBH/youtube_sentiment_analyses)
has the Chrome extension, architecture, and model evaluation.
"""

SERVING_FILES = [
    "Dockerfile", ".dockerignore", "requirements.txt", "app_api.py",
    "src/youtube_sentiment/*.py", "src/youtube_sentiment/api/*.py",
    "src/youtube_sentiment/data/*.py", "src/youtube_sentiment/models/*.py",
    "models/metadata.json", "models/sentiment_pipeline.joblib",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload the API and model to a Hugging Face Docker Space")
    parser.add_argument("space", help="Hugging Face owner/space-name")
    parser.add_argument("--visibility", choices=("public", "private"), required=True)
    args = parser.parse_args()
    if not get_token():
        parser.error("Sign in first with hf auth login")
    required = [Path(path) for path in SERVING_FILES if "*" not in path]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        parser.error("Missing files: " + ", ".join(missing))

    files = sorted({path for pattern in SERVING_FILES for path in Path(".").glob(pattern) if path.is_file()})
    operations = [CommitOperationAdd(path_in_repo="README.md", path_or_fileobj=SPACE_README.encode("utf-8"))]
    operations.extend(CommitOperationAdd(path_in_repo=path.as_posix(), path_or_fileobj=path) for path in files)

    api = HfApi()
    api.create_repo(
        args.space, repo_type="space", space_sdk="docker",
        private=args.visibility == "private", exist_ok=True,
    )
    api.create_commit(
        args.space, operations, repo_type="space",
        commit_message="Deploy the YouTube sentiment API and trained model",
    )
    print(f"https://huggingface.co/spaces/{args.space}")


if __name__ == "__main__":
    main()
