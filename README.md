# DimagX 🧠

> **Project brain for coding agents.**  
> One command. Persistent memory. Switch models freely — your agent always knows where you left off.

---

## The Problem

Every time you start a new coding session, your agent reads your entire codebase from scratch. Switch from Claude to Cursor to GPT-4 — you re-explain everything. Your PRDs, decisions, and context live nowhere.

## The Solution

DimagX builds a **persistent memory graph** for your project — code, features, prompts, PRDs, git history, and architectural decisions — and exposes it to any coding agent via MCP.

```
Without DimagX                    With DimagX
─────────────────────             ─────────────────────
New session → agent reads         New session → agent calls
50 files, asks you to             get_context() → instantly
re-explain everything             oriented, no re-explaining
```

---

## How It Works

```
your-project/
└── .dimagx/              ← created by dimagx init
    ├── config.yaml       ← project identity
    ├── graph.db          ← Kuzu embedded graph (gitignored)
    └── prd/              ← drop PRDs here
```

DimagX indexes your codebase into a graph with 7 node types:

```
Project → File → Feature → Prompt → PRD → Decision → Commit
```

Your coding agent queries this graph via MCP instead of re-reading everything.

---

## Install

### Requirements
- Python 3.10+
- pip

### From source

```bash
git clone https://github.com/yourname/dimagx
cd dimagx
pip install -e .
```

### Verify

```bash
dimagx --help
```

---

## Quick Start

```bash
# Go to any project — new or existing
cd my-project

# Initialize DimagX (scans files, git history, builds graph)
dimagx init

# See what's in memory
dimagx status

# See where you left off
dimagx context
```

---

## All Commands

### Project
```bash
dimagx init              # Scan project, build memory graph
dimagx status            # Memory dashboard — node counts per layer
dimagx context           # Human summary: features, commits, prompts, PRDs
```

### Features
```bash
dimagx feature start "Pricing Engine"   # Tag what you're working on
dimagx feature done  "Pricing Engine"   # Mark it complete
dimagx feature list                      # Show all features + status
```

### PRDs
```bash
# Single file (MD, PDF, DOCX, TXT supported)
dimagx prd ingest ./docs/pricing.md

# Bulk — ingest entire folder
dimagx prd ingest --dir ./docs/prd/

# List and inspect
dimagx prd list
dimagx prd show "Pricing Engine"
```

> PRD ingestion requires an Anthropic API key for AI summarization.  
> Set `ANTHROPIC_API_KEY` in your environment.

### Decisions (Architectural Decision Records)
```bash
dimagx decision add      # Interactive — prompts for title, context, choice, reason
dimagx decision list     # Show all decisions
```

### File Watcher
```bash
dimagx watch                    # Foreground — auto re-index on file save
dimagx watch --background       # Background daemon
dimagx watch --stop             # Stop background watcher
```

### Git Hook
```bash
# Auto-installed on dimagx init if .git exists
# Manual control:
dimagx hook install             # Install post-commit hook
dimagx hook uninstall           # Remove hook
```

### MCP Server
```bash
dimagx mcp                      # Start MCP server + show agent config
```

---

## Connect to Your Coding Agent

Add to your agent config and it automatically calls `get_context()` at the start of every session.

**Claude Code** — `.claude/mcp.json`
```json
{
  "mcpServers": {
    "dimagx": {
      "command": "dimagx-mcp"
    }
  }
}
```

**Cursor / Windsurf** — `.cursor/mcp.json`
```json
{
  "mcpServers": {
    "dimagx": {
      "command": "dimagx-mcp"
    }
  }
}
```

### MCP Tools Available to Your Agent

| Tool | When to call | What it returns |
|---|---|---|
| `get_context()` | Start of every session | Full project orientation |
| `query_memory(question)` | Before asking the user anything | Relevant memory nodes |
| `log_prompt(text, summary, outcome)` | After completing a task | Stores in graph |
| `add_decision(title, context, choice, reason)` | After an architectural decision | Stored as ADR |
| `get_features(status?)` | When planning work | Feature list |
| `get_files(feature?, language?)` | When navigating codebase | Filtered file list |

---

## PRD Ingestion

DimagX reads your PRD, summarizes it with AI, extracts features, and links everything in the graph.

