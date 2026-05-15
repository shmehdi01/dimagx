"""
DimagX MCP Server
Exposes project memory to any coding agent that supports MCP.

Tools:
    get_context()              — session starter: returns full project orientation
    log_prompt(text, summary, feature?)  — capture agent prompt + outcome
    query_memory(question)     — semantic search over graph nodes
    add_decision(title, context, choice, reason) — log an ADR
    get_features()             — list all features and their status
    get_files(feature?)        — list indexed files, optionally filtered by feature
"""

import hashlib
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

# ── Locate project root ────────────────────────────────────────────────────────
# MCP server is launched from the project dir, so walk up from cwd

def find_project_root() -> Optional[Path]:
    current = Path(os.getcwd())
    for parent in [current, *current.parents]:
        if (parent / ".dimagx" / "config.yaml").exists():
            return parent
    return None


ROOT = find_project_root()
if ROOT is None:
    # If launched with --project flag
    if "--project" in sys.argv:
        idx = sys.argv.index("--project")
        ROOT = Path(sys.argv[idx + 1])
    else:
        print("ERROR: No DimagX project found. Run `dimagx init` first.", file=sys.stderr)
        sys.exit(1)

MEMORY_DIR = ROOT / ".dimagx"

# Import after ROOT is set
from dimagx.config import load_config
from dimagx.db import get_db, get_conn, esc, upsert_feature, link_project_feature
from dimagx.graph import init_schema

# ── MCP App ────────────────────────────────────────────────────────────────────

mcp = FastMCP(
    "DimagX",
    instructions=(
        "DimagX is the memory brain for this project. "
        "Always call get_context() at the start of a session to orient yourself. "
        "Call log_prompt() after completing any significant task. "
        "Use query_memory() before asking the user to explain something — it may already be known."
    ),
)


def get_project_id(config: dict) -> str:
    return hashlib.md5(config["project"].encode()).hexdigest()[:12]


# ── Tool: get_context ──────────────────────────────────────────────────────────

@mcp.tool()
def get_context() -> str:
    """
    Get full project context. Call this at the start of every session.
    Returns project summary, active features, recent commits, and PRDs.
    """
    try:
        config = load_config(ROOT)
        db = get_db(MEMORY_DIR)
        conn = get_conn(db)

        project    = config.get("project", "Unknown")
        description = config.get("description", "")
        stack      = ", ".join(config.get("stack", []))

        # Active features
        r = conn.execute(
            "MATCH (f:Feature) WHERE f.status = 'in_progress' "
            "RETURN f.title, f.updated ORDER BY f.updated DESC LIMIT 5"
        )
        active_features = []
        while r.has_next():
            row = r.get_next()
            active_features.append(f"  • {row[0]} (updated: {(row[1] or '')[:10]})")

        # Recent commits
        r = conn.execute(
            "MATCH (c:Commit) RETURN c.hash, c.summary, c.date ORDER BY c.date DESC LIMIT 5"
        )
        recent_commits = []
        while r.has_next():
            row = r.get_next()
            recent_commits.append(f"  [{row[0]}] {row[2][:10] if row[2] else ''} — {row[1][:80] if row[1] else ''}")

        # PRDs
        r = conn.execute("MATCH (p:PRD) RETURN p.title, p.summary LIMIT 5")
        prds = []
        while r.has_next():
            row = r.get_next()
            prds.append(f"  • {row[0]}: {(row[1] or '')[:100]}")

        # Recent prompts
        r = conn.execute(
            "MATCH (p:Prompt) RETURN p.text, p.outcome, p.created ORDER BY p.created DESC LIMIT 3"
        )
        recent_prompts = []
        while r.has_next():
            row = r.get_next()
            recent_prompts.append(f"  [{row[2][:10] if row[2] else ''}] {row[0][:80]} → {row[1] or 'unknown'}")

        # File count
        r = conn.execute("MATCH (f:File) RETURN count(f) AS c")
        file_count = r.get_next()[0]

        # Decision count
        r = conn.execute("MATCH (d:Decision) RETURN count(d) AS c")
        decision_count = r.get_next()[0]

        conn.close()

        lines = [
            f"# {project}",
            f"**Description:** {description}",
            f"**Stack:** {stack}",
            f"**Files indexed:** {file_count}",
            f"**Architectural decisions:** {decision_count}",
            "",
        ]

        if active_features:
            lines += ["## Active Features (in progress)", *active_features, ""]
        else:
            lines += ["## Active Features", "  None. Use `dimagx feature start` to tag work.", ""]

        if recent_commits:
            lines += ["## Recent Git Commits", *recent_commits, ""]

        if prds:
            lines += ["## PRDs", *prds, ""]

        if recent_prompts:
            lines += ["## Recent Agent Prompts", *recent_prompts, ""]

        lines += [
            "---",
            "You are now oriented. Proceed with the user's request.",
            "Call query_memory(question) before asking the user to explain existing code or decisions.",
        ]

        return "\n".join(lines)

    except Exception as e:
        return f"DimagX error: {e}"


