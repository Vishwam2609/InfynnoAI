import hashlib
import json
import os
import urllib3
import warnings
import requests
from WebScraper.web_scraper import WebScraper
from VectorDatabase.vector_database import VectorDBInterface, WeaviateAdapter
from retry_manager import RetryManager

warnings.filterwarnings("ignore", category=DeprecationWarning, module="weaviate")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class RAGClient:
    def __init__(self, weaviate_url, weaviate_api_key, embed_url, generate_url):
        self.vector_db = None
        self.session = None
        self.embed_cache = {}
        self.scraped_cache = {}
        self.plan_cache = {}
        self.cache_dir = "Cache"
        self.embed_cache_file = os.path.join(self.cache_dir, "embed_cache.json")
        self.scraped_cache_file = os.path.join(self.cache_dir, "scraped_cache.json")
        self.plan_cache_file = os.path.join(self.cache_dir, "plan_cache.json")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.load_caches()
        
        # Initialize retry manager
        self.retry_manager = RetryManager(max_attempts=3, backoff_factor=0.2)
        
        # Initialize vector database (Weaviate for now)
        try:
            print("Initializing vector database...")
            self.vector_db = WeaviateAdapter(weaviate_url, weaviate_api_key, self.retry_manager)
            self.vector_db.connect()
            print("Connected to vector database successfully.")
        except Exception as e:
            raise Exception(f"Failed to initialize vector database: {e}")
        
        self.embed_url = embed_url
        self.generate_url = generate_url
        self.scraper = WebScraper()
        self.session = requests.Session()
        self.retry_manager.configure_session(self.session)
        self.ensure_schema()

    def load_caches(self):
        try:
            if os.path.exists(self.embed_cache_file):
                with open(self.embed_cache_file, 'r') as f:
                    self.embed_cache = json.load(f)
                print(f"Loaded embedding cache with {len(self.embed_cache)} entries.")
        except Exception as e:
            print(f"Failed to load embedding cache: {e}")
        
        try:
            if os.path.exists(self.scraped_cache_file):
                with open(self.scraped_cache_file, 'r') as f:
                    self.scraped_cache = json.load(f)
                print(f"Loaded scraped data cache with {len(self.scraped_cache)} entries.")
        except Exception as e:
            print(f"Failed to load scraped data cache: {e}")
        
        try:
            if os.path.exists(self.plan_cache_file):
                with open(self.plan_cache_file, 'r') as f:
                    self.plan_cache = json.load(f)
                print(f"Loaded plan cache with {len(self.plan_cache)} entries.")
        except Exception as e:
            print(f"Failed to load plan cache: {e}")

    def save_caches(self):
        try:
            with open(self.embed_cache_file, 'w') as f:
                json.dump(self.embed_cache, f)
            print("Saved embedding cache.")
        except Exception as e:
            print(f"Failed to save embedding cache: {e}")
        
        try:
            with open(self.scraped_cache_file, 'w') as f:
                json.dump(self.scraped_cache, f)
            print("Saved scraped data cache.")
        except Exception as e:
            print(f"Failed to save scraped data cache: {e}")
        
        try:
            with open(self.plan_cache_file, 'w') as f:
                json.dump(self.plan_cache, f)
            print("Saved plan cache.")
        except Exception as e:
            print(f"Failed to save plan cache: {e}")

    def embed(self, texts, max_length=256):
        @self.retry_manager.retry
        def attempt_embed():
            embeddings = []
            for text in texts:
                cache_key = hashlib.md5(f"{text}:{max_length}".encode()).hexdigest()
                if cache_key in self.embed_cache:
                    embeddings.append(self.embed_cache[cache_key])
                    print(f"Retrieved embedding from cache for text: {text[:50]}...")
                    continue
                
                response = self.session.post(
                    self.embed_url,
                    json={'texts': [text], 'max_length': max_length},
                    verify=False,
                    timeout=20
                )
                if response.status_code == 200:
                    embedding = response.json()['embeddings'][0]
                    self.embed_cache[cache_key] = embedding
                    embeddings.append(embedding)
                    print(f"Generated and cached embedding for text: {text[:50]}...")
                else:
                    raise Exception(f"Embedding API error: {response.json()['error']}")
            
            self.save_caches()
            return embeddings
        
        return attempt_embed()

    def generate_text(self, prompt, sampling_params):
        @self.retry_manager.retry
        def attempt_generate():
            response = self.session.post(
                self.generate_url,
                json={'prompt': prompt, 'sampling_params': sampling_params},
                verify=False,
                timeout=60
            )
            if response.status_code == 200:
                return response.json()['generated_text']
            else:
                raise Exception(f"Generation API error: {response.json()['error']}")
        
        return attempt_generate()

    def ensure_schema(self):
        try:
            self.vector_db.create_schema()
            print("Vector database schema ensured.")
        except Exception as e:
            print(f"Failed to create vector database schema: {e}")
            raise

    def insert_data(self, collection_name, properties, vector):
        return self.vector_db.insert_data(collection_name, properties, vector)

    def query_data(self, collection_name, query_text, query_vec, return_properties, filters=None, limit=1):
        try:
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
                    if collection_name == "DrugDosage" and ("no dosage" in obj.get("dosage", "").lower() or len(obj.get("dosage", "")) < 20):
                        print(f"Invalid cached dosage for {query_text}, fetching from website.")
                        return []
                    if collection_name == "DrugInteractions" and len(obj.get("interactions", "")) < 20:
                        print(f"Invalid cached interactions for {query_text}, fetching from website.")
                        return []
                print(f"Queried data from vector database collection '{collection_name}' (cached).")
                return result
        except Exception as e:
            print(f"Vector database query failed: {e}")
        print(f"No cached data found for '{query_text}' in '{collection_name}'.")
        return []

    def get_dosage_from_cache(self, drug_name, symptom, age_group):
        cache_key = hashlib.md5(f"dosage:{drug_name}:{symptom}:{age_group}".encode()).hexdigest()
        return self.scraped_cache.get(cache_key)

    def store_dosage_in_cache(self, drug_name, symptom, age_group, dosage):
        cache_key = hashlib.md5(f"dosage:{drug_name}:{symptom}:{age_group}".encode()).hexdigest()
        self.scraped_cache[cache_key] = dosage
        self.save_caches()

    def get_interactions_from_cache(self, drug_name):
        cache_key = hashlib.md5(f"interactions:{drug_name}".encode()).hexdigest()
        return self.scraped_cache.get(cache_key)

    def store_interactions_in_cache(self, drug_name, interactions):
        cache_key = hashlib.md5(f"interactions:{drug_name}".encode()).hexdigest()
        self.scraped_cache[cache_key] = interactions
        self.save_caches()

    def get_plan_from_cache(self, plan_key):
        return self.plan_cache.get(plan_key)

    def store_plan_in_cache(self, plan_key, plan):
        self.plan_cache[plan_key] = plan
        self.save_caches()

    def cleanup(self):
        print("Cleanup called")
        try:
            if self.vector_db:
                self.vector_db.close()
                print("Vector database connection closed.")
        except Exception as e:
            print(f"Error closing vector database: {e}")
        try:
            if self.session:
                self.session.close()
                print("Requests session closed.")
        except Exception as e:
            print(f"Error closing requests session: {e}")
        self.save_caches()