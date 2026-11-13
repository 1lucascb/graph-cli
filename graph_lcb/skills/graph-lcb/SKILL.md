---
name: graph-lcb
description: Use the `graph` CLI (graph-lcb) to build, validate, and query typed, evidence-backed knowledge graphs stored in a local `.graph/` workspace. Make sure to use this skill whenever the user mentions graph-lcb, the `graph` command, a `.graph/` folder, graph.json, entity or edge contracts, JSONL batch imports, or wants to map, model, explore, or query a codebase, multiple repositories, documents, systems, or any domain as a graph with nodes and edges, even if they never name the tool. Also use it for searching or traversing an existing graph, finding paths or dependencies between nodes, creating or changing contracts, and importing records in bulk. Also use it to continue an unfinished mapping or to keep a graph current after its sources change.
---

# graph-lcb

`graph` is a local command-line tool that manages a JSON-backed graph with **user-defined entity and edge types** (contracts), **typed properties**, and **evidence** attached to nodes and edges. Everything lives in `.graph/` under the current working directory. There is no server and no database.

This file is the index. Read it fully, then open only the reference file that matches the task.

## Mental model

- **Nodes** are things (an API, a document, a repository). Each has a unique `id`, a `name`, a `type`, optional `description`, typed `properties`, and `evidences`.
- **Edges** are directed relationships (`orders-api CALLS stock-api`). Each has a generated UUID, a `type`, `source`, `target`, optional `description`, `properties`, and `evidences`.
- **Contracts** (`.graph/entities.json`, `.graph/edges.json`) define which types exist, which properties they allow, and which node types an edge may connect. Every write is checked against them.
- **Evidence** is a list of free-form objects recording where a fact came from. The CLI does not enforce its shape, so follow the convention below.

## How to work (read this first)

Four habits make graphs built with this tool precise and trustworthy:

1. **Fit the contract to the domain.** If the graph is new (empty contracts, or only a template applied), do not start adding records. Build the contract with the user, or from what you observe in the environment (a codebase, documents, research material). Templates (`graph init --template=...`) are a base to adapt, never a definitive contract. See `references/contracts.md`.
2. **Look for relationships exhaustively, and be granular.** Two nodes can be linked by more than one edge (different types, or the same type with different properties). Go as fine as the sources support, add node and edge types when they sharpen retrieval, and record every relationship you can prove. See `references/mapping.md`, sections 8 and 9.
3. **Work incrementally and append-only.** Mapping goes through numbered JSONL batch files that are never edited after import. After every batch, update `batches/PROGRESS.md` with what is covered, what is not covered yet, and the exact next step, so anyone can resume where you stopped. See `references/mapping.md`, section 3, and `references/batch_imports.md`.
4. **Evidence and properties are the heart of retrieval.** Every node and edge gets evidence (where the fact came from) and every property the sources support (what makes it filterable). See "Evidence and properties" below.

## Start here

| Situation | First moves |
| --- | --- |
| New graph (empty contracts or only a template, no records) | `graph contract --compact`, observe the environment, build or adapt the contract, propose it to the user, then map (`contracts.md`, `mapping.md`) |
| Continuing a mapping | Read `batches/PROGRESS.md`, run `graph validate` and `graph status`, continue at "Next step" (`mapping.md`, section 3) |
| Answering questions from an existing graph | `graph contract --compact`, `graph status`, then `query.md` |
| Sources changed since the graph was mapped | `maintenance.md` |

## Which file to read

| If the task is... | Read |
| --- | --- |
| Answering questions from an existing graph, tracing dependencies, finding paths, being precise with filters | [references/query.md](references/query.md) |
| Looking for a phrase when you don't know where it lives (names, descriptions, evidence text, file paths) | [references/search.md](references/search.md) |
| Loading many nodes and edges, preparing JSONL, dry runs, conflicts, handing work between agents | [references/batch_imports.md](references/batch_imports.md) |
| Building a contract for a new graph (with the user or from observation), adapting a template, extending the contract, or fixing a graph that stopped validating | [references/contracts.md](references/contracts.md) |
| Mapping a codebase, documents, research material, or many repositories into the graph; resuming an unfinished mapping; finding more relationships; deciding granularity | [references/mapping.md](references/mapping.md) |
| Keeping the graph current after code or documents change, finding stale evidence, refreshing or deleting outdated records, auditing a graph's accuracy | [references/maintenance.md](references/maintenance.md) |

