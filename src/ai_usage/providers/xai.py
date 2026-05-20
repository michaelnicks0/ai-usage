"""xAI provider — balance + token usage via management API."""

from __future__ import annotations

from collections import OrderedDict

from ai_usage.models import ProviderData, TokenData
from ai_usage.providers import Provider, registry


@registry.register
class XAIProvider(Provider):
    name = "xai"
    display_name = "xAI"
    has_tokens = True

    def fetch(self) -> ProviderData:
        data = ProviderData(models=OrderedDict())

        if not (self.creds.xai_management_key and self.creds.xai_team_id):
            return data

        headers = {"Authorization": f"Bearer {self.creds.xai_management_key}"}
        base = f"https://management-api.x.ai/v1/billing/teams/{self.creds.xai_team_id}"

        # Balance
        try:
            r = self.http.get_json(f"{base}/prepaid/balance", headers)
            data.balance = abs(float(r.get("total", {}).get("val", "0"))) / 100
        except Exception:
            data.meta["balance_error"] = True

        # Token usage + spend via invoice preview (with a tight 3s timeout to prevent hanging when xAI backend is slow/broken)
        try:
            r = self.http.get_json(f"{base}/postpaid/invoice/preview", headers, timeout=3)
            inv = r.get("coreInvoice", {})
            for line in inv.get("lines", []):
                desc = line.get("description", "unknown")
                ut = line.get("unitType", "")
                nu = int(line.get("numUnits", "0"))
                md = data.models.setdefault(desc, TokenData())
                if "Cached" in ut:
                    data.tokens.cached += nu
                    md.cached += nu
                elif "Prompt" in ut:
                    data.tokens.input += nu
                    md.input += nu
                elif "Completion" in ut:
                    data.tokens.output += nu
                    md.output += nu
            data.spent = float(inv.get("totalWithCorr", {}).get("val", "0")) / 100
        except Exception:
            data.meta["usage_error"] = True

        return data
