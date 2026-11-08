import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
GRAPH_SCRIPT = ROOT / "graph"


def write_contracts(directory: Path, *, invalid: bool = False) -> None:
    (directory / "entities.json").write_text(json.dumps({
        "API": {"properties": {"name": {"type": "string", "required": True}}},
        "WORKER": {"properties": {}},
    }), encoding="utf-8")
    edges = {"LINK": {"source": ["API"], "target": ["API"], "properties": {}}}
    if invalid:
        edges["LINK"]["source"] = ["UNKNOWN"]
    (directory / "edges.json").write_text(json.dumps(edges), encoding="utf-8")


def invoke(directory: Path, *args: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, [str(ROOT), environment.get("PYTHONPATH", "")])
    )
    return subprocess.run(
        [sys.executable, str(GRAPH_SCRIPT), *args], cwd=directory,
        env=environment, capture_output=True, text=True,
    )


def make_directory(tmp_path: Path) -> Path:
    directory = tmp_path / ".graph"
    directory.mkdir()
    write_contracts(directory)
    return directory


def put_store(directory: Path, nodes: list[dict], edges: list[dict]) -> bytes:
    payload = json.dumps({"nodes": nodes, "edges": edges}).encode()
    (directory / "graph.json").write_bytes(payload)
    return payload


def node(node_id: str = "a", kind: str = "API", props: dict | None = None) -> dict:
    return {"id": node_id, "type": kind, "name": node_id,
            "properties": {"name": "A"} if props is None else props}


def edge(edge_id: str = "e1", source: str = "a", target: str = "b", **kwargs) -> dict:
    return {"id": edge_id, "type": "LINK", "source": source, "target": target,
            "description": kwargs.get("description", "linked"),
            "properties": kwargs.get("properties", {})}


def run_validation(directory: Path) -> tuple[subprocess.CompletedProcess[str], dict]:
    result = invoke(directory.parent, "validate")
    return result, json.loads(result.stdout)


def test_valid_graph_returns_zero_and_does_not_modify_store(tmp_path: Path) -> None:
    directory = make_directory(tmp_path)
    before = put_store(directory, [node(), node("b")], [edge()])

    result, output = run_validation(directory)

    assert result.returncode == 0
    assert output == {"valid": True, "errors": [],
                      "summary": {"nodes": 2, "edges": 1, "errors": 0}}
    assert (directory / "graph.json").read_bytes() == before


@pytest.mark.parametrize(("code", "nodes", "edges", "invalid_contract"), [
    ("invalid_contract", [node()], [], True),
    ("invalid_record", [{"id": "x"}], [] , False),
    ("duplicate_id", [node(), node()], [], False),
    ("invalid_id", [node("Bad ID")], [], False),
    ("unknown_type", [node(kind="BOGUS")], [], False),
    ("missing_required_property", [node(props={})], [], False),
    ("unknown_property", [node(props={"name": "A", "extra": 1})], [], False),
    ("invalid_property_type", [node(props={"name": 3})], [], False),
    ("dangling_endpoint", [node()], [edge(target="missing")], False),
    ("endpoint_not_allowed", [node(), node("worker", "WORKER")],
     [edge(source="worker", target="a")], False),
    ("duplicate_edge", [node(), node("b")],
     [edge(), edge("e2")], False),
    ("parallel_edge_needs_description", [node(), node("b")],
     [edge(description="first"), edge("e2", description="")], False),
])
def test_each_validation_error_code_is_reported(
    tmp_path: Path, code: str, nodes: list[dict], edges: list[dict],
    invalid_contract: bool,
) -> None:
    directory = make_directory(tmp_path)
    if invalid_contract:
        write_contracts(directory, invalid=True)
    put_store(directory, nodes, edges)

    result, output = run_validation(directory)

    assert result.returncode == 3
    assert code in {issue["code"] for issue in output["errors"]}


def test_reports_multiple_violations_together(tmp_path: Path) -> None:
    directory = make_directory(tmp_path)
    put_store(directory, [node("Bad ID", kind="API", props={})],
               [edge(target="absent")])

    result, output = run_validation(directory)

    assert result.returncode == 3
    codes = {issue["code"] for issue in output["errors"]}
    assert {"invalid_id", "missing_required_property",
            "dangling_endpoint"}.issubset(codes)
    assert "unknown_type" not in codes


def test_reports_contract_violations_together_with_store_violations(tmp_path: Path) -> None:
    directory = make_directory(tmp_path)
    write_contracts(directory, invalid=True)
    put_store(directory, [node("Bad ID", kind="API", props={})],
               [edge(target="absent")])

    result, output = run_validation(directory)

    assert result.returncode == 3
    codes = {issue["code"] for issue in output["errors"]}
    assert "invalid_contract" in codes
    assert {"invalid_id", "missing_required_property",
            "dangling_endpoint"}.issubset(codes)


def test_missing_contract_returns_four_without_creating_files(tmp_path: Path) -> None:
    directory = tmp_path / ".graph"
    directory.mkdir()

    result = invoke(tmp_path, "validate")

    assert result.returncode == 4
    assert json.loads(result.stdout)["valid"] is False
    assert not (directory / "entities.json").exists()
    assert not (directory / "edges.json").exists()


def test_bad_arguments_are_usage_errors(tmp_path: Path) -> None:
    make_directory(tmp_path)

    result = invoke(tmp_path, "validate", "extra")

    assert result.returncode == 2
    assert result.stdout == ""


@pytest.mark.parametrize(
    ("contract_file", "types"),
    [
        ("entities.json", {"API": {"properties": {}}, "api": {"properties": {}}}),
        ("edges.json", {
            "LINK": {"source": ["API"], "target": ["API"], "properties": {}},
            "link": {"source": ["API"], "target": ["API"], "properties": {}},
        }),
    ],
)
def test_case_colliding_types_fail_contract_load_and_validate(
    tmp_path: Path, contract_file: str, types: dict,
) -> None:
    directory = make_directory(tmp_path)
    (directory / contract_file).write_text(json.dumps(types), encoding="utf-8")

    command_result = invoke(tmp_path, "contract")
    validation_result, output = run_validation(directory)

    assert command_result.returncode != 0
    assert validation_result.returncode == 3
    assert output["valid"] is False
    assert output["errors"][0]["code"] == "invalid_contract"
    assert "unique ignoring case" in output["errors"][0]["message"]