Several tasks usually combine: mapping uses contracts first, then batch imports, then query to verify, and maintenance later to keep the graph current. Read the files in that order when starting a new graph.

## Golden rules

1. **Check the contract before anything else.** Run `graph contract --compact`. Never guess type or property names. It works even before `graph init`. **If the graph is new, build or adapt the contract first** (with the user, or from what you observe), and only then add records. Templates are a base, not the answer.
2. **Run from the right directory.** The workspace is resolved from the current working directory, not from where the CLI is installed. Confirm `.graph/` exists in the project you mean to use.
3. **Do not hand-edit `graph.json`.** Write through the CLI (`add-node`, `add-edge`, `edit`, `import`). Contracts are the only files meant to be edited by hand.
4. **Every record gets evidence and properties.** Evidence says where a fact came from, and properties make records filterable. A node or edge with neither is hard to trust and hard to find.
5. **Look for all the relationships.** Two nodes can have several edges: use different edge types, or the same type with different properties and a description. Be granular, and add node and edge types when they sharpen retrieval.
6. **Map in append-only JSONL batches and keep the ledger.** Numbered files in `batches/`, never edited after import, incremental, one coherent area or pass per file. Update `batches/PROGRESS.md` after every batch and before stopping: covered, not covered yet, next step.
7. **Validate before you trust.** Use `graph import FILE --dry-run` before every import and `graph validate` after contract changes.
8. **Prefer `import` over many `add-*` calls.** One atomic batch is faster, safer, and cheaper than dozens of single commands.
9. **One writer at a time.** There is no file locking. Never run two commands that write to the graph in parallel (including two imports from different agents).
10. **Be exhaustive in looking and strict in recording.** Search hard for relationships and details, but record only what you actually read. If something is only a suspicion, put it under "to verify" in the ledger.
11. **Keep output small.** Use `--fields`, `--limit`, and narrow filters. Avoid `graph nodes` with no filters on a large graph.
12. **Commit or back up before bulk changes.** There is no undo command. `git commit` the `.graph/` and `batches/` folders before large imports or deletes.

## Evidence and properties

These two are what make retrieval precise: evidence answers "how do we know?", and properties answer "which ones match?".

### Evidence
Evidence objects are **free-form**, but use these fields consistently so the graph stays searchable and comparable across agents:

```json
{"source": "services/orders/src/api.py", "locator": {"start_line": 12, "end_line": 28}, "note": "Route handler for POST /orders"}
```

| Field | Meaning |
| --- | --- |
| `source` | Path relative to the workspace root, or a URL. Required in practice. |
| `locator` | Where inside the source: `start_line`/`end_line` for code, `section` or `page` for documents. |
| `note` | One short sentence on what this evidence shows. |
| `commit` | Optional. Commit hash the evidence was read at, useful for spotting stale evidence later. |

Use several evidences for important records (for example the call site and the config that sets the URL).

### Properties
- Fill **every property the contract defines that the sources support**. They are what `--p.KEY=VALUE` and `--properties` filter on later.
- Put stable, filterable facts in properties (language, version, environment, protocol, method) and explanations in `description`.
- Do not guess values. Leave optional properties out when the sources do not say. If you keep needing a property the contract lacks, add it to the contract (`references/contracts.md`).

### Quality bar
A node has a recognizable `name`, a short `description`, its supportable properties, and at least one evidence. An edge has a `description` explaining why it exists, its supportable properties, and at least one evidence. Details are in `references/mapping.md`, section 6.

## Quick start

```sh
graph init --template=codebase               # a base contract to adapt (list them: graph init --list-templates)
graph init                                   # or: empty contracts to define yourself
graph contract --compact                     # see available types and properties; adapt them to the domain first
# after the contract fits the domain, add records (examples below assume an API type and a CALLS edge type):
graph add-node orders-api "Orders API" API --p.language=Python
graph add-node stock-api "Stock API" API --p.language=Go
graph add-edge orders-api CALLS stock-api --description "Checks stock" --p.call_kind=synchronous --p.protocol=HTTP
graph traverse orders-api --depth=2 --direction=out
graph status                                 # size, orphans, missing evidence
```

