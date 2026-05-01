# AI Usage Watcher — Implementation Plan

## Research Summary

### xAI (api.x.ai/v1)
- **Credit balance**: NO public API. Dashboard-only at `https://console.x.ai/team/default/billing`
- **Usage details**: NO public API for token/model breakdown. Response headers may include rate-limit info
- **Approach**: Verify API key works via `GET /v1/models`, link to console dashboard. xAI does not expose usage programmatically.

### DeepSeek (api.deepseek.com)
- **Credit balance**: `GET /user/balance` → `{"is_available": true, "balance_infos": [{"currency": "CNY", "total_balance": "110.00", "granted_balance": "10.00", "topped_up_balance": "100.00"}]}`
- **Usage details**: No per-model/token breakdown API. Dashboard at `https://platform.deepseek.com/`
- **Auth**: `Authorization: Bearer <api_key>`

### Vast.ai (console.vast.ai/api/v0)
- **Credit balance**: `GET /api/v0/billing/show-charges` (current balance/credits)
- **Usage/costs**: `/api/v0/billing/show-charges` returns charge history
- **Auth**: `Authorization: Bearer <api_key>` (from cloud.vast.ai/manage-keys)

## Architecture

Single Python script (`aiwatch`) — no external dependencies, stdlib only.

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
aiwatch all                # Same as no args
```

## API Keys

Read from environment variables:
- `XAI_API_KEY`
- `DEEPSEEK_API_KEY`
- `VASTAI_API_KEY`

## Output Format

Tabular display for each provider:

```
═══ xAI ═══
  Status: ✅ API key valid (or ❌ missing/invalid)
  Credits: Dashboard only → https://console.x.ai/team/default/billing
  Usage:   Not available via API

═══ DeepSeek ═══
  Status:  ✅ Connected
  Balance: $110.00 USD (granted: $10.00, topped-up: $100.00)
  Usage:   Dashboard only → https://platform.deepseek.com/

═══ Vast.ai ═══
  Status:  ✅ Connected
  Credits: $42.50
  Charges: Last 5 charges shown
```

## Implementation Order

1. Create `aiwatch` script with provider stubs
2. Implement DeepSeek balance check (simplest API)
3. Implement Vast.ai credit check
4. Implement xAI key verification + dashboard link
5. Add `--json` flag for machine-readable output
6. Add `--verbose` for detailed output
