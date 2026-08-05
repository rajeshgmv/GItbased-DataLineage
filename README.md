# Git-Based Data Lineage Indexer

This project clones or updates the Git repositories listed in `git_repo_list.csv`, then indexes them separately with Codebase Memory (CBM). The active SQLite graph indexes are kept inside this project under `.cbm-cache/`.

## Prerequisites

- Python 3.8 or newer
- Git
- Internet access for installing CBM and cloning repositories

## Installation

Create and activate a project virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install all Python dependencies and the CBM command-line package:

```bash
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

The `codebase-memory-mcp` PyPI package installs the command wrapper. On its first invocation, the wrapper downloads and caches the native CBM binary for the current operating system.

Verify the installation:

```bash
"$PWD/.venv/bin/codebase-memory-mcp" --version
```

## Path configuration

All project paths are configured in `.env`:

| Variable | Purpose |
|---|---|
| `PROJECT_DIR` | Root of this project |
| `CBM_CACHE_DIR` | Active CBM SQLite graph databases and CBM configuration |
| `REPO_LIST_FILE` | CSV file containing repository URLs and clone statuses |
| `CLONE_DIR` | Directory where repositories are cloned |
| `CODEBASE_MEMORY_MCP_BIN` | CBM executable installed in the virtual environment |
| `CBM_ALLOWED_ROOT` | Restricts CBM indexing to the local clone directory |

The included `.env` contains absolute paths for this checkout. Update those values if the project directory is moved. Values already exported in the shell take precedence over values in `.env`.

CBM permits only one active canonical cache root for an account at a time. Stop any running CBM daemon or active CBM commands before changing `CBM_CACHE_DIR`.

## Select repositories

Edit `git_repo_list.csv` and add one repository URL per row. Leave both status columns empty for a new entry:

```csv
repo_url,CloneStatus,IndexStatus
https://github.com/spring-petclinic/spring-petclinic-rest.git,,
https://github.com/example/another-repository.git,,
```

The scripts maintain these status values:

| Column | Status | Meaning |
|---|---|---|
| `CloneStatus` | `cloned` | Repository was cloned for the first time, or an existing clone was verified when it had no prior status |
| `CloneStatus` | `cloned again` | New remote commits were found after the repository's earlier version had already been indexed |
| `IndexStatus` | `YetToStart` | Repository is new or changed and needs to be indexed |
| `IndexStatus` | `Indexed` | CBM indexing completed successfully for the current clone |

## Clone or update repositories

With the virtual environment active, run:

```bash
python3 -m lib.clone_repos
```

For an existing clone, the script fetches `origin` and compares the local commit with the tracked remote branch. It updates the clone only when a clean fast-forward is possible. It never discards local modifications or resolves diverged history automatically.

Every new clone or successful remote update resets `IndexStatus` to `YetToStart`. If indexing was already pending, a remote update keeps `CloneStatus` as `cloned`; there is still only one pending initial index. If the earlier version was already indexed, a remote update changes `CloneStatus` to `cloned again`. If a repository is already current, its existing statuses are preserved. Failures are reported after every CSV entry has been attempted.

## Index repositories

After cloning finishes successfully, run indexing separately:

```bash
python3 -m lib.index_repos
```

Only rows with a ready `CloneStatus`, an `IndexStatus` of `YetToStart`, and a valid local Git checkout are indexed. Successful indexing changes `IndexStatus` to `Indexed`; unchanged rows already marked `Indexed` are skipped. CBM 0.8.1 derives each project name from its absolute repository path, and the active graph index is stored in `.cbm-cache/`.

## Run the complete workflow

To clone or update all repositories first and then index pending repositories, run:

```bash
python3 main.py
```

The indexing phase starts only if the cloning phase completes without errors.

## Query the indexes

Load the same environment used during indexing:

```bash
set -a
source .env
set +a
```

List indexed projects:

```bash
"$CODEBASE_MEMORY_MCP_BIN" cli list_projects
```

Copy the exact project name returned by `list_projects`, then inspect its schema and architecture:

```bash
PROJECT_NAME="paste-the-exact-project-name-here"
"$CODEBASE_MEMORY_MCP_BIN" cli get_graph_schema "{\"project\":\"$PROJECT_NAME\"}"
"$CODEBASE_MEMORY_MCP_BIN" cli get_architecture "{\"project\":\"$PROJECT_NAME\"}"
```

CBM 0.8.1 accepts each tool's arguments as one JSON object, as shown above. The same `CBM_CACHE_DIR` must be used for both indexing and querying. The databases in `.cbm-cache/` are the active indexes; a repository's optional `.codebase-memory/graph.db.zst` persistence artifact is a separate portable bootstrap artifact.

## Generated directories

```text
.cbm-cache/       Active CBM SQLite indexes and logs
.venv/            Python virtual environment and installed CBM wrapper
repo_local_clone/ Cloned source repositories
```

These directories can be regenerated and normally should not be committed to Git.
