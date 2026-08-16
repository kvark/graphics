#!/usr/bin/env python3
"""Query the graph.

    python3 tools/kg.py show ggx
    python3 tools/kg.py path lambert diffuse-layering
    python3 tools/kg.py search fresnel
    python3 tools/kg.py stats
"""

import sys
from collections import Counter, deque

from graph import incoming, load_nodes


def adjacency(nodes):
    """Undirected adjacency, remembering which way each edge was declared."""
    adj = {nid: [] for nid in nodes}
    for nid, node in nodes.items():
        for edge in node.get("edges") or []:
            to = edge.get("to")
            if to not in nodes:
                continue
            adj[nid].append((to, edge, True))
            adj[to].append((nid, edge, False))
    return adj


def resolve(nodes, name):
    if name in nodes:
        return name
    lowered = name.lower()
    matches = [
        nid
        for nid, node in nodes.items()
        if lowered == node.get("title", "").lower()
        or lowered in [a.lower() for a in node.get("aka") or []]
    ]
    if len(matches) == 1:
        return matches[0]
    partial = [nid for nid in nodes if lowered in nid]
    if len(partial) == 1:
        return partial[0]
    if matches or partial:
        options = ", ".join(sorted(set(matches + partial))[:8])
        print(f"'{name}' is ambiguous. Did you mean: {options}", file=sys.stderr)
    else:
        print(f"no node matching '{name}'", file=sys.stderr)
    return None


def fmt(nodes, nid):
    return f"{nodes[nid]['title']} ({nid})"


def cmd_show(nodes, args):
    nid = resolve(nodes, args[0])
    if not nid:
        return 1
    node = nodes[nid]

    print(f"{node['title']}  [{nid}]")
    if node.get("year"):
        print(f"  year:    {node['year']}")
    print(f"  cluster: {node.get('cluster')}")
    if node.get("aka"):
        print(f"  aka:     {', '.join(node['aka'])}")
    print()
    print(f"  {' '.join(str(node['summary']).split())}")

    if node.get("edges"):
        print("\n  outgoing:")
        for edge in node["edges"]:
            why = f"  — {edge['why']}" if edge.get("why") else ""
            print(f"    --{edge['rel']}--> {edge['to']}{why}")

    backlinks = incoming(nodes)[nid]
    if backlinks:
        print("\n  incoming:")
        for other, edge in backlinks:
            why = f"  — {edge['why']}" if edge.get("why") else ""
            print(f"    {other} --{edge['rel']}-->{why}")

    for ref in node.get("refs") or []:
        bits = [ref["title"]]
        if ref.get("authors"):
            bits.append(str(ref["authors"]))
        if ref.get("year"):
            bits.append(str(ref["year"]))
        print(f"\n  ref: {', '.join(bits)}")
        if ref.get("url"):
            print(f"       {ref['url']}")
    return 0


def cmd_path(nodes, args):
    src, dst = resolve(nodes, args[0]), resolve(nodes, args[1])
    if not src or not dst:
        return 1
    if src == dst:
        print(fmt(nodes, src))
        return 0

    adj = adjacency(nodes)
    prev, queue = {src: None}, deque([src])
    while queue:
        cur = queue.popleft()
        if cur == dst:
            break
        for nxt, edge, forward in adj[cur]:
            if nxt not in prev:
                prev[nxt] = (cur, edge, forward)
                queue.append(nxt)

    if dst not in prev:
        print(f"no path between {src} and {dst}")
        return 1

    chain, cur = [], dst
    while prev[cur] is not None:
        parent, edge, forward = prev[cur]
        chain.append((parent, edge, forward, cur))
        cur = parent
    chain.reverse()

    print(fmt(nodes, src))
    for _, edge, forward, nxt in chain:
        arrow = f"--{edge['rel']}-->" if forward else f"<--{edge['rel']}--"
        print(f"  {arrow}")
        if edge.get("why"):
            print(f"      ({edge['why']})")
        print(f"  {fmt(nodes, nxt)}")
    print(f"\n{len(chain)} hop(s)")
    return 0


def cmd_search(nodes, args):
    term = " ".join(args).lower()
    hits = []
    for nid, node in sorted(nodes.items()):
        haystack = " ".join(
            [nid, node.get("title", ""), str(node.get("summary", ""))]
            + (node.get("aka") or [])
            + (node.get("tags") or [])
        ).lower()
        if term in haystack:
            hits.append(node)
    for node in hits:
        year = f" ({node['year']})" if node.get("year") else ""
        print(f"{node['id']:<34} {node['title']}{year}")
    print(f"\n{len(hits)} match(es)")
    return 0


def cmd_stats(nodes, args):
    clusters = Counter(n.get("cluster") for n in nodes.values())
    rels = Counter(
        e["rel"] for n in nodes.values() for e in n.get("edges") or [] if e.get("rel")
    )
    refs = sum(len(n.get("refs") or []) for n in nodes.values())
    linked = sum(
        1 for n in nodes.values() for r in n.get("refs") or [] if r.get("url")
    )

    print(f"{len(nodes)} nodes, {sum(rels.values())} edges, {refs} refs ({linked} linked)\n")
    print("by cluster:")
    for cluster, count in clusters.most_common():
        print(f"  {cluster:<20} {count:>4}")
    print("\nby relation:")
    for rel, count in rels.most_common():
        print(f"  {rel:<20} {count:>4}")

    backlinks = incoming(nodes)
    orphans = sorted(
        nid
        for nid in nodes
        if not (nodes[nid].get("edges") or []) and not backlinks[nid]
    )
    if orphans:
        print(f"\nunconnected: {', '.join(orphans)}")
    return 0


COMMANDS = {
    "show": (cmd_show, 1),
    "path": (cmd_path, 2),
    "search": (cmd_search, 1),
    "stats": (cmd_stats, 0),
}


def main():
    args = sys.argv[1:]
    if not args or args[0] not in COMMANDS:
        print(__doc__.strip())
        return 1
    handler, arity = COMMANDS[args[0]]
    if len(args) - 1 < arity:
        print(f"'{args[0]}' needs {arity} argument(s)", file=sys.stderr)
        return 1
    return handler(load_nodes(), args[1:])


if __name__ == "__main__":
    sys.exit(main())
