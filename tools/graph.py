"""Loading, validation and diagram rendering for the node graph.

Shared by build.py (README), kg.py (queries) and site.py (GitHub Pages) so
the schema lives in exactly one place.
"""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
NODES_DIR = ROOT / "nodes"
CLUSTERS_FILE = ROOT / "clusters.yaml"

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
KNOWN_FIELDS = REQUIRED_FIELDS + ("year", "aka", "tags", "wikipedia", "refs", "edges")


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
    if not nodes:
        raise Problem("no nodes found in nodes/")
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

        # Every node has to be anchored to something outside this repo, so a
        # reader can check the claim rather than take the summary on trust.
        if not anchors(node):
            errors.append(
                f"{where}: no anchor — needs a 'wikipedia' link or a ref with a url"
            )

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


def load_all():
    """Load and validate, raising Problem with every error found."""
    clusters = load_clusters()
    nodes = load_nodes()
    errors = validate(nodes, clusters)
    if errors:
        raise Problem(
            f"{len(errors)} problem(s):\n  " + "\n  ".join(errors)
        )
    return nodes, clusters


def incoming(nodes):
    """nid -> [(source_id, edge)], in stable order."""
    result = {nid: [] for nid in nodes}
    for src, node in sorted(nodes.items()):
        for edge in node.get("edges") or []:
            if edge.get("to") in result:
                result[edge["to"]].append((src, edge))
    return result


def members_of(nodes, cluster_id):
    return sorted(nid for nid, n in nodes.items() if n.get("cluster") == cluster_id)


def mermaid_id(node_id):
    return re.sub(r"[^A-Za-z0-9]", "_", node_id)


def clean(text, limit=None):
    """Flatten to a single line safe to embed in a mermaid label."""
    text = re.sub(r"\s+", " ", str(text)).strip().replace('"', "").replace("|", "/")
    if limit and len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def diagram(nodes, members, click=None, direction="LR", click_target="_blank",
            focus=None):
    """Mermaid source for `members` plus any nodes they link to.

    Returned unfenced; callers wrap it for markdown or HTML as needed.
    `click` maps a node id to a URL, or returns None for no link.
    `focus` keeps only edges touching that node, so a neighbourhood view does
    not also draw every unrelated edge its neighbours happen to have.
    """
    members = set(members)
    lines = [f"graph {direction};"]
    edges, external = [], set()

    for nid in sorted(members):
        for edge in nodes[nid].get("edges") or []:
            to = edge.get("to")
            if to not in nodes:
                continue
            if focus and focus not in (nid, to):
                continue
            if to not in members:
                external.add(to)
            edges.append((nid, edge, to))

    for nid in sorted(members) + sorted(external):
        lines.append(f'    {mermaid_id(nid)}["{clean(nodes[nid]["title"])}"];')
        url = click(nid) if click else None
        if url:
            lines.append(f'    click {mermaid_id(nid)} "{url}" {click_target};')

    for src, edge, dst in edges:
        # Taxonomy edges carry no reason, so an unlabelled arrow says as much.
        why = edge.get("why")
        arrow = f'-->|"{clean(why, 58)}"|' if why else "-->"
        lines.append(f"    {mermaid_id(src)} {arrow} {mermaid_id(dst)};")

    if external:
        # Stroke only, no fill or text colour: those come from the mermaid theme,
        # which differs between the light and dark renderings of the same page.
        lines.append("    classDef ext stroke:#888,stroke-dasharray:5 3;")
        lines.append(
            f"    class {','.join(mermaid_id(n) for n in sorted(external))} ext;"
        )

    return "\n".join(lines)


def anchors(node):
    """Every external link for a node: primary sources first, then background."""
    urls = [r["url"] for r in node.get("refs") or [] if r.get("url")]
    if node.get("wikipedia"):
        urls.append(node["wikipedia"])
    return urls


def primary_url(node):
    """The best single link for a node: a source if it has one, else background."""
    found = anchors(node)
    return found[0] if found else None
