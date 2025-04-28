import time
import hashlib
from termcolor import colored
from rag_client import RAGClient
from AIAgents.drug_dosage_agent import DrugDosageAgent
from AIAgents.drug_interaction_agent import DrugInteractionAgent
from utils import extract_dose_frequency, summarize_interaction
from dotenv import load_dotenv
import os
import traceback
import re

def main():
    load_dotenv()
    weaviate_url = os.getenv("WEAVIATE_URL")
    weaviate_api_key = os.getenv("WEAVIATE_API_KEY")
    embed_url = os.getenv("EMBED_URL")
    generate_url = os.getenv("GENERATE_URL")
    
    if not all([weaviate_url, weaviate_api_key, embed_url, generate_url]):
        print(colored("❌ Missing environment variables.", "red"))
        return
    
    rag_client = None
    try:
        rag_client = RAGClient(weaviate_url, weaviate_api_key, embed_url, generate_url)
        dosage_agent = DrugDosageAgent(rag_client)
        interaction_agent = DrugInteractionAgent(rag_client)
        
        print(colored("\n👋 Welcome to the Dosage Guidance Agent!", "blue"))
        print("Extracts dosage & food/alcohol interactions for medications, then builds a plan using Llama-3.2-3B-Instruct.")
        print(colored("⚠️ Not a substitute for professional medical advice.", "red"))
        print("-" * 60)
        
        valid_symptoms = {
            "fever", "pain", "cough", "nasal congestion", "allergic rhinitis",
            "urticaria", "gastroesophageal reflux disease", "diarrhea", "constipation",
            "motion sickness", "vertigo", "nausea", "vomiting", "insomnia",
            "anxiety", "hypertension", "panic attack"
        }
        
        symptom_drugs = {
            "fever": ["acetaminophen", "ibuprofen"],
            "pain": ["acetaminophen", "aspirin"],
            "cough": ["dextromethorphan", "guaifenesin"],
            "nasal congestion": ["pseudoephedrine", "phenylephrine"],
            "allergic rhinitis": ["cetirizine", "loratadine"],
            "urticaria": ["cetirizine", "loratadine"],
            "gastroesophageal reflux disease": ["omeprazole", "famotidine"],
            "diarrhea": ["loperamide", "bismuth subsalicylate"],
            "constipation": ["docusate", "senna"],
            "motion sickness": ["dimenhydrinate", "meclizine"],
            "vertigo": ["dimenhydrinate", "meclizine"],
            "insomnia": ["diphenhydramine", "doxylamine"],
            "anxiety": ["lorazepam", "diazepam"],
            "hypertension": ["lisinopril", "amlodipine"],
            "panic attack": ["alprazolam", "clonazepam"]
        }
        
        while True:
            print(colored("\nEnter patient details:", "blue"))
            symptom = input(colored("Symptom (e.g., fever, headache, cough, panic attack): ", "cyan")).strip().lower()
            if symptom == "headache":
                symptom = "pain"
            elif symptom in ["heartburn", "acid reflux"]:
                symptom = "gastroesophageal reflux disease"
            elif symptom in ["nausea", "vomiting"]:
                symptom = "motion sickness"
            if symptom not in valid_symptoms:
                print(colored("❌ Invalid symptom.", "red"))
                continue
            
            try:
                age = float(input(colored("Age (years): ", "cyan")).strip())
                if age <= 0:
                    print(colored("❌ Age must be positive.", "red"))
                    continue
            except ValueError:
                print(colored("❌ Age must be a number.", "red"))
                continue
            
            weight = None
            weight_input = input(colored("Weight (kg, optional, press Enter to skip): ", "cyan")).strip()
            if weight_input:
                try:
                    weight = float(weight_input)
                    if weight <= 0:
                        print(colored("❌ Weight must be positive.", "red"))
                        continue
                except ValueError:
                    print(colored("❌ Weight must be a number.", "red"))
                    continue
            
            age_group = "adult" if age >= 18 else "pediatric"
            print(colored(
                f"ℹ️ Symptom={symptom}, Age={age}, Group={age_group}"
                f"{', Weight=' + str(weight) + ' kg' if weight else ''}",
                "green"
            ))
            start_time = time.time()
            print(colored("Starting processing timer...", "cyan"))
            
            drugs = symptom_drugs[symptom]
            drug_data = {}
            for d in drugs:
                print(colored(f"\n🔍 Fetching dosage for {d.capitalize()}...", "blue"))
                extracted_dosage = dosage_agent.get_dosage(d, symptom, age_group)
                print(colored(f"\nExtracted Dosage:\n{extracted_dosage}\n", "green"))
                drug_data[d] = {"dosage_details": extracted_dosage, "interactions": ""}
                
                print(colored(f"🔍 Fetching interactions for {d.capitalize()}...", "blue"))
                inter = interaction_agent.get_interactions(d)
                drug_data[d]["interactions"] = inter
                print(colored(f"\n{inter}\n", "green"))
            
            print(colored("🔍 Generating mitigation plan...", "blue"))
            plan = generate_mitigation_plan(rag_client, dosage_agent, symptom, age, age_group, drug_data, weight)
            print(colored(f"\nMitigation Plan:\n{plan}\n", "green"))
            latency = time.time() - start_time
            print(colored(f"Processing took {latency:.2f} seconds.", "green"))
            
            exit_choice = input(colored("\nWould you like to exit? (yes/no): ", "cyan")).strip().lower()
            if exit_choice == "yes":
                print(colored("Exiting program...", "blue"))
                break
            elif exit_choice == "no":
                continue
            else:
                print(colored("Invalid input. Assuming 'no'...", "yellow"))
                continue
    except Exception as e:
        print(colored(f"\n❌ Error: {e}", "red"))
        traceback.print_exc()
    finally:
        if rag_client:
            rag_client.cleanup()

