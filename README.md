# Dosage Guidance Agent

A Python application that retrieves drug dosage and interaction information from `drugs.com`, stores it in a Weaviate vector database, and generates mitigation plans using Llama-3.2-3B-Instruct. The codebase is highly generalized, allowing users to modify configurations, schemas, and agents with minimal changes.

**⚠️ This is not a substitute for professional medical advice. Always consult a doctor.**

## Features
- Retrieves dosage for symptoms and age groups (adult/pediatric).
- Fetches food/alcohol interactions.
- Generates concise mitigation plans.
- Caches data for performance.
- Uses Weaviate for vector storage.
- Highly configurable via `app_config.py` and `collection_config.py`.
- Supports dynamic agent loading and schema management.
- Includes logging, retry logic, and reusable components.

## Directory Structure
```
project/
├── src/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base_agent.py
│   │   ├── drug_dosage_agent.py
│   │   ├── drug_interaction_agent.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── app_config.py
│   │   ├── collection_config.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── vector_database.py
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── web_scraper.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── cache.py
│   │   ├── config_loader.py
│   │   ├── logging_utils.py
│   │   ├── retry_manager.py
│   │   ├── text_processing.py
│   │   ├── validation.py
│   ├── __init__.py
│   ├── main.py
│   ├── rag_client.py
├── cache/ (created automatically)
├── logs/ (created automatically)
├── .env
├── README.md
├── requirements.txt
```

## Setup
1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd project
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**:
   - Copy `.env.example` to `.env` and update with valid credentials:
     ```bash
     cp .env.example .env
     ```
   - Edit `.env`:
     ```
     WEAVIATE_URL=<your-weaviate-url>
     WEAVIATE_API_KEY=<your-weaviate-api-key>
     EMBED_URL=<your-embedding-api-url>
     GENERATE_URL=<your-generation-api-url>
     ```
   - Replace `ngrok` URLs with production endpoints for security.

4. **Run the application**:
   ```bash
   python src/main.py
   ```

## Usage
- Run `src/main.py` and follow prompts for configured input fields (e.g., symptom, age, weight).
- The system outputs a mitigation plan with dosage and interaction details.
- Type `yes` to exit or `no` to continue.

## Configuration
All user-configurable settings are in `src/config/app_config.py` and `src/config/collection_config.py`.

### Modifying Application Settings
Edit `src/config/app_config.py` to change:
- **Retry settings**: Adjust `RETRY_MAX_ATTEMPTS`, `RETRY_BACKOFF_FACTOR`, `RETRY_STATUS_FORCELIST`.
- **Cache settings**: Modify `CACHE_DIR`, `CACHE_MAX_SIZE`, `CACHE_EXPIRY_DAYS`.
- **Logging**: Update `LOG_DIR`, `LOG_FILE`, `LOG_LEVEL`.
- **Symptom-drug mappings**: Add or change entries in `SYMPTOM_DRUGS`.
- **Input fields**: Customize `INPUT_FIELDS` to add/remove prompts, validations, or transformations.
- **Agent mappings**: Update `AGENT_CLASSES` to include new agents.

Example: To add a new symptom:
```python
SYMPTOM_DRUGS = {
    ...
    "migraine": ["sumatriptan", "rizatriptan"]
}
VALID_SYMPTOMS = set(SYMPTOM_DRUGS.keys())
```

### Modifying Collections and Agents
Edit `src/config/collection_config.py` to change:
- **Collection names and schemas**: Update `name` or `properties` in `COLLECTION_CONFIG`.
- **Agent behavior**: Specify `agent`, `query_properties`, `filter_properties`, `result_property`.
- **Scraping rules**: Define `url_template`, `extract_function`, and `params` for scraping.
- **Cache keys**: Set `cache_key_template` for cache entries.

Example: To rename `DrugDosage` to `DosageInfo` and change properties:
```python
COLLECTION_CONFIG = {
    "DrugDosage": {
        "name": "DosageInfo",
        "properties": [
            Property(name="medication", data_type=DataType.TEXT),
            Property(name="condition", data_type=DataType.TEXT),
            Property(name="patientAgeGroup", data_type=DataType.TEXT),
            Property(name="dose", data_type=DataType.TEXT)
        ],
        "agent": "DrugDosageAgent",
        "query_properties": ["medication", "condition", "patientAgeGroup", "dose"],
        "filter_properties": ["medication", "condition", "patientAgeGroup"],
        "result_property": "dose",
        "scrape": {
            "url_template": "https://www.drugs.com/dosage/{drug}.html",
            "extract_function": "extract_dosage_info",
            "params": ["condition", "patientAgeGroup", "medication"]
        },
        "cache_key_template": "dosage:{medication}:{condition}:{patientAgeGroup}"
    },
    ...
}
```

### Adding a New Agent
1. Create a new agent in `src/agents/` (e.g., `side_effects_agent.py`):
   ```python
   from src.agents.base_agent import BaseAgent
   class SideEffectsAgent(BaseAgent):
       def __init__(self, rag_client):
           super().__init__(rag_client, "SideEffects")
       def get_side_effects(self, drug_name):
           return self.retrieve_data({"drugName": drug_name})
       def process_data(self, *args, **kwargs):
           return kwargs.get("data", "No processing implemented.")
   ```
2. Add the agent to `src/config/app_config.py`:
   ```python
   AGENT_CLASSES = {
       ...
       "SideEffectsAgent":