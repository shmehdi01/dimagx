"""
dimagx-commit-log
Called automatically by the post-commit git hook.
Finds the project root and logs the latest commit to the graph.
"""

from pathlib import Path


def main():
    # Walk up from cwd to find .dimagx
    current = Path.cwd()
    root = None
    for parent in [current, *current.parents]:
        if (parent / ".dimagx" / "config.yaml").exists():
            root = parent
            break

    if root is None:
        return  # Not a DimagX project — silently exit

    from dimagx.githook import log_latest_commit
    log_latest_commit(root)


if __name__ == "__main__":
    main()
