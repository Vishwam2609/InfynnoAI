import hashlib
import json
import os
import re
import requests
import time
import urllib3
import warnings
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import weaviate
from weaviate.classes.config import Configure, Property, DataType
from weaviate.classes.init import Auth, AdditionalConfig, Timeout
from weaviate.classes.query import Filter

warnings.filterwarnings("ignore", category=DeprecationWarning, module="weaviate")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class RAGClient:
    def __init__(self, weaviate_url, weaviate_api_key, embed_url, generate_url):
        self.client = None
        self.session = None
        self.embed_cache = {}
        self.cache_file = "embed_cache.json"
        self.load_embed_cache()
        for attempt in range(3):
            try:
                print(f"Connecting to Weaviate (attempt {attempt + 1}/3)...")
                self.client = weaviate.connect_to_weaviate_cloud(
                    cluster_url=weaviate_url,
                    auth_credentials=Auth.api_key(weaviate_api_key),
                    additional_config=AdditionalConfig(timeout=Timeout(query=180, insert=300))
                )
                if not self.client.is_ready():
                    raise Exception("Weaviate Cloud instance not ready.")
                print("Connected to Weaviate successfully.")
                break
            except Exception as e:
                if attempt == 2:
                    raise Exception(f"Failed to connect to Weaviate after retries: {e}")
                time.sleep(0.5 * (2 ** attempt))
        
        self.embed_url = embed_url
        self.generate_url = generate_url
        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.2, status_forcelist=[502, 503, 504, 429])
        self.session.mount('http://', HTTPAdapter(max_retries=retries))
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        self.ensure_schema()

    def load_embed_cache(self):
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    self.embed_cache = json.load(f)
                print(f"Loaded embedding cache with {len(self.embed_cache)} entries.")
        except Exception as e:
            print(f"Failed to load embedding cache: {e}")

    def save_embed_cache(self):
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.embed_cache, f)
            print("Saved embedding cache.")
        except Exception as e:
            print(f"Failed to save embedding cache: {e}")

    def embed(self, texts, max_length=256):
        embeddings = []
        for text in texts:
            cache_key = hashlib.md5(f"{text}:{max_length}".encode()).hexdigest()
            if cache_key in self.embed_cache:
                embeddings.append(self.embed_cache[cache_key])
                print(f"Retrieved embedding from cache for text: {text[:50]}...")
                continue
            
            for attempt in range(3):
                try:
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
                        break
                    else:
                        raise Exception(f"Embedding API error: {response.json()['error']}")
                except Exception as e:
                    if attempt == 2:
                        raise Exception(f"Embedding failed after retries: {e}")
                    time.sleep(0.2 * (2 ** attempt))
        
        self.save_embed_cache()
        return embeddings

    def generate_text(self, prompt, sampling_params):
        for attempt in range(3):
            try:
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
            except Exception as e:
                if attempt == 2:
                    raise Exception(f"Generation failed after retries: {e}")
                time.sleep(0.2 * (2 ** attempt))

    def ensure_schema(self):
        try:
            collections = self.client.collections.list_all()
            if collections and isinstance(collections[0], str):
                collection_names = collections
            else:
                collection_names = [coll.name for coll in collections] if collections else []
            
            if "DrugDosage" not in collection_names:
                self.client.collections.create(
                    name="DrugDosage",
                    vectorizer_config=Configure.Vectorizer.none(),
                    properties=[
                        Property(name="drugName", data_type=DataType.TEXT),
                        Property(name="symptom", data_type=DataType.TEXT),
                        Property(name="ageGroup", data_type=DataType.TEXT),
                        Property(name="dosage", data_type=DataType.TEXT)
                    ]
                )
                print("Created 'DrugDosage' collection.")
            if "DrugInteractions" not in collection_names:
                self.client.collections.create(
                    name="DrugInteractions",
                    vectorizer_config=Configure.Vectorizer.none(),
                    properties=[
                        Property(name="drugName", data_type=DataType.TEXT),
                        Property(name="interactions", data_type=DataType.TEXT)
                    ]
                )
                print("Created 'DrugInteractions' collection.")
        except Exception as e:
            print(f"Failed to create Weaviate schema: {e}")
            raise

    def insert_data(self, collection_name, properties, vector):
        for attempt in range(5):
            try:
                collection = self.client.collections.get(collection_name)
                collection.data.insert(properties=properties, vector=vector)
                print(f"Stored data in Weaviate collection '{collection_name}'.")
                return True
            except Exception as e:
                if attempt == 4:
                    print(f"Failed to store data in Weaviate after retries: {e}")
                    return False
                time.sleep(0.2 * (2 ** attempt))
        return False

    def query_data(self, collection_name, query_text, query_vec, return_properties, filters=None, limit=1):
        try:
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
            if result:
                for obj in result:
                    if collection_name == "DrugDosage" and ("no dosage" in obj.properties.get("dosage", "").lower() or len(obj.properties.get("dosage", "")) < 20):
                        print(f"Invalid cached dosage for {query_text}, fetching from website.")
                        return []
                    if collection_name == "DrugInteractions" and len(obj.properties.get("interactions", "")) < 20:
                        print(f"Invalid cached interactions for {query_text}, fetching from website.")
                        return []
                print(f"Queried data from Weaviate collection '{collection_name}' (cached).")
                return result
        except Exception as e:
            print(f"Weaviate cache query failed: {e}")
        print(f"No cached data found for '{query_text}' in '{collection_name}'.")
        return []

    def scrape_drug_data(self, drug_name, retries=1, delay=3):
        url = f"https://www.drugs.com/dosage/{drug_name.replace(' ', '-').lower()}.html"
        print(f"Scraping dosage URL: {url}")
        for attempt in range(retries + 1):
            try:
                r = self.session.get(url, timeout=10)
                r.raise_for_status()
                return r.text
            except requests.RequestException as e:
                if attempt < retries:
                    time.sleep(delay)
                else:
                    print(f"Failed to fetch {drug_name} dosage: {e}")
                    return None

    def scrape_food_interaction_data(self, drug_name, retries=1, delay=3):
        url = f"https://www.drugs.com/food-interactions/{drug_name.replace(' ', '-').lower()}.html"
        print(f"Scraping interactions URL: {url}")
        for attempt in range(retries + 1):
            try:
                r = self.session.get(url, timeout=10)
                r.raise_for_status()
                return r.text
            except requests.RequestException as e:
                if attempt < retries:
                    time.sleep(delay)
                else:
                    print(f"Failed to fetch {drug_name} interactions: {e}")
                    return None

    def extract_dosage_info(self, scraped_html, symptom, age_group, drug):
        if not scraped_html:
            return f"No dosage information available for {drug}."
        
        if drug.lower() in ["alprazolam", "clonazepam"] and age_group == "pediatric":
            return "Not recommended for patients under 18; consult a doctor."
        
        soup_full = BeautifulSoup(scraped_html, "html.parser")
        main_content = soup_full.find("div", {"id": "content", "class": "ddc-main-content"}) or soup_full
        
        section_title = f"Usual {age_group.capitalize()} Dose for {symptom.capitalize()}"
        candidate_heading = None
        
        for heading in main_content.find_all(["h2", "h3"]):
            heading_text = heading.get_text(" ", strip=True).lower()
            if section_title.lower() in heading_text:
                candidate_heading = heading
                break
        
        if not candidate_heading:
            for heading in main_content.find_all(["h2", "h3"]):
                heading_text = heading.get_text(" ", strip=True).lower()
                if "dose" in heading_text and (age_group.lower() in heading_text or symptom.lower() in heading_text):
                    candidate_heading = heading
                    break
        
        if not candidate_heading:
            return f"No dosage section found for {age_group} and {symptom}."
        
        print(f"Found matching section: '{candidate_heading.get_text(strip=True)}'")
        next_heading = candidate_heading.find_next_sibling(["h2", "h3"])
        content = []
        if next_heading:
            for sibling in candidate_heading.next_siblings:
                if sibling == next_heading:
                    break
                if sibling.name and sibling.name.startswith('h'):
                    continue
                content.append(str(sibling))
        else:
            content = [str(item) for item in candidate_heading.next_siblings if not (item.name and item.name.startswith('h'))]
        
        dosage_html_block = "".join(content)
        dosage_html_with_newlines = re.sub(r'<br\s*/?>', '\n', dosage_html_block, flags=re.IGNORECASE)
        dosage_soup_processed = BeautifulSoup(dosage_html_with_newlines, "html.parser")
        full_text = dosage_soup_processed.get_text(separator='\n', strip=True)
        lines = [line.strip() for line in full_text.splitlines() if line.strip()]
        full_text_cleaned = "\n".join(lines)
        
        match = re.search(r'oral:', full_text_cleaned, re.IGNORECASE)
        if match:
            oral_text = full_text_cleaned[match.start():]
        else:
            oral_text = full_text_cleaned
        
        boundaries = [
            re.compile(r'parenteral\s*(\([^)]+\))?:', re.IGNORECASE),
            re.compile(r'rectal\s*:', re.IGNORECASE),
            re.compile(r'comments?:', re.IGNORECASE),
            re.compile(r'use:', re.IGNORECASE),
        ]
        filtered_lines = []
        for line in oral_text.splitlines():
            stop_processing = False
            for pattern in boundaries:
                match = pattern.search(line)
                if match:
                    before_boundary = line[:match.start()].strip()
                    if before_boundary:
                        filtered_lines.append(before_boundary)
                    stop_processing = True
                    break
            if stop_processing:
                break
            filtered_lines.append(line)
        
        final_text_cleaned = "\n".join(filtered_lines)
        if (len(final_text_cleaned) < 20 or
            all(unit not in final_text_cleaned.lower() for unit in ['mg', 'mcg', 'ml'])):
            return f"No valid dosage found for {age_group} and {symptom}."
        
        return final_text_cleaned

    def extract_food_interaction_info(self, html):
        if not html:
            return "No food/alcohol interactions found."
        
        soup = BeautifulSoup(html, "html.parser")
        main = soup.find("div", id="content", class_="ddc-main-content") or soup
        divs = main.find_all("div", class_="interactions-reference")
        if not divs:
            return "No food/alcohol interactions found."
        parts = []
        for d in divs:
            sev_span = d.find("span", class_="ddc-status-label")
            sev = sev_span.get_text(strip=True) if sev_span else "Unknown"
            title_tag = d.find("h3")
            title = title_tag.get_text(strip=True) if title_tag else "Unknown Interaction"
            desc = ""
            desc_p = d.find("p", recursive=False) or d.find("p")
            if desc_p:
                desc = desc_p.get_text(strip=True)
            else:
                for child in d.find_all(recursive=False):
                    if child != title_tag and child.name != "div":
                        child_text = child.get_text(strip=True)
                        if child_text:
                            desc += child_text + " "
                desc = desc.strip()
            
            if desc and desc.lower() != "information for this minor interaction is available on the professional version":
                parts.append(f"{sev} Interaction: {title}\n{desc}")
        
        return "\n\n".join(parts) if parts else "No relevant food/alcohol interactions found."

    def cleanup(self):
        print("Cleanup called")
        try:
            if self.client:
                self.client.close()
                print("Weaviate client closed.")
        except Exception as e:
            print(f"Error closing Weaviate client: {e}")
        try:
            if self.session:
                self.session.close()
                print("Requests session closed.")
        except Exception as e:
            print(f"Error closing requests session: {e}")
        self.save_embed_cache()