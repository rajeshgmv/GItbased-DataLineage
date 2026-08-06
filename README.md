# Git-Based Data Lineage Indexer

This project clones or updates the Git repositories listed in `git_repo_list.csv`, then indexes them separately with Codebase Memory (CBM). The active SQLite graph indexes are kept inside this project under `.cbm-cache/`. after indexing is completed, context is created and fed into multi-AI agents to create lineage based on the context created.

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

Copy the committed example to create your local path configuration:

```bash
cp .env.example .env
```

All project paths are configured in the local `.env` file:

| Variable | Purpose |
|---|---|
| `PROJECT_DIR` | Root of this project |
| `CBM_CACHE_DIR` | Active CBM SQLite graph databases and CBM configuration |
| `REPO_LIST_FILE` | CSV file containing repository URLs and clone statuses |
| `CLONE_DIR` | Directory where repositories are cloned |
| `CODEBASE_MEMORY_MCP_BIN` | CBM executable installed in the virtual environment |
| `CBM_ALLOWED_ROOT` | Restricts CBM indexing to the local clone directory |
| `LINEAGE_CONTEXT_DIR` | Generated per-repository evidence packages for Agent 1 |

The committed `.env.example` uses paths relative to the project root. The local
`.env` file is ignored by Git, so it can be changed to absolute or machine-specific
paths without committing them. Values already exported in the shell take
precedence over values in `.env`.

CBM permits only one active canonical cache root for an account at a time. Stop any running CBM daemon or active CBM commands before changing `CBM_CACHE_DIR`.

## Select repositories

Edit `git_repo_list.csv` and add one repository URL per row. Leave all status columns empty for a new entry:

```csv
repo_url,CloneStatus,IndexStatus,ContextStatus
https://github.com/spring-petclinic/spring-petclinic-rest.git,,,
https://github.com/example/another-repository.git,,,
```

The scripts maintain these status values:

| Column | Status | Meaning |
|---|---|---|
| `CloneStatus` | `cloned` | Repository was cloned for the first time, or an existing clone was verified when it had no prior status |
| `CloneStatus` | `cloned again` | New remote commits were found after the repository's earlier version had already been indexed |
| `IndexStatus` | `YetToStart` | Repository is new or changed and needs to be indexed |
| `IndexStatus` | `Indexed` | CBM indexing completed successfully for the current clone |
| `ContextStatus` | empty | The current indexed repository still needs a lineage context export |
| `ContextStatus` | `Contexted` | All lineage context files were written successfully for the current index |

## Clone or update repositories

With the virtual environment active, run:

```bash
python3 -m lib.clone_repos
```

For an existing clone, the script fetches `origin` and compares the local commit with the tracked remote branch. It updates the clone only when a clean fast-forward is possible. It never discards local modifications or resolves diverged history automatically.

Every new clone or successful remote update resets `IndexStatus` to `YetToStart` and clears `ContextStatus`. If indexing was already pending, a remote update keeps `CloneStatus` as `cloned`; there is still only one pending initial index. If the earlier version was already indexed, a remote update changes `CloneStatus` to `cloned again`. If a repository is already current, its existing statuses are preserved. Failures are reported after every CSV entry has been attempted.

## Index repositories

After cloning finishes successfully, run indexing separately:

```bash
python3 -m lib.index_repos
```

Only rows with a ready `CloneStatus`, an `IndexStatus` of `YetToStart`, and a valid local Git checkout are indexed. Successful indexing changes `IndexStatus` to `Indexed` and clears `ContextStatus`; unchanged rows already marked `Indexed` are skipped. CBM 0.8.1 derives each project name from its absolute repository path, and the active graph index is stored in `.cbm-cache/`.

## Run the complete workflow

To clone or update all repositories first and then index pending repositories, run:

```bash
python3 main.py
```

The indexing phase starts only if the cloning phase completes without errors. Phase 3 then exports every indexed repository whose `ContextStatus` is empty or whose `CloneStatus` is `cloned again`.

## Export one repository for lineage analysis

After a repository has `IndexStatus=Indexed`, export its graph and graph-selected source evidence:

```bash
python3 -m lib.export_lineage_context --repo crypto-kaka-rag
```

After every context file is written successfully, the repository's `ContextStatus` is changed to `Contexted`. A failed export leaves the previous context status unchanged.

To export every pending repository without running clone and index phases, run:

```bash
python3 -m lib.export_lineage_context --all-pending
```

After a refreshed repository is exported successfully, its `CloneStatus` changes from `cloned again` back to `cloned`. Repositories that are not yet `Indexed` are skipped and retain their pending statuses.

The pilot export is written under `lineage_context/crypto-kaka-rag/`. CBM node labels, node metadata, and relationships select candidate symbols; exact source is then retrieved through each symbol's qualified name. This graph-first path is language-neutral and does not run regular-expression searches by default. Test, generated, dependency, and CI files are excluded from the compact Agent 1 context. Empty JSON attributes and redundant CBM `Module` records are also removed; data, schema, and configuration modules are represented in `artifacts.json`, while source modules are represented by retrieved source files. The exporter verifies its raw query counts against the CBM graph schema before writing the selected context.

Static CBM queries, graph allowlists, artifact extensions, limits, selection rules, and context limitations are maintained separately in `config/lineage_context_config.py`.

If the graph does not model an important boundary, explicitly enable the optional text fallback:

```bash
python3 -m lib.export_lineage_context --repo crypto-kaka-rag --enable-text-fallback
```

Fallback searches are configured in `config/lineage_fallback_search_queries.json` and are labeled separately in `source-evidence.json`. Graph relationships remain discovery evidence; source excerpts provide the assignments, configuration, SQL, schemas, and serialization needed to confirm lineage.

## Generate the repository lineage Markdown

After Agent 1 creates and validates a repository's `repo-lineage.json`, generate
the corresponding Markdown file from that JSON:

```bash
python -m lib.render_repository_lineage \
  lineage_output/crypto-kaka-rag/repo-lineage.json
```

By default, the command writes `repo-lineage.md` beside the input JSON file.

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
