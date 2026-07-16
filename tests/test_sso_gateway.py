"""Tests for the SSO OIDC login gateway."""

from datetime import UTC, datetime

import boto3
from botocore.stub import Stubber
import pytest

from awst.aws.models import AwsError, SlowDownError
from awst.aws.sso import SsoLoginGateway
from tests.fakes import make_device_authorization, make_sso_config

_REGISTER_EXPECTED = {"clientName": "awst", "clientType": "public"}
_REGISTER_RESPONSE = {
    "clientId": "client-id",
    "clientSecret": "client-secret",
    "clientSecretExpiresAt": 1893456000,
}
_DEVICE_EXPECTED = {
    "clientId": "client-id",
    "clientSecret": "client-secret",
    "startUrl": "https://legacy.awsapps.com/start",
}
_DEVICE_RESPONSE = {
    "deviceCode": "device-code",
    "userCode": "ABCD-EFGH",
    "verificationUri": "https://device.sso.eu-west-1.amazonaws.com/",
    "verificationUriComplete": "https://device.sso.eu-west-1.amazonaws.com/?user_code=ABCD-EFGH",
    "expiresIn": 600,
    "interval": 5,
}
_TOKEN_EXPECTED = {
    "clientId": "client-id",
    "clientSecret": "client-secret",
    "grantType": "urn:ietf:params:oauth:grant-type:device_code",
    "deviceCode": "device-code",
}


def _client():  # noqa: ANN202 — the stubs' client type is verbose and irrelevant here
    return boto3.client("sso-oidc", region_name="eu-west-1")


def test_start_device_authorization_registers_and_starts() -> None:
    client = _client()
    with Stubber(client) as stubber:
        stubber.add_response("register_client", _REGISTER_RESPONSE, _REGISTER_EXPECTED)
        stubber.add_response("start_device_authorization", _DEVICE_RESPONSE, _DEVICE_EXPECTED)

        authorization = SsoLoginGateway(client).start_device_authorization(make_sso_config())

    assert authorization.client_id == "client-id"
    assert authorization.client_secret == "client-secret"
    assert authorization.registration_expires_at == datetime.fromtimestamp(1893456000, tz=UTC)
    assert authorization.device_code == "device-code"
    assert authorization.user_code == "ABCD-EFGH"
    assert authorization.verification_uri_complete.endswith("user_code=ABCD-EFGH")
    assert authorization.interval == 5
    assert authorization.expires_at > datetime.now(tz=UTC)


def test_start_device_authorization_maps_failures_to_aws_error() -> None:
    client = _client()
    with Stubber(client) as stubber:
        stubber.add_client_error(
            "register_client", service_error_code="AccessDeniedException", service_message="denied"
        )

        with pytest.raises(AwsError) as excinfo:
            SsoLoginGateway(client).start_device_authorization(make_sso_config())

    assert excinfo.value.message == "denied"


def test_poll_token_returns_none_while_pending() -> None:
    client = _client()
    with Stubber(client) as stubber:
        stubber.add_client_error(
            "create_token", service_error_code="AuthorizationPendingException", service_message="pending"
        )

        assert SsoLoginGateway(client).poll_token(make_device_authorization()) is None


def test_poll_token_raises_slow_down() -> None:
    client = _client()
    with Stubber(client) as stubber:
        stubber.add_client_error("create_token", service_error_code="SlowDownException", service_message="slow down")

        with pytest.raises(SlowDownError):
            SsoLoginGateway(client).poll_token(make_device_authorization())


def test_poll_token_maps_expiry_to_aws_error() -> None:
    client = _client()
    with Stubber(client) as stubber:
        stubber.add_client_error("create_token", service_error_code="ExpiredTokenException", service_message="expired")

        with pytest.raises(AwsError) as excinfo:
            SsoLoginGateway(client).poll_token(make_device_authorization())

    assert excinfo.value.message == "expired"


def test_poll_token_returns_the_token_on_approval() -> None:
    client = _client()
    response = {"accessToken": "access-token", "tokenType": "Bearer", "expiresIn": 28800, "refreshToken": "refresh"}
    with Stubber(client) as stubber:
        stubber.add_response("create_token", response, _TOKEN_EXPECTED)

        token = SsoLoginGateway(client).poll_token(make_device_authorization())

    assert token is not None
    assert token.access_token == "access-token"
    assert token.refresh_token == "refresh"
    assert token.expires_at > datetime.now(tz=UTC)


def test_poll_token_refresh_token_is_none_when_absent() -> None:
    client = _client()
    response = {"accessToken": "access-token", "tokenType": "Bearer", "expiresIn": 28800}
    with Stubber(client) as stubber:
        stubber.add_response("create_token", response, _TOKEN_EXPECTED)

        token = SsoLoginGateway(client).poll_token(make_device_authorization())

    assert token is not None
    assert token.refresh_token is None
