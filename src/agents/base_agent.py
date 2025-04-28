"""Base agent for common data retrieval and caching logic."""
import logging
from abc import ABC, abstractmethod
from src.utils.config_loader import ConfigLoader

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    """Abstract base class for agents handling data retrieval and caching."""
    def __init__(self, rag_client, collection_key):
        """Initialize with a RAG client and collection key.

        Args:
            rag_client: RAGClient instance for database and scraping operations.
            collection_key (str): Key in COLLECTION_CONFIG (e.g., 'DrugDosage').
        """
        self.rag_client = rag_client
        self.collection_config = ConfigLoader().get_collection_config()[collection_key]
        self.collection_name = self.collection_config["name"]

    def retrieve_data(self, query_params):
        """Retrieve data from Weaviate, cache, or scraper.

        Args:
            query_params (dict): Parameters for query (e.g., {'drugName': 'aspirin', 'symptom': 'pain'}).

        Returns:
            str: Retrieved data or error message.
        """
        query_text = " ".join(query_params.values())
        query_vec = self.rag_client.embed([query_text])[0]
        
        filters = {k: v.lower() for k, v in query_params.items() if k in self.collection_config["filter_properties"]}
        result = self.rag_client.query_data(
            collection_name=self.collection_name,
            query_text=query_text,
            query_vec=query_vec,
            return_properties=self.collection_config["query_properties"],
            filters=filters
        )
        
        data_key = query_params.get(self.collection_config["filter_properties"][0], "unknown")
        if result:
            data = result[0].properties.get(self.collection_config["result_property"], "")
            logger.info(f"Retrieved data from Weaviate for {data_key}.")
            return data
        
        cache_key = self.collection_config["cache_key_template"].format(**query_params)
        cached_data = self.rag_client.get_from_cache(cache_key)
        if cached_data and len(cached_data) >= 20 and "no " not in cached_data.lower():
            logger.info(f"Retrieved data from cache for {data_key}.")
            return cached_data
        
        scrape_config = self.collection_config["scrape"]
        drug_key = query_params.get(self.collection_config["filter_properties"][0], "").replace(" ", "-").lower()
        url = scrape_config["url_template"].format(drug=drug_key)
        scraped_content = self.rag_client.scraper.scrape_data(url)
        
        extract_params = [query_params.get(param, "") for param in scrape_config["params"]]
        extracted_data = getattr(self.rag_client.scraper, scrape_config["extract_function"])(scraped_content, *extract_params)
        
        properties = {k: v.lower() for k, v in query_params.items() if k in self.collection_config["filter_properties"]}
        properties[self.collection_config["result_property"]] = extracted_data
        
        success = self.rag_client.insert_data(self.collection_name, properties, query_vec)
        if success:
            logger.info(f"Stored data for {data_key} in Weaviate.")
        
        self.rag_client.store_in_cache(cache_key, extracted_data)
        return extracted_data

    @abstractmethod
    def process_data(self, *args, **kwargs):
        """Process retrieved data (to be implemented by subclasses).

        Args:
            *args: Variable arguments.
            **kwargs: Keyword arguments.

        Returns:
            str: Processed data.
        """
        pass