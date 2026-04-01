"""
AWS S3 implementation for the StoragePort.
"""
from __future__ import annotations

import aioboto3

from workflow_engine.ports import StoragePort


class S3StorageService(StoragePort):
    """
    AWS S3 backed Storage service using aioboto3.
    Requires AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY to be set in env or AWS profiles.
    
    Args:
        bucket_name: The S3 bucket name.
        region_name: The AWS region.
    """

    def __init__(self, bucket_name: str, region_name: str = "us-east-1") -> None:
        self._bucket = bucket_name
        self._region = region_name
        self._session = aioboto3.Session()

    async def upload(self, tenant_id: str, path: str, data: bytes) -> str:
        """
        Upload data and return the object URI.
        Always prefixes the path with tenant_id for strict isolation.
        """
        key = f"{tenant_id}/{path.lstrip('/')}"
        async with self._session.client("s3", region_name=self._region) as s3:
            await s3.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
            )
        return f"s3://{self._bucket}/{key}"

    async def download(self, tenant_id: str, path: str) -> bytes:
        """Download remote object bytes."""
        # Prevent absolute paths or relative traversals skipping the tenant scope
        clean_path = path.replace("s3://", "").replace(f"{self._bucket}/", "", 1)
        if clean_path.startswith(f"{tenant_id}/"):
            key = clean_path
        else:
            key = f"{tenant_id}/{clean_path.lstrip('/')}"
            
        async with self._session.client("s3", region_name=self._region) as s3:
            response = await s3.get_object(Bucket=self._bucket, Key=key)
            body = await response["Body"].read()
            return body

    async def presign_url(self, tenant_id: str, path: str, expires_in: int = 3600) -> str:
        """Generate a temporary presigned GET URL."""
        clean_path = path.replace("s3://", "").replace(f"{self._bucket}/", "", 1)
        if clean_path.startswith(f"{tenant_id}/"):
            key = clean_path
        else:
            key = f"{tenant_id}/{clean_path.lstrip('/')}"
            
        async with self._session.client("s3", region_name=self._region) as s3:
            url = await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_in
            )
            return url
