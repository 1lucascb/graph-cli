_RAW = {
    "status": r"""
graph status - Summarize graph size and data-quality findings

USAGE
  graph status [--check=CHECKS] [--limit N] [--strict]

OPTIONS
  --check=CHECKS   Comma-separated sections: orphans, no-evidence, no-description, components (default: all)
  --limit N        Positive sample cap per section (default: 10)
  --strict         Exit 3 if any selected check has findings

OUTPUT
  Always: nodes and edges with "total" and "by_type".
  Per selected check (keys: orphans, no_evidence, no_description, components): count, ids, truncated.
  Also: "valid", the result of `graph validate` on the current contracts and graph.
  Node samples are sorted IDs. Edge samples are [source,type,target,target_type] in the normal edge order.
  components reports the component "count" and the "largest" size.

WHAT COUNTS AS A FINDING
  orphans          Nodes with no incident edge whose endpoints both exist (a self-loop counts as incident)
  no-evidence      Nodes or edges whose evidences list is empty or absent
  no-description   Nodes or edges whose description is empty or whitespace-only
  components       More than one connected component (undirected, orphans excluded, dangling edges ignored)

NOTES
  Read-only. Requires an initialized workspace. A missing graph.json is treated as an empty graph.

EXIT CODES
  0   Success (default, even with findings)
  3   --strict and at least one selected check has findings

EXAMPLES
  graph status
  graph status --check=orphans,no-evidence --limit=5
  graph status --check=orphans --strict          # use in CI to fail on orphan nodes
""",
    "init": r"""
graph init - Create the .graph/ workspace

USAGE
  graph init [--template NAME] [--dry-run]
  graph init --list-templates

DESCRIPTION
  Creates .graph/, empty contracts containing only their $schema keys, and any missing bundled JSON Schemas. Templates provide editable starting contracts.

OPTIONS
  --template NAME    Apply a bundled template (codebase or documents) to empty contracts
  --list-templates   List bundled templates and descriptions without reading the workspace
  --dry-run          Show files that would be created without writing them

OUTPUT
  Includes initialized, directory, and contracts (empty, template, or existing).
  Template runs also include template and applied. Dry runs include would_write.

NOTES
  Safe to rerun: contracts containing types, schemas, and graph data are never overwritten. Empty contracts can receive a template.
  Templates are starting points. Review and edit them for the project's domain.
  Does not create graph.json; it is written the first time a record is added.
  Run it from the project whose .graph/ you want to use (the workspace is resolved from the current directory).

EXAMPLES
  graph init
  graph init --list-templates
  graph init --template=codebase
  graph init --template documents --dry-run
""",
    "install-skill": r"""
graph install-skill DIRECTORY - Install the bundled graph-lcb agent skill

USAGE
  graph install-skill DIRECTORY

DESCRIPTION
  Copies SKILL.md and its references into DIRECTORY/graph-lcb/.

NOTES
  DIRECTORY is created if needed. Existing DIRECTORY/graph-lcb/ is preserved and causes an error.

EXAMPLES
  graph install-skill .
  graph install-skill ../my-project
""",
    "contract": r"""
graph contract - Show the entity and edge type contracts

USAGE
  graph contract [entities|edges] [--compact]

ARGUMENTS
  entities | edges   Show only that section (default: both)

OPTIONS
  --compact          Readable text summary (types, endpoints, property types) instead of JSON

OUTPUT
  JSON by default: {"entities":...,"edges":...}, or just the selected contract object.
  With --compact: plain text, not JSON. The $schema metadata is always omitted.

NOTES
  Works before `graph init`: prints empty contracts without writing any files.
  AI agents: run this first to learn valid types and properties before adding records.

EXAMPLES
  graph contract
  graph contract edges --compact
""",
    "validate": r"""
graph validate - Check contracts and graph records for problems

USAGE
  graph validate

OUTPUT
  {"valid":bool,"errors":[{"kind","id","code","message"}],"summary":{"nodes","edges","errors"}}
  All detected issues are reported in one response.

NOTES
  Read-only: never creates or repairs files. A missing graph.json is treated as an empty graph.
  A missing workspace or unreadable files are reported in the JSON output (exit 4).

EXIT CODES
  0   Valid
  3   Contract or graph violations found
  4   Workspace, contract, or graph store unavailable or unreadable

EXAMPLES
  graph validate
""",
    "import": r"""
graph import - Bulk-load nodes and edges from JSONL

USAGE
  graph import FILE [--on-conflict=error|skip|replace] [--dry-run]

ARGUMENTS
  FILE   Path to a JSONL file (one JSON object per line), or "-" to read stdin

OPTIONS
  --on-conflict=MODE   error (default): report the conflict and abort everything
                       skip: keep the existing record unchanged
                       replace: update the existing record if content differs (identical content counts as unchanged)
  --dry-run            Validate and report planned counts without writing

RECORD FORMAT
  {"kind":"node","id":"web-api","type":"API","name":"Web API","properties":{"language":"Python"}, "evidences": [{"source": "...", "start_line": X, "end_line": Y}, {...}]}
  {"kind":"edge","type":"CALLS","source":"web-api","target":"billing-api","description":"Requests payment","properties":{"protocol":"HTTP"}, "evidences": [EVIDENCE_OBJECTS...]}
  "kind" is optional: records with source/target are edges, everything else is a node. Edge "id" may be omitted (it is generated).
  Edges may reference nodes defined later in the same file.

CONFLICT KEYS
  Nodes: the node ID.
  Edges: the edge ID, or the same type + endpoints + properties. A semantic replace keeps the existing edge ID.

OUTPUT
  {"valid","dry_run","summary":{"created","updated","unchanged","errors"},"errors":[...]}
  Errors include the input line number when tied to a record.

NOTES
  The whole batch is parsed and validated before one atomic write: a single invalid record aborts all changes.
  AI agents: always run with --dry-run first.

EXIT CODES
  0   Imported (or dry run passed)
  3   Invalid batch; nothing was written

EXAMPLES
  graph import records.jsonl --dry-run
  graph import records.jsonl --on-conflict=replace
  cat records.jsonl | graph import -
""",
    "add-node": r"""
graph add-node - Create a node

USAGE
  graph add-node ID NAME TYPE [--description TEXT] [--properties JSON | --p.KEY=VALUE ...] [--evidences JSON_ARRAY]

ARGUMENTS
  ID     Unique identifier, matching ^[a-z0-9][a-z0-9._-]*$ (lowercase letters/digits first; then also . _ -)
  NAME   Display name, stored as given
  TYPE   Entity type from entities.json (case-insensitive; stored in the contract's spelling)

OPTIONS
  --description TEXT     Free-form description (default: empty)
  --properties JSON      Complete properties object (default: {}). Keys must exist in the contract and required ones must be present
  --p.KEY=VALUE          Set a single property; repeatable. 3, true, null become JSON values, anything else is a string
  --evidences JSON_ARRAY Array of evidence objects (default: []). Fields inside are user-defined

NOTES
  --properties and --p.KEY cannot be combined.
  Metadata created_at and updated_at are set automatically (UTC).

OUTPUT
  The complete node record: id, type, name, description, properties, metadata, evidences.

EXAMPLES
  graph add-node orders-api "Orders API" API --p.language=Python
  graph add-node orders-api "Orders API" API --description "Handles orders" --properties '{"language":"Python","framework":"FastAPI"}'
  graph add-node orders-api "Orders API" API --p.language=Python --evidences '[{"source":"src/orders/api.py","locator":{"start_line":12,"end_line":28}}]'
""",
    "add-edge": r"""
graph add-edge - Create a directed edge between two existing nodes

USAGE
  graph add-edge SOURCE_ID EDGE_TYPE TARGET_ID [--description TEXT] [--properties JSON | --p.KEY=VALUE ...] [--evidences JSON_ARRAY]

ARGUMENTS
  SOURCE_ID    Existing source node ID
  EDGE_TYPE    Edge type from edges.json (case-insensitive)
  TARGET_ID    Existing target node ID

OPTIONS
  --description TEXT      Free-form description (default: empty). Required when another edge already links the same endpoints
  --properties JSON       Complete properties object (default: {})
  --p.KEY=VALUE           Set a single property; repeatable. JSON literals keep their type, anything else is a string
  --evidences JSON_ARRAY  Array of evidence objects (default: [])

RULES
  The edge contract must allow the source node's type and the target node's type.
  Duplicates (same type + endpoints + properties) are rejected, even if descriptions differ.
  A parallel edge of the same type needs a non-empty description and different properties.
  The edge ID is a generated UUID.

OUTPUT
  The complete edge record. target_type is derived from the target node.

EXAMPLES
  graph add-edge orders-api CALLS stock-api
  graph add-edge orders-api CALLS stock-api --description "Checks stock" --p.method=GET
  graph add-edge orders-api CALLS stock-api --description "Reserves stock" --properties '{"method":"POST"}' --evidences '[{"source":"src/orders/client.py"}]'
""",
    "nodes": r"""
graph nodes - Get one node by ID, or list and filter nodes

USAGE
  graph nodes [ID] [--type TYPES] [--properties JSON] [--p.KEY=VALUE ...] [--prefix TEXT] [--suffix TEXT] [--contains TEXT] [--limit N] [--fields FIELDS]

ARGUMENTS
  ID   Exact node ID. Returns the full record directly (no list envelope). Cannot be combined with filters or --fields

FILTERS (combined with AND)
  --type TYPES          One or more types, comma-separated (multiple types combine with OR)
  --properties JSON     Match every given key/value exactly; extra properties on the node are allowed
  --p.KEY=VALUE         Match one property; repeatable. String values compare case-insensitively
  --prefix TEXT         Name starts with TEXT (case-insensitive)
  --suffix TEXT         Name ends with TEXT (case-insensitive)
  --contains TEXT       Name contains TEXT (case-insensitive)

OUTPUT CONTROL
  --limit N             Positive cap on rows, applied after filtering
  --fields FIELDS       Comma-separated subset of: id, type, name, description, properties, metadata, evidences

OUTPUT
  {"rows":[...],"total":N,"truncated":bool}. "total" is counted after filtering but before --limit.
  Rows are full node records unless --fields is used. Order follows graph.json.

EXAMPLES
  graph nodes
  graph nodes orders-api
  graph nodes --type=API,WORKER --contains=order
  graph nodes --p.language=python --limit=10 --fields=id,name,type
""",
    "edges": r"""
graph edges - Get one edge by ID, or list and filter edges

USAGE
  graph edges [EDGE_ID] [--type TYPES] [--properties JSON] [--p.KEY=VALUE ...] [--from SOURCE_ID] [--to TARGET_ID] [--limit N] [--fields FIELDS]

ARGUMENTS
  EDGE_ID   Exact edge ID. Returns the full record directly and cannot be combined with filters

FILTERS (combined with AND)
  --type TYPES          One or more edge types, comma-separated (OR between them). Each must exist in the contract
  --properties JSON     Match every given key/value exactly
  --p.KEY=VALUE         Match one property; repeatable. String values compare case-insensitively
  --from SOURCE_ID      Edges leaving this node (must exist)
  --to TARGET_ID        Edges arriving at this node (must exist)

OUTPUT CONTROL
  --limit N             Positive cap on rows, applied after filtering
  --fields FIELDS       Comma-separated subset of: id, type, source, target, target_type, description, properties, metadata, evidences

OUTPUT
  {"rows":[...],"total":N,"truncated":bool}.
  Default rows are compact tuples [source,type,target,target_type], sorted by source, type, target, then edge ID.
  Use --fields (include "id") when you need edge IDs for `graph edit` or `graph delete`.

EXAMPLES
  graph edges --type=CALLS --from=orders-api --limit=10
  graph edges --to=stock-api --p.method=GET --fields=id,type,source,target,description
  graph edges 6c7f7d2c-22f0-49d2-a7f3-37d9b8cb0988
""",
    "search": r"""
graph search - Find text across nodes and edges

USAGE
  graph search TERM [TERM ...] [--any] [--not TERM ...] [--in FIELDS] [--kind nodes|edges|all] [--type TYPES] [--regex] [--case-sensitive] [--limit N] [--offset N] [--fields FIELDS | --snippets]

MATCHING
  TERM ...            Terms are ANDed by default. Matching is a case-insensitive substring
  --any               OR the positive terms instead
  --not TERM          Exclude records matching TERM; repeatable
  --regex             Treat terms as Python regular expressions
  --case-sensitive    Case-sensitive matching (also applies to regex)

SCOPE
  --in FIELDS         Fields to search: id, name, type, description, properties, evidences, source, target (inapplicable fields are ignored per record kind)
  --kind KIND         nodes, edges, or all (default: all)
  --type TYPES        Only records of these node or edge types

OUTPUT CONTROL
  --limit N           Positive page size
  --offset N          Skip N results (use next_offset from the previous page)
  --snippets          Add an excerpt (about 60 chars) per matched field
  --fields FIELDS     Return arrays of selected values. Allowed: id, type, name, source, target, description, properties, metadata, evidences. Cannot be combined with --snippets

OUTPUT
  {"rows":[...],"total":N,"truncated":bool,"next_offset":N|null}
  Node rows: ["node",id,type,name,matched_fields]. Edge rows: ["edge",source,type,target,matched_fields].
  Results keep graph node order, followed by the normal sorted edge order.

NOTES
  Use `graph nodes` / `graph edges` when you know the structure; use search when you do not know where a phrase appears.
  A term starting with "--" must come after a standalone "--".
  Regex has no timeout: a pathological pattern can be slow on large evidence text.
  Errors are JSON with codes: empty_query, invalid_regex, unknown_field, unknown_kind, unknown_type.

EXAMPLES
  graph search payment billing --kind=nodes
  graph search --regex "payment|billing" stripe --any --limit=20
  graph search timeout --not retry --in=description,evidences --snippets
  graph search -- --literal
""",
    "edit": r"""
graph edit - Update an existing node or edge in place

USAGE
  graph edit node ID [--name TEXT] [--description TEXT] [--properties JSON | --p.KEY=VALUE ...] [--evidences JSON_ARRAY]
  graph edit edge EDGE_ID [--description TEXT] [--properties JSON | --p.KEY=VALUE ...] [--evidences JSON_ARRAY]

OPTIONS
  --name TEXT             (node only) Replace the display name
  --description TEXT      Replace the description; an empty value clears it
  --properties JSON       Replace ALL properties
  --p.KEY=VALUE           Update only the named keys and keep the rest; repeatable. Cannot be combined with --properties
  --evidences JSON_ARRAY  Replace the full evidence list; [] clears it

NOTES
  At least one option is required; omitted fields are preserved.
  IDs, types, and edge endpoints cannot be edited: delete and recreate instead.
  Contracts are revalidated, and edges recheck the duplicate/parallel rules. updated_at is refreshed.

OUTPUT
  The updated complete record.

EXAMPLES
  graph edit node orders-api --name "Orders service"
  graph edit node orders-api --p.framework=FastAPI
  graph edit edge 6c7f7d2c-22f0-49d2-a7f3-37d9b8cb0988 --description "Uses the stock lookup" --p.method=GET
  graph edit node orders-api --evidences '[]'
""",
    "delete": r"""
graph delete - Remove a node or an edge

USAGE
  graph delete node ID
  graph delete edge EDGE_ID
  graph delete edge SOURCE_ID EDGE_TYPE TARGET_ID

FORMS
  node ID                         Deletes the node AND every edge connected to it
  edge EDGE_ID                    Deletes exactly one edge by ID
  edge SOURCE EDGE_TYPE TARGET    Deletes the edge if exactly one matches (type is case-insensitive; both endpoints must exist)

OUTPUT
  The deleted record. Node deletion also reports "deleted_edges" (the number of removed edges).

NOTES
  If the SOURCE/TYPE/TARGET form matches several edges, nothing is deleted and the candidate IDs are printed. Re-run with a specific EDGE_ID.
  Deletion cannot be undone.

EXIT CODES
  0   Deleted
  2   Ambiguous edge selection (graph unchanged) or invalid usage

EXAMPLES
  graph delete node orders-api
  graph delete edge 6c7f7d2c-22f0-49d2-a7f3-37d9b8cb0988
  graph delete edge orders-api CALLS stock-api
""",
    "traverse": r"""
graph traverse - Explore the neighborhood of a node (breadth-first)

USAGE
  graph traverse NODE_ID [--depth N] [--direction in|out|both] [--edge TYPES] [--limit N] [--fields FIELDS]

ARGUMENTS
  NODE_ID   Anchor node (always included in the result)

OPTIONS
  --depth N            Maximum hops, positive integer (default: 1)
  --direction DIR      out follows edges to their targets, in follows them back to their sources, both follows either (default: both)
  --edge TYPES         Only follow these edge types (comma-separated, case-insensitive)
  --limit N            Maximum reached nodes, excluding the anchor
  --fields FIELDS      Return node objects with these fields instead of tuples. Allowed: id, type, name, description, properties, metadata, evidences

OUTPUT
  {"nodes":[...],"edges":[...],"truncated":bool}
  Nodes are [id,type,name] tuples (anchor first). Edges are [source,type,target,target_type] in their stored orientation, even when traversing "in".
  The edge list can include cross-links and cycle-closing edges.
  truncated is true only when --limit excluded reachable nodes (reaching --depth does not set it).

EXAMPLES
  graph traverse orders-api
  graph traverse orders-api --depth=2 --direction=out --edge=CALLS --limit=20
  graph traverse orders-api --fields=id,name,description
""",
    "path": r"""
graph path - Find simple paths between two nodes

USAGE
  graph path SOURCE_ID TARGET_ID [--direction out|in|both] [--edge TYPES] [--max-depth N] [--limit N] [--fields FIELDS]

ARGUMENTS
  SOURCE_ID   Starting node
  TARGET_ID   Destination node

OPTIONS
  --direction DIR     out follows edges forward, in follows them backward, both follows either (default: out)
  --edge TYPES        Only follow these edge types (comma-separated, case-insensitive)
  --max-depth N       Maximum hops, 0 or greater (default: node count - 1). 0 allows only a same-node, zero-hop path
  --limit N           Maximum paths to return (default: 1)
  --fields FIELDS     Return node objects with these fields instead of tuples. Allowed: id, type, name, description, properties, metadata, evidences

OUTPUT
  {"paths":[{"nodes":[...],"edges":[...],"hops":N}],"truncated":bool}
  Nodes are [id,type,name]. Edges are [edge_id,source,type,target,target_type] in stored orientation.
  Paths are ordered shortest first with deterministic tie-breaking. No route gives "paths":[].
  truncated means another path exists beyond --limit; it does not mean the search was cut off.

NOTES
  Simple paths never revisit a node. Parallel edges produce distinct paths.
  On dense graphs, always set --max-depth, --edge, and a modest --limit.

EXAMPLES
  graph path orders-api database
  graph path orders-api database --direction=both --edge=CALLS,READS --max-depth=6 --limit=5
""",
    "view": r"""
graph view - Generate an interactive HTML visualization

USAGE
  graph view [--no-open]

OPTIONS
  --no-open   Write the file but do not open the system browser

OUTPUT
  JSON with the absolute "path" of the page, node and edge counts, and "opened" status.

NOTES
  Writes a self-contained page to .graph/view.html (overwritten on each run). graph.json is not modified.
  Requires an initialized workspace.
  AI agents and headless environments: pass --no-open.

EXAMPLES
  graph view
  graph view --no-open
""",
}

# Entries are written with leading/trailing newlines for readability; strip them here.
HELP_TEXTS = {name: text.strip("\n") for name, text in _RAW.items()}
