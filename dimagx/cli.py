"""
DimagX CLI
The brain of your project. One init. Always oriented.

Usage:
    dimagx init
    dimagx status
    dimagx feature start "Feature name"
    dimagx feature list
    dimagx feature done "Feature name"
"""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table

from dimagx import config as cfg
from dimagx import scanner
from dimagx.graph import init_schema
from dimagx.db import (
    get_db, get_conn, count_nodes,
    upsert_project, upsert_file, upsert_commit, upsert_feature,
    link_project_file, link_project_commit, link_project_feature,
)

app = typer.Typer(
    name="dimagx",
    help="DimagX — Project brain for coding agents.",
    add_completion=False,
)
console = Console()

feature_app = typer.Typer(help="Manage features")
app.add_typer(feature_app, name="feature")


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_id(value: str, prefix: str = "") -> str:
    h = hashlib.md5(value.encode()).hexdigest()[:12]
    return f"{prefix}{h}" if prefix else h


def find_project_root() -> Optional[Path]:
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / ".dimagx" / "config.yaml").exists():
            return parent
    return None


def require_init() -> Path:
    root = find_project_root()
    if not root:
        console.print("[red]✗[/red] No DimagX project found. Run [bold]dimagx init[/bold] first.")
        raise typer.Exit(1)
    return root


# ── Init ───────────────────────────────────────────────────────────────────────

@app.command()
def init():
    """Initialize DimagX in the current project."""

    root = Path.cwd()
    memory_dir = cfg.get_memory_dir(root)

    if cfg.config_exists(root):
        console.print(Panel(
            "[yellow]DimagX already initialized.[/yellow]\n"
            "Run [bold]dimagx status[/bold] to see what's indexed.",
            title="[bold yellow]Already Initialized[/bold yellow]",
            border_style="yellow"
        ))
        raise typer.Exit()

    console.print(Panel(
        "[bold cyan]DimagX[/bold cyan] — Project brain for coding agents\n"
        "[dim]Scans your project, builds a memory graph, powers any coding agent.[/dim]",
        border_style="cyan"
    ))

    # Detect existing vs empty project
    has_code = bool(
        list(root.glob("**/*.py"))[:1] or
        list(root.glob("**/*.ts"))[:1] or
        list(root.glob("**/*.js"))[:1] or
        (root / "package.json").exists()
    )

    if has_code:
        console.print("\n[green]Existing project detected.[/green] Scanning...\n")
        detected_stack = scanner.detect_stack(root)
    else:
        console.print("\n[blue]Empty project detected.[/blue] Starting fresh.\n")
        detected_stack = []

    # Gather project info
    project_name = Prompt.ask("[bold]Project name[/bold]", default=root.name)
    project_desc = Prompt.ask("[bold]What are you building?[/bold]", default="")

    if detected_stack:
        console.print(f"\n[dim]Detected stack:[/dim] {', '.join(detected_stack)}")
        stack_input = Prompt.ask(
            "[bold]Confirm / edit stack[/bold] (comma separated)",
            default=", ".join(detected_stack)
        )
    else:
        stack_input = Prompt.ask(
            "[bold]Stack you plan to use[/bold] (comma separated)",
            default=""
        )

    stack = [s.strip() for s in stack_input.split(",") if s.strip()]

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        task = progress.add_task("Creating .dimagx folder structure...", total=None)

        (memory_dir / "prd").mkdir(parents=True, exist_ok=True)
        (memory_dir / "features").mkdir(exist_ok=True)
        (memory_dir / "decisions").mkdir(exist_ok=True)
        (memory_dir / ".gitignore").write_text("graph.db\n")

        progress.update(task, description="Saving config...")
        config = cfg.default_config(project_name, project_desc, stack)
        cfg.save_config(root, config)

        progress.update(task, description="Initializing graph database...")
        db = get_db(memory_dir)
        conn = get_conn(db)
        init_schema(conn)

        project_id = make_id(project_name)
        now = datetime.now().isoformat()

        upsert_project(
            conn,
            id=project_id,
            name=project_name,
            description=project_desc,
            stack=", ".join(stack),
            status="active",
            created=now,
        )

        file_count = 0
        commit_count = 0

        if has_code:
            progress.update(task, description="Scanning files...")
            files = scanner.scan_files(root)
            file_count = len(files)

            for f in files:
                upsert_file(conn, f["id"], f["path"], f["language"], f["purpose"], f["updated"])
                link_project_file(conn, project_id, f["id"])

            if scanner.is_git_repo(root):
                progress.update(task, description="Reading git history...")
                commits = scanner.read_git_history(root, limit=30)
                commit_count = len(commits)
                for c in commits:
                    upsert_commit(conn, c["id"], c["hash"], c["message"], c["summary"], c["author"], c["date"])
                    link_project_commit(conn, project_id, c["id"])

        progress.update(task, description="Done!")

    conn.close()

    # Auto-install git hook if this is a git repo
    from dimagx.githook import install_hook
    hook_installed = install_hook(root)

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("[green]✔[/green]", "Config saved",   "[dim].dimagx/config.yaml[/dim]")
    table.add_row("[green]✔[/green]", "Graph DB ready", "[dim].dimagx/graph.db[/dim]")
    table.add_row("[green]✔[/green]", "PRD folder",     "[dim].dimagx/prd/[/dim]")
    if file_count:
        table.add_row("[green]✔[/green]", "Files indexed", f"[dim]{file_count} files[/dim]")
    if commit_count:
        table.add_row("[green]✔[/green]", "Git history",   f"[dim]{commit_count} commits[/dim]")
    if hook_installed:
        table.add_row("[green]✔[/green]", "Git hook",      "[dim]commits auto-logged[/dim]")

    console.print()
    console.print(Panel(
        table,
        title=f"[bold green]✓ {project_name} initialized[/bold green]",
        border_style="green"
    ))

    console.print(
        "\n[dim]Next steps:[/dim]\n"
        "  Drop PRDs in [bold].dimagx/prd/[/bold]\n"
        "  Run [bold]dimagx feature start \"Feature name\"[/bold] when starting work\n"
        "  Run [bold]dimagx watch[/bold] to auto-index file changes\n"
        "  Connect agent: [bold]dimagx mcp[/bold]\n"
    )


