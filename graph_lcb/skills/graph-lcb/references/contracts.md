# Contracts: creating, extending, and repairing

Use this file when the contracts are empty or still the starter ones, when the user wants new types or properties, or when `graph validate` started failing after a contract change.

## Contents
1. What a contract is
2. Format and rules
3. Creating a contract from scratch
4. Design guidelines
5. Example contracts
6. Changing a contract safely
7. Change playbooks
8. Diagnosing with validate and status
9. Limits to be aware of
10. Checklist

## 1. What a contract is

Two JSON files in `.graph/` define what the graph may contain:

- `entities.json`: node types and their allowed properties.
- `edges.json`: edge types, which node types they may connect, and their allowed properties.

Every write (`add-node`, `add-edge`, `edit`, `import`) is checked against them, and `graph validate` rechecks everything. The contracts are the **only** files in `.graph/` meant to be edited by hand. `.graph/schemas/*.json` are bundled JSON Schemas that give editors completion and validation through the `$schema` key; do not edit them.

Inspect the current state with:
```sh
graph contract --compact          # readable summary
graph contract entities           # JSON, entity types only
graph contract edges
```
`graph contract` works before `graph init` and shows empty contracts without writing files. `graph init --list-templates` lists editable examples; apply one with `graph init --template=codebase` or `--template=documents`. Templates are starting points and should be adapted to the domain.

## 2. Format and rules

Entity contract:
```json
{
  "$schema": "./schemas/entities.schema.json",
  "API": {
    "description": "An API or application service",
    "properties": {
      "language": { "type": "string", "required": true },
      "framework": "string",
      "base_url": { "type": "string", "required": false }
    }
  }
}
```

Edge contract:
```json
{
  "$schema": "./schemas/edges.schema.json",
  "CALLS": {
    "description": "One service synchronously invokes another.",
    "source": ["API", "WORKER"],
    "target": ["API"],
    "properties": {
      "protocol": { "type": "string", "required": false }
    }
  }
}
```

Rules:
- Each top-level key is a type name mapping to an object. Names must be unique **ignoring case**; commands accept them case-insensitively; the contract's spelling is canonical for new records.
- Entities require `properties`. Edges require `source`, `target`, and `properties`.
- `source` and `target` are lists of entity type names. Each must exist, and the bundled schema expects them non-empty.
- A property is either a shorthand string (`"framework": "string"`) or an object `{ "type": ..., "required": ... }`. `required` defaults to `false`.
- Supported property types: `string`, `number`, `integer`, `boolean`. `number` accepts integers and decimals, not booleans. `integer` accepts integers, not booleans. No null, arrays, or objects as property types.
- `description` is optional at runtime but valuable: it is shown in `graph view` and read by agents. Always write one for each type.

## 3. Creating a contract from scratch

Use this when the workspace was just initialized, a template was applied, or the user describes a new domain. If the contract is empty or a template was applied, check that it can express the user's domain. If it can't, propose changes to the user before adding records.

### Step 1: understand the questions the graph must answer
Ask the user (or infer from the task) what they want to ask later. Examples: "which services depend on X?", "which document describes decision Y?", "what data does this job touch?". Types and edges exist to answer those questions. Anything that does not help a real question stays out.

### Step 2: list the nouns, then the verbs
- **Nouns become entity types.** Things you can point at and name.
- **Verbs become edge types.** Relationships you can state as `A <verb> B`.

### Step 3: keep it small
Start with roughly 3 to 8 entity types and 3 to 8 edge types. Adding a type later is easy; removing or renaming one is painful (see section 7).

### Step 4: define properties sparingly
Only add a property when you will filter or read it often (`language`, `environment`, `status`). Make it `required` only if you can always supply it. Everything else goes into `description` or `evidences`.

### Step 5: write the files
Edit `.graph/entities.json` and `.graph/edges.json` (keep the `$schema` lines).

### Step 6: validate before using
```sh
graph validate
graph contract --compact
```
An empty graph validates cleanly if the contracts are structurally sound. Fix any contract errors now, while no data depends on them.

### Step 7: try it with real records
Add two nodes and one edge with `add-node` / `add-edge`, confirm they are accepted, then `graph delete` them (or keep them if they are real). This catches endpoint mistakes early.

## 4. Design guidelines

