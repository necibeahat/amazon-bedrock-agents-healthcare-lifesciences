#!/usr/bin/env python3
"""
Debug script to analyze the new pattern-based Merck extraction.
"""

import sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import logging
import re

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.agents.web_scraper.extractors import MerckExtractor

# Configure detailed logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(message)s')

def debug_pattern_extraction():
    """Debug the pattern-based extraction process."""
    print("=== DEBUGGING MERCK PATTERN EXTRACTION ===")
    
    # Fetch the Merck page
    url = "https://www.merck.com/research/product-pipeline/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    print(f"Fetching: {url}")
    response = requests.get(url, headers=headers, timeout=30)
    print(f"Status: {response.status_code}")
    print(f"Content length: {len(response.text)}")
    
    # Create extractor
    extractor = MerckExtractor()
    
    # Test the pattern extraction directly
    print("\n=== TESTING PATTERN EXTRACTION ===")
    
    # Find compound codes using the improved pattern (Merck-specific)
    compound_pattern = r'\b(MK-\d+[A-Z]*|V\d+[A-Z]*)\b'  # More specific for Merck compounds
    compound_matches = list(re.finditer(compound_pattern, response.text))
    print(f"Found {len(compound_matches)} compound code matches")
    
    # Test first few matches
    for i, match in enumerate(compound_matches[:5]):
        compound_code = match.group(1)
        start_pos = match.start()
        
        # Get text block
        if i + 1 < len(compound_matches):
            end_pos = compound_matches[i + 1].start()
        else:
            end_pos = start_pos + 2000
        
        text_block = response.text[start_pos:end_pos]
        
        print(f"\n--- Compound {i+1}: {compound_code} ---")
        print(f"Text block (first 500 chars):")
        print(text_block[:500])
        print("...")
        
        # Test parsing
        try:
            entry = extractor._parse_merck_entry_block(compound_code, text_block)
            if entry:
                print(f"✓ Successfully parsed entry:")
                print(f"  Compound: {entry.compound_name}")
                print(f"  Indication: {entry.indication}")
                print(f"  Therapeutic Area: {entry.therapeutic_area}")
                print(f"  Phase: {entry.development_phase}")
                print(f"  MOA: {entry.mechanism_of_action}")
            else:
                print(f"✗ Failed to parse entry")
                
                # Debug why it failed
                entry_data = {'compound_name': compound_code}
                clean_text = extractor._clean_text(text_block)
                
                # Check therapeutic area
                therapeutic_match = re.search(r'Therapeutic area:\s*([^.]+?)(?:\s+Mechanism|$)', clean_text, re.IGNORECASE)
                if therapeutic_match:
                    print(f"  Found therapeutic area: {therapeutic_match.group(1).strip()}")
                    entry_data['therapeutic_area'] = therapeutic_match.group(1).strip()
                
                # Check indication
                indication_pattern = rf'{re.escape(compound_code)}\s+([^.]+?)\s+Therapeutic area'
                indication_match = re.search(indication_pattern, clean_text, re.IGNORECASE)
                if indication_match:
                    potential_indication = indication_match.group(1).strip()
                    print(f"  Found potential indication: {potential_indication}")
                    entry_data['indication'] = potential_indication
                
                # Alternative indication extraction
                indication_patterns = [
                    r'(atherosclerosis)',
                    r'(cancer|carcinoma|tumor|leukemia|lymphoma)',
                    r'(diabetes|diabetic)',
                    r'(alzheimer|dementia)',
                    r'(hypertension|cardiovascular)',
                    r'(arthritis|rheumatoid)',
                ]
                
                for pattern in indication_patterns:
                    match = re.search(pattern, clean_text, re.IGNORECASE)
                    if match:
                        print(f"  Found indication via pattern: {match.group(1)}")
                        entry_data['indication'] = match.group(1)
                        break
                
                # Check if meaningful
                has_meaningful = extractor._has_meaningful_merck_data(entry_data)
                print(f"  Has meaningful data: {has_meaningful}")
                print(f"  Entry data: {entry_data}")
                
        except Exception as e:
            print(f"✗ Exception during parsing: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    debug_pattern_extraction()