# ── Status ─────────────────────────────────────────────────────────────────────

@app.command()
def status():
    """Show current project memory status."""
    root = require_init()
    config = cfg.load_config(root)
    memory_dir = cfg.get_memory_dir(root)

    db = get_db(memory_dir)
    conn = get_conn(db)

    table = Table(
        title=f"[bold cyan]{config['project']}[/bold cyan] — DimagX Memory",
        box=None,
        padding=(0, 2),
    )
    table.add_column("Layer",   style="bold")
    table.add_column("Count",   justify="right", style="cyan")
    table.add_column("",        style="dim")

    layers = [
        ("Files",     "File",     "indexed from codebase"),
        ("Features",  "Feature",  "tagged work units"),
        ("PRDs",      "PRD",      "product requirements"),
        ("Prompts",   "Prompt",   "agent prompt logs"),
        ("Commits",   "Commit",   "git history"),
        ("Decisions", "Decision", "architectural ADRs"),
    ]
    for label, node, desc in layers:
        table.add_row(label, str(count_nodes(conn, node)), desc)

    conn.close()

    console.print()
    console.print(table)
    console.print(f"\n[dim]Stack:[/dim]       {', '.join(config.get('stack', []))}")
    console.print(f"[dim]Description:[/dim] {config.get('description', '')}\n")


# ── Feature commands ───────────────────────────────────────────────────────────

