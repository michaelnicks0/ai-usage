# aiwatch — AI vendor credit & usage watcher

Check credit balance and usage across your AI vendors from the terminal.

## Supported providers

| Provider  | Credit Balance | Usage Details |
|-----------|---------------|---------------|
| **DeepSeek** | ✅ API endpoint | Dashboard only |
| **Vast.ai** | ✅ API endpoint | Invoice history |
| **xAI**      | Dashboard only | Dashboard only |

xAI does not expose a public billing/usage API. The tool verifies your API key
and links to the console dashboard.

## Usage

```bash
# Set API keys
export XAI_API_KEY="xai-..."
export DEEPSEEK_API_KEY="sk-..."
export VASTAI_API_KEY="..."

# Check all providers
./aiwatch

# Check specific provider
./aiwatch deepseek
./aiwatch xai
./aiwatch vastai

# Machine-readable output
./aiwatch --json

# Verbose mode
./aiwatch --verbose
```

## API endpoints used

### DeepSeek
- `GET https://api.deepseek.com/user/balance` — returns balance per currency

### Vast.ai
- `GET https://console.vast.ai/api/v0/users/current/` — user info incl. credit
- `GET https://console.vast.ai/api/v0/invoices` — recent invoices

### xAI
- `GET https://api.x.ai/v1/models` — key verification only

## Requirements

Python 3.8+ with no external dependencies (stdlib only).

## Limitations

- **xAI** and **DeepSeek** do not expose per-model token usage breakdowns
  via public API. Token counts are only visible on their web dashboards.
- Vast.ai invoice details depend on the `/invoices` endpoint response format,
  which may vary by account type.
