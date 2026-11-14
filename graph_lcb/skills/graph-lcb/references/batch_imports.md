# Batch imports

Use this reference whenever importing more than a handful of records, preparing graph data for another agent, or building the graph through an auditable and repeatable process.

Batch imports are the standard way to write graph data. They provide atomic validation, reviewable changes, and a permanent history of how the graph was built.

## Contents

1. Why batch imports
2. Record format
3. Writing good records
4. Standard import workflow
5. Conflict modes
6. Append-only batch history
7. Handoff between agents
8. Concurrency and safety
9. Reading errors
10. Worked example
11. Checklist

## 1. Why batch imports

Batch imports provide several guarantees and practical advantages:

- **Atomic.** The entire file is parsed and validated against the contract and existing graph before any changes are written. One invalid record aborts the import.
- **Order-free.** Nodes are staged before edges, so an edge can reference a node appearing later in the same file.
- **Reviewable.** JSONL files can be read, diffed, committed, and handed to another agent.
- **Efficient.** One import command replaces many individual `add-node` and `add-edge` calls.
- **Incremental.** Numbered batches build the graph step by step and leave a history that can be reviewed or resumed.

For the broader mapping methodology and progress ledger, see `mapping.md`.

## 2. Record format

A batch is a JSONL file: **one JSON object per line**.

Do not wrap records in an array, add commas between lines, or pretty-print individual records across multiple lines.

Example:

```jsonl
{"kind":"node","id":"web-api","type":"API","name":"Web API","description":"Public gateway","properties":{"language":"Python"},"evidences":[{"source":"web/app.py","locator":{"start_line":1,"end_line":40},"note":"Entry point"}]}
{"kind":"node","id":"billing-api","type":"API","name":"Billing API","description":"Handles billing requests","properties":{"language":"Python"}}
{"kind":"edge","type":"CALLS","source":"web-api","target":"billing-api","description":"Requests payment processing.","properties":{"protocol":"HTTP"},"evidences":[{"source":"web/clients/billing.py","locator":{"start_line":10,"end_line":30}}]}
```

### Record rules

- `kind` is optional. Records containing `source` or `target` are interpreted as edges; other records are interpreted as nodes. Include `kind` anyway for readability.
- Edge `id` may be omitted when **creating** an edge; the importer then generates it. Do not invent IDs for new edges. When **updating** an existing edge with `--on-conflict=replace`, include its existing `id` (fetch it with `graph edges ... --fields=id,...`). Without it, the record is matched by type, endpoints, and properties, so a changed property creates a duplicate instead of an update. Never change `type`, `source`, or `target` of an existing `id`: delete and recreate.
- Node `id` must match:
  ```regex
  ^[a-z0-9][a-z0-9._-]*$
  ```
- `type` must exist in the active contract.
- Property names and value types must match the contract. Required properties must be present.
- `properties` accepts only `string`, `number`, `integer`, and `boolean` values, and only keys defined in the contract.
- `evidences` must follow the convention in `SKILL.md`: `source`, `locator`, `note`, and optional `commit`.
- Use `-` as the filename to read JSONL from stdin:
  ```sh
  cat records.jsonl | graph import -
  ```

## 3. Writing good records

### Stable identity

Node IDs identify entities across imports. Generate them deterministically, for example:

```text
<repo>.<component>
```

Never derive IDs from timestamps, random values, or source line numbers. See `mapping.md` for the full naming convention.

### One fact, one record

- Do not represent the same entity under multiple IDs.
- Do not repeat the same relationship.
- Search the graph for existing entities before creating new ones, especially shared resources.

### Batch organization

There is no fixed batch size limit.

- Split batches by repository, area, mapping pass, or document.
- Keep each file coherent and easy to review.
- Several hundred records or more in one file is normal for a large area. Do not split files into tiny pieces just to reduce their size.
- Avoid mixing unrelated areas in one batch.
- A single invalid line aborts the import, but the dry run reports all detected errors with line numbers. Fix them together and rerun.

### Evidence and properties

- Include evidence on every record whenever possible. Missing evidence can be detected with:
  ```sh
  graph status --check=no-evidence
  ```
- Populate every property supported by the sources and defined in the contract.
- Evidence must point to the actual source of the claim, not merely a related folder or file.
- Do not invent values to satisfy required properties. Revisit the contract if a required value cannot be established.