```bash
export ANTHROPIC_API_KEY=sk-ant-...

# Single file
dimagx prd ingest ./docs/auth_prd.md

# Bulk folder
dimagx prd ingest --dir ./docs/prd/
```

Supported formats: `.md` `.pdf` `.docx` `.txt`

Multi-PRD projects are fully supported — each PRD is a separate node linked to its features:

```
prd_auth      → covers → [OTP Login, Session Mgmt, RBAC]
prd_pricing   → covers → [GST Calc, Discount Engine, Charges]
prd_store     → covers → [QR Menu, Cart, Online Payment]
```

---

## Daily Workflow

```bash
cd my-project

# Morning — see where you left off
dimagx context

# Start a feature
dimagx feature start "Online Store"

# Start background watcher
dimagx watch --background

# Work normally — files auto-indexed, commits auto-logged

# Log a decision
dimagx decision add

# End of day — check memory
dimagx status
```

---

## What Gets Stored Automatically

| Layer | Source | How |
|---|---|---|
| Files | Codebase | Auto on `init` + `watch` |
| Git commits | Git history | Auto on `init` + post-commit hook |
| Features | You | `dimagx feature start` |
| PRDs | You drop files | `dimagx prd ingest` or auto via `watch` |
| Prompts | Agent sessions | MCP `log_prompt()` |
| Decisions | You / agent | `dimagx decision add` / MCP |

---

## Architecture

```
┌─────────────────────────────────────────┐
│              Your Codebase              │
└──────────────┬──────────────────────────┘
               │ dimagx init / watch
               ▼
┌─────────────────────────────────────────┐
│           DimagX Memory Graph           │
│  (Kuzu embedded graph DB — .dimagx/)    │
│                                         │
│  Project ── File ── Feature             │
│     │          │       │                │
│  Commit     Prompt    PRD               │
│                │       │                │
│            Decision ───┘                │
└──────────────┬──────────────────────────┘
               │ MCP (stdio)
               ▼
┌─────────────────────────────────────────┐
│         Any Coding Agent                │
│  Claude Code / Cursor / Windsurf / etc  │
└─────────────────────────────────────────┘
```

---

## Stack

| Component | Library |
|---|---|
| Graph DB | [Kuzu](https://kuzudb.com/) — embedded, no server needed |
| CLI | [Typer](https://typer.tiangolo.com/) + [Rich](https://rich.readthedocs.io/) |
| Agent protocol | [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) |
| File watcher | [Watchdog](https://python-watchdog.readthedocs.io/) |
| PRD summarization | [Anthropic SDK](https://github.com/anthropics/anthropic-sdk-python) |
| Code parsing | Tree-sitter (coming in v0.2) |

---

## Project Structure

```
dimagx/
├── dimagx/
│   ├── __init__.py        # Package entry
│   ├── cli.py             # All CLI commands
│   ├── mcp_server.py      # MCP server + tools
│   ├── graph.py           # Kuzu schema (7 nodes, 10 relationships)
│   ├── db.py              # DB upsert helpers
│   ├── scanner.py         # Stack detection, file scan, git history
│   ├── config.py          # .dimagx/config.yaml read/write
│   ├── prd.py             # PRD extraction + AI summarization
│   ├── watcher.py         # File system watcher
│   ├── watcher_daemon.py  # Background daemon entry point
│   ├── githook.py         # Git hook installer + commit logger
│   └── commit_log.py      # Called by post-commit hook
├── pyproject.toml
├── setup.py
└── README.md
```

---

## Roadmap

- [ ] Semantic search (embeddings) in `query_memory`
- [ ] Tree-sitter code parsing — function/class level indexing
- [ ] `dimagx feature update` — add description post-creation
- [ ] Web UI — browser-based memory explorer
- [ ] PyPI publish — `pip install dimagx`
- [ ] VS Code extension

---

## Contributing

PRs welcome. Please open an issue first for major changes.

```bash
git clone https://github.com/yourname/dimagx
cd dimagx
pip install -e .
```

---

## License

MIT — use it, fork it, build on it.

---

## Built by

[@syedhussainmehdi](https://github.com/shmehdi01) - SYED HUSSAIN MEHDI.

> *"Dimaag" (دماغ) means brain in Urdu/Hindi. DimagX is the brain your coding agent never had.*
