"""Shared test fixtures."""

import pytest


@pytest.fixture(autouse=True)
def _aws_test_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fake AWS credentials so no test can ever touch a real account."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