### Relationships

- Record every distinct relationship supported by evidence.
- The same pair of nodes can have multiple edge types.
- Multiple edges with the same type and endpoints require different properties and a non-empty description for each.
- Add descriptions to all edges, not only additional edges between the same endpoints.

A duplicate is determined by the same edge type, endpoints, and properties. Changing only the description does not create a distinct edge.

See `mapping.md`, section 8, for the relationship discovery process.

### Validate generated JSONL

If a script generates the file, validate JSON syntax before invoking the CLI:

```sh
python -c "import json,sys; [json.loads(l) for l in open('file.jsonl')]"
```

This catches malformed JSON independently of contract validation.

## 4. Standard import workflow

Follow this process for every batch.

### 1. Inspect the workspace and contract

```sh
graph contract --compact
graph status
```

Confirm that all node types, edge types, properties, and required fields in the batch exist in the active contract.

### 2. Create a recovery point

Prefer committing the graph before importing:

```sh
git add .graph
git commit -m "Checkpoint graph before batch import"
```

Alternatively, copy the graph file:

```sh
cp .graph/graph.json .graph/graph.json.bak
```

Skip the copy if `graph.json` does not exist yet.

### 3. Write the batch file

Use the JSONL format in section 2. Keep the batch focused on one coherent unit of work.

### 4. Dry-run the import

```sh
graph import batches/0001-orders.jsonl --dry-run
```

Inspect:

- `summary.created`
- `summary.updated`
- `summary.unchanged`
- `summary.errors`

The counts must match your expectations.

For example, if you expected 40 new nodes and 55 new edges but the dry run reports `created: 0`, investigate before proceeding. You may be encountering unexpected conflicts or incorrect IDs.

### 5. Fix errors

Resolve all reported errors and repeat the dry run until:

```json
{
  "valid": true,
  "errors": []
}
```

Do not proceed while errors remain.

### 6. Import for real

```sh
graph import batches/0001-orders.jsonl
```

### 7. Verify the graph

```sh
graph validate
graph status --check=orphans,no-evidence --limit=10
```

### 8. Spot-check records

Inspect two or three records using:

```sh
graph nodes ID
```

Confirm that the records exist and their evidence points to real files and relevant lines or sections.

### 9. Update the progress ledger

Update `batches/PROGRESS.md` with:

- What the batch covered.
- What remains uncovered.
- The batch filename.
- Updated graph totals from `graph status`.
- The exact next step.

For the ledger format and resumption procedure, see `mapping.md`, section 3.

## 5. Conflict modes

The `--on-conflict` option determines how incoming records are handled when they match existing graph data.

| Mode              | Behavior                                                                                      | Appropriate use                                 |
| ----------------- | --------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| `error` (default) | Report the conflict and abort the import                                                      | First import or when conflicts should not exist |
| `skip`            | Preserve the existing record and ignore the incoming one                                      | Adding missing records when overlap is expected |
| `replace`         | Update the existing record if its content differs; identical records are counted as unchanged | Correcting records or refreshing evidence       |

### What counts as a conflict?

- **Nodes:** same node ID.
- **Edges:** matched by edge ID first. A record without an ID (or with an unknown one) is matched by type, endpoints, and properties. Because properties are part of that fallback match, an ID-less record whose properties changed does **not** match and is created as a new edge.

A semantic replacement keeps the existing edge ID.

### Choosing a mode safely

- Always dry-run using the same conflict mode you intend to use for the actual import.
- `--on-conflict=replace --dry-run` shows how many records would change.
- `replace` overwrites the existing record with the incoming content. If the incoming record omits existing evidence or properties, those values may be lost. Supply complete records when replacing.
- To change an edge's properties with `replace`, send its existing `id` (or use `graph edit edge`). In the dry run, `created` must count only genuinely new records; if it counts edges you meant to update, they are missing their IDs.
- `skip` silently preserves existing records, including incorrect ones. Use it to add missing records, not to correct existing data.

## 6. Append-only batch history

The batch directory is the permanent, reviewable history of how the graph was built. The graph represents the current state; the batches explain how it got there.

Recommended layout:

```text
.graph/
  graph.json

batches/
  0001-initial-inventory.jsonl
  0002-orders-edges.jsonl
  0003-fix-billing-evidence.jsonl
  PROGRESS.md
```

