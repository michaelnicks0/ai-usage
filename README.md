# ai-usage-tool

Cross-provider balance + token usage — one command.

```
$ ./get-data
                       DeepSeek                xAI                 Vast.ai                 Exa
────────────────────────────────────────────────────────────────────────────────────────────────
Account Balance                    $6.03                $25.00                 $4.01                   —
Period Spend                       $3.97                 $0.60                $20.99                $0.12
Tokens In (Cache Hit)        118,428,800               315,968                     —                   —
Tokens In (Cache Miss)         7,388,843               435,709                     —                   —
Tokens Out                       379,566                 2,454                     —                   —
Tokens Total                 126,197,209               754,131                     —                   —
```

## Usage

```bash
./get-data                          # all providers
./get-data help                     # same as --help
./get-data -p xai                   # single provider
./get-data -p deepseek,xai          # two providers
./get-data -m                       # per-model token breakdown
./get-data -m -p deepseek,xai       # per-model, filtered
./get-data -j                       # JSON output
./get-data -j -m                    # JSON with per-model breakdown
```

### JSON output

```json
$ ./get-data -j -p deepseek
{
  "deepseek": {
    "balance": 6.03,
    "period_spend": 3.97,
    "tokens_in_hit": 118428800,
    "tokens_in_hit_percentage": 94.1,
    "tokens_in_miss": 7388843,
    "tokens_in_miss_percentage": 5.9,
    "tokens_out": 379566,
    "tokens_total": 126197209
  }
}
```

With `-m`, each provider gets a `models` key:

```json
$ ./get-data -j -m -p deepseek
{
  "deepseek": {
    "balance": 6.03,
    "period_spend": 3.97,
    "tokens_in_hit": 118428800,
    ...
    "models": {
      "deepseek-v4-pro": {
        "tokens_in_hit": 118428800,
        "tokens_in_hit_percentage": 94.1,
        "tokens_in_miss": 7388843,
        "tokens_in_miss_percentage": 5.9,
        "tokens_out": 379566,
        "tokens_total": 126197209
      },
      "deepseek-v4-flash": { ... }
    }
  }
}
```

## Providers

| Provider | Balance | Period Spend | Tokens Hit | Tokens Miss | Tokens Out | Per-model |
|----------|---------|-------------|------------|-------------|------------|-----------|
| DeepSeek | ✅ API | ✅ calc from tokens | ✅ platform API | ✅ platform API | ✅ platform API | ✅ |
| xAI | ✅ mgmt API | ✅ invoice API | ✅ invoice API | ✅ invoice API | ✅ invoice API | ✅ |
| Vast.ai | ✅ API | ✅ charges API | — | — | — | — |
| Exa | — | ✅ admin API | — | — | — | — |

[Architecture diagram →](architecture.html) · [Data architecture →](data-architecture.html)

## API endpoints

| Provider | Data | Endpoint | Auth |
|----------|------|----------|------|
| DeepSeek | Balance | `GET api.deepseek.com/user/balance` | API key |
| DeepSeek | Token usage | `GET platform.deepseek.com/api/v0/usage/amount` | Platform auth token |
| xAI | Balance | `GET management-api.x.ai/v1/billing/teams/{id}/prepaid/balance` | Management key |
| xAI | Token + spend | `GET management-api.x.ai/v1/billing/teams/{id}/postpaid/invoice/preview` | Management key |
| Vast.ai | Balance | `GET console.vast.ai/api/v0/users/current/` | API key |
| Vast.ai | Spend | `GET cloud.vast.ai/api/v0/charges/` (current month) | API key |
| Exa | Spend | `GET admin-api.exa.ai/team-management/api-keys/{id}/usage` | Service key |

## Setup

Add to `~/.hermes/.env`:

```bash
DEEPSEEK_API_KEY=sk-...            # from platform.deepseek.com/api_keys
DEEPSEEK_AUTH_TOKEN=...            # from platform.deepseek.com Network tab
XAI_MANAGEMENT_KEY=xai-token-...   # from console.x.ai/team/default/management-keys
XAI_TEAM_ID=...                    # UUID from management keys page
VASTAI_API_KEY=***                 # from cloud.vast.ai/manage-keys
EXA_SERVICE_KEY=***                # from dashboard.exa.ai (service key, not search key)
```

### Credential refresh

Only `DEEPSEEK_AUTH_TOKEN` expires — it's a browser session token, not an API key.
When token usage data shows `—` for DeepSeek, refresh it:

1. Open https://platform.deepseek.com/usage in Chrome
2. Press F12 → Network tab → refresh the page
3. Find any request to `platform.deepseek.com` → copy the `Authorization: Bearer ...` header value
4. Update `DEEPSEEK_AUTH_TOKEN` in `~/.hermes/.env`

All other credentials are long-lived API keys and never need rotation.
