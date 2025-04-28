"""Utility for loading configurations."""
import logging
from src.config.app_config import *
from src.config.collection_config import COLLECTION_CONFIG

logger = logging.getLogger(__name__)

class ConfigLoader:
    """Loads and provides access to project configurations."""
    def get_config(self):
        """Get application configuration.

        Returns:
            dict: Configuration dictionary.
        """
        try:
            config = {
                "RETRY_MAX_ATTEMPTS": RETRY_MAX_ATTEMPTS,
                "RETRY_BACKOFF_FACTOR": RETRY_BACKOFF_FACTOR,
                "RETRY_STATUS_FORCELIST": RETRY_STATUS_FORCELIST,
                "CACHE_DIR": CACHE_DIR,
                "CACHE_MAX_SIZE": CACHE_MAX_SIZE,
                "CACHE_EXPIRY_DAYS": CACHE_EXPIRY_DAYS,
                "LOG_DIR": LOG_DIR,
                "LOG_FILE": LOG_FILE,
                "LOG_LEVEL": LOG_LEVEL,
                "SYMPTOM_DRUGS": SYMPTOM_DRUGS,
                "VALID_SYMPTOMS": VALID_SYMPTOMS,
                "SSL_VERIFY": SSL_VERIFY,
                "AGENT_CLASSES": AGENT_CLASSES,
                "INPUT_FIELDS": INPUT_FIELDS
            }
            logger.debug("Loaded application configuration")
            return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise

    def get_collection_config(self):
        """Get collection configuration.

        Returns:
            dict: Collection configuration dictionary.
        """
        try:
            logger.debug("Loaded collection configuration")
            return COLLECTION_CONFIG
        except Exception as e:
            logger.error(f"Failed to load collection config: {e}")
            raise