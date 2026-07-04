"""Gateway to the CloudFormation API."""

from typing import TYPE_CHECKING, Self

from botocore.exceptions import BotoCoreError, ClientError

from awst.aws.errors import map_botocore_error
from awst.aws.models import StackSummary

if TYPE_CHECKING:
    from mypy_boto3_cloudformation import CloudFormationClient
    from mypy_boto3_cloudformation.type_defs import StackTypeDef


class CloudFormationGateway:
    """Read-only access to CloudFormation, returning plain data models."""

    def __init__(self: Self, client: CloudFormationClient) -> None:
        self._client = client

    def list_stacks(self: Self) -> list[StackSummary]:
        """Return every stack in the account/region, sorted by name.

        Raises AwsError for any credential, network, or API failure.
        """
        try:
            paginator = self._client.get_paginator("describe_stacks")
            stacks = [_to_summary(stack) for page in paginator.paginate() for stack in page["Stacks"]]
        except (BotoCoreError, ClientError) as error:
            raise map_botocore_error(error) from error
        return sorted(stacks, key=lambda stack: stack.name)


def _to_summary(stack: StackTypeDef) -> StackSummary:
    created = stack["CreationTime"]
    return StackSummary(
        name=stack["StackName"],
        status=stack["StackStatus"],
        created=created,
        updated=stack.get("LastUpdatedTime", created),
        description=stack.get("Description"),
    )
