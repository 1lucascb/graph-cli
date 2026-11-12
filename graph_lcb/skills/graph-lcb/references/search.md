# Using `graph search` effectively

Use `graph search` when you do **not** know where a phrase appears. If you know the type, property, name pattern, or endpoint, prefer `graph nodes` or `graph edges` (see query.md); they are more precise and cheaper.

## Contents
1. What search covers
2. Anatomy of a query
3. Choosing the scope
4. Recipes
5. Reading results
6. Paging
7. Regex notes
8. Pitfalls

## 1. What search covers

Search scans nodes and edges linearly. For each record it can look in these fields:

| Field | Applies to | Notes |
| --- | --- | --- |
| `id` | nodes, edges | Node ID or edge UUID |
| `name` | nodes | Display name |
| `type` | nodes, edges | Entity or edge type |
| `description` | nodes, edges | Free text |
| `properties` | nodes, edges | Property keys and values as text |
| `evidences` | nodes, edges | Source paths, notes, locators |
| `source` | edges | Source node ID |
| `target` | edges | Target node ID |

Fields that do not apply to a record kind are ignored for that kind, so you can list them freely.

## 2. Anatomy of a query

```text
graph search TERM [TERM ...] [--any] [--not TERM ...]
             [--in FIELDS] [--kind nodes|edges|all] [--type TYPES]
             [--regex] [--case-sensitive]
             [--limit N] [--offset N] [--fields FIELDS | --snippets]
```

- **Terms are ANDed by default.** `graph search payment billing` finds records containing both. Add `--any` for OR.
- **`--not TERM`** excludes records matching that term. Repeat it for several exclusions.
- **Matching is a case-insensitive substring** unless `--regex` is set. `--case-sensitive` applies to both modes.
- **`--kind`** defaults to `all`. Use `nodes` or `edges` to cut noise.
- **`--type`** accepts node types or edge types, depending on `--kind`.
- **A term starting with `--`** must come after a standalone `--`: `graph search -- --literal`.

## 3. Choosing the scope

The default scope is every applicable field, which is broad. Narrow it with `--in` once you know what you want.

| Goal | Scope |
| --- | --- |
| Find a node by name or ID fragment | `--kind=nodes --in=id,name` |
| Find by explanation text | `--in=description` |
| Find everything mentioning a file | `--in=evidences` |
| Find by property value | `--in=properties` |
| Find edges touching a node | `--kind=edges --in=source,target` |
| Find by type text | `--in=type` |

## 4. Recipes

### I only remember part of a name
```sh
graph search payment --kind=nodes --in=id,name --fields=id,type,name
```

### Which nodes and edges cite this file? (staleness and impact)
```sh
graph search services/orders/src/api.py --in=evidences --snippets
```
After a file changes, this lists every record whose evidence may need review.

### Find all mentions, excluding a noisy concept
```sh
graph search timeout --not retry --in=description,evidences --snippets
```

### Either of two spellings
```sh
graph search billing invoicing --any --kind=nodes
```

### Regex alternatives or patterns
```sh
graph search --regex "payment|billing" --kind=nodes --in=name,description
graph search --regex "^v[0-9]+\." --in=properties
```

### Find edges that touch a node by text
```sh
graph search orders-api --kind=edges --in=source,target --fields=type,source,target
```
For an exact node, `graph edges --from=ID` or `--to=ID` is more precise; use search only when you are not sure about the ID.

### Restrict to one type
```sh
graph search auth --kind=nodes --type=API,WORKER
```

### Search for text that starts with dashes
```sh
graph search -- --dry-run --in=description
```

## 5. Reading results

Response shape:
```json
{"rows":[...],"total":N,"truncated":false,"next_offset":null}
```

- Node row: `["node", id, type, name, matched_fields]`
- Edge row: `["edge", source, type, target, matched_fields]`
- `matched_fields` tells you **why** the record matched. If a node matched only via `evidences`, it mentions the term indirectly and may not be the thing you want.
- `--snippets` adds a sixth element: an object mapping each matched field to a roughly 60-character excerpt. Use it to judge relevance without opening the record.
- `--fields` returns arrays of the selected values in the order you asked. Allowed: `id`, `type`, `name`, `source`, `target`, `description`, `properties`, `metadata`, `evidences`. Fields that do not apply are omitted per result.
- **`--fields` cannot be combined with `--snippets`.** Pick one.
- `total` is the exact count before paging. Compare it to what you received.
- Results keep graph node order, then the usual sorted edge order. They are not ranked by relevance.

## 6. Paging

When `truncated` is true or `next_offset` is not null:

```sh
graph search auth --limit=20
graph search auth --limit=20 --offset=20    # use next_offset from the previous response
```

Keep the same terms and filters while paging. Stop paging as soon as you have enough; prefer tightening the query over reading every page.

## 7. Regex notes

- Regex uses Python's `re`, applied to every term, with the same `--case-sensitive` behavior.
- **There is no timeout.** A pathological pattern can be slow on large evidence text. Avoid nested quantifiers like `(a+)+`.
- Combine `--regex` with `--in` to shrink the text being scanned.
- Invalid patterns return an `invalid_regex` error. Other error codes: `empty_query`, `unknown_field`, `unknown_kind`, `unknown_type`.

## 8. Pitfalls

| Pitfall | Fix |
| --- | --- |
| Too many results | Add `--kind`, `--in`, `--type`, or `--not`; use `--fields` for compact rows |
| Zero results from a long phrase | Terms are ANDed substrings. Try fewer terms or `--any` |
| Expecting ranking | There is none. Narrow by field and type instead |
| Treating a search hit as a fact | Open the record and its evidence before relying on it |
| Using search for something structural | Use `nodes`, `edges`, `traverse`, or `path` instead |
| Using `--fields` and `--snippets` together | They are mutually exclusive |
| Searching for `--something` literally | Put it after a standalone `--` |