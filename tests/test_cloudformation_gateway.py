"""Tests for the CloudFormation gateway."""

from datetime import UTC, datetime
import json

import boto3
from moto import mock_aws

from awst.aws.cloudformation import CloudFormationGateway, _to_summary

TEMPLATE = json.dumps(
    {
        "Description": "a test stack",
        "Resources": {"Topic": {"Type": "AWS::SNS::Topic"}},
    }
)


def _gateway() -> CloudFormationGateway:
    return CloudFormationGateway(boto3.client("cloudformation", region_name="eu-west-1"))


@mock_aws
def test_list_stacks_returns_all_stacks_sorted_by_name() -> None:
    client = boto3.client("cloudformation", region_name="eu-west-1")
    for name in ("gamma", "alpha", "beta"):
        client.create_stack(StackName=name, TemplateBody=TEMPLATE)

    stacks = _gateway().list_stacks()

    assert [stack.name for stack in stacks] == ["alpha", "beta", "gamma"]


@mock_aws
def test_list_stacks_maps_fields() -> None:
    client = boto3.client("cloudformation", region_name="eu-west-1")
    client.create_stack(StackName="alpha", TemplateBody=TEMPLATE)

    stack = _gateway().list_stacks()[0]

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
