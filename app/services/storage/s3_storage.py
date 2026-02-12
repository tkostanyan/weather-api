"""AWS S3 storage implementation.

This module provides S3 storage for production deployment.
Uses aioboto3 for async S3 operations.
"""

import json
import logging
from datetime import datetime
from typing import Any

from app.services.base import BaseStorage

logger = logging.getLogger(__name__)


class S3Storage(BaseStorage):
    """AWS S3 storage implementation for production.

    Example:
        storage = S3Storage(
            bucket_name="weather-data-bucket",
            region="us-east-1",
            aws_access_key_id="...",
            aws_secret_access_key="..."
        )
        key = storage.generate_weather_key("London")
        url = await storage.save(weather_data, key)
    """

    def __init__(
        self,
        bucket_name: str,
        region: str = "us-east-1",
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        endpoint_url: str | None = None,  # For LocalStack testing
    ):
        """Initialize S3 storage.

        Args:
            bucket_name: S3 bucket name
            region: AWS region
            aws_access_key_id: AWS access key (optional, uses default credentials if not provided)
            aws_secret_access_key: AWS secret key
            endpoint_url: Custom endpoint URL (for LocalStack or testing)
        """
        self._bucket_name = bucket_name
        self._region = region
        self._aws_access_key_id = aws_access_key_id
        self._aws_secret_access_key = aws_secret_access_key
        self._endpoint_url = endpoint_url
        self._client = None

        logger.info(f"S3Storage initialized with bucket: {bucket_name}, region: {region}")

    async def _get_client(self):
        """Get or create the S3 client."""
        if self._client is None:
            try:
                import aioboto3
            except ImportError:
                raise ImportError(
                    "aioboto3 is required for S3 storage. Install it with: pip install aioboto3"
                )

            session = aioboto3.Session()

            client_kwargs = {
                "region_name": self._region,
            }

            if self._aws_access_key_id:
                client_kwargs["aws_access_key_id"] = self._aws_access_key_id
            if self._aws_secret_access_key:
                client_kwargs["aws_secret_access_key"] = self._aws_secret_access_key
            if self._endpoint_url:
                client_kwargs["endpoint_url"] = self._endpoint_url

            self._client = await session.client("s3", **client_kwargs).__aenter__()

        return self._client

    async def close(self):
        """Close the S3 client."""
        if self._client:
            await self._client.__aexit__(None, None, None)
            self._client = None

    async def save(self, data: dict[str, Any], key: str) -> str:
        """Save data to S3."""
        client = await self._get_client()

        json_str = json.dumps(data, indent=2, default=str)

        await client.put_object(
            Bucket=self._bucket_name,
            Key=key,
            Body=json_str.encode("utf-8"),
            ContentType="application/json",
        )

        url = f"s3://{self._bucket_name}/{key}"
        logger.info(f"Saved data to S3: {url}")
        return url

    async def load(self, key: str) -> dict[str, Any] | None:
        """Load data from S3."""
        client = await self._get_client()

        try:
            response = await client.get_object(
                Bucket=self._bucket_name,
                Key=key,
            )
            content = await response["Body"].read()
            return json.loads(content.decode("utf-8"))
        except client.exceptions.NoSuchKey:
            logger.debug(f"Key not found in S3: {key}")
            return None
        except Exception as e:
            logger.error(f"Error loading from S3: {e}")
            return None

    async def delete(self, key: str) -> bool:
        """Delete an object from S3."""
        client = await self._get_client()

        try:
            await client.delete_object(
                Bucket=self._bucket_name,
                Key=key,
            )
            logger.info(f"Deleted from S3: {key}")
            return True
        except Exception as e:
            logger.error(f"Error deleting from S3: {e}")
            return False

    async def list_keys(self, prefix: str = "") -> list[str]:
        """List all keys in the bucket with optional prefix."""
        client = await self._get_client()

        keys = []
        paginator = client.get_paginator("list_objects_v2")

        async for page in paginator.paginate(
            Bucket=self._bucket_name,
            Prefix=prefix,
        ):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])

        return sorted(keys)

    async def save_weather(
        self, data: dict[str, Any], city: str, timestamp: datetime | None = None
    ) -> str:
        """Convenience method to save weather data with auto-generated key."""
        key = self.generate_weather_key(city, timestamp)
        return await self.save(data, key)
