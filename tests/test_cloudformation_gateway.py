"""Tests for the CloudFormation gateway."""

from datetime import UTC, datetime
import json

import boto3
from botocore.stub import Stubber
from moto import mock_aws
import pytest

from awst.aws.cloudformation import CloudFormationGateway, _to_summary
from awst.aws.models import StackNotFoundError, StackParameter

TEMPLATE = json.dumps(
    {
        "Description": "a test stack",
        "Resources": {"Topic": {"Type": "AWS::SNS::Topic"}},
    }
)

DETAIL_TEMPLATE = json.dumps(
    {
        "Description": "a detailed stack",
        "Parameters": {"Env": {"Type": "String"}},
        "Resources": {"Topic": {"Type": "AWS::SNS::Topic"}},
        "Outputs": {"TopicName": {"Value": {"Ref": "Topic"}, "Description": "the topic"}},
    }
)


def _gateway() -> CloudFormationGateway:
    return CloudFormationGateway(boto3.client("cloudformation", region_name="eu-west-1"))


def _create_detailed_stack() -> None:
    client = boto3.client("cloudformation", region_name="eu-west-1")
    client.create_stack(
        StackName="alpha",
        TemplateBody=DETAIL_TEMPLATE,
        Parameters=[{"ParameterKey": "Env", "ParameterValue": "prod"}],
    )


@mock_aws
def test_list_stacks_returns_stacks_in_api_order_unsorted() -> None:
    client = boto3.client("cloudformation", region_name="eu-west-1")
    for name in ("gamma", "alpha", "beta"):
        client.create_stack(StackName=name, TemplateBody=TEMPLATE)

    page = _gateway().list_stacks()

    assert [stack.name for stack in page.items] == ["gamma", "alpha", "beta"]
    assert page.next_token is None


@mock_aws
def test_list_stacks_maps_fields() -> None:
    client = boto3.client("cloudformation", region_name="eu-west-1")
    client.create_stack(StackName="alpha", TemplateBody=TEMPLATE)

    stack = _gateway().list_stacks().items[0]

    assert stack.name == "alpha"
    assert stack.status == "CREATE_COMPLETE"
    assert stack.description == "a test stack"
    assert stack.created.tzinfo is not None
    assert stack.updated == stack.created  # never updated -> falls back to creation time


def test_to_summary_uses_last_updated_time_when_present() -> None:
    created = datetime(2026, 1, 1, tzinfo=UTC)
    updated = datetime(2026, 2, 2, tzinfo=UTC)

    summary = _to_summary(
        {
            "StackName": "alpha",
            "StackStatus": "UPDATE_COMPLETE",
            "CreationTime": created,
            "LastUpdatedTime": updated,
        }
    )

    assert summary.created == created
    assert summary.updated == updated
    assert summary.description is None


@mock_aws
def test_get_stack_detail_maps_overview_fields() -> None:
    _create_detailed_stack()

    detail = _gateway().get_stack_detail("alpha")

    assert detail.name == "alpha"
    assert detail.status == "CREATE_COMPLETE"
    assert detail.description == "a detailed stack"
    assert detail.stack_id.startswith("arn:")
    assert detail.created.tzinfo is not None
    assert detail.updated == detail.created


@mock_aws
def test_get_stack_detail_maps_parameters_and_outputs() -> None:
    _create_detailed_stack()

    detail = _gateway().get_stack_detail("alpha")

    assert detail.parameters == (StackParameter(key="Env", value="prod"),)
    assert len(detail.outputs) == 1
    assert detail.outputs[0].key == "TopicName"
    assert detail.outputs[0].description == "the topic"


@mock_aws
def test_get_stack_detail_lists_resources() -> None:
    _create_detailed_stack()

    detail = _gateway().get_stack_detail("alpha")

    assert len(detail.resources) == 1
    resource = detail.resources[0]
    assert resource.logical_id == "Topic"
    assert resource.resource_type == "AWS::SNS::Topic"
    assert resource.status == "CREATE_COMPLETE"


@mock_aws
def test_get_stack_detail_returns_events_newest_first() -> None:
    _create_detailed_stack()

    detail = _gateway().get_stack_detail("alpha")

    assert detail.events
    timestamps = [event.timestamp for event in detail.events]
    assert timestamps == sorted(timestamps, reverse=True)
    assert detail.events[0].logical_id
    assert detail.events[0].status


@mock_aws
def test_get_stack_detail_raises_stack_not_found_for_missing_stack() -> None:
    with pytest.raises(StackNotFoundError):
        _gateway().get_stack_detail("missing")


@mock_aws
def test_delete_stack_deletes_the_stack() -> None:
    client = boto3.client("cloudformation", region_name="eu-west-1")
    client.create_stack(StackName="alpha", TemplateBody=TEMPLATE)

    _gateway().delete_stack("alpha")

    assert _gateway().list_stacks().items == ()


def test_list_stacks_forwards_next_token() -> None:
    client = boto3.client("cloudformation", region_name="eu-west-1")
    created = datetime(2026, 1, 1, tzinfo=UTC)
    with Stubber(client) as stubber:
        stubber.add_response(
            "describe_stacks",
            {
                "Stacks": [{"StackName": "alpha", "StackStatus": "CREATE_COMPLETE", "CreationTime": created}],
                "NextToken": "t1",
            },
            {},
        )
        stubber.add_response(
            "describe_stacks",
            {"Stacks": [{"StackName": "beta", "StackStatus": "CREATE_COMPLETE", "CreationTime": created}]},
            {"NextToken": "t1"},
        )

        first = CloudFormationGateway(client).list_stacks()
        second = CloudFormationGateway(client).list_stacks(first.next_token)

    assert first.next_token == "t1"
    assert [stack.name for stack in second.items] == ["beta"]
    assert second.next_token is None
