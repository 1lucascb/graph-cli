"""Command help catalog. Keep command behavior descriptions aligned with README.md."""

HELP_TEXTS = {
    "status": """Usage: graph status [--check=orphans,no-evidence,no-description,components] [--limit N] [--strict]

Read-only summary; requires initialized contracts. A missing graph.json is an
empty graph. Totals and per-type counts are always returned. --check selects
finding sections (default: all); --limit is a positive sample cap (default 10).
Orphans have no incident valid edge; self-loops count as incident. Missing
evidence means an empty/absent evidences list; missing description means empty
or whitespace-only. Components are undirected, exclude orphans, and ignore
dangling edges. Node samples are IDs; edge samples use
[source,type,target,target_type]. Sample lists are ID-sorted for nodes and use
the normal edge sort order; each has count, ids, and truncated.
Returns totals, selected checks, and valid from validation.
Exit: 0 by default; --strict returns 3 if a selected check has findings.
Example: graph status --check=orphans,no-evidence --limit=5 --strict""",
    "init": """Usage: graph init

Create .graph/, starter entity/edge contracts, and missing bundled schemas.
Preserves existing files; does not create graph.json.
Returns: {\"initialized\":true,\"directory\":\".graph\"}. Safe to rerun.
Example: graph init""",
    "contract": """Usage: graph contract [entities|edges] [--compact]

Read and print the entity and/or edge type contracts. Before initialization,
prints built-in starter contracts without writing files. Default output is JSON;
--compact prints readable type, endpoint, and property summaries.
Returns: contract object(s), or compact text. $schema metadata is omitted.
Examples: graph contract | graph contract edges --compact""",
    "validate": """Usage: graph validate

Read-only validation of workspace contracts and graph records; reports all
detected issues and never creates or repairs files. Missing graph.json is an
empty graph. A missing workspace or unreadable files are represented in JSON.
Returns: {valid, errors, summary:{nodes,edges,errors}}.
Exit: 0 valid; 3 invalid; 4 unavailable workspace/data.
Example: graph validate""",
    "import": """Usage: graph import FILE [--on-conflict=error|skip|replace] [--dry-run]

Import JSONL (one JSON object per line); FILE '-' reads stdin. Records may use
kind=node|edge; otherwise source/target fields identify edges. Edge IDs may be
omitted and generated. Parses and validates the whole batch before one atomic
write; any invalid record aborts all changes. Conflict key: node ID, or edge ID /
type+endpoints+properties. replace updates differences; skip preserves existing.
--on-conflict=error (default) reports a conflict and aborts the whole import;
skip leaves the existing record unchanged; replace updates differing content.
With replace, identical content is counted as unchanged. For semantic edge
replacement, the existing edge ID is retained.
Returns: {valid,dry_run,summary:{created,updated,unchanged,errors},errors}.
--dry-run reports planned counts without writing. Invalid batch exits 3.
Examples: graph import records.jsonl --dry-run | cat records.jsonl | graph import -""",
    "add-node": """Usage: graph add-node ID NAME TYPE [--description TEXT] [--properties JSON | --p.KEY=VALUE ...] [--evidences JSON_ARRAY]

Create a node; ID must match ^[a-z0-9][a-z0-9._-]*$, be unique, and TYPE must
exist in entities.json. Property keys/types and required values follow its
contract. --properties replaces the complete property object; --p.KEY sets
individual values (JSON literals keep their types, other text is a string).
Returns: complete node record with metadata timestamps and evidences.
Example: graph add-node orders-api \"Orders API\" API --p.language=Python""",
    "add-edge": """Usage: graph add-edge SOURCE_ID EDGE_TYPE TARGET_ID [--description TEXT] [--properties JSON | --p.KEY=VALUE ...] [--evidences JSON_ARRAY]

Create a directed edge between existing nodes. Contract endpoint types must
allow the source and target node types. Duplicate edges (same type/endpoints/
properties) are rejected; parallel edges require a non-empty description and,
for the same type, different properties. Edge ID is generated.
Returns: complete edge record; target_type is derived from target node.
Example: graph add-edge orders-api CALLS stock-api --description \"Checks stock\"""" ,
    "nodes": """Usage: graph nodes [ID] [--type TYPE[,TYPE...]] [--properties JSON] [--p.KEY=VALUE ...] [--prefix TEXT] [--suffix TEXT] [--contains TEXT] [--limit N] [--fields FIELD,...]

Get a complete node by exact ID, or list nodes matching filters. Filters combine
with AND; multiple types combine with OR. Name matches are case-insensitive;
--p.KEY string comparisons ignore case, --properties values compare exactly.
--fields selects id,type,name,description,properties,metadata,evidences.
List returns {rows,total,truncated}; total is before limit. ID lookup cannot
combine with filters or --fields. List order follows graph.json.
Examples: graph nodes orders-api | graph nodes --type=API --contains=order --limit=10""",
    "edges": """Usage: graph edges [EDGE_ID] [--type TYPE[,TYPE...]] [--properties JSON] [--p.KEY=VALUE ...] [--from SOURCE_ID] [--to TARGET_ID] [--limit N] [--fields FIELD,...]

Get a complete edge by ID, or list edges matching filters. Filters combine
with AND; multiple types combine with OR. --from/--to require existing node
IDs. --fields selects id,type,source,target,target_type,description,properties,
metadata,evidences. Default list rows are [source,type,target,target_type],
sorted by source,type,target,edge ID. List returns {rows,total,truncated}.
Examples: graph edges --type=CALLS --from=orders-api | graph edges EDGE_UUID""",
    "edit": """Usage: graph edit node ID [options] | graph edit edge EDGE_ID [options]
Options: [--name TEXT] [--description TEXT] [--properties JSON | --p.KEY=VALUE ...] [--evidences JSON_ARRAY]

Update an existing record in place. Node/edge IDs, types, and endpoints cannot
be edited. --properties replaces all properties; --p.KEY updates selected keys.
--evidences replaces the full evidence list; [] clears it. At least one editable
option is required; omitted values are preserved. Contracts and edge duplicate/
parallel rules are revalidated; updated_at is refreshed.
Returns: updated complete record.
Examples: graph edit node orders-api --name=\"Orders service\" | graph edit edge EDGE_UUID --p.method=GET""",
    "delete": """Usage: graph delete node ID | graph delete edge EDGE_ID | graph delete edge SOURCE_ID EDGE_TYPE TARGET_ID

Delete a node (also removes every connected edge) or an edge. Tuple edge
selection is case-insensitive by type and requires existing endpoints; it only
deletes when exactly one edge matches. If ambiguous, no data changes and the
candidate IDs are printed (exit 2). Delete by ID to select exactly one record.
Returns: deleted record; node deletion also reports deleted_edges count.
Examples: graph delete node orders-api | graph delete edge SOURCE CALLS TARGET""",
    "traverse": """Usage: graph traverse NODE_ID [--depth N] [--direction in|out|both] [--edge TYPE[,TYPE...]] [--limit N] [--fields FIELD,...]

Breadth-first traversal from an existing anchor; anchor is always included.
Depth is positive hops (default 1); direction defaults to both. --edge filters
allowed contract types. --limit caps reached non-anchor nodes. --fields selects
id,type,name,description,properties,metadata,evidences instead of node tuples.
Returns: {nodes,edges,truncated}. Default nodes are [id,type,name]; edges are
[source,type,target,target_type] in stored orientation. Cross-links/cycle edges
may appear. truncated is true only when --limit excludes reachable nodes.
Example: graph traverse orders-api --depth=2 --direction=out --edge=CALLS --limit=20""",
    "path": """Usage: graph path SOURCE_ID TARGET_ID [--direction out|in|both] [--edge TYPE[,TYPE...]] [--max-depth N] [--limit N] [--fields FIELD,...]

Enumerate simple paths (no repeated node) between existing nodes. Direction
defaults to out; in traverses backward and both permits either orientation.
Paths are shortest first with deterministic tie-breaking. max-depth defaults to
node_count-1; 0 permits only a same-node zero-hop path. --limit defaults to 1.
Returns: {paths,truncated}; each path has nodes, edges, hops. Default nodes are
[id,type,name], edges [edge_id,source,type,target,target_type]. No route gives
paths=[]. truncated means another path exists beyond limit, not search cutoff.
Use --max-depth/--edge/modest --limit on dense graphs.
Example: graph path orders-api database --direction=both --edge=CALLS,READS --limit=5""",
    "view": """Usage: graph view [--no-open]

Generate a self-contained HTML visualization at .graph/view.html using graph
records and contract descriptions. Requires initialized workspace; overwrites
view.html but does not modify graph.json. Opens the page in the system browser
unless --no-open is supplied.
Returns: JSON with absolute path, node/edge counts, and opened status.
Example: graph view --no-open""",
}
