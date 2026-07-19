"""The awst Textual application."""

from typing import TYPE_CHECKING, Self

import boto3
from textual.app import App

from awst.aws import profiles
from awst.aws.cloudformation import CloudFormationGateway
from awst.aws.lambda_ import LambdaGateway
from awst.aws.s3 import S3Gateway
from awst.aws.sqs import SqsGateway
from awst.aws.sso import SsoLoginGateway
from awst.screens.home import HomeScreen
from awst.screens.profiles import ProfileSelectScreen
from awst.screens.sso_login import SsoLoginScreen

if TYPE_CHECKING:
    from collections.abc import Callable

    from awst.aws.models import SsoConfig
    from awst.screens.buckets import BucketGateway
    from awst.screens.functions import FunctionLister
    from awst.screens.queues import QueueLister
    from awst.screens.sso_login import SsoAuthorizer
    from awst.screens.stacks import StackGateway


class AwstApp(App[None]):
    """AWS console terminal UI."""

    def __init__(
        self: Self,
        cloudformation_gateway: StackGateway | None = None,
        s3_gateway: BucketGateway | None = None,
        lambda_gateway: FunctionLister | None = None,
        sqs_gateway: QueueLister | None = None,
        sso_gateway_factory: Callable[[SsoConfig], SsoAuthorizer] | None = None,
    ) -> None:
        super().__init__()
        self._cloudformation_gateway = cloudformation_gateway
        self._s3_gateway = s3_gateway
        self._lambda_gateway = lambda_gateway
        self._sqs_gateway = sqs_gateway
        self._sso_gateway_factory = sso_gateway_factory

    @property
    def cloudformation_gateway(self: Self) -> StackGateway:
        """The CloudFormation gateway, built on first use from the default credential chain."""
        if self._cloudformation_gateway is None:
            session = boto3.Session()
            self._cloudformation_gateway = CloudFormationGateway(session.client("cloudformation"))
        return self._cloudformation_gateway

    @property
    def s3_gateway(self: Self) -> BucketGateway:
        """The S3 gateway, built on first use from the default credential chain."""
        if self._s3_gateway is None:
            session = boto3.Session()
            self._s3_gateway = S3Gateway(session.client("s3"))
        return self._s3_gateway

    @property
    def lambda_gateway(self: Self) -> FunctionLister:
        """The Lambda gateway, built on first use from the default credential chain."""
        if self._lambda_gateway is None:
            session = boto3.Session()
            self._lambda_gateway = LambdaGateway(session.client("lambda"))
        return self._lambda_gateway

    @property
    def sqs_gateway(self: Self) -> QueueLister:
        """The SQS gateway, built on first use from the default credential chain."""
        if self._sqs_gateway is None:
            session = boto3.Session()
            self._sqs_gateway = SqsGateway(session.client("sqs"))
        return self._sqs_gateway

    @property
    def sso_login_possible(self: Self) -> bool:
        """Whether the active profile has SSO settings to log in with."""
        return profiles.sso_config(profiles.active_profile()) is not None

    def make_sso_login_screen(self: Self) -> SsoLoginScreen:
        """A login modal for the active profile; only valid when sso_login_possible."""
        config = profiles.sso_config(profiles.active_profile())
        if config is None:
            message = "the active profile has no SSO configuration"
            raise RuntimeError(message)
        if self._sso_gateway_factory is not None:
            return SsoLoginScreen(self._sso_gateway_factory(config), config)
        session = boto3.Session()
        client = session.client("sso-oidc", region_name=config.sso_region)
        return SsoLoginScreen(SsoLoginGateway(client), config)

    def on_mount(self: Self) -> None:
        profile = profiles.active_profile()
        if profile is not None:
            self.sub_title = profile
            self.push_screen(HomeScreen())
            return
        names = profiles.available_profiles()
        if names:
            self.push_screen(ProfileSelectScreen(names), self._on_profile_selected)
        else:
            self.push_screen(HomeScreen())

    def _on_profile_selected(self: Self, name: str | None) -> None:
        if name is not None:
            profiles.select_profile(name)
            self.sub_title = name
        self.push_screen(HomeScreen())
