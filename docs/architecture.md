# DimagX Architecture 🧠

DimagX builds a **persistent memory graph** of your project. This document explains the underlying data model, the graph schema, and how data flows through the system.

## The Memory Graph

At its core, DimagX uses [Kuzu](https://kuzudb.com/), an embedded graph database. Unlike a traditional SQL database or a vector-only store, a graph allows DimagX to maintain **relationships** between disparate types of information.

### Node Types

DimagX indexes your project into 10 distinct node types:

| Node Type | Description |
| :--- | :--- |
| **Project** | The root node representing your application identity and stack. |
| **File** | Source code files, including their purpose and language. |
| **Symbol** | Classes and functions extracted via Tree-sitter. |
| **Entity** | Framework-specific concepts (e.g., Flutter Cubits, React Components, FastAPI Routes). |
| **Feature** | High-level functional units you are currently building. |
| **PRD** | Product Requirements Documents, summarized by AI. |
| **Decision** | Architectural Decision Records (ADRs) explaining *why* something was built. |
| **Prompt** | Captured logs of agent interactions and outcomes. |
| **Commit** | Git history, linking changes to files. |
| **Bug** | Tracked software issues and their resolution status. |

### Relationships (Edges)

The true power of DimagX comes from how these nodes are connected:

- `Project ──HAS_FEATURE──▶ Feature`: Shows the scope of the project.
- `PRD ──COVERS──▶ Feature`: Links requirements to implementation goals.
- `Feature ──IMPLEMENTS──▶ File`: Tracks which files belong to which feature.
- `File ──HAS_SYMBOL──▶ Symbol`: Maps code structure inside files.
- `Commit ──CHANGED──▶ File`: Connects history to source.
- `Prompt ──LOGGED_FOR──▶ Feature`: Records the "train of thought" for a specific feature.

---

## Data Flow

### 1. Ingestion (Scanning)
When you run `dimagx init`, the system:
1.  Detects the project stack (e.g., Python/FastAPI, Flutter).
2.  Scans the file system and extracts **Symbols** using Tree-sitter.
3.  Identifies **Entities** based on framework patterns.
4.  Ingests the last 100 git commits and links them to files.

### 2. Monitoring (Watching)
The `dimagx watch` command uses `watchdog` to monitor file changes. When a file is saved:
- The graph is updated with new symbols.
- If a feature is active, the change is automatically linked to that feature.

### 3. Intelligence (Embeddings)
Most nodes (File, Feature, PRD, Decision, Prompt) have an `embedding` property. 
- DimagX uses `sentence-transformers` to generate **local vector embeddings**.
- This enables **Semantic Search** through the `query_memory` tool without sending your code to external APIs.

### 4. Agent Interaction (MCP)
The MCP server acts as the bridge. When an agent calls `get_context()`, DimagX performs a graph traversal to find the most relevant "active" context (features in progress, recent decisions, related PRDs) and delivers it as a structured summary.

---

## Graph Schema Reference

The schema is defined in `dimagx/graph.py`. It uses a strictly typed schema in Kuzu to ensure data integrity and high-performance querying.
