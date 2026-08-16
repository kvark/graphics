#!/usr/bin/env python3
"""Validate the node graph.

    python3 tools/check.py

Prints every problem found and exits non-zero if there were any. This tool
writes nothing: no file in the repository is generated, so there is nothing
here to keep in sync. The site build runs the same validation before it
publishes.
"""

import sys

from graph import Problem, load_all


def main():
    try:
        nodes, clusters = load_all()
    except Problem as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    edges = sum(len(n.get("edges") or []) for n in nodes.values())
    print(f"ok: {len(nodes)} nodes, {edges} edges, {len(clusters)} clusters")
    return 0


if __name__ == "__main__":
    sys.exit(main())
