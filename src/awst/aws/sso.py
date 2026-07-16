"""Gateway for the AWS SSO OIDC device-authorization login flow."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Self

from botocore.exceptions import BotoCoreError, ClientError

from awst.aws.errors import map_botocore_error
from awst.aws.models import DeviceAuthorization, SlowDownError, SsoToken

if TYPE_CHECKING:
    from mypy_boto3_sso_oidc import SSOOIDCClient

    from awst.aws.models import SsoConfig

_CLIENT_NAME = "awst"
_CLIENT_TYPE = "public"
_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"
_DEFAULT_CACHE_DIR = Path("~/.aws/sso/cache")
_DEFAULT_POLL_INTERVAL_S = 5


class SsoLoginGateway:
    """Drives the SSO OIDC device flow and caches the resulting token."""

    def __init__(self: Self, client: SSOOIDCClient, cache_dir: Path | None = None) -> None:
        self._client = client
        self._cache_dir = cache_dir or _DEFAULT_CACHE_DIR

    def start_device_authorization(self: Self, config: SsoConfig) -> DeviceAuthorization:
        """Register this app with the OIDC service and start a device authorization.

        Raises AwsError for any failure.
        """
        try:
            registration = self._client.register_client(clientName=_CLIENT_NAME, clientType=_CLIENT_TYPE)
            authorization = self._client.start_device_authorization(
                clientId=registration["clientId"],
                clientSecret=registration["clientSecret"],
                startUrl=config.start_url,
            )
        except (BotoCoreError, ClientError) as error:
            raise map_botocore_error(error) from error
        return DeviceAuthorization(
            client_id=registration["clientId"],
            client_secret=registration["clientSecret"],
            registration_expires_at=datetime.fromtimestamp(registration["clientSecretExpiresAt"], tz=UTC),
            device_code=authorization["deviceCode"],
            user_code=authorization["userCode"],
            verification_uri=authorization["verificationUri"],
            verification_uri_complete=authorization["verificationUriComplete"],
            interval=authorization.get("interval", _DEFAULT_POLL_INTERVAL_S),
            expires_at=datetime.now(tz=UTC) + timedelta(seconds=authorization["expiresIn"]),
        )

    def poll_token(self: Self, authorization: DeviceAuthorization) -> SsoToken | None:
        """One create-token attempt; None while the user has not approved yet.

        Raises SlowDownError when the service asks for a longer poll interval,
        and AwsError when the authorization expired or the call failed.
        """
        try:
            response = self._client.create_token(
                clientId=authorization.client_id,
                clientSecret=authorization.client_secret,
                grantType=_GRANT_TYPE,
                deviceCode=authorization.device_code,
            )
        except self._client.exceptions.AuthorizationPendingException:
            return None
        except self._client.exceptions.SlowDownException as error:
            raise SlowDownError from error
        except (BotoCoreError, ClientError) as error:
            raise map_botocore_error(error) from error
        return SsoToken(
            access_token=response["accessToken"],
            expires_at=datetime.now(tz=UTC) + timedelta(seconds=response["expiresIn"]),
            refresh_token=response.get("refreshToken"),
        )
