# aiwatch — AI vendor credit & usage watcher

Check credit balance across your AI vendors from the terminal.

## Quick start

```bash
cp .api-keys.env.example .api-keys.env
# edit .api-keys.env with your keys
./aiwatch
```

## Supported providers

| Provider  | Credit Balance | How |
|-----------|---------------|-----|
| **DeepSeek** | ✅ Full API | `GET /user/balance` |
| **Vast.ai** | ✅ Full API | `GET /users/current/` |
| **xAI** | ❌ Blocked by Cloudflare | Browser-only dashboard |

xAI protects console.x.ai with Cloudflare's anti-bot measures. Even with valid
browser session cookies extracted from Chrome/Firefox, Cloudflare blocks
automated requests. You must check your xAI balance manually at
https://console.x.ai/team/default/billing.

The tool will still verify your xAI API key and list available models.

## Configuration

Store API keys in `.api-keys.env` next to the script:

```bash
XAI_API_KEY=xai-...
DEEPSEEK_API_KEY=sk-...
VASTAI_API_KEY=...
```

Keys from `.api-keys.env` take priority over environment variables.

## Usage

```bash
./aiwatch               # All providers
./aiwatch deepseek      # DeepSeek only
./aiwatch xai           # xAI only
./aiwatch vastai        # Vast.ai only
./aiwatch --json        # Machine-readable output
./aiwatch --verbose     # Detailed output
```

## API endpoints used

### DeepSeek
- `GET https://api.deepseek.com/user/balance` — returns balance per currency

### Vast.ai
- `GET https://console.vast.ai/api/v0/users/current/` — user info incl. credit
- `GET https://console.vast.ai/api/v0/invoices` — recent invoices

### xAI
- `GET https://api.x.ai/v1/models` — API key verification
- `GET https://console.x.ai/api/team/billing` — blocked by Cloudflare

## Requirements

Python 3.8+ with no external dependencies (stdlib only, including sqlite3).

## Limitations

- xAI credit balance is blocked by Cloudflare's anti-bot protection
- xAI and DeepSeek do not expose per-model token usage breakdowns via API
- Vast.ai invoice format may vary by account type
