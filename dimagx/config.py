"""
DimagX Config
Reads and writes .dimagx/config.yaml
"""

import yaml
from pathlib import Path
from typing import Optional

MEMORY_DIR_NAME = ".dimagx"
CONFIG_FILE = "config.yaml"


def get_memory_dir(project_root: Path) -> Path:
    return project_root / MEMORY_DIR_NAME


def get_config_path(project_root: Path) -> Path:
    return get_memory_dir(project_root) / CONFIG_FILE


def config_exists(project_root: Path) -> bool:
    return get_config_path(project_root).exists()


def load_config(project_root: Path) -> dict:
    path = get_config_path(project_root)
    if not path.exists():
        raise FileNotFoundError(f"No DimagX config found. Run `dimagx init` first.")
    with open(path) as f:
        return yaml.safe_load(f)


def save_config(project_root: Path, config: dict):
    path = get_config_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)


def default_config(name: str, description: str, stack: list) -> dict:
    return {
        "project": name,
        "description": description,
        "stack": stack,
        "status": "active",
        "prd_dir": ".dimagx/prd",
        "auto_ingest": True,
        "git_hook": True,
    }
