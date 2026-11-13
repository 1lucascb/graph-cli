# Maintenance: keeping the graph fresh

Use this file when sources have changed since the graph was mapped (new commits, edited documents, deleted or renamed files), when the user asks whether the graph is still accurate, or when you are auditing an old graph before relying on it.

A graph that is silently out of date is worse than no graph, because agents trust it. The goal of this workflow is to find **which records are affected by a change**, re-verify only those, and leave a trail of what was checked.

## Contents
1. What "stale" means
2. What you need in place
3. The refresh workflow
4. Triage: what to do per change type
5. Applying fixes
6. Multiple repositories and parallel work
7. Documents and non-git sources
8. Periodic audit by sampling
9. Maintenance log and templates
10. Pitfalls
11. Checklist

## 1. What "stale" means

| Situation | Effect on the graph |
| --- | --- |
| Cited file modified | Claim may still hold, may have moved (line numbers drifted), or may be false |
| Cited file deleted | Evidence points at nothing; the claim may be gone |
| Cited file renamed or moved | Claim probably holds, but `source` is wrong |
| New files added | The graph is **missing** nodes or edges (search cannot find these) |
| Thing removed without touching cited files | Rare; usually found by sampling or while querying |

Two different problems, two different tools:
- **Wrong or outdated records:** found by searching evidences for changed file paths (this file, sections 3 to 5).
- **Missing records:** found by re-inventorying changed areas (section 4, "Added files") and by periodic audits (section 8).

## 2. What you need in place

1. **Evidence with `source` and `commit`.** The `commit` is what tells you *when* a claim was verified. Records without it can still be checked, but you cannot tell how old they are (section 10). Line locators (`locator`, or flat `start_line`/`end_line`) are used only when you refresh a record.
2. **A record of what was mapped at which commit.** Keep it in the coverage table of `batches/PROGRESS.md` (the `Commit/version read` column) or in the maintenance log (section 9): one line per repository with the commit that was last fully verified.
3. **All repositories cloned under the workspace** (`repos/<name>`), as in mapping.md, so evidence paths like `repos/orders/src/api.py` resolve from the workspace root.
4. **A clean starting point.** `graph validate`, `graph status`, and a commit or backup of `.graph/` before changing anything.

## 3. The refresh workflow

Run it **per repository**. Work from the workspace root.

### Step 1: baseline
```sh
graph validate
graph status --check=orphans,no-evidence --limit=10
```
Know what was already broken, so you do not blame your refresh for it. Back up: `git add .graph batches && git commit -m "graph: before refresh of orders"`.

### Step 2: compare commits
```sh
git -C repos/orders rev-parse --short HEAD          # current
grep orders batches/PROGRESS.md                      # last verified commit (or your log)
```
- Same commit: nothing changed for this repo. Skip to the next repo.
- Check the old commit is still reachable: `git -C repos/orders merge-base --is-ancestor OLD HEAD`. If this fails (force push, shallow clone, history rewrite), you cannot diff reliably. Treat the whole repo as changed and use the sampling audit (section 8) or re-map it (mapping.md).
- Check the working tree is clean: `git -C repos/orders status --porcelain`. Uncommitted changes mean evidence at `HEAD` may not match what you read.

### Step 3: list changed files
```sh
git -C repos/orders diff --name-status -M OLD..HEAD
```
Status letters you care about:
- `M` modified, `D` deleted, `A` added, `R100`/`R085` renamed (similarity percentage), `C` copied.

Ignore files the graph could never cite (tests, docs, lockfiles) **only if** you know the mapping did not use them. The next step proves it by search: if no record cites a file, it needs no action.

### Step 4: find affected records
For every changed path (use the old path for deletes and renames):

```sh
graph search repos/orders/src/api.py --in=evidences --fields=id,type,source,target
```
This returns every node and edge whose evidence mentions that path. It is a substring match, so `src/api.py` also matches `src/api.py.bak`; that is fine, just ignore false positives.

To process a whole diff at once:
```sh
git -C repos/orders diff --name-status -M OLD..HEAD | while IFS=$'\t' read -r status old new; do
  echo "== $status $old ${new:+-> $new}"
  graph search "repos/orders/$old" --in=evidences --fields=id,type,source,target
done > maintenance/worklist-orders.txt
```
Paths containing tabs or newlines break this loop (rare). Paths with spaces are fine because the delimiter is a tab.

Read the worklist and keep only entries with results. **Affected records = the worklist.** Everything else is untouched by this change.

### Step 5: triage and re-verify
For each affected record, open it (`graph nodes ID` or `graph edges EDGE_ID`), then open the cited file **at HEAD** and apply the decision table in section 4. Record the outcome next to each entry in the worklist (`ok`, `moved`, `changed`, `deleted`, `path-renamed`).

