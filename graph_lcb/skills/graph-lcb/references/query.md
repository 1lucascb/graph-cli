# Querying the graph precisely

Use this file when you must answer a question from an existing graph, trace dependencies, or explain how two things connect. The goal is **precise answers with minimal output**.

## Contents
1. Ground rules
2. Choosing the right command
3. Filter semantics you must know
4. Recipes
5. Traverse and path in detail
6. Keeping output small
7. Verifying before you answer
8. Common mistakes

## 1. Ground rules

1. **Know the vocabulary first.** Run `graph contract --compact` once. Without it you will guess type names and get empty results.
2. **Confirm IDs before structural queries.** `traverse`, `path`, `--from`, and `--to` need exact existing node IDs; an unknown ID is an error. If you only know a name, find the ID first (step "Find a node" below).
3. **Go from cheap to expensive.** `status` -> filtered `nodes` -> `traverse` -> `path` -> full record by ID. Do not start with a full dump.
4. **Check `truncated`.** If it is `true`, your answer is incomplete. Narrow the filter or raise `--limit` before concluding anything.
5. **Absence needs care.** An empty result means "not in the graph", not "does not exist in reality". The graph only knows what was mapped.

## 2. Choosing the right command

| You know... | You want... | Use |
| --- | --- | --- |
| The exact node ID | The full record | `graph nodes ID` |
| A type and maybe a property | A list of matching nodes | `graph nodes --type=T --p.KEY=VALUE` |
| Part of a node's name | Candidate nodes | `graph nodes --contains=TEXT` (or `--prefix`, `--suffix`) |
| A phrase but not where it appears | Anything mentioning it | `graph search` (see search.md) |
| A node | What it connects to, one hop | `graph edges --from=ID` and/or `--to=ID` |
| A node | Everything around it | `graph traverse ID --depth=N` |
| Two nodes | How they connect | `graph path A B` |
| An edge ID | The full edge record | `graph edges EDGE_ID` |
| Nothing yet | Overall shape and gaps | `graph status` |

## 3. Filter semantics you must know

- **Filters combine with AND.** Values within `--type=A,B` combine with OR.
- **`nodes --contains/--prefix/--suffix` match the node name only**, case-insensitively. They do not search descriptions, properties, or IDs. For those use `search`.
- **`--p.KEY=VALUE` compares strings case-insensitively.** `--p.language=python` matches `Python`. Numbers and booleans compare by value (`--p.port=8080`, `--p.public=true`).
- **`--properties JSON` compares exactly**, including case, and every supplied key must match. Extra properties on the node are fine.
- **You can combine `--properties` and `--p.KEY`** only when they filter different keys.
- **An ID lookup cannot combine with filters or `--fields`.** `graph nodes orders-api` returns the whole record directly (no `rows` envelope).
- **`--from` and `--to` require existing node IDs.** They can be combined to find edges between two specific nodes.
- **`--type` on `edges` must be an existing edge type.** A typo is an error, not an empty result.
- **Order.** `nodes` follows the order in `graph.json`. `edges` are sorted by source, type, target, edge ID.

## 4. Recipes

### Find a node when you only know a name
```sh
graph nodes --contains=order --fields=id,type,name --limit=10
```
If several candidates appear, pick by type or properties, or open the full record with `graph nodes ID`. If nothing appears, the name may live elsewhere: try `graph search order --kind=nodes`.

### List everything of one type, compactly
```sh
graph nodes --type=API --fields=id,name --limit=50
```
Check `total` against the number of rows returned.

### Filter by property
```sh
graph nodes --type=API --p.language=Go --fields=id,name
graph nodes --properties '{"language":"Go","framework":"Gin"}' --fields=id
```

### What does X call? (outgoing, one hop)
```sh
graph edges --from=orders-api --type=CALLS
```

### Who calls X? (incoming, one hop)
```sh
graph edges --to=stock-api --type=CALLS
```

