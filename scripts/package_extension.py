import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit
from zipfile import ZIP_DEFLATED, ZipFile


def package(source: Path, output: Path, api_url: str) -> None:
    parsed = urlsplit(api_url)
    if (
        not parsed.hostname or parsed.username or parsed.password
        or parsed.path not in {"", "/"} or parsed.query or parsed.fragment
        or (parsed.scheme != "https" and not (
            parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
        ))
    ):
        raise ValueError("Provide an HTTPS API origin or a local HTTP origin, without a path")
    api_origin = f"{parsed.scheme}://{parsed.netloc}"
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    manifest["host_permissions"] = [
        pattern for pattern in manifest["host_permissions"] if pattern.startswith("https://www.youtube.com/")
    ] + [f"{parsed.scheme}://{parsed.hostname}/*"]
    config = (source / "config.js").read_text(encoding="utf-8")
    _, remaining = config.split("\n", 1)
    if not config.startswith("export const API_URL = "):
        raise ValueError("Expected API_URL on the first line of config.js")
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for file in sorted(source.rglob("*")):
            if not file.is_file():
                continue
            name = file.relative_to(source).as_posix()
            if name == "manifest.json":
                archive.writestr(name, json.dumps(manifest, indent=2) + "\n")
            elif name == "config.js":
                archive.writestr(name, f"export const API_URL = {json.dumps(api_origin)};\n" + remaining)
            else:
                archive.write(file, name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Package the Chrome extension with an API endpoint")
    parser.add_argument("--api-url", default="http://127.0.0.1:7860")
    parser.add_argument("--output", type=Path, default=Path("dist/youtube-sentiment.zip"))
    args = parser.parse_args()
    try:
        package(Path("chrome-extension"), args.output, args.api_url)
    except ValueError as exc:
        parser.error(str(exc))
    print(args.output.resolve())


if __name__ == "__main__":
    main()
