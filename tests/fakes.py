"""Test fakes for AWS gateways."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from awst.aws.models import AwsError, StackSummary


class FakeCloudFormationGateway:
    """In-memory stand-in for the real CloudFormation gateway."""

    def __init__(
        self: Self,
        stacks: list[StackSummary] | None = None,
        error: AwsError | None = None,
    ) -> None:
        self.stacks = stacks or []
        self.error = error
        self.calls = 0

    def list_stacks(self: Self) -> list[StackSummary]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return list(self.stacks)
