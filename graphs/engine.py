"""JSON backed graph operations."""
from __future__ import annotations

import heapq
import json
import os
import re
import tempfile
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

from graphs.types import Edge, Node

NODE_ID_PATTERN = r"[a-z0-9][a-z0-9._-]*"


class GraphError(ValueError):
    exit_code = 2


class GraphNotFoundError(GraphError):
    exit_code = 3


class GraphNotInitializedError(GraphError):
    pass


class InvalidContractError(GraphError):
    pass


class GraphData(TypedDict):
    nodes: list[Node]
    edges: list[Edge]


class Graph:
    def __init__(
        self, directory: str | Path = ".graph", *, allow_invalid_contracts: bool = False,
    ) -> None:
        self.directory = Path(directory)
        contract_paths = (self.directory / "entities.json", self.directory / "edges.json")
        if not self.directory.is_dir() or any(not path.is_file() for path in contract_paths):
            raise GraphNotInitializedError(
                "Graph workspace not initialized.\n"
                "Run 'graph init' to initialize this project."
            )
        self.entities = self._load_types("entities.json")
        self.edge_types = self._load_types("edges.json")
        self.contract_errors = self._contract_errors()
        if self.contract_errors and not allow_invalid_contracts:
            raise InvalidContractError(self.contract_errors[0]["message"])
        self.path = self.directory / "graph.json"

    def _contract_errors(self) -> list[dict[str, str]]:
        """Return contract shape and reference errors before graph operations use them."""
        errors: list[dict[str, str]] = []
        for contracts in (self.entities, self.edge_types):
            by_folded: dict[str, list[str]] = {}
            for name in contracts:
                by_folded.setdefault(name.casefold(), []).append(name)
            for names in by_folded.values():
                if len(names) > 1:
                    errors.append({
                        "code": "invalid_contract",
                        "message": f"type names must be unique ignoring case: {', '.join(sorted(names))}",
                    })
        entity_types = {name.casefold() for name in self.entities}
        for name, contract in self.entities.items():
            if not isinstance(contract, dict) or not isinstance(contract.get("properties"), dict):
                errors.append({"code": "invalid_contract", "message": f"entity {name} must define a properties object"})
                continue
            errors.extend(issue for issue in self._validate_properties(name, {}, self.entities)
                          if issue["code"] == "invalid_contract")
        for name, contract in self.edge_types.items():
            if not isinstance(contract, dict):
                errors.append({"code": "invalid_contract", "message": f"edge {name} must be an object"})
                continue
            for endpoint in ("source", "target"):
                values = contract.get(endpoint)
                if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
                    errors.append({"code": "invalid_contract", "message": f"edge {name} {endpoint} must be a list of entity types"})
                else:
                    for value in values:
                        if value.casefold() not in entity_types:
                            errors.append({"code": "invalid_contract", "message": f"edge {name} references unknown entity type: {value}"})
            if not isinstance(contract.get("properties"), dict):
                errors.append({"code": "invalid_contract", "message": f"edge {name} must define a properties object"})
                continue
            errors.extend(issue for issue in self._validate_properties(name, {}, self.edge_types)
                          if issue["code"] == "invalid_contract")
        return errors

    def __now_datetime(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _allowed(values: Any) -> str:
        return ", ".join(sorted(values)) or "(none)"

    @staticmethod
    def _canonical_type(value: str, contracts: dict[str, Any]) -> str | None:
        return next((name for name in contracts if name.casefold() == value.casefold()), None)

    def _canonical_edge_filters(self, edge_types: set[str] | None) -> set[str] | None:
        if edge_types is None:
            return None
        canonical = {name.casefold(): name for name in self.edge_types}
        unknown = {value for value in edge_types if value.casefold() not in canonical}
        if unknown:
            raise GraphError(
                f"unknown edge type: {', '.join(sorted(unknown))}; "
                f"valid types: {self._allowed(self.edge_types)}"
            )
        return {canonical[value.casefold()].casefold() for value in edge_types}

    def _load_types(self, filename: str) -> dict[str, Any]:
        path = self.directory / filename
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise GraphError(f"cannot load type contract {filename}: {exc}") from exc
        if not isinstance(data, dict):
            raise GraphError(f"invalid type contract {filename}")
        if "$schema" in data and not isinstance(data["$schema"], str):
            raise GraphError(f"invalid type contract {filename}: $schema must be a string")
        return {name: contract for name, contract in data.items() if name != "$schema"}

    def load(self) -> GraphData:
        if not self.path.exists():
            return {"nodes": [], "edges": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise GraphError(f"cannot read graph store: {exc}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("nodes"), list) or not isinstance(data.get("edges"), list):
            raise GraphError("graph store must contain nodes and edges arrays")
        try:
            nodes = [Node.from_dict(item) for item in data["nodes"]]
            edges = [Edge.from_dict(item) for item in data["edges"]]
            return {"nodes": nodes, "edges": edges}
        except (TypeError, ValueError) as exc:
            raise GraphError(f"invalid graph record: {exc}") from exc

    def save(self, data: GraphData) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.directory, delete=False) as file:
                temp_name = file.name
                json.dump(data, file, default=lambda item: item.to_dict())
                file.write("\n")
            os.replace(temp_name, self.path)
        finally:
            if temp_name and os.path.exists(temp_name):
                os.unlink(temp_name)

    def add_node(
        self, node_id: str, name: str, kind: str, properties: dict[str, Any],
        evidences: list[dict[str, Any]] | None = None,
        description: str = "",
    ) -> Node:
        requested_kind = kind
        kind = self._canonical_type(kind, self.entities)
        if kind is None:
            raise GraphError(f"unknown entity type: {requested_kind}; valid types: {self._allowed(self.entities)}")
        if not isinstance(node_id, str) or re.fullmatch(NODE_ID_PATTERN, node_id) is None:
            raise GraphError(f"node id must match ^{NODE_ID_PATTERN}$")
        self._require_valid_properties(kind, properties, self.entities)
        if evidences is None:
            evidences = []
        if not isinstance(evidences, list) or any(not isinstance(item, dict) for item in evidences):
            raise GraphError("evidences must be a list of objects")
        if not isinstance(description, str):
            raise GraphError("description must be a string")
        data = self.load()
        if any(node.id == node_id for node in data["nodes"]):
            raise GraphError(f"node id already exists: {node_id}")
        now = self.__now_datetime()
        node = Node(
            id=node_id, type=kind, name=name, description=description, properties=properties,
            metadata={"created_at": now, "updated_at": now}, evidences=evidences,
        )
        data["nodes"].append(node)
        self.save(data)
        return node

    def add_edge(
        self, source_id: str, kind: str, target_id: str, properties: dict[str, Any],
        evidences: list[dict[str, Any]] | None = None, description: str = "",
    ) -> Edge:
        requested_kind = kind
        kind = self._canonical_type(kind, self.edge_types)
        if kind is None:
            raise GraphError(f"unknown edge type: {requested_kind}; valid types: {self._allowed(self.edge_types)}")
        self._require_valid_properties(kind, properties, self.edge_types)
        if evidences is None:
            evidences = []
        if not isinstance(evidences, list) or any(not isinstance(item, dict) for item in evidences):
            raise GraphError("evidences must be a list of objects")
        if not isinstance(description, str):
            raise GraphError("description must be a string")
        data = self.load()
        nodes = {node.id: node for node in data["nodes"]}
        source, target = nodes.get(source_id), nodes.get(target_id)
        if source is None or target is None:
            raise GraphError("source and target must reference existing node IDs")
        contract = self.edge_types[kind]
        allowed_sources = {value.casefold() for value in contract["source"]}
        allowed_targets = {value.casefold() for value in contract["target"]}
        if source.type.casefold() not in allowed_sources or target.type.casefold() not in allowed_targets:
            raise GraphError(
                f"edge {kind} does not allow {source.type} -> {target.type}; "
                f"valid source types: {self._allowed(contract['source'])}; "
                f"valid target types: {self._allowed(contract['target'])}"
            )
        matching = [edge for edge in data["edges"]
                    if edge.source == source.id and edge.target == target.id]
        if any(edge.type.casefold() == kind.casefold() and edge.properties == properties
               for edge in matching):
            raise GraphError(f"duplicate edge: {kind} {source.id} -> {target.id}")
        if matching and not description.strip():
            raise GraphError("parallel edges require a description")
        now = self.__now_datetime()
        edge = Edge(
            id=str(uuid.uuid4()), type=kind, source=source.id, target=target.id,
            description=description,
            properties=properties, metadata={"created_at": now, "updated_at": now},
            evidences=evidences,
        )
        data["edges"].append(edge)
        self.save(data)
        return edge

    def edit_node(self, reference: str, *, name: str | None = None,
                  description: str | None = None,
                  properties: dict[str, Any] | None = None,
                  evidences: list[dict[str, Any]] | None = None) -> Node:
        data = self.load()
        node = self.resolve_node(data, reference)
        if node is None:
            raise GraphNotFoundError(f"unknown node id: {reference}")
        node_type = node.type
        canonical_node_type = self._canonical_type(node_type, self.entities)
        if canonical_node_type is None:
            raise GraphError(f"unknown entity type: {node_type}; valid types: {self._allowed(self.entities)}")
        self._require_valid_properties(
            canonical_node_type,
            properties if properties is not None else node.properties,
            self.entities,
        )
        if name is not None:
            node.name = name
        if description is not None:
            if not isinstance(description, str):
                raise GraphError("description must be a string")
            node.description = description
        if properties is not None:
            node.properties = properties
        if evidences is not None:
            if not isinstance(evidences, list) or any(not isinstance(item, dict) for item in evidences):
                raise GraphError("evidences must be a list of objects")
            node.evidences = evidences
        node.metadata["updated_at"] = self.__now_datetime()
        self.save(data)
        return node

    def edit_edge(self, edge_id: str, *, description: str | None = None,
                  properties: dict[str, Any] | None = None,
                  evidences: list[dict[str, Any]] | None = None) -> Edge:
        data = self.load()
        edge = next((item for item in data["edges"] if item.id == edge_id), None)
        if edge is None:
            raise GraphNotFoundError(f"unknown edge id: {edge_id}")
        edge_type = edge.type
        canonical_edge_type = self._canonical_type(edge_type, self.edge_types)
        if canonical_edge_type is None:
            raise GraphError(f"unknown edge type: {edge_type}; valid types: {self._allowed(self.edge_types)}")
        if description is not None and not isinstance(description, str):
            raise GraphError("description must be a string")
        self._require_valid_properties(
            canonical_edge_type,
            properties if properties is not None else edge.properties,
            self.edge_types,
        )
        edge_properties = properties if properties is not None else edge.properties
        edge_description = description if description is not None else edge.description
        parallel = [other for other in data["edges"] if other.id != edge_id
                    and other.source == edge.source
                    and other.target == edge.target]
        if any(other.type.casefold() == edge_type.casefold() and other.properties == edge_properties
               for other in parallel):
            raise GraphError(f"duplicate edge: {edge_type} {edge.source} -> {edge.target}")
        if parallel and not edge_description.strip():
            raise GraphError("parallel edges require a description")
        if properties is not None:
            edge.properties = properties
        if description is not None:
            edge.description = description
        if evidences is not None:
            if not isinstance(evidences, list) or any(not isinstance(item, dict) for item in evidences):
                raise GraphError("evidences must be a list of objects")
            edge.evidences = evidences
        edge.metadata["updated_at"] = self.__now_datetime()
        self.save(data)
        return edge

    def delete_node(self, *, node_id: str) -> tuple[Node, int]:
        data = self.load()
        matches = [node for node in data["nodes"] if node.id == node_id]
        if len(matches) != 1:
            raise GraphNotFoundError(f"unknown node id: {node_id}")
        node = matches[0]
        node_ref = node.id
        before = len(data["edges"])
        data["edges"] = [edge for edge in data["edges"]
                         if edge.source != node_ref and edge.target != node_ref]
        deleted_edges = before - len(data["edges"])
        data["nodes"].remove(node)
        self.save(data)
        return node, deleted_edges

    def delete_edge(self, *, edge_id: str | None = None, kind: str | None = None,
                    source: str | None = None, target: str | None = None) -> list[Edge]:
        data = self.load()
        if edge_id is not None:
            matches = [edge for edge in data["edges"] if edge.id == edge_id]
            if not matches:
                raise GraphNotFoundError(f"unknown edge id: {edge_id}")
        else:
            if not kind or not source or not target:
                raise GraphError("provide --id or SOURCE_NODE_ID EDGE_TYPE TARGET_NODE_ID")
            nodes = {node.id: node for node in data["nodes"]}
            source_node, target_node = nodes.get(source), nodes.get(target)
            if source_node is None or target_node is None:
                raise GraphError("source and target must reference existing node IDs")
            matches = [edge for edge in data["edges"] if edge.type.casefold() == kind.casefold()
                       and edge.source == source_node.id
                       and edge.target == target_node.id]
            if not matches:
                raise GraphError("no matching edge found")
            if len(matches) > 1:
                return matches
        to_delete = {edge.id for edge in matches}
        data["edges"] = [edge for edge in data["edges"] if edge.id not in to_delete]
        self.save(data)
        return matches

    @staticmethod
    def resolve_node(data: GraphData, reference: str) -> Node | None:
        return next((node for node in data["nodes"] if node.id == reference), None)

    def traverse(
        self, anchor_id: str, *, depth: int = 1,
        direction: str = "both", edge_types: set[str] | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Traverse the graph and return deterministic compact records."""
        if depth < 1:
            raise GraphError("depth must be a positive integer")
        if direction not in {"in", "out", "both"}:
            raise GraphError("direction must be in, out, or both")
        if limit is not None and limit < 1:
            raise GraphError("limit must be positive")

        selected_edge_types = self._canonical_edge_filters(edge_types)
        data = self.load()
        node_by_id = {node.id: node for node in data["nodes"]}
        anchor_node = self.resolve_node(data, anchor_id)
        if anchor_node is None:
            raise GraphNotFoundError(f"unknown node id: {anchor_id}")
        anchor_id = anchor_node.id
        allowed_directions = {"out", "in"} if direction == "both" else {direction}
        frontier = {anchor_id}
        visited = {anchor_id}
        selected_edges: dict[str, Edge] = {}
        truncated = False
        for _ in range(depth):
            next_frontier: set[str] = set()
            candidates: list[tuple[Edge, str]] = []
            for edge in data["edges"]:
                if selected_edge_types is not None and edge.type.casefold() not in selected_edge_types:
                    continue
                if "out" in allowed_directions and edge.source in frontier:
                    candidates.append((edge, edge.target))
                if "in" in allowed_directions and edge.target in frontier:
                    candidates.append((edge, edge.source))
            candidates.sort(key=lambda item: (item[0].id, item[1] or ""))
            for edge, neighbor in candidates:
                if not neighbor or neighbor not in node_by_id:
                    continue
                if neighbor not in visited:
                    next_frontier.add(neighbor)
            newly_reached = sorted(next_frontier)
            if limit is not None:
                remaining = max(0, limit - (len(visited) - 1))
                if len(newly_reached) > remaining:
                    truncated = True
                    newly_reached = newly_reached[:remaining]
            accepted = set(newly_reached)
            for edge, neighbor in candidates:
                if not neighbor or neighbor not in node_by_id:
                    continue
                if neighbor in visited or neighbor in accepted:
                    selected_edges[edge.id] = edge
            visited.update(newly_reached)
            frontier = set(newly_reached)
            if not frontier or truncated:
                break
        reached = sorted(visited - {anchor_id})
        ordered_nodes = [anchor_id, *reached]
        compact_nodes = [[node_id, node_by_id[node_id].type, node_by_id[node_id].name] for node_id in ordered_nodes]
        compact_edges = [[edge.source, edge.type, edge.target, node_by_id[edge.target].type]
                         for edge in sorted(selected_edges.values(), key=lambda item: (item.source, item.type, item.target, item.id))]
        return {"nodes": compact_nodes, "edges": compact_edges, "truncated": truncated}

    def list_edges(
        self, *, kind: str | None = None, properties: dict[str, Any] | None = None,
        kinds: list[str] | None = None,
        source: str | None = None, target: str | None = None,
        limit: int | None = None,
    ) -> list[Edge]:
        """List edges matching type, property, and endpoint filters."""
        if limit is not None and limit < 1:
            raise GraphError("limit must be positive")
        if properties is not None and not isinstance(properties, dict):
            raise GraphError("properties must be an object")
        if kind is not None and kinds is not None:
            raise GraphError("kind and kinds cannot both be provided")
        data = self.load()
        canonical_kinds = None
        if kind is not None:
            canonical_kind = self._canonical_type(kind, self.edge_types)
            if canonical_kind is None:
                raise GraphError(f"unknown edge type: {kind}; valid types: {self._allowed(self.edge_types)}")
            kind = canonical_kind
        if kinds is not None:
            canonical_kinds = set()
            for requested_kind in kinds:
                canonical_kind = self._canonical_type(requested_kind, self.edge_types)
                if canonical_kind is None:
                    raise GraphError(
                        f"unknown edge type: {requested_kind}; valid types: {self._allowed(self.edge_types)}"
                    )
                canonical_kinds.add(canonical_kind.casefold())
        source_node = self.resolve_node(data, source) if source is not None else None
        target_node = self.resolve_node(data, target) if target is not None else None
        if source is not None and source_node is None:
            raise GraphNotFoundError(f"unknown source node id: {source}")
        if target is not None and target_node is None:
            raise GraphNotFoundError(f"unknown target node id: {target}")
        source_id = source_node.id if source_node else None
        target_id = target_node.id if target_node else None
        records = [edge for edge in data["edges"]
                   if (kind is None or edge.type.casefold() == kind.casefold())
                   and (canonical_kinds is None or edge.type.casefold() in canonical_kinds)
                   and (source_id is None or edge.source == source_id)
                   and (target_id is None or edge.target == target_id)
                   and all(edge.properties.get(k) == v for k, v in (properties or {}).items())]
        records.sort(key=lambda edge: (edge.source, edge.type, edge.target, edge.id))
        return records if limit is None else records[:limit]

    def find_paths(
        self, source: str, target: str, *, direction: str = "out",
        edge_types: set[str] | None = None, max_depth: int | None = None,
        limit: int = 1,
    ) -> dict[str, Any]:
        """Return up to limit simple paths in shortest-first deterministic order."""
        if direction not in {"out", "in", "both"}:
            raise GraphError("direction must be out, in, or both")
        if limit < 1:
            raise GraphError("limit must be positive")
        selected_edge_types = self._canonical_edge_filters(edge_types)
        data = self.load()
        start = self.resolve_node(data, source)
        finish = self.resolve_node(data, target)
        if start is None:
            raise GraphNotFoundError(f"unknown source node id: {source}")
        if finish is None:
            raise GraphNotFoundError(f"unknown target node id: {target}")
        nodes = {node.id: node for node in data["nodes"]}
        start_id, target_id = start.id, finish.id
        if max_depth is None:
            max_depth = max(0, len(nodes) - 1)
        if max_depth < 0:
            raise GraphError("max depth must not be negative")
        adjacency: dict[str, list[tuple[str, Edge, int, tuple[str, str, str, int]]]] = {
            node_id: [] for node_id in nodes
        }
        for edge_index, edge in enumerate(data["edges"]):
            if selected_edge_types is not None and edge.type.casefold() not in selected_edge_types:
                continue
            if direction in {"out", "both"} and edge.source in nodes and edge.target in nodes:
                neighbor = edge.target
                arc_key = (neighbor, edge.type, edge.id, edge_index)
                adjacency[edge.source].append((neighbor, edge, edge_index, arc_key))
            if direction in {"in", "both"} and edge.source in nodes and edge.target in nodes:
                neighbor = edge.source
                arc_key = (neighbor, edge.type, edge.id, edge_index)
                adjacency[edge.target].append((neighbor, edge, edge_index, arc_key))
        for neighbors in adjacency.values():
            neighbors.sort(key=lambda item: item[3])

        def shortest_path(
            spur_node: str, depth_limit: int, blocked_nodes: set[str], blocked_edges: set[int],
        ) -> tuple[list[str], list[int], tuple[tuple[str, str, str, int], ...]] | None:
            if spur_node == target_id:
                return [spur_node], [], ()
            queue = deque([spur_node])
            depths = {spur_node: 0}
            parents: dict[str, tuple[str, int, tuple[str, str, str, int]]] = {}
            while queue:
                current = queue.popleft()
                if depths[current] >= depth_limit:
                    continue
                for neighbor, _, edge_index, arc_key in adjacency[current]:
                    if edge_index in blocked_edges or neighbor in blocked_nodes or neighbor in depths:
                        continue
                    parents[neighbor] = (current, edge_index, arc_key)
                    depths[neighbor] = depths[current] + 1
                    if neighbor == target_id:
                        path_nodes = [target_id]
                        path_edges = []
                        path_keys = []
                        while path_nodes[-1] != spur_node:
                            parent, parent_edge, parent_key = parents[path_nodes[-1]]
                            path_nodes.append(parent)
                            path_edges.append(parent_edge)
                            path_keys.append(parent_key)
                        return path_nodes[::-1], path_edges[::-1], tuple(path_keys[::-1])
                    queue.append(neighbor)
            return None

        first_path = shortest_path(start_id, max_depth, set(), set())
        if first_path is None:
            return {"paths": [], "truncated": False}

        accepted = [first_path]
        accepted_signatures = {tuple(first_path[1])}
        candidates: list[
            tuple[int, tuple[tuple[str, str, str, int], ...], tuple[int, ...], list[str], list[int]]
        ] = []
        candidate_signatures: set[tuple[int, ...]] = set()

        while len(accepted) <= limit:
            previous_nodes, previous_edges, previous_keys = accepted[-1]
            for spur_index in range(len(previous_edges)):
                root_nodes = previous_nodes[:spur_index + 1]
                root_edges = previous_edges[:spur_index]
                root_keys = previous_keys[:spur_index]
                root_signature = tuple(root_edges)
                blocked_edges = {
                    path_edges[spur_index]
                    for _, path_edges, _ in accepted
                    if len(path_edges) > spur_index and tuple(path_edges[:spur_index]) == root_signature
                }
                spur = shortest_path(
                    root_nodes[-1], max_depth - spur_index, set(root_nodes[:-1]), blocked_edges
                )
                if spur is None:
                    continue
                spur_nodes, spur_edges, spur_keys = spur
                path_nodes = root_nodes[:-1] + spur_nodes
                path_edges = root_edges + spur_edges
                signature = tuple(path_edges)
                if signature in accepted_signatures or signature in candidate_signatures:
                    continue
                candidate_signatures.add(signature)
                path_keys = root_keys + spur_keys
                heapq.heappush(
                    candidates,
                    (len(path_edges), path_keys, signature, path_nodes, path_edges),
                )
            if not candidates:
                break
            _, path_keys, _, path_nodes, path_edges = heapq.heappop(candidates)
            accepted.append((path_nodes, path_edges, path_keys))
            accepted_signatures.add(tuple(path_edges))

        paths = [
            (path_nodes, [data["edges"][edge_index] for edge_index in edge_indices])
            for path_nodes, edge_indices, _ in accepted
        ]
        truncated = len(paths) > limit
        paths = paths[:limit]
        rendered = [{
            "nodes": [[node_id, nodes[node_id].type, nodes[node_id].name] for node_id in node_ids],
            "edges": [[edge.id, edge.source, edge.type, edge.target, nodes[edge.target].type] for edge in edges],
            "hops": len(edges),
        } for node_ids, edges in paths]
        return {"paths": rendered, "truncated": truncated}

    def _require_valid_properties(self, kind: str, properties: dict[str, Any], contracts: dict[str, Any]) -> None:
        violations = self._validate_properties(kind, properties, contracts)
        if violations:
            raise GraphError(violations[0]["message"])

    @staticmethod
    def _validate_properties(
        kind: str, properties: Any, contracts: dict[str, Any],
    ) -> list[dict[str, str]]:
        violations: list[dict[str, str]] = []
        if not isinstance(properties, dict):
            return [{"code": "invalid_property_type", "message": "properties must be a JSON object"}]
        allowed = contracts[kind].get("properties")
        if not isinstance(allowed, dict):
            return [{"code": "invalid_contract", "message": f"invalid properties contract for {kind}"}]
        valid = {
            "string": lambda value: isinstance(value, str),
            "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
            "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
            "boolean": lambda value: isinstance(value, bool),
        }
        definitions: dict[str, tuple[str, bool]] = {}
        for property_name, definition in allowed.items():
            if isinstance(definition, str):
                expected, is_required = definition, False
            elif isinstance(definition, dict):
                expected = definition.get("type")
                is_required = definition.get("required", False)
            else:
                violations.append({"code": "invalid_contract", "message": f"invalid contract for property {property_name} on {kind}"})
                continue
            if expected not in valid or not isinstance(is_required, bool):
                violations.append({"code": "invalid_contract", "message": f"invalid contract for property {property_name} on {kind}"})
                continue
            definitions[property_name] = (expected, is_required)
        required = [name for name, (_, is_required) in definitions.items() if is_required]
        for name in sorted(set(required) - properties.keys()):
            violations.append({"code": "missing_required_property", "message": f"missing required property: {name}"})
        for key, value in properties.items():
            definition = definitions.get(key)
            if definition is None:
                violations.append({"code": "unknown_property", "message": f"unknown property: {key}; valid properties: {Graph._allowed(definitions)}"})
                continue
            expected = definition[0]
            if not valid[expected](value):
                violations.append({"code": "invalid_property_type", "message": f"property {key} must be {expected}"})
        return violations

    def validate(self) -> dict[str, Any]:
        """Report contract and graph-store violations without changing files."""
        errors: list[dict[str, Any]] = []

        def report(kind: str, code: str, message: str, record_id: str | None = None,
                   **details: Any) -> None:
            item: dict[str, Any] = {"kind": kind}
            if record_id is not None:
                item["id"] = record_id
            item.update({"code": code, "message": message})
            item.update(details)
            errors.append(item)

        for issue in self.contract_errors:
            report("contract", issue["code"], issue["message"])

        # Graph.__init__ loads both contract files before this method is called.
        entity_types = {name.casefold(): name for name in self.entities}
        edge_types = {name.casefold(): name for name in self.edge_types}
        try:
            raw_text = self.path.read_text(encoding="utf-8") if self.path.exists() else '{"nodes": [], "edges": []}'
            store = json.loads(raw_text)
        except (OSError, json.JSONDecodeError) as exc:
            return {"valid": False, "errors": [{"kind": "store", "code": "invalid_record", "message": f"cannot read graph store: {exc}"}],
            "summary": {"nodes": 0, "edges": 0, "errors": 1}, "unavailable": True}
        if not isinstance(store, dict):
            store = {}
            report("store", "invalid_record", "graph store must be a JSON object")
        raw_nodes, raw_edges = store.get("nodes"), store.get("edges")
        if not isinstance(raw_nodes, list):
            report("store", "invalid_record", "graph store nodes must be an array")
            raw_nodes = []
        if not isinstance(raw_edges, list):
            report("store", "invalid_record", "graph store edges must be an array")
            raw_edges = []

        nodes: list[Node] = []
        node_ids: set[str] = set()
        for record in raw_nodes:
            try:
                node = Node.from_dict(record)
            except (TypeError, ValueError) as exc:
                record_id = record.get("id") if isinstance(record, dict) and isinstance(record.get("id"), str) else None
                report("store", "invalid_record", str(exc), record_id)
                continue
            if node.id in node_ids:
                report("node", "duplicate_id", f"duplicate node ID: {node.id}", node.id)
            node_ids.add(node.id)
            nodes.append(node)
            if not re.fullmatch(NODE_ID_PATTERN, node.id):
                report("node", "invalid_id", f"ID must match ^{NODE_ID_PATTERN}$", node.id)
            canonical = entity_types.get(node.type.casefold())
            if canonical is None:
                report("node", "unknown_type", f"unknown entity type: {node.type}; valid types: {self._allowed(self.entities)}", node.id,
                       valid_types=sorted(self.entities))
            else:
                for issue in self._validate_properties(canonical, node.properties, self.entities):
                    report("node", issue["code"], issue["message"], node.id,
                           **({"valid_properties": sorted(self.entities[canonical].get("properties", {}))}
                              if issue["code"] == "unknown_property" else {}))

        node_by_id = {node.id: node for node in nodes}
        edge_ids: set[str] = set()
        seen_exact: set[str] = set()
        parallel_groups: dict[tuple[str, str, str], list[Edge]] = {}
        for record in raw_edges:
            try:
                edge = Edge.from_dict(record)
            except (TypeError, ValueError) as exc:
                record_id = record.get("id") if isinstance(record, dict) and isinstance(record.get("id"), str) else None
                report("store", "invalid_record", str(exc), record_id)
                continue
            if edge.id in edge_ids:
                report("edge", "duplicate_id", f"duplicate edge ID: {edge.id}", edge.id)
            edge_ids.add(edge.id)
            canonical = edge_types.get(edge.type.casefold())
            if canonical is None:
                report("edge", "unknown_type", f"unknown edge type: {edge.type}; valid types: {self._allowed(self.edge_types)}", edge.id,
                       valid_types=sorted(self.edge_types))
            contract = self.edge_types.get(canonical, {}) if canonical is not None else {}
            source, target = node_by_id.get(edge.source), node_by_id.get(edge.target)
            for endpoint_name, node in (("source", source), ("target", target)):
                if node is None:
                    report("edge", "dangling_endpoint", f"{endpoint_name} node does not exist: {edge.source if endpoint_name == 'source' else edge.target}", edge.id)
            if (canonical is not None and source is not None and target is not None
                    and isinstance(contract.get("source"), list)
                    and isinstance(contract.get("target"), list)
                    and all(isinstance(value, str) for value in contract["source"])
                    and all(isinstance(value, str) for value in contract["target"])):
                allowed_source = contract.get("source", [])
                allowed_target = contract.get("target", [])
                if (source.type.casefold() not in {value.casefold() for value in allowed_source}
                        or target.type.casefold() not in {value.casefold() for value in allowed_target}):
                    report("edge", "endpoint_not_allowed", f"{canonical} does not allow {source.type} -> {target.type}", edge.id,
                           allowed_source=allowed_source, allowed_target=allowed_target)
            if canonical is not None:
                for issue in self._validate_properties(canonical, edge.properties, self.edge_types):
                    report("edge", issue["code"], issue["message"], edge.id,
                           **({"valid_properties": sorted(contract.get("properties", {}))}
                              if issue["code"] == "unknown_property" else {}))
            group = ((canonical or edge.type).casefold(), edge.source, edge.target)
            parallel_groups.setdefault(group, []).append(edge)
            exact_key = json.dumps([(canonical or edge.type).casefold(), edge.source, edge.target, edge.description, edge.properties],
                                   sort_keys=True, separators=(",", ":"))
            if exact_key in seen_exact:
                report("edge", "duplicate_edge", "exact duplicate edge", edge.id)
            seen_exact.add(exact_key)

        for group in parallel_groups.values():
            if len(group) > 1:
                for edge in group:
                    if not edge.description.strip():
                        report("edge", "parallel_edge_needs_description", "parallel edges require a non-empty description", edge.id)

        order = {name: index for index, name in enumerate(("contract", "store", "node", "edge"))}
        errors.sort(key=lambda item: (order.get(item["kind"], 99), item.get("id", ""), item["code"]))
        return {"valid": not errors, "errors": errors,
                "summary": {"nodes": len(raw_nodes), "edges": len(raw_edges), "errors": len(errors)}}
