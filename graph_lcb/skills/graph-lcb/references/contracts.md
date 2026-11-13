# Contracts: creating, extending, and repairing

Use this file when starting a new graph (empty contracts or a freshly applied template), when the user wants new types or properties, when mapping reveals something the contract cannot express, or when `graph validate` started failing after a contract change.

## Contents
1. What a contract is
2. Format and rules
3. Creating a contract for a new graph
4. Design guidelines: granularity and properties
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
`graph contract` works before `graph init` and shows empty contracts without writing files. `graph init --list-templates` lists editable examples; apply one with `graph init --template=codebase` or `--template=documents`. Templates (for example `codebase`, `documents`, `data-pipeline`, `research`) are **a base to adapt, never a finished contract**: review them, then add, remove, and reshape types and properties until they fit the domain (section 3).

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

## 3. Creating a contract for a new graph

Use this when the graph is new: empty contracts, or a template just applied, and no records yet. **Do not start adding records until the contract fits the domain.** A contract that fits is the foundation of precise retrieval.

### Step 1: choose where the contract comes from

| Situation | Approach |
| --- | --- |
| The user is available | Build it **with the user**: find out what the graph should answer, propose a contract, confirm |
| You can inspect the environment (codebase, documents, research material) | Build it **from what you observe**, then propose it to the user for confirmation |
| Both | Observe first, then propose, so your questions are specific |

Avoid open questions like "what contract do you want?". Observe, propose something concrete, and ask for corrections. If the user cannot answer, proceed with the observed contract, write your assumptions in `batches/PROGRESS.md`, and say so in your report.

### Step 2: observe the environment

Look at what is actually there before deciding on types. These are suggestions for what to inspect and what it tends to reveal; adapt them to what you see.

| Environment | Inspect | Entity types it suggests | Relationships it suggests |
| --- | --- | --- | --- |
| Codebase | Folder layout, manifests, Dockerfiles and compose files, routes, OpenAPI/proto files, HTTP/gRPC clients, ORM models and migrations, queue configs, IaC, CI, READMEs, ADRs, CODEOWNERS | `REPOSITORY`, `SERVICE` or `API`, `ENDPOINT`, `MODULE`, `WORKER`, `DATASTORE`, `TABLE`, `QUEUE`, `EXTERNAL_SYSTEM`, `LIBRARY`, `CONFIG_KEY`, `TEAM` | `CONTAINS`, `EXPOSES`, `CALLS`, `DEPENDS_ON`, `READS`, `WRITES`, `PUBLISHES`, `CONSUMES`, `CONFIGURED_BY`, `DEPLOYED_ON`, `OWNED_BY` |
| Documents | Titles, headings, glossaries, ADRs, version numbers, cross-references | `DOCUMENT`, `SECTION`, `CONCEPT`, `DECISION`, `REQUIREMENT`, `STAKEHOLDER` | `DEFINES`, `DESCRIBES`, `DECIDES`, `SUPERSEDES`, `REFERENCES`, `SATISFIES`, `CONTRADICTS` |
| Research material | Papers, notes, datasets, experiment logs, bibliographies | `PAPER`, `AUTHOR`, `CLAIM`, `METHOD`, `DATASET`, `EXPERIMENT`, `RESULT`, `TOPIC` | `CITES`, `AUTHORED_BY`, `SUPPORTS`, `CONTRADICTS`, `USES_METHOD`, `USES_DATASET`, `REPORTS` |
| Data pipelines | Job definitions, DAGs, schemas, table lists, schedules | `JOB`, `DATASET`, `TABLE`, `SCHEMA`, `SOURCE_SYSTEM`, `SINK` | `READS`, `WRITES`, `TRANSFORMS`, `DEPENDS_ON`, `SCHEDULED_BY` |
| Infrastructure | IaC, manifests, cloud inventories | `CLUSTER`, `NAMESPACE`, `DEPLOYMENT`, `BUCKET`, `NETWORK` | `HOSTED_ON`, `ROUTES_TO`, `DEPENDS_ON` |

