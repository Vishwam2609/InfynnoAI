from termcolor import colored
import re

class DrugDosageAgent:
    def __init__(self, rag_client):
        self.rag_client = rag_client

    def get_dosage(self, drug_name, symptom, age_group):
        query_text = f"{drug_name} {symptom} {age_group} dosage"
        query_vec = self.rag_client.embed([query_text])[0]
        
        filters = {
            "drugName": drug_name.lower(),
            "symptom": symptom.lower(),
            "ageGroup": age_group.lower()
        }
        
        result = self.rag_client.query_data(
            collection_name="DrugDosage",
            query_text=query_text,
            query_vec=query_vec,
            return_properties=["drugName", "symptom", "ageGroup", "dosage"],
            filters=filters
        )
        
        if result:
            dosage = result[0].properties.get("dosage", "")
            return dosage
        
        scraped_html = self.rag_client.scrape_drug_data(drug_name)
        dosage_info = self.rag_client.extract_dosage_info(scraped_html, symptom, age_group, drug_name)
        
        properties = {
            "drugName": drug_name.lower(),
            "symptom": symptom.lower(),
            "ageGroup": age_group.lower(),
            "dosage": dosage_info
        }
        
        success = self.rag_client.insert_data("DrugDosage", properties, query_vec)
        if success:
            print(f"Stored dosage for {drug_name.lower()} in Weaviate.")
        return dosage_info

    def extract_relevant_dosage(self, drug_name, dosage_text, weight, age):
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