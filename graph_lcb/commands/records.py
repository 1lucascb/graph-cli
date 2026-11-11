from graph_lcb.cli import CLIError, Context
from graph_lcb.graphs.engine import Graph, GraphError
from graph_lcb.commands.common import (
    cli, property_arguments, matches_property_filter, parse_fields, evidences, edge_response,
    emit, positive_limit,
)

@cli.handler("add-node", "Add a node: add-node ID NAME TYPE [--description TEXT] [--properties JSON | --p.KEY=VALUE ...] [--evidences JSON_OBJECTS_ARRAY]")
def add_node(ctx: Context) -> None:
    evidence_values = evidences(ctx.flag("evidences", default="[]"))
    description = ctx.flag("description", default="")
    if not isinstance(description, str):
        raise CLIError("--description requires text")
    replacement, updates = property_arguments(ctx)
    node_properties = replacement if replacement is not None else updates or {}
    node = Graph().add_node(ctx.positional(0), ctx.positional(1), ctx.positional(2), node_properties, evidence_values, description)
    emit(node)

@cli.handler("add-edge", "Add an edge: add-edge SOURCE_ID EDGE_TYPE TARGET_ID [--description TEXT] [--properties JSON | --p.KEY=VALUE ...] [--evidences JSON_OBJECTS_ARRAY]")
def add_edge(ctx: Context) -> None:
    evidence_values = evidences(ctx.flag("evidences", default="[]"))
    description = ctx.flag("description")
    if description is not None and not isinstance(description, str):
        raise CLIError("--description requires text")
    graph = Graph()
    replacement, updates = property_arguments(ctx)
    edge_properties = replacement if replacement is not None else updates or {}
    edge = graph.add_edge(ctx.positional(0), ctx.positional(1), ctx.positional(2), edge_properties, evidence_values, description or "")
    edge = edge_response(edge, graph.load()["nodes"])
    emit(edge)

@cli.handler("nodes", "List or query nodes: nodes [ID] [--type TYPE[,TYPE...]] [--properties JSON | --p.KEY=VALUE ...] [--limit N] [--prefix TEXT] [--suffix TEXT] [--contains TEXT] [--fields FIELD,...]")
def list_nodes(ctx: Context) -> None:
    data = Graph().load()

    reference = ctx.positional(0, None)
    property_filter, property_terms = property_arguments(ctx, allow_combined=True)
    fields = parse_fields(ctx.flag("fields"), {"id", "type", "name", "description", "properties", "metadata", "evidences"})
    if reference is not None:
        if property_filter is not None or property_terms is not None:
            raise CLIError("property filters cannot be combined with a node ID")
        if fields is not None:
            raise CLIError("--fields cannot be combined with a node ID")
        node = Graph.resolve_node(data, reference)
        if node is None:
            raise CLIError(f"unknown node id: {reference}")
        emit(node)
        return
    nodes = data["nodes"]

    prefix = ctx.flag("prefix")
    suffix = ctx.flag("suffix")
    contains = ctx.flag("contains")
    raw_kinds = ctx.flag("type")
    kinds = None
    if raw_kinds is not None:
        if not isinstance(raw_kinds, str) or not raw_kinds:
            raise CLIError("--type requires comma-separated entity type names")
        kinds = [item.strip().casefold() for item in raw_kinds.split(",")]
        if any(not item for item in kinds):
            raise CLIError("--type requires comma-separated entity type names")
    limit_value = positive_limit(ctx.flag("limit"))
    filters = (("--prefix", prefix), ("--suffix", suffix), ("--contains", contains))
    for option, value in filters:
        if value is not None and not isinstance(value, str):
            raise CLIError(f"{option} requires a value")
    if prefix is not None:
        nodes = [node for node in nodes if node.name.lower().startswith(prefix.lower())]
    if kinds is not None:
        nodes = [node for node in nodes if node.type.casefold() in kinds]
    if suffix is not None:
        nodes = [node for node in nodes if node.name.lower().endswith(suffix.lower())]
    if contains is not None:
        nodes = [node for node in nodes if contains.lower() in node.name.lower()]
    nodes = [node for node in nodes
             if matches_property_filter(node.properties, property_filter)
             and matches_property_filter(
                 node.properties, property_terms, case_insensitive_strings=True,
             )]
    total = len(nodes)
    if limit_value is not None:
        nodes = nodes[:limit_value]
    if fields is not None:
        nodes = [{field: getattr(node, field) for field in fields} for node in nodes]
    emit({"rows": nodes, "total": total, "truncated": total > len(nodes)})

@cli.handler("edges", "List or query edges: edges [ID] [--type TYPE[,TYPE...]] [--properties JSON | --p.KEY=VALUE ...] [--from NODE] [--to NODE] [--limit N] [--fields FIELD,...]")
def list_edges(ctx: Context) -> None:
    graph = Graph()
    reference = ctx.positional(0, None)
    if reference is not None:
        if len(ctx.args) != 1 or any(ctx.flag(name) is not None for name in ("type", "properties", "from", "to", "limit", "fields", "description")) or any(
            name.startswith("p.") or name == "p" for name, _ in ctx._options
        ):
            raise CLIError("an edge ID cannot be combined with filters")
        data = graph.load()
        edge = next((item for item in data["edges"] if item.id == reference), None)
        if edge is None:
            raise CLIError(f"unknown edge ID: {reference}")
        emit(edge_response(edge, data["nodes"]))
        return
    raw_kind = ctx.flag("type")
    kinds = None
    if raw_kind is not None:
        if not isinstance(raw_kind, str) or not raw_kind:
            raise CLIError("--type requires comma-separated edge type names")
        kinds = [item.strip() for item in raw_kind.split(",")]
        if any(not item for item in kinds):
            raise CLIError("--type requires comma-separated edge type names")
    properties, property_terms = property_arguments(ctx, allow_combined=True)
    source, target = ctx.flag("from"), ctx.flag("to")
    for option, value in (("--from", source), ("--to", target)):
        if value is not None and not isinstance(value, str):
            raise CLIError(f"{option} requires a value")
    limit = positive_limit(ctx.flag("limit"))
    fields = parse_fields(ctx.flag("fields"), {"id", "type", "source", "target", "target_type", "description", "properties", "evidences", "metadata"})
    records = graph.list_edges(
        kinds=kinds, properties=properties, source=source, target=target,
    )
    records = [record for record in records if matches_property_filter(
        record.properties, property_terms, case_insensitive_strings=True,
    )]
    total = len(records)
    if limit is not None:
        records = records[:limit]
    nodes = graph.load()["nodes"]
    if fields is not None:
        rows = [
            {field: getattr(edge_response(record, nodes), field) for field in fields}
            for record in records
        ]
    else:
        rows = [
            [
                record.source, record.type, record.target,
                next((node.type for node in nodes if node.id == record.target), ""),
            ]
            for record in records
        ]
    emit({"rows": rows, "total": total, "truncated": total > len(rows)})
