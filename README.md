# ai-providers-cost-tool

Cross-provider balance + token usage — one command.

```
$ ./get-data
                       DeepSeek                   xAI               Vast.ai
───────────────────────────────────────────────────────────────────────────
Balance                   $7.81                $25.00                 $4.01
Input                 3,857,226               435,709                     —
Cached in            72,020,480               315,968                     —
Output                  287,317                 2,454                     —
```

## Quick start

```bash
# Add keys to ~/.hermes/.env (or export as env vars):
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_AUTH_TOKEN=...       # from platform.deepseek.com network tab
XAI_MANAGEMENT_KEY=xai-token-...
XAI_TEAM_ID=551b7c87-...
VASTAI_API_KEY=...            # or auto-read from ~/.config/vastai/vast_api_key

# Run it
./get-data
./get-data --model          # show model names
```

## Providers

| Provider  | Balance | Input tokens | Cached input | Output tokens | Model |
|-----------|---------|-------------|-------------|--------------|-------|
| DeepSeek  | ✅ API  | ✅ platform API | ✅ platform API | ✅ platform API | ✅ |
| xAI       | ✅ mgmt API | ✅ invoice API | ✅ invoice API | ✅ invoice API | ✅ |
| Vast.ai   | ✅ API  | — | — | — | — |

## API endpoints

| Provider | Endpoint | Auth |
|----------|----------|------|
| DeepSeek balance | `GET api.deepseek.com/user/balance` | API key |
| DeepSeek usage | `GET platform.deepseek.com/api/v0/usage/amount` | Platform auth token |
| xAI balance | `GET management-api.x.ai/v1/billing/teams/{id}/prepaid/balance` | Management key |
| xAI tokens | `GET management-api.x.ai/v1/billing/teams/{id}/postpaid/invoice/preview` | Management key |
| Vast.ai | `GET console.vast.ai/api/v0/users/current/` | API key |
