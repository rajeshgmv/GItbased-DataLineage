#!/usr/bin/env python3
import csv
import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv


SCRIPT_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = SCRIPT_DIR / ".env"
load_dotenv(ENV_FILE)


def configured_path(variable_name: str, default: Path) -> Path:
    """Return an absolute path from an environment variable or its default."""
    configured_value = os.getenv(variable_name)
    path = Path(configured_value).expanduser() if configured_value else default
    if not path.is_absolute():
        path = SCRIPT_DIR / path
    return path.resolve()


PROJECT_DIR = configured_path("PROJECT_DIR", SCRIPT_DIR)
CBM_CACHE_DIR = configured_path("CBM_CACHE_DIR", PROJECT_DIR / ".cbm-cache")
REPO_LIST_FILE = configured_path("REPO_LIST_FILE", PROJECT_DIR / "git_repo_list.csv")
CLONE_DIR = configured_path("CLONE_DIR", PROJECT_DIR / "repo_local_clone")
CODEBASE_MEMORY_MCP_BIN = configured_path(
    "CODEBASE_MEMORY_MCP_BIN",
    PROJECT_DIR / ".venv" / "bin" / "codebase-memory-mcp",
)
os.environ["CBM_CACHE_DIR"] = str(CBM_CACHE_DIR)
CSV_FIELDS = ("repo_url", "CloneStatus", "IndexStatus")


def run_command(cmd):
    """Run a CBM command and report the full command if it fails."""
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        print(f"ERROR: command failed: {' '.join(cmd)}", file=sys.stderr)
        raise


def load_repository_rows(csv_path: Path):
    """Load and validate repository clone/index statuses from the CSV file."""
    if not csv_path.is_file():
        raise FileNotFoundError(f"Repository CSV file not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames != list(CSV_FIELDS):
            expected = ",".join(CSV_FIELDS)
            raise ValueError(f"Expected CSV header '{expected}' in {csv_path}")

        rows = []
        for row in reader:
            repo_url = (row.get("repo_url") or "").strip()
            if not repo_url:
                continue
            rows.append({
                "repo_url": repo_url,
                "CloneStatus": (row.get("CloneStatus") or "").strip(),
                "IndexStatus": (row.get("IndexStatus") or "").strip(),
            })
        return rows


def write_repository_rows(csv_path: Path, rows):
    """Atomically save indexing status changes to the repository CSV file."""
    temporary_path = csv_path.with_suffix(f"{csv_path.suffix}.tmp")
    with temporary_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary_path.replace(csv_path)


def repo_name_from_url(repo_url: str) -> str:
    """Derive the local clone directory name from a Git URL."""
    name = repo_url.rstrip("/").rsplit("/", maxsplit=1)[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name


def main():
    """Index only repositories whose IndexStatus is exactly YetToStart."""
    if not ENV_FILE.is_file():
        print(f"ERROR: Environment file not found: {ENV_FILE}", file=sys.stderr)
        sys.exit(1)

    if not CODEBASE_MEMORY_MCP_BIN.is_file():
        print(f"ERROR: codebase-memory-mcp binary not found at: {CODEBASE_MEMORY_MCP_BIN}", file=sys.stderr)
        print("Install dependencies with: python3 -m pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)

    try:
        rows = load_repository_rows(REPO_LIST_FILE)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    if not rows:
        print(f"ERROR: No repository URLs found in {REPO_LIST_FILE}", file=sys.stderr)
        sys.exit(1)

    CBM_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    failures = []

    for row in rows:
        repo_url = row["repo_url"].strip()
        name = repo_name_from_url(repo_url)
        target_dir = CLONE_DIR / name

        if row["CloneStatus"] not in {"cloned", "cloned again"}:
            message = f"{name}: clone status is not ready in {REPO_LIST_FILE}"
            failures.append(message)
            print(f"Skipping {message}", file=sys.stderr)
            continue

        if row["IndexStatus"] == "Indexed":
            print(f"Already indexed and unchanged: {name}")
            continue

        if row["IndexStatus"] != "YetToStart":
            message = f"{name}: unexpected IndexStatus '{row['IndexStatus']}'"
            failures.append(message)
            print(f"Skipping {message}", file=sys.stderr)
            continue

        if not (target_dir / ".git").is_dir():
            message = f"{name}: cloned repository not found at {target_dir}"
            failures.append(message)
            print(f"Skipping {message}", file=sys.stderr)
            continue

        print(f"Indexing repository: {target_dir}")
        try:
            index_arguments = json.dumps({
                "repo_path": str(target_dir),
            })
            run_command([
                str(CODEBASE_MEMORY_MCP_BIN),
                "cli",
                "--progress",
                "index_repository",
                index_arguments,
            ])
            row["IndexStatus"] = "Indexed"
            write_repository_rows(REPO_LIST_FILE, rows)
            print(f"Finished indexing {name}\n{'-' * 40}")
        except subprocess.CalledProcessError as exc:
            failures.append(f"{name}: CBM exited with status {exc.returncode}")

    if failures:
        print("\nSome repositories were not indexed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        sys.exit(1)

    print("All repositories are indexed.")
    print("Verification command:")
    print(f'  CBM_CACHE_DIR="{CBM_CACHE_DIR}" "{CODEBASE_MEMORY_MCP_BIN}" cli list_projects')


if __name__ == "__main__":
    main()
