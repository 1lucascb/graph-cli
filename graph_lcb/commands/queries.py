import re

from graph_lcb.cli import CLIError, Context
from graph_lcb.graphs.engine import Graph, GraphError
from graph_lcb.commands.common import cli, emit, positive_limit, parse_edge_types, parse_fields

SEARCH_FIELDS = {"id", "name", "type", "description", "properties", "evidences", "source", "target"}


def searchable_text(record, kind: str) -> dict[str, list[str]]:
    """Extract searchable text by field without performing I/O."""
    fields = {key: [] for key in ("id", "name", "type", "description", "properties", "evidences", "source", "target")}
    for key in ("id", "name", "type", "description", "source", "target"):
        value = getattr(record, key, None)
        if isinstance(value, str):
            fields[key].append(value)
    def flatten(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for item in value.values():
                yield from flatten(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                yield from flatten(item)
        elif value is not None:
            yield str(value)
    properties = getattr(record, "properties", {})
    if isinstance(properties, dict):
        fields["properties"] = [str(key) for key in properties]
        for value in properties.values():
            fields["properties"].extend(flatten(value))
        fields["properties"].extend(f"{key}={value}" for key, value in properties.items())
    fields["evidences"] = list(flatten(getattr(record, "evidences", [])))
    return fields


def _search_error(code: str, message: str, hint: str) -> None:
    emit({"error": {"code": code, "message": message, "hint": hint}})


@cli.handler("search", "Search graph text: search TERM [TERM ...] [--any] [--not TERM ...] [--in FIELD,...] [--kind nodes|edges|all] [--type TYPE,...] [--regex] [--case-sensitive] [--limit N] [--offset N] [--snippets]")
def search(ctx: Context) -> None:
    options = ctx._options
    excluded = [value for name, value in options if name == "not"]
    if any(not isinstance(value, str) or value == "" for value in excluded):
        _search_error("empty_query", "--not requires a non-empty term", "Provide a term after every --not option.")
        return
    terms = list(ctx.args)
    if not terms or any(not term for term in terms):
        _search_error("empty_query", "search requires non-empty terms", "Provide one or more terms after `graph search`.")
        return
    regex_mode = ctx.flag("regex") is True
    case_sensitive = ctx.flag("case-sensitive") is True
    if regex_mode:
        for term in terms + excluded:
            try:
                re.compile(term, 0 if case_sensitive else re.IGNORECASE)
            except re.error as exc:
                _search_error("invalid_regex", f"invalid regex {term!r} at position {exc.pos}: {exc}", "Correct the regular expression and retry.")
                return
    in_value = ctx.flag("in")
    valid_fields = sorted(SEARCH_FIELDS)
    fields = set(valid_fields)
    if in_value is not None:
        if not isinstance(in_value, str):
            _search_error("unknown_field", "--in requires comma-separated fields", f"Valid fields: {', '.join(valid_fields)}")
            return
        fields = {v.strip() for v in in_value.split(",")}
        unknown = fields - SEARCH_FIELDS
        if unknown:
            _search_error("unknown_field", f"unknown search field: {', '.join(sorted(unknown))}", f"Valid fields: {', '.join(valid_fields)}")
            return
    kind = ctx.flag("kind", default="all")
    if kind not in {"nodes", "edges", "all"}:
        _search_error("unknown_kind", f"unknown kind: {kind}", "Valid kinds: nodes, edges, all")
        return
    graph = Graph()
    data = graph.load()
    type_value = ctx.flag("type")
    types = None
    if type_value is not None:
        if not isinstance(type_value, str):
            type_value = ""
        types = {v.strip().casefold() for v in type_value.split(",")}
        known = {x.casefold() for x in (*graph.entities.keys(), *graph.edge_types.keys())}
        invalid = types - known
        if invalid:
            _search_error("unknown_type", f"unknown type: {', '.join(sorted(invalid))}", f"Valid types: {', '.join(sorted(graph.entities.keys() | graph.edge_types.keys())[:20])}")
            return
    limit = positive_limit(ctx.flag("limit"))
    offset_value = ctx.flag("offset")
    try:
        offset = 0 if offset_value is None else int(offset_value)
        if offset < 0: raise ValueError
    except (ValueError, TypeError):
        _search_error("unknown_field", "--offset requires a non-negative integer", "Use zero or a positive integer.")
        return
    snippets = ctx.flag("snippets") is True
    records = ([ ("node", n) for n in data["nodes"]] if kind in {"all", "nodes"} else [])
    records += [("edge", e) for e in graph.list_edges()] if kind in {"all", "edges"} else []
    rows_all = []
    for record_kind, record in records:
        if types is not None and record.type.casefold() not in types:
            continue
        available = searchable_text(record, record_kind)
        selected = {f: values for f, values in available.items() if f in fields}
        matches = []
        hit_snippets = {}
        for term in terms:
            hit = [field for field, values in selected.items() if any(_matches(term, value, regex_mode, case_sensitive) for value in values)]
            matches.append(hit)
            for field in hit:
                if field not in hit_snippets:
                    value = next(v for v in selected[field] if _matches(term, v, regex_mode, case_sensitive))
                    hit_snippets[field] = _excerpt(value, term, regex_mode, case_sensitive)
        excluded_hit = any(_matches(term, value, regex_mode, case_sensitive) for term in excluded for values in selected.values() for value in values)
        positive = bool(set.union(*(set(x) for x in matches))) if ctx.flag("any") is True else all(matches)
        if not positive or excluded_hit:
            continue
        matched = sorted(set().union(*map(set, matches)))
        row = ["node", record.id, record.type, record.name, matched] if record_kind == "node" else ["edge", record.source, record.type, record.target, matched]
        if snippets:
            row.append({k: hit_snippets[k] for k in matched})
        rows_all.append(row)
    total = len(rows_all)
    page = rows_all[offset: offset + limit if limit is not None else None]
    next_offset = offset + len(page) if offset + len(page) < total else None
    emit({"rows": page, "total": total, "truncated": next_offset is not None, "next_offset": next_offset})


def _matches(term, value, regex_mode, case_sensitive):
    if regex_mode:
        return re.search(term, value, 0 if case_sensitive else re.IGNORECASE) is not None
    return (term if case_sensitive else term.casefold()) in (value if case_sensitive else value.casefold())


def _excerpt(value, term, regex_mode, case_sensitive):
    match = re.search(term, value, 0 if case_sensitive else re.IGNORECASE) if regex_mode else None
    start = match.start() if match else (value.find(term) if case_sensitive else value.casefold().find(term.casefold()))
    start = max(0, start - 25)
    return ("…" if start else "") + value[start:start + 60] + ("…" if start + 60 < len(value) else "")



NODE_FIELDS = {"id", "type", "name", "description", "properties", "metadata", "evidences"}


def expand_node_fields(graph: Graph, result: dict, fields: list[str] | None, *, paths: bool = False) -> None:
    """Replace compact node tuples with selected node fields when requested."""
    if fields is None:
        return
    data = graph.load()
    nodes = {node.id: node for node in data["nodes"]}

    def project(tuple_row: list) -> dict:
        node = nodes[tuple_row[0]]
        return {field: getattr(node, field) for field in fields}

    if paths:
        for path_result in result["paths"]:
            path_result["nodes"] = [project(row) for row in path_result["nodes"]]
    else:
        result["nodes"] = [project(row) for row in result["nodes"]]

@cli.handler("traverse", "Traverse from a node: traverse NODE_ID [--depth N] [--direction in|out|both] [--edge TYPE[,TYPE...]] [--limit N] [--fields FIELD,...]")
def traverse(ctx: Context) -> None:
    if len(ctx.args) != 1:
        raise CLIError("traverse requires exactly one NODE_ID positional argument")
    if ctx.flag("from") is not None or ctx.flag("to") is not None:
        raise CLIError("traverse uses a positional NODE_ID; --from and --to are not supported")
    anchor_id = ctx.positional(0)

    def integer_flag(name: str, default: int | None) -> int | None:
        value = ctx.flag(name)
        if value is None:
            return default
        if not isinstance(value, str):
            raise CLIError(f"--{name} requires an integer")
        try:
            parsed = int(value)
        except ValueError as exc:
            raise CLIError(f"--{name} requires an integer") from exc
        if parsed < (1 if name == "depth" else 0):
            raise CLIError(f"--{name} must be {'positive' if name == 'depth' else 'non-negative'}")
        return parsed

    depth = integer_flag("depth", 1)
    limit = positive_limit(ctx.flag("limit"))
    direction = ctx.flag("direction", default="both")
    if direction is not None and not isinstance(direction, str):
        raise CLIError("--direction requires in, out, or both")
    graph = Graph()
    fields = parse_fields(ctx.flag("fields"), NODE_FIELDS)
    edge_types = parse_edge_types(ctx.flag("edge"), graph)
    result = graph.traverse(anchor_id, depth=depth, direction=direction,
                              edge_types=edge_types, limit=limit)
    expand_node_fields(graph, result, fields)
    emit(result)

@cli.handler("path", "Find shortest paths between nodes: path SOURCE TARGET [--direction out|in|both] [--edge TYPE[,TYPE...]] [--max-depth N] [--limit N] [--fields FIELD,...]")
def path(ctx: Context) -> None:
    if len(ctx.args) != 2:
        raise CLIError("path requires exactly SOURCE and TARGET")
    source, target = ctx.positional(0), ctx.positional(1)
    direction = ctx.flag("direction", default="out")
    if not isinstance(direction, str):
        raise CLIError("--direction requires out, in, or both")
    graph = Graph()
    fields = parse_fields(ctx.flag("fields"), NODE_FIELDS)
    edge_types = parse_edge_types(ctx.flag("edge"), graph)

    def non_negative_option(name: str, default: int) -> int:
        value = ctx.flag(name)
        if value is None:
            return default
        if not isinstance(value, str):
            raise CLIError(f"--{name} requires a non-negative integer")
        try:
            parsed = int(value)
        except ValueError as exc:
            raise CLIError(f"--{name} requires a non-negative integer") from exc
        if parsed < 0:
            raise CLIError(f"--{name} must be non-negative")
        return parsed

    max_depth = ctx.flag("max-depth")
    if max_depth is not None:
        max_depth = non_negative_option("max-depth", 0)
    limit = positive_limit(ctx.flag("limit"), default=1)
    result = graph.find_paths(source, target, direction=direction, edge_types=edge_types,
                              max_depth=max_depth, limit=limit)
    expand_node_fields(graph, result, fields, paths=True)
    emit(result)
