"""Retry manager for handling transient failures."""
import time
import functools
import requests
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Callable, Optional, List
from src.utils.config_loader import ConfigLoader

logger = logging.getLogger(__name__)

class RetryManager:
    """Manages retries with exponential backoff for operations."""
    def __init__(self, max_attempts: Optional[int] = None, 
                 backoff_factor: Optional[float] = None, 
                 status_forcelist: Optional[List[int]] = None):
        """Initialize the RetryManager.

        Args:
            max_attempts (int, optional): Maximum retry attempts.
            backoff_factor (float, optional): Factor for exponential backoff.
            status_forcelist (List[int], optional): HTTP status codes to retry.
        """
        config = ConfigLoader().get_config()
        self.max_attempts = max_attempts or config["RETRY_MAX_ATTEMPTS"]
        self.backoff_factor = backoff_factor or config["RETRY_BACKOFF_FACTOR"]
        self.status_forcelist = status_forcelist or config["RETRY_STATUS_FORCELIST"]

    def retry(self, func: Callable) -> Callable:
        """Decorator to retry a function with exponential backoff.

        Args:
            func: Function to wrap with retry logic.

        Returns:
            Callable: Wrapped function.
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(self.max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt == self.max_attempts - 1:
                        logger.error(f"{func.__name__} failed after {self.max_attempts} attempts: {e}")
                        raise
                    delay = self.backoff_factor * (2 ** attempt)
                    logger.debug(f"Retrying {func.__name__} after {delay}s")
                    time.sleep(delay)
            raise last_exception
        return wrapper

    def configure_session(self, session: requests.Session) -> None:
        """Configure a requests Session with retry settings.

        Args:
            session: Requests Session to configure.
        """
        retries = Retry(
            total=self.max_attempts,
            backoff_factor=self.backoff_factor,
            status_forcelist=self.status_forcelist
        )
        session.mount('http://', HTTPAdapter(max_retries=retries))
        session.mount('https://', HTTPAdapter(max_retries=retries))