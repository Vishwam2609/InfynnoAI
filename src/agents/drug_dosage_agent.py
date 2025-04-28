"""Agent for retrieving and processing drug dosage information."""
import re
import logging
from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

class DrugDosageAgent(BaseAgent):
    """Handles retrieval and extraction of drug dosage information."""
    def __init__(self, rag_client):
        """Initialize with a RAG client.

        Args:
            rag_client: RAGClient instance for database and scraping operations.
        """
        super().__init__(rag_client, "DrugDosage")

    def get_dosage(self, drug_name, symptom, age_group):
        """Retrieve dosage information for a drug, symptom, and age group.

        Args:
            drug_name (str): Name of the drug.
            symptom (str): Symptom being treated.
            age_group (str): Age group ('adult' or 'pediatric').

        Returns:
            str: Dosage information or error message.
        """
        query_params = {
            "drugName": drug_name,
            "symptom": symptom,
            "ageGroup": age_group
        }
        return self.retrieve_data(query_params)

    def process_data(self, drug_name, dosage_text, weight, age):
        """Extract specific dosage details based on weight and age.

        Args:
            drug_name (str): Name of the drug.
            dosage_text (str): Raw dosage information.
            weight (float): Patient weight in kg (optional).
            age (float): Patient age in years.

        Returns:
            str: Extracted dosage or error message.
        """
        if not dosage_text or "no dosage" in dosage_text.lower():
            return f"No dosage information available for {drug_name}."
        
        lines = [line.strip() for line in dosage_text.split('\n') if line.strip()]
        age_group = "pediatric" if age < 18 else "adult"
        weight_kg = weight if weight is not None else -1
        
        if age_group == "pediatric" and weight_kg > 0:
            for line in lines:
                mg_kg_match = re.search(r'(\d+\s*to\s*\d+\s*mg/kg|\d+\s*mg/kg)', line, re.IGNORECASE)
                if mg_kg_match:
                    dose_str = mg_kg_match.group(1)
                    doses = [float(d) for d in re.findall(r'\d+', dose_str)]
                    if len(doses) == 1:
                        calc_dose = int(doses[0] * weight_kg)
                        dose_range = f"{calc_dose} mg"
                    else:
                        calc_low, calc_high = int(doses[0] * weight_kg), int(doses[1] * weight_kg)
                        dose_range = f"{calc_low} to {calc_high} mg"
                    frequency_match = re.search(r'(every\s*\d+\s*to\s*\d+\s*hours|every\s*\d+\s*hours)', line, re.IGNORECASE)
                    max_match = re.search(r'(not to exceed\s*\d+\s*doses\s*in\s*24\s*hours)', line, re.IGNORECASE)
                    frequency = frequency_match.group(1) if frequency_match else "as needed"
                    max_limit = max_match.group(1) if max_match else ""
                    return f"{dose_range} {frequency} {max_limit}".strip()
        
        for line in lines:
            if age_group == "adult" or weight_kg <= 0:
                match = re.search(r'(\d+\s*(?:to\s*\d+\s*)?(?:mg|ml)).*?(every\s*\d+\s*(?:to\s*\d+\s*)?hours.*?not to exceed\s*\d+\s*doses\s*in\s*24\s*hours)', line, re.IGNORECASE)
                if match:
                    return match.group(0)
        
        return f"No specific dosage found for {drug_name} at age {age}."