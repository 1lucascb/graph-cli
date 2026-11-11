import json
import os
import subprocess
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_graph(directory: Path, *args: str):
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(ROOT), env.get("PYTHONPATH", "")]))
    return subprocess.run([sys.executable, str(ROOT / "graph"), *args], cwd=directory,
                          env=env, capture_output=True, text=True)


def setup_graph(directory: Path):
    path = directory / ".graph"
    path.mkdir()
    (path / "entities.json").write_text(json.dumps({"API": {"properties": {"language": "string"}}}), encoding="utf-8")
    (path / "edges.json").write_text(json.dumps({"CALLS": {"source": ["API"], "target": ["API"], "properties": {}}}), encoding="utf-8")
    (path / "graph.json").write_text(json.dumps({"nodes": [
        {"id": "a", "type": "API", "name": "Orders", "description": "handles payments", "properties": {"language": "python"}, "evidences": [{"locator": {"path": "src/order.py"}}]},
        {"id": "b", "type": "API", "name": "Billing", "description": "handles invoices", "properties": {"language": "go"}, "evidences": []},
    ], "edges": [{"id": "e", "type": "CALLS", "source": "a", "target": "b", "description": "payment request", "properties": {}, "evidences": []}]}), encoding="utf-8")


def test_search_and_or_not_and_paging(tmp_path):
    setup_graph(tmp_path)
    result = run_graph(tmp_path, "search", "orders", "python")
    assert json.loads(result.stdout)["rows"] == [["node", "a", "API", "Orders", ["name", "properties"]]]
    result = run_graph(tmp_path, "search", "payment", "invoice", "--any", "--not", "invoice", "--limit", "1")
    body = json.loads(result.stdout)
    assert body == {"rows": [["node", "a", "API", "Orders", ["description"]]], "total": 2, "truncated": True, "next_offset": 1}


def test_search_regex_snippets_and_error_shape(tmp_path):
    setup_graph(tmp_path)
    result = run_graph(tmp_path, "search", "pay.*request", "--regex", "--kind=edges", "--snippets")
    assert json.loads(result.stdout)["rows"][0][-1] == {"description": "payment request"}
    result = run_graph(tmp_path, "search", "[", "--regex")
    assert json.loads(result.stdout)["error"]["code"] == "invalid_regex"


def test_search_scope_and_case_sensitivity(tmp_path):
    setup_graph(tmp_path)
    assert json.loads(run_graph(tmp_path, "search", "PYTHON").stdout)["total"] == 1
    assert json.loads(run_graph(tmp_path, "search", "PYTHON", "--case-sensitive").stdout)["total"] == 0
    assert json.loads(run_graph(tmp_path, "search", "src/order.py", "--in=evidences").stdout)["total"] == 1


def test_search_fields_omit_fields_not_applicable_to_result_kind(tmp_path):
    setup_graph(tmp_path)
    result = run_graph(tmp_path, "search", "payment", "--fields=id,name,source,target,type")
    rows = json.loads(result.stdout)["rows"]
    assert rows == [
        ["a", "Orders", "API"],
        ["e", "a", "b", "CALLS"],
    ]
