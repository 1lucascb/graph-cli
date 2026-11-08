"""Graph management CLI entry point."""

import sys

from commands import admin, mutations, queries, records, visualization  # noqa: F401
from commands.common import cli
from graphs.engine import GraphError


def main() -> int:
    try:
        return cli.run()
    except GraphError as exc:
        print(f"graph: error: {exc}", file=sys.stderr)
        return getattr(exc, "exit_code", 2)
