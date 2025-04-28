"""Centralized configuration for the project."""
import os

# Retry settings
RETRY_MAX_ATTEMPTS = 3
RETRY_BACKOFF_FACTOR = 0.2
RETRY_STATUS_FORCELIST = [502, 503, 504, 429]

# Cache settings
CACHE_DIR = "cache"
CACHE_MAX_SIZE = 1000
CACHE_EXPIRY_DAYS = 30

# Logging settings
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "app.log")
LOG_LEVEL = "INFO"

# Symptom to drug mappings
SYMPTOM_DRUGS = {
    "fever": ["acetaminophen", "ibuprofen"],
    "pain": ["acetaminophen", "aspirin"],
    "cough": ["dextromethorphan", "guaifenesin"],
    "nasal congestion": ["pseudoephedrine", "phenylephrine"],
    "allergic rhinitis": ["cetirizine", "loratadine"],
    "urticaria": ["cetirizine", "loratadine"],
    "gastroesophageal reflux disease": ["omeprazole", "famotidine"],
    "diarrhea": ["loperamide", "bismuth subsalicylate"],
    "constipation": ["docusate", "senna"],
    "motion sickness": ["dimenhydrinate", "meclizine"],
    "vertigo": ["dimenhydrinate", "meclizine"],
    "insomnia": ["diphenhydramine", "doxylamine"],
    "anxiety": ["lorazepam", "diazepam"],
    "hypertension": ["lisinopril", "amlodipine"],
    "panic attack": ["alprazolam", "clonazepam"]
}

# Valid symptoms
VALID_SYMPTOMS = set(SYMPTOM_DRUGS.keys())

# API settings
SSL_VERIFY = True

# Agent mappings
AGENT_CLASSES = {
    "DrugDosageAgent": "src.agents.drug_dosage_agent.DrugDosageAgent",
    "DrugInteractionAgent": "src.agents.drug_interaction_agent.DrugInteractionAgent"
}

# User input fields
INPUT_FIELDS = [
    {
        "name": "symptom",
        "prompt": "Symptom (e.g., fever, headache, cough)",
        "type": "text",
        "validation": {"type": "enum", "values": VALID_SYMPTOMS},
        "transformations": [
            {"match": "headache", "replace": "pain"},
            {"match": "heartburn|acid reflux", "replace": "gastroesophageal reflux disease"},
            {"match": "nausea|vomiting", "replace": "motion sickness"}
        ]
    },
    {
        "name": "age",
        "prompt": "Age (years)",
        "type": "numeric",
        "validation": {"min": 0, "max": 120}
    },
    {
        "name": "weight",
        "prompt": "Weight (kg, optional, press Enter to skip)",
        "type": "numeric",
        "optional": True,
        "validation": {"min": 0, "max": 300}
    }
]