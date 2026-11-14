# Mapping codebases, documents, and many repositories

Use this reference when building a graph from source material: a codebase, a folder of documents, research material, or several repositories. It assumes you know the basics from `SKILL.md`. Use `contracts.md` to define the graph schema and `batch_imports.md` to write and import records.

The mapping process has four priorities:

1. Build a contract that fits the domain.
2. Investigate sources thoroughly and record every relationship you can prove.
3. Work incrementally, using deterministic IDs and evidence-backed records.
4. Maintain a progress ledger so another agent can resume without repeating work.

## Contents

1. Principles
2. Pre-flight
3. Scope and progress tracking
4. Workspace layout
5. ID conventions
6. Evidence and properties
7. Mapping passes
8. Relationship discovery
9. Granularity
10. Mapping a single codebase
11. Mapping many repositories
12. Mapping documents and research
13. Parallel agents
14. Quality gates
15. Keeping the graph fresh
16. Pitfalls

## 1. Principles

1. **The contract fits the domain.** For a new graph, build the contract with the user or derive an initial version from the sources (`contracts.md`, section 3). Templates are starting points, not finished schemas.
2. **Investigate broadly, record strictly.** Search actively for relationships and details. Record only what the sources support. Put suspicions and unverified relationships in the progress ledger.
3. **Use appropriate granularity.** Prefer finer nodes and relationship types when they improve retrieval and the sources support them (section 9).
4. **Evidence and properties are essential.** Evidence makes claims verifiable; properties make records filterable (section 6).
5. **Work incrementally.** Organize mapping into coherent batches. Follow the append-only import process in `batch_imports.md`.
6. **Maintain a progress trail.** Update `batches/PROGRESS.md` after every completed batch and before stopping.
7. **Map breadth before depth.** Inventory entities first, map obvious relationships next, then investigate less obvious connections.
8. **Use deterministic IDs.** The same entity should receive the same ID across mapping runs.
9. **Keep batches coherent.** Split work by repository, area, document, or mapping pass. Each batch should be independently reviewable and verifiable.

## 2. Pre-flight

Before inspecting sources:

1. **Check for existing work.**
   ```sh
   ls batches/
   ```
   If `batches/PROGRESS.md` exists, read it completely and follow the resumption procedure in section 3.

2. **Confirm the workspace root.** Run all `graph` commands from the directory that owns `.graph/`. For multi-repository mapping, this is normally the parent directory containing all repository clones.

3. **Initialize if necessary.**
   ```sh
   graph init
   ```
   Or start from a template:
   ```sh
   graph init --template=NAME
   ```

4. **Inspect the contract.**
   ```sh
   graph contract --compact
   ```
   - If it is empty or contains only an unreviewed template, inspect the environment first: list directories, read manifests, and skim document headings. Then build or adapt the contract (`contracts.md`, section 3).
   - If the user is available, propose the contract and confirm it before mapping.
   - If confirmation is not possible, proceed using the best source-supported assumptions and document them in the progress ledger.
   - If the existing contract cannot express what you discover, extend it before writing records (`contracts.md`, section 6).

5. **Inspect the existing graph.**
   ```sh
   graph status
   ```
   If it is not empty, inspect relevant existing records before creating new ones:
   ```sh
   graph nodes --type=T --fields=id,name --limit=50
   ```
   Extend the existing graph rather than duplicating entities.

6. **Define the scope and questions.** Write one or two sentences describing what is being mapped and what questions the graph should answer. For example:
   > Map runtime service dependencies across all repositories under `./repos` to support impact analysis.

   These questions guide priorities and granularity. They do not limit other information you should record when the sources support it.

7. **Create `batches/PROGRESS.md`** using the template in section 3.

8. **Create a recovery point.**
   ```sh
   git add .graph batches
   git commit -m "Initialize graph mapping workspace"
   ```

## 3. Scope and progress tracking

Mapping is often interrupted by context limits, session boundaries, or handoffs between agents. The progress ledger is the source of truth for what has been investigated, what remains, and where work should resume.

