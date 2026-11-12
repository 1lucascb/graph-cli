"""Commands for installing bundled agent skills."""

from importlib.resources import files
from pathlib import Path
import shutil

from graph_lcb.cli import CLIError, Context
from graph_lcb.commands.common import cli, emit


@cli.handler("install-skill", "Copy the bundled graph-lcb agent skill into a project.")
def install_skill(ctx: Context) -> None:
    if len(ctx.args) != 1 or ctx._options:
        raise CLIError("install-skill requires one destination directory and accepts no options")

    destination_root = Path(ctx.args[0]).expanduser()
    destination = destination_root / "graph-lcb"
    if destination.exists():
        raise CLIError(f"skill destination already exists: {destination}")

    source = files("graph_lcb").joinpath("skills", "graph-lcb")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination)
    except OSError as exc:
        raise CLIError(f"cannot install skill into {destination}: {exc}") from exc

    emit({"installed": True, "path": str(destination)})
