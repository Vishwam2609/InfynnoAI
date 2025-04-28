import re
import requests
from bs4 import BeautifulSoup
from retry_manager import RetryManager

class WebScraper:
    def __init__(self):
        self.session = requests.Session()
        self.retry_manager = RetryManager(max_attempts=2, backoff_factor=0.2)  # 1 retry + original attempt
        self.retry_manager.configure_session(self.session)

    def scrape_drug_data(self, drug_name):
        url = f"https://www.drugs.com/dosage/{drug_name.replace(' ', '-').lower()}.html"
        print(f"Scraping dosage URL: {url}")
        try:
            r = self.session.get(url, timeout=10)
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            print(f"Failed to fetch {drug_name} dosage: {e}")
            return None

    def scrape_food_interaction_data(self, drug_name):
        url = f"https://www.drugs.com/food-interactions/{drug_name.replace(' ', '-').lower()}.html"
        print(f"Scraping interactions URL: {url}")
        try:
            r = self.session.get(url, timeout=10)
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
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