# ai-usage Test Inventory

> Purpose: keep the test surface auditable, generated from source, and drift-checked alongside the CLI documentation.

| Field | Value |
|---|---|
| Owner | Mike Nicks |
| Status | Generated inventory + human strategy notes |
| Last updated | 2026-06-28 |
| Generator | `scripts/generate_test_inventory.py` |
| Runtime gate | `.venv/bin/python -m pytest tests/ -v --cov=ai_usage` |

<!-- BEGIN GENERATED:inventory-summary -->
> **Current inventory:** 112 test functions across 17 files (18 test classes)
<!-- END GENERATED:inventory-summary -->

## How to read this inventory

The generated count below is a static AST count of Python test functions and methods. It intentionally counts test functions, not expanded parametrized runtime cases. The full runtime suite remains the authority for pass/fail behavior.

## Verification commands

```bash
python scripts/generate_test_inventory.py --write
python scripts/generate_test_inventory.py --check
.venv/bin/python -m pytest tests/ -v --cov=ai_usage
```

<!-- BEGIN GENERATED:audit-run -->
Latest inventory: **112 test functions** across **17 files** and **18 test classes** (AST of `test_*` / `*_test.py`). Regenerate with `python scripts/generate_test_inventory.py --write`; enforce with `--check`. Counts are static test functions, not parametrized-case expansions.
<!-- END GENERATED:audit-run -->

## Coverage strategy

| Area | Test files | What the tests protect |
|---|---|---|
| CLI routing | `tests/test_cli.py` | Help text, provider validation, JSON/live fetch routing, history mode, and Nous auth refresh command behavior. |
| Configuration | `tests/test_config.py` | Environment-file parsing, credential defaults, local fallback files, Exa enablement, and Hermes Codex credential-pool loading. |
| Persistence | `tests/test_db.py` | SQLite table creation, snapshot save/query semantics, provider filtering, Codex account-qualified rows, and close idempotence. |
| HTTP + data model | `tests/test_http.py`, `tests/test_models.py` | Retry/non-retry behavior, headers, default user agent, token totals, percentages, and normalized dictionary output. |
| Provider adapters | `tests/test_providers/*.py` | Provider-specific auth-missing paths, successful payload normalization, API-error handling, OAuth refresh/retry behavior, and subscription quota structures. |
| Rendering | `tests/test_render.py` | Table alignment, JSON branch separation, skip reasons, subscription quota rows, per-model output, and history rendering. |

## Per-file generated counts

<!-- BEGIN GENERATED:per-file-counts -->
| Test file | Test functions |
|---|---:|
| `tests/test_cli.py` | 8 |
| `tests/test_config.py` | 10 |
| `tests/test_db.py` | 7 |
| `tests/test_fixtures.py` | 3 |
| `tests/test_http.py` | 4 |
| `tests/test_models.py` | 8 |
| `tests/test_providers/test_claude.py` | 5 |
| `tests/test_providers/test_codex.py` | 5 |
| `tests/test_providers/test_deepseek.py` | 6 |
| `tests/test_providers/test_exa.py` | 5 |
| `tests/test_providers/test_google.py` | 5 |
| `tests/test_providers/test_nous.py` | 4 |
| `tests/test_providers/test_openrouter.py` | 4 |
| `tests/test_providers/test_vastai.py` | 4 |
| `tests/test_providers/test_x.py` | 5 |
| `tests/test_providers/test_xai.py` | 5 |
| `tests/test_render.py` | 24 |
| **Total** | **112** |
<!-- END GENERATED:per-file-counts -->

## Generated test-case inventory