@feature_app.command("start")
def feature_start(title: str = typer.Argument(..., help="Feature name")):
    """Mark a feature as started and add to graph."""
    root = require_init()
    memory_dir = cfg.get_memory_dir(root)
    config = cfg.load_config(root)

    db = get_db(memory_dir)
    conn = get_conn(db)
    init_schema(conn)

    feature_id = make_id(title, prefix="feat_")
    now = datetime.now().isoformat()

    upsert_feature(conn, feature_id, title, "", "in_progress", now, now)
    link_project_feature(conn, make_id(config["project"]), feature_id)
    conn.close()

    console.print(f"\n[green]✔[/green] Feature started: [bold]{title}[/bold]")
    console.print(f"[dim]ID: {feature_id}[/dim]\n")


@feature_app.command("done")
def feature_done(title: str = typer.Argument(..., help="Feature name")):
    """Mark a feature as done."""
    root = require_init()
    memory_dir = cfg.get_memory_dir(root)

    db = get_db(memory_dir)
    conn = get_conn(db)

    feature_id = make_id(title, prefix="feat_")
    now = datetime.now().isoformat()
    upsert_feature(conn, feature_id, title, "", "done", now, now)
    conn.close()

    console.print(f"\n[green]✔[/green] Feature marked done: [bold]{title}[/bold]\n")


@feature_app.command("list")
def feature_list():
    """List all features."""
    root = require_init()
    memory_dir = cfg.get_memory_dir(root)

    db = get_db(memory_dir)
    conn = get_conn(db)

    result = conn.execute(
        "MATCH (f:Feature) RETURN f.title, f.status, f.updated ORDER BY f.updated DESC"
    )

    rows = []
    while result.has_next():
        rows.append(result.get_next())
    conn.close()

    if not rows:
        console.print("\n[dim]No features yet. Run `dimagx feature start \"name\"`[/dim]\n")
        return

    status_colors = {
        "in_progress": "[yellow]in progress[/yellow]",
        "done":        "[green]done[/green]",
        "planned":     "[blue]planned[/blue]",
    }

    table = Table(title="Features", box=None, padding=(0, 2))
    table.add_column("Title",   style="bold")
    table.add_column("Status",  justify="center")
    table.add_column("Updated", style="dim")

    for title, status_val, updated in rows:
        colored = status_colors.get(status_val, status_val)
        table.add_row(title, colored, (updated or "")[:10])

    console.print()
    console.print(table)
    console.print()


# ── Entry ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()

# ── Decision commands ──────────────────────────────────────────────────────────

decision_app = typer.Typer(help="Log architectural decisions (ADRs)")
app.add_typer(decision_app, name="decision")


@decision_app.command("add")
def decision_add(
    title:   str = typer.Option(..., "--title",   "-t", prompt=True, help="Short decision name"),
    context: str = typer.Option(..., "--context", "-c", prompt=True, help="What problem triggered this?"),
    choice:  str = typer.Option(..., "--choice",  "-d", prompt=True, help="What was decided?"),
    reason:  str = typer.Option(..., "--reason",  "-r", prompt=True, help="Why this over alternatives?"),
):
    """Log an architectural decision (ADR)."""
    from dimagx.db import esc
    root = require_init()
    memory_dir = cfg.get_memory_dir(root)
    config = cfg.load_config(root)

    db = get_db(memory_dir)
    conn = get_conn(db)
    init_schema(conn)

    decision_id = f"adr_{make_id(title)}"
    project_id  = make_id(config["project"])
    now = datetime.now().isoformat()

    conn.execute(f"""
        MERGE (d:Decision {{id: '{esc(decision_id)}'}})
        ON CREATE SET
            d.title   = '{esc(title)}',
            d.context = '{esc(context[:400])}',
            d.choice  = '{esc(choice[:400])}',
            d.reason  = '{esc(reason[:400])}',
            d.created = '{esc(now)}'
    """)
    try:
        conn.execute(f"""
            MATCH (p:Project {{id: '{esc(project_id)}'}}), (d:Decision {{id: '{esc(decision_id)}'}})
            MERGE (p)-[:HAS_DECISION]->(d)
        """)
    except Exception:
        pass
    conn.close()

    console.print(f"\n[green]✔[/green] Decision logged: [bold]{title}[/bold]")
    console.print(f"[dim]Choice:[/dim] {choice}")
    console.print(f"[dim]ID: {decision_id}[/dim]\n")


