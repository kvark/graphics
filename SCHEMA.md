# Schema

The graph is a directory of YAML files, one per node, in [`nodes/`](nodes/).
There is no database and no build step required to *read* it — every file is
plain text and renders fine on GitHub. The tools in [`tools/`](tools/) are
optional conveniences.

## Node files

The filename is the node id. `nodes/ggx.yaml` is the node `ggx`. The id is
never repeated inside the file, so it cannot drift out of sync.

```yaml
title: GGX / Trowbridge-Reitz
cluster: materials
year: 2007
aka: [Trowbridge-Reitz, GTR2]
tags: [microfacet, ndf, specular]
summary: >
  Microfacet normal distribution with a much longer tail than Beckmann,
  which is why rough metals rendered with it keep a visible highlight
  falloff instead of ending abruptly.
refs:
  - title: Microfacet Models for Refraction through Rough Surfaces
    authors: Walter, Marschner, Li, Torrance
    year: 2007
    url: http://www.cs.cornell.edu/~srm/publications/EGSR07-btdf.pdf
edges:
  - rel: specializes
    to: microfacet-model
    why: supplies the D term for the microfacet framework
```

| field | required | notes |
|---|---|---|
| `title` | yes | human-readable name, used as the diagram label |
| `cluster` | yes | must appear in [`clusters.yaml`](clusters.yaml); groups nodes into diagrams. Each cluster names a domain in [`domains.yaml`](domains.yaml) — nodes never name a domain directly |
| `summary` | yes | one or two sentences, prose |
| `year` | no | year the idea was introduced |
| `aka` | no | alternate names, for search |
| `tags` | no | free-form, not validated |
| `wikipedia` | no | full URL of a background article |
| `refs` | no | primary sources |
| `edges` | no | typed relations to other nodes |

**Every node must have at least one link out** — a `ref` with a `url`, or a
`wikipedia` article, or both. A node with neither fails validation. The point is
that a reader can check a claim against something outside this repository rather
than trusting a summary written here; a `corrects` edge is only worth having if
the paper it points at can be read.

Prefer the primary source. Wikipedia is the fallback for ideas that never had
one paper — radiance, rasterization, tone mapping — and for nodes whose source
is a course or a talk with no stable URL.

## Edges

Edges are declared **on the subject node** and read as a sentence:

> *&lt;this node&gt;* — *&lt;rel&gt;* → *&lt;target&gt;*, because *&lt;why&gt;*

This direction matters for scale: adding a node means adding exactly one
file. You never edit a parent to register a child, so two people adding
nodes in the same area do not conflict.

Every edge needs a `why` except `part-of`, whose meaning is already carried
by the relation. `why` is the point of the project — it is the compressed
judgment that citation databases throw away — so keep it specific and
short enough to sit on a diagram edge. "fixes a problem" is not a `why`;
"can't hit back-facing normals" is.

### Relation vocabulary

The vocabulary is deliberately closed. Eight relations, no free-form types.
If something doesn't fit, that's a discussion to have before widening it.

| rel | reads as | example |
|---|---|---|
| `part-of` | this is a subtopic of the target | `lambert` → `diffuse-reflection` |
| `specializes` | this is a specific case of a general framework | `ggx` → `microfacet-model` |
| `approximates` | this is a cheaper stand-in for the target | `schlick` → `fresnel` |
| `corrects` | this fixes a named defect in the target | `vndf` → `ggx` |
| `extends` | this adds capability to the target, no defect implied | `restir-gi` → `restir` |
| `requires` | this does not work without the target | `taa` → `temporal-reprojection` |
| `alternative-to` | a competing approach to the same problem | `photon-mapping` → `bidirectional-path-tracing` |
| `validates` | this is a test or metric for the target | `white-furnace-test` → `energy-conservation` |

`corrects` and `extends` are the two that carry the most information and
are the easiest to conflate. Use `corrects` only when you can name the
specific thing that was wrong.

## Tools

```
python3 tools/check.py            # validate the graph; this is what CI runs
python3 tools/kg.py show ggx      # node detail, with incoming and outgoing edges
python3 tools/kg.py path lambert diffuse-layering
python3 tools/kg.py search fresnel
python3 tools/kg.py stats
python3 tools/site.py             # build the GitHub Pages site into site/
```

All three read the graph through `tools/graph.py`, which owns the schema —
the relation vocabulary and the validation rules live there and nowhere else.

No tool writes into the repository. `site.py` is the only generator and its
output goes to `site/`, which is gitignored and published to Pages. Counts,
indexes and diagrams therefore live on the site only: nothing committed here
can go stale, because nothing committed here is derived.

`path` is the query the mind-map format could never answer: it prints the
chain of typed edges connecting two techniques, with the reason on each hop.