<!-- BEGIN GENERATED:test-case-inventory -->
| File | Class | Test function | Line | Coverage note |
|---|---|---|---:|---|
| `tests/test_cli.py` | `TestCLI` | `test_help_flag` | 13 | Help flag. |
| `tests/test_cli.py` | `TestCLI` | `test_help_subcommand` | 22 | Help subcommand. |
| `tests/test_cli.py` | `TestCLI` | `test_unknown_provider_stderr` | 28 | Unknown provider stderr. |
| `tests/test_cli.py` | `TestCLI` | `test_refresh_auth_nous` | 35 | Refresh auth nous. |
| `tests/test_cli.py` | `TestCLI` | `test_history_unknown_provider` | 48 | History unknown provider. |
| `tests/test_cli.py` | `TestCLI` | `test_live_fetch_json` | 56 | Live fetch json. |
| `tests/test_cli.py` | `TestCLI` | `test_codex_multi_account_saves_account_qualified_snapshots` | 75 | Codex multi account saves account qualified snapshots. |
| `tests/test_cli.py` | `TestCLI` | `test_history_empty` | 100 | History empty. |
| `tests/test_config.py` | `TestReadEnvFile` | `test_reads_simple_file` | 15 | Reads simple file. |
| `tests/test_config.py` | `TestReadEnvFile` | `test_missing_file_returns_empty` | 21 | Missing file returns empty. |
| `tests/test_config.py` | `TestReadEnvFile` | `test_ignores_comments_and_blanks` | 25 | Ignores comments and blanks. |
| `tests/test_config.py` | `TestCredentials` | `test_defaults` | 32 | Defaults. |
| `tests/test_config.py` | `TestCredentials` | `test_custom_values` | 41 | Custom values. |
| `tests/test_config.py` | `TestLoadCredentials` | `test_loads_from_env_vars` | 53 | Loads from env vars. |
| `tests/test_config.py` | `TestLoadCredentials` | `test_loads_from_env_file` | 58 | Loads from env file. |
| `tests/test_config.py` | `TestLoadCredentials` | `test_missing_nous_auth_is_graceful` | 83 | Missing nous auth is graceful. |
| `tests/test_config.py` | `TestLoadCredentials` | `test_loads_codex_credential_pool_from_hermes_auth` | 87 | Loads codex credential pool from hermes auth. |
| `tests/test_config.py` | `TestLoadCredentials` | `test_vast_file_fallback` | 125 | Vast file fallback. |
| `tests/test_db.py` | `TestSnapshotDB` | `test_creates_tables` | 9 | Creates tables. |
| `tests/test_db.py` | `TestSnapshotDB` | `test_save_and_query` | 16 | Save and query. |
| `tests/test_db.py` | `TestSnapshotDB` | `test_filter_by_provider` | 31 | Filter by provider. |
| `tests/test_db.py` | `TestSnapshotDB` | `test_codex_filter_includes_account_qualified_rows` | 46 | Codex filter includes account qualified rows. |
| `tests/test_db.py` | `TestSnapshotDB` | `test_limit` | 57 | Limit. |
| `tests/test_db.py` | `TestSnapshotDB` | `test_all_provider_limit_uses_provider_count` | 65 | All provider limit uses provider count. |
| `tests/test_db.py` | `TestSnapshotDB` | `test_close_is_idempotent` | 73 | Close is idempotent. |
| `tests/test_fixtures.py` | `(module)` | `test_credentials_fixture` | 6 | Credentials fixture provides test values. |
| `tests/test_fixtures.py` | `(module)` | `test_http_client_fixture` | 14 | HTTP client fixture has short timeouts. |
| `tests/test_fixtures.py` | `(module)` | `test_mock_http` | 22 | Mock HTTP client works. |
| `tests/test_http.py` | `TestHttpClient` | `test_get_json_success` | 13 | Get json success. |
| `tests/test_http.py` | `TestHttpClient` | `test_custom_headers` | 18 | Custom headers. |
| `tests/test_http.py` | `TestHttpClient` | `test_default_user_agent` | 26 | Default user agent. |
| `tests/test_http.py` | `TestHttpClient` | `test_retry_config` | 30 | Retry config. |
| `tests/test_models.py` | `TestTokenData` | `test_defaults` | 11 | Defaults. |
| `tests/test_models.py` | `TestTokenData` | `test_total` | 18 | Total. |
| `tests/test_models.py` | `TestTokenData` | `test_hit_pct` | 22 | Hit pct. |
| `tests/test_models.py` | `TestTokenData` | `test_miss_pct` | 26 | Miss pct. |
| `tests/test_models.py` | `TestTokenData` | `test_hit_pct_zero_division` | 30 | Hit pct zero division. |
| `tests/test_models.py` | `TestTokenData` | `test_to_dict` | 35 | To dict. |
| `tests/test_models.py` | `TestProviderData` | `test_defaults` | 47 | Defaults. |
| `tests/test_models.py` | `TestProviderData` | `test_with_values` | 53 | With values. |
| `tests/test_providers/test_claude.py` | `(module)` | `test_expired_token_refreshes_before_usage_call` | 66 | Expired token refreshes before usage call. |
| `tests/test_providers/test_claude.py` | `(module)` | `test_auth_failure_refreshes_token_and_retries` | 96 | Auth failure refreshes token and retries. |
| `tests/test_providers/test_claude.py` | `(module)` | `test_plan_type_falls_back_to_local_organization_type` | 130 | Plan type falls back to local organization type. |
| `tests/test_providers/test_claude.py` | `(module)` | `test_local_plan_type_ignores_billing_transport_label` | 150 | Local plan type ignores billing transport label. |
| `tests/test_providers/test_claude.py` | `(module)` | `test_refresh_failure_is_reported_without_raising` | 169 | Refresh failure is reported without raising. |
| `tests/test_providers/test_codex.py` | `(module)` | `test_fetches_all_hermes_codex_accounts` | 114 | Fetches all hermes codex accounts. |
| `tests/test_providers/test_codex.py` | `(module)` | `test_hermes_codex_account_failure_does_not_hide_other_accounts` | 148 | Hermes codex account failure does not hide other accounts. |
| `tests/test_providers/test_codex.py` | `(module)` | `test_rpc_auth_error_is_reported_not_silent_when_relogin_unavailable` | 168 | Rpc auth error is reported not silent when relogin unavailable. |
| `tests/test_providers/test_codex.py` | `(module)` | `test_rpc_auth_error_runs_codex_login_and_retries` | 184 | Rpc auth error runs codex login and retries. |
| `tests/test_providers/test_codex.py` | `(module)` | `test_missing_codex_cli_is_reported_not_silent` | 214 | Missing codex cli is reported not silent. |
| `tests/test_providers/test_deepseek.py` | `TestDeepSeekProvider` | `test_no_credentials_returns_empty` | 9 | No credentials returns empty. |
| `tests/test_providers/test_deepseek.py` | `TestDeepSeekProvider` | `test_balance_success` | 18 | Balance success. |
| `tests/test_providers/test_deepseek.py` | `TestDeepSeekProvider` | `test_balance_api_error_graceful` | 26 | Balance api error graceful. |
| `tests/test_providers/test_deepseek.py` | `TestDeepSeekProvider` | `test_token_usage_success` | 33 | Token usage success. |
| `tests/test_providers/test_deepseek.py` | `TestDeepSeekProvider` | `test_usage_error_graceful` | 63 | Usage error graceful. |
| `tests/test_providers/test_deepseek.py` | `TestDeepSeekProvider` | `test_models_parsed` | 74 | Models parsed. |
| `tests/test_providers/test_exa.py` | `TestExaProvider` | `test_disabled_reports_skip_reason` | 9 | Disabled reports skip reason. |
| `tests/test_providers/test_exa.py` | `TestExaProvider` | `test_no_credentials_returns_empty` | 18 | No credentials returns empty. |
| `tests/test_providers/test_exa.py` | `TestExaProvider` | `test_balance_via_session` | 26 | Balance via session. |
| `tests/test_providers/test_exa.py` | `TestExaProvider` | `test_spend_via_service_key` | 32 | Spend via service key. |
| `tests/test_providers/test_exa.py` | `TestExaProvider` | `test_key_discovery_failure` | 43 | Key discovery failure. |
| `tests/test_providers/test_google.py` | `TestGoogleProvider` | `test_no_auth_file_returns_empty` | 18 | No auth file returns empty. |
| `tests/test_providers/test_google.py` | `TestGoogleProvider` | `test_refresh_token_needed_and_success` | 27 | Refresh token needed and success. |
| `tests/test_providers/test_google.py` | `TestGoogleProvider` | `test_auth_failure_refreshes_and_retries` | 99 | Auth failure refreshes and retries. |
| `tests/test_providers/test_google.py` | `TestGoogleProvider` | `test_missing_remaining_fraction_is_zero` | 156 | When remainingFraction is absent from quotaInfo, quota is exhausted (0%). |
| `tests/test_providers/test_google.py` | `TestGoogleProvider` | `test_api_error_graceful` | 203 | Api error graceful. |
| `tests/test_providers/test_nous.py` | `(module)` | `test_missing_nous_token_reports_auth_missing` | 49 | Missing nous token reports auth missing. |
| `tests/test_providers/test_nous.py` | `(module)` | `test_missing_access_token_refreshes_from_refresh_token` | 63 | Missing access token refreshes from refresh token. |
| `tests/test_providers/test_nous.py` | `(module)` | `test_rejected_token_refreshes_and_retries` | 100 | Rejected token refreshes and retries. |
| `tests/test_providers/test_nous.py` | `(module)` | `test_fetch_reports_total_usable_and_credit_breakdown` | 138 | Fetch reports total usable and credit breakdown. |
| `tests/test_providers/test_openrouter.py` | `TestOpenRouterProvider` | `test_no_key_returns_empty` | 9 | No key returns empty. |
| `tests/test_providers/test_openrouter.py` | `TestOpenRouterProvider` | `test_balance_and_monthly_usage_success` | 16 | Balance and monthly usage success. |
| `tests/test_providers/test_openrouter.py` | `TestOpenRouterProvider` | `test_balance_error_still_fetches_usage` | 30 | Balance error still fetches usage. |
| `tests/test_providers/test_openrouter.py` | `TestOpenRouterProvider` | `test_usage_error_keeps_balance` | 41 | Usage error keeps balance. |
| `tests/test_providers/test_vastai.py` | `TestVastAIProvider` | `test_no_key_returns_empty` | 9 | No key returns empty. |
| `tests/test_providers/test_vastai.py` | `TestVastAIProvider` | `test_balance_success` | 15 | Balance success. |
| `tests/test_providers/test_vastai.py` | `TestVastAIProvider` | `test_spend_success` | 24 | Spend success. |
| `tests/test_providers/test_vastai.py` | `TestVastAIProvider` | `test_balance_error_graceful` | 34 | Balance error graceful. |
| `tests/test_providers/test_x.py` | `TestXProvider` | `test_no_credentials_returns_empty` | 9 | No credentials returns empty. |
| `tests/test_providers/test_x.py` | `TestXProvider` | `test_balance_success` | 15 | Balance success. |
| `tests/test_providers/test_x.py` | `TestXProvider` | `test_spend_with_pricing` | 25 | Spend with pricing. |
| `tests/test_providers/test_x.py` | `TestXProvider` | `test_skips_total_group` | 45 | Skips total group. |
| `tests/test_providers/test_x.py` | `TestXProvider` | `test_api_error_graceful` | 60 | Api error graceful. |
| `tests/test_providers/test_xai.py` | `TestXAIProvider` | `test_no_credentials_returns_empty` | 9 | No credentials returns empty. |
| `tests/test_providers/test_xai.py` | `TestXAIProvider` | `test_balance_success` | 16 | Balance success. |
| `tests/test_providers/test_xai.py` | `TestXAIProvider` | `test_balance_negative_becomes_positive` | 25 | Balance negative becomes positive. |
| `tests/test_providers/test_xai.py` | `TestXAIProvider` | `test_token_and_spend` | 34 | Token and spend. |
| `tests/test_providers/test_xai.py` | `TestXAIProvider` | `test_api_error_graceful` | 56 | Api error graceful. |
| `tests/test_render.py` | `TestFormatting` | `test_fmt_amt_none` | 19 | Fmt amt none. |
| `tests/test_render.py` | `TestFormatting` | `test_fmt_amt_value` | 22 | Fmt amt value. |
| `tests/test_render.py` | `TestFormatting` | `test_fmt_tok_zero` | 25 | Fmt tok zero. |
| `tests/test_render.py` | `TestFormatting` | `test_fmt_tok_value` | 28 | Fmt tok value. |
| `tests/test_render.py` | `TestFormatting` | `test_fmt_countdown_none` | 31 | Fmt countdown none. |
| `tests/test_render.py` | `TestRenderJson` | `test_empty` | 36 | Empty. |
| `tests/test_render.py` | `TestRenderJson` | `test_deepseek` | 40 | Deepseek. |
| `tests/test_render.py` | `TestRenderJson` | `test_codex` | 52 | Codex. |
| `tests/test_render.py` | `TestRenderJson` | `test_codex_multi_account_json` | 65 | Codex multi account json. |
| `tests/test_render.py` | `TestRenderJson` | `test_models_flag` | 80 | Models flag. |
| `tests/test_render.py` | `TestRenderJson` | `test_nous` | 91 | Nous. |
| `tests/test_render.py` | `TestRenderJson` | `test_skip_reason_json` | 117 | Skip reason json. |
| `tests/test_render.py` | `TestRenderTable` | `test_empty` | 133 | Empty. |
| `tests/test_render.py` | `TestRenderTable` | `test_deepseek_row` | 137 | Deepseek row. |
| `tests/test_render.py` | `TestRenderTable` | `test_skip_reason_table` | 148 | Skip reason table. |
| `tests/test_render.py` | `TestRenderTable` | `test_nous_table_reports_total_balance_and_period_spend` | 158 | Nous table reports total balance and period spend. |
| `tests/test_render.py` | `TestRenderTable` | `test_codex_detail_section` | 176 | Codex detail section. |
| `tests/test_render.py` | `TestRenderTable` | `test_codex_multi_account_detail_section` | 191 | Codex multi account detail section. |
| `tests/test_render.py` | `TestRenderTable` | `test_codex_auth_failure_fallback_is_visible` | 212 | Codex auth failure fallback is visible. |
| `tests/test_render.py` | `TestRenderTable` | `test_claude_detail_section` | 223 | Claude detail section. |
| `tests/test_render.py` | `TestRenderTable` | `test_claude_auth_failure_fallback_is_not_misleading_403` | 235 | Claude auth failure fallback is not misleading 403. |
| `tests/test_render.py` | `TestRenderTable` | `test_google_quota_rows_use_entitlement_tier_not_model_heuristic` | 245 | Google quota rows use entitlement tier not model heuristic. |
| `tests/test_render.py` | `TestRenderTable` | `test_google_json_includes_plan_source_and_quota_source` | 271 | Google json includes plan source and quota source. |
| `tests/test_render.py` | `TestRenderTable` | `test_models_section` | 292 | Models section. |
<!-- END GENERATED:test-case-inventory -->
