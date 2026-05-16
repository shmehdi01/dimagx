import os
from pathlib import Path
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import kuzu

from dimagx import config as cfg
from dimagx.db import get_db, get_conn

app = FastAPI(title="DimagX Graph UI")

# Global state to store the project root
PROJECT_ROOT: Path = Path.cwd()

def set_project_root(root: Path):
    global PROJECT_ROOT
    PROJECT_ROOT = root

@app.get("/", response_class=HTMLResponse)
async def read_index():
    static_dir = Path(__file__).parent / "static"
    index_file = static_dir / "index.html"
    if not index_file.exists():
        # Fallback for development if run from root
        index_file = Path.cwd() / "dimagx" / "static" / "index.html"
        if not index_file.exists():
            raise HTTPException(status_code=404, detail=f"Static files not found at {index_file}")
    return index_file.read_text()

@app.get("/api/graph")
async def get_graph():
    memory_dir = cfg.get_memory_dir(PROJECT_ROOT)
    if not (memory_dir / "graph.db").exists():
        return {"nodes": [], "links": []}

    db = get_db(memory_dir)
    conn = get_conn(db)
    
    nodes = []
    edges = []
    
    # Fetch all nodes
    node_labels = ["Project", "File", "Feature", "PRD", "Decision", "Commit", "Prompt", "Entity"]
    for label in node_labels:
        try:
            result = conn.execute(f"MATCH (n:{label}) RETURN n")
            while result.has_next():
                n = result.get_next()[0]
                # Ensure we have a plain dictionary for properties
                props = {}
                for k, v in n.items():
                    if isinstance(v, (str, int, float, bool)) or v is None:
                        props[k] = v
                    else:
                        props[k] = str(v)
                
                nodes.append({
                    "id": props.get("id"),
                    "label": label,
                    "properties": props
                })
        except Exception:
            continue
            
    # Fetch all relationships
    rel_types = ["HAS_FILE", "HAS_FEATURE", "HAS_PRD", "HAS_DECISION", "HAS_COMMIT", 
                 "COVERS", "IMPLEMENTS", "LOGGED_FOR", "PRODUCED", "CHANGED", "HAS_ENTITY"]
    for rel in rel_types:
        try:
            result = conn.execute(f"MATCH (a)-[r:{rel}]->(b) RETURN a.id, b.id")
            while result.has_next():
                a_id, b_id = result.get_next()
                edges.append({
                    "source": a_id,
                    "target": b_id,
                    "type": rel
                })
        except Exception:
            continue
            
    conn.close()
    return {"nodes": nodes, "links": edges}

@app.get("/api/node/{node_id}")
async def get_node_details(node_id: str):
    memory_dir = cfg.get_memory_dir(PROJECT_ROOT)
    db = get_db(memory_dir)
    conn = get_conn(db)
    
    node_labels = ["Project", "File", "Feature", "PRD", "Decision", "Commit", "Prompt", "Entity"]
    for label in node_labels:
        try:
            result = conn.execute(f"MATCH (n:{label}) WHERE n.id = '{node_id}' RETURN n")
            if result.has_next():
                n = result.get_next()[0]
                conn.close()
                return {"id": n["id"], "label": label, "properties": n}
        except Exception:
            continue
            
    conn.close()
    raise HTTPException(status_code=404, detail="Node not found")

# Try to mount static files
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=static_path), name="static")
else:
    # Fallback for dev
    dev_static = Path.cwd() / "dimagx" / "static"
    if dev_static.exists():
        app.mount("/static", StaticFiles(directory=dev_static), name="static")
