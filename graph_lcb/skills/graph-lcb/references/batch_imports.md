# Batch imports

Use this file whenever you load more than a handful of records, prepare data for another agent, or need an auditable, repeatable way to build the graph.

## Contents
1. Why batch imports
2. Record format
3. Writing good records
4. The standard workflow
5. Conflict modes
6. Keeping the batch history append-only
7. Handoff between agents
8. Concurrency and safety
9. Reading errors
10. Worked example
11. Checklist

## 1. Why batch imports

- **Atomic.** The whole file is parsed and validated against the contracts and the existing graph before anything is written. One bad line aborts everything, so you never end up with half an import.
- **Order-free.** Nodes are staged before edges, so an edge may reference a node that appears later in the file.
- **Reviewable.** A JSONL file can be read, diffed, committed, and handed to someone else.
- **Cheap.** One command instead of dozens of `add-node` / `add-edge` calls.
- **Incremental.** Numbered batches, one per area or pass, each imported and verified, build a graph step by step and leave a trail that others can resume (mapping.md, section 3).

## 2. Record format

One JSON object per line. No commas between lines, no wrapping array, no pretty-printing.

```jsonl
{"kind":"node","id":"web-api","type":"API","name":"Web API","description":"Public gateway","properties":{"language":"Python"},"evidences":[{"source":"web/app.py","locator":{"start_line":1,"end_line":40},"note":"Entry point"}]}
{"kind":"node","id":"billing-api","type":"API","name":"Billing API","properties":{"language":"Python"}}
{"kind":"edge","type":"CALLS","source":"web-api","target":"billing-api","description":"Requests payment processing.","properties":{"protocol":"HTTP"},"evidences":[{"source":"web/clients/billing.py","locator":{"start_line":10,"end_line":30}}]}
```

- `kind` is optional. Records with `source` or `target` are edges; everything else is a node. Write `kind` anyway for readability.
- Edge `id` may be omitted and is then generated. Do not invent edge IDs.
- Node `id` must match `^[a-z0-9][a-z0-9._-]*$`.
- `type` must exist in the contracts. Property keys and types must match the contract, and required properties must be present.
- `"properties"` can only hold `string`, `number`, `integer`, `boolean` values (and only keys defined in the contract).
- `evidences` is an array of objects. Follow the convention in SKILL.md (`source`, `locator`, `note`, optional `commit`).
- Read from stdin with `-` as the file name: `cat records.jsonl | graph import -`.

## 3. Writing good records

- **Stable IDs.** IDs are the identity of a node across re-imports. Derive them deterministically (for example `<repo>.<component>`), never from timestamps or random values. See mapping.md for conventions.
- **One fact, one record.** Do not duplicate a node under two IDs; do not repeat the same edge.
- **Batch size.** There is no size limit. Split files by area, pass, or document so each one is easy to track and review. Several hundred records or more per file is normal for a large area, so do not cut files into tiny pieces, and do not mix unrelated areas into one file. In a large file one bad line still aborts the import, but the dry run lists every error with its line number, so fix them all in one pass and rerun.
- **Evidence on everything.** Missing evidence shows up later in `graph status --check=no-evidence`.
- **Properties filled in.** Include every property the sources support. Properties are what make records findable with `--p.KEY` filters.
- **All the relationships you can prove.** Two nodes can have several edges (different types, or the same type with different properties and a description). Do not stop at the first one (mapping.md, section 8).
- **Descriptions on edges.** If two edges share endpoints, every additional one needs a non-empty description. Writing a description on every edge avoids the problem.
- **Duplicates.** Same type + endpoints + properties is a duplicate even if descriptions differ, and is a conflict on import.
- **Validate JSON yourself first** if you generate it with a script: `python -c "import json,sys; [json.loads(l) for l in open('file.jsonl')]"` catches syntax slips before the CLI does.

## 4. The standard workflow

1. **Check the workspace and contracts.**
   ```sh
   graph contract --compact
   graph status
   ```
2. **Back up.** `git commit` the `.graph/` folder, or copy it: `cp .graph/graph.json .graph/graph.json.bak` (skip if `graph.json` does not exist yet).
3. **Write the batch file** (see sections 2 and 3).
4. **Dry run.**
   ```sh
   graph import batches/0001-orders.jsonl --dry-run
   ```
   Read `summary.created`, `updated`, `unchanged`, and `errors`. **The numbers must match your expectation.** If you meant to add 40 nodes and 55 edges but see `created: 0`, something is wrong (probably conflicts you did not intend).
