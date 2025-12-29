#!/usr/bin/env python3
"""
Test script to examine Merck website structure and improve extraction.
"""

import requests
import time
from bs4 import BeautifulSoup
import json
import re

def test_merck_page():
    """Test extraction from Merck pipeline page."""
    url = "https://www.merck.com/research/product-pipeline/"
    
    print(f"Testing Merck pipeline page: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        print(f"Status Code: {response.status_code}")
        print(f"Content Length: {len(response.text)}")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for common pipeline data patterns
        print("\n=== SEARCHING FOR MERCK PIPELINE DATA PATTERNS ===")
        
        # 1. Look for tables
        tables = soup.find_all('table')
        print(f"Tables found: {len(tables)}")
        for i, table in enumerate(tables[:5]):  # Show first 5 tables
            print(f"\nTable {i+1}:")
            rows = table.find_all('tr')[:5]  # First 5 rows
            for j, row in enumerate(rows):
                cells = [cell.get_text().strip()[:80] for cell in row.find_all(['td', 'th'])]
                if cells:  # Only show non-empty rows
                    print(f"  Row {j+1}: {cells}")
        
        # 2. Look for divs with pipeline-related classes or IDs
        pipeline_divs = soup.find_all(['div', 'section'], 
                                     class_=re.compile(r'pipeline|product|drug|compound|card|item|program', re.I))
        print(f"\nPipeline-related divs by class: {len(pipeline_divs)}")
        
        # Also look by ID
        pipeline_ids = soup.find_all(['div', 'section'], 
                                    id=re.compile(r'pipeline|product|drug|compound|program', re.I))
        print(f"Pipeline-related divs by ID: {len(pipeline_ids)}")
        
        # 3. Look for specific phase mentions
        phase_patterns = ['Phase 1', 'Phase 2', 'Phase 3', 'Phase I', 'Phase II', 'Phase III']
        phase_counts = {}
        for phase in phase_patterns:
            count = response.text.count(phase)
            if count > 0:
                phase_counts[phase] = count
        
        print(f"\nPhase mentions found: {phase_counts}")
        
        # 4. Look for JSON data in script tags
        scripts = soup.find_all('script')
        json_scripts = []
        for script in scripts:
            if script.string and ('pipeline' in script.string.lower() or 'phase' in script.string.lower()):
                json_scripts.append(script.string[:300])
        
        print(f"\nScript tags with potential pipeline data: {len(json_scripts)}")
        for i, script in enumerate(json_scripts[:3]):
            print(f"Script {i+1}: {script}...")
        
        # 5. Look for specific pharmaceutical terms
        pharma_terms = ['compound', 'indication', 'oncology', 'diabetes', 'clinical trial', 'FDA', 'approval']
        term_counts = {}
        for term in pharma_terms:
            count = response.text.lower().count(term.lower())
            if count > 0:
                term_counts[term] = count
        
        print(f"\nPharmaceutical terms found: {term_counts}")
        
        # 6. Look for accordion/collapsible content (common for pipeline pages)
        accordions = soup.find_all(['div', 'section'], 
                                  class_=re.compile(r'accordion|collapse|expand|toggle', re.I))
        print(f"\nAccordion/collapsible elements: {len(accordions)}")
        
        # 7. Look for data attributes that might contain pipeline info
        data_attrs = soup.find_all(attrs=lambda x: x and any(
            k.startswith('data-') and any(term in k.lower() for term in ['phase', 'compound', 'program'])
            for k in x.keys()
        ))
        print(f"Elements with pipeline data attributes: {len(data_attrs)}")
        
        # 8. Search for specific compound patterns (MK-xxxx, etc.)
        compound_patterns = [
            r'\bMK-\d+',  # Merck compounds like MK-1234
            r'\bV\d+',    # V-series compounds
            r'\b[A-Z]{2,}-\d+',  # General compound codes
        ]
        
        all_compounds = set()
        for pattern in compound_patterns:
            matches = re.findall(pattern, response.text)
            all_compounds.update(matches)
        
        print(f"\nCompound codes found: {len(all_compounds)}")
        if all_compounds:
            print(f"Sample compounds: {list(all_compounds)[:10]}")
        
        # 9. Look for structured data sections
        structured_sections = soup.find_all(['section', 'div'], 
                                          attrs={'data-section': True})
        print(f"\nStructured data sections: {len(structured_sections)}")
        
        # 10. Save sample HTML for manual inspection
        with open('merck_pipeline_sample.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        print(f"\nSaved full HTML to merck_pipeline_sample.html")
        
        return response.text
        
    except Exception as e:
        print(f"Error testing Merck page: {e}")
        return None

def main():
    """Test Merck page and analyze patterns."""
    print("=== MERCK PIPELINE EXTRACTION ANALYSIS ===\n")
    test_merck_page()

if __name__ == "__main__":
    main()