"""Local file storage implementation.

This module provides local file storage as an S3 equivalent for local development.
Weather responses are saved as JSON files with timestamped filenames.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles

from app.services.base import BaseStorage

logger = logging.getLogger(__name__)


class LocalFileStorage(BaseStorage):
    """Local file storage implementation (S3 equivalent for local development).

    Files are stored as JSON in the configured data directory.

    Example:
        storage = LocalFileStorage(data_dir=Path("./data"))
        key = storage.generate_weather_key("London")
        path = await storage.save(weather_data, key)
    """

    def __init__(self, data_dir: Path):
        """Initialize storage.

        Args:
            data_dir: Directory for storing files
        """
        self._data_dir = data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"LocalFileStorage initialized with data_dir: {self._data_dir}")

    @property
    def data_dir(self) -> Path:
        """Get the data directory path."""
        return self._data_dir

    def _get_full_path(self, key: str) -> Path:
        """Get full filesystem path for a key."""
        # Handle nested paths like "weather/london_123.json"
        return self._data_dir / key

    async def save(self, data: dict[str, Any], key: str) -> str:
        """Save data to a JSON file."""
        file_path = self._get_full_path(key)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            json_str = json.dumps(data, indent=2, default=str)
            await f.write(json_str)

        logger.info(f"Saved data to: {file_path}")
        return str(file_path)

    async def load(self, key: str) -> dict[str, Any] | None:
        """Load data from a JSON file."""
        file_path = self._get_full_path(key)

        if not file_path.exists():
            logger.debug(f"File not found: {file_path}")
            return None

        try:
            async with aiofiles.open(file_path, encoding="utf-8") as f:
                content = await f.read()
                return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from {file_path}: {e}")
            return None

    async def delete(self, key: str) -> bool:
        """Delete a file from storage."""
        file_path = self._get_full_path(key)

        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted file: {file_path}")
            return True

        logger.debug(f"File not found for deletion: {file_path}")
        return False

    async def list_keys(self, prefix: str = "") -> list[str]:
        """List all JSON files in storage."""
        keys = []
        search_dir = self._data_dir

        # If prefix contains directory, adjust search
        if "/" in prefix:
            prefix_path = self._data_dir / prefix.rsplit("/", 1)[0]
            if prefix_path.exists():
                search_dir = prefix_path

        for file_path in search_dir.rglob("*.json"):
            rel_path = str(file_path.relative_to(self._data_dir))
            if prefix and not rel_path.startswith(prefix):
                continue
            keys.append(rel_path)

        return sorted(keys)

    async def save_weather(
        self, data: dict[str, Any], city: str, timestamp: datetime | None = None
    ) -> str:
        """Convenience method to save weather data with auto-generated key."""
        key = self.generate_weather_key(city, timestamp)
        return await self.save(data, key)
