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
from dimagx.db import (
    get_db, get_conn, esc, 
    upsert_feature, link_project_feature, 
    upsert_bug, link_project_bug, 
    update_feature, update_bug
)
from dimagx.graph import init_schema

BUG_KEYWORDS = {"fix", "bug", "issue", "crash", "error", "broken", "failed", "regression"}
FEATURE_KEYWORDS = {"implement", "feature", "add", "new", "enhance", "build", "create", "support"}
DONE_KEYWORDS = {"done", "finished", "completed", "resolved", "fixed", "implemented"}

# ── MCP App ────────────────────────────────────────────────────────────────────

mcp = FastMCP(
    "DimagX",
    instructions=(
        "DimagX is the memory brain for this project. "
        "Always call get_context() at the start of a session to orient yourself. "
        "Do NOT analyze files from scratch. Always use get_files() or query_memory() to look up files by feature or purpose. "
        "Call log_prompt() after completing any significant task. DimagX will automatically detect if your prompt is a Bug Fix or a Feature implementation based on your description. "
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

        # Bug count
        r = conn.execute("MATCH (b:Bug) WHERE b.status = 'open' RETURN count(b) AS c")
        open_bugs = r.get_next()[0]

        conn.close()

        lines = [
            f"# {project}",
            f"**Description:** {description}",
            f"**Stack:** {stack}",
            f"**Files indexed:** {file_count}",
            f"**Architectural decisions:** {decision_count}",
            f"**Open bugs:** {open_bugs}",
            "",
        ]

        if active_features:
            lines += ["## Active Features (in progress)", *active_features, ""]
        else:
            lines += ["## Active Features", "  None. Use `dimagx feature start` to tag work.", ""]

        # Active bugs
        r = conn.execute(
            "MATCH (b:Bug) WHERE b.status = 'open' "
            "RETURN b.title, b.severity ORDER BY b.updated DESC LIMIT 5"
        )
        active_bugs = []
        while r.has_next():
            row = r.get_next()
            active_bugs.append(f"  • {row[0]} ({row[1]})")
        
        if active_bugs:
            lines += ["## Active Bugs (open)", *active_bugs, ""]

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

        from dimagx.embeddings import generate_embedding
        from dimagx.db import upsert_prompt

        prompt_id = f"prompt_{hashlib.md5((text + datetime.now().isoformat()).encode()).hexdigest()[:10]}"
        now = datetime.now().isoformat()
        
        # Generate embedding for semantic search
        emb = generate_embedding(f"{text} {response_summary}")
        upsert_prompt(conn, prompt_id, text, response_summary, outcome, now, embedding=emb)

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
        else:
            # Auto-detect Bug or Feature
            words = text.lower().split()
            is_bug = any(w in BUG_KEYWORDS for w in words)
            is_feature = any(w in FEATURE_KEYWORDS for w in words)
            is_done = any(w in DONE_KEYWORDS for w in words) or outcome == "implemented"

            project_id = get_project_id(config)
            
            if is_bug:
                # Suggest bug title from first line of text
                title = text.split('\n')[0][:60]
                bug_id = f"bug_{hashlib.md5(title.encode()).hexdigest()[:12]}"
                bug_status = "fixed" if is_done else "open"
                
                upsert_bug(
                    conn, bug_id, title, text, 
                    status=bug_status, severity="medium", 
                    created=now, updated=now, embedding=emb
                )
                link_project_bug(conn, project_id, bug_id)
                conn.execute(f"MATCH (p:Prompt {{id: '{esc(prompt_id)}'}}), (b:Bug {{id: '{esc(bug_id)}'}}) MERGE (p)-[:LOGGED_FOR]->(b)")
            
            elif is_feature:
                title = text.split('\n')[0][:60]
                feature_id = f"feat_{hashlib.md5(title.encode()).hexdigest()[:12]}"
                feat_status = "done" if is_done else "in_progress"
                
                upsert_feature(
                    conn, feature_id, title, text, 
                    status=feat_status, created=now, updated=now, embedding=emb
                )
                link_project_feature(conn, project_id, feature_id)
                conn.execute(f"MATCH (p:Prompt {{id: '{esc(prompt_id)}'}}), (f:Feature {{id: '{esc(feature_id)}'}}) MERGE (p)-[:LOGGED_FOR]->(f)")

        conn.close()
        msg = f"✔ Prompt logged: {prompt_id}"
        if not feature_title:
            if is_bug: msg += f" (Auto-detected Bug: {title})"
            elif is_feature: msg += f" (Auto-detected Feature: {title})"
        return msg

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

        from dimagx.embeddings import generate_embedding, cosine_similarity

        query_vec = generate_embedding(question)
        results = []

        # We'll pull nodes and compute similarity in memory for now
        # Kuzu supports vector search in later versions, but this is robust
        
        keywords = [w.lower() for w in question.split() if len(w) > 3]

        # 1. Search Features
        r = conn.execute("MATCH (f:Feature) RETURN f.title, f.description, f.status, f.embedding")
        while r.has_next():
            row = r.get_next()
            title, desc, status, emb = row[0], row[1], row[2], row[3]
            score = 0.0
            if emb:
                score = cosine_similarity(query_vec, emb)
            else:
                score = 0.5 if any(k in (title + (desc or "")).lower() for k in keywords) else 0.0
            
            if score > 0.3:
                results.append((score, f"[Feature] {title} — {status} — {desc[:100] if desc else ''}"))

        # 2. Search Bugs
        r = conn.execute("MATCH (b:Bug) RETURN b.title, b.description, b.status, b.severity, b.embedding")
        while r.has_next():
            row = r.get_next()
            title, desc, status, sev, emb = row[0], row[1], row[2], row[3], row[4]
            score = 0.0
            if emb:
                score = cosine_similarity(query_vec, emb)
            else:
                score = 0.5 if any(k in (title + (desc or "")).lower() for k in keywords) else 0.0
            
            if score > 0.3:
                results.append((score, f"[Bug] {title} — {status} ({sev}) — {desc[:100] if desc else ''}"))

        # 3. Search Prompts
        r = conn.execute("MATCH (p:Prompt) RETURN p.text, p.response_summary, p.outcome, p.embedding")
        while r.has_next():
            row = r.get_next()
            text, summary, outcome, emb = row[0], row[1], row[2], row[3]
            score = 0.0
            if emb:
                score = cosine_similarity(query_vec, emb)
            else:
                score = 0.5 if any(k in (text + summary).lower() for k in keywords) else 0.0
            
            if score > 0.3:
                results.append((score, f"[Prompt/{outcome}] {text[:80]} → {summary[:100] if summary else ''}"))

        # 3. Search PRDs
        r = conn.execute("MATCH (p:PRD) RETURN p.title, p.summary, p.embedding")
        while r.has_next():
            row = r.get_next()
            title, summary, emb = row[0], row[1], row[2]
            score = 0.0
            if emb:
                score = cosine_similarity(query_vec, emb)
            else:
                score = 0.5 if any(k in (title + summary).lower() for k in keywords) else 0.0
            
            if score > 0.3:
                results.append((score, f"[PRD] {title}: {summary[:120] if summary else ''}"))

        # 4. Search Decisions
        r = conn.execute("MATCH (d:Decision) RETURN d.title, d.choice, d.reason, d.embedding")
        while r.has_next():
            row = r.get_next()
            title, choice, reason, emb = row[0], row[1], row[2], row[3]
            score = 0.0
            if emb:
                score = cosine_similarity(query_vec, emb)
            else:
                score = 0.5 if any(k in (title + choice + reason).lower() for k in keywords) else 0.0
            
            if score > 0.3:
                results.append((score, f"[Decision] {title} → chose: {choice} — {reason[:100] if reason else ''}"))

        # 5. Search Files
        r = conn.execute("MATCH (f:File) RETURN f.path, f.purpose, f.language, f.embedding")
        while r.has_next():
            row = r.get_next()
            path, purpose, lang, emb = row[0], row[1], row[2], row[3]
            score = 0.0
            if emb:
                score = cosine_similarity(query_vec, emb)
            else:
                score = 0.5 if any(k in (path + purpose).lower() for k in keywords) else 0.0
            
            if score > 0.3:
                results.append((score, f"[File/{lang}] {path} — {purpose[:80] if purpose else ''}"))


        # Sort by score
        results.sort(key=lambda x: x[0], reverse=True)
        final_results = [r[1] for r in results]

        conn.close()

        if not final_results:
            return f"No memory found for: '{question}'\nThis may be new territory — proceed and consider logging what you learn."

        out = [f"## Memory results for: '{question}'", ""]
        for r in final_results[:10]:   # cap at 10 results
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

        from dimagx.embeddings import generate_embedding
        from dimagx.db import upsert_decision

        decision_id = f"adr_{hashlib.md5(title.encode()).hexdigest()[:10]}"
        project_id  = get_project_id(config)
        now = datetime.now().isoformat()
        
        # Generate embedding
        emb = generate_embedding(f"{title} {context} {choice} {reason}")
        upsert_decision(conn, decision_id, title, context, choice, reason, now, embedding=emb)

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
