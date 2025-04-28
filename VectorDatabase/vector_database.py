from abc import ABC, abstractmethod
import weaviate
from weaviate.classes.config import Configure
from weaviate.classes.init import Auth, AdditionalConfig, Timeout
from weaviate.classes.query import Filter
from retry_manager import RetryManager
from collection_config import COLLECTION_CONFIG

class VectorDBInterface(ABC):
    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def create_schema(self):
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
    def __init__(self, weaviate_url, weaviate_api_key, retry_manager: RetryManager):
        self.weaviate_url = weaviate_url
        self.weaviate_api_key = weaviate_api_key
        self.client = None
        self.retry_manager = RetryManager(
            max_attempts=5,
            backoff_factor=retry_manager.backoff_factor,
            status_forcelist=retry_manager.status_forcelist
        )

    def connect(self):
        @self.retry_manager.retry
        def attempt_connect():
            print(f"Connecting to Weaviate...")
            self.client = weaviate.connect_to_weaviate_cloud(
                cluster_url=self.weaviate_url,
                auth_credentials=Auth.api_key(self.weaviate_api_key),
                additional_config=AdditionalConfig(timeout=Timeout(query=180, insert=300))
            )
            if not self.client.is_ready():
                raise Exception("Weaviate Cloud instance not ready.")
            print("Connected to Weaviate successfully.")
        
        attempt_connect()

    def create_schema(self):
        try:
            collections = self.client.collections.list_all()
            if collections and isinstance(collections[0], str):
                collection_names = collections
            else:
                collection_names = [coll.name for coll in collections] if collections else []
            
            for config in COLLECTION_CONFIG.values():
                collection_name = config["name"]
                if collection_name not in collection_names:
                    self.client.collections.create(
                        name=collection_name,
                        vectorizer_config=Configure.Vectorizer.none(),
                        properties=config["properties"]
                    )
                    print(f"Created '{collection_name}' collection.")
        except Exception as e:
            raise Exception(f"Failed to create Weaviate schema: {e}")

    def insert_data(self, collection_name, properties, vector):
        @self.retry_manager.retry
        def attempt_insert():
            collection = self.client.collections.get(collection_name)
            collection.data.insert(properties=properties, vector=vector)
            return True
        
        return attempt_insert()

    def query_data(self, collection_name, query_text, query_vec, return_properties, filters=None, limit=1):
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
        try:
            if self.client:
                self.client.close()
                print("Weaviate client closed.")
        except Exception as e:
            raise Exception(f"Error closing Weaviate client: {e}")