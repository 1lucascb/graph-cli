from __future__ import annotations

import json
from pathlib import Path

from graph_lcb.cli import CLIError

TEMPLATES_DIRECTORY = Path(__file__).resolve().parent / "templates"


def list_templates() -> list[tuple[str, str]]:
    """Return available template names and their bundled descriptions."""
    results = []
    for directory in sorted(TEMPLATES_DIRECTORY.iterdir()):
        metadata = directory / "template.json"
        if directory.is_dir() and metadata.is_file():
            try:
                info = json.loads(metadata.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise CLIError(f"cannot load template metadata {metadata.name}: {exc}") from exc
            if isinstance(info, dict) and isinstance(info.get("description"), str):
                results.append((directory.name, info["description"]))
    return results


def load_template(name: str) -> tuple[dict, dict]:
    """Load one template's entity and edge contracts."""
    available = dict(list_templates())
    if name not in available:
        names = ", ".join(available) or "(none)"
        raise CLIError(f"unknown template '{name}'; valid templates: {names}")
    directory = TEMPLATES_DIRECTORY / name
    try:
        entities = json.loads((directory / "entities.json").read_text(encoding="utf-8"))
        edges = json.loads((directory / "edges.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CLIError(f"cannot load template '{name}': {exc}") from exc
    if not isinstance(entities, dict) or not isinstance(edges, dict):
        raise CLIError(f"invalid contract files in template '{name}'")
    return entities, edges


__all__ = ["list_templates", "load_template"]