### Rules

1. **Never edit an imported batch.** Treat imported files as immutable.
2. **Add new numbered files.** Each new mapping unit gets a new batch instead of rewriting an earlier one.
3. **Corrections require new batches.** Use `--on-conflict=replace` with complete records (edge records carry their existing `id`). The history then shows what changed.
4. **Additions can use `skip`.** Use it when overlap with earlier batches is possible and existing records should be preserved.
5. **Keep numbering sequential and obvious.** Use prefixes such as `0001-`, `0002-`, and `0003-`.
6. **Do not append corrections to old files.** If a single ledger file is unavoidable, append only brand-new IDs and never repeat IDs already present. Dry-run before importing. Prefer separate files.
7. **Record deletions.** Use `graph delete` for deletions and document them in `batches/PROGRESS.md` under `Deletions and manual edits`. Replaying the batches alone would otherwise recreate deleted records.
8. **Update the progress ledger after every batch and before stopping.** Mark files that were written but not imported.
9. **Commit batches together with `.graph/`.** The batch files explain the graph's history; the graph contains its current state.

## 7. Handoff between agents

Use this process when one agent investigates sources and another imports the data, or when several agents map different repositories in parallel.

### Roles

- **Producers:** one or more agents that inspect sources and write batch files. They do not run `graph import`.
- **Importer:** exactly one agent that validates and imports the batch files sequentially.

### Producer requirements

Each producer must:

1. Read the active contract and use only defined types and properties. If a new type or property is needed, stop and report it instead of inventing one.
2. Write to its own file:
   ```text
   batches/<seq>-<scope>.jsonl
   ```
   Example:
   ```text
   batches/0004-repo-orders.jsonl
   ```
3. Prefix node IDs with its assigned scope, such as `orders.*`, to prevent collisions.
4. Include evidence on every record.
5. Run `graph import FILE --dry-run` only when it has a graph copy that cannot be modified by other agents. Otherwise, skip the dry run because its results may become stale before the final import.
6. Leave a handoff note describing coverage, remaining work, assumptions, and the exact stopping point.

### Handoff note template

```text
Batch: batches/0004-repo-orders.jsonl
Scope: repository "orders" at commit abc1234

Contents:
38 nodes (API 6, WORKER 2, DATASTORE 3, ...)
71 edges (CALLS 40, READS 21, ...)

Depends on:
Nodes from 0001-initial-inventory.jsonl (billing-api, stock-api)

Assumptions:
<anything uncertain or requiring verification>

Covered:
<areas read completely; whether the relationship sweep was completed>

Not covered yet:
<areas not read or only partially investigated>

Stopped at:
<exact location so work can continue>

Not covered on purpose:
<what was skipped and why>

Suggested command:
graph import batches/0004-repo-orders.jsonl --on-conflict=skip
```

### Importer routine

For each batch, in sequence:

1. Read the handoff note and the active contract.
2. Run the dry run with the suggested conflict mode:
   ```sh
   graph import FILE --dry-run
   ```
3. Compare the import summary with the producer's handoff counts. Investigate mismatches before importing.
4. Import the batch.
5. Run:
   ```sh
   graph validate
   graph status --check=orphans,no-evidence
   ```
6. Record the import result, counts, producer coverage, and next step in `batches/PROGRESS.md`.

If the dry run fails, send the errors back to the producer. Errors include input line numbers when tied to a record, allowing the producer to correct the relevant lines.

## 8. Concurrency and safety

- **There is no file locking.** Concurrent imports can silently overwrite each other's changes. Imports must run sequentially.
- Dry runs are read-only and can run in parallel, but their results may become outdated after another import changes the graph.
- A failed import leaves the graph unchanged, so fixing the batch and retrying is safe.
- There is no built-in undo. If an import was incorrect, restore the backup or committed graph:
  ```sh
  git checkout -- .graph/graph.json
  ```
  Or restore the backup:
  ```sh
  cp .graph/graph.json.bak .graph/graph.json
  ```
  Then correct the batch and import again.

## 9. Reading errors

Import errors are returned as JSON with an `errors` array. When an error is associated with a record, the report includes its input line number.

