import sys
from cli import CLIError, Context
from graphs.engine import Graph, GraphError
from commands.common import cli, evidences, edge_response, emit, parse_properties

@cli.handler("edit", "Edit node fields or edge description/properties/evidences: edit node|edge ...")
def edit_record(ctx: Context) -> None:
    target = ctx.positional(0).lower()
    graph = Graph()
    if target == "node":
        if ctx.flag("id") is not None:
            raise CLIError("edit node ID is positional: edit node ID --name=...")
        if len(ctx.args) != 2:
            raise CLIError("use edit node ID with --name, --properties, and/or --evidences")
        reference = ctx.positional(1)
        name = ctx.flag("name")
        raw_properties = ctx.flag("properties")
        raw_evidences = ctx.flag("evidences")
        if name is None and raw_properties is None and raw_evidences is None:
            raise CLIError("provide --name, --properties, and/or --evidences")
        if name is not None and not isinstance(name, str):
            raise CLIError("--name requires a value")
        parsed_properties = parse_properties(raw_properties)
        parsed_evidences = None
        if raw_evidences is not None:
            parsed_evidences = evidences(raw_evidences)
        result = graph.edit_node(reference, name=name, properties=parsed_properties, evidences=parsed_evidences)
    elif target == "edge":
        if ctx.flag("id") is not None:
            raise CLIError("edit edge ID is positional: edit edge ID --description=...")
        if len(ctx.args) != 2:
            raise CLIError("use edit edge ID with --description, --properties, and/or --evidences")
        edge_id = ctx.positional(1)
        description = ctx.flag("description")
        raw_properties = ctx.flag("properties")
        raw_evidences = ctx.flag("evidences")
        if not isinstance(edge_id, str):
            raise CLIError("edit edge requires an edge ID")
        if description is not None and not isinstance(description, str):
            raise CLIError("--description requires text")
        if description is None and raw_properties is None and raw_evidences is None:
            raise CLIError("provide --description, --properties, and/or --evidences")
        parsed_properties = parse_properties(raw_properties)
        parsed_evidences = None
        if raw_evidences is not None:
            parsed_evidences = evidences(raw_evidences)
        result = graph.edit_edge(edge_id, description=description, properties=parsed_properties, evidences=parsed_evidences)
        result = edge_response(result, graph.load()["nodes"])
    else:
        raise CLIError("expected 'node' or 'edge'")
    emit(result)

@cli.handler("delete", "Delete a node and its edges, or delete an edge: delete node|edge ...")
def delete_record(ctx: Context) -> int | None:
    target = ctx.positional(0).lower()
    graph = Graph()
    if target == "node":
        if ctx.flag("id") is not None:
            raise CLIError("delete node ID is positional: delete node ID")
        if len(ctx.args) != 2:
            raise CLIError("use delete node ID")
        node_id = ctx.positional(1)
        node, edge_count = graph.delete_node(node_id=node_id)
        emit({"deleted_node": node, "deleted_edges": edge_count})
    elif target == "edge":
        if ctx.flag("id") is not None:
            raise CLIError("delete edge ID is positional: delete edge ID")
        if len(ctx.args) == 2:
            edge_id = ctx.positional(1)
            kind = source = destination = None
        elif len(ctx.args) == 4:
            edge_id = None
            source, kind, destination = ctx.args[1:]
        else:
            raise CLIError("use delete edge ID or delete edge SOURCE_NODE_ID EDGE_TYPE TARGET_NODE_ID")
        matches = graph.delete_edge(edge_id=edge_id, kind=kind, source=source, target=destination)
        nodes = graph.load()["nodes"]
        if len(matches) > 1:
            print("Multiple matching edges found; none were deleted. Delete one by ID:", file=sys.stderr)
            emit([edge_response(edge, nodes) for edge in matches])
            print("Use: graph delete edge EDGE_ID", file=sys.stderr)
            return 2
        emit({"deleted_edge": edge_response(matches[0], nodes)})
    else:
        raise CLIError("expected 'node' or 'edge'")
