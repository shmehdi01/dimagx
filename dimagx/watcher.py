"""
DimagX File Watcher
Watches the project directory and .dimagx/prd/ folder.
- Code file saved → re-index in graph
- PRD dropped in .dimagx/prd/ → auto-ingest
Runs as a background process via `dimagx watch`
"""

import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent
from watchdog.observers import Observer

from dimagx.scanner import INDEXABLE_EXTENSIONS, IGNORE_DIRS
from dimagx.db import get_db, get_conn, upsert_file, link_project_file
from dimagx.graph import init_schema
from dimagx.config import load_config


PRD_EXTENSIONS = {".md", ".markdown", ".pdf", ".txt", ".docx"}


class CodeFileHandler(FileSystemEventHandler):
    """Re-indexes source files when saved."""

    def __init__(self, root: Path, memory_dir: Path, project_id: str):
        self.root       = root
        self.memory_dir = memory_dir
        self.project_id = project_id
        self._last: dict = {}   # debounce: path → last event time

    def _should_index(self, path: Path) -> bool:
        if path.suffix not in INDEXABLE_EXTENSIONS:
            return False
        if any(part in IGNORE_DIRS for part in path.parts):
            return False
        if self.memory_dir in path.parents:
            return False
        return True

    def _debounce(self, src: str, gap: float = 1.0) -> bool:
        now = time.time()
        if now - self._last.get(src, 0) < gap:
            return False
        self._last[src] = now
        return True

    def on_modified(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if not self._should_index(path) or not self._debounce(event.src_path):
            return
        self._index(path)

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if self._should_index(path):
            self._index(path)

    def _index(self, path: Path):
        try:
            rel = path.relative_to(self.root)
            file_id = hashlib.md5(str(rel).encode()).hexdigest()[:12]
            db   = get_db(self.memory_dir)
            conn = get_conn(db)
            init_schema(conn)
            upsert_file(conn, file_id, str(rel), path.suffix.lstrip("."), "", datetime.now().isoformat())
            link_project_file(conn, self.project_id, file_id)
            conn.close()
            print(f"  [dimagx] indexed: {rel}", flush=True)
        except Exception as e:
            print(f"  [dimagx] index error {path}: {e}", flush=True)


class PRDFolderHandler(FileSystemEventHandler):
    """Auto-ingests PRD files dropped in .dimagx/prd/"""

    def __init__(self, root: Path, memory_dir: Path, project_id: str, api_key: Optional[str]):
        self.root       = root
        self.memory_dir = memory_dir
        self.project_id = project_id
        self.api_key    = api_key

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() not in PRD_EXTENSIONS:
            return
        print(f"  [dimagx] PRD detected: {path.name}", flush=True)
        self._ingest(path)

    def _ingest(self, path: Path):
        if not self.api_key:
            print("  [dimagx] No API key — skipping auto PRD summarization", flush=True)
            return
        try:
            from dimagx.prd import extract_text, summarize_prd, store_prd
            text = extract_text(path)
            if len(text.strip()) < 50:
                return
            prd_data = summarize_prd(text, self.api_key)
            db   = get_db(self.memory_dir)
            conn = get_conn(db)
            init_schema(conn)
            prd_id = store_prd(self.memory_dir, self.project_id, prd_data, str(path), prd_data.get("version", "v1"))
            conn.close()
            print(f"  [dimagx] PRD ingested: {prd_data.get('title', path.name)} ({prd_id})", flush=True)
        except Exception as e:
            print(f"  [dimagx] PRD ingest error: {e}", flush=True)


def run_watcher(root: Path, api_key: Optional[str] = None):
    """Start file watcher — blocks until Ctrl+C."""
    from dimagx.config import load_config
    import hashlib

    memory_dir = root / ".dimagx"
    config     = load_config(root)
    project_id = hashlib.md5(config["project"].encode()).hexdigest()[:12]
    prd_dir    = memory_dir / "prd"
    prd_dir.mkdir(exist_ok=True)

    observer = Observer()

    # Watch project root for code changes
    observer.schedule(
        CodeFileHandler(root, memory_dir, project_id),
        path=str(root),
        recursive=True,
    )

    # Watch PRD folder for new docs
    observer.schedule(
        PRDFolderHandler(root, memory_dir, project_id, api_key),
        path=str(prd_dir),
        recursive=False,
    )

    observer.start()
    print(f"[dimagx] Watching {root}", flush=True)
    print(f"[dimagx] PRD auto-ingest: {'enabled' if api_key else 'disabled (set ANTHROPIC_API_KEY)'}", flush=True)
    print(f"[dimagx] Press Ctrl+C to stop", flush=True)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n[dimagx] Watcher stopped.", flush=True)

    observer.join()
