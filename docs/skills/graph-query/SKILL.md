---
name: graph-query
description: Query this graph workspace effectively. Use when exploring graph nodes, edges, neighborhoods, connections, paths, or choosing graph contract, nodes, edges, traverse, and path commands.
---

# Graph Query

Use this workflow when answering questions about what is in the graph or how
records are connected. Run commands from the project directory whose `.graph/`
workspace you want to inspect.

## Query workflow

1. **Check the contract first.**
   - Run `graph contract` to see entity and edge types, descriptions, properties,
     and endpoint constraints.
   - Use `graph contract entities` or `graph contract edges` to narrow the
     output.
   - Confirm the edge type allows the source and target entity types you expect.
     Type names are case-insensitive, but use the contract's canonical spelling
     in explanations.

2. **Find and confirm the nodes.**
   - Use `graph nodes` to list nodes, or narrow the list with `--type`,
     `--contains`, `--prefix`, `--suffix`, or `--properties`.
   - Use `graph nodes NODE_ID` to inspect a matching node's full record.
   - Query commands take node IDs, not display names. Confirm the IDs before
     using them as path endpoints or traversal anchors.
   - If results are unexpectedly unavailable, check that you are in the
     intended working directory and that the workspace has been initialized
     with `graph init`.

3. **Choose the query that matches the question.**
   - Use `graph edges --from=NODE_ID`, `--to=NODE_ID`, and `--type=TYPE` to
     inspect direct connections or filter edges.
   - Use `graph traverse NODE_ID` to explore a neighborhood breadth-first.
     Set `--depth` to bound the number of hops, `--direction=in|out|both` to
     control traversal direction, and `--edge=TYPE[,TYPE...]` to focus on
     specific relationships. Traversal defaults to depth 1 and direction
     `both`.
   - Use `graph path SOURCE_ID TARGET_ID` to find routes between two nodes.
     Path search defaults to outgoing edges and returns one shortest path.
     Consider `--direction=both` if the intended relationship may be followed
     in either direction.

4. **Narrow broad or ambiguous results.**
   - Add edge-type filters and a modest `--max-depth` to path queries.
   - Increase `--limit` only when you need alternate paths; path results are
     ordered shortest first, and parallel edges may produce distinct paths.
   - For traversal, keep `--depth` and `--limit` appropriate to the question.
     The output's `truncated` field indicates whether a node limit excluded
     reachable nodes.
   - Read the result fields and direction carefully: path/traversal edge tuples
     preserve each edge's stored source-to-target orientation, even if the
     query follows it backward.

## Examples

Discover candidate nodes, then inspect one:

```sh
graph nodes --type=API --contains=order
graph nodes orders-api
```

Inspect direct edges and a bounded neighborhood:

```sh
graph edges --from=orders-api --type=CALLS
graph traverse orders-api --depth=2 --direction=out --edge=CALLS,PUBLISHES --limit=20
```

Compare paths in both endpoint orders. The commands are independent searches:

```sh
graph path orders-api database
graph path database orders-api
```

They can also be run in one terminal command when useful:

```sh
# POSIX shells and PowerShell: run the second query regardless of the first result.
graph path orders-api database; graph path database orders-api

# POSIX shells, cmd.exe, and PowerShell 7+: run the second only if the first succeeds.
graph path orders-api database && graph path database orders-api
```

Use the command separator supported by the active shell. In particular,
`&&` is not supported by Windows PowerShell 5.1; use separate commands or `;`
there. The semicolon is not a command separator in `cmd.exe`.

## Useful references

- `graph help COMMAND` for a concise command synopsis.
- `graph contract` for type and endpoint definitions.
- The repository README sections for `graph nodes`, `graph edges`,
  `graph traverse`, and `graph path` for the complete option and output
  reference.
