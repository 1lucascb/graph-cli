# Mapping codebases, documents, and many repositories

Use this file when the task is to **build** a graph from sources: one codebase, a folder of documents, research material, or several repositories at once. It assumes you know the basics from SKILL.md and will use contracts.md and batch_imports.md along the way.

Four habits matter most here: build a contract that fits the domain, look hard for every relationship, work in incremental, append-only JSONL batches, and keep a progress ledger so anyone can resume exactly where you stopped.

## Contents
1. Principles
2. Pre-flight
3. Incremental work and the progress ledger
4. Workspace layout
5. ID conventions
6. Evidence and properties
7. The passes
8. Relationships: look for all of them
9. Granularity
10. Mapping a single codebase
11. Mapping many repositories
12. Mapping documents and research material
13. Parallel agents
14. Quality gates
15. Keeping the graph fresh
16. Pitfalls

## 1. Principles

1. **The contract fits the domain.** For a new graph, build the contract with the user or from what you observe (contracts.md, section 3). Templates are a base to adapt, never a finished contract.
2. **Look for everything, record what you can prove.** Search actively for relationships and details. If the sources support it, record it. If you only suspect it, do not record it; write it in the ledger as "to verify".
3. **Be granular when the sources support it.** More node types, more edge types, and finer nodes make retrieval sharper (section 9).
4. **Evidence and properties are the heart of the graph.** Evidence makes every claim verifiable; properties make nodes and edges filterable (section 6).
5. **Incremental and append-only.** All mapping goes through numbered JSONL batch files that are never edited after import (section 3).
6. **Always leave a trail.** Update `batches/PROGRESS.md` after every batch and before you stop: what is covered, what is not, and the exact next step.
7. **Breadth first, then depth.** Inventory the nodes, then the obvious edges, then sweep for the subtle ones.
8. **Deterministic IDs.** Same inputs produce the same IDs, so re-mapping updates records instead of duplicating them.
9. **One verified batch per coherent unit.** Split by area, pass, or document so each file can be tracked, dry-run, and verified. There is no size limit.

## 2. Pre-flight

Before reading any source:

1. **Resume check.** Run `ls batches/` and read `batches/PROGRESS.md` if it exists. If it does, you are resuming: follow "Resuming" in section 3 instead of starting over.
2. **Confirm the working directory.** Run all `graph` commands from the folder that will own `.graph/`. For many repositories this is the **parent folder that contains all clones** (see section 11).
3. **Initialize if needed:** `graph init` (empty contracts) or `graph init --template=NAME` to start from a base.
4. **Look at the contract:** `graph contract --compact`.
   - **Empty, or only a template applied:** do not add records yet. Observe the environment (list directories, read manifests, skim document headings), then build or adapt the contract (contracts.md, section 3). If the user is available, propose it and confirm. If not, proceed with your best observation-based contract, write your assumptions in the ledger, and flag them in your report.
   - **Already fits the domain:** check that it can express what you are about to find. If it cannot, extend it before mapping (contracts.md, section 6).
5. **Check the current graph:** `graph status`. If it is not empty, find out what exists so you extend it instead of duplicating (`graph nodes --type=T --fields=id,name --limit=50`).
6. **Define scope and questions** in one or two sentences. Example: "Map runtime service dependencies of all repos under `./repos`, to answer impact-analysis questions." Questions guide priorities and granularity; they do not limit what you record when the sources support it.
7. **Create `batches/PROGRESS.md`** from the template in section 3, with the scope filled in.
8. **Commit** the `.graph/` and `batches/` folders (`git commit`) so you can recover from mistakes.

## 3. Incremental work and the progress ledger

### Why
Mapping is long. Sessions get interrupted, context fills up, and other agents take over. Append-only JSONL batches plus a progress ledger make the work resumable, reviewable, and honest about what is missing.