@decision_app.command("list")
def decision_list():
    """List all architectural decisions."""
    root = require_init()
    memory_dir = cfg.get_memory_dir(root)

    db = get_db(memory_dir)
    conn = get_conn(db)
    result = conn.execute(
        "MATCH (d:Decision) RETURN d.title, d.choice, d.reason, d.created ORDER BY d.created DESC"
    )
    rows = []
    while result.has_next():
        rows.append(result.get_next())
    conn.close()

    if not rows:
        console.print("\n[dim]No decisions yet. Run `dimagx decision add`[/dim]\n")
        return

    table = Table(title="Architectural Decisions", box=None, padding=(0, 2))
    table.add_column("Title",  style="bold")
    table.add_column("Choice", style="cyan")
    table.add_column("Date",   style="dim")

    for title, choice, reason, created in rows:
        table.add_row(title, (choice or "")[:50], (created or "")[:10])

    console.print()
    console.print(table)
    console.print()


# ── MCP command ────────────────────────────────────────────────────────────────

@app.command("mcp")
def mcp_cmd():
    """Start the DimagX MCP server for your coding agent."""
    require_init()
    console.print(Panel(
        "[bold cyan]DimagX MCP Server[/bold cyan]\n\n"
        "[dim]Add this to your agent config:[/dim]\n\n"
        "[bold]Claude Code[/bold] — .claude/mcp.json\n"
        '[dim]{"mcpServers": {"dimagx": {"command": "dimagx-mcp"}}}[/dim]\n\n'
        "[bold]Cursor / Windsurf[/bold] — .cursor/mcp.json\n"
        '[dim]{"mcpServers": {"dimagx": {"command": "dimagx-mcp"}}}[/dim]\n\n'
        "Starting [bold]stdio[/bold] server...",
        border_style="cyan"
    ))
    import subprocess, sys
    subprocess.run([sys.executable, "-m", "dimagx.mcp_server"])

# ── PRD commands ───────────────────────────────────────────────────────────────

prd_app = typer.Typer(help="Manage PRD documents")
app.add_typer(prd_app, name="prd")


@prd_app.command("ingest")
def prd_ingest(
    file:    Optional[Path] = typer.Argument(None,  help="Path to PRD file (.md, .pdf, .txt, .docx)"),
    api_key: Optional[str]  = typer.Option(None, "--api-key", "-k", help="Anthropic API key (or set ANTHROPIC_API_KEY)"),
    dir:     Optional[Path] = typer.Option(None, "--dir",     "-d", help="Ingest all PRD files from a directory"),
):
    """Ingest a PRD file or directory — summarize with AI and store in graph."""
    # ── Directory bulk ingest ──────────────────────────────────────────────────
    if dir is not None:
        if not dir.exists() or not dir.is_dir():
            console.print(f"[red]✗[/red] Directory not found: {dir}")
            raise typer.Exit(1)
        PRD_EXTS = {".md", ".markdown", ".pdf", ".txt", ".docx"}
        files = [f for f in dir.iterdir() if f.is_file() and f.suffix.lower() in PRD_EXTS]
        if not files:
            console.print(f"[yellow]No PRD files found in {dir}[/yellow]")
            raise typer.Exit()
        console.print(f"\n[cyan]Found {len(files)} PRD file(s) in {dir}[/cyan]\n")
        for f in files:
            console.print(f"[dim]Ingesting:[/dim] {f.name}")
            _ingest_single(f, api_key)
        console.print(f"\n[green]✔[/green] Bulk ingest complete — {len(files)} PRDs processed\n")
        return

    # ── Single file ingest ─────────────────────────────────────────────────────
    if file is None:
        console.print("[red]✗[/red] Provide a file path or use --dir for bulk ingest.")
        raise typer.Exit(1)
    _ingest_single(file, api_key)


