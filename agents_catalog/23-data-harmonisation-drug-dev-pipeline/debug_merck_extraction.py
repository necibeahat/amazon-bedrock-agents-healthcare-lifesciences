#!/usr/bin/env python3
"""
Debug script to analyze why Merck extraction is only returning 4 entries instead of 85+.
"""

import sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import logging

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.agents.web_scraper.extractors import MerckExtractor

# Configure detailed logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(message)s')

def debug_merck_extraction():
    """Debug the Merck extraction process step by step."""
    print("=== DEBUGGING MERCK EXTRACTION ===")
    
    # Fetch the Merck page
    url = "https://www.merck.com/research/product-pipeline/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    print(f"Fetching: {url}")
    response = requests.get(url, headers=headers, timeout=30)
    print(f"Status: {response.status_code}")
    print(f"Content length: {len(response.text)}")
    
    # Create extractor and run extraction
    extractor = MerckExtractor()
    
    # Parse HTML first
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Debug table extraction specifically
    print("\n=== DEBUGGING TABLE EXTRACTION ===")
    tables = soup.find_all('table')
    print(f"Found {len(tables)} tables")
    
    all_entries = []
    
    for i, table in enumerate(tables):
        print(f"\n--- Processing Table {i+1} ---")
        
        rows = table.find_all('tr')
        print(f"Table {i+1} has {len(rows)} rows")
        
        if len(rows) < 2:
            print(f"Skipping table {i+1} - not enough rows")
            continue
        
        # Check headers
        header_row = rows[0]
        headers = [extractor._clean_text(th.get_text()) for th in header_row.find_all(['th', 'td'])]
        print(f"Headers: {headers}")
        
        # Check if this looks like a pipeline table
        header_text = ' '.join(headers).lower()
        has_pipeline_terms = any(term in header_text for term in ['molecule', 'compound', 'indication', 'phase', 'therapeutic', 'status'])
        print(f"Has pipeline terms: {has_pipeline_terms}")
        
        if not has_pipeline_terms:
            print(f"Skipping table {i+1} - no pipeline terms in headers")
            continue
        
        # Process data rows
        print(f"Processing {len(rows)-1} data rows...")
        
        for row_idx, row in enumerate(rows[1:], 1):
            cells = row.find_all(['td', 'th'])
            if not cells:
                continue
            
            cell_texts = [extractor._clean_text(cell.get_text()) for cell in cells]
            print(f"  Row {row_idx}: {cell_texts}")
            
            # Try to extract entry data
            entry_data = {}
            
            # Map to standard fields
            for j, cell_text in enumerate(cell_texts):
                if not cell_text:
                    continue
                
                if j < len(headers):
                    header = headers[j].lower()
                    if any(term in header for term in ['molecule', 'compound', 'drug', 'name']):
                        entry_data['compound_name'] = cell_text
                    elif any(term in header for term in ['indication', 'disease', 'condition']):
                        entry_data['indication'] = cell_text
                    elif any(term in header for term in ['phase', 'stage', 'status']):
                        entry_data['development_phase'] = cell_text
                    elif any(term in header for term in ['therapeutic', 'area', 'category']):
                        entry_data['therapeutic_area'] = cell_text
                    elif any(term in header for term in ['modality', 'mechanism', 'action']):
                        entry_data['mechanism_of_action'] = cell_text
                
                # Also try pattern matching
                if extractor._looks_like_compound_name(cell_text):
                    entry_data['compound_name'] = cell_text
                elif extractor._looks_like_indication(cell_text):
                    entry_data['indication'] = cell_text
                elif extractor._looks_like_phase(cell_text):
                    phase = extractor._extract_phase(cell_text)
                    if phase:
                        entry_data['development_phase'] = phase
                elif extractor._looks_like_therapeutic_area(cell_text):
                    entry_data['therapeutic_area'] = cell_text
            
            print(f"    Extracted data: {entry_data}")
            
            # Check if meaningful
            has_meaningful = extractor._has_meaningful_data(entry_data)
            print(f"    Has meaningful data: {has_meaningful}")
            
            if has_meaningful:
                entry = extractor._create_pipeline_entry(entry_data)
                if entry:
                    all_entries.append(entry)
                    print(f"    ✓ Created entry: {entry.compound_name} - {entry.indication}")
                else:
                    print(f"    ✗ Failed to create entry")
            else:
                print(f"    ✗ Not meaningful data")
    
    print(f"\n=== EXTRACTION SUMMARY ===")
    print(f"Total entries before deduplication: {len(all_entries)}")
    
    # Test deduplication
    deduplicated = extractor._deduplicate_entries(all_entries)
    print(f"Total entries after deduplication: {len(deduplicated)}")
    
    for i, entry in enumerate(deduplicated):
        print(f"  {i+1}. {entry.compound_name} - {entry.indication} - {entry.development_phase}")
    
    # Now run the full extraction to compare
    print(f"\n=== FULL EXTRACTION COMPARISON ===")
    result = extractor.extract(response.text)
    print(f"Full extraction returned: {len(result.entries)} entries")
    print(f"Confidence score: {result.confidence_score}")
    print(f"Errors: {result.errors}")
    
    for i, entry in enumerate(result.entries):
        print(f"  {i+1}. {entry.compound_name} - {entry.indication} - {entry.development_phase}")

if __name__ == "__main__":
    debug_merck_extraction()