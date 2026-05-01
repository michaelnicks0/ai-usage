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
| **xAI** | ⚠️ Browser cookie | Reads Chrome/Firefox session |

xAI does not expose credit balance via its public API. This tool extracts your
console.x.ai session cookie from your browser (Chrome/Firefox) to check your
balance. You must be logged into `https://console.x.ai` in your browser.

If no browser session is found, it falls back to verifying your API key and
showing a dashboard link.

## Configuration

Store API keys in `.api-keys.env` next to the script:

```bash
XAI_API_KEY=xai-...
DEEPSEEK_API_KEY=sk-...
VASTAI_API_KEY=...
# Optional: manual xAI console session token (if browser cookie fails)
# XAI_CONSOLE_TOKEN=
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

## How xAI cookie extraction works

1. Opens your browser's cookie database (SQLite, read-only, no lock)
2. Finds cookies for `console.x.ai`
3. Uses them to call `console.x.ai/api/team/billing`
4. Extracts the credit balance from the JSON response

Supported browsers:
- **Chrome** — Linux, Windows (via WSL paths)
- **Chromium** — Linux
- **Firefox** — Linux
- **Edge** — Linux

You must be logged into `https://console.x.ai` in one of these browsers.

## API endpoints used

### DeepSeek
- `GET https://api.deepseek.com/user/balance` — returns balance per currency

### Vast.ai
- `GET https://console.vast.ai/api/v0/users/current/` — user info incl. credit
- `GET https://console.vast.ai/api/v0/invoices` — recent invoices

### xAI
- `GET https://api.x.ai/v1/models` — API key verification
- `GET https://console.x.ai/api/team/billing` — credit balance (browser cookie)

## Requirements

Python 3.8+ with no external dependencies (stdlib only, including sqlite3).

## Limitations

- xAI credit balance requires you to be logged into console.x.ai in your browser
- xAI and DeepSeek do not expose per-model token usage breakdowns via API
- Vast.ai invoice format may vary by account type
