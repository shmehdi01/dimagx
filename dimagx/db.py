"""
DimagX DB Helpers
Kuzu v0.11 compatible query helpers.
Kuzu 0.11 has limited multi-param support in SET — use f-string queries with sanitization.
"""

import kuzu
from pathlib import Path


def get_db(memory_dir: Path) -> kuzu.Database:
    return kuzu.Database(str(memory_dir / "graph.db"))


def get_conn(db: kuzu.Database) -> kuzu.Connection:
    return kuzu.Connection(db)


def esc(s: str) -> str:
    """Escape single quotes for Kuzu string literals."""
    return str(s).replace("'", "''")


def count_nodes(conn: kuzu.Connection, label: str) -> int:
    try:
        r = conn.execute(f"MATCH (n:{label}) RETURN count(n) AS c")
        return r.get_next()[0]
    except Exception:
        return 0


# ── Upsert helpers ─────────────────────────────────────────────────────────────

def upsert_project(conn, id, name, description, stack, status, created):
    conn.execute(f"""
        MERGE (p:Project {{id: '{esc(id)}'}})
        ON CREATE SET
            p.name        = '{esc(name)}',
            p.description = '{esc(description)}',
            p.stack       = '{esc(stack)}',
            p.status      = '{esc(status)}',
            p.created     = '{esc(created)}'
    """)


def upsert_file(conn, id, path, language, purpose, updated, embedding=None):
    emb_set = f", f.embedding = {embedding}" if embedding else ""
    conn.execute(f"""
        MERGE (f:File {{id: '{esc(id)}'}})
        ON CREATE SET
            f.path     = '{esc(path)}',
            f.language = '{esc(language)}',
            f.purpose  = '{esc(purpose)}',
            f.updated  = '{esc(updated)}'
            {emb_set}
        ON MATCH SET
            f.updated  = '{esc(updated)}'
            {emb_set}
    """)


def upsert_commit(conn, id, hash_, message, summary, author, date):
    conn.execute(f"""
        MERGE (c:Commit {{id: '{esc(id)}'}})
        ON CREATE SET
            c.hash    = '{esc(hash_)}',
            c.message = '{esc(message)}',
            c.summary = '{esc(summary)}',
            c.author  = '{esc(author)}',
            c.date    = '{esc(date)}'
    """)


def upsert_feature(conn, id, title, description, status, created, updated, embedding=None):
    emb_set = f", f.embedding = {embedding}" if embedding else ""
    conn.execute(f"""
        MERGE (f:Feature {{id: '{esc(id)}'}})
        ON CREATE SET
            f.title       = '{esc(title)}',
            f.description = '{esc(description)}',
            f.status      = '{esc(status)}',
            f.created     = '{esc(created)}',
            f.updated     = '{esc(updated)}'
            {emb_set}
        ON MATCH SET
            f.status  = '{esc(status)}',
            f.updated = '{esc(updated)}'
            {emb_set}
    """)


def link_project_file(conn, project_id, file_id):
    try:
        conn.execute(f"""
            MATCH (p:Project {{id: '{esc(project_id)}'}}), (f:File {{id: '{esc(file_id)}'}})
            MERGE (p)-[:HAS_FILE]->(f)
        """)
    except Exception:
        pass


def link_project_commit(conn, project_id, commit_id):
    try:
        conn.execute(f"""
            MATCH (p:Project {{id: '{esc(project_id)}'}}), (c:Commit {{id: '{esc(commit_id)}'}})
            MERGE (p)-[:HAS_COMMIT]->(c)
        """)
    except Exception:
        pass


def link_project_feature(conn, project_id, feature_id):
    try:
        conn.execute(f"""
            MATCH (p:Project {{id: '{esc(project_id)}'}}), (f:Feature {{id: '{esc(feature_id)}'}})
            MERGE (p)-[:HAS_FEATURE]->(f)
        """)
    except Exception:
        pass


def upsert_symbol(conn, id, name, kind, line):
    conn.execute(f"""
        MERGE (s:Symbol {{id: '{esc(id)}'}})
        ON CREATE SET
            s.name = '{esc(name)}',
            s.kind = '{esc(kind)}',
            s.line = {int(line)}
    """)


def link_file_symbol(conn, file_id, symbol_id):
    try:
        conn.execute(f"""
            MATCH (f:File {{id: '{esc(file_id)}'}}), (s:Symbol {{id: '{esc(symbol_id)}'}})
            MERGE (f)-[:HAS_SYMBOL]->(s)
        """)
    except Exception:
        pass


