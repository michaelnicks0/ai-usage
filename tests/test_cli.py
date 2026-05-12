"""Tests for CLI entry point."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ai_usage.cli import main


class TestCLI:
    def test_help_flag(self, capsys):
        result = main(["--help"])
        assert result == 0
        captured = capsys.readouterr()
        assert "ai-usage" in captured.out

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

    @patch("ai_usage.cli.SnapshotDB")
    def test_history_empty(self, mock_db, capsys):
        mock_db_instance = MagicMock()
        mock_db_instance.query.return_value = []
        mock_db.return_value = mock_db_instance

        result = main(["--history"])
        assert result == 0
        captured = capsys.readouterr()
        assert "No history found" in captured.out