### Progress ledger

Maintain `batches/PROGRESS.md` with the following structure:

```markdown
# Mapping progress

## Scope
What is being mapped and which questions the graph should answer.
Workspace root: <path>
ID convention: <pattern>
Evidence paths relative to the workspace root.

## Contract
Based on: <template name or "from scratch">
Key decisions and assumptions:
- ...

## Coverage
| Area | Status | Batch(es) | Commit/version read | Granularity | Notes |
| --- | --- | --- | --- | --- | --- |
| repos/orders (services, workers) | covered | 0002, 0006 | abc1234 | endpoints + tables | relationship sweep done |
| repos/orders (infra, CI) | partial | 0006 | abc1234 | services only | Terraform not read yet |
| repos/billing | not started | | | | |
| docs/architecture.md | skipped | | | | Outdated; revisit if requested |

Status values:
- covered: read fully and relationship sweep completed
- partial: investigated, but some areas remain
- not started
- skipped: intentionally excluded, with a reason

## Not covered yet
- repos/billing: everything
- repos/orders: Terraform and CI workflows
- Cross-repository integration pass

## Where I stopped / next step
Exact, actionable next step.

## To verify / open questions
- Is stock-api also called by the nightly job? Configuration suggests yes, but no call site was found.

## Contract changes
- 0005: added property owner to API; added edge type DEPENDS_ON

## Deletions and manual edits
- <date>: deleted edge <id> (call removed in def5678)

## Totals after last import
nodes: N
edges: M
```

### Updating the ledger

After each imported batch, record:

- The area and pass covered.
- The batch filename.
- The source commit or document version inspected.
- The achieved granularity.
- Remaining gaps and unverified relationships.
- Updated graph totals from `graph status`.
- The next concrete step.

If a batch was written but not imported, explicitly mark it as `written, not imported`.

Before stopping for any reason, update the ledger. The next step must be precise enough for another agent to continue without asking what to do.

### Resuming

1. Read `batches/PROGRESS.md` completely.
2. List the batch files:
   ```sh
   ls batches/
   ```
3. Check graph consistency:
   ```sh
   graph validate
   graph status
   ```
4. Compare the current totals with the ledger.
5. If the last batch is marked `written, not imported`, dry-run and import it using `batch_imports.md`.
6. Do not repeat areas marked `covered` unless their sources have changed (`maintenance.md`).
7. Continue from `Where I stopped / next step`.
8. Update the ledger after the first newly completed batch.

## 4. Workspace layout

Recommended structure:

```text
workspace/                 <- run graph commands here
  .graph/
  batches/
    0001-initial-inventory.jsonl
    0002-orders-structure.jsonl
    PROGRESS.md
  repos/
    orders/
    billing/
    stock/
  docs/
    architecture.md
```

A single workspace is useful when mapping multiple repositories because:

- One `.graph/` can contain cross-repository relationships.
- Evidence paths are relative to one root and remain portable.
- Search works across repositories:
  ```sh
  graph search repos/orders/ --in=evidences
  ```

## 5. ID conventions

IDs must match:

```regex
^[a-z0-9][a-z0-9._-]*$
```

Recommended pattern:

```text
<scope>.<kind-or-area>.<name>
```

Use lowercase, with kebab-case inside segments.

| Entity | Example |
| --- | --- |
| Repository | `repo.orders` |
| Service | `orders.api` or `orders.orders-api` |
| Endpoint | `orders.api.post-orders` |
| Worker | `orders.worker.invoice-sync` |
| Datastore | `orders.db.main` |
| Table | `orders.db.main.orders-table` |
| Shared resource | `shared.kafka.orders-topic` |
| External service | `ext.stripe` |
| Document | `doc.architecture-overview` |
| Document section | `doc.architecture-overview.4-data-flow` |
| Decision | `adr.0007-use-kafka` |

Rules:

