"""Test fakes for AWS gateways."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from awst.aws.models import StackNotFoundError

if TYPE_CHECKING:
    from awst.aws.models import AwsError, StackDetail, StackSummary


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
