"""LRU cache implementation for reusable caching."""
import json
import os
import time
import logging
from collections import OrderedDict

logger = logging.getLogger(__name__)

class LRUCache:
    """LRU cache with expiration for managing cached data."""
    def __init__(self, max_size, expiry_days):
        """Initialize the LRU cache.

        Args:
            max_size (int): Maximum number of entries.
            expiry_days (int): Expiration time in days.
        """
        self.cache = OrderedDict()
        self.max_size = max_size
        self.expiry_seconds = expiry_days * 24 * 60 * 60
        self.timestamps = {}

    def get(self, key):
        """Get an item from the cache.

        Args:
            key: Cache key.

        Returns:
            Value if found and not expired, else None.
        """
        if key in self.cache:
            if time.time() - self.timestamps[key] < self.expiry_seconds:
                self.cache.move_to_end(key)
                return self.cache[key]
            else:
                del self.cache[key]
                del self.timestamps[key]
        return None

    def put(self, key, value):
        """Put an item in the cache.

        Args:
            key: Cache key.
            value: Value to store.
        """
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        self.timestamps[key] = time.time()
        if len(self.cache) > self.max_size:
            self.cache.popitem(last=False)
            del self.timestamps[list(self.timestamps.keys())[0]]

    def save(self, file_path):
        """Save cache to file.

        Args:
            file_path (str): Path to save the cache.
        """
        try:
            with open(file_path, 'w') as f:
                json.dump(self.cache, f)
            logger.info(f"Saved cache to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save cache to {file_path}: {e}")

    def load(self, file_path):
        """Load cache from file.

        Args:
            file_path (str): Path to load the cache from.
        """
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    data = json.load(f)
                for key, value in data.items():
                    self.put(key, value)
                logger.info(f"Loaded cache from {file_path} with {len(self.cache)} entries")
        except Exception as e:
            logger.error(f"Failed to load cache from {file_path}: {e}")