- **Scope IDs by repository or domain.** This prevents collisions and makes ownership clear.
- **Never use timestamps, random values, or line numbers.** IDs represent entity identity, not source location.
- **Choose a convention once** and document it in the progress ledger.
- **Create shared resources once.** Use a shared scope such as `shared.` or `ext.`. Other repositories should reference the existing entity through edges.
- **Do not reuse an ID for different entities.**
- Edge IDs are generated. Control edge identity through its type, endpoints, and properties.

See `batch_imports.md` for how IDs behave during imports.

## 6. Evidence and properties

Evidence answers **how do we know?** Properties answer **which records match?** Both are part of the graph's data model, not optional decoration.

### Evidence

Follow the evidence convention from `SKILL.md`:

- `source`
- `locator`
- `note`
- Optional `commit`

Examples:

Code:
```json
{
  "source": "repos/orders/src/api.py",
  "locator": {
    "start_line": 12,
    "end_line": 28
  },
  "note": "Route handler for POST /orders",
  "commit": "abc1234"
}
```

Document:
```json
{
  "source": "docs/architecture.md",
  "locator": {
    "section": "3.2 Retries"
  },
  "note": "Defines the retry policy"
}
```

Rules:

- `source` must be relative to the workspace root, never an absolute path.
- Use the most specific locator available: the call site, not merely the containing folder.
- Include the commit hash for code evidence. For example:
  ```sh
  git -C repos/orders rev-parse --short HEAD
  ```
- Important records should have multiple evidences where possible. For example, a service-to-service call can be supported by the caller's client code and the callee's route.
- Evidence should demonstrate the claim made by the record.

### Properties

- Fill every property defined by the contract that the sources support.
- Put stable, filterable facts in properties; put explanations and context in `description`.
- Examples of node properties: language, framework, version, environment, port, owner, visibility, status.
- Examples of edge properties: protocol, method, path, sync/async, authentication, frequency, criticality.
- Do not guess values. Omit unsupported optional properties.
- If a required property cannot be determined from the sources, reconsider the contract instead of inventing a value (`contracts.md`, section 6).
- If the same fact repeatedly appears inside descriptions, consider adding it as a contract property and backfilling existing records.

### Quality bar per record

| Record | Minimum |
| --- | --- |
| Node | Recognizable name, one- or two-sentence description, every supportable property, at least one evidence |
| Edge | Description explaining the relationship, supportable properties, at least one evidence |
| Important node or edge | Two or more evidences, ideally from both sides of the relationship |

## 7. Mapping passes

Do not attempt to map everything in one sweep. Use separate passes and import each coherent unit before continuing.

1. **Inventory pass — nodes.** Identify repositories, services, endpoints, workers, datastores, queues, documents, and other relevant entities. Produce node batches with evidence and properties.
2. **Structure pass — intra-scope edges.** Map containment and obvious relationships within a repository or document.
3. **Integration pass — cross-scope edges.** Map calls, shared datastores, shared queues, and document-to-code relationships. Do this after the relevant endpoint nodes exist.
4. **Relationship sweep.** Revisit every node and actively search for relationships that were not captured in earlier passes (section 8).
5. **Refinement pass.** Improve descriptions, properties, evidence, and granularity. Correct issues found during verification.

After each pass, use the batch-import workflow to dry-run, import, validate, and update the progress ledger.

## 8. Relationship discovery

Two entities can have several distinct relationships. For example, one service may call another, depend on its library, and read its database. Each relationship answers a different query and should have its own edge.

### Multiple edges

- Different edge types between the same endpoints are valid:
  - `orders-api CALLS stock-api`
  - `orders-api DEPENDS_ON stock-api`
- Multiple edges with the same type and endpoints require distinct properties and a non-empty description for each. For example, two `CALLS` edges with different methods or paths.
- Direction matters. Investigate both directions: A may call B, while B may also call A through callbacks, webhooks, or events.
- A duplicate is generally the same type, endpoints, and properties. A different description does not make it a distinct relationship.

### Relationship sweep checklist

For each node, investigate applicable questions and look for source evidence.

