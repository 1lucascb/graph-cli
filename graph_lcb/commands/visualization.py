import json
import webbrowser
from pathlib import Path

from graph_lcb.cli import CLIError, Context
from graph_lcb.graphs.engine import Graph, GraphError
from graph_lcb.commands.common import cli, emit, json_default

@cli.handler("view", "Write a self-contained HTML view of the graph to .graph/view.html and open it: view [--no-open]")
def view_graph(ctx: Context) -> None:
    graph = Graph()
    data = graph.load()

    def descriptions(contracts: dict) -> dict:
        return {name: (c.get("description", "") if isinstance(c, dict) else "") for name, c in contracts.items()}

    payload = {
        "nodes": data["nodes"],
        "edges": data["edges"],
        "types": {"entities": descriptions(graph.entities), "edges": descriptions(graph.edge_types)},
    }
    # Escaping "<" keeps "</script>" and "<!--" inside the data from breaking out of the script tag.
    graph_json = json.dumps(payload, ensure_ascii=False, default=json_default).replace("<", "\\u003c")

    template_path = Path(__file__).parent / "visualization-templates" / "graphs.template.html"
    with template_path.open(encoding="utf-8") as file:
        TEMPLATE = file.read()

    page = TEMPLATE.replace("__GRAPH_DATA__", graph_json)

    try:
        graph.directory.mkdir(parents=True, exist_ok=True)
        out = (graph.directory / "view.html").resolve()
        out.write_text(page, encoding="utf-8")
    except OSError as exc:
        raise CLIError(f"cannot write view: {exc}") from exc

    opened = False
    if not ctx.flag("no-open"):
        try:
            opened = webbrowser.open(out.as_uri())
        except webbrowser.Error:
            opened = False
    emit({"path": str(out), "nodes": len(data["nodes"]), "edges": len(data["edges"]), "opened": opened})