While observing, note the **facts you will want to filter by** (language, version, environment, owner, status, protocol). They become properties (section 4).

### Step 3: start from a template when one fits

```sh
graph init --list-templates
graph init --template=codebase --dry-run     # preview
graph init --template=codebase               # apply
graph contract --compact                     # read what you got
```

A template is a base. After applying one:
1. **Compare it with what you observed.** Which types are missing? Which are irrelevant?
2. **Adapt it while the graph is empty**, when changes are free: add types, edge types, and properties; remove types you will not use; rename types to the user's vocabulary.
3. **Relax required properties** you cannot always supply. Templates define required properties, so records of those types cannot be added with an empty `properties` object until the contract matches reality.
4. **Never map with a template you have not reviewed.**

If no template fits, run a plain `graph init` and write the contract from scratch. `init` never overwrites a contract that already defines types.

### Step 4: propose and confirm

Present a concrete proposal and ask once. For example:

```text
Proposed contract (based on the codebase template, adapted)
Entity types: SERVICE (language*, framework, owner), ENDPOINT (method*, path*), DATASTORE (engine*, version),
              QUEUE (technology), EXTERNAL_SYSTEM (vendor), TEAM
Edge types:   CALLS (SERVICE -> SERVICE; protocol, method), EXPOSES (SERVICE -> ENDPOINT),
              READS / WRITES (SERVICE -> DATASTORE), PUBLISHES / CONSUMES (SERVICE -> QUEUE),
              OWNED_BY (SERVICE -> TEAM), DEPENDS_ON (SERVICE -> SERVICE | EXTERNAL_SYSTEM)
Assumptions:  <what you inferred and from where>
Not modeled:  <what you left out on purpose>
Questions:    <at most two or three, specific>
```
(`*` marks required properties.) Proceed after confirmation, or adjust if the user corrects you.

### Step 5: write the files
Edit `.graph/entities.json` and `.graph/edges.json` (keep the `$schema` lines).

### Step 6: validate and try it
```sh
graph validate
graph contract --compact
```
Then add two nodes and one edge with `add-node` / `add-edge`, confirm they are accepted, and `graph delete` them (or keep them if they are real). This catches endpoint mistakes early.

### Step 7: expect the contract to grow
Mapping will reveal things you did not anticipate. That is normal: extend the contract when it happens (section 6, "During mapping"), and do not force data into the wrong type.

## 4. Design guidelines: granularity and properties

### Granularity
- **Specific types beat generic ones.** Create a type when you would filter by it (`--type=`), when it has its own properties, when it takes part in different relationships, or when merging it with another type would blur answers.
- **There is no fixed cap on the number of types.** Each type should be justified by something you have seen or will map soon. Remove speculative types that no source supports (while the graph is still empty, this is free).
- **Several edge types between the same node types is a feature.** `CALLS`, `DEPENDS_ON`, and `CONFIGURED_BY` between two services each answer a different question. Prefer `READS`/`WRITES` over one `ACCESSES` plus a property, because `--edge=READS` in `traverse` and `path` then works directly.
- **Use endpoint lists to encode meaning.** `READS: source [SERVICE, WORKER], target [DATASTORE, TABLE]` makes invalid relationships impossible to write.
- **One concept, one type** unless the differences matter. If two types differ only by a property value (for example `INTERNAL_API` and `EXTERNAL_API`), use one type and a property (`visibility`), unless they need different endpoint rules or different properties.
- **Avoid a catch-all type** (`THING`, `OTHER`). It makes queries ambiguous and defeats validation.