### Impact analysis: what breaks if X changes?
Follow incoming edges transitively.
```sh
graph traverse stock-api --direction=in --edge=CALLS --depth=3 --limit=50
```
Everything returned (except the anchor) depends on `stock-api` directly or indirectly.

### Dependency closure: what does X rely on?
```sh
graph traverse orders-api --direction=out --edge=CALLS,READS --depth=4 --limit=50
```

### Does A reach B, and how?
```sh
graph path orders-api orders-db --direction=out --max-depth=6 --limit=3
```
Empty `paths` means no route under those constraints. Retry with `--direction=both` or without `--edge` before concluding they are unrelated.

### Edges between two specific nodes
```sh
graph edges --from=orders-api --to=stock-api --fields=id,type,description,properties
```
Useful to see parallel edges (same endpoints, different purpose).

### Why does this edge exist?
```sh
graph edges EDGE_UUID
```
Read `description` and `evidences`, then open the cited `source` file if the answer matters.

### Find loose ends
```sh
graph status --check=orphans,no-evidence,no-description --limit=20
```

## 5. Traverse and path in detail

### traverse
- Breadth-first from the anchor. **The anchor is always included.**
- **Default direction is `both`.** This pulls in both callers and callees and gets noisy fast. Choose `out` or `in` deliberately.
- **Default depth is 1.** Increase gradually (2, then 3). Each hop can multiply results.
- `--edge` restricts which edge types are followed. Use it whenever you know the relationship you care about.
- `--limit` caps reached nodes (excluding the anchor). `truncated:true` appears only when the limit cut off reachable nodes, not merely because the depth ended.
- Edges in the result keep their stored orientation, even when traversing `in`. Read `[source,type,target,target_type]` literally.
- The edge list can include cross-links and cycle-closing edges, so it may contain more edges than a tree would.

### path
- Returns **simple paths** (no node repeats), shortest first.
- **Default direction is `out`** and **default `--limit` is 1.** Ask for more paths with `--limit=5` when alternatives matter.
- `--max-depth` defaults to node count minus 1, which can be expensive on dense graphs. Always set `--max-depth`, `--edge`, and a modest `--limit` there.
- `truncated:true` means another path exists beyond the limit.
- Parallel edges produce distinct paths.
- Same source and target gives a zero-hop path.

## 6. Keeping output small

- Always pass `--fields` for lists. `id,type,name` is usually enough to decide what to look at next.
- Use `--limit` and read `total` to decide whether to refine or page.
- Prefer a precise filter over a large limit.
- Use `--fields=id,description` when you want to understand nodes without evidences and metadata.
- Open full records (`graph nodes ID`, `graph edges EDGE_ID`) only for the few items you will actually cite. Full records include evidences and metadata and are the most expensive output.

## 7. Verifying before you answer

The graph is a map, not the territory. For anything consequential:

1. Open the full record of the key nodes or edges.
2. Read their `evidences`. Each should name a `source` and `locator`.
3. Open that source and confirm the claim still holds. Evidence can be stale if files changed after mapping.
4. In your answer, distinguish **what the graph says** from **what you verified in source**.
5. If evidence is missing, say so. A relationship with no evidence is a lead, not a fact.

## 8. Common mistakes

| Mistake | Fix |
| --- | --- |
| Guessing a type name and getting `unknown_type` or empty rows | Run `graph contract --compact` first |
| Using `--contains` to look in descriptions | It only matches names. Use `graph search` |
| Treating default `traverse` (direction `both`) as "dependencies" | Set `--direction=out` or `in` explicitly |
| Concluding "no path" from one default `path` call | Try `--direction=both`, raise `--max-depth`, drop `--edge` |
| Ignoring `truncated:true` | Narrow the query or raise the limit and rerun |
| Reading edge rows as `[from,to,...]` | The order is `[source,type,target,target_type]` |
| Dumping all nodes of a large graph | Filter by type/property and use `--fields` |
| Trusting evidence without opening the source | Verify the cited file and lines for anything important |