- **Entity type names:** singular, `UPPER_SNAKE_CASE` nouns (`API`, `WORKER`, `DATASTORE`, `DOCUMENT`).
- **Edge type names:** `UPPER_SNAKE_CASE` verbs, read as `SOURCE VERB TARGET` (`CALLS`, `READS`, `PUBLISHES`, `DEPENDS_ON`, `DESCRIBES`). The direction should be obvious from the name.
- **Prefer specific edges over a generic one.** `READS`/`WRITES` is better than one `ACCESSES` plus a property, because you can filter with `--edge=READS` in `traverse` and `path`.
- **Use endpoint lists to encode meaning.** `READS: source [API, WORKER], target [DATASTORE]` makes invalid relationships impossible to write.
- **One concept, one type.** If two types differ only by a property value (for example `INTERNAL_API` and `EXTERNAL_API`), use one type and a property (`visibility`) unless you need different endpoint rules.
- **Properties are for facts you filter on**, not prose. Long text belongs in `description`.
- **Required means always known.** A required property you often lack will cause failed imports and invented values.
- **Write a `description` for every type** so a future agent knows when to use it.
- **Avoid a catch-all type** (`THING`, `OTHER`). It makes queries ambiguous and defeats validation.

## 5. Example contracts

### Software systems
```json
{
  "API":       { "description": "An HTTP/gRPC service", "properties": { "language": {"type":"string","required":true}, "framework": "string" } },
  "WORKER":    { "description": "A background job or consumer", "properties": { "language": {"type":"string","required":true} } },
  "DATASTORE": { "description": "A database, cache, or bucket", "properties": { "engine": {"type":"string","required":true} } },
  "QUEUE":     { "description": "A message queue or topic", "properties": { "technology": "string" } },
  "REPOSITORY":{ "description": "A source repository", "properties": { "default_branch": "string" } }
}
```
```json
{
  "CALLS":      { "description": "Synchronous call", "source": ["API","WORKER"], "target": ["API"], "properties": { "protocol": "string" } },
  "READS":      { "description": "Reads data from", "source": ["API","WORKER"], "target": ["DATASTORE"], "properties": {} },
  "WRITES":     { "description": "Writes data to", "source": ["API","WORKER"], "target": ["DATASTORE"], "properties": {} },
  "PUBLISHES":  { "description": "Publishes messages to", "source": ["API","WORKER"], "target": ["QUEUE"], "properties": {} },
  "CONSUMES":   { "description": "Consumes messages from", "source": ["WORKER","API"], "target": ["QUEUE"], "properties": {} },
  "CONTAINS":   { "description": "Repository contains a component", "source": ["REPOSITORY"], "target": ["API","WORKER"], "properties": {} }
}
```

### Documents and decisions
```json
{
  "DOCUMENT": { "description": "A source document", "properties": { "format": "string", "version": "string" } },
  "CONCEPT":  { "description": "An idea or term defined in documents", "properties": {} },
  "DECISION": { "description": "A recorded decision", "properties": { "status": {"type":"string","required":true} } }
}
```
```json
{
  "DEFINES":    { "description": "Document defines a concept", "source": ["DOCUMENT"], "target": ["CONCEPT"], "properties": {} },
  "SUPERSEDES": { "description": "Newer decision replaces an older one", "source": ["DECISION"], "target": ["DECISION"], "properties": {} },
  "DECIDES":    { "description": "Document records a decision", "source": ["DOCUMENT"], "target": ["DECISION"], "properties": {} }
}
```

## 6. Changing a contract safely

Always follow this loop:

1. **Baseline.** `graph validate` and `graph status`. Know whether the graph is clean *before* you change anything.
2. **Back up.** Commit or copy `.graph/entities.json`, `.graph/edges.json`, and `graph.json`.
3. **Make one logical change** in the contract files.
4. **Validate.** `graph validate` and read the errors grouped by `code` and `kind`.
5. **Repair** the affected records (see playbooks).
6. **Validate again** until `valid:true`, then `graph status` to confirm totals and orphans did not change unexpectedly.

Rules of thumb:
- **Loosening is safe** (new type, new optional property, widening endpoint lists, making a required property optional). Existing data stays valid.
- **Tightening is risky** (new required property, removing a property or type, narrowing endpoint lists, changing a property type). Existing records may become invalid.
- `validate` is read-only and never repairs. You fix data with `edit` or `import --on-conflict=replace`.

