"""Gateway to the SQS API."""

from typing import TYPE_CHECKING, Self

from botocore.exceptions import BotoCoreError, ClientError

from awst.aws.errors import map_botocore_error
from awst.aws.models import Page, QueueSummary

if TYPE_CHECKING:
    from mypy_boto3_sqs import SQSClient


class SqsGateway:
    """Access to SQS, returning plain data models."""

    def __init__(self: Self, client: SQSClient) -> None:
        self._client = client

    def list_queues(self: Self, next_token: str | None = None) -> Page[QueueSummary]:
        """Return one page of queues in the region.

        Raises AwsError for any credential, network, or API failure.
        """
        try:
            if next_token is None:
                response = self._client.list_queues()
            else:
                response = self._client.list_queues(NextToken=next_token)
        except (BotoCoreError, ClientError) as error:
            raise map_botocore_error(error) from error
        queues = tuple(_to_summary(url) for url in response.get("QueueUrls", []))
        return Page(items=queues, next_token=response.get("NextToken"))


def _to_summary(queue_url: str) -> QueueSummary:
    # A page with no queues omits the QueueUrls key entirely; list_queues returns only URLs,
    # so the name is the last path segment and FIFO-ness comes from the mandatory .fifo suffix.
    name = queue_url.rsplit("/", 1)[-1]
    return QueueSummary(name=name, is_fifo=name.endswith(".fifo"))
