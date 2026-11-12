# Mapping codebases, documents, and many repositories

Use this file when the task is to **build** a graph from sources: one codebase, a folder of documents, or several repositories at once. It assumes you know the basics from SKILL.md and will use contracts.md and batch_imports.md along the way.

## Contents
1. Principles
2. Pre-flight
3. Workspace layout
4. ID conventions
5. Evidence conventions
6. The passes
7. Mapping a single codebase
8. Mapping many repositories
9. Mapping documents
10. Parallel agents
11. Quality gates
12. Keeping the graph fresh
13. Pitfalls

## 1. Principles

1. **Evidence or it does not go in.** Every node and edge must come from something you read. If you inferred it from naming alone, either verify it or leave it out.
2. **Map for questions, not completeness.** A focused graph that answers real questions beats an exhaustive one nobody trusts. Decide the questions first.
3. **Breadth first, then depth.** Inventory the nodes, then the obvious edges, then the subtle ones.
4. **Unknown is a valid answer.** Prefer a missing edge over a wrong edge. Record uncertainty in the handoff note, not in the graph.
5. **Deterministic and repeatable.** Same inputs should produce the same IDs so re-mapping updates records instead of duplicating them.
6. **Small verified batches** beat one giant unverified import.

## 2. Pre-flight

Before reading any source:

1. **Confirm the working directory.** Run all `graph` commands from the folder that will own `.graph/`. For many repositories this is the **parent folder that contains all clones** (see section 8).
2. **Initialize if needed:** `graph init`.
3. **Read or create the contracts.** If they are still the starter, design them for this domain first (contracts.md). Do not map with a contract that cannot express what you will find.
4. **Check the current graph:** `graph status`. If it is not empty, find out what exists so you extend it instead of duplicating (`graph nodes --type=T --fields=id,name --limit=50`).
5. **Define scope and questions** in one or two sentences. Example: "Map runtime service dependencies of all repos under `./repos`, to answer impact-analysis questions."
6. **Back up** (`git commit` the `.graph/` folder).

## 3. Workspace layout

Recommended, with one workspace for everything:

