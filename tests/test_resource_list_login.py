"""Tests for the SSO login binding on resource list screens."""

import contextlib
import os
from pathlib import Path
from typing import TYPE_CHECKING, Self
import webbrowser

import pytest
from textual.app import App
from textual.widgets import DataTable, Static
from textual.worker import WorkerCancelled, WorkerFailed

from awst.app import AwstApp
from awst.aws.models import AwsError, CredentialsError
from awst.aws.sso import SsoLoginGateway
from awst.screens.buckets import BucketListScreen
from awst.screens.sso_login import SsoLoginScreen
from tests.fakes import FakeS3Gateway, FakeSsoLoginGateway, make_bucket, make_device_authorization

if TYPE_CHECKING:
    from textual.pilot import Pilot

_SSO_CONFIG = """\
[profile dev]
sso_start_url = https://legacy.awsapps.com/start
sso_region = eu-west-1
"""

_PLAIN_CONFIG = """\
[profile dev]
region = eu-west-1
"""

_SSO_SESSION_CONFIG = """\
[profile dev]
sso_session = corp
region = eu-west-1

[sso-session corp]
sso_start_url = https://corp.awsapps.com/start
sso_region = us-east-1
"""


@pytest.fixture(autouse=True)
def _no_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(webbrowser, "open", lambda _url: True)


def _activate_profile(monkeypatch: pytest.MonkeyPatch, config: str) -> None:
    Path(os.environ["AWS_CONFIG_FILE"]).write_text(config)
    monkeypatch.setenv("AWS_PROFILE", "dev")


class PlainBucketApp(App[None]):
    """Harness without the SSO seam, like any third-party App."""

    def __init__(self: Self, gateway: FakeS3Gateway) -> None:
        super().__init__()
        self.gateway = gateway

    def on_mount(self: Self) -> None:
        self.push_screen(BucketListScreen(self.gateway))


def _panel_text(app: App[None]) -> str:
    return str(app.screen.query_one("#error", Static).content)


async def _wait_for_workers(app: App[None], pilot: Pilot[None]) -> None:
    """Let the fetch worker settle; a handled CredentialsError still surfaces as WorkerFailed here."""
    with contextlib.suppress(WorkerFailed, WorkerCancelled):
        await app.workers.wait_for_complete()
    await pilot.pause()


@pytest.mark.asyncio
async def test_login_recovers_from_credential_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _activate_profile(monkeypatch, _SSO_CONFIG)
    sso_gateway = FakeSsoLoginGateway()
    gateway = FakeS3Gateway(error=CredentialsError("token expired", hint="log in"))
    app = AwstApp(s3_gateway=gateway, sso_gateway_factory=lambda _config: sso_gateway)

    async with app.run_test() as pilot:
        await pilot.pause()  # lands on HomeScreen (AWS_PROFILE=dev is active)
        app.push_screen(BucketListScreen(app.s3_gateway))
        await _wait_for_workers(app, pilot)
        assert "Press l to log in via AWS SSO." in _panel_text(app)

        gateway.error = None
        gateway.buckets = [make_bucket("assets")]
        await pilot.press("l")
        for _ in range(100):
            await _wait_for_workers(app, pilot)
            if gateway.calls > 1:
                break

        assert len(sso_gateway.cached) == 1
        assert isinstance(app.screen, BucketListScreen)
        assert app.screen.query_one(DataTable).row_count == 1

        # after a successful load the binding is gone again
        await pilot.press("l")
        await pilot.pause()
        assert isinstance(app.screen, BucketListScreen)


@pytest.mark.asyncio
async def test_login_binding_appears_after_refresh_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _activate_profile(monkeypatch, _SSO_CONFIG)
    sso_gateway = FakeSsoLoginGateway(authorization=make_device_authorization(interval=60), pending_polls=10**6)
    gateway = FakeS3Gateway(buckets=[make_bucket("assets")])
    app = AwstApp(s3_gateway=gateway, sso_gateway_factory=lambda _config: sso_gateway)

    async with app.run_test() as pilot:
        await pilot.pause()  # lands on HomeScreen (AWS_PROFILE=dev is active)
        app.push_screen(BucketListScreen(app.s3_gateway))
        await _wait_for_workers(app, pilot)

        gateway.error = CredentialsError("token expired")
        await pilot.press("r")
        await _wait_for_workers(app, pilot)

        await pilot.press("l")
        await pilot.pause()
        assert isinstance(app.screen, SsoLoginScreen)


@pytest.mark.asyncio
async def test_no_login_for_non_sso_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    _activate_profile(monkeypatch, _PLAIN_CONFIG)
    gateway = FakeS3Gateway(error=CredentialsError("no creds"))
    app = AwstApp(s3_gateway=gateway)

    async with app.run_test() as pilot:
        await pilot.pause()  # lands on HomeScreen (AWS_PROFILE=dev is active)
        app.push_screen(BucketListScreen(app.s3_gateway))
        await _wait_for_workers(app, pilot)
        assert "Press l" not in _panel_text(app)

        await pilot.press("l")
        await pilot.pause()
        assert isinstance(app.screen, BucketListScreen)


@pytest.mark.asyncio
async def test_no_login_for_non_credential_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    _activate_profile(monkeypatch, _SSO_CONFIG)
    gateway = FakeS3Gateway(error=AwsError("throttled"))
    app = AwstApp(s3_gateway=gateway)

    async with app.run_test() as pilot:
        await pilot.pause()  # lands on HomeScreen (AWS_PROFILE=dev is active)
        app.push_screen(BucketListScreen(app.s3_gateway))
        await _wait_for_workers(app, pilot)
        assert "Press l" not in _panel_text(app)

        await pilot.press("l")
        await pilot.pause()
        assert isinstance(app.screen, BucketListScreen)


@pytest.mark.asyncio
async def test_make_sso_login_screen_builds_a_real_gateway_for_the_sso_region(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When no sso_gateway_factory is injected, the real branch builds a client for the sso-session region."""
    _activate_profile(monkeypatch, _SSO_SESSION_CONFIG)
    app = AwstApp(s3_gateway=FakeS3Gateway())

    screen = app.make_sso_login_screen()

    gateway = screen._gateway  # noqa: SLF001
    assert isinstance(gateway, SsoLoginGateway)
    assert gateway._client.meta.region_name == "us-east-1"  # noqa: SLF001


@pytest.mark.asyncio
async def test_no_login_without_app_support() -> None:
    gateway = FakeS3Gateway(error=CredentialsError("no creds"))
    app = PlainBucketApp(gateway)

    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert "Press l" not in _panel_text(app)

        await pilot.press("l")
        await pilot.pause()
        assert isinstance(app.screen, BucketListScreen)
