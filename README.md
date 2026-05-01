# ai-providers-usage-tool

Cross-provider balance + token usage — one command.

```
$ ./get-data
                       DeepSeek                xAI                 Vast.ai
────────────────────────────────────────────────────────────────────────────────────────
Account Balance                    $6.19                $25.00                 $4.01
Period Spend                       $3.81                 $0.60                $20.99
Tokens In (Cache Hit)        109,174,912               315,968                     —
Tokens In (Cache Miss)         7,123,680               435,709                     —
Tokens Out                       357,649                 2,454                     —
Tokens Total                 116,656,241               754,131                     —
```

## Usage

```bash
./get-data                          # all providers
./get-data help                     # same as --help
./get-data --provider xai           # single provider
./get-data -p deepseek,xai          # two providers
./get-data --json                   # JSON output
./get-data --json -p vastai         # JSON, single provider
./get-data --model                  # show model names
```

### JSON output

```json
$ ./get-data --json -p deepseek
{
  "deepseek": {
    "balance": 6.19,
    "period_spend": 3.81,
    "tokens_in_hit": 109174912,
    "tokens_in_hit_percentage": 93.9,
    "tokens_in_miss": 7123680,
    "tokens_in_miss_percentage": 6.1,
    "tokens_out": 357649,
    "tokens_total": 116656241
  }
}
```

## Providers

| Provider | Balance | Period Spend | Tokens Hit | Tokens Miss | Tokens Out | Model |
|----------|---------|-------------|------------|-------------|------------|-------|
| DeepSeek | ✅ API | ✅ calc from tokens | ✅ platform API | ✅ platform API | ✅ platform API | ✅ |
| xAI | ✅ mgmt API | ✅ invoice API | ✅ invoice API | ✅ invoice API | ✅ invoice API | ✅ |
| Vast.ai | ✅ API | ✅ charges API | — | — | — | — |

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

## Setup

Add to `~/.hermes/.env`:

```bash
DEEPSEEK_API_KEY=sk-...            # from platform.deepseek.com/api_keys
DEEPSEEK_AUTH_TOKEN=...            # from platform.deepseek.com Network tab
XAI_MANAGEMENT_KEY=xai-token-...   # from console.x.ai/team/default/management-keys
XAI_TEAM_ID=...                    # UUID from management keys page
VASTAI_API_KEY=...                 # from cloud.vast.ai/manage-keys
```
