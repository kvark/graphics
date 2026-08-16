#!/usr/bin/env python3
"""Generate the static site published to GitHub Pages.

    python3 tools/site.py              # diagrams load mermaid from a CDN
    python3 tools/site.py --vendor     # download mermaid into the output instead
    python3 tools/site.py --out DIR

Everything is derived from nodes/*.yaml. The site is a convenience view: the
YAML files remain the canonical artifact, readable with no tooling at all.

CI publishes with --vendor so the deployed site has no external dependency.
If mermaid fails to load for any reason the diagrams degrade to their source
text, which is still readable, rather than to empty boxes.
"""

import html
import json
import shutil
import ssl
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from graph import (
    ROOT,
    RELATIONS,
    Problem,
    clean,
    diagram,
    incoming,
    load_all,
    members_of,
)

# Pinned: a floating major version can change rendering under us with no commit.
# The UMD bundle, not the ESM entry point: the latter lazy-loads sibling chunks
# (flowDiagram-*.mjs among them), so vendoring a single file only works here.
MERMAID_VERSION = "11.4.1"
MERMAID_FILE = "mermaid.min.js"
MERMAID_CDN = f"https://cdn.jsdelivr.net/npm/mermaid@{MERMAID_VERSION}/dist/{MERMAID_FILE}"
REPO = "https://github.com/kvark/graphics"

STYLE = """
:root {
  --bg: #fbfbfa; --fg: #1a1a19; --muted: #6b6b66; --line: #e2e2dd;
  --card: #ffffff; --accent: #7a4b2a; --code: #f2f2ee;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #16171a; --fg: #e6e6e3; --muted: #9a9a94; --line: #2c2e33;
    --card: #1d1f23; --accent: #d79a6a; --code: #23252a;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--fg);
  font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
}
.wrap { max-width: 62rem; margin: 0 auto; padding: 1.5rem 1.25rem 5rem; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
nav { border-bottom: 1px solid var(--line); margin-bottom: 2rem; padding-bottom: .75rem;
      font-size: .9rem; display: flex; gap: 1rem; flex-wrap: wrap; align-items: baseline; }
nav .home { font-weight: 600; }
nav .sp { flex: 1; }
h1 { font-size: 1.9rem; line-height: 1.25; margin: 0 0 .4rem; }
h2 { font-size: 1.25rem; margin: 2.5rem 0 .5rem; }
h3 { font-size: 1rem; margin: 1.75rem 0 .5rem; text-transform: uppercase;
     letter-spacing: .06em; color: var(--muted); font-weight: 600; }
.lede { color: var(--muted); margin: 0 0 1.5rem; }
.meta { color: var(--muted); font-size: .875rem; margin: 0 0 1.25rem; }
.summary { font-size: 1.05rem; margin: 0 0 1.5rem; }
code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .9em;
       background: var(--code); padding: .1em .35em; border-radius: 3px; }
.cards { display: grid; gap: .75rem; grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr)); }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 8px;
        padding: .85rem 1rem; }
.card h4 { margin: 0 0 .25rem; font-size: 1rem; }
.card p { margin: 0; color: var(--muted); font-size: .85rem; }
.edges { list-style: none; padding: 0; margin: 0; }
.edges li { padding: .55rem 0; border-top: 1px solid var(--line); }
.edges li:first-child { border-top: 0; }
.rel { display: inline-block; font-size: .72rem; text-transform: uppercase;
       letter-spacing: .07em; padding: .12em .5em; border-radius: 3px;
       background: var(--code); color: var(--muted); margin-right: .5rem;
       font-family: ui-monospace, monospace; }
.why { color: var(--muted); display: block; margin-top: .15rem; font-size: .92rem; }
.diagram { position: relative; background: var(--card); border: 1px solid var(--line);
           border-radius: 8px; padding: 1rem; margin: 1rem 0 2rem; overflow: auto; }
/* Break out of the text column: a 29-node graph needs the whole window. */
.diagram.wide { width: min(97vw, 1700px); margin-left: calc(50% - min(48.5vw, 850px)); }
/* Only once pan/zoom is live does the box become a fixed viewport. Without JS
   it stays auto-height and scrollable, so nothing is ever clipped away. */
.diagram.pz { overflow: hidden; height: 62vh; min-height: 24rem; cursor: grab;
              user-select: none; -webkit-user-select: none;
              touch-action: none; }
.diagram.wide.pz { height: 80vh; }
.diagram.pz.grabbing { cursor: grabbing; }
.diagram.pz svg { width: 100%; height: 100%; max-width: none; display: block; }
.diagram:fullscreen { height: 100vh; width: 100vw; margin: 0; border-radius: 0; }
.tools { position: absolute; top: .5rem; right: .5rem; z-index: 2; display: none;
         gap: .25rem; }
.diagram.pz .tools { display: flex; }
.tools button { font: 600 .8rem/1 ui-monospace, monospace; color: var(--muted);
                background: var(--bg); border: 1px solid var(--line);
                border-radius: 5px; padding: .4rem .55rem; cursor: pointer; }
.tools button:hover { color: var(--fg); border-color: var(--muted); }
/* Until mermaid replaces it, this is the diagram source. Keep it legible:
   if the library never loads, the page degrades to readable text. */
pre.mermaid { margin: 0; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
              font-size: .78rem; line-height: 1.5; color: var(--muted);
              white-space: pre; }
pre.mermaid[data-processed] { color: inherit; }
.refs { list-style: none; padding: 0; }
.refs li { padding: .4rem 0; color: var(--muted); font-size: .92rem; }
.refs .t { color: var(--fg); }
#q { width: 100%; padding: .6rem .8rem; font-size: 1rem; border-radius: 6px;
     border: 1px solid var(--line); background: var(--card); color: var(--fg); }
#results { list-style: none; padding: 0; margin: .75rem 0 0; }
#results li { padding: .3rem 0; }
#results .c { color: var(--muted); font-size: .85rem; }
.stat { display: flex; gap: 2rem; flex-wrap: wrap; margin: 0 0 2rem; }
.stat b { display: block; font-size: 1.5rem; }
.stat span { color: var(--muted); font-size: .8rem; text-transform: uppercase;
             letter-spacing: .06em; }
footer { margin-top: 4rem; padding-top: 1rem; border-top: 1px solid var(--line);
         color: var(--muted); font-size: .85rem; }
"""


