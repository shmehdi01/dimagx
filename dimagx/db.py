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


def upsert_file(conn, id, path, language, purpose, updated):
    conn.execute(f"""
        MERGE (f:File {{id: '{esc(id)}'}})
        ON CREATE SET
            f.path     = '{esc(path)}',
            f.language = '{esc(language)}',
            f.purpose  = '{esc(purpose)}',
            f.updated  = '{esc(updated)}'
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


def upsert_feature(conn, id, title, description, status, created, updated):
    conn.execute(f"""
        MERGE (f:Feature {{id: '{esc(id)}'}})
        ON CREATE SET
            f.title       = '{esc(title)}',
            f.description = '{esc(description)}',
            f.status      = '{esc(status)}',
            f.created     = '{esc(created)}',
            f.updated     = '{esc(updated)}'
        ON MATCH SET
            f.status  = '{esc(status)}',
            f.updated = '{esc(updated)}'
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