```text
workspace/                 <- run `graph` here
  .graph/
  batches/                 <- JSONL batch files (see batch_imports.md)
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

## 4. ID conventions

IDs must match `^[a-z0-9][a-z0-9._-]*$` (lowercase letters and digits first, then also `.`, `_`, `-`).

Recommended pattern: `<scope>.<kind-or-area>.<name>`, lowercase, kebab-case inside segments.

| What | Example |
| --- | --- |
| Repository | `repo.orders` |
| Service inside a repo | `orders.api` or `orders.orders-api` |
| Worker | `orders.worker.invoice-sync` |
| Datastore | `orders.db.main` |
| Shared/external thing | `ext.stripe`, `shared.kafka.orders-topic` |
| Document | `doc.architecture-overview` |
| Decision | `adr.0007-use-kafka` |

Rules:
- **Prefix with the repo (scope)** so parallel work cannot collide and ownership is obvious.
- **Never use timestamps, random values, or line numbers** in IDs.
- **Be consistent.** Decide the pattern once, write it in the batches README, and reuse it.
- **Shared resources get a shared scope** (`shared.`/`ext.`) and are created exactly once, by whoever maps them first. Other repos only create **edges** to them.
- Edge IDs are generated; you control identity through type + endpoints + properties.

## 5. Evidence conventions

Follow SKILL.md: `source`, `locator`, `note`, optional `commit`.

- `source` is **relative to the workspace root** (`repos/orders/src/api.py`), never absolute, so it works on every machine.
- `locator` for code: `{"start_line": 12, "end_line": 28}`. For documents: `{"section": "3.2 Retries"}` or `{"page": 14}`.
- `note`: one sentence saying what the evidence shows ("Route handler for POST /orders").
- `commit`: the commit hash you read (`git -C repos/orders rev-parse --short HEAD`). Cheap to add, and it lets you detect stale evidence later.
- **Multiple evidences are better than one** for important edges (the call site and the config that sets the URL).
- Point to the most specific place: the call site, not the folder.

## 6. The passes

Do not try to do everything in one sweep. Work in passes and import after each one.

1. **Inventory pass: nodes.** Find the things: repositories, services, workers, datastores, queues, documents. Output: one batch of nodes with evidence.
2. **Structure pass: intra-scope edges.** Containment and obvious relationships inside a repo or document. Output: batch of edges between nodes of that scope.
3. **Integration pass: cross-scope edges.** Calls, shared datastores, shared queues, document-to-code links between scopes. This is the most valuable and most error-prone pass; do it after every endpoint node exists.
4. **Refinement pass.** Add descriptions, properties, extra evidence; fix what verification found.

After each pass: dry-run, import, `graph validate`, `graph status` (see section 11).

## 7. Mapping a single codebase

### Where to look
| You want | Look at |
| --- | --- |
| Services and entry points | Repo root layout, `main`/`app` files, Dockerfiles, `docker-compose.yml`, Helm charts, Procfiles |
| Languages and frameworks | Manifests: `pyproject.toml`, `requirements.txt`, `go.mod`, `package.json`, `pom.xml`, `build.gradle` |
| Inbound interfaces | Route definitions, controllers, OpenAPI/proto files, handler registrations |
| Outbound calls | HTTP/gRPC clients, SDK wrappers, config with base URLs, service discovery names |
| Datastores | Connection strings (variable names, not secrets), ORM models, migrations, repository classes |
| Queues and events | Producer/consumer code, topic names in config, broker clients |
| Infrastructure | Terraform, CloudFormation, Kubernetes manifests |
| Ownership and boundaries | README files, CODEOWNERS, ADRs |

### Procedure
1. Read the top-level layout and README, then the manifests.
2. List candidate nodes (services, workers, datastores, queues) and the file that proves each exists.
3. For each service, find its inbound and outbound integrations. **Follow config to the real target** (an env var named `STOCK_URL` does not prove the callee; check where it is set).
4. Write the node batch, import, then the edge batch, import.

### Granularity
Map at the level the questions need. For "what calls what" use services and datastores, not classes and functions. Going finer multiplies noise and cost. If you need finer detail for one area, add a dedicated type for it in the contract (for example `MODULE`) and map only that area.

### Secrets
Never put secrets, tokens, or credentials in properties, descriptions, or evidence notes. Reference the variable name or the config key instead.

## 8. Mapping many repositories

### Setup
1. Put all clones side by side under the workspace (`repos/<name>`).
2. Run `graph` from the workspace root.
3. Create a `REPOSITORY` node per repository (`repo.<name>`) with evidence pointing at its root files, and use `CONTAINS`-style edges from it to its components if the contract has one.
4. Record the commit of each repository in evidences (`commit` field) when you map it.

### Procedure
1. **Inventory every repository first** (pass 1 for all repos) so that cross-repo edges have endpoints.
2. **Map each repository's internal structure** (pass 2), one batch per repository: `batches/0003-repo-orders.jsonl`.
3. **Then the integration pass** across repositories (pass 3). Typical evidence: the client code in repo A **and** the route or contract in repo B. Where both sides exist, cite both.
4. **Shared infrastructure** (databases, topics, gateways) appears in several repos. Create the node once with a shared ID, and let each repo contribute edges. Before creating one, check it does not exist: `graph search kafka --kind=nodes --in=id,name`.
5. **External services** (payment providers, SaaS) get an `ext.` ID and a node typed accordingly, with evidence from the integration code.

### Naming collisions
Two repos can contain a service with the same short name (`api`). The scope prefix (`orders.api` vs `billing.api`) prevents collisions. Never reuse an ID for two different things.

### Order of work
```text
1. contract (shared across all repos)
2. batch 0001: repo nodes + obvious components for ALL repos
3. batches 0002..N: one structure batch per repo
4. batch N+1: cross-repo edges
5. refinement batches
```

## 9. Mapping documents

For architecture docs, ADRs, specs, PDFs, wiki exports.

1. **Create a node per document** (`doc.*`) with `format` and `version` if the contract has them. Evidence: the file path.
2. **Extract the entities the document is about** (concepts, decisions, systems). Reuse existing nodes where they exist (search first) rather than creating parallel "document versions" of the same thing.
3. **Link with typed edges**: `DESCRIBES`, `DEFINES`, `DECIDES`, `SUPERSEDES`, `REFERENCES`. Each edge's evidence carries a **section or page locator**: `{"source":"docs/architecture.md","locator":{"section":"4 Data flow"},"note":"Describes the order-to-stock call"}`.
4. **Connect documents to code** when the document names a system that exists in the graph. Use the existing node ID, and cite the passage.
5. **Conflicts between documents** (or document vs. code) are valuable: record both as separate edges with descriptions, and mention the conflict in the handoff note. Do not silently pick one.
6. **Long documents:** work section by section, one small batch per document.

## 10. Parallel agents

Parallel reading is fine; **parallel writing is not.**

- Assign **one scope** (repository or document set) per producer agent. Producers write their own batch file and never run `graph import`.
- One importer (or the orchestrating agent) imports the files **sequentially**, with a dry run each time. Details and the handoff template are in batch_imports.md.
- Give every producer the same inputs: the contracts, the ID convention, the evidence convention, and the list of already existing shared nodes.
- Tell producers to **stop and report** if they need a type that is not in the contract. The orchestrator decides whether to change the contract (contracts.md), then re-runs the affected producers.
- Cross-repo edges are best written by one agent that sees the inventory of all repos, after the structure batches are imported.

## 11. Quality gates

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

Then sample-check:
1. Pick 5 to 10 records at random (`graph nodes --type=T --limit=N`, `graph edges --limit=N`).
2. Open each cited `source` at its `locator` and confirm the claim.
3. If more than a couple fail, stop and review the method before adding more.

Finally, test with real questions (query.md): can you answer the questions you defined in pre-flight? If not, the missing piece tells you what to map next.

## 12. Keeping the graph fresh

- **Re-map only what changed.** Compare current commits with the `commit` recorded in evidences; map the repos that moved.
- **Find records affected by a file change:**
  ```sh
  graph search repos/orders/src/api.py --in=evidences --snippets
  ```
- **Update with replace batches** (new numbered batch, complete records, `--on-conflict=replace`, dry-run first).
- **Delete what no longer exists** with `graph delete`, and note it in the batches README.
- **Version the graph.** Commit `.graph/` and `batches/` together after each mapping session.

## 13. Pitfalls

| Pitfall | Fix |
| --- | --- |
| Mapping from names and folder structure only | Read the code that proves each relationship |
| Treating config variable names as targets | Follow them to where they are set or documented |
| Creating the same shared node in several batches | Search first; one owner per shared node |
| Cross-repo edges before endpoint nodes exist | Finish the inventory pass for all repos first |
| Too granular (every class and function) | Match granularity to the questions; add a dedicated type only for areas that need it |
| IDs that change between runs | Deterministic, scoped IDs only |
| Absolute paths in evidence | Always relative to the workspace root |
| One huge import | Small batches per pass and per repo, each dry-run and verified |
| Silent guesses | Leave it out and note it in the handoff |
| Secrets in descriptions or evidence | Reference the key name, never the value |