### Properties
Properties are retrieval handles: they are what `--p.KEY=VALUE` and `--properties` filter on. Define them **generously** for facts you can verify from the sources and that someone might filter or read.
- **Identification:** language, framework, version, runtime, format.
- **Operations:** environment, port, owner, region, schedule.
- **Semantics:** status, visibility, criticality, kind.
- **Edge properties** matter too: protocol, method, path, sync or async, authentication, frequency.
- **Required only if always known.** A required property you often lack causes failed imports and invented values. Everything else stays optional.
- **Scalars only** (`string`, `number`, `integer`, `boolean`). For a closed set of values, use a `string` and list the allowed values in the type's `description` (for example "status: active, deprecated, retired").
- **Long prose belongs in `description`**, and structured detail belongs in `evidences` or in extra nodes.
- **If you keep writing the same fact into descriptions, add a property for it.**

### Naming and documentation
- **Entity type names:** singular, `UPPER_SNAKE_CASE` nouns (`SERVICE`, `DATASTORE`, `DOCUMENT`).
- **Edge type names:** `UPPER_SNAKE_CASE` verbs, read as `SOURCE VERB TARGET` (`CALLS`, `READS`, `PUBLISHES`, `DEPENDS_ON`, `DESCRIBES`). The direction should be obvious from the name.
- **Write a `description` for every type**, including when to use it, so a future agent picks the right one.

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

### Granularity in practice

Coarse contract: two services, one relationship.
```json
{ "CALLS": { "description": "Service calls service", "source": ["SERVICE"], "target": ["SERVICE"], "properties": {} } }
```

Granular contract: the same two services can now be related in several useful ways, and the question "which endpoint writes this table" has an answer.
```json
{
  "CALLS":         { "description": "Synchronous call", "source": ["SERVICE", "WORKER"], "target": ["SERVICE"], "properties": { "protocol": "string", "method": "string", "path": "string" } },
  "DEPENDS_ON":    { "description": "Build or runtime dependency without a direct call", "source": ["SERVICE", "WORKER"], "target": ["SERVICE", "LIBRARY", "EXTERNAL_SYSTEM"], "properties": { "kind": "string" } },
  "EXPOSES":       { "description": "Service exposes an endpoint", "source": ["SERVICE"], "target": ["ENDPOINT"], "properties": {} },
  "HANDLES":       { "description": "Endpoint is implemented by a module", "source": ["ENDPOINT"], "target": ["MODULE"], "properties": {} },
  "WRITES":        { "description": "Writes data to", "source": ["ENDPOINT", "WORKER", "SERVICE"], "target": ["TABLE", "DATASTORE"], "properties": { "operation": "string" } },
  "CONFIGURED_BY": { "description": "Reads configuration from", "source": ["SERVICE", "WORKER"], "target": ["CONFIG_KEY"], "properties": {} }
}
```
Two services can now have `CALLS`, `DEPENDS_ON`, and a shared `TABLE` they both `WRITES`, each with its own evidence and properties.

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

### During mapping: the contract is a living document
- **When you find something the contract cannot express, extend it** instead of forcing data into the wrong type or dropping it. Extending is safe (loosening). Steps: edit the contract, `graph validate`, note it under "Contract changes" in `batches/PROGRESS.md`, and mention it to the user.
- **Parallel producer agents do not edit the contract.** They stop and report the missing type or property to the orchestrator (mapping.md, section 13).
- **Avoid renaming types mid-mapping.** It is the heavy procedure in the playbooks below. Add the right type and migrate deliberately if you must.
- **Review the contract at the end of each pass.** Types with zero records and properties nobody filled are candidates for cleanup; missing properties are candidates for backfill.

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

- [ ] Source of the contract is clear: built with the user, or from observing the environment (and confirmed)
- [ ] If a template was used, it was reviewed and adapted, not taken as is
- [ ] Questions the graph must answer are written down
- [ ] Types are specific and justified by sources; several edge types between the same node types where relationships differ
- [ ] Properties defined for the facts you will filter or read (nodes and edges); required only when always known
- [ ] Every type has a `description`; edge names read as `SOURCE VERB TARGET`; endpoints restricted on purpose
- [ ] `graph validate` clean before and after changes
- [ ] Backup or commit made before any tightening change
- [ ] `graph status` totals sanity-checked afterward
- [ ] Contract changes noted in `batches/PROGRESS.md`