import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GRAPH_SCRIPT = ROOT / "graph"


class GraphOutputTests(unittest.TestCase):
    def test_contract_command_formats_contracts_and_required_properties(self) -> None:
        entities = {
            "API": {
                "description": "An API or application service",
                "properties": {
                    "language": {"type": "string", "required": True},
                    "protocol": {"type": "string", "required": True},
                    "framework": "string",
                },
            }
        }
        with tempfile.TemporaryDirectory() as working_directory:
            graph_directory = Path(working_directory) / ".graph"
            graph_directory.mkdir()
            (graph_directory / "entities.json").write_text(
                json.dumps(entities), encoding="utf-8"
            )
            edges = {
                "CALLS": {
                    "description": "A service invokes another API.",
                    "source": ["API"],
                    "target": ["API"],
                    "properties": {
                        "endpoint": {"type": "string", "required": True},
                        "httpVersion": {"type": "string", "required": False},
                    },
                }
            }
            (graph_directory / "edges.json").write_text(
                json.dumps(edges), encoding="utf-8"
            )
            environment = os.environ.copy()
            environment["PYTHONPATH"] = os.pathsep.join(
                filter(None, [str(ROOT), environment.get("PYTHONPATH", "")])
            )

            result = subprocess.run(
                [sys.executable, str(GRAPH_SCRIPT), "contract", "entities"],
                cwd=working_directory,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )
            edge_result = subprocess.run(
                [sys.executable, str(GRAPH_SCRIPT), "contract", "edges"],
                cwd=working_directory,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )
            json_entities_result = subprocess.run(
                [sys.executable, str(GRAPH_SCRIPT), "contract", "entities", "--compact"],
                cwd=working_directory,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )
            json_edges_result = subprocess.run(
                [sys.executable, str(GRAPH_SCRIPT), "contract", "edges", "--compact"],
                cwd=working_directory,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )
            all_compact_result = subprocess.run(
                [sys.executable, str(GRAPH_SCRIPT), "contract", "--compact"],
                cwd=working_directory,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            )

        self.assertEqual(
            result.stdout,
            json.dumps(entities, separators=(",", ":")) + "\n",
        )
        self.assertEqual(
            edge_result.stdout,
            json.dumps(edges, separators=(",", ":")) + "\n",
        )
        self.assertEqual(json_entities_result.stdout,
                         "API: An API or application service\n"
                         "Properties:\n"
                         "- language: string; required\n"
                         "- protocol: string; required\n"
                         "- framework: string\n")
        self.assertEqual(json_edges_result.stdout,
                         "CALLS: A service invokes another API.\n"
                         "Source: API\n"
                         "Target: API\n"
                         "Properties:\n"
                         "- endpoint: string; required\n"
                         "- httpVersion: string\n")
        self.assertIn("# Entities\n", all_compact_result.stdout)
        self.assertIn("\n\n# Edges\n", all_compact_result.stdout)


if __name__ == "__main__":
    unittest.main()

