"""Tests for CLI entry point."""

from __future__ import annotations

from collections import OrderedDict
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ai_usage.cli import main


class TestCLI:
    def test_help_flag(self, capsys):
        result = main(["--help"])
        assert result == 0
        captured = capsys.readouterr()
        assert "ai-usage" in captured.out
        assert "Google AI Studio" in captured.out
        assert "OPENROUTER_API_KEY" in captured.out
        assert "EXA_ENABLED" in captured.out

    def test_help_subcommand(self, capsys):
        result = main(["help"])
        assert result == 0
        captured = capsys.readouterr()
        assert "Usage:" in captured.out

    def test_unknown_provider_stderr(self, capsys):
        result = main(["-p", "nonexistent"])
        assert result == 1
        captured = capsys.readouterr()
        assert "Unknown provider" in captured.err

    @patch("ai_usage.providers.nous.refresh_nous_auth")
    def test_refresh_auth_nous(self, mock_refresh, capsys):
        mock_refresh.return_value = SimpleNamespace(
            ok=True,
            message="Nous token refreshed successfully.",
        )

        result = main(["--refresh-auth", "nous"])

        assert result == 0
        captured = capsys.readouterr()
        assert "Nous token refreshed successfully." in captured.out
        mock_refresh.assert_called_once_with()

    def test_history_unknown_provider(self, capsys):
        result = main(["--history", "--history-provider", "nonexistent"])
        assert result == 1
        captured = capsys.readouterr()
        assert "Unknown provider" in captured.err

    @patch("ai_usage.cli.fetch_all")
    @patch("ai_usage.cli.SnapshotDB")
    def test_live_fetch_json(self, mock_db, mock_fetch, capsys):
        from ai_usage.models import ProviderData, TokenData
        mock_fetch.return_value = {
            "deepseek": ProviderData(
                balance=10.0, spent=2.0,
                tokens=TokenData(input=100, cached=50, output=25),
            ),
        }
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance

        result = main(["-j", "-p", "deepseek"])
        assert result == 0
        captured = capsys.readouterr()
        assert '"deepseek"' in captured.out
        assert "10.0" in captured.out

    @patch("ai_usage.cli.fetch_all")
    @patch("ai_usage.cli.SnapshotDB")
    def test_codex_multi_account_saves_account_qualified_snapshots(self, mock_db, mock_fetch, capsys):
        from ai_usage.models import ProviderData

        mock_fetch.return_value = {
            "codex": ProviderData(
                extra={
                    "accounts": OrderedDict([
                        ("primary", {"credits": {"balance": 0}}),
                        ("wife-codex-pro", {"credits": {"balance": 0}}),
                    ])
                },
            ),
        }
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance

        result = main(["-j", "-p", "codex"])

        assert result == 0
        saved_providers = [call.args[0] for call in mock_db_instance.save.call_args_list]
        assert saved_providers == ["codex:primary", "codex:wife-codex-pro"]
        captured = capsys.readouterr()
        assert "wife-codex-pro" in captured.out

    @patch("ai_usage.cli.SnapshotDB")
    def test_history_empty(self, mock_db, capsys):
        mock_db_instance = MagicMock()
        mock_db_instance.query.return_value = []
        mock_db.return_value = mock_db_instance

        result = main(["--history"])
        assert result == 0
        mock_db_instance.query.assert_called_once_with(
            provider=None,
            limit=10,
            provider_count=10,
        )
        captured = capsys.readouterr()
        assert "No history found" in captured.out
