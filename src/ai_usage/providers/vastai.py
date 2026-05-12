"""Vast.ai provider — balance + GPU rental spend."""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime
from urllib.parse import quote

from ai_usage.models import ProviderData
from ai_usage.providers import Provider, registry


@registry.register
class VastAIProvider(Provider):
    name = "vastai"
    display_name = "Vast.ai"

    def fetch(self) -> ProviderData:
        data = ProviderData(models=OrderedDict())

        if not self.creds.vastai_api_key:
            return data

        auth = {"Authorization": f"Bearer {self.creds.vastai_api_key}"}

        # Balance
        try:
            r = self.http.get_json(
                "https://console.vast.ai/api/v0/users/current/", auth,
            )
            data.balance = float(r.get("credit", 0))
        except Exception:
            data.meta["balance_error"] = True

        # Spend (monthly charges)
        try:
            now = datetime.now()
            month_start = int(datetime(now.year, now.month, 1).timestamp())
            if now.month == 12:
                month_end = int(datetime(now.year + 1, 1, 1).timestamp())
            else:
                month_end = int(datetime(now.year, now.month + 1, 1).timestamp())

            filters = json.dumps(
                {"day": {"gte": month_start, "lte": month_end}},
                separators=(",", ":"),
            )
            url = (
                f"https://cloud.vast.ai/api/v0/charges/?"
                f"select_filters={quote(filters)}&latest_first=true&limit=50"
            )
            charges = self.http.get_json(url, auth)
            spent = sum(
                float(r.get("amount", 0)) for r in charges.get("results", [])
            )
            if spent > 0:
                data.spent = spent
        except Exception:
            data.meta["spend_error"] = True

        return data