| Symptom                                               | Likely cause                                                                                                        |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Invalid JSON on a line                                | Trailing comma, unescaped quote, or multi-line record                                                               |
| Unknown type                                          | Type is missing from the contract or misspelled                                                                     |
| Unknown property or wrong property type               | Property is undefined or its value has the wrong type                                                               |
| Missing required property                             | The contract marks the property as required                                                                         |
| Invalid node ID                                       | Uppercase letters, spaces, or leading `.`, `-`, or `_`                                                              |
| Edge endpoint not found                               | Source or target node is missing from both the graph and the batch                                                  |
| Edge not allowed                                      | Contract source/target constraints do not allow the endpoint types                                                  |
| Conflict                                              | Record already exists and `--on-conflict=error` is active                                                           |
| Duplicate or parallel edge                            | Same type, endpoints, and properties, or another edge between the same endpoints without a description              |
| Dry run shows `created` for edges you meant to update | The records have no `id` and a changed property, so they do not match the existing edge; add the existing edge `id` |

Fix all reported errors in one pass, then dry-run again. The importer reports detected problems together, so repeated trial-and-error should rarely be necessary.

## 10. Worked example

Assume the active contract defines:

- Node type `API`, with required property `language`.
- Edge type `CALLS`, with optional property `protocol`.

Always inspect the actual contract first:

```sh
graph contract --compact
```

Create `batches/0001-initial.jsonl`:

```jsonl
{"kind":"node","id":"orders-api","type":"API","name":"Orders API","description":"Handles order requests.","properties":{"language":"Python"},"evidences":[{"source":"orders/main.py","locator":{"start_line":1,"end_line":30},"note":"Application entry point"}]}
{"kind":"node","id":"stock-api","type":"API","name":"Stock API","description":"Provides stock availability.","properties":{"language":"Go"},"evidences":[{"source":"stock/main.go","locator":{"start_line":1,"end_line":25},"note":"Application entry point"}]}
{"kind":"edge","type":"CALLS","source":"orders-api","target":"stock-api","description":"Checks stock before confirming an order.","properties":{"protocol":"HTTP"},"evidences":[{"source":"orders/clients/stock.py","locator":{"start_line":8,"end_line":22},"note":"HTTP client call to the stock service"}]}
```

Dry-run and import:

```sh
graph import batches/0001-initial.jsonl --dry-run
# {"valid":true,"dry_run":true,"summary":{"created":3,"updated":0,"unchanged":0,"errors":0},"errors":[]}

graph import batches/0001-initial.jsonl
graph validate
```

Later, if the stock API evidence needs correction, create a new batch containing the complete corrected record and use `replace`:

```sh
graph import batches/0002-fix-stock-evidence.jsonl --on-conflict=replace --dry-run
graph import batches/0002-fix-stock-evidence.jsonl --on-conflict=replace
```

If an edge's properties changed instead (for example `protocol` from `HTTP` to `gRPC`), fetch the edge ID and include it in the corrected record. Without the `id`, the changed record would not match the existing edge and `replace` would create a second one:

```sh
graph edges --from=orders-api --to=stock-api --fields=id,type,description,properties,evidences
```

```jsonl
{"kind":"edge","id":"EXISTING-EDGE-ID","type":"CALLS","source":"orders-api","target":"stock-api","description":"Checks stock before confirming an order.","properties":{"protocol":"gRPC"},"evidences":[{"source":"orders/clients/stock.py","locator":{"start_line":8,"end_line":22},"note":"gRPC client call to the stock service"}]}
```

In the dry run, expect `updated: 1` and `created: 0`.

Do not modify `0001-initial.jsonl` after importing it.

## 11. Checklist

Before importing:

- [ ] Contract inspected; all types and properties exist.
- [ ] Node IDs are deterministic and scoped.
- [ ] Evidence and supportable properties are included.
- [ ] All evidenced relationships are represented, including multiple edges between the same nodes.
- [ ] Edges have descriptions.
- [ ] A backup or commit exists.
- [ ] Dry run returns `valid:true` with zero errors.
- [ ] Dry-run counts match expectations.
- [ ] Edge updates carry the existing edge `id`.
- [ ] Conflict mode is chosen intentionally.
- [ ] Only one importer is running.

After importing:

- [ ] `graph validate` passes.
- [ ] `graph status` has been inspected.
- [ ] A sample of records and evidence has been verified.
- [ ] The batch file is treated as immutable.
- [ ] `batches/PROGRESS.md` is updated with coverage, remaining work, totals, and the next step.