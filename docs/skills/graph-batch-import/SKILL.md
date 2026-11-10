---
name: graph-batch-import
description: Build an evidence-backed batch of graph nodes and edges in JSONL, validate it, and import it atomically only after the batch is complete. Use when mapping a codebase, system, organization, or other domain into a graph.
---

# Graph Batch Import

Use this workflow to build a detailed graph from available sources while
keeping graph changes append-only. Gather and verify evidence first, record all
proposed nodes and edges in one JSONL file, review and dry-run the file, then
perform one import after the batch is ready. Do not add or edit graph records
while evidence gathering or batch construction is in progress.

Run commands from the project directory whose `.graph/` workspace you intend
to update.

## 1. Establish scope and inspect the workspace

1. Clarify the subject, boundaries, level of detail, and source material to
   cover. Explore broadly before deciding that the map is complete.
2. Run `graph contract` and read both entity and edge definitions. Record the
   canonical type names, required properties, property types, and allowed edge
   endpoint types. Use only types and properties defined by the contract.
3. Run `graph validate` to check the existing workspace before planning the
   batch. Resolve pre-existing validation issues or report them before
   importing; the import validates the resulting graph too.
4. Explore existing records with `graph nodes`, `graph edges`, and focused
   queries. Use `graph nodes --type=TYPE`, `--contains`, `--properties`, or
   `--p.KEY=VALUE` to find likely matches. Inspect candidates with
   `graph nodes NODE_ID` and inspect their relationships with `graph edges`,
   `graph traverse`, or `graph path`.
5. Reuse an existing node when it represents the same real-world entity. Do
   not create a second ID just because a source uses an alias or alternate
   spelling. Record aliases as properties or evidence only when the contract
   provides a suitable place for them.

## 2. Explore sources and collect evidence

Search all relevant source types that are available: source code, configuration,
schemas, deployment files, documentation, APIs, issue records, and other
authoritative material. Follow references between sources and inspect
surrounding context instead of relying on a single search hit. For a codebase,
trace entry points, callers, callees, data stores, queues, external APIs,
configuration, deployment units, and ownership boundaries as far as evidence
supports them.

For each proposed node and edge:

- Attach evidence that supports its existence and its important details.
- Prefer precise locators: repository-relative file path plus line range or
  symbol, URL plus section, schema path, API operation, or another stable
  reference. Include a short note explaining what the source establishes.
- Use evidence objects such as
  `{"source":"src/orders/client.py","locator":{"start_line":20,"end_line":35},"note":"Calls the stock lookup API."}`.
  Evidence object fields are user-defined; keep a consistent `source`,
  `locator`, and `note` structure when useful.
- Separate direct facts from inferences. Label an inference in the evidence
  note and include the sources behind it. Do not turn guesses into graph facts.
- Capture conflicting evidence instead of silently choosing one account. Add a
  note that explains the conflict and what remains uncertain.
- Avoid unsupported detail. A relationship should have evidence for its
  direction and meaning, not merely evidence that both endpoints exist.

Keep exploring until the agreed scope has been covered or additional detail is
not supported by the available sources. Prefer a well-connected map with
evidence-backed detail over a short list of top-level components. Include
important dependencies, data flows, ownership, runtime or deployment roles,
interfaces, constraints, and failure or trust boundaries when the sources and
contract support them.

## 3. Plan IDs and relationships

Before writing JSONL, make a working inventory of the candidate records:

- Choose stable, descriptive node IDs using lowercase letters, digits, `.`, `_`,
  or `-`; IDs must match `^[a-z0-9][a-z0-9._-]*$`.
- Record each node's canonical contract type, display name, optional
  description, contract-valid properties, and evidence.
- Check each edge's canonical type and verify that its source and target node
  types are allowed by the edge contract.
- Give edges meaningful descriptions, especially when several relationships
  connect the same nodes. Record evidence for each distinct relationship.
- Check whether the same entities or relationships are already present. The
  default import conflict policy is `error`; an existing node ID or an edge
  with the same type, endpoints, and properties is a conflict.

Use JSON values that satisfy the contract exactly: strings, numbers, integers,
and booleans are distinct. Put properties inside the `properties` object; do
not use CLI `--p.*` flags in the JSONL file.

## 4. Build one append-only JSONL batch

Create a single `.jsonl` artifact for the import. Write one complete JSON object
per line, without a surrounding array or trailing commas. Put nodes before
edges for readability, although the importer stages nodes first automatically.
The optional `kind` field can be `"node"` or `"edge"`; omit it only when the
record shape makes the kind clear (`source` or `target` implies an edge).

Example node:

```json
{"kind":"node","id":"orders-api","type":"API","name":"Orders API","description":"Accepts and routes order requests.","properties":{"language":"Python"},"evidences":[{"source":"src/orders/api.py","locator":{"start_line":12,"end_line":28},"note":"Defines the order API routes."}]}
```

Example edge:

```json
{"kind":"edge","type":"CALLS","source":"orders-api","target":"stock-api","description":"Checks stock availability before confirming an order.","properties":{"protocol":"HTTP"},"evidences":[{"source":"src/orders/stock_client.py","locator":{"start_line":20,"end_line":35},"note":"Sends the stock lookup request."}]}
```

An edge will be automatically generated by the importer. Keep the batch
append-only while gathering records: do not apply individual graph mutations
or incrementally import partial batches. If a record needs correction, revise
the batch artifact before the final import and re-run the dry-run.

## 5. Review and dry-run the complete batch

Review the JSONL artifact line by line. Check that every record has the
intended type, stable ID, valid properties, evidence, and correct endpoints.
Check that every edge source and target is either already in the graph or
represented by a node in this batch. Confirm evidence coverage and detail for
the whole agreed scope.

Run the dry-run with the default conflict policy first:

```sh
graph import batch.jsonl --dry-run
```

For standard append-only work, keep `--on-conflict=error` (the default). Use
`--on-conflict=skip` only when intentionally keeping existing records unchanged.
Use `--on-conflict=replace` only when overwriting matching records is part of
the requested task; node conflicts match by ID and edge conflicts match by ID
or by type, endpoints, and properties. Do not use replacement as a shortcut
for avoiding evidence review.

Inspect the JSON result:

- `valid` must be true and `errors` must be empty.
- Review the `created`, `updated`, and `unchanged` counts. Under the default
  conflict policy, `updated` and `unchanged` should normally be zero.
- Resolve every line-numbered parse, conflict, contract, or endpoint error in
  the batch, then dry-run the complete batch again. Dry-run does not write to
  the graph.

## 6. Import once, then verify

Only after evidence gathering, record construction, review, and dry-run are
complete, run the real import once:

```sh
graph import batch.jsonl
```

Use the same conflict policy that passed the dry-run. Import validates the
combined graph and writes it atomically; if any input or graph validation error
remains, it writes none of the batch. Confirm the success summary, then run
`graph validate` and inspect representative nodes, edges, and neighborhoods to
confirm the imported graph reflects the evidence and intended coverage.

