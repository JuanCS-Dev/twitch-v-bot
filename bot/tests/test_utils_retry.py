"""Tests for bot.utils.retry module."""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from bot.utils.retry import RetryableError, is_retryable_error, retry_async, with_retry


class TestRetryDecorator(unittest.IsolatedAsyncioTestCase):
    async def test_successful_call_no_retry(self):
        call_count = 0

        @with_retry(max_retries=3)
        async def success_fn():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await success_fn()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 1)

    async def test_retry_on_failure_then_success(self):
        call_count = 0

        @with_retry(max_retries=3, backoff_base=0.01)
        async def fail_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("fail")
            return "success"

        result = await fail_then_success()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)

    async def test_max_retries_exceeded(self):
        call_count = 0

        @with_retry(max_retries=2, backoff_base=0.01)
        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("always fails")

        with self.assertRaises(ValueError):
            await always_fail()

        self.assertEqual(call_count, 3)  # 1 initial + 2 retries

    async def test_custom_retryable_predicate(self):
        call_count = 0

        def is_retryable(e: Exception) -> bool:
            return isinstance(e, ValueError) and str(e) == "retryable"

        @with_retry(max_retries=2, backoff_base=0.01, retryable_predicate=is_retryable)
        async def mixed_errors():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("retryable")
            raise RuntimeError("not retryable")

        with self.assertRaises(RuntimeError):
            await mixed_errors()

        self.assertEqual(call_count, 2)


class TestRetryAsyncFunction(unittest.IsolatedAsyncioTestCase):
    async def test_retry_async_success_first_try(self):
        mock_fn = AsyncMock(return_value="result")
        result = await retry_async(mock_fn, max_retries=3)
        self.assertEqual(result, "result")
        mock_fn.assert_called_once()

    async def test_retry_async_retry_then_success(self):
        mock_fn = AsyncMock(side_effect=[ValueError("fail"), "success"])
        result = await retry_async(mock_fn, max_retries=3, backoff_base=0.01)
        self.assertEqual(result, "success")
        self.assertEqual(mock_fn.call_count, 2)

    async def test_retry_async_exhausted(self):
        mock_fn = AsyncMock(side_effect=ValueError("fail"))
        with self.assertRaises(ValueError):
            await retry_async(mock_fn, max_retries=2, backoff_base=0.01)
        self.assertEqual(mock_fn.call_count, 3)


class TestIsRetryableError(unittest.IsolatedAsyncioTestCase):
    def test_retryable_error_base_class(self):
        self.assertTrue(is_retryable_error(RetryableError()))

    def test_timeout_error(self):
        self.assertTrue(is_retryable_error(TimeoutError()))

    def test_custom_predicate(self):
        def is_network_error(e: Exception) -> bool:
            return isinstance(e, ConnectionError)

        self.assertTrue(is_retryable_error(ConnectionError(), is_network_error))
        self.assertFalse(is_retryable_error(ValueError(), is_network_error))


if __name__ == "__main__":
    unittest.main()