PANZOOM = """
(function () {
  function setup(box) {
    var svg = box.querySelector('svg');
    if (!svg) return;
    var raw = (svg.getAttribute('viewBox') || '').split(/[\\s,]+/).map(Number);
    if (raw.length !== 4 || !raw[2]) return;
    var home = raw.slice(), vb = raw.slice();

    svg.removeAttribute('width');
    svg.removeAttribute('height');
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    box.classList.add('pz');

    // Match the box to the graph's own aspect rather than a fixed height:
    // these graphs are wide and short, and a tall box just letterboxes them.
    function fit() {
      if (document.fullscreenElement === box) { box.style.height = '100vh'; return; }
      var inner = box.clientWidth - 32;
      var ideal = inner * home[3] / home[2] + 32;
      var cap = window.innerHeight * 0.85;
      box.style.height = Math.round(Math.max(320, Math.min(ideal, cap))) + 'px';
    }
    fit();
    window.addEventListener('resize', fit);
    document.addEventListener('fullscreenchange', fit);

    function apply() { svg.setAttribute('viewBox', vb.join(' ')); }
    function zoom(f, cx, cy) {
      var w = vb[2] * f;
      if (w < home[2] / 50 || w > home[2] * 15) return;
      vb[0] = cx - (cx - vb[0]) * f;
      vb[1] = cy - (cy - vb[1]) * f;
      vb[2] = w; vb[3] = vb[3] * f;
      apply();
    }
    function at(e) {
      var r = svg.getBoundingClientRect();
      return [vb[0] + (e.clientX - r.left) / r.width * vb[2],
              vb[1] + (e.clientY - r.top) / r.height * vb[3]];
    }

    box.addEventListener('wheel', function (e) {
      e.preventDefault();
      var p = at(e);
      zoom(e.deltaY > 0 ? 1.15 : 1 / 1.15, p[0], p[1]);
    }, { passive: false });

    var drag = null, moved = 0;
    svg.addEventListener('pointerdown', function (e) {
      if (e.button !== 0) return;
      drag = { x: e.clientX, y: e.clientY };
      moved = 0;
      box.classList.add('grabbing');
    });
    // Tracked on window, not via setPointerCapture: capturing the pointer
    // retargets the following click to the svg, which would stop mermaid's
    // per-node click handlers from ever firing.
    window.addEventListener('pointermove', function (e) {
      if (!drag) return;
      var r = svg.getBoundingClientRect();
      moved += Math.abs(e.clientX - drag.x) + Math.abs(e.clientY - drag.y);
      vb[0] -= (e.clientX - drag.x) * vb[2] / r.width;
      vb[1] -= (e.clientY - drag.y) * vb[3] / r.height;
      drag.x = e.clientX; drag.y = e.clientY;
      apply();
    });
    function release() { drag = null; box.classList.remove('grabbing'); }
    window.addEventListener('pointerup', release);
    window.addEventListener('pointercancel', release);
    // A drag that happens to end on a node must not also navigate to it.
    svg.addEventListener('click', function (e) {
      if (moved > 6) { e.stopPropagation(); e.preventDefault(); }
      moved = 0;
    }, true);

    box.querySelectorAll('[data-act]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var act = btn.getAttribute('data-act');
        var cx = vb[0] + vb[2] / 2, cy = vb[1] + vb[3] / 2;
        if (act === 'in') zoom(1 / 1.4, cx, cy);
        else if (act === 'out') zoom(1.4, cx, cy);
        else if (act === 'reset') { vb = home.slice(); apply(); }
        else if (document.fullscreenElement) document.exitFullscreen();
        else if (box.requestFullscreen) box.requestFullscreen();
      });
    });
  }
  window.__diagrams = function () {
    document.querySelectorAll('.diagram').forEach(setup);
  };
})();
"""