5. **Fix errors and repeat** until `valid:true` with zero errors.
6. **Import for real.**
   ```sh
   graph import batches/0001-orders.jsonl
   ```
7. **Verify.**
   ```sh
   graph validate
   graph status --check=orphans,no-evidence --limit=10
   ```
8. **Spot-check** two or three records with `graph nodes ID`, and confirm evidence points at real files and lines.
9. **Update `batches/PROGRESS.md`**: what this batch covered, what is still not covered, totals from `graph status`, and the exact next step.

## 5. Conflict modes

`--on-conflict` controls what happens when an incoming record matches existing data.

| Mode | Behavior | Use when |
| --- | --- | --- |
| `error` (default) | Report the conflict and abort the whole import | First import, or when conflicts should be impossible |
| `skip` | Keep the existing record, ignore the incoming one | Re-running a batch safely; adding only what is new |
| `replace` | Update the existing record if content differs; identical content is counted as `unchanged` | Correcting records or refreshing evidence |

What counts as a conflict:
- **Nodes:** same node ID.
- **Edges:** same edge ID, or same type + endpoints + properties. A semantic replacement keeps the existing edge ID.

Guidance:
- Always dry-run with the mode you intend. `--on-conflict=replace --dry-run` tells you exactly how many records would change.
- `replace` overwrites the record's content with what is in your file. If your file has partial data (missing evidence, missing properties), you will erase what was there. Include complete records when replacing.
- `skip` hides mistakes: a corrected record in your file will be silently ignored. Use it for "add what is missing", not for fixes.

## 6. Keeping the batch history append-only

Goal: the sequence of batch files is a permanent, reviewable ledger of how the graph was built, and `batches/PROGRESS.md` says what each file covered and what is still missing.

Recommended layout:

```text
.graph/
  graph.json
batches/
  0001-initial-inventory.jsonl
  0002-orders-edges.jsonl
  0003-fix-billing-evidence.jsonl
  PROGRESS.md            # coverage ledger: covered, not covered yet, next step (template in mapping.md, section 3)
```

Rules:
1. **Never edit a batch file after it was imported.** Treat it as immutable. This is what append-only means here: history only grows by adding new files.
2. **Work incrementally.** Add a new numbered batch per area or pass instead of rewriting earlier ones.
3. **Corrections are new batch files**, imported with `--on-conflict=replace` (with complete records). The history then shows what changed and why.
4. **Additions are new batch files**, imported with `--on-conflict=skip` if overlap with earlier batches is possible.
5. **Number the files** (`0001-`, `0002-`) so the order is obvious.
6. **Do not append corrections to an old file.** If you must keep a single ledger file, append only brand-new IDs, never repeat an ID that already appears in the file, and always dry-run first. (Duplicate IDs inside one file are better avoided than relied upon.)
7. **Deletions** are done with `graph delete`. Record them in `batches/PROGRESS.md` (section "Deletions and manual edits") so the history stays truthful, because a replay of the batches alone would resurrect deleted records.
8. **Update `batches/PROGRESS.md` after every batch**, and before stopping. If a file is written but not imported yet, mark it "written, not imported".
9. **Commit batches together with `.graph/`.** The batch files are the "why", the graph is the "what".

## 7. Handoff between agents

Use this when one agent gathers data and another one imports, or when several agents map different repositories in parallel.

### Roles
- **Producers** (one or many) read sources and write batch files. They do **not** run `graph import`.
- **The importer** (exactly one) validates and imports the files, one at a time.

### Producer contract
Each producer must:
1. Read `graph contract` and use only existing types and properties. If a new type is needed, stop and report it instead of inventing one.
2. Write to its own file: `batches/<seq>-<scope>.jsonl`, for example `0004-repo-orders.jsonl`.
3. Prefix node IDs with its scope (for example `orders.*`) so parallel producers cannot collide. See mapping.md.
4. Include evidence on every record.
5. Run `graph import FILE --dry-run` **only if** a graph copy is available that cannot be written by others, otherwise skip it. (Dry runs do not write, but they read the shared graph, so results can differ from the final import.)
6. Leave a short handoff note next to the file, including what was covered, what was not, and where it stopped.

