"""OpenRouter provider — credit balance + key monthly spend."""

from __future__ import annotations

from collections import OrderedDict

from ai_usage.models import ProviderData
from ai_usage.providers import Provider, registry


@registry.register
class OpenRouterProvider(Provider):
    name = "openrouter"
    display_name = "OpenRouter"

    def fetch(self) -> ProviderData:
        data = ProviderData(models=OrderedDict())

        if not self.creds.openrouter_api_key:
            return data

        headers = {"Authorization": f"Bearer {self.creds.openrouter_api_key}"}
        base = "https://openrouter.ai/api/v1"

        # Account credits. OpenRouter returns all-time purchased credits and usage;
        # the displayed balance is remaining credit.
        try:
            r = self.http.get_json(f"{base}/credits", headers)
            credits = r.get("data", {})
            total_credits = float(credits.get("total_credits", 0))
            total_usage = float(credits.get("total_usage", 0))
            data.balance = total_credits - total_usage
            data.extra = {
                "total_credits": total_credits,
                "total_usage": total_usage,
            }
        except Exception:
            data.meta["balance_error"] = True

        # API key usage. `usage_monthly` is the current key's month-to-date spend.
        try:
            r = self.http.get_json(f"{base}/key", headers)
            key_data = r.get("data", {})
            usage_monthly = key_data.get("usage_monthly")
            if usage_monthly is not None:
                data.spent = float(usage_monthly)
            if data.extra is None:
                data.extra = {}
            data.extra.update({
                "key_usage": key_data.get("usage"),
                "key_usage_daily": key_data.get("usage_daily"),
                "key_usage_weekly": key_data.get("usage_weekly"),
                "key_usage_monthly": key_data.get("usage_monthly"),
                "byok_usage_monthly": key_data.get("byok_usage_monthly"),
                "limit": key_data.get("limit"),
                "limit_remaining": key_data.get("limit_remaining"),
                "is_free_tier": key_data.get("is_free_tier"),
            })
        except Exception:
            data.meta["usage_error"] = True

        return data
