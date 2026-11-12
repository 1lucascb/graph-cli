import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


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
    assert json.loads(first.stdout) == {
        "initialized": True, "directory": ".graph", "contracts": "empty"
    }
    graph_directory = tmp_path / ".graph"
    expected_files = {
        "entities.json",
        "edges.json",
        "schemas/entities.schema.json",
        "schemas/edges.schema.json",
    }
    assert {path.relative_to(graph_directory).as_posix()
            for path in graph_directory.rglob("*") if path.is_file()} == expected_files
    assert json.loads((graph_directory / "entities.json").read_text(encoding="utf-8")) == {
        "$schema": "./schemas/entities.schema.json"
    }
    assert json.loads((graph_directory / "edges.json").read_text(encoding="utf-8")) == {
        "$schema": "./schemas/edges.schema.json"
    }

    custom_entities = '{"CUSTOM":{"properties":{}}}\n'
    (graph_directory / "entities.json").write_text(custom_entities, encoding="utf-8")
    graph_store = '{"nodes":[],"edges":[]}\n'
    (graph_directory / "graph.json").write_text(graph_store, encoding="utf-8")

    second = invoke(tmp_path, "init")

    assert second.returncode == 0
    assert json.loads(second.stdout)["contracts"] == "existing"
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


def test_contract_displays_empty_contracts_without_creating_workspace(tmp_path: Path) -> None:
    result = invoke(tmp_path, "contract")

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output == {"entities": {}, "edges": {}}
    assert not (tmp_path / ".graph").exists()


@pytest.mark.parametrize("template", ["codebase", "documents", "data-pipeline", "research"])
def test_each_template_initializes_and_validates(tmp_path: Path, template: str) -> None:
    result = invoke(tmp_path, "init", f"--template={template}")

    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["contracts"] == "template"
    assert output["template"] == template
    assert output["applied"] is True
    assert invoke(tmp_path, "validate").returncode == 0

    entities = json.loads((tmp_path / ".graph" / "entities.json").read_text(encoding="utf-8"))
    edges = json.loads((tmp_path / ".graph" / "edges.json").read_text(encoding="utf-8"))
    entity_types = set(entities) - {"$schema"}
    for entity_type, definition in entities.items():
        if entity_type == "$schema":
            continue
        properties = definition["properties"]
        assert properties
        assert any(isinstance(value, dict) and value.get("required") is True
                   for value in properties.values())
    for edge_type, definition in edges.items():
        if edge_type == "$schema":
            continue
        assert definition["properties"]
        assert any(isinstance(value, dict) and value.get("required") is True
                   for value in definition["properties"].values())
        assert set(definition["source"]) <= entity_types
        assert set(definition["target"]) <= entity_types


def test_template_fills_existing_empty_contracts_and_preserves_populated_ones(tmp_path: Path) -> None:
    assert invoke(tmp_path, "init").returncode == 0
    graph_directory = tmp_path / ".graph"

    applied = invoke(tmp_path, "init", "--template", "codebase")
    assert applied.returncode == 0, applied.stderr
    assert json.loads(applied.stdout)["applied"] is True
    assert "FILE" in json.loads((graph_directory / "entities.json").read_text(encoding="utf-8"))

    original_entities = (graph_directory / "entities.json").read_text(encoding="utf-8")
    skipped = invoke(tmp_path, "init", "--template=documents")
    assert skipped.returncode == 0
    assert json.loads(skipped.stdout)["applied"] is False
    assert (graph_directory / "entities.json").read_text(encoding="utf-8") == original_entities


def test_init_list_templates_does_not_create_workspace(tmp_path: Path) -> None:
    result = invoke(tmp_path, "init", "--list-templates")

    assert result.returncode == 0
    assert {line.split("\t", 1)[0] for line in result.stdout.splitlines()} == {
        "codebase", "documents", "data-pipeline", "research"
    }
    assert not (tmp_path / ".graph").exists()


def test_init_dry_run_and_unknown_template_do_not_write(tmp_path: Path) -> None:
    preview = invoke(tmp_path, "init", "--template=codebase", "--dry-run")
    assert preview.returncode == 0
    preview_output = json.loads(preview.stdout)
    assert preview_output["applied"] is False
    assert preview_output["dry_run"] is True
    assert "would_write" in preview_output
    assert not (tmp_path / ".graph").exists()

    unknown = invoke(tmp_path, "init", "--template=unknown")
    assert unknown.returncode == 2
    assert "valid templates" in unknown.stderr
    assert not (tmp_path / ".graph").exists()


def test_template_required_properties_reject_empty_node_and_edge_properties(tmp_path: Path) -> None:
    initialized = invoke(tmp_path, "init", "--template=codebase")
    assert initialized.returncode == 0, initialized.stderr

    missing_node_property = invoke(tmp_path, "add-node", "api", "API", "API")
    assert missing_node_property.returncode == 2
    assert "missing required property" in missing_node_property.stderr

    first = invoke(tmp_path, "add-node", "api", "API", "API", "--p.language=Python")
    second = invoke(tmp_path, "add-node", "worker", "Worker", "WORKER", "--p.runtime=Python")
    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    missing_edge_property = invoke(tmp_path, "add-edge", "api", "CALLS", "worker")
    assert missing_edge_property.returncode == 2
    assert "missing required property" in missing_edge_property.stderr


def test_help_does_not_create_workspace(tmp_path: Path) -> None:
    result = invoke(tmp_path, "--help")

    assert result.returncode == 0
    assert "init" in result.stdout
    assert not (tmp_path / ".graph").exists()
