import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
GRAPH_SCRIPT = ROOT / "graph"


@pytest.fixture
def graph_directory(tmp_path: Path) -> Path:
    directory = tmp_path / ".graph"
    directory.mkdir()
    (directory / "entities.json").write_text(json.dumps({
        "API": {"properties": {}},
        "WORKER": {"properties": {}},
    }), encoding="utf-8")
    (directory / "edges.json").write_text(json.dumps({
        "CALLS": {
            "source": ["API"], "target": ["API"], "properties": {},
        },
        "RUNS": {
            "source": ["WORKER"], "target": ["API"], "properties": {},
        },
    }), encoding="utf-8")
    return directory


def run_graph(directory: Path, *args: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(ROOT), environment.get("PYTHONPATH", "")])
    )
    return subprocess.run(
        [sys.executable, str(GRAPH_SCRIPT), *args], cwd=directory.parent,
        env=environment, capture_output=True, text=True,
    )


def test_add_node_resolves_entity_type_case_insensitively(graph_directory: Path) -> None:
    result = run_graph(graph_directory, "add-node", "orders", "Orders API", "aPi")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["type"] == "API"

@pytest.mark.parametrize("node_id", ["Bad", "bad id", "_hidden", ".hidden", "-hidden"])
def test_add_node_rejects_ids_outside_shared_pattern(
    graph_directory: Path, node_id: str,
) -> None:
    result = run_graph(graph_directory, "add-node", "--", node_id, "Orders API", "API")

    assert result.returncode == 2
    assert "node id must match ^[a-z0-9][a-z0-9._-]*$" in result.stderr
    store = graph_directory / "graph.json"
    assert not store.exists()


def test_add_edge_resolves_edge_and_endpoint_types_case_insensitively(
    graph_directory: Path,
) -> None:
    run_graph(graph_directory, "add-node", "orders", "Orders", "api")
    run_graph(graph_directory, "add-node", "stock", "Stock", "API")

    result = run_graph(graph_directory, "add-edge", "orders", "cAlLs", "stock")

    assert result.returncode == 0, result.stderr
    edge = json.loads(result.stdout)
    assert edge["type"] == "CALLS"
    assert edge["target_type"] == "API"


@pytest.mark.parametrize("command", ["traverse", "path"])
def test_edge_filters_resolve_case_insensitively(
    graph_directory: Path, command: str,
) -> None:
    run_graph(graph_directory, "add-node", "orders", "Orders", "API")
    run_graph(graph_directory, "add-node", "stock", "Stock", "API")
    run_graph(graph_directory, "add-edge", "orders", "CALLS", "stock")

    if command == "traverse":
        result = run_graph(graph_directory, "traverse", "orders", "--edge=cAlLs")
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["nodes"] == [
            ["orders", "API", "Orders"], ["stock", "API", "Stock"],
        ]
    else:
        result = run_graph(graph_directory, "path", "orders", "stock", "--edge=cAlLs")
        assert result.returncode == 0, result.stderr
        assert len(json.loads(result.stdout)["paths"]) == 1


def test_edge_type_filter_accepts_comma_separated_types(
    graph_directory: Path,
) -> None:
    run_graph(graph_directory, "add-node", "orders", "Orders", "API")
    run_graph(graph_directory, "add-node", "stock", "Stock", "API")
    run_graph(graph_directory, "add-node", "worker", "Worker", "WORKER")
    run_graph(graph_directory, "add-edge", "orders", "CALLS", "stock")
    run_graph(graph_directory, "add-edge", "worker", "RUNS", "stock")

    result = run_graph(graph_directory, "edges", "--type=calls,rUnS", "--fields=type")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "rows": [{"type": "CALLS"}, {"type": "RUNS"}],
        "total": 2,
        "truncated": False,
    }


@pytest.mark.parametrize(
    ("raw_types", "error"),
    [
        ("CALLS,", "--type requires comma-separated edge type names"),
        ("CALLS,UNKNOWN", "unknown edge type: UNKNOWN"),
    ],
)
def test_edge_type_filter_rejects_empty_or_unknown_types(
    graph_directory: Path, raw_types: str, error: str,
) -> None:
    result = run_graph(graph_directory, "edges", f"--type={raw_types}")

    assert result.returncode != 0
    assert error in result.stderr
