import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GRAPH_SCRIPT = ROOT / "graph"


def invoke(directory: Path, *args: str) -> subprocess.CompletedProcess[str]:
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


def test_init_creates_workspace_and_is_idempotent(tmp_path: Path) -> None:
    first = invoke(tmp_path, "init")

    assert first.returncode == 0
    assert json.loads(first.stdout) == {"initialized": True, "directory": ".graph"}
    graph_directory = tmp_path / ".graph"
    expected_files = {
        "entities.json",
        "edges.json",
        "schemas/entities.schema.json",
        "schemas/edges.schema.json",
    }
    assert {path.relative_to(graph_directory).as_posix()
            for path in graph_directory.rglob("*") if path.is_file()} == expected_files

    custom_entities = '{"CUSTOM":{"properties":{}}}\n'
    (graph_directory / "entities.json").write_text(custom_entities, encoding="utf-8")
    graph_store = '{"nodes":[],"edges":[]}\n'
    (graph_directory / "graph.json").write_text(graph_store, encoding="utf-8")

    second = invoke(tmp_path, "init")

    assert second.returncode == 0
    assert (graph_directory / "entities.json").read_text(encoding="utf-8") == custom_entities
    assert (graph_directory / "graph.json").read_text(encoding="utf-8") == graph_store


def test_init_usage_error_does_not_create_workspace(tmp_path: Path) -> None:
    result = invoke(tmp_path, "init", "extra")

    assert result.returncode == 2
    assert not (tmp_path / ".graph").exists()


def test_graph_operations_require_init_without_creating_files(tmp_path: Path) -> None:
    result = invoke(tmp_path, "nodes")

    assert result.returncode != 0
    assert "Graph workspace not initialized." in result.stderr
    assert "Run 'graph init' to initialize this project." in result.stderr
    assert not (tmp_path / ".graph").exists()


def test_validate_reports_missing_workspace_without_creating_files(tmp_path: Path) -> None:
    result = invoke(tmp_path, "validate")

    assert result.returncode == 4
    output = json.loads(result.stdout)
    assert output["valid"] is False
    assert output["errors"][0]["code"] == "not_initialized"
    assert not (tmp_path / ".graph").exists()


def test_contract_displays_starter_contracts_without_creating_workspace(tmp_path: Path) -> None:
    result = invoke(tmp_path, "contract")

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert "API" in output["entities"]
    assert "CALLS" in output["edges"]
    assert not (tmp_path / ".graph").exists()


def test_help_does_not_create_workspace(tmp_path: Path) -> None:
    result = invoke(tmp_path, "--help")

    assert result.returncode == 0
    assert "init" in result.stdout
    assert not (tmp_path / ".graph").exists()