For anything beyond a handful of records, switch to the batch workflow in `references/batch_imports.md` and keep `batches/PROGRESS.md` up to date.

## Command cheat sheet

| Command | Purpose | Key facts |
| --- | --- | --- |
| `init [--template=NAME] [--list-templates] [--dry-run]` | Create `.graph/`, empty contracts or a template as a base, schemas | Safe to rerun; existing types are preserved; templates are a base to adapt |
| `contract [entities\|edges] [--compact]` | Show contracts | Works before init |
| `validate` | Check contracts and records | Read-only; exit 3 invalid, 4 unavailable |
| `status [--check=...] [--limit N] [--strict]` | Totals and quality findings | Orphans, missing evidence/description, components |
| `import FILE [--on-conflict=...] [--dry-run]` | Bulk load JSONL | Atomic; any invalid line aborts everything |
| `add-node ID NAME TYPE` | Create a node | ID matches `^[a-z0-9][a-z0-9._-]*$` |
| `add-edge SRC TYPE TGT` | Create an edge | Duplicates rejected; parallel edges need a description |
| `nodes [ID] [filters]` | Get or list nodes | ID lookup returns the full record |
| `edges [EDGE_ID] [filters]` | Get or list edges | Rows are `[source,type,target,target_type]` |
| `search TERM...` | Text search over nodes and edges | AND by default; supports `--regex`, `--snippets`, paging |
| `traverse NODE_ID` | Neighborhood, breadth-first | Default depth 1, direction `both` |
| `path SRC TGT` | Simple paths between two nodes | Default direction `out`, default limit 1 |
| `edit node\|edge ...` | Update in place | IDs, types, endpoints are immutable |
| `delete node\|edge ...` | Remove | Deleting a node also deletes its edges |
| `view [--no-open]` | Generate `.graph/view.html` | Use `--no-open` when headless |
| `help [COMMAND]` | Technical guide for one command | Reads no graph files |

## Output and exit codes

Default output is compact single-line JSON. Lists come back as `{"rows":[...],"total":N,"truncated":bool}`. `total` is counted before `--limit`, so `truncated:true` means you are not seeing everything.

| Code | Meaning |
| --- | --- |
| `0` | Success (`validate` valid; `status --strict` without findings) |
| `2` | Usage or operation error: bad arguments, invalid data, missing workspace, ambiguous edge delete |
| `3` | Record not found, `validate` found violations, or `status --strict` found findings |
| `4` | `validate` could not run (workspace or files unavailable or unreadable) |

When a command fails, read the JSON error first. It usually names the exact problem (unknown property, wrong type, missing required property, unknown endpoint).

## Common pitfalls

- **Rows are positional tuples.** An edge row is `[source, type, target, target_type]`. Use `--fields=id,type,source,target,description` when you need edge IDs or descriptions.
- **Edge IDs are generated.** You cannot choose them. To edit or delete one edge precisely, list it with `--fields=id,...` first.
- **Immutable fields.** Node/edge IDs, types, and edge endpoints cannot be edited. To change them, delete and recreate.
- **`--properties` replaces everything; `--p.KEY` updates one key.** On `edit`, `--properties '{"a":1}'` drops all other properties.
- **`--evidences` always replaces the whole list.** To add one evidence, read the current list, append, and write it back.
- **Missing `graph.json` is normal** right after `graph init`. It is created on the first write.
- **Templates are a base, not a definitive contract.** Review the template, compare it with what you observe in the environment, and adapt it (add, remove, rename types and properties) before adding records. Template types can require properties, so records cannot have empty `properties` until the contract fits.
- **Stopping at one edge per pair of nodes.** Look for every other relationship between connected nodes (other edge types, reverse direction, same type with different properties).
- **Stopping a mapping without writing the ledger.** Update `batches/PROGRESS.md` before you stop, or the next agent cannot tell what is covered.
- **Contracts support only `string`, `number`, `integer`, `boolean`.** No arrays or nested objects in properties. Put structured data in `evidences`, or split it into extra nodes.

## Getting help from the CLI itself

`graph help COMMAND` prints a precise guide with options, output shape, and examples. Prefer it over guessing flags.