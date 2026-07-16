"""Test fakes and model factories for AWS gateways."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Self

from awst.aws.models import (
    BucketSummary,
    DeviceAuthorization,
    FunctionSummary,
    QueueSummary,
    SsoConfig,
    SsoToken,
    StackDetail,
    StackEvent,
    StackNotFoundError,
    StackOutput,
    StackParameter,
    StackResource,
    StackSummary,
)

if TYPE_CHECKING:
    from awst.aws.models import AwsError

_CREATED = datetime(2026, 1, 1, tzinfo=UTC)
_PARAMETERS = (StackParameter(key="Env", value="prod"),)
_OUTPUTS = (StackOutput(key="Url", value="https://example.com", description="endpoint"),)


def make_stack(name: str, status: str = "CREATE_COMPLETE") -> StackSummary:
    """A stack summary with sensible defaults for list-screen tests."""
    return StackSummary(name=name, status=status, created=_CREATED, updated=_CREATED, description=None)


def make_detail(
    parameters: tuple[StackParameter, ...] = _PARAMETERS,
    outputs: tuple[StackOutput, ...] = _OUTPUTS,
) -> StackDetail:
    """A fully populated stack detail named "alpha" for detail-screen tests."""
    return StackDetail(
        name="alpha",
        stack_id="arn:aws:cloudformation:eu-west-1:123456789012:stack/alpha/abc",
        status="CREATE_COMPLETE",
        status_reason=None,
        description="a test stack",
        created=_CREATED,
        updated=_CREATED,
        parameters=parameters,
        outputs=outputs,
        resources=(
            StackResource(
                logical_id="Topic",
                physical_id="arn:aws:sns:eu-west-1:123456789012:topic",
                resource_type="AWS::SNS::Topic",
                status="CREATE_COMPLETE",
            ),
        ),
        events=(
            StackEvent(
                timestamp=_CREATED,
                logical_id="alpha",
                resource_type="AWS::CloudFormation::Stack",
                status="CREATE_COMPLETE",
                reason=None,
            ),
            StackEvent(
                timestamp=_CREATED,
                logical_id="Topic",
                resource_type="AWS::SNS::Topic",
                status="CREATE_IN_PROGRESS",
                reason="Resource creation Initiated",
            ),
        ),
    )


class FakeCloudFormationGateway:
    """In-memory stand-in for the real CloudFormation gateway."""

    def __init__(
        self: Self,
        stacks: list[StackSummary] | None = None,
        error: AwsError | None = None,
        detail: StackDetail | None = None,
        detail_error: AwsError | None = None,
        delete_error: AwsError | None = None,
    ) -> None:
        self.stacks = stacks or []
        self.error = error
        self.detail = detail
        self.detail_error = detail_error
        self.delete_error = delete_error
        self.calls = 0
        self.detail_calls: list[str] = []
        self.deleted: list[str] = []

    def list_stacks(self: Self) -> list[StackSummary]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return list(self.stacks)

    def get_stack_detail(self: Self, name: str) -> StackDetail:
        self.detail_calls.append(name)
        if self.detail_error is not None:
            raise self.detail_error
        if self.detail is None:
            message = f"Stack {name} does not exist."
            raise StackNotFoundError(message)
        return self.detail

    def delete_stack(self: Self, name: str) -> None:
        if self.delete_error is not None:
            raise self.delete_error
        self.deleted.append(name)


def make_bucket(name: str, region: str = "eu-west-1") -> BucketSummary:
    """A bucket summary with sensible defaults for list-screen tests."""
    return BucketSummary(name=name, region=region, created=_CREATED)


class FakeS3Gateway:
    """In-memory stand-in for the real S3 gateway."""

    def __init__(self: Self, buckets: list[BucketSummary] | None = None, error: AwsError | None = None) -> None:
        self.buckets = buckets or []
        self.error = error
        self.calls = 0

    def list_buckets(self: Self) -> list[BucketSummary]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return list(self.buckets)


def make_function(name: str, runtime: str = "python3.14") -> FunctionSummary:
    """A function summary with sensible defaults for list-screen tests."""
    return FunctionSummary(name=name, runtime=runtime, memory_mb=128, timeout_s=30, modified=_CREATED)


class FakeLambdaGateway:
    """In-memory stand-in for the real Lambda gateway."""

    def __init__(self: Self, functions: list[FunctionSummary] | None = None, error: AwsError | None = None) -> None:
        self.functions = functions or []
        self.error = error
        self.calls = 0

    def list_functions(self: Self) -> list[FunctionSummary]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return list(self.functions)


def make_queue(name: str) -> QueueSummary:
    """A queue summary whose FIFO flag follows the .fifo naming rule."""
    return QueueSummary(name=name, is_fifo=name.endswith(".fifo"))


class FakeSqsGateway:
    """In-memory stand-in for the real SQS gateway."""

    def __init__(self: Self, queues: list[QueueSummary] | None = None, error: AwsError | None = None) -> None:
        self.queues = queues or []
        self.error = error
        self.calls = 0

    def list_queues(self: Self) -> list[QueueSummary]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return list(self.queues)


def make_sso_config(session_name: str | None = None) -> SsoConfig:
    """SSO settings matching the canned device-flow responses in tests."""
    return SsoConfig(start_url="https://legacy.awsapps.com/start", sso_region="eu-west-1", session_name=session_name)


def make_device_authorization(interval: int = 0, expires_in_s: int = 600) -> DeviceAuthorization:
    """A device authorization with sensible defaults; interval 0 keeps tests fast."""
    now = datetime.now(tz=UTC)
    return DeviceAuthorization(
        client_id="client-id",
        client_secret="client-secret",
        registration_expires_at=now + timedelta(days=90),
        device_code="device-code",
        user_code="ABCD-EFGH",
        verification_uri="https://device.sso.eu-west-1.amazonaws.com/",
        verification_uri_complete="https://device.sso.eu-west-1.amazonaws.com/?user_code=ABCD-EFGH",
        interval=interval,
        expires_at=now + timedelta(seconds=expires_in_s),
    )


def make_sso_token(refresh_token: str | None = None) -> SsoToken:
    """An SSO access token for login-flow tests."""
    return SsoToken(
        access_token="access-token",
        expires_at=datetime.now(tz=UTC) + timedelta(hours=8),
        refresh_token=refresh_token,
    )