# ── Tool: log_prompt ───────────────────────────────────────────────────────────

@mcp.tool()
def log_prompt(
    text: str,
    response_summary: str,
    outcome: str = "implemented",
    feature_title: Optional[str] = None,
) -> str:
    """
    Log an agent prompt and its outcome into project memory.

    Args:
        text: The prompt or task description
        response_summary: Brief summary of what was done / decided
        outcome: One of: implemented, decided, rejected, pending
        feature_title: Optional — which feature this relates to
    """
    try:
        config = load_config(ROOT)
        db = get_db(MEMORY_DIR)
        conn = get_conn(db)
        init_schema(conn)

        prompt_id = f"prompt_{hashlib.md5((text + datetime.now().isoformat()).encode()).hexdigest()[:10]}"
        now = datetime.now().isoformat()

        conn.execute(f"""
            MERGE (p:Prompt {{id: '{esc(prompt_id)}'}})
            ON CREATE SET
                p.text             = '{esc(text[:500])}',
                p.response_summary = '{esc(response_summary[:500])}',
                p.outcome          = '{esc(outcome)}',
                p.created          = '{esc(now)}'
        """)

        # Link to feature if provided
        if feature_title:
            feature_id = f"feat_{hashlib.md5(feature_title.encode()).hexdigest()[:12]}"
            try:
                conn.execute(f"""
                    MATCH (pr:Prompt {{id: '{esc(prompt_id)}'}}), (f:Feature {{id: '{esc(feature_id)}'}})
                    MERGE (pr)-[:LOGGED_FOR]->(f)
                """)
            except Exception:
                pass

        conn.close()
        return f"✔ Prompt logged: {prompt_id}"

    except Exception as e:
        return f"DimagX error logging prompt: {e}"


# ── Tool: query_memory ─────────────────────────────────────────────────────────

@mcp.tool()
def query_memory(question: str) -> str:
    """
    Search project memory for relevant context.
    Use this before asking the user to explain something — it may already be known.

    Args:
        question: Natural language question about the project
    """
    try:
        config = load_config(ROOT)
        db = get_db(MEMORY_DIR)
        conn = get_conn(db)

        keywords = [w.lower() for w in question.split() if len(w) > 3]
        results = []

        # Search features
        r = conn.execute("MATCH (f:Feature) RETURN f.title, f.description, f.status")
        while r.has_next():
            row = r.get_next()
            title = (row[0] or "").lower()
            desc  = (row[1] or "").lower()
            if any(k in title or k in desc for k in keywords):
                results.append(f"[Feature] {row[0]} — {row[2]} — {row[1][:100] if row[1] else ''}")

        # Search prompts
        r = conn.execute("MATCH (p:Prompt) RETURN p.text, p.response_summary, p.outcome, p.created ORDER BY p.created DESC")
        while r.has_next():
            row = r.get_next()
            text    = (row[0] or "").lower()
            summary = (row[1] or "").lower()
            if any(k in text or k in summary for k in keywords):
                results.append(
                    f"[Prompt/{row[2]}] {row[0][:80]} → {row[1][:100] if row[1] else ''}"
                )

        # Search PRDs
        r = conn.execute("MATCH (p:PRD) RETURN p.title, p.summary")
        while r.has_next():
            row = r.get_next()
            title   = (row[0] or "").lower()
            summary = (row[1] or "").lower()
            if any(k in title or k in summary for k in keywords):
                results.append(f"[PRD] {row[0]}: {row[1][:120] if row[1] else ''}")

        # Search decisions
        r = conn.execute("MATCH (d:Decision) RETURN d.title, d.choice, d.reason")
        while r.has_next():
            row = r.get_next()
            title  = (row[0] or "").lower()
            choice = (row[1] or "").lower()
            reason = (row[2] or "").lower()
            if any(k in title or k in choice or k in reason for k in keywords):
                results.append(f"[Decision] {row[0]} → chose: {row[1]} — {row[2][:100] if row[2] else ''}")

        # Search files
        r = conn.execute("MATCH (f:File) RETURN f.path, f.purpose, f.language")
        while r.has_next():
            row = r.get_next()
            path    = (row[0] or "").lower()
            purpose = (row[1] or "").lower()
            if any(k in path or k in purpose for k in keywords):
                results.append(f"[File/{row[2]}] {row[0]} — {row[1][:80] if row[1] else ''}")

        conn.close()

        if not results:
            return f"No memory found for: '{question}'\nThis may be new territory — proceed and consider logging what you learn."

        out = [f"## Memory results for: '{question}'", ""]
        for r in results[:10]:   # cap at 10 results
            out.append(f"• {r}")
        return "\n".join(out)

    except Exception as e:
        return f"DimagX query error: {e}"


