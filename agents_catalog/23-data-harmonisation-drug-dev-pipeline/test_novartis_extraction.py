#!/usr/bin/env python3
"""
Test script to examine Novartis website structure and improve extraction.
"""

import requests
import time
from bs4 import BeautifulSoup
import json

def test_novartis_page(page_num=0):
    """Test extraction from a single Novartis page."""
    url = f"https://www.novartis.com/research-development/novartis-pipeline?page={page_num}"
    
    print(f"Testing Novartis page {page_num}: {url}")
    
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
        print("\n=== SEARCHING FOR PIPELINE DATA PATTERNS ===")
        
        # 1. Look for tables
        tables = soup.find_all('table')
        print(f"Tables found: {len(tables)}")
        for i, table in enumerate(tables[:3]):  # Show first 3 tables
            print(f"Table {i+1} preview:")
            rows = table.find_all('tr')[:3]  # First 3 rows
            for j, row in enumerate(rows):
                cells = [cell.get_text().strip()[:50] for cell in row.find_all(['td', 'th'])]
                print(f"  Row {j+1}: {cells}")
        
        # 2. Look for divs with pipeline-related classes
        pipeline_divs = soup.find_all(['div', 'section'], class_=lambda x: x and any(
            term in str(x).lower() for term in ['pipeline', 'product', 'drug', 'compound', 'asset']
        ))
        print(f"\nPipeline-related divs: {len(pipeline_divs)}")
        for i, div in enumerate(pipeline_divs[:3]):
            text = div.get_text().strip()[:100]
            print(f"Div {i+1}: {text}...")
        
        # 3. Look for JSON data in script tags
        scripts = soup.find_all('script')
        json_scripts = []
        for script in scripts:
            if script.string and ('pipeline' in script.string.lower() or 'product' in script.string.lower()):
                json_scripts.append(script.string[:200])
        
        print(f"\nScript tags with potential JSON data: {len(json_scripts)}")
        for i, script in enumerate(json_scripts[:2]):
            print(f"Script {i+1}: {script}...")
        
        # 4. Look for specific pharmaceutical terms
        pharma_terms = ['phase', 'indication', 'compound', 'drug', 'clinical', 'trial', 'oncology', 'diabetes']
        term_counts = {}
        for term in pharma_terms:
            count = response.text.lower().count(term)
            if count > 0:
                term_counts[term] = count
        
        print(f"\nPharmaceutical terms found: {term_counts}")
        
        # 5. Look for structured data (JSON-LD, microdata)
        json_ld = soup.find_all('script', type='application/ld+json')
        print(f"\nJSON-LD scripts: {len(json_ld)}")
        
        # 6. Look for data attributes
        data_attrs = soup.find_all(attrs=lambda x: x and any(k.startswith('data-') for k in x.keys()))
        print(f"Elements with data attributes: {len(data_attrs)}")
        
        # 7. Save a sample of the HTML for manual inspection
        with open(f'novartis_page_{page_num}_sample.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        print(f"\nSaved full HTML to novartis_page_{page_num}_sample.html")
        
        return response.text
        
    except Exception as e:
        print(f"Error testing page {page_num}: {e}")
        return None

def main():
    """Test multiple pages and analyze patterns."""
    print("=== NOVARTIS PIPELINE EXTRACTION ANALYSIS ===\n")
    
    # Test first few pages
    for page in range(3):  # Test pages 0, 1, 2
        print(f"\n{'='*60}")
        test_novartis_page(page)
        if page < 2:  # Don't sleep after last page
            time.sleep(2)  # Be respectful with requests

if __name__ == "__main__":
    main()