def update_feature(conn, id, title=None, description=None, status=None, updated=None, embedding=None):
    sets = []
    if title is not None:
        sets.append(f"f.title = '{esc(title)}'")
    if description is not None:
        sets.append(f"f.description = '{esc(description)}'")
    if status is not None:
        sets.append(f"f.status = '{esc(status)}'")
    if updated is not None:
        sets.append(f"f.updated = '{esc(updated)}'")
    if embedding is not None:
        sets.append(f"f.embedding = {embedding}")

    if not sets:
        return

    query = f"MATCH (f:Feature {{id: '{esc(id)}'}}) SET " + ", ".join(sets)
    conn.execute(query)


def upsert_prompt(conn, id, text, summary, outcome, created, embedding=None):
    emb_set = f", p.embedding = {embedding}" if embedding else ""
    conn.execute(f"""
        MERGE (p:Prompt {{id: '{esc(id)}'}})
        ON CREATE SET
            p.text             = '{esc(text)}',
            p.response_summary = '{esc(summary)}',
            p.outcome          = '{esc(outcome)}',
            p.created          = '{esc(created)}'
            {emb_set}
        ON MATCH SET
            p.outcome = '{esc(outcome)}'
            {emb_set}
    """)


def upsert_prd(conn, id, title, summary, source, version, created, embedding=None):
    emb_set = f", p.embedding = {embedding}" if embedding else ""
    conn.execute(f"""
        MERGE (p:PRD {{id: '{esc(id)}'}})
        ON CREATE SET
            p.title   = '{esc(title)}',
            p.summary = '{esc(summary)}',
            p.source  = '{esc(source)}',
            p.version = '{esc(version)}',
            p.created = '{esc(created)}'
            {emb_set}
    """)


def upsert_decision(conn, id, title, context, choice, reason, created, embedding=None):
    emb_set = f", d.embedding = {embedding}" if embedding else ""
    conn.execute(f"""
        MERGE (d:Decision {{id: '{esc(id)}'}})
        ON CREATE SET
            d.title   = '{esc(title)}',
            d.context = '{esc(context)}',
            d.choice  = '{esc(choice)}',
            d.reason  = '{esc(reason)}',
            d.created = '{esc(created)}'
            {emb_set}
    """)


def upsert_entity(conn, id, name, kind, framework, line):
    conn.execute(f"""
        MERGE (e:Entity {{id: '{esc(id)}'}})
        ON CREATE SET
            e.name      = '{esc(name)}',
            e.kind      = '{esc(kind)}',
            e.framework = '{esc(framework)}',
            e.line      = {int(line)}
    """)


def link_file_entity(conn, file_id, entity_id):
    try:
        conn.execute(f"""
            MATCH (f:File {{id: '{esc(file_id)}'}}), (e:Entity {{id: '{esc(entity_id)}'}})
            MERGE (f)-[:HAS_ENTITY]->(e)
        """)
    except Exception:
        pass


def upsert_bug(conn, id, title, description, status, severity, created, updated, embedding=None):
    emb_set = f", b.embedding = {embedding}" if embedding else ""
    conn.execute(f"""
        MERGE (b:Bug {{id: '{esc(id)}'}})
        ON CREATE SET
            b.title       = '{esc(title)}',
            b.description = '{esc(description)}',
            b.status      = '{esc(status)}',
            b.severity    = '{esc(severity)}',
            b.created     = '{esc(created)}',
            b.updated     = '{esc(updated)}'
            {emb_set}
        ON MATCH SET
            b.status  = '{esc(status)}',
            b.updated = '{esc(updated)}'
            {emb_set}
    """)


def update_bug(conn, id, status=None, updated=None):
    sets = []
    if status is not None:
        sets.append(f"b.status = '{esc(status)}'")
    if updated is not None:
        sets.append(f"b.updated = '{esc(updated)}'")
    
    if not sets:
        return
        
    conn.execute(f"MATCH (b:Bug {{id: '{esc(id)}'}}) SET " + ", ".join(sets))


def link_project_bug(conn, project_id, bug_id):
    try:
        conn.execute(f"""
            MATCH (p:Project {{id: '{esc(project_id)}'}}), (b:Bug {{id: '{esc(bug_id)}'}})
            MERGE (p)-[:HAS_BUG]->(b)
        """)
    except Exception:
        pass


def link_bug_file(conn, bug_id, file_path):
    try:
        conn.execute(f"""
            MATCH (b:Bug {{id: '{esc(bug_id)}'}}), (f:File {{path: '{esc(file_path)}'}})
            MERGE (b)-[:FIXES]->(f)
        """)
    except Exception:
        pass