## 7. Change playbooks

### Add a new entity or edge type
Edit the contract, `graph validate`. Nothing else is needed.

### Add an optional property
Edit the contract, `graph validate`. Existing nodes remain valid. Fill values later with `graph edit node ID --p.KEY=VALUE` or a `replace` import.

### Add a required property to an existing type
1. Add it as **optional** first and validate.
2. Backfill every node of that type (`graph nodes --type=T --fields=id` to list them; then `edit` one by one or a `replace` batch with complete records).
3. Confirm nothing is missing: flip `required` to `true`, run `graph validate`. Remaining `missing_required_property` errors point at nodes still to fix.

### Make a property optional
Change `required` to `false` (or remove it from `required`). Safe.

### Rename or remove a property
1. Add the new name (if renaming) as optional.
2. Copy values over using `edit` (`--p.NEW=VALUE`) or a `replace` batch. Note `--p.KEY` edits keep the other keys, but `--properties` replaces them all.
3. Remove the old key from the contract and from the records. `validate` reports records still carrying an undefined property.

### Change a property's type
Treat as removing and re-adding: add a new property with the new type, migrate values, remove the old one.

### Widen an edge's endpoints
Add the new type names to `source` or `target`. Safe.

### Narrow an edge's endpoints
Edit the contract, then `graph validate`. Edges that no longer fit are reported. Fix by deleting them or by re-creating them with a more suitable type.

### Rename an entity or edge type
There is **no rename command**, and node/edge types are immutable. The procedure is heavy:
1. Add the new type to the contract (keep the old one for now).
2. List old records: `graph nodes --type=OLD` (full records) or `graph edges --type=OLD --fields=id,type,source,target,description,properties,evidences`.
3. Build a JSONL with the same IDs, the new type, and the same content.
4. `graph delete` the old nodes. **This deletes their connected edges too**, so re-create those edges in the same batch.
5. Import the batch, remove the old type from the contract, validate.
Because of this cost, think hard about names up front. Often adding a new type and leaving the old one in place is the better trade.

### Remove an entity type
Delete all its nodes first (`graph nodes --type=T --fields=id`, then `graph delete node ID` for each; connected edges are deleted with them), then remove the type from both contract files, then validate. Remember edge contracts that list it in `source` or `target`.

### Split one type into two
Treated like a rename for the nodes that move: recreate them with the new type and ID (or the same ID after deleting the old node).

## 8. Diagnosing with validate and status

`graph validate` returns:
```json
{"valid":false,"errors":[{"kind":"node","id":"orders-api","code":"missing_required_property","message":"missing required property: language"}],"summary":{"nodes":1,"edges":0,"errors":1}}
```
- `kind` says what failed: contract, store, node, or edge. `id` is present when a record is involved.
- Errors are exhaustive in one response. Group them by `code` and fix them as a class (for example all `missing_required_property` at once).
- Exit codes: `0` valid, `3` violations, `4` workspace or files unreadable or missing.

Useful companion checks:
```sh
graph status                                      # totals and per-type counts reveal missing or surprising types
graph status --check=orphans --limit=20           # nodes that lost all edges after an edge type change
graph status --check=no-description,no-evidence   # quality gaps
```
After a contract change, compare `by_type` counts with what you expect. A type with an unexpected zero often means records were deleted or never imported.

## 9. Limits to be aware of

- Property types are limited to `string`, `number`, `integer`, `boolean`. Model structured data as extra node types or put it in evidences.
- Evidence objects have **no contract**; they are free-form. Keep to the convention in SKILL.md.
- Types and endpoints are immutable on existing records; changing them means delete and recreate.
- There is no migration command and no undo. Back up before tightening a contract.

## 10. Checklist

- [ ] Questions the graph must answer are written down
- [ ] 3 to 8 entity types and edge types, with descriptions
- [ ] Edge names read as `SOURCE VERB TARGET`, endpoints restricted on purpose
- [ ] Required properties are things you can always supply
- [ ] `graph validate` clean before and after changes
- [ ] Backup made before any tightening change
- [ ] `graph status` totals sanity-checked afterward