### Rules
1. **All mapping writes go through JSONL batch files** in `batches/`, numbered (`0001-...`, `0002-...`). Use `add-node` and `add-edge` only for experiments or one-off fixes, and log those in the ledger.
2. **Append-only.** Never edit a batch file after it was imported. Additions and corrections are new files (batch_imports.md, section 6). Within a session, keep adding new batch files; do not rewrite old ones.
3. **One coherent unit per batch, no size limit.** Split by area, pass, or document (a repository's services, one directory, one document, one pass) so the work is easy to track and review. Let the unit decide the size: a large area normally produces a file with several hundred records or more, depending on the codebase or environment. Do not split into tiny files for the sake of being small, and do not mix unrelated areas into one file. This is a guideline, not a limit.
4. **Cycle after every batch:** dry-run, import, `graph validate`, `graph status`, then **update `batches/PROGRESS.md` before starting the next batch.**
5. **Write the ledger before you stop**, for any reason (context almost full, user interruption, end of session). The "Next step" must be concrete enough that a fresh agent can continue without asking.
6. **If a batch file is written but not imported**, say so in the ledger ("written, not imported") so nobody assumes it is in the graph.

### `batches/PROGRESS.md` template
```markdown
# Mapping progress

## Scope
What is being mapped and which questions the graph should answer.
Workspace root: <path>. ID convention: <pattern>. Evidence paths relative to the workspace root.

## Contract
Based on: <template name or "from scratch">. Key decisions and assumptions:
- ...

## Coverage
| Area | Status | Batch(es) | Commit/version read | Granularity | Notes |
| --- | --- | --- | --- | --- | --- |
| repos/orders (services, workers) | covered | 0002, 0006 | abc1234 | endpoints + tables | relationship sweep done |
| repos/orders (infra, CI) | partial | 0006 | abc1234 | services only | Terraform not read yet |
| repos/billing | not started | | | | |
| docs/architecture.md | skipped | | | | Outdated per README; revisit if user asks |

Status values: `covered` (read fully and relationship sweep done), `partial` (say what is missing), `not started`, `skipped` (say why).

## Not covered yet
- repos/billing: everything
- repos/orders: Terraform, CI workflows
- Cross-repo integration pass

## Where I stopped / next step
Exact, actionable next step (for example: "Map repos/billing/src/payments/ (routes first), batch 0009, then sweep relationships between billing and orders").

## To verify / open questions
- Is `stock-api` also called by the nightly job? (config suggests yes; no call site found)

## Contract changes
- 0005: added property `owner` to API; added edge type DEPENDS_ON

## Deletions and manual edits
- <date>: deleted edge <id> (call removed in def5678)

## Totals after last import
nodes: N, edges: M (from `graph status`)
```

### Resuming
1. Read `batches/PROGRESS.md` completely, then `ls batches/`.
2. Run `graph validate` and `graph status`. Compare the totals with the ledger.
3. If the last batch is marked "written, not imported", dry-run it and import it.
4. Do **not** redo areas marked `covered` unless the sources changed (maintenance.md).
5. Continue at "Next step". Update the ledger after the first batch you complete.

## 4. Workspace layout

Recommended, with one workspace for everything:

```text
workspace/                 <- run `graph` here
  .graph/
  batches/                 <- numbered JSONL batch files + PROGRESS.md
    0001-initial-inventory.jsonl
    0002-orders-structure.jsonl
    PROGRESS.md
  repos/                   <- all repositories cloned side by side
    orders/
    billing/
    stock/
  docs/                    <- optional: documents to map
```

Why one parent folder:
- A single `.graph/` can hold cross-repository edges.
- Evidence paths are uniform and relative to the workspace root (`repos/orders/src/api.py`), so anyone can open them.
- Search by file path works across all repos (`graph search repos/orders/ --in=evidences`).

## 5. ID conventions

IDs must match `^[a-z0-9][a-z0-9._-]*$` (lowercase letters and digits first, then also `.`, `_`, `-`).

Recommended pattern: `<scope>.<kind-or-area>.<name>`, lowercase, kebab-case inside segments.

| What | Example |
| --- | --- |
| Repository | `repo.orders` |
| Service inside a repo | `orders.api` or `orders.orders-api` |
| Endpoint | `orders.api.post-orders` |
| Worker | `orders.worker.invoice-sync` |
| Datastore | `orders.db.main` |
| Table | `orders.db.main.orders-table` |
| Shared/external thing | `ext.stripe`, `shared.kafka.orders-topic` |
| Document | `doc.architecture-overview` |
| Document section | `doc.architecture-overview.4-data-flow` |
| Decision | `adr.0007-use-kafka` |

Rules:
- **Prefix with the repo (scope)** so parallel work cannot collide and ownership is obvious.
- **Never use timestamps, random values, or line numbers** in IDs.
- **Be consistent.** Decide the pattern once, write it in the ledger, and reuse it.
- **Shared resources get a shared scope** (`shared.`/`ext.`) and are created exactly once, by whoever maps them first. Other repos only create **edges** to them.
- Edge IDs are generated; you control identity through type + endpoints + properties.

## 6. Evidence and properties

Evidence and properties are what make retrieval precise. Evidence answers "how do we know?", and properties answer "which ones match?". Treat both as part of the record, not as decoration.

### Evidence
Follow SKILL.md: `source`, `locator`, `note`, optional `commit`.

- `source` is **relative to the workspace root** (`repos/orders/src/api.py`), never absolute, so it works on every machine.
- `locator` for code: `{"start_line": 12, "end_line": 28}`. For documents: `{"section": "3.2 Retries"}` or `{"page": 14}`.
- `note`: one sentence saying what the evidence shows ("Route handler for POST /orders").
- `commit`: the commit hash you read (`git -C repos/orders rev-parse --short HEAD`). Cheap to add, and it lets you detect stale evidence later.
- **Multiple evidences are better than one** for important records (the call site and the config that sets the URL; the client and the route).
- Point to the most specific place: the call site, not the folder.

### Properties
- **Fill every property the contract defines that the sources support.** Properties are how agents filter later (`--p.language=Go`, `--properties '{...}'`), so a missing value makes a node harder to find.
- **Put stable, filterable facts in properties**, and explanations in `description`. Nodes: language, framework, version, environment, port, owner, visibility, status. Edges: protocol, method, path, sync or async, authentication, frequency, criticality.
- **Do not guess values.** If the sources do not say, leave an optional property out. If a required property is unknowable, the contract is wrong for this domain: fix it (contracts.md, section 6) instead of inventing values.
- **If you keep burying the same fact in descriptions**, it deserves a property. Add it to the contract and backfill.

### Quality bar per record
| Record | Minimum |
| --- | --- |
| Node | Recognizable `name`, a one or two sentence `description`, every supportable property, at least one evidence |
| Edge | A `description` explaining why it exists, supportable properties, at least one evidence |
| Important node or edge | Two or more evidences, ideally from both sides of the relationship |

## 7. The passes

Do not try to do everything in one sweep. Work in passes and import after each one. Record each pass per area in the ledger.

1. **Inventory pass: nodes.** Find the things: repositories, services, endpoints, workers, datastores, queues, documents. Output: batches of nodes with evidence and properties.
2. **Structure pass: intra-scope edges.** Containment and obvious relationships inside a repo or document. Output: batch of edges between nodes of that scope.
3. **Integration pass: cross-scope edges.** Calls, shared datastores, shared queues, document-to-code links between scopes. This is the most valuable and most error-prone pass; do it after every endpoint node exists.
4. **Relationship sweep.** Go back over every node and look for relationships you have not recorded yet (section 8). Output: additional edge batches.
5. **Refinement pass.** Add descriptions, properties, extra evidence; fix what verification found; go finer where the sources support it (section 9).

After each pass: dry-run, import, `graph validate`, `graph status`, update the ledger (see section 14).

## 8. Relationships: look for all of them

Two nodes are often connected in more than one way, and each way is worth recording. A service can call another, depend on its library, and read the same database. Each relationship answers a different question later, so each gets its own edge with its own type, properties, description, and evidence.

### Rules for multiple edges
- **Different edge types between the same two nodes are always fine.** `orders-api CALLS stock-api` and `orders-api DEPENDS_ON stock-api` can both exist.
- **The same edge type twice between the same nodes** needs different properties and a non-empty description on each (for example two `CALLS` with different `method` or `path`).
- **Direction matters.** Ask both ways: A calls B, and does B call A (callbacks, webhooks, events)?
- **A true duplicate** (same type, endpoints, properties) is rejected, so if the dry run reports one, you probably found the same fact twice.

### Sweep checklist
For each node, ask these questions and look for evidence for each answer. Skip questions that do not apply to the domain.

| Question | Typical edge types |
| --- | --- |
| What does it call or depend on? Who calls or depends on it? | `CALLS`, `DEPENDS_ON` |
| What data does it read, write, or own? | `READS`, `WRITES`, `OWNS` |
| What does it publish or consume? | `PUBLISHES`, `CONSUMES` |
| What configures it, and what secrets or keys does it use (names only)? | `CONFIGURED_BY`, `USES_CONFIG` |
| Where is it hosted or deployed? What builds it? | `DEPLOYED_ON`, `BUILT_BY` |
| Who owns it? Which team? | `OWNED_BY` |
| Which documents describe or decide things about it? | `DESCRIBES`, `DECIDES` |
| What replaced it, or what does it replace? | `SUPERSEDES` |
| For documents and research: what does it define, cite, support, or contradict? | `DEFINES`, `CITES`, `SUPPORTS`, `CONTRADICTS` |

These are examples. Use the edge types in your contract, and add new types when you find a relationship the contract cannot express (contracts.md, section 6).

### Procedure
1. List what is recorded for a node: `graph edges --from=ID --fields=id,type,target,description` and `graph edges --to=ID --fields=id,type,source,description`.
2. Go through the checklist and look for evidence of each relationship that is **not** in that list.
3. For every connected pair, ask "is there another relationship between these two?"
4. Write the new edges in a batch with evidence and properties.
5. Note nodes you could not finish in the ledger.

### Finding gaps with the graph
- `graph status --check=orphans` shows nodes with no edges at all.
- Nodes with a single edge are suspects too: `graph edges --from=ID` and `--to=ID` quickly show them.
- Compare `by_type` counts: a type with many nodes and few edges of a given kind (for example many `API` nodes and few `READS`) points at what to search next.

### Exhaustive in looking, strict in recording
Searching hard is encouraged. Recording without evidence is not. A relationship inferred from names alone is a lead for the ledger ("to verify"), not an edge.

## 9. Granularity

Default to **as fine as the sources support**, wherever a finer node or edge would help someone retrieve something precisely. Coarse graphs answer "what services exist"; granular graphs also answer "which endpoint writes this table" and "which section defines this term".

### What finer can mean
| Domain | Finer nodes |
| --- | --- |
| Code | Endpoints and routes, modules, jobs, database tables, topics, config keys, feature flags, external integrations, libraries |
| Documents | Sections, requirements, concepts, decisions, stakeholders |
| Research | Claims, methods, datasets, experiments, results |
| Infrastructure | Clusters, namespaces, deployments, buckets, networks |
| Data pipelines | Jobs, tables, schemas, sources, sinks |

### More types are welcome
Add a node or edge type when things need to be filtered or related differently (contracts.md, section 4). A contract with many specific types usually retrieves better than one with a few generic ones.

### Where to stop
Go finer while you can attach evidence and someone could plausibly ask about it or traverse through it. Stop at details nobody would query (every getter, every private helper) or where you cannot point to a source.

### Work in layers
Map coarse first, then add finer nodes area by area in later batches. Record in the ledger which area is at which granularity, so nobody wonders why `billing` has endpoints and `stock` does not yet.

## 10. Mapping a single codebase

### Where to look
| You want | Look at |
| --- | --- |
| Services and entry points | Repo root layout, `main`/`app` files, Dockerfiles, `docker-compose.yml`, Helm charts, Procfiles |
| Languages, frameworks, versions | Manifests: `pyproject.toml`, `requirements.txt`, `go.mod`, `package.json`, `pom.xml`, `build.gradle` |
| Inbound interfaces | Route definitions, controllers, OpenAPI/proto files, handler registrations |
| Outbound calls | HTTP/gRPC clients, SDK wrappers, config with base URLs, service discovery names |
| Datastores and tables | Connection settings (variable names, not secrets), ORM models, migrations, repository classes |
| Queues and events | Producer/consumer code, topic names in config, broker clients |
| Infrastructure | Terraform, CloudFormation, Kubernetes manifests |
| Build and deploy | CI workflows, Makefiles, release scripts |
| Ownership and boundaries | README files, CODEOWNERS, ADRs |

### Procedure
1. Read the top-level layout and README, then the manifests.
2. Observe and confirm the contract can express what you see (section 2, step 4).
3. List candidate nodes (services, workers, datastores, queues, endpoints) and the file that proves each exists.
4. For each service, find its inbound and outbound integrations. **Follow config to the real target** (an env var named `STOCK_URL` does not prove the callee; check where it is set).
5. Write the node batch, import, then the edge batch, import. Update the ledger after each.
6. Run the relationship sweep (section 8) and go finer where useful (section 9).

### Secrets
Never put secrets, tokens, or credentials in properties, descriptions, or evidence notes. Reference the variable name or the config key instead.

## 11. Mapping many repositories

### Setup
1. Put all clones side by side under the workspace (`repos/<name>`).
2. Run `graph` from the workspace root.
3. Create a `REPOSITORY` node per repository (`repo.<name>`) with evidence pointing at its root files, and use `CONTAINS`-style edges from it to its components if the contract has one.
4. Record the commit of each repository in evidences (`commit` field) and in the ledger coverage table when you map it.

### Procedure
1. **Inventory every repository first** (pass 1 for all repos) so that cross-repo edges have endpoints.
2. **Map each repository's internal structure** (pass 2), one batch per repository or per area: `batches/0003-repo-orders.jsonl`.
3. **Then the integration pass** across repositories (pass 3). Typical evidence: the client code in repo A **and** the route or contract in repo B. Where both sides exist, cite both.
4. **Shared infrastructure** (databases, topics, gateways) appears in several repos. Create the node once with a shared ID, and let each repo contribute edges. Before creating one, check it does not exist: `graph search kafka --kind=nodes --in=id,name`.
5. **External services** (payment providers, SaaS) get an `ext.` ID and a node typed accordingly, with evidence from the integration code.
6. **Relationship sweep across repos:** for each pair of repositories that interact, list every way they interact (calls, shared tables, shared topics, shared libraries, deployment coupling).

### Naming collisions
Two repos can contain a service with the same short name (`api`). The scope prefix (`orders.api` vs `billing.api`) prevents collisions. Never reuse an ID for two different things.

### Order of work
```text
1. contract (shared across all repos)
2. batch 0001: repo nodes + obvious components for ALL repos
3. batches 0002..N: structure batches per repo and area
4. batch N+1: cross-repo edges
5. relationship sweep and refinement batches
(update batches/PROGRESS.md after every batch)
```

## 12. Mapping documents and research material

For architecture docs, ADRs, specs, PDFs, wiki exports, papers, and notes.

1. **Create a node per document** (`doc.*`) with `format` and `version` (or equivalent properties) if the contract has them. Evidence: the file path.
2. **Go finer than the document** when it helps: sections, requirements, claims, methods, datasets. Each gets its own node with a locator in its evidence.
3. **Extract the entities the document is about** (concepts, decisions, systems). Reuse existing nodes where they exist (search first) rather than creating parallel "document versions" of the same thing.
4. **Link with typed edges**: `DESCRIBES`, `DEFINES`, `DECIDES`, `SUPERSEDES`, `REFERENCES`, `CITES`, `SUPPORTS`, `CONTRADICTS`. Each edge's evidence carries a **section or page locator**: `{"source":"docs/architecture.md","locator":{"section":"4 Data flow"},"note":"Describes the order-to-stock call"}`.
5. **Connect documents to code** when the document names a system that exists in the graph. Use the existing node ID, and cite the passage.
6. **Conflicts between documents** (or document vs. code) are valuable: record both as separate edges with descriptions, and mention the conflict in the ledger. Do not silently pick one.
7. **Long documents:** work section by section, one batch per document (or per group of short documents), and mark partial coverage in the ledger.

## 13. Parallel agents

Parallel reading is fine; **parallel writing is not.**

- Assign **one scope** (repository or document set) per producer agent. Producers write their own batch file and never run `graph import`.
- One importer (or the orchestrating agent) imports the files **sequentially**, with a dry run each time. Details and the handoff template are in batch_imports.md.
- Give every producer the same inputs: the contracts, the ID convention, the evidence convention, the granularity expectations, and the list of already existing shared nodes.
- Each producer's handoff note states what it **covered**, what it **did not cover**, and where it stopped. The importer merges this into `batches/PROGRESS.md`.
- Tell producers to **stop and report** if they need a type or property that is not in the contract. The orchestrator decides whether to change the contract (contracts.md, section 6), then re-runs the affected producers. (A single agent working alone may extend the contract itself and note it in the ledger.)
- Cross-repo edges are best written by one agent that sees the inventory of all repos, after the structure batches are imported.

## 14. Quality gates

Run after each import and before declaring a pass finished.

```sh
graph validate
graph status --check=orphans,no-evidence,no-description,components --limit=20
```

| Finding | Meaning | Action |
| --- | --- | --- |
| Validate errors | Contract mismatch | Fix records or contract (contracts.md) |
| Orphans | Nodes with no edges | Missing edges, or nodes that do not belong. Investigate each; some orphans are legitimate (a repo with no integrations) |
| No evidence | Unverifiable claims | Add evidence or remove the record |
| No description (edges) | Hard to understand relationships | Add one sentence |
| Many components | Graph is split | Expected per repo before the integration pass; unexpected afterwards (missing cross edges) |

Density and completeness checks (not covered by `status`):
1. **Relationship density.** Sample nodes (`graph edges --from=ID`, `--to=ID`). If most have one or two edges, run the relationship sweep (section 8).
2. **Property completeness.** Sample `graph nodes --type=T --fields=id,properties --limit=20`. If common properties are missing, backfill with a `replace` batch.
3. **Evidence quality.** Sample `graph nodes --type=T --fields=id,evidences --limit=10`: do they have `source`, `locator`, and `note`?

Then sample-check against the sources:
1. Pick 5 to 10 records at random (`graph nodes --type=T --limit=N`, `graph edges --limit=N`).
2. Open each cited `source` at its `locator` and confirm the claim.
3. If more than a couple fail, stop and review the method before adding more.

Finally, test with real questions (query.md): can you answer the questions you defined in pre-flight? If not, the missing piece tells you what to map next. Write it in the ledger.

## 15. Keeping the graph fresh

Once the graph is mapped, sources keep changing. maintenance.md has the full workflow: compare recorded commits with current HEAD, find affected records by searching evidences for changed paths, re-verify, and refresh with new batches. The coverage table in `batches/PROGRESS.md` records which commit each area was last verified at.

## 16. Pitfalls

| Pitfall | Fix |
| --- | --- |
| Mapping with an unreviewed template | Templates are a base; adapt the contract to the domain first |
| Starting to add records before the contract fits | Observe, propose, confirm, then map |
| Mapping from names and folder structure only | Read the code that proves each relationship |
| Treating config variable names as targets | Follow them to where they are set or documented |
| Stopping after one edge per node pair | Run the relationship sweep; record every evidenced relationship |
| Too coarse (only top-level services and one `CALLS` edge) | Go finer where the sources support it, add types and edge types |
| Leaving properties empty | Fill every supportable property; add missing ones to the contract |
| Creating the same shared node in several batches | Search first; one owner per shared node |
| Cross-repo edges before endpoint nodes exist | Finish the inventory pass for all repos first |
| IDs that change between runs | Deterministic, scoped IDs only |
| Absolute paths in evidence | Always relative to the workspace root |
| Editing an imported batch file | Never; write a new numbered batch |
| Batches without a clear unit (everything in one file, or dozens of tiny files) | One file per coherent area, pass, or document; size follows the unit, and each file is dry-run and verified |
| Stopping without updating the ledger | Write coverage, not-covered list, and exact next step before you stop |
| Silent guesses | Leave it out and put it under "to verify" in the ledger |
| Secrets in descriptions or evidence | Reference the key name, never the value |