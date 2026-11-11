"""A small, dependency-free command-line interface helper."""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypeVar, overload

from .help_texts import HELP_TEXTS

__all__ = ["CLIError", "Context", "CLI"]

_MISSING = object()
_COMMAND_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")
_FLAG_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_-]*\Z")
_T = TypeVar("_T")


class CLIError(ValueError):
    """An expected command-line usage error."""


class Context:
    """Arguments and options for one command invocation."""

    def __init__(
        self,
        command: str,
        positionals: Sequence[str],
        options: Sequence[tuple[str, str | bool]],
    ) -> None:
        self.command = command
        self.args = tuple(positionals)
        self._options = tuple(options)

    @overload
    def positional(self, index: int) -> str: ...

    @overload
    def positional(self, index: int, default: _T) -> str | _T: ...

    def positional(self, index: int, default: object = _MISSING) -> str | object:
        """Return a positional argument, or its default if one was provided."""
        if index < 0:
            raise ValueError("positional indexes must not be negative")
        if index < len(self.args):
            return self.args[index]
        if default is not _MISSING:
            return default
        raise CLIError(f"missing positional argument {index + 1}")

    @overload
    def flag(self, name: str, default: None = None) -> str | bool | None: ...

    @overload
    def flag(self, name: str, default: _T = ...) -> str | bool | _T: ...

    def flag(
        self,
        name: str,
        default: object = None,
    ) -> str | bool | object:
        """Return an option's value by its long name."""
        normalized_name = name.removeprefix("--").removeprefix("-")
        if not _FLAG_PATTERN.fullmatch(normalized_name):
            raise ValueError(f"invalid flag name: {name!r}")

        for option_name, value in reversed(self._options):
            if option_name == normalized_name:
                return value
        return default


@dataclass(frozen=True)
class _Handler:
    description: str
    callback: Callable[[Context], int | None]
    help_text: str | None = None


