"""DeepSeek provider — balance + token usage via platform API."""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime

from ai_usage.config import Credentials
from ai_usage.http import HttpClient
from ai_usage.models import ProviderData, TokenData
from ai_usage.providers import Provider, registry


@registry.register
class DeepSeekProvider(Provider):
    name = "deepseek"
    display_name = "DeepSeek"
    has_tokens = True

    def fetch(self) -> ProviderData:
        data = ProviderData(models=OrderedDict())
        now = datetime.now()

        # Balance
        if self.creds.deepseek_api_key:
            try:
                r = self.http.get_json(
                    "https://api.deepseek.com/user/balance",
                    {"Authorization": f"Bearer {self.creds.deepseek_api_key}"},
                )
                for b in r.get("balance_infos", []):
                    if b.get("currency") == "USD":
                        data.balance = float(b["total_balance"])
            except Exception:
                data.meta["balance_error"] = True

        # Token usage
        if self.creds.deepseek_auth_token:
            try:
                r = self.http.get_json(
                    f"https://platform.deepseek.com/api/v0/usage/amount"
                    f"?month={now.month}&year={now.year}",
                    {"Authorization": f"Bearer {self.creds.deepseek_auth_token}",
                     "x-app-version": "20240425.0"},
                )
                for m in r["data"]["biz_data"]["total"]:
                    name = m["model"]
                    md = TokenData()
                    for u in m["usage"]:
                        amt = int(u["amount"])
                        t = u["type"]
                        if t == "PROMPT_CACHE_MISS_TOKEN":
                            data.tokens.input += amt
                            md.input += amt
                        elif t == "PROMPT_CACHE_HIT_TOKEN":
                            data.tokens.cached += amt
                            md.cached += amt
                        elif t == "RESPONSE_TOKEN":
                            data.tokens.output += amt
                            md.output += amt
                    data.models[name] = md

                data.spent = (
                    data.tokens.input / 1_000_000 * self.creds.ds_price_cache_miss +
                    data.tokens.cached / 1_000_000 * self.creds.ds_price_cache_hit +
                    data.tokens.output / 1_000_000 * self.creds.ds_price_output
                )
            except Exception:
                data.meta["usage_error"] = True

        return data
