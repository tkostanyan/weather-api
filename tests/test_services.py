"""Unit tests for service modules."""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.models.weather import WeatherSummary
from app.services.cache import InMemoryCache
from app.services.cache.memory_cache import CacheEntry
from app.services.storage import LocalFileStorage


class TestInMemoryCache:
    """Tests for the InMemoryCache class."""

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self, cache: InMemoryCache):
        """Test basic set and get operations."""
        await cache.set("test_key", "test_value")
        result = await cache.get("test_key")
        assert result == "test_value"

    @pytest.mark.asyncio
    async def test_cache_miss(self, cache: InMemoryCache):
        """Test cache miss returns None."""
        result = await cache.get("nonexistent_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_expiry(self):
        """Test that cached items expire after TTL."""
        cache = InMemoryCache(ttl_seconds=1)
        await cache.set("expiring_key", "value")

        # Should exist immediately
        result = await cache.get("expiring_key")
        assert result == "value"

        # Wait for expiry
        await asyncio.sleep(1.1)

        # Should be expired now
        result = await cache.get("expiring_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_delete(self, cache: InMemoryCache):
        """Test cache deletion."""
        await cache.set("to_delete", "value")
        assert await cache.get("to_delete") == "value"

        deleted = await cache.delete("to_delete")
        assert deleted is True

        result = await cache.get("to_delete")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_delete_nonexistent(self, cache: InMemoryCache):
        """Test deleting nonexistent key."""
        deleted = await cache.delete("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_cache_clear(self, cache: InMemoryCache):
        """Test clearing all cache entries."""
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")

        count = await cache.clear()
        assert count == 2

        assert await cache.get("key1") is None
        assert await cache.get("key2") is None

    @pytest.mark.asyncio
    async def test_cache_stats(self, cache: InMemoryCache):
        """Test cache statistics."""
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")

        stats = await cache.stats()
        assert stats["total_entries"] == 2
        assert stats["valid_entries"] == 2
        assert stats["expired_entries"] == 0

    @pytest.mark.asyncio
    async def test_cache_cleanup_expired(self):
        """Test cleanup of expired entries."""
        cache = InMemoryCache(ttl_seconds=1)
        await cache.set("expiring", "value")
        await cache.set("also_expiring", "value2")

        await asyncio.sleep(1.1)

        removed = await cache.cleanup_expired()
        assert removed == 2

    @pytest.mark.asyncio
    async def test_cache_with_weather_summary(
        self, cache: InMemoryCache, weather_summary_model: WeatherSummary
    ):
        """Test caching WeatherSummary objects."""
        await cache.set("london", weather_summary_model)

        result = await cache.get("london")
        assert result is not None


class TestCacheEntry:
    """Tests for the CacheEntry class."""

    def test_cache_entry_creation(self):
        """Test CacheEntry creation."""
        entry = CacheEntry("test_value")
        assert entry.value == "test_value"
        assert entry.created_at is not None

    def test_cache_entry_not_expired(self):
        """Test entry is not expired immediately."""
        entry = CacheEntry("value")
        assert entry.is_expired(300) is False

    def test_cache_entry_expired(self):
        """Test entry expiration detection."""
        entry = CacheEntry("value", created_at=datetime.utcnow() - timedelta(seconds=400))
        assert entry.is_expired(300) is True

    def test_cache_entry_age(self):
        """Test entry age calculation."""
        past_time = datetime.utcnow() - timedelta(seconds=100)
        entry = CacheEntry("value", created_at=past_time)

        age = entry.age_seconds()
        assert 99 <= age <= 101  # Allow for small timing differences


class TestLocalFileStorage:
    """Tests for the LocalFileStorage class."""

    @pytest.mark.asyncio
    async def test_save_and_load(self, storage: LocalFileStorage):
        """Test saving and loading data."""
        data = {"city": "London", "temp": 15.5}

        path = await storage.save(data, "test_file.json")
        assert Path(path).exists()

        loaded = await storage.load("test_file.json")
        assert loaded == data

    @pytest.mark.asyncio
    async def test_save_weather(
        self, storage: LocalFileStorage, weather_summary_model: WeatherSummary
    ):
        """Test saving weather data with auto-generated filename."""
        data = weather_summary_model.model_dump(mode="json")

        path = await storage.save_weather(data, "London")

        assert Path(path).exists()
        assert "london_" in path.lower()
        assert path.endswith(".json")

    @pytest.mark.asyncio
    async def test_load_nonexistent(self, storage: LocalFileStorage):
        """Test loading nonexistent file returns None."""
        result = await storage.load("nonexistent.json")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_keys(self, storage: LocalFileStorage):
        """Test listing files."""
        await storage.save({"data": 1}, "file1.json")
        await storage.save({"data": 2}, "file2.json")

        files = await storage.list_keys()
        assert "file1.json" in files
        assert "file2.json" in files

    @pytest.mark.asyncio
    async def test_delete_file(self, storage: LocalFileStorage):
        """Test file deletion."""
        await storage.save({"data": 1}, "to_delete.json")

        deleted = await storage.delete("to_delete.json")
        assert deleted is True

        result = await storage.load("to_delete.json")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, storage: LocalFileStorage):
        """Test deleting nonexistent file."""
        deleted = await storage.delete("nonexistent.json")
        assert deleted is False
