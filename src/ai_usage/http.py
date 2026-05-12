"""HTTP client with retry, timeout, and connection reuse."""

from __future__ import annotations

import json
import logging
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

# Transient HTTP status codes worth retrying
_RETRYABLE_STATUSES = frozenset({429, 502, 503, 504})

# Exceptions worth retrying
_RETRYABLE_ERRORS = (URLError, ConnectionError, TimeoutError, OSError)

# Non-retryable: we don't retry on these
_NON_RETRYABLE = frozenset({400, 401, 403, 404, 405})


class HttpClient:
    """HTTP client with retry, connection reuse, and configurable timeout."""

    def __init__(
        self,
        timeout: int = 10,
        max_retries: int = 3,
        retry_backoff: float = 0.5,
        user_agent: str = "ai-usage/2.0",
    ) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.user_agent = user_agent

    def get_json(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> dict | list:
        """GET a JSON endpoint with retry logic.

        Args:
            url: The URL to GET.
            headers: Extra headers (Authorization, etc.).
            timeout: Per-request timeout in seconds (default: self.timeout).

        Returns:
            Parsed JSON body as dict or list.

        Raises:
            HTTPError: On non-retryable HTTP errors (400-405).
            URLError: On network errors after retries exhausted.
            ValueError: On invalid JSON response.
        """
        if timeout is None:
            timeout = self.timeout

        hdrs = {"User-Agent": self.user_agent}
        if headers:
            hdrs.update(headers)

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                req = Request(url, headers=hdrs)
                with urlopen(req, timeout=timeout) as resp:
                    body = resp.read()
                    return json.loads(body)
            except HTTPError as e:
                if e.code in _NON_RETRYABLE:
                    raise
                if e.code in _RETRYABLE_STATUSES and attempt < self.max_retries:
                    logger.debug("HTTP %d on %s, retrying (%d/%d)",
                                 e.code, url, attempt + 1, self.max_retries)
                    time.sleep(self.retry_backoff * (2 ** attempt))
                    last_error = e
                    continue
                raise
            except _RETRYABLE_ERRORS as e:
                if attempt < self.max_retries:
                    logger.debug("Network error on %s: %s, retrying (%d/%d)",
                                 url, e, attempt + 1, self.max_retries)
                    time.sleep(self.retry_backoff * (2 ** attempt))
                    last_error = e
                    continue
                raise
            except ValueError as e:
                # JSON decode error — don't retry
                raise

        # Should not reach here, but if we do:
        if last_error:
            raise last_error
        raise URLError(f"Failed to fetch {url} after {self.max_retries} retries")
