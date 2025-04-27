import re

def extract_dose_frequency(dosage_line):
    match = re.search(r'(\d+\s*(?:to\s*\d+\s*)?(?:mg|ml)).*?(every\s*\d+\s*(?:to\s*\d+\s*)?hours.*?not to exceed\s*\d+\s*doses\s*in\s*24\s*hours)', dosage_line, re.IGNORECASE)
    if match:
        dose = match.group(1)
        freq = match.group(2)
        freq = freq.replace("not to exceed", "max")
        freq = re.sub(r'in\s*24\s*hours', 'day', freq, flags=re.IGNORECASE)
        return f"{dose} {freq}"
    return dosage_line

def summarize_interaction(interaction_text, drug_name):
    if "no food/alcohol interactions found" in interaction_text.lower():
        return "No interactions."
    summary = []
    if "alcohol" in interaction_text.lower():
        if "acetaminophen" in drug_name.lower():
            summary.append("Avoid alcohol; liver risk.")
        elif "ibuprofen" in drug_name.lower() or "aspirin" in drug_name.lower():
            summary.append("Avoid alcohol; stomach bleeding.")
        else:
            summary.append("Avoid alcohol; sedation risk.")
    if "high blood pressure" in interaction_text.lower() or "hypertension" in interaction_text.lower():
        summary.append("Use cautiously with hypertension.")
    return " ".join(summary) if summary else "Check with doctor."