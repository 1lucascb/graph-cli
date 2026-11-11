"""Pure graph status calculations."""

from collections import Counter
from collections.abc import Iterable

from graph_lcb.graphs.types import Edge, Node, compact_edge_tuple

CHECKS = ("orphans", "no-evidence", "no-description", "components")


def _samples(items: list, limit: int) -> dict:
    return {"count": len(items), "ids": items[:limit], "truncated": len(items) > limit}


def _by_type(records: Iterable[Node | Edge]) -> dict[str, int]:
    counts = Counter(record.type for record in records)
    return {kind: counts[kind] for kind in sorted(counts)}


def compute_status(entities, edges_contract, graph, checks, limit) -> dict:
    """Summarize graph totals and selected quality findings without I/O.

    ``entities`` and ``edges_contract`` are accepted with the workspace inputs
    so callers can pass the complete graph context; record counts are based on
    the stored records, including records with unknown contract types.
    ``graph`` is a mapping with ``nodes`` and ``edges`` lists of typed records.
    """
    del entities, edges_contract
    nodes: list[Node] = graph["nodes"]
    edges: list[Edge] = graph["edges"]
    selected = set(checks)
    node_by_id = {node.id: node for node in nodes}
    degree = {node.id: 0 for node in nodes}
    no_evidence_nodes = []
    no_description_nodes = []

    for node in nodes:
        if not node.evidences:
            no_evidence_nodes.append(node.id)
        if not node.description.strip():
            no_description_nodes.append(node.id)

    no_evidence_edges = []
    no_description_edges = []
    valid_component_nodes: set[str] = set()
    parent = {node.id: node.id for node in nodes}

    def find(node_id: str) -> str:
        while parent[node_id] != node_id:
            parent[node_id] = parent[parent[node_id]]
            node_id = parent[node_id]
        return node_id

    for edge in edges:
        if not edge.evidences:
            no_evidence_edges.append(edge)
        if not edge.description.strip():
            no_description_edges.append(edge)
        source = edge.source if edge.source in node_by_id else None
        target = edge.target if edge.target in node_by_id else None
        if source is None or target is None:
            continue
        degree[source] += 1
        degree[target] += 1
        valid_component_nodes.update((source, target))
        source_root, target_root = find(source), find(target)
        if source_root != target_root:
            parent[target_root] = source_root

    result = {
        "nodes": {"total": len(nodes), "by_type": _by_type(nodes)},
        "edges": {"total": len(edges), "by_type": _by_type(edges)},
    }
    if "orphans" in selected:
        orphan_ids = sorted(node_id for node_id, value in degree.items() if value == 0)
        result["orphans"] = _samples(orphan_ids, limit)
    if "no-evidence" in selected:
        result["no_evidence"] = {
            "nodes": _samples(sorted(no_evidence_nodes), limit),
            "edges": _samples(
                [compact_edge_tuple(edge, node_by_id) for edge in sorted(
                    no_evidence_edges, key=lambda item: (item.source, item.type, item.target, item.id)
                )], limit,
            ),
        }
    if "no-description" in selected:
        result["no_description"] = {
            "nodes": _samples(sorted(no_description_nodes), limit),
            "edges": _samples(
                [compact_edge_tuple(edge, node_by_id) for edge in sorted(
                    no_description_edges, key=lambda item: (item.source, item.type, item.target, item.id)
                )], limit,
            ),
        }
    if "components" in selected:
        sizes = Counter(find(node_id) for node_id in valid_component_nodes)
        result["components"] = {
            "count": len(sizes), "largest": max(sizes.values(), default=0),
        }
    return result
