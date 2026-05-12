"""X (Twitter) API provider — balance + event usage spend."""

from __future__ import annotations

from collections import OrderedDict

from ai_usage.models import ProviderData
from ai_usage.providers import Provider, registry


@registry.register
class XProvider(Provider):
    name = "x"
    display_name = "X API"

    def fetch(self) -> ProviderData:
        data = ProviderData(models=OrderedDict())

        if not (
            self.creds.x_api_auth_token
            and self.creds.x_api_ct0
            and self.creds.x_api_account_id
        ):
            return data

        cookie = f"auth_token={self.creds.x_api_auth_token}; ct0={self.creds.x_api_ct0}"
        headers = {"x-csrf-token": self.creds.x_api_ct0, "Cookie": cookie}
        base = "https://console.x.com/api"

        # Balance
        try:
            r = self.http.get_json(
                f"{base}/accounts/{self.creds.x_api_account_id}/credits", headers,
            )
            data.balance = float(r["credits"]["balance"])
        except Exception:
            data.meta["balance_error"] = True

        # Pricing (for spend calculation)
        pricing: dict[str, float] = {}
        try:
            r = self.http.get_json(f"{base}/credits/pricing", headers)
            pricing = r.get("eventTypePricing", {})
        except Exception:
            pass

        # Usage + spend
        try:
            r = self.http.get_json(
                f"{base}/accounts/{self.creds.x_api_account_id}/usage"
                f"?interval=30days&groupBy=eventType",
                headers,
            )
            usage_data = r.get("usage", {})
            spend = 0.0
            for app_id, app in usage_data.items():
                if app_id == "_total" or not isinstance(app, dict):
                    continue
                groups = app.get("groups", {})
                for event_type, evt in groups.items():
                    count = int(evt.get("usage", 0))
                    if count > 0:
                        data.models[event_type] = type(
                            "TokenData",
                            (),
                            {"input": count, "cached": 0, "output": 0,
                             "total": count, "hit_pct": 0.0, "miss_pct": 0.0},
                        )()
                        if event_type in pricing:
                            spend += count * pricing[event_type]
            if spend > 0:
                data.spent = round(spend, 2)
        except Exception:
            data.meta["usage_error"] = True

        return data
