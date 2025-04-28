from weaviate.classes.config import Property, DataType

# Configuration for Weaviate collections
COLLECTION_CONFIG = {
    "DrugDosage": {
        "name": "DrugDosage",
        "properties": [
            Property(name="drugName", data_type=DataType.TEXT),
            Property(name="symptom", data_type=DataType.TEXT),
            Property(name="ageGroup", data_type=DataType.TEXT),
            Property(name="dosage", data_type=DataType.TEXT)
        ]
    },
    "DrugInteractions": {
        "name": "DrugInteractions",
        "properties": [
            Property(name="drugName", data_type=DataType.TEXT),
            Property(name="interactions", data_type=DataType.TEXT)
        ]
    }
}