| Question | Typical edge types |
| --- | --- |
| What does it call or depend on? Who calls or depends on it? | `CALLS`, `DEPENDS_ON` |
| What data does it read, write, or own? | `READS`, `WRITES`, `OWNS` |
| What does it publish or consume? | `PUBLISHES`, `CONSUMES` |
| What configures it? Which secrets or keys does it use? | `CONFIGURED_BY`, `USES_CONFIG` |
| Where is it hosted or deployed? What builds it? | `DEPLOYED_ON`, `BUILT_BY` |
| Who owns it? Which team? | `OWNED_BY` |
| Which documents describe or decide things about it? | `DESCRIBES`, `DECIDES` |
| What replaced it, or what does it replace? | `SUPERSEDES` |
| What does a document define, cite, support, or contradict? | `DEFINES`, `CITES`, `SUPPORTS`, `CONTRADICTS` |

These are examples. Use the types in the active contract. Add new types when the contract cannot express a relationship you have found (`contracts.md`, section 6).

### Procedure

1. Inspect outgoing edges:
   ```sh
   graph edges --from=ID --fields=id,type,target,description
   ```
2. Inspect incoming edges:
   ```sh
   graph edges --to=ID --fields=id,type,source,description
   ```
3. Compare existing relationships against the checklist.
4. For every connected pair, ask whether another distinct relationship exists.
5. Write additional edges with evidence and properties.
6. Record unfinished investigations in the progress ledger.

### Finding gaps

- Find nodes with no edges:
  ```sh
  graph status --check=orphans
  ```
- Inspect nodes with only one edge using `graph edges --from=ID` and `graph edges --to=ID`.
- Compare `by_type` counts. For example, many `API` nodes but very few `READS` edges may indicate missing data-access relationships.

**Be exhaustive in investigation, but strict in recording.** A relationship inferred only from names is a lead to verify, not a graph edge.

## 9. Granularity

Default to the finest granularity that the sources support and that improves retrieval.

A coarse graph may answer which services exist. A more granular graph can answer which endpoint writes a particular table or which document section defines a requirement.

### Examples

| Domain | Possible finer nodes |
| --- | --- |
| Code | Endpoints, routes, modules, jobs, tables, topics, config keys, feature flags, integrations, libraries |
| Documents | Sections, requirements, concepts, decisions, stakeholders |
| Research | Claims, methods, datasets, experiments, results |
| Infrastructure | Clusters, namespaces, deployments, buckets, networks |
| Data pipelines | Jobs, tables, schemas, sources, sinks |

### Choosing types

Add node or edge types when they enable meaningful filtering or relationships (`contracts.md`, section 4). More specific types generally provide better retrieval than a small set of generic types, provided the distinctions are useful.

### Where to stop

Go finer while:

- You can attach reliable evidence.
- The entity or relationship could plausibly be queried or traversed.
- The additional detail provides meaningful retrieval value.

Avoid mapping implementation details nobody is likely to query, such as every getter or private helper, or details that cannot be tied to a source.

### Work in layers

Map coarse structure first, then refine areas in later batches. Record the achieved granularity per area in the progress ledger. This makes partial coverage explicit instead of making an unfinished area look complete.

## 10. Mapping a single codebase

### Where to look

| Target | Sources |
| --- | --- |
| Services and entry points | Repository layout, `main`/`app` files, Dockerfiles, `docker-compose.yml`, Helm charts, Procfiles |
| Languages, frameworks, versions | `pyproject.toml`, `requirements.txt`, `go.mod`, `package.json`, `pom.xml`, `build.gradle` |
| Inbound interfaces | Routes, controllers, OpenAPI/proto files, handler registrations |
| Outbound calls | HTTP/gRPC clients, SDK wrappers, base URL configuration, service discovery names |
| Datastores and tables | Connection settings, ORM models, migrations, repository classes |
| Queues and events | Producer/consumer code, topic configuration, broker clients |
| Infrastructure | Terraform, CloudFormation, Kubernetes manifests |
| Build and deploy | CI workflows, Makefiles, release scripts |
| Ownership and boundaries | README files, CODEOWNERS, ADRs |

### Procedure

