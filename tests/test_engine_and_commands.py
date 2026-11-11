import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from graph_lcb.graphs.engine import Graph, GraphError
from graph_lcb.graphs.types import Edge, Node

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


def _run_graph(
    directory: Path, *args: str, input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
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
        input=input_text,
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
        ROOT / "graph_lcb" / "schemas" / "entities.schema.json"
    ).read_bytes()
    assert (graph_directory / "schemas" / "edges.schema.json").read_bytes() == (
        ROOT / "graph_lcb" / "schemas" / "edges.schema.json"
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


def test_cli_property_flags_add_typed_node_and_edge_properties(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_contracts(workspace / ".graph")
    entities_path = workspace / ".graph" / "entities.json"
    entities = json.loads(entities_path.read_text(encoding="utf-8"))
    entities["API"]["properties"].update({
        "retries": {"type": "integer", "required": False},
        "enabled": {"type": "boolean", "required": False},
    })
    entities_path.write_text(json.dumps(entities), encoding="utf-8")
    edges_path = workspace / ".graph" / "edges.json"
    edge_contracts = json.loads(edges_path.read_text(encoding="utf-8"))
    edge_contracts["CALLS"]["properties"]["weight"] = {"type": "number", "required": False}
    edges_path.write_text(json.dumps(edge_contracts), encoding="utf-8")

    add_node = _run_graph(
        workspace, "add-node", "orders", "Orders", "API",
        "--p.language=python", "--p.retries=3", "--p.enabled=true",
    )
    add_second = _run_graph(
        workspace, "add-node", "stock", "Stock", "API", "--p.language=python",
    )

    assert add_node.returncode == 0, add_node.stderr
    assert json.loads(add_node.stdout)["properties"] == {
        "language": "python", "retries": 3, "enabled": True,
    }
    assert add_second.returncode == 0, add_second.stderr

    add_edge = _run_graph(
        workspace, "add-edge", "orders", "CALLS", "stock",
        "--p.protocol=https", "--p.weight=1.5",
    )

    assert add_edge.returncode == 0, add_edge.stderr
    edge = json.loads(add_edge.stdout)
    assert edge["properties"] == {"protocol": "https", "weight": 1.5}


def test_cli_property_flags_patch_and_validate_node_and_edge_properties(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_contracts(workspace / ".graph")
    entities_path = workspace / ".graph" / "entities.json"
    entities = json.loads(entities_path.read_text(encoding="utf-8"))
    entities["API"]["properties"]["retries"] = {"type": "integer", "required": False}
    entities_path.write_text(json.dumps(entities), encoding="utf-8")
    edges_path = workspace / ".graph" / "edges.json"
    edge_contracts = json.loads(edges_path.read_text(encoding="utf-8"))
    edge_contracts["CALLS"]["properties"]["weight"] = {"type": "number", "required": False}
    edges_path.write_text(json.dumps(edge_contracts), encoding="utf-8")
    graph = Graph(workspace / ".graph")
    graph.add_node("orders", "Orders", "API", {"language": "python", "retries": 1})
    graph.add_node("stock", "Stock", "API", {"language": "python"})
    edge = graph.add_edge("orders", "CALLS", "stock", {"protocol": "https", "weight": 1.5})

    edit_node = _run_graph(workspace, "edit", "node", "orders", "--p.retries=4")
    invalid_node = _run_graph(workspace, "edit", "node", "orders", '--p.language=4')
    mixed_node = _run_graph(
        workspace, "edit", "node", "orders", '--properties={"language":"python"}',
        "--p.retries=4",
    )
    edit_edge = _run_graph(workspace, "edit", "edge", edge.id, "--p.weight=2")
    invalid_edge = _run_graph(workspace, "edit", "edge", edge.id, "--p.weight=not-json")

    assert edit_node.returncode == 0, edit_node.stderr
    assert json.loads(edit_node.stdout)["properties"] == {"language": "python", "retries": 4}
    assert invalid_node.returncode != 0
    assert "property language must be string" in invalid_node.stderr
    assert mixed_node.returncode != 0
    assert "cannot be combined" in mixed_node.stderr
    assert edit_edge.returncode == 0, edit_edge.stderr
    assert json.loads(edit_edge.stdout)["properties"] == {"protocol": "https", "weight": 2}
    assert invalid_edge.returncode != 0
    assert "property weight must be number" in invalid_edge.stderr


def test_cli_nodes_p_property_filter_is_case_insensitive_and_composable(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_contracts(workspace / ".graph")
    entities_path = workspace / ".graph" / "entities.json"
    entities = json.loads(entities_path.read_text(encoding="utf-8"))
    entities["API"]["properties"]["runtime"] = {"type": "string", "required": False}
    entities_path.write_text(json.dumps(entities), encoding="utf-8")
    graph = Graph(workspace / ".graph")
    graph.add_node("one", "One", "API", {"language": "Python", "runtime": "FastAPI"})
    graph.add_node("two", "Two", "API", {"language": "PYTHON", "runtime": "Flask"})
    graph.add_node("three", "Three", "API", {"language": "Go", "runtime": "Gin"})

    insensitive = _run_graph(workspace, "nodes", "--p.language=python", "--fields=id")
    exact = _run_graph(workspace, "nodes", '--properties={"language":"Python"}', "--fields=id")
    combined = _run_graph(
        workspace, "nodes", '--properties={"language":"Python"}',
        "--p.runtime=fastapi", "--fields=id",
    )
    duplicate = _run_graph(
        workspace, "nodes", '--properties={"language":"Python"}',
        "--p.language=python", "--fields=id",
    )

    assert insensitive.returncode == 0, insensitive.stderr
    assert json.loads(insensitive.stdout)["rows"] == [{"id": "one"}, {"id": "two"}]
    assert exact.returncode == 0, exact.stderr
    assert json.loads(exact.stdout)["rows"] == [{"id": "one"}]
    assert combined.returncode == 0, combined.stderr
    assert json.loads(combined.stdout)["rows"] == [{"id": "one"}]
    assert duplicate.returncode != 0
    assert "filtered more than once" in duplicate.stderr


def test_cli_edges_p_property_filter_is_case_insensitive_and_composable(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_contracts(workspace / ".graph")
    edges_path = workspace / ".graph" / "edges.json"
    edge_contracts = json.loads(edges_path.read_text(encoding="utf-8"))
    edge_contracts["CALLS"]["properties"]["weight"] = {"type": "number", "required": False}
    edges_path.write_text(json.dumps(edge_contracts), encoding="utf-8")
    graph = Graph(workspace / ".graph")
    graph.add_node("source", "Source", "API", {"language": "python"})
    graph.add_node("target", "Target", "API", {"language": "python"})
    graph.add_edge("source", "CALLS", "target", {"protocol": "HTTPS", "weight": 1}, description="secure")
    graph.add_edge("source", "CALLS", "target", {"protocol": "http", "weight": 2}, description="plain")

    insensitive = _run_graph(workspace, "edges", "--p.protocol=https", "--fields=properties")
    exact = _run_graph(
        workspace, "edges", '--properties={"protocol":"HTTPS"}', "--fields=properties",
    )
    combined = _run_graph(
        workspace, "edges", '--properties={"weight":1}', "--p.protocol=https",
        "--fields=properties",
    )

    assert insensitive.returncode == 0, insensitive.stderr
    assert json.loads(insensitive.stdout)["rows"] == [{"properties": {"protocol": "HTTPS", "weight": 1}}]
    assert exact.returncode == 0, exact.stderr
    assert json.loads(exact.stdout)["rows"] == [{"properties": {"protocol": "HTTPS", "weight": 1}}]
    assert combined.returncode == 0, combined.stderr
    assert json.loads(combined.stdout)["rows"] == [{"properties": {"protocol": "HTTPS", "weight": 1}}]


def test_cli_import_applies_nodes_before_edges_and_generates_missing_edge_ids(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_contracts(workspace / ".graph")
    import_path = workspace / "records.jsonl"
    import_path.write_text(
        '\n'.join([
            json.dumps({"kind": "edge", "type": "CALLS", "source": "a", "target": "b", "properties": {"protocol": "grpc"}}),
            json.dumps({"id": "a", "type": "API", "name": "A", "properties": {"language": "python"}}),
            json.dumps({"id": "b", "type": "API", "name": "B", "properties": {"language": "go"}}),
        ]) + '\n',
        encoding="utf-8",
    )

    result = _run_graph(workspace, "import", str(import_path))

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["valid"] is True
    assert payload["dry_run"] is False
    assert payload["summary"] == {"created": 3, "updated": 0, "unchanged": 0, "errors": 0}
    store = json.loads((workspace / ".graph" / "graph.json").read_text(encoding="utf-8"))
    assert [node["id"] for node in store["nodes"]] == ["a", "b"]
    assert store["edges"][0]["source"] == "a"
    assert store["edges"][0]["target"] == "b"
    assert store["edges"][0]["id"]


def test_cli_import_dry_run_from_stdin_does_not_write_store(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_contracts(workspace / ".graph")
    line = json.dumps({"id": "a", "type": "API", "name": "A", "properties": {"language": "python"}})

    result = _run_graph(workspace, "import", "-", "--dry-run", input_text=line + "\n")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "valid": True,
        "dry_run": True,
        "summary": {"created": 1, "updated": 0, "unchanged": 0, "errors": 0},
        "errors": [],
    }
    assert not (workspace / ".graph" / "graph.json").exists()


def test_cli_import_validation_errors_include_line_and_preserve_store_atomically(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_contracts(workspace / ".graph")
    graph = Graph(workspace / ".graph")
    graph.add_node("existing", "Existing", "API", {"language": "python"})
    graph_path = workspace / ".graph" / "graph.json"
    before = graph_path.read_bytes()
    import_path = workspace / "invalid.jsonl"
    import_path.write_text(
        '\n'.join([
            json.dumps({"id": "new-node", "type": "API", "name": "New", "properties": {"language": "python"}}),
            json.dumps({"kind": "edge", "id": "dangling-edge", "type": "CALLS", "source": "new-node", "target": "missing"}),
            "{invalid json",
        ]) + '\n',
        encoding="utf-8",
    )

    result = _run_graph(workspace, "import", str(import_path))

    assert result.returncode == 3
    payload = json.loads(result.stdout)
    assert payload["valid"] is False
    assert payload["summary"] == {"created": 2, "updated": 0, "unchanged": 0, "errors": 2}
    assert {error["line"] for error in payload["errors"]} == {2, 3}
    assert graph_path.read_bytes() == before


def test_cli_import_on_conflict_error_skip_replace_and_dry_run(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_contracts(workspace / ".graph")
    graph = Graph(workspace / ".graph")
    graph.add_node("a", "Old A", "API", {"language": "python"})
    graph.add_node("b", "Old B", "API", {"language": "python"})
    existing_edge = graph.add_edge("a", "CALLS", "b", {"protocol": "http"}, description="old edge")
    graph_path = workspace / ".graph" / "graph.json"
    before = graph_path.read_bytes()
    import_path = workspace / "replacement.jsonl"
    import_path.write_text(
        '\n'.join([
            json.dumps({"kind": "node", "id": "a", "type": "API", "name": "New A", "properties": {"language": "python"}}),
            json.dumps({"kind": "edge", "id": existing_edge.id, "type": "CALLS", "source": "a", "target": "b", "description": "updated edge", "properties": {"protocol": "http"}}),
        ]) + '\n',
        encoding="utf-8",
    )

    default_error = _run_graph(workspace, "import", str(import_path))
    skip = _run_graph(workspace, "import", str(import_path), "--on-conflict=skip")
    dry_replace = _run_graph(workspace, "import", str(import_path), "--on-conflict=replace", "--dry-run")

    assert default_error.returncode == 3
    assert json.loads(default_error.stdout)["summary"] == {
        "created": 0, "updated": 0, "unchanged": 0, "errors": 2,
    }
    assert graph_path.read_bytes() == before
    assert skip.returncode == 0, skip.stderr
    assert json.loads(skip.stdout)["summary"] == {
        "created": 0, "updated": 0, "unchanged": 2, "errors": 0,
    }
    assert graph_path.read_bytes() == before
    assert dry_replace.returncode == 0, dry_replace.stderr
    assert json.loads(dry_replace.stdout)["summary"] == {
        "created": 0, "updated": 2, "unchanged": 0, "errors": 0,
    }
    assert graph_path.read_bytes() == before

    replace = _run_graph(workspace, "import", str(import_path), "--on-conflict=replace")

    assert replace.returncode == 0, replace.stderr
    assert json.loads(replace.stdout)["summary"] == {
        "created": 0, "updated": 2, "unchanged": 0, "errors": 0,
    }
    replaced = Graph(workspace / ".graph").load()
    assert next(node for node in replaced["nodes"] if node.id == "a").name == "New A"
    assert replaced["edges"][0].id == existing_edge.id
    assert replaced["edges"][0].description == "updated edge"

    unchanged = _run_graph(workspace, "import", str(import_path), "--on-conflict=replace")
    assert unchanged.returncode == 0, unchanged.stderr
    assert json.loads(unchanged.stdout)["summary"] == {
        "created": 0, "updated": 0, "unchanged": 2, "errors": 0,
    }

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
