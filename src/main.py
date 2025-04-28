"""Main script for the Dosage Guidance Agent."""
import time
import hashlib
import logging
import re
import importlib
from termcolor import colored
from src.rag_client import RAGClient
from src.utils.text_processing import TextProcessor
from src.utils.validation import sanitize_input, restrict_numeric
from src.utils.logging_utils import setup_logging
from src.utils.config_loader import ConfigLoader
from dotenv import load_dotenv
import os
import traceback

def main():
    """Main function to run the Dosage Guidance Agent."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    load_dotenv()
    config_loader = ConfigLoader()
    config = config_loader.get_config()
    
    weaviate_url = os.getenv("WEAVIATE_URL")
    weaviate_api_key = os.getenv("WEAVIATE_API_KEY")
    embed_url = os.getenv("EMBED_URL")
    generate_url = os.getenv("GENERATE_URL")
    
    if not all([weaviate_url, weaviate_api_key, embed_url, generate_url]):
        logger.error("Missing environment variables.")
        print(colored("❌ Missing environment variables.", "red"))
        return
    
    rag_client = None
    try:
        rag_client = RAGClient(weaviate_url, weaviate_api_key, embed_url, generate_url)
        text_processor = TextProcessor()
        
        # Dynamically load agents
        agents = {}
        for coll_key, coll_config in config_loader.get_collection_config().items():
            agent_name = coll_config.get("agent")
            if agent_name and agent_name in config["AGENT_CLASSES"]:
                module_path, class_name = config["AGENT_CLASSES"][agent_name].rsplit(".", 1)
                module = importlib.import_module(module_path)
                agent_class = getattr(module, class_name)
                agents[coll_key] = agent_class(rag_client)
                logger.info(f"Loaded agent: {agent_name}")
        
        print(colored("\n👋 Welcome to the Dosage Guidance Agent!", "blue"))
        print("Extracts dosage & food/alcohol interactions for medications.")
        print(colored("⚠️ Not a substitute for professional medical advice.", "red"))
        print("-" * 60)
        
        while True:
            input_data = {}
            for field in config["INPUT_FIELDS"]:
                field_name = field["name"]
                prompt = field["prompt"]
                input_value = sanitize_input(input(colored(f"{prompt}: ", "cyan")).lower())
                logger.debug(f"Raw input for {field_name}: {input_value}")
                
                # Apply transformations
                for transform in field.get("transformations", []):
                    if re.match(transform["match"], input_value):
                        input_value = transform["replace"]
                        logger.debug(f"Transformed {field_name}: {input_value}")
                
                # Validate input
                validation = field.get("validation", {})
                if field["type"] == "text" and validation.get("type") == "enum":
                    if input_value not in validation["values"]:
                        logger.warning(f"Invalid {field_name}: {input_value}")
                        print(colored(f"❌ Invalid {field_name}. Please enter one of: {', '.join(validation['values'])}", "red"))
                        break
                    input_data[field_name] = input_value
                    logger.debug(f"Stored {field_name}: {input_value}")
                elif field["type"] == "numeric":
                    try:
                        if input_value:
                            num_value = restrict_numeric(input_value, validation["min"], validation["max"])
                            if num_value is None:
                                logger.warning(f"Invalid {field_name}: {input_value}")
                                print(colored(f"❌ {field_name} must be between {validation['min']} and {validation['max']}.", "red"))
                                break
                            input_data[field_name] = num_value
                            logger.debug(f"Stored {field_name}: {num_value}")
                        elif not field.get("optional", False):
                            logger.warning(f"Missing required {field_name}")
                            print(colored(f"❌ {field_name} is required.", "red"))
                            break
                    except ValueError:
                        logger.warning(f"Invalid {field_name} input: {input_value}")
                        print(colored(f"❌ {field_name} must be a number.", "red"))
                        break
                else:
                    input_data[field_name] = input_value
                    logger.debug(f"Stored {field_name}: {input_value}")
            else:
                # All inputs valid, proceed
                symptom = input_data.get("symptom")
                if not symptom:
                    logger.error("Symptom is None or missing")
                    print(colored("❌ Error: Symptom is required.", "red"))
                    continue
                
                age = input_data.get("age")
                weight = input_data.get("weight")
                age_group = "adult" if age >= 18 else "pediatric"
                
                logger.info(f"Processing: Symptom={symptom}, Age={age}, Group={age_group}, Weight={weight} kg")
                print(colored(
                    f"ℹ️ Symptom={symptom}, Age={age}, Group={age_group}"
                    f"{', Weight=' + str(weight) + ' kg' if weight else ''}",
                    "green"
                ))
                start_time = time.time()
                logger.info("Starting processing...")
                
                drugs = config["SYMPTOM_DRUGS"][symptom]
                drug_data = {}
                for d in drugs:
                    drug_data[d] = {}
                    for coll_key, agent in agents.items():
                        coll_config = config_loader.get_collection_config()[coll_key]
                        if coll_key == "DrugDosage":
                            extracted_data = agent.get_dosage(d, symptom, age_group)
                            logger.info(f"Fetched dosage for {d.capitalize()}")
                            print(colored(f"\n🔍 Dosage for {d.capitalize()}:\n{extracted_data}\n", "green"))
                            drug_data[d]["dosage_details"] = extracted_data
                        elif coll_key == "DrugInteractions":
                            extracted_data = agent.get_interactions(d)
                            logger.info(f"Fetched interactions for {d.capitalize()}")
                            print(colored(f"\n🔍 Interactions for {d.capitalize()}:\n{extracted_data}\n", "green"))
                            drug_data[d]["interactions"] = extracted_data
                
                logger.info("Generating mitigation plan")
                print(colored("🔍 Generating mitigation plan...", "blue"))
                plan = generate_mitigation_plan(rag_client, agents.get("DrugDosage"), text_processor, symptom, age, age_group, drug_data, weight)
                print(colored(f"\nMitigation Plan:\n{plan}\n", "green"))
                latency = time.time() - start_time
                logger.info(f"Processing took {latency:.2f} seconds")
                print(colored(f"Processing took {latency:.2f} seconds.", "green"))
                
                exit_choice = sanitize_input(input(colored("\nWould you like to exit? (yes/no): ", "cyan")).lower())
                if exit_choice == "yes":
                    logger.info("Exiting program")
                    print(colored("Exiting program...", "blue"))
                    break
                elif exit_choice == "no":
                    continue
                else:
                    logger.warning(f"Invalid exit choice: {exit_choice}")
                    print(colored("Invalid input. Assuming 'no'...", "yellow"))
                    continue
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        print(colored(f"\n❌ Error: {e}", "red"))
        traceback.print_exc()
    finally:
        if rag_client:
            rag_client.cleanup()

def generate_mitigation_plan(rag_client, dosage_agent, text_processor, symptom, age, age_group, drug_data, weight):
    """Generate a mitigation plan for the patient.

    Args:
        rag_client: RAGClient instance.
        dosage_agent: DrugDosageAgent instance.
        text_processor: TextProcessor instance.
        symptom (str): Symptom being treated.
        age (float): Patient age.
        age_group (str): Age group ('adult' or 'pediatric').
        drug_data (dict): Drug dosage and interaction data.
        weight (float): Patient weight in kg (optional).

    Returns:
        str: Mitigation plan with dosage and interaction details.
    """
    logger = logging.getLogger(__name__)
    drug_names = list(drug_data.keys())
    if len(drug_names) < 2:
        logger.error("Expected data for two drugs")
        print(colored("❌ Error: Expected data for two drugs.", "red"))
        return "Error: Insufficient drug data."
    
    drug1_name_key = drug_names[0].lower()
    drug2_name_key = drug_names[1].lower()
    
    drug1_info = drug_data[drug1_name_key]
    drug2_info = drug_data[drug2_name_key]
    
    drug1_name_display = drug1_name_key.capitalize()
    drug2_name_display = drug2_name_key.capitalize()
    
    drug1_dosage_line = dosage_agent.process_data(drug1_name_display, drug1_info.get('dosage_details', ''), weight, age)
    drug2_dosage_line = dosage_agent.process_data(drug2_name_display, drug2_info.get('dosage_details', ''), weight, age)
    drug1_dosage_concise = text_processor.extract_dose_frequency(drug1_dosage_line)
    drug2_dosage_concise = text_processor.extract_dose_frequency(drug2_dosage_line)
    
    drug1_interactions = drug1_info.get('interactions', 'No food/alcohol interactions found.')
    drug2_interactions = drug2_info.get('interactions', 'No food/alcohol interactions found.')
    drug1_interaction_summary = text_processor.summarize_interaction(drug1_interactions, drug1_name_display)
    drug2_interaction_summary = text_processor.summarize_interaction(drug2_interactions, drug2_name_display)
    
    plan_key = hashlib.md5(f"{symptom}:{age}:{weight}:{drug1_name_display}:{drug2_name_display}".encode()).hexdigest()
    cached_plan = rag_client.get_plan_from_cache(plan_key)
    if cached_plan:
        logger.info(f"Retrieved mitigation plan from cache for {symptom}")
        print(colored(f"Retrieved mitigation plan from cache for {symptom}.", "green"))
        return f"{cached_plan}\n\n⚠️ This is not a substitute for professional medical advice. Always consult a doctor."

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
            logger.info(f"Generating plan (attempt {attempt + 1}/3)")
            print(colored(f"Attempting to generate plan (attempt {attempt + 1}/3)...", "cyan"))
            sampling_params = {
                "temperature": 0.1,
                "top_p": 0.9,
                "max_tokens": 200,
                "min_tokens": 100,
            }
            plan = rag_client.generate_text(prompt, sampling_params)
            logger.debug(f"Raw plan: {repr(plan)}")
            plan = re.sub(r'^(?:assistant|user|system|<\|[^>]*\|>)+[\s\n]*', '', plan, flags=re.MULTILINE | re.IGNORECASE)
            paragraphs = [p.strip() for p in plan.split('\n') if p.strip()]
            logger.debug(f"Parsed paragraphs: {paragraphs}")
            if (len(paragraphs) == 2 and
                paragraphs[0].startswith("Hello!") and
                paragraphs[0].endswith("Follow doctor’s advice!") and
                paragraphs[1].startswith("Caution! ") and
                paragraphs[1].endswith("Consult a doctor!") and
                len(paragraphs[0]) <= 400 and len(paragraphs[1]) <= 400):
                logger.info("Plan generated successfully")
                print(colored("Plan generated successfully.", "green"))
                final_plan = f"Dosage Plan:\n{paragraphs[0]}\n\nInteraction Plan:\n{paragraphs[1]}"
                rag_client.store_plan_in_cache(plan_key, final_plan)
                return f"{final_plan}\n\n⚠️ This is not a substitute for professional medical advice. Always consult a doctor."
            else:
                logger.warning(f"Invalid plan (paragraphs: {len(paragraphs)}), retrying")
                print(colored(f"Generated plan is invalid (paragraphs: {len(paragraphs)}), retrying...", "yellow"))
        except Exception as e:
            logger.error(f"Error generating plan (attempt {attempt + 1}/3): {e}", exc_info=True)
            print(colored(f"Error generating plan (attempt {attempt + 1}/3): {e}", "yellow"))
        if attempt < 2:
            time.sleep(0.5 * (2 ** attempt))
    
    logger.warning("Using fallback plan due to generation failure")
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
    return f"{final_plan}\n\n⚠️ This is not a substitute for professional medical advice. Always consult a doctor."

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Execution interrupted by user")
        print(colored("\n🛑 Execution interrupted by user.", "red"))
    except Exception as e:
        logging.getLogger(__name__).error(f"Error: {e}", exc_info=True)
        print(colored(f"\n❌ Error: {e}", "red"))
        traceback.print_exc()