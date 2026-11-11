import json
import tempfile
import unittest
from pathlib import Path

from graph_lcb.graphs.engine import Graph, GraphError
from graph_lcb.graphs.types import Edge, Node


class GraphTraversalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.directory = Path(self.temp_dir.name)
        (self.directory / "entities.json").write_text(
            json.dumps({"NODE": {"properties": {}}}), encoding="utf-8"
        )
        (self.directory / "edges.json").write_text(
            json.dumps({
                "LINK": {"source": ["NODE"], "target": ["NODE"], "properties": {}},
                "OTHER": {"source": ["NODE"], "target": ["NODE"], "properties": {}},
            }),
            encoding="utf-8",
        )
        self.graph = Graph(self.directory)

    def put_graph(self, node_ids: list[str], edges: list[tuple[str, str, str]]) -> None:
        nodes = [Node(id=node_id, type="NODE", name=node_id) for node_id in node_ids]
        edge_records = [
            Edge(id=f"e{index}", type=kind, source=source, target=target)
            for index, (source, kind, target) in enumerate(edges)
        ]
        self.graph.save({"nodes": nodes, "edges": edge_records})

    def test_defaults_to_both_and_honors_depth_and_edge_type(self) -> None:
        self.put_graph(
            ["a", "b", "c", "d"],
            [("a", "LINK", "b"), ("b", "OTHER", "c"), ("a", "LINK", "d"), ("c", "LINK", "a")],
        )

        result = self.graph.traverse("a", depth=2, edge_types={"LINK"})

        self.assertEqual(result["nodes"], [
            ["a", "NODE", "a"],
            ["b", "NODE", "b"],
            ["c", "NODE", "c"],
            ["d", "NODE", "d"],
        ])
        self.assertEqual(result["edges"], [
            ["a", "LINK", "b", "NODE"],
            ["a", "LINK", "d", "NODE"],
            ["c", "LINK", "a", "NODE"],
        ])
        self.assertFalse(result["truncated"])

    def test_direction_can_select_incoming_edges(self) -> None:
        self.put_graph(["a", "b", "c"], [("a", "LINK", "b"), ("c", "LINK", "b")])

        result = self.graph.traverse("b", direction="in")

        self.assertEqual(result["nodes"], [["b", "NODE", "b"], ["a", "NODE", "a"], ["c", "NODE", "c"]])
        self.assertEqual(result["edges"], [["a", "LINK", "b", "NODE"], ["c", "LINK", "b", "NODE"]])

    def test_both_directions_do_not_repeat_nodes_in_a_cycle(self) -> None:
        self.put_graph(["a", "b", "c"], [("a", "LINK", "b"), ("b", "LINK", "c"), ("c", "LINK", "a")])

        result = self.graph.traverse("a", direction="both", depth=4)

        self.assertEqual([node[0] for node in result["nodes"]], ["a", "b", "c"])
        self.assertEqual(len(result["edges"]), 3)

    def test_truncation_preserves_edges_from_earlier_depths(self) -> None:
        self.put_graph(
            ["00", "a", "b", "c", "d"],
            [("00", "LINK", "a"), ("a", "LINK", "b"), ("b", "LINK", "c"), ("b", "LINK", "d")],
        )

        result = self.graph.traverse("00", depth=3, limit=2)

        self.assertEqual([node[0] for node in result["nodes"]], ["00", "a", "b"])
        self.assertEqual(result["edges"], [["00", "LINK", "a", "NODE"], ["a", "LINK", "b", "NODE"]])
        self.assertTrue(result["truncated"])

    def test_zero_limit_is_rejected(self) -> None:
        with self.assertRaisesRegex(GraphError, "limit must be positive"):
            self.graph.traverse("a", limit=0)

    def test_target_type_is_not_persisted_on_edges(self) -> None:
        self.put_graph(["a", "b"], [("a", "LINK", "b")])
        graph_data = json.loads(self.graph.path.read_text(encoding="utf-8"))
        self.assertNotIn("target_type", graph_data["edges"][0])
        edge = self.graph.list_edges()[0]
        self.assertFalse(hasattr(edge, "target_type"))


if __name__ == "__main__":
    unittest.main()
