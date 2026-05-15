"""
DimagX Git Hook
Installs a post-commit hook that auto-logs every git commit into the graph.
"""

import hashlib
import os
import subprocess
from datetime import datetime
from pathlib import Path

HOOK_SCRIPT = """\
#!/bin/sh
# DimagX post-commit hook — auto-logs commit to project memory graph
dimagx-commit-log 2>/dev/null || true
"""


def install_hook(root: Path) -> bool:
    """Install post-commit hook into .git/hooks/"""
    git_dir = root / ".git"
    if not git_dir.exists():
        return False

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    hook_path = hooks_dir / "post-commit"

    # If hook already exists, append instead of overwrite
    if hook_path.exists():
        existing = hook_path.read_text()
        if "DimagX" in existing:
            return True  # already installed
        # Append to existing hook
        with open(hook_path, "a") as f:
            f.write("\n# DimagX\ndimagx-commit-log 2>/dev/null || true\n")
    else:
        hook_path.write_text(HOOK_SCRIPT)

    hook_path.chmod(0o755)
    return True


def uninstall_hook(root: Path) -> bool:
    """Remove DimagX lines from post-commit hook."""
    hook_path = root / ".git" / "hooks" / "post-commit"
    if not hook_path.exists():
        return False

    lines = hook_path.read_text().splitlines()
    cleaned = [l for l in lines if "dimagx" not in l.lower() and "DimagX" not in l]
    hook_path.write_text("\n".join(cleaned) + "\n")
    return True


def log_latest_commit(root: Path):
    """Read the latest git commit and store it in the graph."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H|%s|%an|%ai"],
            cwd=str(root),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return

        line = result.stdout.strip()
        if not line:
            return

        parts = line.split("|", 3)
        if len(parts) < 4:
            return

        full_hash, subject, author, date_str = parts
        short_hash = full_hash[:8]
        commit_id  = f"commit_{short_hash}"

        from dimagx.config import load_config
        from dimagx.db import get_db, get_conn, upsert_commit, link_project_commit
        from dimagx.graph import init_schema

        memory_dir = root / ".dimagx"
        config     = load_config(root)
        project_id = hashlib.md5(config["project"].encode()).hexdigest()[:12]

        db   = get_db(memory_dir)
        conn = get_conn(db)
        init_schema(conn)

        upsert_commit(
            conn,
            id=commit_id,
            hash_=short_hash,
            message=subject,
            summary=subject[:120],
            author=author,
            date=date_str,
        )
        link_project_commit(conn, project_id, commit_id)
        conn.close()

    except Exception as e:
        print(f"[dimagx] commit log error: {e}")
