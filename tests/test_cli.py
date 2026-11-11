import io
import unittest
from contextlib import redirect_stderr, redirect_stdout

from graph_lcb.cli import CLIError, Context, CLI


class MyCLITests(unittest.TestCase):
    def setUp(self) -> None:
        self.cli = CLI("graph")
        self.received: tuple[str, str | bool | object] | None = None

        def query(ctx: Context) -> None:
            self.received = (
                ctx.positional(0),
                ctx.flag("name"),
            )

        self.cli.new_handler("query", "Run a graph query.", query)

    def test_dispatches_positionals_and_long_flags(self) -> None:
        result = self.cli.run(["query", "MATCH (n)", "--name", "Ada"])

        self.assertEqual(result, 0)
        self.assertEqual(self.received, ("MATCH (n)", "Ada"))

    def test_rejects_short_flags(self) -> None:
        errors = io.StringIO()
        with redirect_stderr(errors):
            result = self.cli.run(["query", "MATCH (n)", "-n=Ada"])

        self.assertEqual(result, 2)
        self.assertIn("short options are not supported", errors.getvalue())

    def test_dispatches_attached_long_flags(self) -> None:
        result = self.cli.run(["query", "MATCH (n)", "--name=Ada"])

        self.assertEqual(result, 0)
        self.assertEqual(self.received, ("MATCH (n)", "Ada"))

    def test_returns_default_for_missing_flag(self) -> None:
        result = self.cli.run(["query", "MATCH (n)"])

        self.assertEqual(result, 0)
        self.assertEqual(self.received, ("MATCH (n)", None))

    def test_boolean_flag_and_end_of_options(self) -> None:
        context = Context("query", ["-literal"], [("verbose", True)])

        self.assertIs(context.flag("verbose"), True)
        self.assertEqual(context.positional(0), "-literal")

    def test_help_option_after_separator_is_positional(self) -> None:
        result = self.cli.run(["query", "MATCH (n)", "--", "-h"])

        self.assertEqual(result, 0)
        self.assertEqual(self.received, ("MATCH (n)", None))

    def test_help_lists_registered_commands(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            result = self.cli.run(["--help"])

        self.assertEqual(result, 0)
        self.assertIn("query", output.getvalue())
        self.assertIn("Run a graph query.", output.getvalue())

    def test_command_help_shows_description(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            result = self.cli.run(["help", "query"])

        self.assertEqual(result, 0)
        self.assertIn("Usage: graph query", output.getvalue())
        self.assertIn("Run a graph query.", output.getvalue())

    def test_missing_positional_is_reported_as_usage_error(self) -> None:
        errors = io.StringIO()
        with redirect_stderr(errors):
            result = self.cli.run(["query"])

        self.assertEqual(result, 2)
        self.assertIn("missing positional argument 1", errors.getvalue())

    def test_unknown_command_is_reported(self) -> None:
        errors = io.StringIO()
        with redirect_stderr(errors):
            result = self.cli.run(["missing"])

        self.assertEqual(result, 2)
        self.assertIn("unknown command: missing", errors.getvalue())

    def test_invalid_positional_index_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Context("query", [], []).positional(-1)

    def test_cli_error_is_public(self) -> None:
        self.assertTrue(issubclass(CLIError, ValueError))

    def test_handler_decorator_registers_and_returns_callback(self) -> None:
        cli = CLI("graph")
        calls: list[str] = []

        @cli.handler("query", "Run a graph query.")
        def query(ctx: Context) -> None:
            calls.append(ctx.positional(0))

        self.assertEqual(cli.run(["query", "MATCH (n)"]), 0)
        self.assertEqual(calls, ["MATCH (n)"])
        self.assertIs(query, cli._handlers["query"].callback)

    def test_handler_decorator_rejects_duplicate_commands(self) -> None:
        cli = CLI("graph")
        cli.new_handler("query", "First registration.", lambda ctx: None)

        with self.assertRaises(ValueError):
            @cli.handler("query", "Duplicate registration.")
            def query(ctx: Context) -> None:
                pass


if __name__ == "__main__":
    unittest.main()
