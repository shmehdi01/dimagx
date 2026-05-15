"""
DimagX Scanner
Detects stack, indexes files, reads git history on init
"""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import git as gitpython
    HAS_GIT = True
except ImportError:
    HAS_GIT = False


# ── Stack detection ────────────────────────────────────────────────────────────

STACK_SIGNALS = {
    "Python":     ["*.py", "requirements.txt", "pyproject.toml", "Pipfile"],
    "Node.js":    ["package.json", "*.js", "*.mjs"],
    "TypeScript": ["tsconfig.json", "*.ts"],
    "React":      ["*.jsx", "*.tsx"],
    "Supabase":   ["supabase/", ".supabase/"],
    "Android":    ["*.kt", "*.java", "AndroidManifest.xml", "build.gradle"],
    "Flutter":    ["pubspec.yaml", "*.dart"],
    "Go":         ["go.mod", "*.go"],
    "Rust":       ["Cargo.toml", "*.rs"],
    "Docker":     ["Dockerfile", "docker-compose.yml"],
    "PostgreSQL": ["*.sql", "migrations/"],
}

IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", ".dimagx", "target",
}

INDEXABLE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".kt",
    ".java", ".dart", ".sql", ".md", ".yaml", ".yml", ".json",
    ".toml", ".env",
}


def detect_stack(root: Path) -> list[str]:
    detected = []
    for tech, patterns in STACK_SIGNALS.items():
        for pattern in patterns:
            if pattern.endswith("/"):
                if (root / pattern.rstrip("/")).is_dir():
                    detected.append(tech)
                    break
            else:
                matches = list(root.glob(pattern)) + list(root.glob(f"**/{pattern}"))
                matches = [m for m in matches if not any(p in m.parts for p in IGNORE_DIRS)]
                if matches:
                    detected.append(tech)
                    break
    return detected


def scan_files(root: Path) -> list[dict]:
    """Return list of indexable files with metadata."""
    files = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix in INDEXABLE_EXTENSIONS:
            # Skip ignored dirs
            if any(part in IGNORE_DIRS for part in path.parts):
                continue
            rel = path.relative_to(root)
            file_id = hashlib.md5(str(rel).encode()).hexdigest()[:12]
            files.append({
                "id":       file_id,
                "path":     str(rel),
                "language": path.suffix.lstrip("."),
                "purpose":  "",          # filled by LLM later
                "updated":  datetime.now().isoformat(),
            })
    return files


def read_git_history(root: Path, limit: int = 30) -> list[dict]:
    """Read last N commits from git history."""
    if not HAS_GIT:
        return []
    try:
        repo = gitpython.Repo(root, search_parent_directories=True)
        commits = []
        for i, commit in enumerate(repo.iter_commits(max_count=limit)):
            commit_id = f"commit_{commit.hexsha[:8]}"
            commits.append({
                "id":      commit_id,
                "hash":    commit.hexsha[:8],
                "message": commit.message.strip(),
                "summary": commit.message.strip()[:120],
                "author":  str(commit.author),
                "date":    datetime.fromtimestamp(commit.committed_date).isoformat(),
            })
        return commits
    except Exception:
        return []


def is_git_repo(root: Path) -> bool:
    if not HAS_GIT:
        return False
    try:
        gitpython.Repo(root, search_parent_directories=True)
        return True
    except Exception:
        return False