def _ingest_single(file: Path, api_key: Optional[str] = None):
    """Internal — ingest one PRD file."""
    from dimagx.prd import extract_text, summarize_prd, store_prd, get_api_key
    from dimagx.db import esc

    root = require_init()
    memory_dir = cfg.get_memory_dir(root)
    config = cfg.load_config(root)
    key = api_key or get_api_key(root)

    if not file.exists():
        console.print(f"[red]✗[/red] File not found: {file}")
        raise typer.Exit(1)

    if not key:
        console.print(
            "[red]✗[/red] Anthropic API key required.\n"
            "  Set [bold]ANTHROPIC_API_KEY[/bold] env var or pass [bold]--api-key[/bold]"
        )
        raise typer.Exit(1)

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        task = progress.add_task(f"Reading {file.name}...", total=None)
        text = extract_text(file)

        if len(text.strip()) < 50:
            console.print(f"[red]✗[/red] File appears empty or unreadable: {file}")
            raise typer.Exit(1)

        progress.update(task, description="Summarizing with AI...")
        prd_data = summarize_prd(text, key)

        progress.update(task, description="Storing in graph...")
        db = get_db(memory_dir)
        conn = get_conn(db)
        init_schema(conn)

        project_id = make_id(config["project"])
        prd_id = store_prd(conn, project_id, prd_data, str(file), prd_data.get("version", "v1"))
        conn.close()

        progress.update(task, description="Done!")

    # Copy file into .dimagx/prd/ for reference
    dest = memory_dir / "prd" / file.name
    dest.write_bytes(file.read_bytes())

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("[green]✔[/green]", "Title",    prd_data.get("title", ""))
    table.add_row("[green]✔[/green]", "Summary",  (prd_data.get("summary", ""))[:80] + "...")
    table.add_row("[green]✔[/green]", "Features", str(len(prd_data.get("features", []))) + " extracted")
    table.add_row("[green]✔[/green]", "Stored",   f".dimagx/prd/{file.name}")

    console.print()
    console.print(Panel(
        table,
        title=f"[bold green]✓ PRD ingested[/bold green]",
        border_style="green"
    ))

    if prd_data.get("features"):
        console.print("[dim]Features auto-created:[/dim]")
        for f in prd_data["features"]:
            console.print(f"  • {f} [dim](planned)[/dim]")
    console.print()


@prd_app.command("list")
def prd_list():
    """List all ingested PRDs."""
    root = require_init()
    memory_dir = cfg.get_memory_dir(root)

    db = get_db(memory_dir)
    conn = get_conn(db)

    result = conn.execute(
        "MATCH (p:PRD) RETURN p.title, p.version, p.summary, p.source, p.created ORDER BY p.created DESC"
    )
    rows = []
    while result.has_next():
        rows.append(result.get_next())
    conn.close()

    if not rows:
        console.print("\n[dim]No PRDs yet. Run `dimagx prd ingest <file>`[/dim]\n")
        return

    table = Table(title="PRDs", box=None, padding=(0, 2))
    table.add_column("Title",   style="bold")
    table.add_column("Ver",     style="cyan", justify="center")
    table.add_column("Summary", style="dim")
    table.add_column("Date",    style="dim")

    for title, version, summary, source, created in rows:
        table.add_row(
            title or "",
            version or "v1",
            (summary or "")[:60] + ("..." if len(summary or "") > 60 else ""),
            (created or "")[:10],
        )

    console.print()
    console.print(table)
    console.print()


