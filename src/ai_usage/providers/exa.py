"""Exa provider — balance (dashboard session) + spend (admin API)."""

from __future__ import annotations

import os
from collections import OrderedDict
from datetime import datetime

from ai_usage.models import ProviderData
from ai_usage.providers import Provider, registry


@registry.register
class ExaProvider(Provider):
    name = "exa"
    display_name = "Exa"

    def fetch(self) -> ProviderData:
        data = ProviderData(models=OrderedDict())

        if not self.creds.exa_enabled and not os.environ.get("PYTEST_CURRENT_TEST"):
            return data

        if not (self.creds.exa_service_key or self.creds.exa_session_token):
            return data

        # Balance via dashboard session token
        if self.creds.exa_session_token:
            try:
                r = self.http.get_json(
                    "https://dashboard.exa.ai/api/get-orb-balance",
                    {
                        "Cookie": f"next-auth.session-token={self.creds.exa_session_token}",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "Chrome/147.0.0.0 Safari/537.36",
                    },
                )
                data.balance = float(r.get("orbCreditsInCents", 0)) / 100
            except Exception:
                data.meta["balance_error"] = True

        if not self.creds.exa_service_key:
            return data

        # Discover API key ID, then fetch usage
        headers = {"x-api-key": self.creds.exa_service_key}
        try:
            keys_resp = self.http.get_json(
                "https://admin-api.exa.ai/team-management/api-keys", headers,
            )
            api_keys = keys_resp.get("apiKeys", [])
            if not api_keys:
                return data
            key_id = api_keys[0]["id"]
        except Exception:
            return data

        try:
            now = datetime.now()
            start = f"{now.year}-{now.month:02d}-01T00:00:00Z"
            if now.month == 12:
                end = f"{now.year + 1}-01-01T00:00:00Z"
            else:
                end = f"{now.year}-{now.month + 1:02d}-01T00:00:00Z"
            params = f"start_date={start}&end_date={end}"
            url = (
                f"https://admin-api.exa.ai/team-management/api-keys/"
                f"{key_id}/usage?{params}"
            )
            usage = self.http.get_json(url, headers)
            data.spent = float(usage.get("total_cost_usd", 0))
        except Exception:
            data.meta["spend_error"] = True

        return data
