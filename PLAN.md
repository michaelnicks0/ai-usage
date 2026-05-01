# AI Usage Watcher — Implementation Plan

## Research Summary

### xAI (api.x.ai/v1)
- **Credit balance**: NO public API endpoint. The OpenAPI spec confirms no billing/balance routes.
- **Console API**: `console.x.ai/api/team/billing` exists (returns 403 without auth, not 404) but requires browser session cookies, not API keys.
- **Approach**: 
  1. Extract session cookie from Chrome/Firefox cookie database (user must be logged into console.x.ai)
  2. Fall back to `XAI_CONSOLE_TOKEN` env var for manual session token
  3. If neither works: verify API key and show dashboard link
- **Auth**: `Authorization: Bearer <api_key>` for API endpoints; Cookie-based for console

### DeepSeek (api.deepseek.com)
- **Credit balance**: `GET /user/balance` → `{"is_available": true, "balance_infos": [{"currency": "CNY", "total_balance": "110.00", "granted_balance": "10.00", "topped_up_balance": "100.00"}]}`
- **Auth**: `Authorization: Bearer <api_key>`

### Vast.ai (console.vast.ai/api/v0)
- **Credit balance**: `GET /api/v0/users/current/` — returns user info including credit
- **Invoice history**: `GET /api/v0/invoices`
- **Auth**: `Authorization: Bearer <api_key>` (from cloud.vast.ai/manage-keys)

## Architecture

Single Python script (`aiwatch`) — no external dependencies, stdlib only.
Uses `sqlite3` (stdlib) to read browser cookie databases.

```
~/repos/ai-usage-watcher/
  aiwatch              # Entry point (chmod +x)
  README.md
  PLAN.md
```

## CLI Interface

```
aiwatch                    # Show all providers
aiwatch xai                # xAI only
aiwatch deepseek           # DeepSeek only
aiwatch vastai             # Vast.ai only
aiwatch --json             # Machine-readable JSON output
aiwatch --verbose          # Detailed output
```

## API Keys

Read from environment variables:
- `XAI_API_KEY` — for API verification (not credit balance)
- `DEEPSEEK_API_KEY` — for balance check
- `VASTAI_API_KEY` — for credit check
- `XAI_CONSOLE_TOKEN` — optional manual session token for xAI console

## xAI Cookie Extraction

The tool tries these browser paths:
- Linux: `~/.config/google-chrome/Default/Network/Cookies`
- Linux: `~/.config/chromium/Default/Network/Cookies`
- Linux: `~/.mozilla/firefox/*.default-release/cookies.sqlite`
- WSL: `/mnt/c/Users/*/AppData/Local/Google/Chrome/User Data/*/Network/Cookies`
- WSL: `/mnt/c/Users/*/AppData/Local/Google/Chrome/User Data/*/Cookies`

User must be logged into `https://console.x.ai` in one of these browsers.
