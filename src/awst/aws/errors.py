"""Translate botocore failures into user-presentable AwsError values."""

from botocore.exceptions import (
    ClientError,
    ConnectTimeoutError,
    EndpointConnectionError,
    NoCredentialsError,
    SSOTokenLoadError,
    TokenRetrievalError,
    UnauthorizedSSOTokenError,
)

from awst.aws.models import AwsError

_CREDENTIALS_HINT = "Check AWS_PROFILE, or run `aws sso login` if you use SSO."
_NETWORK_HINT = "Check your network connection and AWS region."

_CREDENTIAL_ERRORS = (NoCredentialsError, SSOTokenLoadError, TokenRetrievalError, UnauthorizedSSOTokenError)
_NETWORK_ERRORS = (EndpointConnectionError, ConnectTimeoutError)


def map_botocore_error(error: Exception) -> AwsError:
    """Return the AwsError equivalent of a botocore exception."""
    if isinstance(error, _CREDENTIAL_ERRORS):
        return AwsError("No valid AWS credentials found.", hint=_CREDENTIALS_HINT)
    if isinstance(error, _NETWORK_ERRORS):
        return AwsError(str(error), hint=_NETWORK_HINT)
    if isinstance(error, ClientError):
        return AwsError(error.response["Error"]["Message"])
    return AwsError(str(error))
