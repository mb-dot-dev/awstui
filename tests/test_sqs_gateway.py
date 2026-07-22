"""Tests for the SQS gateway."""

import boto3
from botocore.stub import Stubber
from moto import mock_aws
import pytest

from awst.aws.models import AwsError
from awst.aws.sqs import SqsGateway, _to_summary


def _gateway() -> SqsGateway:
    return SqsGateway(boto3.client("sqs", region_name="eu-west-1"))


def _create_queue(name: str) -> None:
    client = boto3.client("sqs", region_name="eu-west-1")
    attributes = {"FifoQueue": "true"} if name.endswith(".fifo") else {}
    client.create_queue(QueueName=name, Attributes=attributes)


@mock_aws
def test_list_queues_returns_queues_in_api_order_unsorted() -> None:
    for name in ("gamma", "alpha", "beta"):
        _create_queue(name)

    page = _gateway().list_queues()

    assert [queue.name for queue in page.items] == ["gamma", "alpha", "beta"]
    assert page.next_token is None


@mock_aws
def test_list_queues_marks_fifo_queues() -> None:
    _create_queue("orders.fifo")
    _create_queue("orders")

    queues = _gateway().list_queues().items

    # moto's list_queues returns creation order, not alphabetical, and the gateway no longer
    # sorts; this test only cares about correct FIFO detection, so compare order-independently.
    assert {(queue.name, queue.is_fifo) for queue in queues} == {("orders", False), ("orders.fifo", True)}


@mock_aws
def test_list_queues_returns_empty_list_for_empty_region() -> None:
    assert _gateway().list_queues().items == ()


def test_list_queues_forwards_next_token() -> None:
    client = boto3.client("sqs", region_name="eu-west-1")
    with Stubber(client) as stubber:
        stubber.add_response(
            "list_queues",
            {"QueueUrls": ["https://sqs.eu-west-1.amazonaws.com/123456789012/alpha"], "NextToken": "t1"},
            {},
        )
        stubber.add_response(
            "list_queues", {"QueueUrls": ["https://sqs.eu-west-1.amazonaws.com/123456789012/beta"]}, {"NextToken": "t1"}
        )

        first = SqsGateway(client).list_queues()
        second = SqsGateway(client).list_queues(first.next_token)

    assert first.next_token == "t1"
    assert [queue.name for queue in second.items] == ["beta"]
    assert second.next_token is None


def test_to_summary_takes_name_from_last_url_segment() -> None:
    summary = _to_summary("https://sqs.eu-west-1.amazonaws.com/123456789012/orders")

    assert summary.name == "orders"
    assert summary.is_fifo is False


def test_to_summary_detects_fifo_suffix() -> None:
    summary = _to_summary("https://sqs.eu-west-1.amazonaws.com/123456789012/orders.fifo")

    assert summary.name == "orders.fifo"
    assert summary.is_fifo is True


def test_list_queues_maps_client_error_to_aws_error() -> None:
    client = boto3.client("sqs", region_name="eu-west-1")
    with Stubber(client) as stubber:
        stubber.add_client_error("list_queues", service_error_code="AccessDenied", service_message="Access Denied")

        with pytest.raises(AwsError) as excinfo:
            SqsGateway(client).list_queues()

    assert excinfo.value.message == "Access Denied"
