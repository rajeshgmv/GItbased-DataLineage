#!/usr/bin/env python3
from lib.clone_repos import main as clone_repositories
from lib.index_repos import main as index_repositories
from lib.export_lineage_context import export_pending_repository_contexts

def Title_printer(title: str):
    """Print a formatted title for the current phase."""
    print("=" * 100)
    print(f"\t\t\t\t\t{title}")
    print("=" * 100)

def main():
    """Clone or update all repositories before indexing pending repositories."""
    Title_printer("Phase 1: Clone or update repositories")
    clone_repositories()
    
    Title_printer("Phase 2: Index repositories")
    index_repositories()

    Title_printer("Phase 3: Creating lineage context")
    export_pending_repository_contexts()


if __name__ == "__main__":
    main()
