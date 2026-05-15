"""
DimagX Watcher Daemon
Entry point for background watcher process.
Called by: dimagx watch --background
"""

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", help="Project root path")
    parser.add_argument("--api-key", default=None)
    args = parser.parse_args()

    root = Path(args.root)
    from dimagx.watcher import run_watcher
    run_watcher(root, api_key=args.api_key)


if __name__ == "__main__":
    main()
