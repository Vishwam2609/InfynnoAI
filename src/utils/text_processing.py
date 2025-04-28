"""Utilities for processing text data."""
import re
import logging

logger = logging.getLogger(__name__)

class TextProcessor:
    """Handles text extraction and summarization tasks."""
    def extract_pattern(self, text, pattern, default=None):
        """Extract text matching a regex pattern.

        Args:
            text (str): Input text.
            pattern (str): Regex pattern.
            default (str, optional): Default value if no match.

        Returns:
            str: Matched text or default.
        """
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)
        logger.debug(f"No match for pattern '{pattern}' in text: {text[:50]}...")
        return default or text

    def extract_dose_frequency(self, dosage_line):
        """Extract concise dosage and frequency from dosage text.

        Args:
            dosage_line (str): Raw dosage text.

        Returns:
            str: Concise dosage and frequency or original text.
        """
        pattern = r'(\d+\s*(?:to\s*\d+\s*)?(?:mg|ml)).*?(every\s*\d+\s*(?:to\s*\d+\s*)?hours.*?not to exceed\s*\d+\s*doses\s*in\s*24\s*hours)'
        match = re.search(pattern, dosage_line, re.IGNORECASE)
        if match:
            dose = match.group(1)
            freq = match.group(2)
            freq = freq.replace("not to exceed", "max")
            freq = re.sub(r'in\s*24\s*hours', 'day', freq, flags=re.IGNORECASE)
            return f"{dose} {freq}"
        logger.debug(f"No dose frequency match for: {dosage_line}")
        return dosage_line

    def summarize_interaction(self, interaction_text, drug_name):
        """Summarize interaction information.

        Args:
            interaction_text (str): Raw interaction text.
            drug_name (str): Name of the drug.

        Returns:
            str: Summarized interaction or default message.
        """
        if "no food/alcohol interactions found" in interaction_text.lower():
            return "No interactions."
        summary = []
        if "alcohol" in interaction_text.lower():
            if "acetaminophen" in drug_name.lower():
                summary.append("Avoid alcohol; liver risk.")
            elif "ibuprofen" in drug_name.lower() or "aspirin" in drug_name.lower():
                summary.append("Avoid alcohol; stomach bleeding.")
            else:
                summary.append("Avoid alcohol; sedation risk.")
        if "high blood pressure" in interaction_text.lower() or "hypertension" in interaction_text.lower():
            summary.append("Use cautiously with hypertension.")
        result = " ".join(summary) if summary else "Check with doctor."
        logger.debug(f"Interaction summary for {drug_name}: {result}")
        return result