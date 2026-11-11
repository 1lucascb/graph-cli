import json
import os
import subprocess
import sys
from pathlib import Path

from graph_lcb.graphs.status import compute_status
from graph_lcb.graphs.types import Edge, Node


ROOT = Path(__file__).resolve().parents[1]


def test_compute_status_snapshot_and_graph_definitions() -> None:
    nodes = [
        Node(id="d", type="WORKER", name="D"),
        Node(id="c", type="WORKER", name="C"),
        Node(id="b", type="API", name="B", evidences=[{"source": "b.py"}]),
        Node(id="a", type="API", name="A", description=" "),
    ]
    edges = [
        Edge(id="e1", type="CALLS", source="a", target="b", description="connects"),
        Edge(id="e2", type="CALLS", source="c", target="c", description=" "),
        Edge(id="e3", type="CALLS", source="d", target="missing", description="dangling"),
    ]

    result = compute_status({}, {}, {"nodes": nodes, "edges": edges},
                            ["orphans", "no-evidence", "no-description", "components"], 1)

    assert result == {
        "nodes": {"total": 4, "by_type": {"API": 2, "WORKER": 2}},
        "edges": {"total": 3, "by_type": {"CALLS": 3}},
        "orphans": {"count": 1, "ids": ["d"], "truncated": False},
        "no_evidence": {
            "nodes": {"count": 3, "ids": ["a"], "truncated": True},
            "edges": {"count": 3, "ids": [["a", "CALLS", "b", "API"]], "truncated": True},
        },
        "no_description": {
            "nodes": {"count": 4, "ids": ["a"], "truncated": True},
            "edges": {"count": 1, "ids": [["c", "CALLS", "c", "WORKER"]], "truncated": False},
        },
        "components": {"count": 2, "largest": 2},
    }


def _invoke(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(ROOT), environment.get("PYTHONPATH", "")])
    )
    return subprocess.run([sys.executable, str(ROOT / "graph"), *args], cwd=cwd,
                          env=environment, capture_output=True, text=True)


def _workspace(tmp_path: Path, *, with_store: bool = True) -> Path:
    directory = tmp_path / ".graph"
    directory.mkdir()
    (directory / "entities.json").write_text(
        json.dumps({"API": {"properties": {}}}), encoding="utf-8"
    )
    (directory / "edges.json").write_text(
        json.dumps({"LINK": {"source": ["API"], "target": ["API"], "properties": {}}}),
        encoding="utf-8",
    )
    if with_store:
        (directory / "graph.json").write_text('{"nodes":[],"edges":[]}', encoding="utf-8")
    return directory


def test_status_missing_store_is_empty_and_checks_are_selective(tmp_path: Path) -> None:
    _workspace(tmp_path, with_store=False)

    result = _invoke(tmp_path, "status", "--check=components")

    assert result.returncode == 0
    assert json.loads(result.stdout) == {
        "nodes": {"total": 0, "by_type": {}},
        "edges": {"total": 0, "by_type": {}},
        "components": {"count": 0, "largest": 0},
        "valid": True,
    }


def test_status_unknown_check_lists_valid_names(tmp_path: Path) -> None:
    _workspace(tmp_path)

    result = _invoke(tmp_path, "status", "--check=unknown")

    assert result.returncode == 2
    assert "orphans, no-evidence, no-description, components" in result.stderr


def test_status_strict_returns_three_only_for_selected_findings(tmp_path: Path) -> None:
    directory = _workspace(tmp_path)
    (directory / "graph.json").write_text(json.dumps({
        "nodes": [{"id": "alone", "type": "API", "name": "Alone"}], "edges": [],
    }), encoding="utf-8")

    strict = _invoke(tmp_path, "status", "--check=orphans", "--strict")
    unselected = _invoke(tmp_path, "status", "--check=components", "--strict")

    assert strict.returncode == 3
    assert json.loads(strict.stdout)["orphans"]["count"] == 1
    assert unselected.returncode == 0


def test_status_reports_semantically_invalid_dangling_edge(tmp_path: Path) -> None:
    directory = _workspace(tmp_path)
    (directory / "graph.json").write_text(json.dumps({
        "nodes": [{"id": "a", "type": "API", "name": "A"}],
        "edges": [{"id": "e1", "type": "LINK", "source": "a", "target": "missing"}],
    }), encoding="utf-8")

    result = _invoke(tmp_path, "status", "--check=orphans,components")

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["valid"] is False
    assert output["orphans"]["ids"] == ["a"]
    assert output["components"] == {"count": 0, "largest": 0}


def test_status_requires_initialized_workspace(tmp_path: Path) -> None:
    result = _invoke(tmp_path, "status")

    assert result.returncode == 2
    assert "not initialized" in result.stderr
