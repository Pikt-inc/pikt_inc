from __future__ import annotations

import subprocess
import sys
from pathlib import Path


TEXT_SUFFIXES = {
    ".css",
    ".csv",
    ".html",
    ".htm",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".py",
    ".scss",
    ".svg",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}


def list_tracked_files(repo_root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    files: list[Path] = []
    for raw_path in result.stdout.splitlines():
        if not raw_path:
            continue
        path = repo_root / raw_path
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            files.append(path)
    return files


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    failures: list[str] = []

    for path in list_tracked_files(repo_root):
        data = path.read_bytes()
        relative_path = path.relative_to(repo_root).as_posix()

        if data.startswith(b"\xef\xbb\xbf"):
            failures.append(f"{relative_path}: UTF-8 BOM is not allowed")
            continue

        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            failures.append(
                f"{relative_path}: invalid UTF-8 at byte {exc.start}"
            )

    if failures:
        print("UTF-8 validation failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    print("UTF-8 validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
