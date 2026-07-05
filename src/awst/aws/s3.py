"""Gateway to the S3 API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from botocore.exceptions import BotoCoreError, ClientError

from awst.aws.errors import map_botocore_error
from awst.aws.models import BucketSummary

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client
    from mypy_boto3_s3.type_defs import BucketTypeDef


class S3Gateway:
    """Access to S3, returning plain data models."""

    def __init__(self: Self, client: S3Client) -> None:
        self._client = client

    def list_buckets(self: Self) -> list[BucketSummary]:
        """Return every bucket in the account, sorted by name.

        Raises AwsError for any credential, network, or API failure.
        """
        try:
            paginator = self._client.get_paginator("list_buckets")
            buckets = [_to_summary(bucket) for page in paginator.paginate() for bucket in page["Buckets"]]
        except (BotoCoreError, ClientError) as error:
            raise map_botocore_error(error) from error
        return sorted(buckets, key=lambda bucket: bucket.name)


def _to_summary(bucket: BucketTypeDef) -> BucketSummary:
    return BucketSummary(
        name=bucket["Name"],
        region=bucket.get("BucketRegion", ""),
        created=bucket["CreationDate"],
    )
