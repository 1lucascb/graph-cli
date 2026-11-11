"""Typed graph records used by the engine and CLI."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def compact_edge_tuple(edge: Edge, nodes: dict[str, Node]) -> list[str]:
    """Return the CLI's compact edge tuple, deriving target type when present."""
    target = nodes.get(edge.target)
    return [edge.source, edge.type, edge.target, target.type if target is not None else ""]


@dataclass(slots=True)
class Node:
    id: str
    type: str
    name: str
    properties: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)
    evidences: list[dict[str, Any]] = field(default_factory=list)
    description: str = ""

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Node:
        if not isinstance(value, dict):
            raise ValueError("node record must be an object")
        for key in ("id", "type", "name"):
            if not isinstance(value.get(key), str):
                raise ValueError(f"node {key} must be a string")
        if not isinstance(value.get("description", ""), str):
            raise ValueError("node description must be a string")
        if not isinstance(value.get("properties", {}), dict):
            raise ValueError("node properties must be an object")
        if not isinstance(value.get("metadata", {}), dict):
            raise ValueError("node metadata must be an object")
        if not isinstance(value.get("evidences", []), list) or any(
            not isinstance(item, dict) for item in value.get("evidences", [])
        ):
            raise ValueError("node evidences must be a list of objects")
        return cls(
            id=value["id"], type=value["type"], name=value["name"],
            description=value.get("description", ""),
            properties=value.get("properties", {}), metadata=value.get("metadata", {}),
            evidences=value.get("evidences", []),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Edge:
    id: str
    type: str
    source: str
    target: str
    description: str = ""
    properties: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)
    evidences: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Edge:
        if not isinstance(value, dict):
            raise ValueError("edge record must be an object")
        for key in ("id", "type", "source", "target"):
            if not isinstance(value.get(key), str):
                raise ValueError(f"edge {key} must be a string")
        if not isinstance(value.get("description", ""), str):
            raise ValueError("edge description must be a string")
        if not isinstance(value.get("properties", {}), dict):
            raise ValueError("edge properties must be an object")
        if not isinstance(value.get("metadata", {}), dict):
            raise ValueError("edge metadata must be an object")
        if not isinstance(value.get("evidences", []), list) or any(
            not isinstance(item, dict) for item in value.get("evidences", [])
        ):
            raise ValueError("edge evidences must be a list of objects")
        return cls(
            id=value["id"], type=value["type"], source=value["source"], target=value["target"],
            description=value.get("description", ""),
            properties=value.get("properties", {}), metadata=value.get("metadata", {}),
            evidences=value.get("evidences", []),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EdgeResponse:
    """Edge output DTO with target type derived from its target node."""

    id: str
    type: str
    source: str
    target: str
    target_type: str
    description: str
    properties: dict[str, Any]
    metadata: dict[str, str]
    evidences: list[dict[str, Any]]

    @classmethod
    def from_edge(cls, edge: Edge, target_type: str) -> EdgeResponse:
        return cls(
            id=edge.id, type=edge.type, source=edge.source, target=edge.target,
            target_type=target_type, description=edge.description,
            properties=edge.properties, metadata=edge.metadata, evidences=edge.evidences,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
