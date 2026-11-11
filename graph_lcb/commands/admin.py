from pathlib import Path

from graph_lcb.cli import CLIError, Context
from graph_lcb.graphs.engine import Graph, GraphError, GraphNotInitializedError, InvalidContractError
from graph_lcb.commands.common import cli, emit, positive_limit, starter_contracts
from graph_lcb.graphs.status import CHECKS, compute_status

@cli.handler("validate", "Validate stored graph records against the current contracts (read-only).")
def validate_graph(ctx: Context) -> int:
    if ctx.args or ctx._options:
        raise CLIError("validate accepts no arguments or options")
    try:
        result = Graph(allow_invalid_contracts=True).validate()
    except GraphNotInitializedError as exc:
        result = {
            "valid": False,
            "errors": [{"kind": "workspace", "code": "not_initialized", "message": str(exc)}],
            "summary": {"nodes": 0, "edges": 0, "errors": 1},
            "unavailable": True,
        }
    except InvalidContractError as exc:
        result = {
            "valid": False,
            "errors": [{"kind": "contract", "code": "invalid_contract", "message": str(exc)}],
            "summary": {"nodes": 0, "edges": 0, "errors": 1},
        }
        emit(result)
        return 3
    except GraphError as exc:
        result = {
            "valid": False,
            "errors": [{"kind": "contract", "code": "invalid_contract", "message": str(exc)}],
            "summary": {"nodes": 0, "edges": 0, "errors": 1},
        }
        emit(result)
        return 4
    unavailable = result.pop("unavailable", False)
    emit(result)
    return 4 if unavailable else 0 if result["valid"] else 3


@cli.handler("status", "Summarize graph totals and selected quality findings: status [--check=orphans,no-evidence,no-description,components] [--limit N] [--strict]")
def graph_status(ctx: Context) -> int:
    if ctx.args:
        raise CLIError("status accepts no positional arguments")
    option_names = {name for name, _ in ctx._options}
    unknown_options = option_names - {"check", "limit", "strict"}
    if unknown_options:
        raise CLIError(f"unknown status option: {', '.join(sorted(unknown_options))}")

    raw_checks = ctx.flag("check")
    if raw_checks is None:
        checks = list(CHECKS)
    elif isinstance(raw_checks, str):
        checks = [item.strip() for item in raw_checks.split(",")]
        if not all(checks):
            raise CLIError(f"--check requires comma-separated values: {', '.join(CHECKS)}")
        invalid = sorted(set(checks) - set(CHECKS))
        if invalid:
            raise CLIError(f"unknown --check value: {', '.join(invalid)}; valid checks: {', '.join(CHECKS)}")
    else:
        raise CLIError("--check requires comma-separated values")

    strict = ctx.flag("strict")
    if strict is not None and strict is not True:
        raise CLIError("--strict does not accept a value")
    limit = positive_limit(ctx.flag("limit"), default=10)

    graph = Graph(allow_invalid_contracts=True)
    data = graph.load()
    result = compute_status(graph.entities, graph.edge_types, data, checks, limit)
    result["valid"] = graph.validate()["valid"]
    emit(result)

    has_findings = any(
        (check == "components" and result.get("components", {}).get("count", 0) > 1)
        or (check == "orphans" and result.get("orphans", {}).get("count", 0) > 0)
        or (check == "no-evidence" and (
            result.get("no_evidence", {}).get("nodes", {}).get("count", 0) > 0
            or result.get("no_evidence", {}).get("edges", {}).get("count", 0) > 0
        ))
        or (check == "no-description" and (
            result.get("no_description", {}).get("nodes", {}).get("count", 0) > 0
            or result.get("no_description", {}).get("edges", {}).get("count", 0) > 0
        ))
        for check in checks
    )
    return 3 if strict is True and has_findings else 0

@cli.handler("contract", "Show entity and edge contracts: contract [entities|edges] [--compact]")
def show_schema(ctx: Context) -> None:
    if len(ctx.args) > 1:
        raise CLIError("use contract [entities|edges] [--compact]")
    category = ctx.positional(0, "all").lower()
    if category not in {"all", "entity", "entities", "edge", "edges"}:
        raise CLIError("expected 'entities' or 'edges'")

    contracts_directory = Path(".graph")
    entity_contract_path = contracts_directory / "entities.json"
    edge_contract_path = contracts_directory / "edges.json"
    if (not contracts_directory.exists()
            or (contracts_directory.is_dir()
                and not entity_contract_path.exists()
                and not edge_contract_path.exists())):
        entities, edge_types = starter_contracts()
    else:
        graph = Graph(contracts_directory)
        entities, edge_types = graph.entities, graph.edge_types

    sections = []
    if category in {"all", "entity", "entities"}:
        sections.append(("entities", entities, False))
    if category in {"all", "edge", "edges"}:
        sections.append(("edges", edge_types, True))
    compact = ctx.flag("compact")
    json_output = ctx.flag("json")
    for option, value in (("--compact", compact), ("--json", json_output)):
        if value is not None and value is not True:
            raise CLIError(f"{option} does not accept a value")
    if not compact:
        if len(sections) == 1:
            emit(sections[0][1])
        else:
            emit({name: types for name, types, _ in sections})
        return
    summaries = []
    for section_name, types, is_edge in sections:
        section_summaries = []
        for name, contract in types.items():
            if name == "$schema":
                continue
            description = contract.get("description", "")
            lines = [f"{name}: {description}" if description else name]
            if is_edge:
                lines.extend((
                    f"Source: {', '.join(contract.get('source', []))}",
                    f"Target: {', '.join(contract.get('target', []))}",
                ))
            lines.append("Properties:")
            for property_name, definition in contract.get("properties", {}).items():
                if isinstance(definition, str):
                    property_type, required = definition, False
                else:
                    property_type = definition.get("type", "unknown")
                    required = definition.get("required") is True
                suffix = "; required" if required else ""
                lines.append(f"- {property_name}: {property_type}{suffix}")
            section_summaries.append("\n".join(lines))
        summary = "\n\n".join(section_summaries)
        if len(sections) > 1:
            summary = f"# {section_name.title()}\n" + summary
        summaries.append(summary)
    print("\n\n".join(summaries))
