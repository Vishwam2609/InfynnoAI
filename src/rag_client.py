"""RAG client for interfacing with vector database, scraper, and APIs."""
import hashlib
import os
import time
import urllib3
import warnings
import requests
import logging
from src.scraper.web_scraper import WebScraper
from src.database.vector_database import VectorDBInterface, WeaviateAdapter
from src.utils.retry_manager import RetryManager
from src.utils.cache import LRUCache
from src.utils.config_loader import ConfigLoader

warnings.filterwarnings("ignore", category=DeprecationWarning, module="weaviate")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class RAGClient:
    """Client for RAG operations with vector database, scraper, and APIs."""
    def __init__(self, weaviate_url, weaviate_api_key, embed_url, generate_url):
        """Initialize the RAG client.

        Args:
            weaviate_url (str): Weaviate cluster URL.
            weaviate_api_key (str): Weaviate API key.
            embed_url (str): Embedding API URL.
            generate_url (str): Text generation API URL.
        """
        config_loader = ConfigLoader()
        self.config = config_loader.get_config()
        self.vector_db = None
        self.session = None
        self.embed_cache = LRUCache(self.config["CACHE_MAX_SIZE"], self.config["CACHE_EXPIRY_DAYS"])
        self.scraped_cache = LRUCache(self.config["CACHE_MAX_SIZE"], self.config["CACHE_EXPIRY_DAYS"])
        self.plan_cache = LRUCache(self.config["CACHE_MAX_SIZE"], self.config["CACHE_EXPIRY_DAYS"])
        self.cache_dir = self.config["CACHE_DIR"]
        self.embed_cache_file = os.path.join(self.cache_dir, "embed_cache.json")
        self.scraped_cache_file = os.path.join(self.cache_dir, "scraped_cache.json")
        self.plan_cache_file = os.path.join(self.cache_dir, "plan_cache.json")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.load_caches()
        
        self.retry_manager = RetryManager()
        
        try:
            logger.info("Initializing vector database")
            self.vector_db = WeaviateAdapter(weaviate_url, weaviate_api_key, self.retry_manager)
            self.vector_db.connect()
            logger.info("Connected to vector database")
        except Exception as e:
            logger.error(f"Failed to initialize vector database: {e}")
            raise
        
        self.embed_url = embed_url
        self.generate_url = generate_url
        self.scraper = WebScraper()
        self.session = requests.Session()
        self.retry_manager.configure_session(self.session)
        self.ensure_schema()
        if not self.config["SSL_VERIFY"]:
            logger.warning("SSL verification is disabled. Use secure endpoints in production.")

    def load_caches(self):
        """Load caches from disk."""
        self.embed_cache.load(self.embed_cache_file)
        self.scraped_cache.load(self.scraped_cache_file)
        self.plan_cache.load(self.plan_cache_file)

    def save_caches(self):
        """Save caches to disk."""
        self.embed_cache.save(self.embed_cache_file)
        self.scraped_cache.save(self.scraped_cache_file)
        self.plan_cache.save(self.plan_cache_file)

    def embed(self, texts, max_length=256):
        """Generate embeddings for texts.

        Args:
            texts (list): List of texts to embed.
            max_length (int): Maximum length for embedding.

        Returns:
            list: List of embeddings.
        """
        @self.retry_manager.retry
        def attempt_embed():
            embeddings = []
            for text in texts:
                cache_key = hashlib.md5(f"{text}:{max_length}".encode()).hexdigest()
                cached = self.embed_cache.get(cache_key)
                if cached:
                    embeddings.append(cached)
                    logger.info(f"Retrieved embedding from cache for text: {text[:50]}...")
                    continue
                
                try:
                    response = self.session.post(
                        self.embed_url,
                        json={'texts': [text], 'max_length': max_length},
                        verify=self.config["SSL_VERIFY"],
                        timeout=20
                    )
                    if response.status_code == 200:
                        embedding = response.json()['embeddings'][0]
                        self.embed_cache.put(cache_key, embedding)
                        embeddings.append(embedding)
                        logger.info(f"Generated and cached embedding for text: {text[:50]}...")
                    else:
                        raise Exception(f"Embedding API error: {response.json()['error']}")
                except Exception as e:
                    logger.error(f"Embedding failed for {text[:50]}: {e}")
                    embeddings.append(None)
            self.save_caches()
            return embeddings
        
        return attempt_embed()

    def generate_text(self, prompt, sampling_params):
        """Generate text using the generation API.

        Args:
            prompt (str): Prompt for text generation.
            sampling_params (dict): Parameters for sampling.

        Returns:
            str: Generated text or fallback message.
        """
        @self.retry_manager.retry
        def attempt_generate():
            try:
                response = self.session.post(
                    self.generate_url,
                    json={'prompt': prompt, 'sampling_params': sampling_params},
                    verify=self.config["SSL_VERIFY"],
                    timeout=60
                )
                if response.status_code == 200:
                    return response.json()['generated_text']
                else:
                    raise Exception(f"Generation API error: {response.json()['error']}")
            except Exception as e:
                logger.error(f"Text generation failed: {e}")
                raise
        
        try:
            return attempt_generate()
        except Exception:
            logger.warning("Generation API unavailable, returning fallback")
            return "Unable to generate plan due to API unavailability."

    def ensure_schema(self):
        """Ensure vector database schema exists."""
        try:
            collection_config = ConfigLoader().get_collection_config()
            self.vector_db.create_schema(collection_config)
            logger.info("Vector database schema ensured")
        except Exception as e:
            logger.error(f"Failed to create vector database schema: {e}")
            raise

    def insert_data(self, collection_name, properties, vector):
        """Insert data into the vector database.

        Args:
            collection_name (str): Name of the collection.
            properties (dict): Data properties.
            vector (list): Vector embedding.

        Returns:
            bool: True if successful.
        """
        try:
            return self.vector_db.insert_data(collection_name, properties, vector)
        except Exception as e:
            logger.error(f"Failed to insert data into {collection_name}: {e}")
            return False

    def query_data(self, collection_name, query_text, query_vec, return_properties, filters=None, limit=1):
        """Query data from the vector database.

        Args:
            collection_name (str): Name of the collection.
            query_text (str): Query text.
            query_vec (list): Query vector.
            return_properties (list): Properties to return.
            filters (dict, optional): Query filters.
            limit (int): Maximum results.

        Returns:
            list: Query results or empty list on failure.
        """
        collection_config = ConfigLoader().get_collection_config()
        try:
            for coll_key, config in collection_config.items():
                if config["name"] == collection_name:
                    result_property = config["result_property"]
                    break
            else:
                logger.error(f"Collection {collection_name} not found in config")
                return []
            
            result = self.vector_db.query_data(
                collection_name=collection_name,
                query_text=query_text,
                query_vec=query_vec,
                return_properties=return_properties,
                filters=filters,
                limit=limit
            )
            if result:
                for obj in result:
                    data = obj.get(result_property, "")
                    if len(data) < 20 or "no " in data.lower():
                        logger.info(f"Invalid cached data for {query_text}, fetching from website")
                        return []
                logger.info(f"Queried data from {collection_name} (cached)")
                return result
        except Exception as e:
            logger.error(f"Vector database query failed: {e}")
        logger.info(f"No cached data for '{query_text}' in '{collection_name}'")
        return []

    def get_from_cache(self, cache_key):
        """Get data from scraped cache.

        Args:
            cache_key (str): Cache key.

        Returns:
            str: Cached data or None.
        """
        return self.scraped_cache.get(cache_key)

    def store_in_cache(self, cache_key, data):
        """Store data in scraped cache.

        Args:
            cache_key (str): Cache key.
            data (str): Data to store.
        """
        self.scraped_cache.put(cache_key, data)
        self.save_caches()

    def get_plan_from_cache(self, plan_key):
        """Get mitigation plan from cache.

        Args:
            plan_key (str): Cache key for the plan.

        Returns:
            str: Cached plan or None.
        """
        return self.plan_cache.get(plan_key)

    def store_plan_in_cache(self, plan_key, plan):
        """Store mitigation plan in cache.

        Args:
            plan_key (str): Cache key for the plan.
            plan (str): Mitigation plan.
        """
        self.plan_cache.put(plan_key, plan)
        self.save_caches()

    def cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up resources")
        try:
            if self.vector_db:
                self.vector_db.close()
                logger.info("Vector database connection closed")
        except Exception as e:
            logger.error(f"Error closing vector database: {e}")
        try:
            if self.session:
                self.session.close()
                logger.info("Requests session closed")
        except Exception as e:
            logger.error(f"Error closing requests session: {e}")
        self.save_caches()