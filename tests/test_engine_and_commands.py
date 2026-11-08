import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from graphs.engine import Graph, GraphError
from graphs.types import Edge, Node

ROOT = Path(__file__).resolve().parents[1]
GRAPH_SCRIPT = ROOT / "graph"


def _write_contracts(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "entities.json").write_text(
        json.dumps({
            "API": {"properties": {"language": {"type": "string", "required": True}}},
            "WORKER": {"properties": {}},
        }),
        encoding="utf-8",
    )
    (directory / "edges.json").write_text(
        json.dumps({
            "CALLS": {
                "source": ["API"],
                "target": ["API"],
                "properties": {"protocol": {"type": "string", "required": False}},
            }
        }),
        encoding="utf-8",
    )


def _run_graph(directory: Path, *args: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(ROOT), environment.get("PYTHONPATH", "")])
    )
    return subprocess.run(
        [sys.executable, str(GRAPH_SCRIPT), *args],
        cwd=directory,
        env=environment,
        capture_output=True,
        text=True,
    )


def test_graph_traverse_honors_depth_and_direction(tmp_path: Path) -> None:
    graph_directory = tmp_path / ".graph"
    _write_contracts(graph_directory)
    graph = Graph(graph_directory)

    for node_id, name in (("a", "Alpha"), ("b", "Beta"), ("c", "Gamma"), ("d", "Delta")):
        graph.add_node(node_id, name, "API", {"language": "python"})
    graph.add_edge("a", "CALLS", "b", {"protocol": "http"}, description="first")
    graph.add_edge("a", "CALLS", "d", {"protocol": "https"}, description="second")
    graph.add_edge("b", "CALLS", "c", {"protocol": "grpc"}, description="third")

    result = graph.traverse("a", depth=2, direction="out")

    assert result["nodes"] == [
        ["a", "API", "Alpha"],
        ["b", "API", "Beta"],
        ["c", "API", "Gamma"],
        ["d", "API", "Delta"],
    ]
    assert [edge[0] for edge in result["edges"]] == ["a", "a", "b"]
    assert result["truncated"] is False


@pytest.mark.parametrize("query", ["traverse", "find_paths"])
def test_graph_queries_reject_unknown_edge_filters(tmp_path: Path, query: str) -> None:
    graph_directory = tmp_path / ".graph"
    _write_contracts(graph_directory)
    graph = Graph(graph_directory)

    with pytest.raises(GraphError, match="unknown edge type: MISSING"):
        if query == "traverse":
            graph.traverse("start", edge_types={"MISSING"})
        else:
            graph.find_paths("start", "finish", edge_types={"MISSING"})


def test_graph_find_paths_returns_shortest_simple_paths(tmp_path: Path) -> None:
    graph_directory = tmp_path / ".graph"
    _write_contracts(graph_directory)
    graph = Graph(graph_directory)

    for node_id, name in (("start", "Start"), ("mid", "Mid"), ("leaf", "Leaf"), ("other", "Other")):
        graph.add_node(node_id, name, "API", {"language": "python"})
    graph.add_edge("start", "CALLS", "mid", {"protocol": "https"}, description="route 1")
    graph.add_edge("mid", "CALLS", "leaf", {"protocol": "http"}, description="route 2")
    graph.add_edge("start", "CALLS", "other", {"protocol": "http"}, description="branch")
    graph.add_edge("other", "CALLS", "leaf", {"protocol": "http"}, description="branch route")

    result = graph.find_paths("start", "leaf", direction="out", limit=2)

    assert result["truncated"] is False
    assert [path["hops"] for path in result["paths"]] == [2, 2]
    assert [[node[0] for node in path["nodes"]] for path in result["paths"]] == [
        ["start", "mid", "leaf"],
        ["start", "other", "leaf"],
    ]

    limited_result = graph.find_paths("start", "leaf", direction="out", limit=1)
    assert limited_result["truncated"] is True
    assert [[node[0] for node in path["nodes"]] for path in limited_result["paths"]] == [
        ["start", "mid", "leaf"],
    ]


def test_graph_find_paths_returns_immediately_when_target_is_unreachable(tmp_path: Path) -> None:
    graph_directory = tmp_path / ".graph"
    _write_contracts(graph_directory)
    graph = Graph(graph_directory)
    node_ids = ["start"]
    edge_records = []
    previous_layer = ["start"]
    next_edge_index = 0
    for layer_index in range(14):
        current_layer = [f"layer-{layer_index}-{index}" for index in range(3)]
        node_ids.extend(current_layer)
        for source in previous_layer:
            for target in current_layer:
                edge_records.append(Edge(
                    id=f"edge-{next_edge_index}",
                    type="CALLS",
                    source=source,
                    target=target,
                ))
                next_edge_index += 1
        previous_layer = current_layer
    node_ids.append("unreachable")
    graph.save({
        "nodes": [Node(id=node_id, type="API", name=node_id) for node_id in node_ids],
        "edges": edge_records,
    })

    assert graph.find_paths("start", "unreachable", direction="out") == {
        "paths": [],
        "truncated": False,
    }


