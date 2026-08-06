#!/usr/bin/env python3
import csv
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

from config.lineage_context_config import CSV_FIELDS, CONTEXT_STATUS_PENDING


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
REPO_LIST_FILE = configured_path("REPO_LIST_FILE", PROJECT_DIR / "git_repo_list.csv")
CLONE_DIR = configured_path("CLONE_DIR", PROJECT_DIR / "repo_local_clone")


def run_command(cmd, cwd=None, capture_output=False, check=True):
    """Run a subprocess and report useful command details when it fails."""
    try:
        return subprocess.run(
            cmd,
            cwd=cwd,
            check=check,
            capture_output=capture_output,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: command failed: {' '.join(cmd)}", file=sys.stderr)
        if exc.stderr:
            print(exc.stderr.strip(), file=sys.stderr)
        raise


def load_repository_rows(csv_path: Path):
    """Load and validate repository clone, index, and context statuses."""
    if not csv_path.is_file():
        raise FileNotFoundError(f"Repository CSV file not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames != list(CSV_FIELDS):
            expected = ",".join(CSV_FIELDS)
            raise ValueError(f"Expected CSV header '{expected}' in {csv_path}")

        rows = []
        for line_number, row in enumerate(reader, start=2):
            repo_url = (row.get("repo_url") or "").strip()
            if not repo_url:
                print(f"Skipping empty repository URL at CSV line {line_number}")
                continue
            rows.append({
                "repo_url": repo_url,
                "CloneStatus": (row.get("CloneStatus") or "").strip(),
                "IndexStatus": (row.get("IndexStatus") or "").strip(),
                "ContextStatus": (row.get("ContextStatus") or "").strip(),
            })
    return rows


def write_repository_rows(csv_path: Path, rows):
    """Atomically save repository rows so an interrupted write cannot corrupt the CSV."""
    temporary_path = csv_path.with_suffix(f"{csv_path.suffix}.tmp")
    with temporary_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=CSV_FIELDS,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    temporary_path.replace(csv_path)


def repo_name_from_url(repo_url: str) -> str:
    """Derive the local clone directory name from a Git URL."""
    name = repo_url.rstrip("/").rsplit("/", maxsplit=1)[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name


def git_output(repo_dir: Path, *args):
    """Run a Git command in a repository and return its trimmed standard output."""
    result = run_command(
        ["git", *args],
        cwd=repo_dir,
        capture_output=True,
    )
    return result.stdout.strip()


def clone_or_update_repository(repo_url: str, target_dir: Path):
    """Clone a new repository or safely fast-forward an unchanged local checkout."""
    if not target_dir.exists():
        print(f"Cloning {repo_url} into {target_dir}")
        run_command(["git", "clone", repo_url, str(target_dir)])
        return "cloned"

    if not (target_dir / ".git").is_dir():
        raise RuntimeError(f"Target exists but is not a Git repository: {target_dir}")

    print(f"Checking existing repository: {target_dir}")
    run_command(["git", "fetch", "--prune", "origin"], cwd=target_dir)

    try:
        upstream = git_output(
            target_dir,
            "rev-parse",
            "--abbrev-ref",
            "--symbolic-full-name",
            "@{upstream}",
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"The current branch in {target_dir} has no upstream branch."
        ) from exc

    local_commit = git_output(target_dir, "rev-parse", "HEAD")
    remote_commit = git_output(target_dir, "rev-parse", upstream)
    if local_commit == remote_commit:
        print(f"Already up to date: {target_dir}")
        return None

    working_tree_changes = git_output(target_dir, "status", "--porcelain")
    if working_tree_changes:
        raise RuntimeError(
            f"Remote changes exist, but {target_dir} has local changes. "
            "Commit or stash them before updating."
        )

    ancestry_check = run_command(
        ["git", "merge-base", "--is-ancestor", "HEAD", upstream],
        cwd=target_dir,
        check=False,
    )
    if ancestry_check.returncode != 0:
        raise RuntimeError(
            f"The local and remote histories have diverged in {target_dir}; "
            "automatic updating was skipped."
        )

    print(f"Remote changes found; fast-forwarding {target_dir}")
    run_command(["git", "merge", "--ff-only", upstream], cwd=target_dir)
    return "cloned again"


def main():
    """Clone or update every CSV repository and persist its resulting statuses."""
    if not ENV_FILE.is_file():
        print(f"ERROR: Environment file not found: {ENV_FILE}", file=sys.stderr)
        sys.exit(1)

    try:
        rows = load_repository_rows(REPO_LIST_FILE)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    if not rows:
        print(f"ERROR: No repository URLs found in {REPO_LIST_FILE}", file=sys.stderr)
        sys.exit(1)

    CLONE_DIR.mkdir(parents=True, exist_ok=True)
    failures = []

    for row in rows:
        repo_url = row["repo_url"]
        name = repo_name_from_url(repo_url)
        if not name:
            failures.append(f"Invalid repository URL: {repo_url}")
            continue

        target_dir = CLONE_DIR / name
        try:
            new_status = clone_or_update_repository(repo_url, target_dir)
            if new_status and row["IndexStatus"] == "YetToStart":
                row["CloneStatus"] = "cloned"
                row["IndexStatus"] = "YetToStart"
                row["ContextStatus"] = CONTEXT_STATUS_PENDING
            elif new_status:
                row["CloneStatus"] = new_status
                row["IndexStatus"] = "YetToStart"
                row["ContextStatus"] = CONTEXT_STATUS_PENDING
            elif not row["CloneStatus"]:
                row["CloneStatus"] = "cloned"
                row["IndexStatus"] = "YetToStart"
                row["ContextStatus"] = CONTEXT_STATUS_PENDING
            elif not row["IndexStatus"]:
                row["IndexStatus"] = "YetToStart"
                row["ContextStatus"] = CONTEXT_STATUS_PENDING
            write_repository_rows(REPO_LIST_FILE, rows)
        except (RuntimeError, subprocess.CalledProcessError) as exc:
            message = f"{name}: {exc}"
            failures.append(message)
            print(f"ERROR: {message}", file=sys.stderr)

    if failures:
        print("\nSome repositories could not be cloned or updated:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        sys.exit(1)

    print(f"\nAll repositories are ready in: {CLONE_DIR}")
    print(f"Clone, index, and context statuses were saved to: {REPO_LIST_FILE}")


if __name__ == "__main__":
    main()
