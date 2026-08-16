# graphics

A knowledge graph of computer graphics, in which **the edges carry the reasons**.

Most maps of a field give you the nodes: a list of techniques, a reading list, a
citation graph. The nodes are the easy part — GGX, Smith, VNDF are in every
textbook index. What is almost never written down is *why one leads to the next*:

```
GGX  ──"can't hit back-facing normals"──▶  VNDF
```

That edge is the compressed judgment a practitioner accumulates and a citation
database throws away. Collecting those is the entire point of this repository.

## Where things live

Nothing in this file is generated, and nothing generated is committed. The
repository holds only what a person wrote; everything derived from it is built
on demand and published to the site, so the two can never drift apart.

| | |
| --- | --- |
| [`nodes/`](nodes/) | the graph — one hand-written YAML file per node |
| [`clusters.yaml`](clusters.yaml) | the groupings nodes are filed under |
| [`tools/`](tools/) | validation, queries, and the site generator |
| [`SCHEMA.md`](SCHEMA.md) | the node format and the relation vocabulary |
| **[kvark.github.io/graphics](https://kvark.github.io/graphics/)** | the rendered graph: diagrams, a page per node, search, `graph.json` |

## A node

Plain YAML. The filename is the id, so it cannot drift out of sync with the
contents.

```yaml
title: Height-Correlated Smith
cluster: materials
year: 2014
summary: >
  Accounts for the fact that a microfacet hidden from the light is likely to
  be hidden from the view as well, since both depend on the same height field.
wikipedia: https://en.wikipedia.org/wiki/Specular_highlight
refs:
  - title: Understanding the Masking-Shadowing Function in Microfacet-Based BRDFs
    authors: Heitz
    year: 2014
    url: https://jcgt.org/published/0003/02/03/paper.pdf
edges:
  - rel: corrects
    to: smith-masking
    why: incident and exitant masks are related, not independent
```

Eight relations, no free-form types: `part-of`, `specializes`, `approximates`,
`corrects`, `extends`, `requires`, `alternative-to`, `validates`.

Two rules the validator enforces. Every edge except `part-of` must say *why* —
that reason is the thing being collected, so an edge without one is not worth
having. And every node must carry at least one link out, a paper or a Wikipedia
article, so a reader can check a claim instead of trusting the summary.

## Browsing

Each cluster is one pannable, zoomable diagram. Every node gets a page with its
reasoned edges in **both** directions — what it corrects, and what corrects it —
along with its neighbourhood and its sources. The whole graph is also served as
a single [`graph.json`](https://kvark.github.io/graphics/graph.json).

Edges are colour-coded by family — supersedes, classifies, substitutes for,
depends on — with the second relation in each family drawn dashed. Eight hues
would have been simpler, but eight cannot be told apart reliably under colour
vision deficiency, and four plus a line pattern can.

The site is published automatically on every push to `main`.

## Querying

The question a rendered mind map can never answer is "what connects these two
things?" — so that is the one the tools answer:

```console
$ python3 tools/kg.py path lambert diffuse-layering
Lambertian Diffuse (lambert)
  --specializes-->
      (the simplest case, a constant BRDF)
  Diffuse Reflection (diffuse-reflection)
  --part-of-->
  Reflection (reflection)
  <--part-of--
  Fresnel Equations (fresnel)
  <--requires--
      (each microfacet is a mirror, so needs its reflectance)
  Microfacet Model (microfacet-model)
  ...
```

```console
$ python3 tools/kg.py show vndf       # a node, with incoming and outgoing edges
$ python3 tools/kg.py search fresnel  # substring across ids, titles, summaries
$ python3 tools/kg.py stats           # counts, and anything left unconnected
```

## Contributing

Add one file to `nodes/`. You never have to edit an existing node to attach a
new one, because edges are declared on the node that owns them — so two people
working in the same area do not collide.

```console
$ python3 tools/check.py           # validate; CI runs exactly this
$ python3 tools/site.py            # build the site locally into site/
$ python3 tools/site.py --vendor   # ...with mermaid bundled, as CI publishes it
```

An edge whose `why` could be swapped onto any other pair of nodes is not
carrying its weight. "improves on it" is not a reason; "photon count is capped
by memory, so bias never vanishes" is.
