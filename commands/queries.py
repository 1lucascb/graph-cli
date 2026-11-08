from cli import CLIError, Context
from graphs.engine import Graph, GraphError
from commands.common import cli, emit, positive_limit, parse_edge_types

@cli.handler("traverse", "Traverse from a node: traverse NODE_ID [--depth N] [--direction in|out|both] [--edge TYPE[,TYPE...]] [--limit N]")
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
    edge_types = parse_edge_types(ctx.flag("edge"), graph)
    result = graph.traverse(anchor_id, depth=depth, direction=direction,
                              edge_types=edge_types, limit=limit)
    emit(result)

@cli.handler("path", "Find shortest paths between nodes: path SOURCE TARGET [--direction out|in|both] [--edge TYPE[,TYPE...]] [--max-depth N] [--limit N]")
def path(ctx: Context) -> None:
    if len(ctx.args) != 2:
        raise CLIError("path requires exactly SOURCE and TARGET")
    source, target = ctx.positional(0), ctx.positional(1)
    direction = ctx.flag("direction", default="out")
    if not isinstance(direction, str):
        raise CLIError("--direction requires out, in, or both")
    graph = Graph()
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
    emit(result)