def test_graph_find_paths_counts_parallel_edges_as_distinct_paths(tmp_path: Path) -> None:
    graph_directory = tmp_path / ".graph"
    _write_contracts(graph_directory)
    graph = Graph(graph_directory)
    graph.add_node("start", "Start", "API", {"language": "python"})
    graph.add_node("leaf", "Leaf", "API", {"language": "python"})
    graph.add_edge("start", "CALLS", "leaf", {"protocol": "http"}, description="HTTP route")
    graph.add_edge("start", "CALLS", "leaf", {"protocol": "https"}, description="HTTPS route")

    result = graph.find_paths("start", "leaf", direction="out", limit=2)

    assert result["truncated"] is False
    assert len(result["paths"]) == 2
    assert [path["nodes"] for path in result["paths"]] == [
        [["start", "API", "Start"], ["leaf", "API", "Leaf"]],
        [["start", "API", "Start"], ["leaf", "API", "Leaf"]],
    ]
    assert len({path["edges"][0][0] for path in result["paths"]}) == 2


def test_new_graph_copies_schemas_and_references_them(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    init_result = _run_graph(workspace, "init")
    assert init_result.returncode == 0, init_result.stderr

    result = _run_graph(workspace, "contract", "entities")

    assert result.returncode == 0, result.stderr
    graph_directory = workspace / ".graph"
    entities_path = graph_directory / "entities.json"
    edges_path = graph_directory / "edges.json"
    entities = json.loads(entities_path.read_text(encoding="utf-8"))
    edges = json.loads(edges_path.read_text(encoding="utf-8"))
    assert entities["$schema"] == "./schemas/entities.schema.json"
    assert edges["$schema"] == "./schemas/edges.schema.json"
    assert (graph_directory / "schemas" / "entities.schema.json").read_bytes() == (
        ROOT / "schemas" / "entities.schema.json"
    ).read_bytes()
    assert (graph_directory / "schemas" / "edges.schema.json").read_bytes() == (
        ROOT / "schemas" / "edges.schema.json"
    ).read_bytes()
    custom_schema = graph_directory / "schemas" / "entities.schema.json"
    custom_schema.write_text("customized", encoding="utf-8")
    rerun = _run_graph(workspace, "contract", "entities")

    assert rerun.returncode == 0, rerun.stderr
    assert custom_schema.read_text(encoding="utf-8") == "customized"
    assert Graph(graph_directory).validate()["valid"] is True


@pytest.mark.parametrize("arguments", [
    ("--help",),
    ("help", "contract"),
    ("contract", "--help"),
    ("unknown-command",),
])
def test_help_and_unknown_commands_do_not_create_graph_files(
    tmp_path: Path, arguments: tuple[str, ...],
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = _run_graph(workspace, *arguments)

    assert result.returncode == (2 if arguments == ("unknown-command",) else 0)
    assert not (workspace / ".graph").exists()

def test_cli_commands_add_and_delete_graph_records(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_contracts(workspace / ".graph")

    add_node = _run_graph(workspace, "add-node", "orders", "Orders API", "API", "--properties", '{"language":"python"}')
    add_second = _run_graph(workspace, "add-node", "stock", "Stock API", "API", "--properties", '{"language":"python"}')
    add_edge = _run_graph(workspace, "add-edge", "orders", "CALLS", "stock", "--description", "calls downstream")
    add_incoming_edge = _run_graph(workspace, "add-edge", "stock", "CALLS", "orders")
    traverse = _run_graph(workspace, "traverse", "orders", "--edge=CALLS")
    delete = _run_graph(workspace, "delete", "edge", "orders", "CALLS", "stock")

    assert add_node.returncode == 0, add_node.stderr
    assert add_second.returncode == 0, add_second.stderr
    assert add_edge.returncode == 0, add_edge.stderr
    assert add_incoming_edge.returncode == 0, add_incoming_edge.stderr
    assert traverse.returncode == 0, traverse.stderr
    assert delete.returncode == 0, delete.stderr

    traversed = json.loads(traverse.stdout)
    assert traversed["nodes"] == [
        ["orders", "API", "Orders API"],
        ["stock", "API", "Stock API"],
    ]
    assert traversed["edges"] == [
        ["orders", "CALLS", "stock", "API"],
        ["stock", "CALLS", "orders", "API"],
    ]

    deleted = json.loads(delete.stdout)
    assert deleted["deleted_edge"]["source"] == "orders"
    assert deleted["deleted_edge"]["target"] == "stock"

def test_ambiguous_cli_edge_delete_returns_two_without_deleting(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_contracts(workspace / ".graph")
    graph = Graph(workspace / ".graph")
    graph.add_node("orders", "Orders", "API", {"language": "python"})
    graph.add_node("stock", "Stock", "API", {"language": "python"})
    graph.add_edge("orders", "CALLS", "stock", {"protocol": "http"}, description="first")
    graph.add_edge("orders", "CALLS", "stock", {"protocol": "https"}, description="second")
    graph_path = workspace / ".graph" / "graph.json"
    before = graph_path.read_bytes()

    result = _run_graph(workspace, "delete", "edge", "orders", "CALLS", "stock")

    assert result.returncode == 2
    assert "Multiple matching edges found" in result.stderr
    assert graph_path.read_bytes() == before


def test_cli_nodes_fields_projects_selected_fields(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_contracts(workspace / ".graph")
    graph = Graph(workspace / ".graph")
    graph.add_node("orders", "Orders API", "API", {"language": "python"})
    graph.add_node("indexer", "Indexer", "WORKER", {})

    result = _run_graph(workspace, "nodes", "--type=API", "--fields=name,properties,id")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "rows": [{
            "name": "Orders API",
            "properties": {"language": "python"},
            "id": "orders",
        }],
        "total": 1,
        "truncated": False,
    }


def test_cli_nodes_type_filter_accepts_comma_separated_types(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_contracts(workspace / ".graph")
    graph = Graph(workspace / ".graph")
    graph.add_node("orders", "Orders API", "API", {"language": "python"})
    graph.add_node("indexer", "Indexer", "WORKER", {})

    result = _run_graph(workspace, "nodes", "--type=api,worker", "--fields=type")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "rows": [{"type": "API"}, {"type": "WORKER"}],
        "total": 2,
        "truncated": False,
    }


def test_cli_nodes_limit_reports_total_matches_and_truncation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_contracts(workspace / ".graph")
    graph = Graph(workspace / ".graph")
    graph.add_node("orders", "Orders API", "API", {"language": "python"})
    graph.add_node("stock", "Stock API", "API", {"language": "python"})
    graph.add_node("indexer", "Indexer", "WORKER", {})

    result = _run_graph(workspace, "nodes", "--type=API", "--limit=1", "--fields=id")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "rows": [{"id": "orders"}],
        "total": 2,
        "truncated": True,
    }


def test_cli_edges_limit_reports_total_matches_and_truncation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_contracts(workspace / ".graph")
    graph = Graph(workspace / ".graph")
    graph.add_node("orders", "Orders API", "API", {"language": "python"})
    graph.add_node("stock", "Stock API", "API", {"language": "python"})
    graph.add_node("catalog", "Catalog API", "API", {"language": "python"})
    graph.add_edge("orders", "CALLS", "stock", {"protocol": "http"})
    graph.add_edge("orders", "CALLS", "catalog", {"protocol": "https"})

    result = _run_graph(workspace, "edges", "--from=orders", "--limit=1")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "rows": [["orders", "CALLS", "catalog", "API"]],
        "total": 2,
        "truncated": True,
    }


def test_cli_view_loads_template_relative_to_command_from_workspace(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_contracts(workspace / ".graph")
    Graph(workspace / ".graph").add_node(
        "orders", "Orders API", "API", {"language": "python"},
    )

    result = _run_graph(workspace, "view", "--no-open")

    assert result.returncode == 0, result.stderr
    view_path = workspace / ".graph" / "view.html"
    assert view_path.is_file()
    assert "orders" in view_path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("args", "error"),
    [
        (("--fields=",), "--fields requires comma-separated field names"),
        (("--fields=id,,name",), "--fields requires comma-separated field names"),
        (("--fields=id,unknown",), "unknown field: unknown"),
        (("orders", "--fields=id"), "--fields cannot be combined with a node ID"),
    ],
)
def test_cli_nodes_fields_rejects_invalid_usage(
    tmp_path: Path, args: tuple[str, ...], error: str
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_contracts(workspace / ".graph")
    Graph(workspace / ".graph").add_node("orders", "Orders API", "API", {"language": "python"})

    result = _run_graph(workspace, "nodes", *args)

    assert result.returncode != 0
    assert error in result.stderr


def test_cli_traverse_requires_positional_node_id(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_contracts(workspace / ".graph")

    missing_node = _run_graph(workspace, "traverse", "--from=orders")
    extra_node = _run_graph(workspace, "traverse", "orders", "stock")
    old_anchor_flag = _run_graph(workspace, "traverse", "orders", "--to=stock")

    assert missing_node.returncode != 0
    assert "NODE_ID positional argument" in missing_node.stderr
    assert extra_node.returncode != 0
    assert "NODE_ID positional argument" in extra_node.stderr
    assert old_anchor_flag.returncode != 0
    assert "--from and --to are not supported" in old_anchor_flag.stderr