1. Read the repository layout and README, then inspect the manifests.
2. Confirm that the contract can represent the discovered entities and relationships (section 2).
3. Identify candidate nodes and the source files that prove they exist.
4. For each service, investigate inbound and outbound integrations.
5. Follow configuration to the actual target. An environment variable named `STOCK_URL` does not prove which service it points to; inspect where the value is set or documented.
6. Write and import the node batch, followed by the relevant edge batches.
7. Run the relationship sweep (section 8).
8. Refine granularity where it adds value (section 9).

### Secrets

Never include secrets, tokens, credentials, or sensitive values in properties, descriptions, or evidence notes. Reference variable names or configuration keys instead.

## 11. Mapping many repositories

Use one workspace containing all repository clones so the graph can represent cross-repository relationships.

### Setup

1. Clone repositories side by side under `repos/<name>`.
2. Run `graph` from the workspace root.
3. Create a `REPOSITORY` node per repository, using IDs such as `repo.orders`.
4. Add containment edges from repository nodes to their components if the contract supports them.
5. Record each repository's commit hash in its evidence and in the coverage table.

### Procedure

1. **Inventory every repository first.** Complete the initial node inventory across all repositories before mapping cross-repository edges.
2. **Map internal structure.** Use separate batches per repository or coherent area, for example `batches/0003-repo-orders.jsonl`.
3. **Map cross-repository integrations.** Use evidence from both sides when available: the caller's client code and the callee's route or contract.
4. **Create shared infrastructure once.** Databases, topics, gateways, and other shared resources should use a shared ID. Search before creating them:
   ```sh
   graph search kafka --kind=nodes --in=id,name
   ```
5. **Represent external services explicitly.** Use IDs such as `ext.stripe`, with an appropriate node type and evidence from the integration code.
6. **Run a cross-repository relationship sweep.** For every interacting repository pair, investigate calls, shared tables, shared topics, shared libraries, and deployment coupling.

### Naming collisions

Two repositories may contain entities with identical short names, such as `api`. Scope IDs to their repository:

- `orders.api`
- `billing.api`

Never reuse one ID for two different entities.

### Recommended order

```text
1. Define the shared contract.
2. Batch 0001: repository nodes and obvious components for ALL repositories.
3. Batches 0002..N: internal structure, organized by repository and area.
4. Batch N+1: cross-repository relationships.
5. Additional batches: relationship sweep and refinement.
```

Update `batches/PROGRESS.md` after every batch.

## 12. Mapping documents and research

This applies to architecture documents, ADRs, specifications, PDFs, wiki exports, papers, and notes.

1. **Create a node per document.** Use IDs such as `doc.*`. Include properties such as `format` and `version` when supported by the contract.
2. **Map meaningful sections.** Create finer nodes for sections, requirements, claims, methods, or datasets when they improve retrieval. Attach section or page locators to their evidence.
3. **Extract the entities discussed.** Identify concepts, decisions, systems, and stakeholders. Search for existing nodes and reuse them instead of creating parallel representations of the same entity.
4. **Use typed relationships.** Examples include `DESCRIBES`, `DEFINES`, `DECIDES`, `SUPERSEDES`, `REFERENCES`, `CITES`, `SUPPORTS`, and `CONTRADICTS`.
5. **Connect documents to code.** When a document refers to a system already represented in the graph, reuse that node ID and cite the relevant passage.
6. **Preserve conflicts.** If documents disagree, or a document contradicts the implementation, record both claims as separate relationships with descriptions. Note the conflict in the progress ledger; do not silently choose one source.
7. **Work section by section for long documents.** Use one batch per document or coherent group of short documents. Mark partial coverage explicitly.

Example evidence:

```json
{
  "source": "docs/architecture.md",
  "locator": {
    "section": "4 Data flow"
  },
  "note": "Describes the order-to-stock call"
}
```

## 13. Parallel agents

Parallel reading is acceptable. **Parallel imports are not.**

