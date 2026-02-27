"""Generic retry utilities for async operations."""

import asyncio
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

logger = logging.getLogger("ByteBot")

T = TypeVar("T")


class RetryableError(Exception):
    """Base exception for errors that should trigger retry."""


def is_retryable_error(
    error: Exception, retryable_predicate: Callable[[Exception], bool] | None = None
) -> bool:
    """Check if an error should trigger a retry.

    Args:
        error: The exception that was raised
        retryable_predicate: Optional custom function to determine if error is retryable

    Returns:
        True if the error should trigger a retry
    """
    if retryable_predicate is not None:
        return retryable_predicate(error)
    return isinstance(error, RetryableError | asyncio.TimeoutError)


def with_retry(
    max_retries: int = 3,
    backoff_base: float = 1.0,
    backoff_multiplier: float = 1.0,
    retryable_predicate: Callable[[Exception], bool] | None = None,
    on_retry: Callable[[Exception, int], None] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that retries an async function on failure.

    Args:
        max_retries: Maximum number of retry attempts
        backoff_base: Base delay in seconds (will be multiplied by attempt number)
        backoff_multiplier: Additional multiplier for backoff calculation
        retryable_predicate: Function to determine if error is retryable
        on_retry: Optional callback called on each retry with (error, attempt_number)

    Example:
        @with_retry(max_retries=3, backoff_base=1.0)
        async def fetch_data():
            return await api.get()
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return await fn(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if attempt >= max_retries:
                        break

                    if retryable_predicate is not None and not retryable_predicate(e):
                        break

                    delay = backoff_base * (attempt + 1) * backoff_multiplier

                    if on_retry:
                        on_retry(e, attempt + 1)
                    else:
                        logger.warning(
                            "Retry attempt %d/%d after %.2fs: %s",
                            attempt + 1,
                            max_retries + 1,
                            delay,
                            str(e)[:100],
                        )

                    await asyncio.sleep(delay)

            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected error in retry wrapper")

        return wrapper

    return decorator


async def retry_async(
    fn: Callable[..., Any],
    *args: Any,
    max_retries: int = 3,
    backoff_base: float = 1.0,
    backoff_multiplier: float = 1.0,
    retryable_predicate: Callable[[Exception], bool] | None = None,
    **kwargs: Any,
) -> Any:
    """Retry an async function with exponential backoff.

    This is a functional alternative to the decorator for cases where
    you want to retry a single call without wrapping a function.

    Args:
        fn: Async function to call
        *args: Positional arguments for fn
        max_retries: Maximum number of retry attempts
        backoff_base: Base delay in seconds
        backoff_multiplier: Multiplier for backoff
        retryable_predicate: Custom function to determine retryability
        **kwargs: Keyword arguments for fn

    Returns:
        Result of fn

    Example:
        result = await retry_async(api.fetch, max_retries=3)
    """
    last_exception: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            return await fn(*args, **kwargs)
        except Exception as e:
            last_exception = e

            if attempt >= max_retries:
                break

            if retryable_predicate is not None and not retryable_predicate(e):
                break

            delay = backoff_base * (attempt + 1) * backoff_multiplier
            logger.warning(
                "Retry attempt %d/%d after %.2fs: %s",
                attempt + 1,
                max_retries + 1,
                delay,
                str(e)[:100],
            )
            await asyncio.sleep(delay)

    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected error in retry_async")
