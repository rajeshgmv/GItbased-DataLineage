#!/usr/bin/env python3
from lib.clone_repos import main as clone_repositories
from lib.index_repos import main as index_repositories

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


if __name__ == "__main__":
    main()
