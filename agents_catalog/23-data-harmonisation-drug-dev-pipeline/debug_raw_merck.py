#!/usr/bin/env python3
"""
Debug the raw Merck data before harmonization.
"""

import sys
from pathlib import Path
import logging
import requests

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.agents.web_scraper.extractors import MerckExtractor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

def debug_raw_merck():
    """Debug the raw Merck data collection."""
    print("=== DEBUGGING RAW MERCK DATA ===")
    
    # Fetch Merck page
    url = "https://www.merck.com/research/product-pipeline/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    print(f"Fetching: {url}")
    response = requests.get(url, headers=headers, timeout=30)
    print(f"Status: {response.status_code}")
    
    # Extract using MerckExtractor
    extractor = MerckExtractor()
    result = extractor.extract(response.text)
    
    print(f"Raw Merck entries collected: {len(result.entries)}")
    print(f"Extraction method: {result.extraction_method}")
    print(f"Confidence score: {result.confidence_score}")
    
    if result.entries:
        print("\nFirst 5 entries:")
        for i, entry in enumerate(result.entries[:5]):
            print(f"\n--- Entry {i+1} ---")
            print(f"Compound: {entry.compound_name}")
            print(f"Indication: {entry.indication}")
            print(f"Therapeutic Area: {entry.therapeutic_area}")
            print(f"Phase: {entry.development_phase}")
            print(f"MOA: {entry.mechanism_of_action}")
            print(f"Status: {entry.status}")
        
        # Analyze phases
        phases = [entry.development_phase for entry in result.entries if entry.development_phase]
        print(f"\nPhases found: {len(phases)}")
        from collections import Counter
        phase_counts = Counter(phases)
        for phase, count in phase_counts.most_common():
            print(f"  {phase}: {count}")
        
        # Check for target phases
        phase_2_count = sum(count for phase, count in phase_counts.items() if phase and ('Phase 2' in str(phase) or 'phase-2' in str(phase) or '2' in str(phase)))
        phase_3_count = sum(count for phase, count in phase_counts.items() if phase and ('Phase 3' in str(phase) or 'phase-3' in str(phase) or '3' in str(phase)))
        under_review_count = sum(count for phase, count in phase_counts.items() if phase and ('Under Review' in str(phase) or 'under-review' in str(phase)))
        
        print(f"\nTarget Analysis (Raw Data):")
        print(f"  Phase 2 programs: {phase_2_count} (target: 50+)")
        print(f"  Phase 3 programs: {phase_3_count} (target: 30+)")
        print(f"  Under Review programs: {under_review_count} (target: 5+)")
        print(f"  Total: {phase_2_count + phase_3_count + under_review_count} (target: 85+)")
        
        # Show all unique phases
        print(f"\nAll unique phases found:")
        for phase in sorted(set(phases)):
            print(f"  - '{phase}'")
    
    else:
        print("No Merck data collected!")
        print(f"Errors: {result.errors}")

if __name__ == "__main__":
    debug_raw_merck()