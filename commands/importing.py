"""Import JSONL node and edge records as one validated graph update."""

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cli import CLIError, Context
from commands.common import cli, emit
from graphs.engine import Graph
from graphs.types import Edge, Node


@cli.handler(
    "import",
    "Import JSONL records atomically: import FILE [--on-conflict=error|skip|replace] [--dry-run]; use - for stdin.",
)
def import_graph(ctx: Context) -> int:
    if len(ctx.args) != 1:
        raise CLIError("use import FILE [--on-conflict=error|skip|replace] [--dry-run]")
    allowed_options = {"dry-run", "on-conflict"}
    unknown_options = {name for name, _ in ctx._options} - allowed_options
    if unknown_options:
        raise CLIError(f"unknown import option: {', '.join(sorted(unknown_options))}")
    dry_run = ctx.flag("dry-run")
    if dry_run is not None and dry_run is not True:
        raise CLIError("--dry-run does not accept a value")
    on_conflict = ctx.flag("on-conflict", default="error")
    if on_conflict not in {"error", "skip", "replace"}:
        raise CLIError("--on-conflict must be error, skip, or replace")
    input_name = ctx.positional(0)

    try:
        contents = sys.stdin.read() if input_name == "-" else Path(input_name).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise CLIError(f"cannot read import input {input_name}: {exc}") from exc

    graph = Graph()
    existing = graph.load()
    errors: list[dict[str, Any]] = []
    parsed_nodes: list[tuple[Node, int, bool]] = []
    parsed_edges: list[tuple[Edge, int, bool]] = []
    line_by_record: dict[tuple[str, str], int] = {}
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def line_error(line: int, kind: str, code: str, message: str) -> None:
        errors.append({"line": line, "kind": kind, "code": code, "message": message})

    def canonical_type(value: Any, contracts: dict[str, Any]) -> Any:
        if not isinstance(value, str):
            return value
        return next((name for name in contracts if name.casefold() == value.casefold()), value)

    for line_number, line in enumerate(contents.splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            line_error(line_number, "record", "invalid_json", f"invalid JSON: {exc.msg}")
            continue
        if not isinstance(record, dict):
            line_error(line_number, "record", "invalid_record", "each JSONL line must be an object")
            continue

        record = dict(record)
        explicit_kind = "kind" in record
        requested_kind = record.pop("kind", None)
        if explicit_kind:
            if not isinstance(requested_kind, str) or requested_kind.casefold() not in {"node", "edge"}:
                line_error(line_number, "record", "invalid_kind", "kind must be 'node' or 'edge'")
                continue
            record_kind = requested_kind.casefold()
        else:
            record_kind = "edge" if "source" in record or "target" in record else "node"

        metadata_supplied = "metadata" in record
        if record_kind == "node":
            record["type"] = canonical_type(record.get("type"), graph.entities)
            record.setdefault("metadata", {})
            try:
                node = Node.from_dict(record)
            except (TypeError, ValueError) as exc:
                line_error(line_number, "node", "invalid_record", str(exc))
                continue
            parsed_nodes.append((node, line_number, metadata_supplied))
        else:
            record["type"] = canonical_type(record.get("type"), graph.edge_types)
            record.setdefault("id", str(uuid.uuid4()))
            record.setdefault("metadata", {})
            try:
                edge = Edge.from_dict(record)
            except (TypeError, ValueError) as exc:
                line_error(line_number, "edge", "invalid_record", str(exc))
                continue
            parsed_edges.append((edge, line_number, metadata_supplied))

    counts = {"created": 0, "updated": 0, "unchanged": 0}
    nodes_by_id = {node.id: node for node in existing["nodes"]}
    edges_by_id = {edge.id: edge for edge in existing["edges"]}

    def node_conflict(incoming: Node) -> Node | None:
        return nodes_by_id.get(incoming.id)

    def edge_conflict(incoming: Edge) -> Edge | None:
        by_id = edges_by_id.get(incoming.id)
        if by_id is not None:
            return by_id
        return next((edge for edge in edges_by_id.values()
                     if edge.type.casefold() == incoming.type.casefold()
                     and edge.source == incoming.source
                     and edge.target == incoming.target
                     and edge.properties == incoming.properties), None)

    for node, line_number, metadata_supplied in parsed_nodes:
        current = node_conflict(node)
        if current is None:
            if not metadata_supplied:
                node.metadata = {"created_at": now, "updated_at": now}
            nodes_by_id[node.id] = node
            counts["created"] += 1
            line_by_record[("node", node.id)] = line_number
            continue
        if on_conflict == "error":
            line_error(line_number, "node", "conflict", f"node ID already exists: {node.id}")
        elif on_conflict == "skip":
            counts["unchanged"] += 1
        else:
            if not metadata_supplied:
                node.metadata = current.metadata
            if node.to_dict() == current.to_dict():
                counts["unchanged"] += 1
            else:
                node.metadata["updated_at"] = now
                nodes_by_id[node.id] = node
                counts["updated"] += 1
            line_by_record[("node", node.id)] = line_number

    for edge, line_number, metadata_supplied in parsed_edges:
        current = edge_conflict(edge)
        if current is None:
            if not metadata_supplied:
                edge.metadata = {"created_at": now, "updated_at": now}
            edges_by_id[edge.id] = edge
            counts["created"] += 1
            line_by_record[("edge", edge.id)] = line_number
            continue
        if on_conflict == "error":
            line_error(line_number, "edge", "conflict", f"edge already exists: {edge.id}")
        elif on_conflict == "skip":
            counts["unchanged"] += 1
        else:
            edge.id = current.id
            if not metadata_supplied:
                edge.metadata = current.metadata
            if edge.to_dict() == current.to_dict():
                counts["unchanged"] += 1
            else:
                edge.metadata["updated_at"] = now
                edges_by_id[edge.id] = edge
                counts["updated"] += 1
            line_by_record[("edge", edge.id)] = line_number

    candidate = {"nodes": list(nodes_by_id.values()), "edges": list(edges_by_id.values())}
    validation = graph.validate({
        "nodes": [node.to_dict() for node in candidate["nodes"]],
        "edges": [edge.to_dict() for edge in candidate["edges"]],
    })
    for issue in validation["errors"]:
        line_number = None
        kind = issue.get("kind", "record")
        record_id = issue.get("id")
        if kind in {"node", "edge"} and record_id is not None:
            line_number = line_by_record.get((kind, record_id))
        item = dict(issue)
        if line_number is not None:
            item["line"] = line_number
        errors.append(item)

    errors.sort(key=lambda item: (item.get("line", float("inf")), item.get("kind", ""), item["code"]))
    result = {
        "valid": not errors,
        "dry_run": dry_run is True,
        "summary": {**counts, "errors": len(errors)},
        "errors": errors,
    }
    if not errors and dry_run is not True and (counts["created"] or counts["updated"]):
        graph.save(candidate)
    emit(result)
    return 0 if not errors else 3
