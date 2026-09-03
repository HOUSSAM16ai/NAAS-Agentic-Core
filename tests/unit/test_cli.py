import os
from unittest.mock import MagicMock, patch

import click
from click.testing import CliRunner

from app.cli import cli
from app.cli_handlers.context import CLIContext


def test_cli_env_flag():
    runner = CliRunner()

    @cli.command("dummy")
    @click.pass_context
    def dummy_cmd(ctx):
        click.echo("dummy command run")
        # Check that environment was set
        assert os.environ.get("ENV_FILE") == "test.env"

    with patch.dict(os.environ, {}, clear=True):
        with (
            patch("app.cli.get_settings") as mock_settings,
            patch("app.cli.get_logger") as mock_logger,
            patch("app.cli.get_session"),
        ):
            mock_settings.return_value = MagicMock()
            mock_logger.return_value = MagicMock()

            result = runner.invoke(cli, ["--env", "test.env", "dummy"])

            assert result.exit_code == 0
            assert "dummy command run" in result.output
            assert os.environ.get("ENV_FILE") == "test.env"

    # Cleanup the dynamically added command
    if "dummy" in cli.commands:
        del cli.commands["dummy"]


def test_cli_context_initialization():
    runner = CliRunner()

    mocked_settings = MagicMock()
    mocked_logger = MagicMock()

    # We will verify context inside the dummy command

    @cli.command("verify_ctx")
    @click.pass_context
    def verify_ctx_cmd(ctx):
        assert "context" in ctx.obj
        context = ctx.obj["context"]
        assert isinstance(context, CLIContext)
        assert context.settings == mocked_settings
        assert context.logger == mocked_logger
        # session_provider is get_session, we can check it's not None
        assert context.session_provider is not None
        click.echo("context verified")

    with (
        patch("app.cli.get_settings", return_value=mocked_settings),
        patch("app.cli.get_logger", return_value=mocked_logger),
        patch("app.cli.get_session"),
    ):
        result = runner.invoke(cli, ["verify_ctx"])

        assert result.exit_code == 0
        assert "context verified" in result.output

    # Cleanup the dynamically added command
    if "verify_ctx" in cli.commands:
        del cli.commands["verify_ctx"]


def test_cli_command_registrars():
    runner = CliRunner()

    with patch("app.cli.get_settings"), patch("app.cli.get_logger"), patch("app.cli.get_session"):
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "db" in result.output
        assert "migrate" in result.output
        assert "maintenance" in result.output
