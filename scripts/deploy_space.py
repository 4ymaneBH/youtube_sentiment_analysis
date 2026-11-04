import argparse
from pathlib import Path

from huggingface_hub import HfApi, get_token

SERVING_FILES = [
    "README.md", "Dockerfile", ".dockerignore", "requirements.txt", "app_api.py",
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
    api = HfApi()
    api.create_repo(
        args.space, repo_type="space", space_sdk="docker",
        private=args.visibility == "private", exist_ok=True,
    )
    api.upload_folder(
        folder_path=".", repo_id=args.space, repo_type="space", allow_patterns=SERVING_FILES,
        ignore_patterns=["**/__pycache__/**", "**/*.pyc"],
        commit_message="Deploy the YouTube sentiment API and trained model",
    )
    print(f"https://huggingface.co/spaces/{args.space}")


if __name__ == "__main__":
    main()
