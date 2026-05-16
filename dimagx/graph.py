"""
DimagX Graph Schema
Kuzu embedded graph DB — nodes for files, features, prompts, PRDs, decisions
"""

import kuzu
from pathlib import Path


def get_db(memory_dir: Path) -> kuzu.Database:
    db_path = str(memory_dir / "graph.db")
    return kuzu.Database(db_path)


def get_conn(db: kuzu.Database) -> kuzu.Connection:
    return kuzu.Connection(db)


def init_schema(conn: kuzu.Connection):
    """Create all node and relationship tables if they don't exist."""

    statements = [
        # ── Node tables ──────────────────────────────────────────────────────

        # Project root node (one per project)
        """
        CREATE NODE TABLE IF NOT EXISTS Project (
            id       STRING,
            name     STRING,
            description STRING,
            stack    STRING,
            status   STRING,
            created  STRING,
            PRIMARY KEY (id)
        )
        """,

        # Source files
        """
        CREATE NODE TABLE IF NOT EXISTS File (
            id       STRING,
            path     STRING,
            purpose  STRING,
            language STRING,
            updated  STRING,
            embedding FLOAT[384],
            PRIMARY KEY (id)
        )
        """,

        # Features (manual or agent-tagged)
        """
        CREATE NODE TABLE IF NOT EXISTS Feature (
            id          STRING,
            title       STRING,
            description STRING,
            status      STRING,
            created     STRING,
            updated     STRING,
            embedding   FLOAT[384],
            PRIMARY KEY (id)
        )
        """,

        # Prompt logs (every agent prompt captured via MCP)
        """
        CREATE NODE TABLE IF NOT EXISTS Prompt (
            id              STRING,
            text            STRING,
            response_summary STRING,
            outcome         STRING,
            created         STRING,
            embedding       FLOAT[384],
            PRIMARY KEY (id)
        )
        """,

        # PRD documents
        """
        CREATE NODE TABLE IF NOT EXISTS PRD (
            id      STRING,
            title   STRING,
            summary STRING,
            source  STRING,
            version STRING,
            created STRING,
            embedding FLOAT[384],
            PRIMARY KEY (id)
        )
        """,

        # Architectural decisions (ADRs)
        """
        CREATE NODE TABLE IF NOT EXISTS Decision (
            id      STRING,
            title   STRING,
            context STRING,
            choice  STRING,
            reason  STRING,
            created STRING,
            embedding FLOAT[384],
            PRIMARY KEY (id)
        )
        """,

        # Git commits
        """
        CREATE NODE TABLE IF NOT EXISTS Commit (
            id      STRING,
            hash    STRING,
            message STRING,
            summary STRING,
            author  STRING,
            date    STRING,
            PRIMARY KEY (id)
        )
        """,
        # Symbols (classes, functions extracted via Tree-sitter)
        """
        CREATE NODE TABLE IF NOT EXISTS Symbol (
            id      STRING,
            name    STRING,
            kind    STRING,
            line    INT64,
            PRIMARY KEY (id)
        )
        """,
        # Entities (Framework-specific concepts like Cubit, Component)
        """
        CREATE NODE TABLE IF NOT EXISTS Entity (
            id         STRING,
            name       STRING,
            kind       STRING,
            framework  STRING,
            line       INT64,
            PRIMARY KEY (id)
        )
        """,

        # Bugs (tracked issues)
        """
        CREATE NODE TABLE IF NOT EXISTS Bug (
            id          STRING,
            title       STRING,
            description STRING,
            status      STRING,
            severity    STRING,
            created     STRING,
            updated     STRING,
            embedding   FLOAT[384],
            PRIMARY KEY (id)
        )
        """,

        # ── Relationship tables ───────────────────────────────────────────────

        "CREATE REL TABLE IF NOT EXISTS HAS_FILE    (FROM Project TO File)",
        "CREATE REL TABLE IF NOT EXISTS HAS_FEATURE (FROM Project TO Feature)",
        "CREATE REL TABLE IF NOT EXISTS HAS_BUG     (FROM Project TO Bug)",
        "CREATE REL TABLE IF NOT EXISTS HAS_PRD     (FROM Project TO PRD)",
        "CREATE REL TABLE IF NOT EXISTS HAS_DECISION(FROM Project TO Decision)",
        "CREATE REL TABLE IF NOT EXISTS HAS_COMMIT  (FROM Project TO Commit)",
        "CREATE REL TABLE IF NOT EXISTS HAS_SYMBOL  (FROM File TO Symbol)",
        "CREATE REL TABLE IF NOT EXISTS HAS_ENTITY  (FROM File TO Entity)",

        "CREATE REL TABLE IF NOT EXISTS COVERS      (FROM PRD TO Feature)",
        "CREATE REL TABLE IF NOT EXISTS IMPLEMENTS  (FROM Feature TO File)",
        "CREATE REL TABLE IF NOT EXISTS FIXES       (FROM Bug TO File)",
        "CREATE REL TABLE IF NOT EXISTS LOGGED_FOR  (FROM Prompt TO Feature)",
        "CREATE REL TABLE IF NOT EXISTS LOGGED_BUG  (FROM Prompt TO Bug)",
        "CREATE REL TABLE IF NOT EXISTS PRODUCED    (FROM Prompt TO File)",
        "CREATE REL TABLE IF NOT EXISTS CHANGED     (FROM Commit TO File)",
    ]

    for stmt in statements:
        conn.execute(stmt.strip())
