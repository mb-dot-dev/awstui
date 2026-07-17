"""Tests for botocore -> AwsError mapping."""

from typing import TYPE_CHECKING, NoReturn, cast

from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    EndpointConnectionError,
    NoCredentialsError,
    SSOTokenLoadError,
    TokenRetrievalError,
    UnauthorizedSSOTokenError,
)
import pytest

from awst.aws.cloudformation import CloudFormationGateway
from awst.aws.errors import map_botocore_error
from awst.aws.models import AwsError, CredentialsError

if TYPE_CHECKING:
    from mypy_boto3_cloudformation import CloudFormationClient


def test_missing_credentials_get_a_credentials_hint() -> None:
    error = map_botocore_error(NoCredentialsError())

    assert "credentials" in error.message.lower()
    assert error.hint is not None
    assert "aws sso login" in error.hint


def test_expired_sso_token_gets_a_credentials_hint() -> None:
    error = map_botocore_error(TokenRetrievalError(provider="sso", error_msg="token expired"))

    assert error.hint is not None
    assert "aws sso login" in error.hint


def test_connection_error_gets_a_network_hint() -> None:
    error = map_botocore_error(EndpointConnectionError(endpoint_url="https://cloudformation.example"))

    assert error.hint is not None
    assert "network" in error.hint.lower()


def test_client_error_uses_the_service_message() -> None:
    client_error = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "User is not authorized"}},
        "DescribeStacks",
    )

    error = map_botocore_error(client_error)

    assert error.message == "User is not authorized"


def test_unknown_botocore_error_falls_back_to_str() -> None:
    error = map_botocore_error(BotoCoreError())

    assert error.message == str(BotoCoreError())


class _ExplodingClient:
    def get_paginator(self, _operation_name: str) -> NoReturn:
        raise NoCredentialsError


def test_list_stacks_raises_aws_error() -> None:
    gateway = CloudFormationGateway(cast("CloudFormationClient", _ExplodingClient()))

    with pytest.raises(AwsError) as excinfo:
        gateway.list_stacks()

    assert excinfo.value.hint is not None


@pytest.mark.parametrize(
    "botocore_error",
    [
        NoCredentialsError(),
        SSOTokenLoadError(profile_name="dev", error_msg="missing"),
        TokenRetrievalError(provider="sso", error_msg="expired"),
        UnauthorizedSSOTokenError(),
    ],
)
def test_credential_failures_map_to_credentials_error(botocore_error: Exception) -> None:
    error = map_botocore_error(botocore_error)

    assert isinstance(error, CredentialsError)


def test_non_credential_failures_are_not_credentials_errors() -> None:
    error = map_botocore_error(BotoCoreError())

    assert not isinstance(error, CredentialsError)
