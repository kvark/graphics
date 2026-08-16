#!/usr/bin/env python3
"""Validate the node graph and regenerate the generated section of the README.

    python3 tools/build.py           # validate, then rewrite README
    python3 tools/build.py --check   # validate only, fail if README is stale
"""

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
NODES_DIR = ROOT / "nodes"
README = ROOT / "README.md"
CLUSTERS_FILE = ROOT / "clusters.yaml"

BEGIN = "<!-- BEGIN GENERATED -->"
END = "<!-- END GENERATED -->"

# rel -> (reads-as, why-required)
RELATIONS = {
    "part-of": ("is a subtopic of", False),
    "specializes": ("is a specific case of", True),
    "approximates": ("is a cheaper stand-in for", True),
    "corrects": ("fixes a defect in", True),
    "extends": ("adds capability to", True),
    "requires": ("does not work without", True),
    "alternative-to": ("is a competing approach to", True),
    "validates": ("is a test for", True),
}

REQUIRED_FIELDS = ("title", "cluster", "summary")
KNOWN_FIELDS = REQUIRED_FIELDS + ("year", "aka", "tags", "refs", "edges")


class Problem(Exception):
    pass


def load_clusters():
    data = yaml.safe_load(CLUSTERS_FILE.read_text())
    return [(c["id"], c["title"], c.get("blurb", "")) for c in data]


def load_nodes():
    nodes = {}
    for path in sorted(NODES_DIR.glob("*.yaml")):
        node = yaml.safe_load(path.read_text())
        if not isinstance(node, dict):
            raise Problem(f"{path.name}: file is not a YAML mapping")
        node["id"] = path.stem
        node["_path"] = path.name
        nodes[path.stem] = node
    return nodes


def validate(nodes, clusters):
    errors = []
    cluster_ids = {c[0] for c in clusters}

    for nid, node in sorted(nodes.items()):
        where = node["_path"]

        for field in REQUIRED_FIELDS:
            if not node.get(field):
                errors.append(f"{where}: missing required field '{field}'")

        for field in node:
            if field not in KNOWN_FIELDS and not field.startswith("_") and field != "id":
                errors.append(f"{where}: unknown field '{field}'")

        cluster = node.get("cluster")
        if cluster and cluster not in cluster_ids:
            errors.append(f"{where}: cluster '{cluster}' is not in clusters.yaml")

        for ref in node.get("refs") or []:
            if not ref.get("title"):
                errors.append(f"{where}: a ref has no title")

        seen = set()
        for edge in node.get("edges") or []:
            rel, to = edge.get("rel"), edge.get("to")
            if rel not in RELATIONS:
                errors.append(
                    f"{where}: unknown relation '{rel}' "
                    f"(allowed: {', '.join(sorted(RELATIONS))})"
                )
                continue
            if not to:
                errors.append(f"{where}: edge '{rel}' has no target")
                continue
            if to == nid:
                errors.append(f"{where}: edge '{rel}' points at itself")
            elif to not in nodes:
                errors.append(f"{where}: edge '{rel}' points at unknown node '{to}'")
            if (rel, to) in seen:
                errors.append(f"{where}: duplicate edge '{rel} -> {to}'")
            seen.add((rel, to))
            if RELATIONS[rel][1] and not edge.get("why"):
                errors.append(f"{where}: edge '{rel} -> {to}' needs a 'why'")

    return errors


def mermaid_id(node_id):
    return re.sub(r"[^A-Za-z0-9]", "_", node_id)


def clean(text, limit=None):
    text = re.sub(r"\s+", " ", str(text)).strip().replace('"', "").replace("|", "/")
    if limit and len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def cluster_diagram(cluster_id, nodes):
    members = {n for n, node in nodes.items() if node.get("cluster") == cluster_id}
    if not members:
        return None

    lines = ["```mermaid", "graph LR;"]
    edges, external = [], set()

    for nid in sorted(members):
        for edge in nodes[nid].get("edges") or []:
            to = edge.get("to")
            if to not in nodes:
                continue
            if to not in members:
                external.add(to)
            edges.append((nid, edge, to))

    for nid in sorted(members):
        node = nodes[nid]
        lines.append(f'    {mermaid_id(nid)}["{clean(node["title"])}"];')
        refs = node.get("refs") or []
        if refs and refs[0].get("url"):
            lines.append(f'    click {mermaid_id(nid)} "{refs[0]["url"]}" _blank;')

    for nid in sorted(external):
        lines.append(f'    {mermaid_id(nid)}["{clean(nodes[nid]["title"])}"];')

    for src, edge, dst in edges:
        # Taxonomy edges carry no reason, so an unlabelled arrow says as much.
        why = edge.get("why")
        arrow = f'-->|"{clean(why, 58)}"|' if why else "-->"
        lines.append(f"    {mermaid_id(src)} {arrow} {mermaid_id(dst)};")

    if external:
        lines.append(
            "    classDef ext fill:#eee,stroke:#999,stroke-dasharray:4 3,color:#555;"
        )
        lines.append(
            f"    class {','.join(mermaid_id(n) for n in sorted(external))} ext;"
        )

    lines.append("```")
    return "\n".join(lines)


def render(nodes, clusters):
    edge_count = sum(len(n.get("edges") or []) for n in nodes.values())
    ref_count = sum(len(n.get("refs") or []) for n in nodes.values())

    out = [
        BEGIN,
        "<!-- Generated by tools/build.py from nodes/*.yaml. Do not edit by hand. -->",
        "",
        f"**{len(nodes)} nodes, {edge_count} typed edges, {ref_count} references "
        f"across {len(clusters)} clusters.**",
        "",
        "Dashed boxes are nodes belonging to another cluster. Click a node to open "
        "its primary reference.",
        "",
    ]

    for cid, title, blurb in clusters:
        diagram = cluster_diagram(cid, nodes)
        if not diagram:
            continue
        members = sorted(
            (n for n in nodes.values() if n.get("cluster") == cid),
            key=lambda n: (n.get("year") or 9999, n["id"]),
        )
        out += [f"### {title}", "", blurb, "", diagram, "", "<details>",
                f"<summary>{len(members)} nodes</summary>", ""]
        for node in members:
            year = f" *({node['year']})*" if node.get("year") else ""
            out.append(
                f"- [`{node['id']}`](nodes/{node['id']}.yaml) — "
                f"**{node['title']}**{year}. {clean(node['summary'])}"
            )
        out += ["", "</details>", ""]

    out.append(END)
    return "\n".join(out)


def main():
    check = "--check" in sys.argv

    try:
        clusters = load_clusters()
        nodes = load_nodes()
    except Problem as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not nodes:
        print("error: no nodes found in nodes/", file=sys.stderr)
        return 1

    errors = validate(nodes, clusters)
    if errors:
        print(f"{len(errors)} problem(s):", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    text = README.read_text()
    if BEGIN not in text or END not in text:
        print(f"error: README.md is missing {BEGIN} / {END} markers", file=sys.stderr)
        return 1

    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    updated = head + render(nodes, clusters) + tail

    if check:
        if updated != text:
            print("error: README.md is stale; run python3 tools/build.py", file=sys.stderr)
            return 1
        print(f"ok: {len(nodes)} nodes valid, README up to date")
        return 0

    README.write_text(updated)
    edge_count = sum(len(n.get("edges") or []) for n in nodes.values())
    print(f"ok: {len(nodes)} nodes, {edge_count} edges -> README.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
