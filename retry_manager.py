import time
import functools
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Callable, Optional, List

class RetryManager:
    def __init__(self, max_attempts: int = 3, backoff_factor: float = 0.2, status_forcelist: Optional[List[int]] = None):
        """
        Initialize the RetryManager for handling retries with exponential backoff.
        
        Args:
            max_attempts: Maximum number of retry attempts.
            backoff_factor: Factor for exponential backoff (delay = backoff_factor * 2^attempt).
            status_forcelist: List of HTTP status codes to retry (e.g., [502, 503, 504, 429]).
        """
        self.max_attempts = max_attempts
        self.backoff_factor = backoff_factor
        self.status_forcelist = status_forcelist or [502, 503, 504, 429]

    def retry(self, func: Callable) -> Callable:
        """
        Decorator to retry a function with exponential backoff.
        
        Args:
            func: The function to wrap with retry logic.
        
        Returns:
            Wrapped function that retries on failure.
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
                        raise Exception(f"{func.__name__} failed after {self.max_attempts} attempts: {e}")
                    delay = self.backoff_factor * (2 ** attempt)
                    time.sleep(delay)
            raise last_exception  # This line should never be reached
        return wrapper

    def configure_session(self, session: requests.Session) -> None:
        """
        Configure a requests Session with retry settings for HTTP requests.
        
        Args:
            session: The requests Session to configure.
        """
        retries = Retry(
            total=self.max_attempts,
            backoff_factor=self.backoff_factor,
            status_forcelist=self.status_forcelist
        )
        session.mount('http://', HTTPAdapter(max_retries=retries))
        session.mount('https://', HTTPAdapter(max_retries=retries))