### Step 6: look for what is new
Search cannot find things that were never mapped. For files with status `A`, and for modified files in areas that define structure (routes, clients, configs, manifests, infrastructure), re-run the relevant part of the inventory in mapping.md section 10. Check new files against existing nodes first (`graph search NAME --kind=nodes --in=id,name`) to avoid duplicates.

### Step 7: apply fixes
See section 5. Use batches for many changes, `edit` or `delete` for a few.

### Step 8: verify and record
```sh
graph validate
graph status --check=orphans,no-evidence --limit=20
```
Compare against the baseline from Step 1. New orphans usually mean you deleted a node's only edges or removed an edge it depended on. Then update the "last verified commit" for the repository and commit `.graph/`, `batches/`, and the maintenance log together.

## 4. Triage: what to do per change type

### Modified file (`M`)
Open each affected record's cited `source` at its locator **in the current file**, then pick one outcome:

| Outcome | How to recognize it | Action |
| --- | --- | --- |
| Still true, same place | Lines unchanged | Bump `commit` in that evidence (this counts as re-verified) |
| Still true, moved | Same code, different lines | Update the locator and `commit` |
| True but details changed | E.g. protocol, method, or target differs | Fix properties, description, and evidence; use a `replace` batch or `edit` |
| No longer true | The call, route, or table access is gone | Delete the edge (or node), unless other evidence still supports it |
| Cannot tell | Code was refactored beyond recognition | Re-map that area (mapping.md); do not guess |

Only bump `commit` after you actually re-read the cited code. Bumping without checking turns the commit field into a lie.

### Deleted file (`D`)
1. List records citing it (Step 4).
2. If a record has **other evidence** that still holds, remove only the dead evidence and keep the record.
3. If the dead file was the **only** evidence, find out why it disappeared: moved (search the repo for the same symbol), replaced, or the feature was removed.
4. Moved or replaced: re-point the evidence to the new location. Removed: delete the record.

### Renamed or moved file (`R`)
Git reports the old and new path. If similarity is high (for example `R100`), the content is the same, so update `source` to the new path and `commit` to HEAD; no deeper verification is needed. For lower similarity (below about `R080`), treat it as a modification as well.

### Added file (`A`) and structural changes
Not discoverable through search. Inspect the new files in the areas the mapping covers (new routes, clients, workers, migrations, manifests, infrastructure) and map new nodes and edges in a refresh batch.

### Dependency or config changes
A modified manifest or config can change relationships without touching the code that was cited: a base URL, a queue name, a datastore. If the diff touches these, check the edges and properties derived from them even when search finds no record citing that exact file.

## 5. Applying fixes

### Small number of records
```sh
graph edit node orders.api --evidences '[...complete new list...]'
graph edit edge EDGE_UUID --description "..." --p.protocol=https
graph delete edge EDGE_UUID
```
Remember: `--evidences` **replaces the whole list**, so read the current list first and send it back with your change. Get edge IDs with `--fields=id,...`.

### Many records
Write a new numbered batch with **complete records** and import with `replace`:
```sh
graph import batches/0012-refresh-orders-abc1234.jsonl --on-conflict=replace --dry-run
graph import batches/0012-refresh-orders-abc1234.jsonl --on-conflict=replace
```
- The dry-run summary should say `updated` roughly equal to the number of records you changed and `created` equal to genuinely new ones. A large `unchanged` count means you re-sent records you did not touch (harmless, but check it is intentional).
- Never edit earlier batch files. Corrections are new files (batch_imports.md, section 6).
- New nodes and edges discovered in Step 6 go in the same batch or a separate "additions" batch with `--on-conflict=skip`.

### Deletions
`graph delete node ID` also removes every connected edge, so check with `graph edges --from=ID` and `graph edges --to=ID` what will disappear before deleting. Record every deletion in the maintenance log, because replaying old batches would bring the records back.

## 6. Multiple repositories and parallel work

- **Refresh each repository independently.** One repo's diff only affects records citing that repo's paths, plus cross-repo edges that cite both sides.
- **Cross-repo edges:** an edge from repo A to repo B usually has evidence in both repos. A change in **either** repo can invalidate it. Step 4 finds it when you search the changed path in that repo's turn, so make sure you refresh every changed repo.
- **Parallel agents:** assign one repository per producer agent, each writing `batches/NNNN-refresh-<repo>-<commit>.jsonl` plus the worklist. Imports stay **sequential**, by a single importer (batch_imports.md, sections 7 and 8). Deletions proposed by producers are listed in their handoff note and executed by the importer.
- **Shared nodes** (databases, queues) are refreshed once, by one owner, to avoid conflicting `replace` batches.
- **Order:** refresh structure first (nodes), then edges, then cross-repo edges, as in the original mapping.

## 7. Documents and non-git sources

For documents inside a git repository, the same commit-based workflow applies.

