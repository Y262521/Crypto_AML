from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests


@dataclass(slots=True)
class RetryConfig:
    attempts: int = 3
    backoff_seconds: float = 1.0
    max_backoff_seconds: float = 8.0


def request_with_retry(
    session: requests.Session,
    method: str,
    url: str,
    *,
    retry_config: RetryConfig,
    retry_for_statuses: set[int] | None = None,
    **kwargs: Any,
) -> requests.Response:
    retry_for_statuses = retry_for_statuses or {429, 500, 502, 503, 504}
    last_error: Exception | None = None

    for attempt in range(retry_config.attempts):
        try:
            response = session.request(method=method, url=url, **kwargs)
            if response.status_code in retry_for_statuses:
                response.raise_for_status()
            return response
        except (requests.RequestException, requests.HTTPError) as exc:
            last_error = exc
            if attempt == retry_config.attempts - 1:
                break
            delay = min(
                retry_config.backoff_seconds * (2**attempt),
                retry_config.max_backoff_seconds,
            )
            time.sleep(delay)

    if last_error is None:
        raise RuntimeError("Request failed without an exception")
    raise last_error
