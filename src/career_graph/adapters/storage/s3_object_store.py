"""Object store over the S3 API (boto3). Built for MinIO, which runs as a separate container; works with any S3."""

from __future__ import annotations

import boto3
from botocore.exceptions import ClientError

from career_graph.application.ports import ObjectNotFound

_MISSING = {"404", "NoSuchKey", "NoSuchBucket", "NotFound"}


class S3ObjectStore:
    def __init__(self, endpoint_url: str, bucket: str, access_key: str, secret_key: str, region: str = "us-east-1") -> None:
        self._bucket = bucket
        self._s3 = boto3.client("s3", endpoint_url=endpoint_url, region_name=region,
                                aws_access_key_id=access_key, aws_secret_access_key=secret_key)
        try:
            self._s3.head_bucket(Bucket=bucket)
        except ClientError as error:
            if error.response["Error"]["Code"] not in _MISSING:
                raise
            # us-east-1 is the one region that must not be named in the request.
            config = {} if region == "us-east-1" else {"CreateBucketConfiguration": {"LocationConstraint": region}}
            self._s3.create_bucket(Bucket=bucket, **config)

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._s3.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> bytes:
        try:
            return self._s3.get_object(Bucket=self._bucket, Key=key)["Body"].read()
        except ClientError as error:
            if error.response["Error"]["Code"] in _MISSING:
                raise ObjectNotFound(key) from error
            raise

    def exists(self, key: str) -> bool:
        try:
            self._s3.head_object(Bucket=self._bucket, Key=key)
        except ClientError as error:
            if error.response["Error"]["Code"] in _MISSING:
                return False
            raise
        return True

    def delete(self, key: str) -> None:
        self._s3.delete_object(Bucket=self._bucket, Key=key)  # S3 deletes are already idempotent
