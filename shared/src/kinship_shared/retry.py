"""
Async retry helper with exponential backoff for HTTP calls.

Retries on transient server errors (429, 500, 502, 503, 504) and
network-level failures (connection errors, timeouts). Uses only
stdlib + httpx — no extra dependencies.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

MAX_RETRIES = 3
BASE_DELAY = 1.0  # seconds
BACKOFF_FACTOR = 2.0


async def http_get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict | None = None,
    max_retries: int = MAX_RETRIES,
    base_delay: float = BASE_DELAY,
    backoff_factor: float = BACKOFF_FACTOR,
) -> httpx.Response:
    """
    Perform an HTTP GET with retry + exponential backoff.

    Retries on:
      - httpx.ConnectError / httpx.TimeoutException
      - HTTP status codes 429, 500, 502, 503, 504

    After exhausting retries, re-raises the last exception or returns the
    last failing response (so callers can inspect the status code).
    """
    last_exception: BaseException | None = None

    for attempt in range(max_retries + 1):
        try:
            resp = await client.get(url, params=params)

            if resp.status_code not in RETRYABLE_STATUS_CODES:
                return resp

            # Retryable status code — log and maybe retry
            if attempt < max_retries:
                delay = base_delay * (backoff_factor ** attempt)
                logger.warning(
                    "HTTP %d from %s (attempt %d/%d), retrying in %.1fs",
                    resp.status_code, url, attempt + 1, max_retries + 1, delay,
                )
                await asyncio.sleep(delay)
            else:
                # Exhausted retries — return the response so caller can
                # call raise_for_status() and get the real error
                return resp

        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            last_exception = exc
            if attempt < max_retries:
                delay = base_delay * (backoff_factor ** attempt)
                logger.warning(
                    "%s for %s (attempt %d/%d), retrying in %.1fs",
                    type(exc).__name__, url, attempt + 1, max_retries + 1, delay,
                )
                await asyncio.sleep(delay)
            else:
                raise

    # Should not be reached, but satisfy type checker
    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected state in http_get_with_retry")