- Assign one repository or document set to each producer agent.
- Producers investigate sources and write their own batch files. They do not run `graph import`.
- A single importer validates and imports batches sequentially. See `batch_imports.md` for the operational workflow and handoff template.
- Give every producer the same contract, ID convention, evidence convention, granularity expectations, and list of existing shared nodes.
- Each producer must report what it covered, what remains, and exactly where it stopped.
- The importer consolidates producer coverage into `batches/PROGRESS.md`.
- If a producer needs a type or property that does not exist in the contract, it must stop and report the requirement. The orchestrator decides whether to change the contract (`contracts.md`, section 6), then re-runs affected producers.
- A single agent working alone may extend the contract itself, provided the change is documented in the ledger.
- Prefer one agent for cross-repository edges. It should have visibility into the complete repository inventory and import results.

## 14. Quality gates

Run these checks after each import and before declaring a pass complete:

```sh
graph validate
graph status --check=orphans,no-evidence,no-description,components --limit=20
```

| Finding | Meaning | Action |
| --- | --- | --- |
| Validation errors | Contract mismatch | Fix records or the contract |
| Orphans | Nodes with no edges | Investigate missing relationships or legitimate standalone nodes |
| Missing evidence | Claims cannot be verified | Add evidence or remove the record |
| Missing edge descriptions | Relationships are unclear | Add a concise explanation |
| Many components | Graph is disconnected | Expected before integration mapping; investigate if still present afterwards |

`status` does not cover every quality dimension. Also inspect:

1. **Relationship density.** Sample nodes using `graph edges --from=ID` and `graph edges --to=ID`. If most nodes have only one or two edges, repeat the relationship sweep.
2. **Property completeness.** Sample records:
   ```sh
   graph nodes --type=T --fields=id,properties --limit=20
   ```
   If common properties are missing, backfill them using a new `replace` batch.
3. **Evidence quality.** Sample records:
   ```sh
   graph nodes --type=T --fields=id,evidences --limit=10
   ```
   Check that evidence includes meaningful `source`, `locator`, and `note` values.

### Source verification

1. Select 5–10 records at random:
   ```sh
   graph nodes --type=T --limit=N
   graph edges --limit=N
   ```
2. Open each cited source at its locator.
3. Confirm that the evidence supports the record.
4. If more than a couple of records fail verification, stop and review the mapping method before adding more data.

### Query verification

Use real questions from the pre-flight scope (`query.md`). If the graph cannot answer them, identify the missing entities, relationships, or properties and record the next mapping task in the ledger.

## 15. Keeping the graph fresh

Sources change after the initial mapping. Use `maintenance.md` for the full refresh workflow:

- Compare recorded source commits with current HEAD.
- Identify affected records by searching evidence paths for changed files.
- Re-investigate and verify affected claims.
- Write corrections and additions as new batches.
- Update the progress ledger with the latest verified commit.

The coverage table should make it clear which version of each area was last inspected.

## 16. Pitfalls

| Pitfall | Better approach |
| --- | --- |
| Using an unreviewed template | Adapt the contract to the actual domain |
| Writing records before the contract fits | Inspect sources and define the schema first |
| Mapping only from names and folder structure | Read the source that proves each relationship |
| Treating configuration variable names as actual targets | Follow configuration to its assigned value |
| Stopping after one edge per node pair | Run the relationship sweep |
| Mapping only top-level services | Go finer where evidence and retrieval value justify it |
| Leaving supportable properties empty | Populate them and extend the contract when necessary |
| Creating shared nodes in multiple batches | Search first and assign one owner per shared entity |
| Mapping cross-repository edges before endpoints exist | Complete the inventory across repositories first |
| Using unstable IDs | Use deterministic, scoped IDs |
| Using absolute evidence paths | Use paths relative to the workspace root |
| Editing imported batches | Create a new numbered batch |
| Creating incoherent batches | Split by meaningful area, pass, or document |
| Stopping without updating the ledger | Record coverage, gaps, and the exact next step |
| Recording guesses as facts | Leave them out and list them under `To verify` |
| Including secrets in records | Reference key names, never secret values |