# ── Tool: add_decision ─────────────────────────────────────────────────────────

@mcp.tool()
def add_decision(
    title: str,
    context: str,
    choice: str,
    reason: str,
) -> str:
    """
    Log an architectural decision (ADR) into project memory.

    Args:
        title:   Short name for the decision (e.g. "Auth strategy")
        context: What problem / situation triggered this decision
        choice:  What was decided
        reason:  Why this was chosen over alternatives
    """
    try:
        config = load_config(ROOT)
        db = get_db(MEMORY_DIR)
        conn = get_conn(db)
        init_schema(conn)

        decision_id = f"adr_{hashlib.md5(title.encode()).hexdigest()[:10]}"
        project_id  = get_project_id(config)
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
        return f"✔ Decision logged: {decision_id}\n  {title} → {choice}"

    except Exception as e:
        return f"DimagX error logging decision: {e}"


# ── Tool: get_features ─────────────────────────────────────────────────────────

@mcp.tool()
def get_features(status_filter: Optional[str] = None) -> str:
    """
    List all features in the project.

    Args:
        status_filter: Optional — filter by 'in_progress', 'done', or 'planned'
    """
    try:
        db = get_db(MEMORY_DIR)
        conn = get_conn(db)

        if status_filter:
            r = conn.execute(
                f"MATCH (f:Feature) WHERE f.status = '{esc(status_filter)}' "
                "RETURN f.title, f.status, f.description, f.updated ORDER BY f.updated DESC"
            )
        else:
            r = conn.execute(
                "MATCH (f:Feature) RETURN f.title, f.status, f.description, f.updated ORDER BY f.updated DESC"
            )

        rows = []
        while r.has_next():
            rows.append(r.get_next())
        conn.close()

        if not rows:
            return "No features found. Use `dimagx feature start \"name\"` to add one."

        lines = ["## Features", ""]
        for title, status, desc, updated in rows:
            lines.append(f"• [{status}] {title}")
            if desc:
                lines.append(f"  {desc[:100]}")
        return "\n".join(lines)

    except Exception as e:
        return f"DimagX error: {e}"


# ── Tool: get_files ────────────────────────────────────────────────────────────

@mcp.tool()
def get_files(feature_title: Optional[str] = None, language: Optional[str] = None) -> str:
    """
    List indexed files in the project.

    Args:
        feature_title: Optional — only files linked to this feature
        language:      Optional — filter by language (py, ts, sql, etc.)
    """
    try:
        db = get_db(MEMORY_DIR)
        conn = get_conn(db)

        if feature_title:
            feature_id = f"feat_{hashlib.md5(feature_title.encode()).hexdigest()[:12]}"
            r = conn.execute(f"""
                MATCH (feat:Feature {{id: '{esc(feature_id)}' }})<-[:LOGGED_FOR]-(p:Prompt)-[:PRODUCED]->(f:File)
                RETURN f.path, f.language, f.purpose
            """)
        elif language:
            r = conn.execute(
                f"MATCH (f:File) WHERE f.language = '{esc(language)}' "
                "RETURN f.path, f.language, f.purpose ORDER BY f.path"
            )
        else:
            r = conn.execute(
                "MATCH (f:File) RETURN f.path, f.language, f.purpose ORDER BY f.path LIMIT 50"
            )

        rows = []
        while r.has_next():
            rows.append(r.get_next())
        conn.close()

        if not rows:
            return "No files found matching the filter."

        lines = ["## Files", ""]
        for path, lang, purpose in rows:
            purpose_str = f" — {purpose}" if purpose else ""
            lines.append(f"• [{lang}] {path}{purpose_str}")
        return "\n".join(lines)

    except Exception as e:
        return f"DimagX error: {e}"


# ── Entry ──────────────────────────────────────────────────────────────────────

def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