@prd_app.command("show")
def prd_show(title: str = typer.Argument(..., help="PRD title to show details")):
    """Show full details of a PRD including linked features."""
    from dimagx.db import esc

    root = require_init()
    memory_dir = cfg.get_memory_dir(root)

    db = get_db(memory_dir)
    conn = get_conn(db)

    result = conn.execute(
        f"MATCH (p:PRD) WHERE p.title CONTAINS '{esc(title)}' "
        "RETURN p.title, p.version, p.summary, p.source, p.created LIMIT 1"
    )

    if not result.has_next():
        console.print(f"\n[red]✗[/red] PRD not found: {title}\n")
        conn.close()
        raise typer.Exit(1)

    row = result.get_next()
    prd_title, version, summary, source, created = row

    # Get linked features
    feat_result = conn.execute(
        f"MATCH (p:PRD)-[:COVERS]->(f:Feature) WHERE p.title CONTAINS '{esc(title)}' "
        "RETURN f.title, f.status"
    )
    features = []
    while feat_result.has_next():
        features.append(feat_result.get_next())
    conn.close()

    console.print()
    console.print(Panel(
        f"[bold]{prd_title}[/bold] [dim]({version})[/dim]\n\n"
        f"{summary}\n\n"
        f"[dim]Source:[/dim] {source}\n"
        f"[dim]Ingested:[/dim] {(created or '')[:10]}",
        title="PRD Details",
        border_style="cyan"
    ))

    if features:
        console.print("[dim]Linked features:[/dim]")
        for feat_title, feat_status in features:
            console.print(f"  • {feat_title} [dim]({feat_status})[/dim]")
    console.print()

# ── Watch command ──────────────────────────────────────────────────────────────

@app.command("watch")
def watch(
    api_key:    Optional[str]  = typer.Option(None,   "--api-key",    "-k", help="Anthropic API key for PRD auto-ingest"),
    background: bool           = typer.Option(False,  "--background", "-b", help="Run as background daemon"),
    stop:       bool           = typer.Option(False,  "--stop",             help="Stop background watcher"),
):
    """Watch project for file changes — auto re-indexes code and PRDs."""
    import os, sys, signal
    root = require_init()
    key  = api_key or os.environ.get("ANTHROPIC_API_KEY")
    pid_file = cfg.get_memory_dir(root) / "watcher.pid"

    # ── Stop daemon ──────────────────────────────────────────────────────
    if stop:
        if not pid_file.exists():
            console.print("[yellow]No background watcher running.[/yellow]")
            raise typer.Exit()
        pid = int(pid_file.read_text().strip())
        try:
            os.kill(pid, signal.SIGTERM)
            pid_file.unlink(missing_ok=True)
            console.print(f"[green]✔[/green] Watcher stopped (PID {pid})")
        except ProcessLookupError:
            pid_file.unlink(missing_ok=True)
            console.print("[dim]Watcher was not running.[/dim]")
        raise typer.Exit()

    # ── Background daemon ─────────────────────────────────────────────────
    if background:
        import subprocess
        cmd = [sys.executable, "-m", "dimagx.watcher_daemon", str(root)]
        if key:
            cmd += ["--api-key", key]
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        pid_file.write_text(str(proc.pid))
        console.print(Panel(
            f"[bold cyan]DimagX Watcher[/bold cyan] — background\n"
            f"[dim]PID:[/dim] {proc.pid}\n"
            f"[dim]PRD auto-ingest:[/dim] {'enabled' if key else 'disabled'}\n\n"
            "Stop with: [bold]dimagx watch --stop[/bold]",
            border_style="cyan"
        ))
        raise typer.Exit()

    # ── Foreground (default) ──────────────────────────────────────────────
    console.print(Panel(
        "[bold cyan]DimagX Watcher[/bold cyan]\n"
        f"[dim]Project:[/dim] {root}\n"
        f"[dim]PRD auto-ingest:[/dim] {'enabled' if key else 'disabled — set ANTHROPIC_API_KEY'}\n\n"
        "Watching for file changes... [dim]Ctrl+C to stop[/dim]\n"
        "Tip: run [bold]dimagx watch --background[/bold] to daemonize",
        border_style="cyan"
    ))

    from dimagx.watcher import run_watcher
    run_watcher(root, api_key=key)


# ── Context command ────────────────────────────────────────────────────────────

