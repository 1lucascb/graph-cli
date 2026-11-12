#!/usr/bin/env python
"""Graph management CLI."""
import json
import shutil
from copy import deepcopy
from pathlib import Path

from graph_lcb.cli import CLI, CLIError, Context
from graph_lcb.graphs.engine import Graph
from graph_lcb.graphs.types import Edge, EdgeResponse, Node

cli = CLI("graph")

EMPTY_ENTITY_CONTRACT = {"$schema": "./schemas/entities.schema.json"}
EMPTY_EDGE_CONTRACT = {"$schema": "./schemas/edges.schema.json"}

def edge_response(edge: Edge, nodes: list[Node]) -> EdgeResponse:
    target = next((node for node in nodes if node.id == edge.target), None)
    return EdgeResponse.from_edge(edge, target.type if target else "")


def json_default(value: object) -> dict:
    if isinstance(value, (Node, Edge, EdgeResponse)):
        return value.to_dict()
    raise TypeError(f"cannot serialize {type(value).__name__}")


def emit(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, default=json_default, separators=(",", ":")))


def initialize_graph_contracts(entities: dict | None = None, edges: dict | None = None,
                               *, dry_run: bool = False,
                               replace_empty_contracts: bool = False) -> list[str]:
    """Create missing contracts and schemas; return the files that would be written."""
    directory = Path(".graph")
    schema_directory = directory / "schemas"
    bundled_schema_directory = Path(__file__).resolve().parents[1] / "contracts" / "schemas"
    entities = entities or EMPTY_ENTITY_CONTRACT
    edges = edges or EMPTY_EDGE_CONTRACT
    writes: list[str] = []
    try:
        if not dry_run:
            directory.mkdir(parents=True, exist_ok=True)
            schema_directory.mkdir(parents=True, exist_ok=True)
        for filename in ("entities.schema.json", "edges.schema.json"):
            source = bundled_schema_directory / filename
            destination = schema_directory / filename
            if not destination.exists():
                writes.append(destination.as_posix())
                if not dry_run:
                    shutil.copyfile(source, destination)
            elif not destination.is_file():
                raise CLIError(f"cannot initialize graph schema: {destination} is not a file")
        for filename, contract in (
            ("entities.json", entities),
            ("edges.json", edges),
        ):
            path = directory / filename
            if path.exists() and not path.is_file():
                raise CLIError(f"cannot initialize graph contract: {path} is not a file")
            if not path.exists():
                writes.append(path.as_posix())
                if not dry_run:
                    path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            elif replace_empty_contracts:
                try:
                    current = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError):
                    current = None
                if isinstance(current, dict) and not any(key != "$schema" for key in current):
                    writes.append(path.as_posix())
                    if not dry_run:
                        path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        raise CLIError(f"cannot initialize graph contracts: {exc}") from exc
    return writes


def starter_contracts() -> tuple[dict, dict]:
    """Return fresh starter contracts without the schema metadata."""
    entities = deepcopy(EMPTY_ENTITY_CONTRACT)
    edges = deepcopy(EMPTY_EDGE_CONTRACT)
    entities.pop("$schema")
    edges.pop("$schema")
    return entities, edges


@cli.handler("init", "Initialize a graph workspace in the current directory.")
def init_graph(ctx: Context) -> None:
    if ctx.args:
        raise CLIError("init accepts no positional arguments")
    from graph_lcb.contracts import list_templates, load_template

    allowed = {"template", "list-templates", "dry-run"}
    unknown = {name for name, _ in ctx._options} - allowed
    if unknown:
        raise CLIError(f"unknown init option: {', '.join(sorted(unknown))}")
    listing = ctx.flag("list-templates")
    dry_run = ctx.flag("dry-run")
    if listing not in (None, True) or dry_run not in (None, True):
        raise CLIError("--list-templates and --dry-run do not accept values")
    raw_template = ctx.flag("template")
    if listing:
        if raw_template is not None or dry_run:
            raise CLIError("--list-templates cannot be combined with other options")
        for name, description in list_templates():
            print(f"{name}\t{description}")
        return
    if raw_template is True:
        raise CLIError("--template requires a template name")
    if raw_template is not None and not isinstance(raw_template, str):
        raise CLIError("--template requires a template name")
    if raw_template == "":
        raise CLIError("--template requires a template name")

    template_name = raw_template
    template_entities = template_edges = None
    if template_name:
        template_entities, template_edges = load_template(template_name)

    directory = Path(".graph")
    # A template fills each missing or schema-only contract. Existing type definitions
    # are preserved independently, so a partial workspace can still receive a template.
    entities = template_entities or EMPTY_ENTITY_CONTRACT
    edges = template_edges or EMPTY_EDGE_CONTRACT
    for filename, template in (("entities.json", template_entities), ("edges.json", template_edges)):
        path = directory / filename
        if template is None or not path.is_file():
            continue
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise CLIError(f"cannot read graph contract {path}: {exc}") from exc
        if isinstance(current, dict) and any(key != "$schema" for key in current):
            if filename == "entities.json":
                entities = current
            else:
                edges = current
    if dry_run:
        writes = initialize_graph_contracts(entities, edges, dry_run=True,
                                            replace_empty_contracts=bool(template_name))
    else:
        writes = initialize_graph_contracts(entities, edges,
                                            replace_empty_contracts=bool(template_name))
    would_apply = bool(template_name and any(name.endswith(("entities.json", "edges.json")) for name in writes))
    applied = would_apply and not dry_run
    contract_writes = any(name.endswith(("entities.json", "edges.json")) for name in writes)
    output = {"initialized": True, "directory": ".graph",
              "contracts": "template" if would_apply else (
                  "empty" if contract_writes and not template_name else "existing")}
    if template_name:
        output.update({"template": template_name, "applied": applied})
        if not applied:
            output["reason"] = ("dry run; no files were written" if dry_run
                                else "contracts already contain types")
    if dry_run:
        output["dry_run"] = True
        output["would_write"] = writes
    emit(output)