### Handoff note template
```text
Batch: batches/0004-repo-orders.jsonl
Scope: repository "orders" at commit abc1234
Contents: 38 nodes (API 6, WORKER 2, DATASTORE 3, ...), 71 edges (CALLS 40, READS 21, ...)
Depends on: nodes from 0001-initial-inventory.jsonl (billing-api, stock-api)
Assumptions: <anything guessed or uncertain>
Covered: <areas read completely, relationship sweep done or not>
Not covered yet: <areas not read, or read only partially>
Stopped at: <exact place, so work can continue>
Not covered on purpose: <what was skipped and why>
Suggested command: graph import batches/0004-repo-orders.jsonl --on-conflict=skip
```

### Importer routine
For each batch, in order:
1. Read the handoff note and the contract.
2. `graph import FILE --dry-run` with the suggested conflict mode.
3. Compare the `summary` counts to the note. Investigate any mismatch before importing.
4. Import.
5. `graph validate` and `graph status --check=orphans,no-evidence`.
6. Record the result (counts, command) and the producer's coverage notes in `batches/PROGRESS.md`.

If the dry run fails, send the error list back to the producer. Because errors include the input line number, the producer can fix exactly those lines.

## 8. Concurrency and safety

- **There is no file locking.** Two simultaneous writes can silently lose one update. Imports from different agents must run **sequentially**.
- Dry runs are read-only and safe to run in parallel with each other, but their counts can become outdated once another import lands.
- A failed import leaves the graph untouched, so retrying is always safe.
- There is no undo. If an import was a mistake, restore the backup (`git checkout .graph/graph.json` or copy back `graph.json.bak`) and fix the batch.

## 9. Reading errors

Import errors come back as JSON with an `errors` array, and the input line number when tied to a record. Typical causes:

| Symptom | Likely cause |
| --- | --- |
| Invalid JSON on a line | Trailing comma, unescaped quote, multi-line record |
| Unknown type | Type missing in the contract, or misspelled |
| Unknown property / wrong property type | Property not defined in the contract, or a number sent as a string |
| Missing required property | Contract marks it required |
| Invalid node ID | Uppercase letters, spaces, or leading `.`/`-`/`_` |
| Edge endpoint not found | Source or target node is neither in the graph nor in the same file |
| Edge not allowed | Contract `source`/`target` lists do not include these node types |
| Conflict | Record already exists and `--on-conflict=error` is active |
| Duplicate / parallel edge | Same type, endpoints, and properties; or a second edge between the same endpoints without a description |

Fix all errors listed in one pass, then dry-run again. The report lists every detected problem, so you rarely need many rounds.

## 10. Worked example

Example contract: node type `API` with required `language`; edge type `CALLS` with optional `protocol`. (Your contract will differ; read it with `graph contract --compact` first.)

`batches/0001-initial.jsonl`
```jsonl
{"kind":"node","id":"orders-api","type":"API","name":"Orders API","properties":{"language":"Python"},"evidences":[{"source":"orders/main.py","locator":{"start_line":1,"end_line":30}}]}
{"kind":"node","id":"stock-api","type":"API","name":"Stock API","properties":{"language":"Go"},"evidences":[{"source":"stock/main.go","locator":{"start_line":1,"end_line":25}}]}
{"kind":"edge","type":"CALLS","source":"orders-api","target":"stock-api","description":"Checks stock before confirming an order.","properties":{"protocol":"HTTP"},"evidences":[{"source":"orders/clients/stock.py","locator":{"start_line":8,"end_line":22}}]}
```

```sh
graph import batches/0001-initial.jsonl --dry-run
# {"valid":true,"dry_run":true,"summary":{"created":3,"updated":0,"unchanged":0,"errors":0},"errors":[]}
graph import batches/0001-initial.jsonl
graph validate
```

Later correction (new file, complete records, `replace`):
```sh
graph import batches/0002-fix-stock-evidence.jsonl --on-conflict=replace --dry-run
graph import batches/0002-fix-stock-evidence.jsonl --on-conflict=replace
```

## 11. Checklist

- [ ] Contracts read; every type and property exists
- [ ] Deterministic, scoped IDs
- [ ] Evidence and supportable properties on every record
- [ ] All evidenced relationships recorded, including multiple edges between the same nodes
- [ ] Descriptions on edges
- [ ] Backup or commit made
- [ ] Dry run: `valid:true`, counts match expectations, conflict mode chosen on purpose
- [ ] Only one importer running
- [ ] `graph validate` and `graph status` after import
- [ ] Batch file frozen; `batches/PROGRESS.md` updated (covered, not covered yet, next step)