def generate_mitigation_plan(rag_client, dosage_agent, symptom, age, age_group, drug_data, weight):
    drug_names = list(drug_data.keys())
    if len(drug_names) < 2:
        print(colored("❌ Error: Expected data for two drugs.", "red"))
        return "Error: Insufficient drug data."
    
    drug1_name_key = drug_names[0].lower()
    drug2_name_key = drug_names[1].lower()
    
    drug1_info = drug_data[drug1_name_key]
    drug2_info = drug_data[drug2_name_key]
    
    drug1_name_display = drug1_name_key.capitalize()
    drug2_name_display = drug2_name_key.capitalize()
    
    drug1_dosage_line = dosage_agent.extract_relevant_dosage(drug1_name_display, drug1_info.get('dosage_details', ''), weight, age)
    drug2_dosage_line = dosage_agent.extract_relevant_dosage(drug2_name_display, drug2_info.get('dosage_details', ''), weight, age)
    drug1_dosage_concise = extract_dose_frequency(drug1_dosage_line)
    drug2_dosage_concise = extract_dose_frequency(drug2_dosage_line)
    
    drug1_interactions = drug1_info.get('interactions', 'No food/alcohol interactions found.')
    drug2_interactions = drug2_info.get('interactions', 'No food/alcohol interactions found.')
    drug1_interaction_summary = summarize_interaction(drug1_interactions, drug1_name_display)
    drug2_interaction_summary = summarize_interaction(drug2_interactions, drug2_name_display)
    
    plan_key = hashlib.md5(f"{symptom}:{age}:{weight}:{drug1_name_display}:{drug2_name_display}".encode()).hexdigest()
    cached_plan = rag_client.get_plan_from_cache(plan_key)
    if cached_plan:
        print(colored(f"Retrieved mitigation plan from cache for {symptom}.", "green"))
        return cached_plan
    
    prompt = f"""
You are a doctor speaking to a parent. Generate a mitigation plan for a {age}-year-old ({weight or 'unknown'} kg) with {symptom}. The plan must have exactly two paragraphs separated by a single newline, each under 400 characters.

**Dosage Paragraph:**
- Start with "Hello!"
- Include precise dosing for {drug1_name_display} and {drug2_name_display} using the exact details below.
- End with "Follow doctor’s advice!"

**Interactions Paragraph:**
- Start with "Caution! "
- Summarize food/alcohol interactions using the exact details below. If none, state "No interactions."
- End with "Consult a doctor!"

**Input:**
- {drug1_name_display} Dosage: {drug1_dosage_concise}
- {drug1_name_display} Interactions: {drug1_interaction_summary}
- {drug2_name_display} Dosage: {drug2_dosage_concise}
- {drug2_name_display} Interactions: {drug2_interaction_summary}
"""
    
    for attempt in range(3):
        try:
            print(colored(f"Attempting to generate plan (attempt {attempt + 1}/3) with Llama-3.2-3B-Instruct...", "cyan"))
            sampling_params = {
                "temperature": 0.1,
                "top_p": 0.9,
                "max_tokens": 200,
                "min_tokens": 100,
            }
            plan = rag_client.generate_text(prompt, sampling_params)
            print(colored(f"Raw plan: {repr(plan)}", "cyan"))
            plan = re.sub(r'^(?:assistant|user|system|<\|[^>]*\|>)+[\s\n]*', '', plan, flags=re.MULTILINE | re.IGNORECASE)
            paragraphs = [p.strip() for p in plan.split('\n') if p.strip()]
            print(colored(f"Parsed paragraphs: {paragraphs}", "cyan"))
            if (len(paragraphs) == 2 and
                paragraphs[0].startswith("Hello!") and
                paragraphs[0].endswith("Follow doctor’s advice!") and
                paragraphs[1].startswith("Caution! ") and
                paragraphs[1].endswith("Consult a doctor!") and
                len(paragraphs[0]) <= 400 and len(paragraphs[1]) <= 400):
                print(colored("Plan generated successfully.", "green"))
                final_plan = f"Dosage Plan:\n{paragraphs[0]}\n\nInteraction Plan:\n{paragraphs[1]}"
                rag_client.store_plan_in_cache(plan_key, final_plan)
                return final_plan
            else:
                print(colored(f"Generated plan is invalid (paragraphs: {len(paragraphs)}), retrying...", "yellow"))
        except Exception as e:
            print(colored(f"Error generating plan (attempt {attempt + 1}/3): {e}", "yellow"))
            traceback.print_exc()
        if attempt < 2:
            time.sleep(0.5 * (2 ** attempt))
    
    print(colored("Using fallback plan due to generation failure.", "yellow"))
    dosage_fallback = (
        f"Hello! For your {age}-year-old with {symptom}, give {drug1_name_display} ({drug1_dosage_concise}) or "
        f"{drug2_name_display} ({drug2_dosage_concise}). Follow doctor’s advice!"
    )
    interaction_fallback = (
        f"Caution! {drug1_name_display}: {drug1_interaction_summary} {drug2_name_display}: {drug2_interaction_summary} Consult a doctor!"
    )
    if len(dosage_fallback) > 400:
        dosage_fallback = dosage_fallback[:397] + "..."
    if len(interaction_fallback) > 400:
        interaction_fallback = interaction_fallback[:397] + "..."
    final_plan = f"Dosage Plan:\n{dosage_fallback}\n\nInteraction Plan:\n{interaction_fallback}"
    rag_client.store_plan_in_cache(plan_key, final_plan)
    return final_plan

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(colored("\n🛑 Execution interrupted by user.", "red"))
    except Exception as e:
        print(colored(f"\n❌ Error: {e}", "red"))
        traceback.print_exc()