"""Utility for configuring logging."""
import logging
import os
from src.utils.config_loader import ConfigLoader

def setup_logging():
    """Configure logging for the application."""
    config_loader = ConfigLoader()
    config = config_loader.get_config()
    
    os.makedirs(config["LOG_DIR"], exist_ok=True)
    
    log_level = getattr(logging, config["LOG_LEVEL"].upper(), logging.INFO)
    
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(config["LOG_FILE"]),
            logging.StreamHandler()
        ]
    )
    logging.getLogger(__name__).info("Logging configured")