"""Interface for vector database operations."""
from abc import ABC, abstractmethod

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