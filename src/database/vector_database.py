"""Interface and adapter for vector database operations."""
from abc import ABC, abstractmethod
import weaviate
import logging
from weaviate.classes.config import Configure
from weaviate.classes.init import Auth, AdditionalConfig, Timeout
from weaviate.classes.query import Filter
from src.utils.retry_manager import RetryManager

logger = logging.getLogger(__name__)

class VectorDBInterface(ABC):
    """Abstract interface for vector database operations."""
    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def create_schema(self, config):
        pass

    @abstractmethod
    def insert_data(self, collection_name, properties, vector):
        pass

    @abstractmethod
    def query_data(self, collection_name, query_text, query_vec, return_properties, filters=None, limit=1):
        pass

    @abstractmethod
    def close(self):
        pass

class WeaviateAdapter(VectorDBInterface):
    """Weaviate implementation of the vector database interface."""
    def __init__(self, weaviate_url, weaviate_api_key, retry_manager: RetryManager):
        """Initialize with Weaviate connection details.

        Args:
            weaviate_url (str): Weaviate cluster URL.
            weaviate_api_key (str): Weaviate API key.
            retry_manager (RetryManager): Manager for retry logic.
        """
        self.weaviate_url = weaviate_url
        self.weaviate_api_key = weaviate_api_key
        self.client = None
        self.retry_manager = retry_manager

    def connect(self):
        """Connect to the Weaviate database."""
        @self.retry_manager.retry
        def attempt_connect():
            logger.info("Connecting to Weaviate...")
            self.client = weaviate.connect_to_weaviate_cloud(
                cluster_url=self.weaviate_url,
                auth_credentials=Auth.api_key(self.weaviate_api_key),
                additional_config=AdditionalConfig(timeout=Timeout(query=180, insert=300))
            )
            if not self.client.is_ready():
                raise Exception("Weaviate Cloud instance not ready.")
            logger.info("Connected to Weaviate successfully.")
        
        attempt_connect()

    def create_schema(self, config):
        """Create schemas for configured collections.

        Args:
            config (dict): Collection configuration with names and properties.
        """
        try:
            collections = self.client.collections.list_all()
            if collections and isinstance(collections[0], str):
                collection_names = collections
            else:
                collection_names = [coll.name for coll in collections] if collections else []
            
            for coll_config in config.values():
                collection_name = coll_config["name"]
                if collection_name not in collection_names:
                    self.client.collections.create(
                        name=collection_name,
                        vectorizer_config=Configure.Vectorizer.none(),
                        properties=coll_config["properties"]
                    )
                    logger.info(f"Created '{collection_name}' collection.")
        except Exception as e:
            logger.error(f"Failed to create Weaviate schema: {e}")
            raise

    def insert_data(self, collection_name, properties, vector):
        """Insert data into a Weaviate collection.

        Args:
            collection_name (str): Name of the collection.
            properties (dict): Data properties to insert.
            vector (list): Vector embedding for the data.

        Returns:
            bool: True if insertion was successful.
        """
        @self.retry_manager.retry
        def attempt_insert():
            collection = self.client.collections.get(collection_name)
            collection.data.insert(properties=properties, vector=vector)
            return True
        
        return attempt_insert()

    def query_data(self, collection_name, query_text, query_vec, return_properties, filters=None, limit=1):
        """Query data from a Weaviate collection.

        Args:
            collection_name (str): Name of the collection.
            query_text (str): Query text for hybrid search.
            query_vec (list): Query vector for hybrid search.
            return_properties (list): Properties to return.
            filters (dict, optional): Filters for the query.
            limit (int): Maximum number of results.

        Returns:
            list: Query results as list of property dictionaries.
        """
        @self.retry_manager.retry
        def attempt_query():
            collection = self.client.collections.get(collection_name)
            filter_obj = None
            if filters:
                filter_list = [Filter.by_property(key).equal(value) for key, value in filters.items()]
                filter_obj = Filter.all_of(filter_list)
            
            result = collection.query.hybrid(
                query=query_text,
                vector=query_vec,
                alpha=0.6,
                limit=limit,
                return_properties=return_properties,
                filters=filter_obj
            ).objects
            return [obj.properties for obj in result]
        
        return attempt_query()

    def close(self):
        """Close the Weaviate client connection."""
        try:
            if self.client:
                self.client.close()
                logger.info("Weaviate client closed.")
        except Exception as e:
            logger.error(f"Error closing Weaviate client: {e}")
            raise