def property_arguments(
    ctx: Context, *, allow_combined: bool = False,
) -> tuple[dict | None, dict | None]:
    """Parse full properties replacement and individual JSON property options."""
    raw_properties = ctx.flag("properties")
    property_options = [(name[2:], value) for name, value in ctx._options if name.startswith("p.")]
    malformed = any(name == "p" for name, _ in ctx._options)
    if malformed:
        raise CLIError("use --p.KEY=VALUE for individual properties")
    if raw_properties is not None and property_options and not allow_combined:
        raise CLIError("--properties cannot be combined with --p.KEY options")

    updates: dict[str, object] = {}
    for key, raw_value in property_options:
        if not key:
            raise CLIError("property option requires a key: --p.KEY=VALUE")
        if key in updates:
            raise CLIError(f"property supplied more than once: {key}")
        if not isinstance(raw_value, str):
            raise CLIError(f"--p.{key} requires a value")
        try:
            updates[key] = json.loads(raw_value)
        except json.JSONDecodeError:
            # Plain text is the convenient string form. JSON literals retain
            # their native types, while other unquoted text becomes a string.
            updates[key] = raw_value

    replacement = parse_properties(raw_properties)
    if replacement is not None and property_options:
        duplicate_keys = replacement.keys() & updates.keys()
        if duplicate_keys:
            raise CLIError(f"property filtered more than once: {', '.join(sorted(duplicate_keys))}")
    return replacement, updates or None


def matches_property_filter(
    properties: dict, filters: dict | None, *, case_insensitive_strings: bool = False,
) -> bool:
    if not filters:
        return True
    for key, expected in filters.items():
        if key not in properties:
            return False
        actual = properties.get(key)
        if case_insensitive_strings and isinstance(actual, str) and isinstance(expected, str):
            if actual.casefold() != expected.casefold():
                return False
        elif actual != expected:
            return False
    return True


def parse_properties(raw: object | None) -> dict | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise CLIError("--properties requires a JSON object")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CLIError(f"invalid properties JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise CLIError("--properties must be a JSON object")
    return value


def parse_fields(raw: object | None, allowed: set[str]) -> list[str] | None:
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw:
        raise CLIError("--fields requires comma-separated field names")
    fields = [field.strip() for field in raw.split(",")]
    if any(not field for field in fields):
        raise CLIError("--fields requires comma-separated field names")
    unknown = set(fields) - allowed
    if unknown:
        raise CLIError(f"unknown field: {', '.join(sorted(unknown))}")
    return fields


def parse_edge_types(raw: object | None, graph: Graph) -> set[str] | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise CLIError("--edge requires comma-separated edge types")
    values = {value.strip() for value in raw.split(",")}
    if not values or "" in values:
        raise CLIError("--edge requires comma-separated edge types")
    canonical = {name.casefold(): name for name in graph.edge_types}
    unknown = {value for value in values if value.casefold() not in canonical}
    if unknown:
        raise CLIError(f"unknown edge type: {', '.join(sorted(unknown))}; valid types: {', '.join(sorted(graph.edge_types)) or '(none)'}")
    return {canonical[value.casefold()] for value in values}


def evidences(raw: object) -> list[dict]:
    if not isinstance(raw, str):
        raise CLIError("--evidences requires a JSON array of objects")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CLIError(f"invalid evidences JSON: {exc.msg}") from exc
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise CLIError("--evidences must be a JSON array of objects")
    return value


def positive_limit(value: object, default: int | None = None) -> int | None:
    """Parse an optional --limit value, which must be a positive integer."""
    if value is None:
        return default
    if not isinstance(value, str):
        raise CLIError("--limit requires a positive integer")
    try:
        parsed = int(value)
    except ValueError as exc:
        raise CLIError("--limit requires a positive integer") from exc
    if parsed < 1:
        raise CLIError("--limit must be a positive integer")
    return parsed
