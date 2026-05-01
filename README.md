# ai-providers-cost-tool

Cross-provider balance + token usage — one command.

```
$ ./get-data
                         DeepSeek                xAI                 Vast.ai
────────────────────────────────────────────────────────────────────────────────────
Account Balance                    $7.46                $25.00                 $4.01
Tokens In                      4,542,147               435,709                     —
Tokens In (Cached)            80,816,768               315,968                     —
Tokens Out                       303,615                 2,454                     —
Tokens Total                  85,662,530               754,131                     —
```

## Usage

```bash
./get-data                          # all providers
./get-data --provider xai           # single provider
./get-data -p deepseek,xai          # two providers
./get-data --json                   # JSON output
./get-data --json -p vastai         # JSON, single provider
./get-data --model                  # show model names
```

### JSON output

```json
$ ./get-data --json -p deepseek,xai
{
  "deepseek": {
    "balance": 7.19,
    "tokens_in": 5104219,
    "tokens_in_cached": 85533056,
    "tokens_out": 312431,
    "tokens_total": 90849706
  },
  "xai": {
    "balance": 25.0,
    "tokens_in": 435709,
    "tokens_in_cached": 315968,
    "tokens_out": 2454,
    "tokens_total": 754131
  }
}
```

## Providers

| Provider | Balance | Tokens In | Tokens Cached | Tokens Out | Model |
|----------|---------|-----------|---------------|------------|-------|
| DeepSeek | ✅ API | ✅ platform API | ✅ platform API | ✅ platform API | ✅ |
| xAI | ✅ mgmt API | ✅ invoice API | ✅ invoice API | ✅ invoice API | ✅ |
| Vast.ai | ✅ API | — | — | — | — |

## API endpoints

| Provider | Data | Endpoint | Auth |
|----------|------|----------|------|
| DeepSeek | Balance | `GET api.deepseek.com/user/balance` | API key |
| DeepSeek | Token usage | `GET platform.deepseek.com/api/v0/usage/amount` | Platform auth token |
| xAI | Balance | `GET management-api.x.ai/v1/billing/teams/{id}/prepaid/balance` | Management key |
| xAI | Token usage | `GET management-api.x.ai/v1/billing/teams/{id}/postpaid/invoice/preview` | Management key |
| Vast.ai | Balance | `GET console.vast.ai/api/v0/users/current/` | API key |

## Setup

Add to `~/.hermes/.env`:

```bash
DEEPSEEK_API_KEY=sk-...            # from platform.deepseek.com/api_keys
DEEPSEEK_AUTH_TOKEN=...            # from platform.deepseek.com Network tab
XAI_MANAGEMENT_KEY=xai-token-...   # from console.x.ai/team/default/management-keys
XAI_TEAM_ID=...                    # UUID from management keys page
VASTAI_API_KEY=...                 # from cloud.vast.ai/manage-keys
```
