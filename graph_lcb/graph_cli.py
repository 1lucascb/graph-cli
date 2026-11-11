"""Graph management CLI entry point."""

import sys
from importlib.metadata import PackageNotFoundError, version

from graph_lcb.commands import admin, importing, mutations, queries, records, visualization  # noqa: F401
from graph_lcb.commands.common import cli
from graph_lcb.graphs.engine import GraphError


def main() -> int:
    if sys.argv[1:] == ["--version"]:
        try:
            installed_version = version("graph-lcb")
        except PackageNotFoundError:
            installed_version = "unknown"
        print(f"graph {installed_version}")
        return 0

    try:
        return cli.run()
    except GraphError as exc:
        print(f"graph: error: {exc}", file=sys.stderr)
        return getattr(exc, "exit_code", 2)
