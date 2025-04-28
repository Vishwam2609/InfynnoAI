"""Configuration for Weaviate collections and agent behavior."""
from weaviate.classes.config import Property, DataType

COLLECTION_CONFIG = {
    "DrugDosage": {
        "name": "DrugDosage",
        "properties": [
            Property(name="drugName", data_type=DataType.TEXT),
            Property(name="symptom", data_type=DataType.TEXT),
            Property(name="ageGroup", data_type=DataType.TEXT),
            Property(name="dosage", data_type=DataType.TEXT)
        ],
        "agent": "DrugDosageAgent",
        "query_properties": ["drugName", "symptom", "ageGroup", "dosage"],
        "filter_properties": ["drugName", "symptom", "ageGroup"],
        "result_property": "dosage",
        "scrape": {
            "url_template": "https://www.drugs.com/dosage/{drug}.html",
            "extract_function": "extract_dosage_info",
            "params": ["symptom", "ageGroup", "drugName"]
        },
        "cache_key_template": "dosage:{drugName}:{symptom}:{ageGroup}"
    },
    "DrugInteractions": {
        "name": "DrugInteractions",
        "properties": [
            Property(name="drugName", data_type=DataType.TEXT),
            Property(name="interactions", data_type=DataType.TEXT)
        ],
        "agent": "DrugInteractionAgent",
        "query_properties": ["drugName", "interactions"],
        "filter_properties": ["drugName"],
        "result_property": "interactions",
        "scrape": {
            "url_template": "https://www.drugs.com/food-interactions/{drug}.html",
            "extract_function": "extract_food_interaction_info",
            "params": ["drugName"]
        },
        "cache_key_template": "interactions:{drugName}"
    }
}