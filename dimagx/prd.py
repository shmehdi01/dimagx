"""
DimagX PRD Ingestion
Reads MD / PDF / TXT files, summarizes via Anthropic API,
stores structured PRD nodes in the graph linked to features.
"""

import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── File readers ───────────────────────────────────────────────────────────────

def read_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def read_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def read_pdf(path: Path) -> str:
    try:
        import PyPDF2
        text = []
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text.append(page.extract_text() or "")
        return "\n".join(text)
    except Exception as e:
        return f"[PDF read error: {e}]"


def read_docx(path: Path) -> str:
    try:
        import docx
        doc = docx.Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as e:
        return f"[DOCX read error: {e}]"


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in (".md", ".markdown"):
        return read_markdown(path)
    elif suffix == ".pdf":
        return read_pdf(path)
    elif suffix in (".docx",):
        return read_docx(path)
    elif suffix in (".txt", ".rst"):
        return read_txt(path)
    else:
        return path.read_text(encoding="utf-8", errors="ignore")


# ── LLM summarization ──────────────────────────────────────────────────────────

SUMMARIZE_PROMPT = """\
You are a technical analyst. Read the following PRD (Product Requirements Document) and extract:

1. **title** — short name for this PRD (max 60 chars)
2. **summary** — 2-3 sentence overview of what this PRD covers
3. **features** — list of feature names mentioned (short, 3-6 words each)
4. **decisions** — any architectural or product decisions mentioned
5. **version** — version if mentioned, else "v1"

Respond ONLY as valid JSON, no markdown fences, no preamble:
{
  "title": "...",
  "summary": "...",
  "features": ["...", "..."],
  "decisions": ["...", "..."],
  "version": "..."
}

PRD content:
"""


def summarize_prd(text: str, api_key: str) -> dict:
    import anthropic
    import json

    client = anthropic.Anthropic(api_key=api_key)

    # Truncate to ~12k chars to stay within token budget
    truncated = text[:12000]
    if len(text) > 12000:
        truncated += "\n\n[... document truncated for summarization ...]"

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        messages=[{"role": "user", "content": SUMMARIZE_PROMPT + truncated}],
    )

    raw = response.content[0].text.strip()

    # Strip fences if model added them anyway
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        return json.loads(raw)
    except Exception:
        # Fallback: return minimal structure
        return {
            "title": "PRD",
            "summary": raw[:300],
            "features": [],
            "decisions": [],
            "version": "v1",
        }


# ── Graph storage ──────────────────────────────────────────────────────────────

def store_prd(conn, project_id: str, prd_data: dict, source_file: str, version: str) -> str:
    from dimagx.db import esc, upsert_feature, link_project_feature, upsert_prd
    from dimagx.embeddings import generate_embedding

    prd_id = f"prd_{hashlib.md5((prd_data['title'] + version).encode()).hexdigest()[:10]}"
    now = datetime.now().isoformat()

    title   = prd_data.get("title", "PRD")
    summary = prd_data.get("summary", "")
    ver     = prd_data.get("version", version)

    # Generate embedding for PRD
    prd_emb = generate_embedding(f"{title} {summary}")
    upsert_prd(conn, prd_id, title, summary, source_file, ver, now, embedding=prd_emb)

    # Link PRD to project
    try:
        conn.execute(f"""
            MATCH (proj:Project {{id: '{esc(project_id)}'}}), (p:PRD {{id: '{esc(prd_id)}'}})
            MERGE (proj)-[:HAS_PRD]->(p)
        """)
    except Exception:
        pass

    # Auto-create feature nodes from PRD and link
    for feat_title in prd_data.get("features", []):
        feat_id = f"feat_{hashlib.md5(feat_title.encode()).hexdigest()[:12]}"
        feat_desc = f"Auto-created from PRD: {title}"
        
        # Generate embedding for feature
        f_emb = generate_embedding(f"{feat_title} {feat_desc}")
        upsert_feature(conn, feat_id, feat_title, feat_desc, "planned", now, now, embedding=f_emb)
        
        try:
            conn.execute(f"""
                MATCH (proj:Project {{id: '{esc(project_id)}'}}), (f:Feature {{id: '{esc(feat_id)}'}})
                MERGE (proj)-[:HAS_FEATURE]->(f)
            """)
        except Exception:
            pass
        try:
            conn.execute(f"""
                MATCH (p:PRD {{id: '{esc(prd_id)}'}}), (f:Feature {{id: '{esc(feat_id)}'}})
                MERGE (p)-[:COVERS]->(f)
            """)
        except Exception:
            pass

    return prd_id


def get_api_key(root: Path) -> Optional[str]:
    """Get Anthropic API key from env or .dimagx/config.yaml."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key

    try:
        from dimagx.config import load_config
        config = load_config(root)
        return config.get("anthropic_api_key")
    except Exception:
        return None
