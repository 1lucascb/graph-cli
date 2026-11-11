# Repository guide

## Project overview

`graph-lcb` is a dependency-light Python CLI for a local, JSON-backed graph.
The `graph` executable reads and writes the `.graph/` workspace in the current
working directory. Python 3.10 or newer is required. The runtime has no
third-party dependencies; pytest is used for development tests.

## Where things live

- `graph` is the source-tree executable shim; `graph_cli.py` is the installed
  console-script entry point and wires command modules into the CLI.
- `cli/` contains the small argument parser, command dispatch, and detailed
  command help text in `help_texts.py`.
- `commands/` contains command handlers, grouped by responsibility:
  - `records.py`: add, edit, delete, and list nodes/edges.
  - `queries.py`: search, traversal, and path query handlers.
  - `admin.py`: initialization, contracts, validation, and status.
  - `importing.py`: JSONL import and conflict handling.
  - `visualization.py` and `visualization-templates/`: HTML graph view.
  - `common.py`: shared command CLI, JSON output, and option helpers.
- `graphs/engine.py` implements graph loading, validation, mutations, and graph
  algorithms. `graphs/types/` defines the node and edge records;
  `graphs/status.py` computes graph status summaries.
- `schemas/` contains the JSON Schemas copied into a new workspace by `graph
  init`.
- `docs/skills/` contains agent workflows for querying a graph and mapping a
  codebase into one. `README.md` is the user-facing command and workspace
  reference. `SEARCH_COMMAND.md` records the search command design.
- `tests/` contains CLI, engine, and command tests. Tests that invoke the CLI
  use temporary workspaces so they do not alter a developer's `.graph/` data.
- `pyproject.toml` defines package metadata, the `graph` console script, and
  the optional test dependency.

## Development workflow

Install the package and test dependency in editable mode, then run the suite:

```sh
python -m pip install -e ".[test]"
python -m pytest
```

For a quick command check from a checkout, run `python graph help COMMAND`.
`graph init` creates a workspace in the current directory, so run it only in a
disposable project or the intended graph project.

## Implementation notes

- Keep command handlers in the existing `commands/` modules and register them
  with the shared `cli` instance imported from `commands.common`.
- Keep user-visible command help in `cli/help_texts.py` and update the matching
  README reference when command behavior or output changes.
- Graph records are typed dataclasses loaded from `.graph/graph.json`; use the
  graph engine for persistence and validation rather than editing the store
  directly in command handlers.
- Preserve compact JSON output and deterministic ordering used by existing
  commands. Node list order follows `graph.json`; edge lists use the engine's
  established edge sort order.
- Keep pure transformations, such as search text extraction, independent of
  filesystem access when practical so they are straightforward to test.
- When changing graph query workflows, update the relevant skill in
  `docs/skills/` so agents use the command consistently.