class CLI:
    """Register commands and dispatch arguments without third-party packages."""

    def __init__(self, prog: str | None = None) -> None:
        self.prog = prog
        self._handlers: dict[str, _Handler] = {}
        # Detailed, stable command guides live in a small key-value catalog.
        self._help_texts: dict[str, str] = dict(HELP_TEXTS)
        self._before_run_callbacks: list[Callable[[], None]] = []

    @overload
    def before_run(self, callback: Callable[[], None]) -> Callable[[], None]: ...

    @overload
    def before_run(self) -> Callable[[Callable[[], None]], Callable[[], None]]: ...

    def before_run(
        self, callback: Callable[[], None] | None = None
    ) -> Callable[[], None] | Callable[[Callable[[], None]], Callable[[], None]]:
        """Register a no-argument callback to run before a command handler.

        Supports both ``@cli.before_run`` and ``@cli.before_run()``.
        Callbacks run in registration order after command selection and argument
        parsing, so help and usage paths do not trigger command setup.
        """
        def register(function: Callable[[], None]) -> Callable[[], None]:
            self._before_run_callbacks.append(function)
            return function

        return register(callback) if callback is not None else register

    def set_help(self, name: str, help_text: str) -> None:
        """Attach detailed help text to a command."""
        self._help_texts[name] = help_text
        if name in self._handlers:
            handler = self._handlers[name]
            self._handlers[name] = _Handler(handler.description, handler.callback, help_text)

    def new_handler(
        self,
        name: str,
        description: str,
        handler: Callable[[Context], int | None],
        help_text: str | None = None,
    ) -> None:
        """Register a command and the function that handles it."""
        if not _COMMAND_PATTERN.fullmatch(name):
            raise ValueError(f"invalid command name: {name!r}")
        if name in {"help"} or name in self._handlers:
            raise ValueError(f"command already registered or reserved: {name!r}")
        text = help_text or self._help_texts.get(name)
        self._handlers[name] = _Handler(description, handler, text)

    def handler(
        self, name: str, description: str, help_text: str | None = None
    ) -> Callable[[Callable[[Context], int | None]], Callable[[Context], int | None]]:
        """Register a command using a decorator and return its handler unchanged."""

        def register(
            callback: Callable[[Context], int | None],
        ) -> Callable[[Context], int | None]:
            self.new_handler(name, description, callback, help_text=help_text)
            return callback

        return register

    def run(self, argv: Sequence[str] | None = None) -> int:
        """Run the CLI with arguments, defaulting to ``sys.argv[1:]``."""
        arguments = list(sys.argv[1:] if argv is None else argv)
        program = self.prog or os.path.basename(sys.argv[0]) or "cli"

        if not arguments or arguments[0] in {"-h", "--help", "help"}:
            if arguments and arguments[0] == "help":
                if len(arguments) > 2:
                    return self._usage_error("help accepts at most one command", program)
                if len(arguments) == 2:
                    return self._show_command_help(arguments[1], program)
            self._show_help(program)
            return 0

        command = arguments[0]
        registered = self._handlers.get(command)
        if registered is None:
            return self._usage_error(f"unknown command: {command}", program)
        command_arguments = arguments[1:]
        help_arguments = (
            command_arguments[: command_arguments.index("--")]
            if "--" in command_arguments
            else command_arguments
        )
        if any(argument in {"-h", "--help"} for argument in help_arguments):
            self._show_command_help(command, program)
            return 0

        try:
            positionals, options = self._parse_arguments(command_arguments)
            for callback in self._before_run_callbacks:
                callback()
            result = registered.callback(Context(command, positionals, options))
        except CLIError as error:
            return self._usage_error(str(error), program, command)

        return 0 if result is None else result

    def _parse_arguments(
        self, arguments: Sequence[str]
    ) -> tuple[list[str], list[tuple[str, str | bool]]]:
        positionals: list[str] = []
        options: list[tuple[str, str | bool]] = []
        parse_options = True
        index = 0

        while index < len(arguments):
            argument = arguments[index]
            if parse_options and argument == "--":
                parse_options = False
                index += 1
                continue
            if not parse_options or argument == "-" or not argument.startswith("-"):
                positionals.append(argument)
                index += 1
                continue
            if len(argument) > 1 and argument[1].isdigit():
                positionals.append(argument)
                index += 1
                continue

            if not argument.startswith("--"):
                raise CLIError(f"short options are not supported: {argument}")
            option_name, equals, attached_value = argument[2:].partition("=")
            if not option_name:
                raise CLIError("empty option name")
            if equals:
                options.append((option_name, attached_value))
                index += 1
                continue

            if index + 1 < len(arguments) and not arguments[index + 1].startswith("-"):
                options.append((option_name, arguments[index + 1]))
                index += 2
            else:
                options.append((option_name, True))
                index += 1

        return positionals, options

    def _show_help(self, program: str) -> None:
        print(f"Usage: {program} <command> [arguments]", file=sys.stdout)
        print("\nCommands:", file=sys.stdout)
        if not self._handlers:
            print("  (no commands registered)", file=sys.stdout)
        for name, handler in self._handlers.items():
            print(f"  {name:<16} {handler.description}", file=sys.stdout)
        print(f"\nRun '{program} help <command>' for command details.", file=sys.stdout)

    def _show_command_help(self, command: str, program: str) -> int:
        if command == "help":
            self._show_help(program)
            return 0
        registered = self._handlers.get(command)
        if registered is None:
            return self._usage_error(f"unknown command: {command}", program)
        help_text = self._help_texts.get(command) or registered.help_text
        if help_text:
            print(help_text.replace("graph ", f"{program} "), file=sys.stdout)
            return 0
        print(f"Usage: {program} {command} [arguments]", file=sys.stdout)
        if registered.description:
            print(f"\n{registered.description}", file=sys.stdout)
        print("\nOptions: -h, --help  Show this help.", file=sys.stdout)
        return 0

    def _usage_error(self, message: str, program: str, command: str | None = None) -> int:
        print(f"{program}: error: {message}", file=sys.stderr)
        if command is None:
            print(f"Try '{program} --help' for usage.", file=sys.stderr)
        else:
            print(f"Try '{program} {command} --help' for usage.", file=sys.stderr)
        return 2
