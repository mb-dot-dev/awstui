"""Gateway to the S3 API."""

from typing import TYPE_CHECKING, Self

from botocore.exceptions import BotoCoreError, ClientError

from awst.aws.errors import map_botocore_error
from awst.aws.models import AwsError, BucketSummary

if TYPE_CHECKING:
    from collections.abc import Iterator

    from mypy_boto3_s3 import S3Client
    from mypy_boto3_s3.type_defs import BucketTypeDef, ObjectIdentifierTypeDef


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

    def empty_bucket(self: Self, name: str) -> Iterator[int]:
        """Delete every object version and delete marker in the bucket.

        Yields the cumulative deleted-object count after each batch of up to
        1000 keys; an already-empty bucket yields nothing. Raises AwsError for
        any credential, network, or API failure, including per-key failures
        reported by DeleteObjects.
        """
        deleted = 0
        try:
            while True:
                paginator = self._client.get_paginator("list_object_versions")
                has_items = False
                for page in paginator.paginate(Bucket=name, PaginationConfig={"PageSize": 1000}):
                    items = [*page.get("Versions", []), *page.get("DeleteMarkers", [])]
                    keys: list[ObjectIdentifierTypeDef] = [
                        {"Key": item["Key"], "VersionId": item["VersionId"]} for item in items
                    ]
                    if not keys:
                        continue
                    has_items = True
                    self._delete_batch(name, keys)
                    deleted += len(keys)
                    yield deleted
                    break
                if not has_items:
                    break
        except (BotoCoreError, ClientError) as error:
            raise map_botocore_error(error) from error

    def _delete_batch(self: Self, name: str, keys: list[ObjectIdentifierTypeDef]) -> None:
        response = self._client.delete_objects(Bucket=name, Delete={"Objects": keys, "Quiet": True})
        errors = response.get("Errors", [])
        if errors:
            first = errors[0]
            reason = first.get("Message", first.get("Code", "unknown error"))
            message = f"Could not delete {first.get('Key', 'an object')}: {reason}"
            raise AwsError(message)


def _to_summary(bucket: BucketTypeDef) -> BucketSummary:
    return BucketSummary(
        name=bucket["Name"],
        region=bucket.get("BucketRegion", ""),
        created=bucket["CreationDate"],
    )