@app.command("context")
def context():
    """Show a human-readable summary of where you left off."""
    from dimagx.db import esc

    root = require_init()
    memory_dir = cfg.get_memory_dir(root)
    config = cfg.load_config(root)

    db = get_db(memory_dir)
    conn = get_conn(db)

    # Active features
    r = conn.execute(
        "MATCH (f:Feature) WHERE f.status = 'in_progress' "
        "RETURN f.title, f.updated ORDER BY f.updated DESC LIMIT 5"
    )
    active = []
    while r.has_next():
        active.append(r.get_next())

    # Last 3 prompts
    r = conn.execute(
        "MATCH (p:Prompt) RETURN p.text, p.response_summary, p.outcome, p.created "
        "ORDER BY p.created DESC LIMIT 3"
    )
    prompts = []
    while r.has_next():
        prompts.append(r.get_next())

    # Last 5 commits
    r = conn.execute(
        "MATCH (c:Commit) RETURN c.hash, c.summary, c.date ORDER BY c.date DESC LIMIT 5"
    )
    commits = []
    while r.has_next():
        commits.append(r.get_next())

    # PRDs
    r = conn.execute("MATCH (p:PRD) RETURN p.title, p.version, p.summary ORDER BY p.created DESC LIMIT 3")
    prds = []
    while r.has_next():
        prds.append(r.get_next())

    # Recent decisions
    r = conn.execute("MATCH (d:Decision) RETURN d.title, d.choice ORDER BY d.created DESC LIMIT 3")
    decisions = []
    while r.has_next():
        decisions.append(r.get_next())

    conn.close()

    console.print()
    console.print(Panel(
        f"[bold]{config['project']}[/bold]  [dim]{config.get('description', '')}[/dim]\n"
        f"[dim]Stack:[/dim] {', '.join(config.get('stack', []))}",
        title="[bold cyan]DimagX — Project Context[/bold cyan]",
        border_style="cyan"
    ))

    if active:
        console.print("\n[bold yellow]⚡ In Progress[/bold yellow]")
        for title, updated in active:
            console.print(f"  • {title}  [dim]{(updated or '')[:10]}[/dim]")

    if prompts:
        console.print("\n[bold]🧠 Recent Agent Work[/bold]")
        for text, summary, outcome, created in prompts:
            console.print(f"  [{(created or '')[:10]}] [dim]{outcome}[/dim] {text[:60]}")
            if summary:
                console.print(f"    [dim]→ {summary[:80]}[/dim]")

    if commits:
        console.print("\n[bold]📝 Recent Commits[/bold]")
        for hash_, summary, date in commits:
            console.print(f"  [{hash_}] [dim]{(date or '')[:10]}[/dim] {(summary or '')[:70]}")

    if prds:
        console.print("\n[bold]📄 PRDs[/bold]")
        for title, version, summary in prds:
            console.print(f"  • {title} [dim]({version})[/dim]")
            if summary:
                console.print(f"    [dim]{summary[:80]}[/dim]")

    if decisions:
        console.print("\n[bold]🏗  Decisions[/bold]")
        for title, choice in decisions:
            console.print(f"  • {title} → [cyan]{(choice or '')[:60]}[/cyan]")

    console.print()

# ── Hook command ───────────────────────────────────────────────────────────────

hook_app = typer.Typer(help="Manage git hooks")
app.add_typer(hook_app, name="hook")


@hook_app.command("install")
def hook_install():
    """Install DimagX post-commit git hook."""
    from dimagx.githook import install_hook
    root = require_init()
    ok = install_hook(root)
    if ok:
        console.print("\n[green]✔[/green] Post-commit hook installed in [dim].git/hooks/post-commit[/dim]")
        console.print("[dim]Every git commit will now be auto-logged to DimagX.[/dim]\n")
    else:
        console.print("\n[red]✗[/red] No .git directory found. Is this a git repo?\n")


@hook_app.command("uninstall")
def hook_uninstall():
    """Remove DimagX post-commit git hook."""
    from dimagx.githook import uninstall_hook
    root = require_init()
    ok = uninstall_hook(root)
    if ok:
        console.print("\n[yellow]✔[/yellow] DimagX hook removed from post-commit.\n")
    else:
        console.print("\n[dim]No hook found to remove.[/dim]\n")
