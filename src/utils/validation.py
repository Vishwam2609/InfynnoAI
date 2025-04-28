"""Utilities for input validation and sanitization."""
import re
import logging

logger = logging.getLogger(__name__)

def sanitize_input(text):
    """Sanitize input to remove potentially malicious characters.

    Args:
        text (str): Input text to sanitize.

    Returns:
        str: Sanitized text.
    """
    sanitized = re.sub(r'[^a-zA-Z0-9\s.,-]', '', text.strip())
    logger.debug(f"Sanitized input: {text} -> {sanitized}")
    return sanitized

def restrict_numeric(value, min_val, max_val):
    """Restrict a numeric input to a specified range.

    Args:
        value (str): Input value to convert and restrict.
        min_val (float): Minimum allowed value.
        max_val (float): Maximum allowed value.

        Returns:
            float: Validated number or None if invalid.
    """
    try:
        num = float(value)
        if min_val <= num <= max_val:
            return num
        logger.warning(f"Value {num} out of range [{min_val}, {max_val}]")
        return None
    except ValueError:
        logger.warning(f"Invalid numeric value: {value}")
        return None