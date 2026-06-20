"""Tests for render module."""

from __future__ import annotations

import json
from collections import OrderedDict

from ai_usage.models import ProviderData, TokenData
from ai_usage.render import (
    fmt_amt,
    fmt_countdown,
    fmt_tok,
    render_json,
    render_table,
)


class TestFormatting:
    def test_fmt_amt_none(self):
        assert fmt_amt(None) == "     —"

    def test_fmt_amt_value(self):
        assert fmt_amt(12.50) == "$12.50"

    def test_fmt_tok_zero(self):
        assert fmt_tok(0) == "        —"

    def test_fmt_tok_value(self):
        assert fmt_tok(1234567) == "1,234,567"

    def test_fmt_countdown_none(self):
        assert fmt_countdown(None) == "—"


class TestRenderJson:
    def test_empty(self):
        result = render_json({})
        assert result == "{}"

    def test_deepseek(self):
        td = TokenData(input=400, cached=600, output=200)
        pd = ProviderData(balance=6.03, spent=3.97, tokens=td)
        result = render_json({"deepseek": pd})
        parsed = json.loads(result)
        assert "api" in parsed
        assert "deepseek" in parsed["api"]
        ds = parsed["api"]["deepseek"]
        assert ds["balance"] == 6.03
        assert ds["tokens_in_hit"] == 600
        assert ds["tokens_total"] == 1200

    def test_codex(self):
        pd = ProviderData(
            extra={
                "plan_type": "plus",
                "session": {"remaining_pct": 55, "resets_at": 1778467926},
                "weekly": {"remaining_pct": 93, "resets_at": 1779054726},
            },
        )
        result = render_json({"codex": pd})
        parsed = json.loads(result)
        assert "subscription" in parsed
        assert parsed["subscription"]["codex"]["plan_type"] == "plus"

    def test_codex_multi_account_json(self):
        pd = ProviderData(
            extra={
                "accounts": OrderedDict([
                    ("primary", {"plan_type": "plus", "session": {"remaining_pct": 77}}),
                    ("wife-codex-pro", {"plan_type": "pro", "weekly": {"remaining_pct": 60}}),
                ])
            },
        )
        result = render_json({"codex": pd})
        parsed = json.loads(result)
        accounts = parsed["subscription"]["codex"]["accounts"]
        assert list(accounts) == ["primary", "wife-codex-pro"]
        assert accounts["wife-codex-pro"]["plan_type"] == "pro"

    def test_models_flag(self):
        td = TokenData(input=500, cached=300, output=100)
        pd = ProviderData(balance=25.0, spent=5.0, tokens=td,
                          models=OrderedDict([("deepseek-chat", TokenData(input=500, cached=300, output=100))]))
        result = render_json({"deepseek": pd}, show_model=True)
        parsed = json.loads(result)
        assert "models" in parsed["api"]["deepseek"]
        m = parsed["api"]["deepseek"]["models"]["deepseek-chat"]
        assert m["tokens_in_hit"] == 300
        assert m["tokens_in_miss"] == 500

    def test_nous(self):
        pd = ProviderData(
            balance=21.74, spent=20.00,
            extra={
                "plan_type": "Plus",
                "credits_remaining": 21.74,
                "monthly_charge": 20.00,
                "current_period_end": "2026-06-11",
            },
        )
        result = render_json({"nous": pd})
        parsed = json.loads(result)
        assert parsed["api"]["nous"]["credits_remaining"] == 21.74

    def test_skip_reason_json(self):
        pd = ProviderData(
            meta={
                "skip_reason": "disabled",
                "skip_detail": "set EXA_ENABLED=true",
            },
        )
        result = render_json({"exa": pd})
        parsed = json.loads(result)
        exa = parsed["api"]["exa"]
        assert exa["status"] == "skipped"
        assert exa["reason"] == "disabled"
        assert exa["detail"] == "set EXA_ENABLED=true"


