"""Provider fetcher — orchestrates parallel or sequential API calls."""

from __future__ import annotations

import signal
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai_usage.models import ProviderData
    from ai_usage.providers import Provider


class FetchError(Exception):
    """Wraps an error from a specific provider."""


def _fetch_provider(provider: Provider) -> tuple[str, ProviderData]:
    """Fetch a single provider (target for ThreadPoolExecutor)."""
    return provider.name, provider.fetch()


def fetch_all(
    providers: dict[str, Provider],
    parallel: bool = True,
    total_timeout: int | None = None,
) -> dict[str, ProviderData]:
    """Fetch data from multiple providers.

    Args:
        providers: Dict of name → Provider instances.
        parallel: If True, fetch concurrently via ThreadPoolExecutor.
        total_timeout: Max total seconds for all fetches (None = no cap).

    Returns:
        Dict of provider_name → ProviderData.
    """
    if not providers:
        return {}

    if not parallel or len(providers) == 1:
        # Sequential (single provider, or parallel disabled)
        results: dict[str, ProviderData] = {}
        for name, prov in providers.items():
            _, data = _fetch_provider(prov)
            results[name] = data
        return results

    # Parallel with ThreadPoolExecutor
    results = {}
    with ThreadPoolExecutor(max_workers=min(len(providers), 8)) as executor:
        futures: dict[Future, str] = {}
        for name, prov in providers.items():
            future = executor.submit(_fetch_provider, prov)
            futures[future] = name

        for future in futures:
            name = futures[future]
            try:
                timeout = total_timeout if total_timeout else None
                prov_name, data = future.result(timeout=timeout)
                results[prov_name] = data
            except FutureTimeout:
                results[name] = type(
                    "ProviderData", (), {
                        "balance": None, "spent": None,
                        "tokens": None, "models": {},
                        "extra": None, "meta": {"timeout": True},
                    },
                )()
            except Exception as e:
                results[name] = type(
                    "ProviderData", (), {
                        "balance": None, "spent": None,
                        "tokens": None, "models": {},
                        "extra": None, "meta": {"error": str(e)},
                    },
                )()

    return results
