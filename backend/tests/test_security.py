"""Unit tests for the auth and rate-limiting helpers in main.py (pure logic, no HTTP)."""

import time

import pytest
from fastapi import HTTPException

import main


class TestCheckAppSecret:
    def test_auth_skipped_when_no_secret_configured(self):
        assert main.APP_SECRET == ""  # conftest forced this before import
        main.check_app_secret(None)  # must not raise

    def test_missing_header_rejected(self, monkeypatch):
        monkeypatch.setattr(main, "APP_SECRET", "s3cret")
        with pytest.raises(HTTPException) as exc:
            main.check_app_secret(None)
        assert exc.value.status_code == 401

    def test_wrong_secret_rejected(self, monkeypatch):
        monkeypatch.setattr(main, "APP_SECRET", "s3cret")
        with pytest.raises(HTTPException) as exc:
            main.check_app_secret("wrong")
        assert exc.value.status_code == 401

    def test_correct_secret_accepted(self, monkeypatch):
        monkeypatch.setattr(main, "APP_SECRET", "s3cret")
        main.check_app_secret("s3cret")  # must not raise


class TestCheckRateLimit:
    def test_requests_under_the_limit_pass(self):
        for _ in range(main.RATE_LIMIT_MAX_REQUESTS):
            main.check_rate_limit("1.2.3.4")

    def test_request_over_the_limit_is_rejected(self):
        for _ in range(main.RATE_LIMIT_MAX_REQUESTS):
            main.check_rate_limit("1.2.3.4")
        with pytest.raises(HTTPException) as exc:
            main.check_rate_limit("1.2.3.4")
        assert exc.value.status_code == 429

    def test_limit_is_per_client(self):
        for _ in range(main.RATE_LIMIT_MAX_REQUESTS):
            main.check_rate_limit("1.2.3.4")
        main.check_rate_limit("5.6.7.8")  # different IP: still allowed

    def test_old_entries_expire_out_of_the_window(self, monkeypatch):
        now = time.time()
        monkeypatch.setattr(main.time, "time", lambda: now)
        for _ in range(main.RATE_LIMIT_MAX_REQUESTS):
            main.check_rate_limit("1.2.3.4")
        # Jump past the window: every logged entry is now stale.
        monkeypatch.setattr(main.time, "time", lambda: now + main.RATE_LIMIT_WINDOW_SECONDS + 1)
        main.check_rate_limit("1.2.3.4")  # must not raise