class TestRenderTable:
    def test_empty(self):
        result = render_table({})
        assert result == ""

    def test_deepseek_row(self):
        td = TokenData(input=500000, cached=1000000, output=200000)
        pd = ProviderData(balance=6.03, spent=3.97, tokens=td)
        result = render_table({"deepseek": pd})
        assert "DeepSeek" in result
        assert "$6.03" in result
        assert "1,000,000" in result  # cached
        assert "500,000" in result    # input
        assert "200,000" in result    # output
        assert "1,700,000" in result  # total

    def test_skip_reason_table(self):
        result = render_table({
            "exa": ProviderData(meta={"skip_reason": "disabled"}),
            "nous": ProviderData(meta={"skip_reason": "auth missing"}),
        })
        assert "Exa" in result
        assert "disabled" in result
        assert "Nous" in result
        assert "auth missing" in result

    def test_codex_detail_section(self):
        pd = ProviderData(
            balance=0,
            extra={
                "plan_type": "plus",
                "session": {"remaining_pct": 55, "resets_at": None},
                "weekly": {"remaining_pct": 93, "resets_at": None},
                "credits": {"balance": "0"},
            },
        )
        result = render_table({"codex": pd})
        assert "Subscription Quotas" in result
        assert "Codex" in result
        assert "55%" in result

    def test_codex_multi_account_detail_section(self):
        pd = ProviderData(
            extra={
                "accounts": OrderedDict([
                    ("primary", {
                        "plan_type": "plus",
                        "session": {"remaining_pct": 77, "resets_at": None},
                    }),
                    ("wife-codex-pro", {
                        "plan_type": "pro",
                        "weekly": {"remaining_pct": 60, "resets_at": None},
                    }),
                ])
            },
        )
        result = render_table({"codex": pd})
        assert "Codex (primary)" in result
        assert "Codex (wife-codex-pro)" in result
        assert "77%" in result
        assert "60%" in result

    def test_codex_auth_failure_fallback_is_visible(self):
        pd = ProviderData(
            extra={"plan_type": "unknown"},
            meta={"auth_error": True, "rpc_error": "token_expired"},
        )
        result = render_table({"codex": pd})
        assert "Subscription Quotas" in result
        assert "Codex" in result
        assert "Rate Limits" in result
        assert "auth failed" in result

    def test_claude_detail_section(self):
        pd = ProviderData(
            extra={
                "plan_type": "pro",
                "session": {"remaining_pct": 80, "resets_at": None},
            },
        )
        result = render_table({"claude": pd})
        assert "Subscription Quotas" in result
        assert "Claude Code" in result
        assert "80%" in result

    def test_claude_auth_failure_fallback_is_not_misleading_403(self):
        pd = ProviderData(
            extra={"plan_type": "pro"},
            meta={"oauth_error": True, "refresh_error": "exit 7"},
        )
        result = render_table({"claude": pd})
        assert "Claude Code" in result
        assert "auth failed" in result
        assert "403 blocked" not in result

    def test_google_quota_rows_use_entitlement_tier_not_model_heuristic(self):
        pd = ProviderData(
            extra={
                "plan_type": "free",
                "plan_label": "Antigravity Starter Quota",
                "plan_source": "loadCodeAssist.paidTier",
                "subscription_status": "free",
                "raw_tier_id": "free-tier",
                "quota_source": "fetchAvailableModels",
                "models": OrderedDict([
                    ("gemini-3.1-pro-high", {
                        "display_name": "Gemini 3.1 Pro (High)",
                        "remaining_pct": 100,
                        "resets_at": None,
                    }),
                ]),
            },
        )

        result = render_table({"google": pd})

        assert "Google AI Studio" in result
        assert "Free" in result
        assert "Gemini 3.1 Pro (High)" in result
        assert "Ultra 20x" not in result

    def test_google_json_includes_plan_source_and_quota_source(self):
        pd = ProviderData(
            extra={
                "plan_type": "pro",
                "plan_label": "Google AI Pro",
                "plan_source": "loadCodeAssist.paidTier",
                "subscription_status": "active",
                "raw_tier_id": "g1-pro-tier",
                "quota_source": "fetchAvailableModels",
                "models": {},
            },
        )

        parsed = json.loads(render_json({"google": pd}))
        google = parsed["subscription"]["google ai studio"]

        assert google["plan_type"] == "pro"
        assert google["plan_label"] == "Google AI Pro"
        assert google["plan_source"] == "loadCodeAssist.paidTier"
        assert google["quota_source"] == "fetchAvailableModels"

    def test_models_section(self):
        td = TokenData(input=500, cached=300, output=100)
        pd = ProviderData(
            balance=25.0, spent=5.0, tokens=td,
            models=OrderedDict([("deepseek-chat", TokenData(input=500, cached=300, output=100))]),
        )
        result = render_table({"deepseek": pd}, show_model=True)
        assert "Models — DeepSeek" in result
        assert "deepseek-chat" in result
