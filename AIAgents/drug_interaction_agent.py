from termcolor import colored

class DrugInteractionAgent:
    def __init__(self, rag_client):
        self.rag_client = rag_client

    def get_interactions(self, drug_name):
        query_text = f"{drug_name} interactions"
        query_vec = self.rag_client.embed([query_text])[0]
        
        filters = {
            "drugName": drug_name.lower()
        }
        
        result = self.rag_client.query_data(
            collection_name="DrugInteractions",
            query_text=query_text,
            query_vec=query_vec,
            return_properties=["drugName", "interactions"],
            filters=filters
        )
        
        if result:
            interactions = result[0].properties.get("interactions", "")
            return interactions
        
        cached_interactions = self.rag_client.get_interactions_from_cache(drug_name.lower())
        if cached_interactions and len(cached_interactions) >= 20:
            print(f"Retrieved interactions from scraped cache for {drug_name.lower()}.")
            return cached_interactions
        
        scraped_html = self.rag_client.scraper.scrape_food_interaction_data(drug_name)
        interactions_info = self.rag_client.scraper.extract_food_interaction_info(scraped_html)
        
        properties = {
            "drugName": drug_name.lower(),
            "interactions": interactions_info
        }
        
        success = self.rag_client.insert_data("DrugInteractions", properties, query_vec)
        if success:
            print(f"Stored interactions for {drug_name.lower()} in Weaviate.")
        
        self.rag_client.store_interactions_in_cache(drug_name.lower(), interactions_info)
        return interactions_info