def esc(text):
    return html.escape(str(text), quote=True)


def page(title, body, depth, mermaid_src, script=""):
    up = "../" * depth
    # Page scripts are emitted before, and separately from, mermaid: a failure
    # to load the library must not take search down with it.
    extra = f"<script>{script}</script>" if script else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<link rel="stylesheet" href="{up}style.css">
</head>
<body>
<div class="wrap">
<nav>
  <a class="home" href="{up}index.html">graphics</a>
  <span class="sp"></span>
  <a href="{REPO}">source</a>
</nav>
{body}
<footer>
Generated from <code>nodes/*.yaml</code> by <code>tools/site.py</code>.
The YAML files are the canonical form — this site is a view of them.
</footer>
</div>
{extra}
<script>{PANZOOM}</script>
<script src="{mermaid_src}"></script>
<script>
if (window.mermaid) {{
  mermaid.initialize({{
    startOnLoad: false,
    theme: matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'neutral',
    securityLevel: 'loose',
    flowchart: {{ curve: 'basis', useMaxWidth: false }}
  }});
  // Explicit run rather than startOnLoad: pan/zoom needs the rendered svg,
  // and this gives a promise to hang that on.
  mermaid.run().then(window.__diagrams).catch(function (e) {{ console.error(e); }});
}}
</script>
</body>
</html>
"""


def fig(source, wide=False):
    tools = (
        '<div class="tools">'
        '<button data-act="out" title="Zoom out">&minus;</button>'
        '<button data-act="in" title="Zoom in">+</button>'
        '<button data-act="reset" title="Reset view">reset</button>'
        '<button data-act="full" title="Fullscreen">&#9974;</button>'
        "</div>"
    )
    cls = "diagram wide" if wide else "diagram"
    return (f'<div class="{cls}">{tools}'
            f'<pre class="mermaid">{esc(source)}</pre></div>')


def node_link(nid, nodes, depth):
    up = "../" * depth
    return f'<a href="{up}n/{nid}.html">{esc(nodes[nid]["title"])}</a>'


def render_refs(node):
    refs = node.get("refs") or []
    wiki = node.get("wikipedia")
    if not refs and not wiki:
        return ""
    items = []
    for ref in refs:
        bits = [f'<span class="t">{esc(ref["title"])}</span>']
        if ref.get("authors"):
            bits.append(esc(ref["authors"]))
        if ref.get("year"):
            bits.append(esc(ref["year"]))
        line = " — ".join(bits)
        if ref.get("url"):
            line += f' · <a href="{esc(ref["url"])}">link</a>'
        items.append(f"<li>{line}</li>")
    if wiki:
        article = urllib.parse.unquote(wiki.rsplit("/", 1)[-1]).replace("_", " ")
        items.append(
            f'<li>Background — <a href="{esc(wiki)}">{esc(article)}</a> on Wikipedia</li>'
        )
    return f'<h3>References</h3><ul class="refs">{"".join(items)}</ul>'


def edge_items(rows):
    return "".join(
        f'<li><span class="rel">{esc(rel)}</span>{text}'
        + (f'<span class="why">{esc(why)}</span>' if why else "")
        + "</li>"
        for rel, text, why in rows
    )


def render_node(nid, nodes, clusters, backlinks, mermaid_src):
    node = nodes[nid]
    titles = {c[0]: c[1] for c in clusters}

    meta = [f'<a href="../c/{node["cluster"]}.html">'
            f'{esc(titles.get(node["cluster"], node["cluster"]))}</a>']
    if node.get("year"):
        meta.append(esc(node["year"]))
    if node.get("aka"):
        meta.append("also: " + esc(", ".join(node["aka"])))

    out = [
        f"<h1>{esc(node['title'])}</h1>",
        f'<p class="meta">{" · ".join(meta)} · '
        f'<a href="{REPO}/blob/main/nodes/{nid}.yaml"><code>{nid}.yaml</code></a></p>',
        f'<p class="summary">{esc(clean(node["summary"]))}</p>',
    ]

    neighbours = {nid}
    neighbours.update(e["to"] for e in node.get("edges") or [] if e.get("to") in nodes)
    neighbours.update(src for src, _ in backlinks[nid])
    if len(neighbours) > 1:
        out.append(fig(diagram(
            nodes, neighbours, click=lambda n: f"../n/{n}.html",
            click_target="_self", focus=nid,
        )))

    outgoing = [
        (e["rel"], f'{RELATIONS[e["rel"]][0]} {node_link(e["to"], nodes, 1)}', e.get("why"))
        for e in node.get("edges") or []
        if e["to"] in nodes
    ]
    if outgoing:
        out.append(f'<h3>This node</h3><ul class="edges">{edge_items(outgoing)}</ul>')

    inbound = [
        (e["rel"], f'{node_link(src, nodes, 1)} {RELATIONS[e["rel"]][0]} this', e.get("why"))
        for src, e in backlinks[nid]
    ]
    if inbound:
        out.append(f'<h3>Referenced by</h3><ul class="edges">{edge_items(inbound)}</ul>')

    out.append(render_refs(node))
    return page(node["title"], "\n".join(out), 1, mermaid_src)


def render_cluster(cid, title, blurb, nodes, mermaid_src):
    members = members_of(nodes, cid)
    source = diagram(
        nodes, members, click=lambda n: f"../n/{n}.html", click_target="_self"
    )
    cards = "".join(
        f'<div class="card"><h4>{node_link(nid, nodes, 1)}</h4>'
        f'<p>{esc(clean(nodes[nid]["summary"], 150))}'
        f'{esc(" · " + str(nodes[nid]["year"]) if nodes[nid].get("year") else "")}</p></div>'
        for nid in sorted(members, key=lambda n: (nodes[n].get("year") or 9999, n))
    )
    body = (
        f"<h1>{esc(title)}</h1>"
        f'<p class="lede">{esc(blurb)} '
        "<em>Drag to pan, scroll to zoom, click a node to open it.</em></p>"
        f"{fig(source, wide=True)}"
        f'<h2>{len(members)} nodes</h2><div class="cards">{cards}</div>'
    )
    return page(title, body, 1, mermaid_src)


def render_index(nodes, clusters, mermaid_src):
    edge_count = sum(len(n.get("edges") or []) for n in nodes.values())
    ref_count = sum(len(n.get("refs") or []) for n in nodes.values())

    index = [
        {
            "i": nid,
            "t": node["title"],
            "c": node["cluster"],
            "s": clean(node["summary"], 120),
            "k": " ".join(
                [nid, node["title"]] + (node.get("aka") or []) + (node.get("tags") or [])
            ).lower(),
        }
        for nid, node in sorted(nodes.items())
    ]

    cards = "".join(
        f'<div class="card"><h4><a href="c/{cid}.html">{esc(title)}</a></h4>'
        f"<p>{esc(blurb)} — {len(members_of(nodes, cid))} nodes</p></div>"
        for cid, title, blurb in clusters
        if members_of(nodes, cid)
    )

    legend = "".join(
        f'<li><span class="rel">{esc(rel)}</span>{esc(reads)} the target'
        + ("" if required else " <em>(no reason required)</em>")
        + "</li>"
        for rel, (reads, required) in RELATIONS.items()
    )

    body = f"""
<h1>A knowledge graph of computer graphics</h1>
<p class="lede">Where the edges carry the reasons. Most maps of a field give you
the nodes; what is almost never written down is why one technique leads to the
next — and that is the part this collects.</p>

<div class="stat">
  <div><b>{len(nodes)}</b><span>nodes</span></div>
  <div><b>{edge_count}</b><span>typed edges</span></div>
  <div><b>{ref_count}</b><span>references</span></div>
  <div><b>{len(clusters)}</b><span>clusters</span></div>
</div>

<input id="q" type="search" placeholder="Search nodes — try ggx, fresnel, denoise"
       autocomplete="off" spellcheck="false">
<ul id="results"></ul>

<h2>Clusters</h2>
<div class="cards">{cards}</div>

<h2>Relations</h2>
<p class="lede">A closed vocabulary. Every edge but <code>part-of</code> must say
why — an edge without a reason is rejected by CI.</p>
<ul class="edges">{legend}</ul>
"""

    script = """
var NODES = %s;
var q = document.getElementById('q'), out = document.getElementById('results');
q.addEventListener('input', function () {
  var v = q.value.trim().toLowerCase();
  if (!v) { out.innerHTML = ''; return; }
  out.innerHTML = NODES
    .filter(function (n) { return n.k.indexOf(v) >= 0 || n.s.toLowerCase().indexOf(v) >= 0; })
    .slice(0, 40)
    .map(function (n) {
      return '<li><a href="n/' + n.i + '.html">' + n.t + '</a> <span class="c">' + n.c + '</span></li>';
    })
    .join('') || '<li class="c">no matches</li>';
});
""" % json.dumps(index, separators=(",", ":"))

    return page("graphics — a knowledge graph", body, 0, mermaid_src, script=script)


def fetch(url):
    ctx = ssl.create_default_context()
    bundle = Path("/root/.ccr/ca-bundle.crt")
    if bundle.exists():
        ctx.load_verify_locations(str(bundle))
    with urllib.request.urlopen(url, context=ctx, timeout=90) as response:
        return response.read()


def main():
    argv = sys.argv[1:]
    out_dir = ROOT / "site"
    if "--out" in argv:
        out_dir = Path(argv[argv.index("--out") + 1]).resolve()
    vendor = "--vendor" in argv

    try:
        nodes, clusters = load_all()
    except Problem as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "n").mkdir(parents=True)
    (out_dir / "c").mkdir(parents=True)

    mermaid_rel = MERMAID_CDN
    if vendor:
        try:
            payload = fetch(MERMAID_CDN)
        except Exception as exc:  # network is the only thing that can fail here
            print(f"error: could not vendor mermaid: {exc}", file=sys.stderr)
            return 1
        (out_dir / "vendor").mkdir()
        (out_dir / "vendor" / MERMAID_FILE).write_bytes(payload)
        mermaid_rel = f"vendor/{MERMAID_FILE}"
        print(f"vendored mermaid {MERMAID_VERSION} ({len(payload) // 1024} KiB)")

    def src(depth):
        return ("../" * depth + mermaid_rel) if vendor else MERMAID_CDN

    backlinks = incoming(nodes)

    (out_dir / "style.css").write_text(STYLE.strip() + "\n")
    (out_dir / ".nojekyll").write_text("")
    (out_dir / "index.html").write_text(render_index(nodes, clusters, src(0)))

    for cid, title, blurb in clusters:
        if members_of(nodes, cid):
            (out_dir / "c" / f"{cid}.html").write_text(
                render_cluster(cid, title, blurb, nodes, src(1))
            )

    for nid in nodes:
        (out_dir / "n" / f"{nid}.html").write_text(
            render_node(nid, nodes, clusters, backlinks, src(1))
        )

    # The whole graph as one file, for anyone who wants to query it elsewhere.
    (out_dir / "graph.json").write_text(json.dumps({
        "nodes": {
            nid: {k: v for k, v in node.items() if not k.startswith("_")}
            for nid, node in sorted(nodes.items())
        },
        "clusters": [{"id": c, "title": t, "blurb": b} for c, t, b in clusters],
        "relations": {r: reads for r, (reads, _) in RELATIONS.items()},
    }, indent=2))

    pages = 1 + len(nodes) + sum(1 for c in clusters if members_of(nodes, c[0]))
    print(f"ok: {pages} pages -> {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