For files outside git (shared drives, exports, PDFs):
- Record a **content hash or modified date** per document in `batches/PROGRESS.md` or the maintenance log when you map it (for example `sha256sum docs/architecture.pdf`).
- On refresh, recompute and compare. A changed hash means every record citing that document is affected: `graph search docs/architecture.pdf --in=evidences`.
- Section or page locators are fragile when a document is edited. Re-read the cited section, and if sections were renumbered, update the locators.
- If you add a version-like property to `DOCUMENT` nodes in the contract (contracts.md), update it during refresh.

## 8. Periodic audit by sampling

Use this when you do not know how old the graph is, when commits are not recorded, or on a schedule (for example monthly, or before relying on the graph for a big decision).

1. **Pick a sample** of 10 to 20 records across types, not all from one area. A simple random pick:
   ```sh
   graph nodes --type=API --fields=id --limit=200 | python3 -c "
   import json,random,sys
   rows=json.load(sys.stdin)['rows']
   ids=[r['id'] if isinstance(r,dict) else r[0] for r in rows]
   print('\n'.join(random.sample(ids,min(10,len(ids)))))"
   ```
   Do the same for edges (`graph edges --limit=200 --fields=id,type,source,target`).
2. **Verify each record:** open its evidence at the current commit and confirm the claim.
3. **Score it.** `failed / checked` is your error rate.
4. **Decide** (these thresholds are suggestions; adjust them to your risk):
   - Under about 5%: fix the failures, note the date in the log.
   - Between about 5% and 20%: run the full refresh workflow for the affected repositories.
   - Over about 20%: the area is unreliable; re-map it (mapping.md) rather than patching.
5. **Look at the pattern of failures.** If they cluster in one repo or one type, focus there.
6. **Check the structural gaps** too:
   ```sh
   graph status --check=orphans,no-evidence,no-description,components --limit=20
   ```

## 9. Maintenance log and templates

Keep a small append-only log, for example `maintenance/log.md` (or inside `batches/PROGRESS.md`). One entry per refresh:

```text
## 2026-11-11  orders   abc1234 -> def5678
Changed files: 14 (M 11, A 2, D 1)
Affected records: 9 (nodes 3, edges 6)
Outcome: ok 5, moved 2, changed 1, deleted 1
Batches: batches/0012-refresh-orders-def5678.jsonl (replace)
Deleted by hand: edge orders.api CALLS stock.api (call removed in def5678)
New records: 2 edges (see 0012)
Verified: validate OK; orphans 0 (was 0)
Last verified commit for orders: def5678
```

Worklist file per repository (`maintenance/worklist-<repo>.txt`) is a scratch artifact; keep it if useful for review, but the log is the permanent record.

Template for a refresh handoff note (producer to importer):
```text
Repo: orders   OLD abc1234 -> NEW def5678
Batch: batches/0012-refresh-orders-def5678.jsonl   (import with --on-conflict=replace)
Updated: 9 records (list the IDs)
Additions: 2 edges
To delete (importer runs these): graph delete edge EDGE_UUID   # reason
Not verified / uncertain: <list>
```

## 10. Pitfalls

| Pitfall | Fix |
| --- | --- |
| Bumping `commit` on records you did not re-read | Only bump after verifying; otherwise leave the old commit so the age stays visible |
| Records with no `commit` in their evidence | Treat their age as unknown; add `commit` whenever you re-verify them, and consider a sampling audit for that area |
| Relying on search to find missing records | Search finds records citing a path, not things never mapped; re-inventory changed areas |
| Diffing from a commit that is no longer reachable | Check with `merge-base --is-ancestor`; fall back to sampling or a re-map |
| Updating evidence without sending the full list | `--evidences` replaces everything; read first, then write the complete list |
| Deleting a node without checking its edges | Node deletion cascades; list its edges first |
| Forgetting that replaying batches resurrects deleted records | Log every deletion |
| Refreshing only one side of a cross-repo edge | Refresh all changed repositories; edges cite both sides |
| Running refresh imports in parallel | Imports are sequential; there is no locking |
| Treating "no search hits" as "nothing changed" | It means no record cites that file; new behavior may still need mapping |
| Mapping from a dirty working tree | Check `git status --porcelain` before reading evidence |

## 11. Checklist

- [ ] Baseline taken (`validate`, `status`) and `.graph/` committed or backed up
- [ ] Per repository: current commit vs last verified commit compared
- [ ] Old commit confirmed reachable; working tree clean
- [ ] Changed files listed with `git diff --name-status -M`
- [ ] Every changed path searched in evidences; worklist written
- [ ] Each affected record re-read at HEAD and given an outcome
- [ ] Added and structural files inspected for new nodes and edges
- [ ] Fixes applied through a new numbered batch (`replace`) or targeted `edit`/`delete`
- [ ] Deletions logged
- [ ] `validate` and `status` compared with the baseline
- [ ] Last verified commit and maintenance log updated, then everything committed