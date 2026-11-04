"""Run the local sentiment API with the project virtual environment."""

import uvicorn


def main() -> None:
    uvicorn.run("app_api:app", host="127.0.0.1", port=7860)


if __name__ == "__main__":
    main()
