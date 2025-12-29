#!/usr/bin/env python3
"""
Analyze the Merck extraction results to see what phases we're getting.
"""

import json
import sys
from pathlib import Path
from collections import Counter

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

def analyze_merck_results():
    """Analyze the Merck extraction results."""
    print("=== ANALYZING MERCK EXTRACTION RESULTS ===")
    
    # Load the results
    with open('pipeline_results.json', 'r') as f:
        results = json.load(f)
    
    # Find Merck data
    merck_data = None
    for source in results['raw_data_collection']['sources']:
        if source['company'] == 'Merck':
            merck_data = source
            break
    
    if not merck_data:
        print("No Merck data found in results")
        return
    
    print(f"Total Merck entries: {merck_data['entries_count']}")
    
    # Load the detailed data
    with open('pipeline_results.json', 'r') as f:
        full_results = json.load(f)
    
    # Extract Merck entries from harmonized data
    harmonized_entries = full_results.get('harmonization_results', {}).get('canonical_entries', [])
    
    merck_entries = []
    for entry in harmonized_entries:
        if 'Merck' in str(entry.get('source_companies', [])):
            merck_entries.append(entry)
    
    print(f"Merck entries in harmonized data: {len(merck_entries)}")
    
    # Analyze phases
    phases = []
    compounds = []
    indications = []
    
    for entry in merck_entries:
        if entry.get('development_phase'):
            phases.append(entry['development_phase'])
        if entry.get('compound_name'):
            compounds.append(entry['compound_name'])
        if entry.get('indication'):
            indications.append(entry['indication'])
    
    print(f"\nPhase distribution:")
    phase_counts = Counter(phases)
    for phase, count in phase_counts.most_common():
        print(f"  {phase}: {count}")
    
    print(f"\nSample compounds:")
    for compound in compounds[:10]:
        print(f"  - {compound}")
    
    print(f"\nSample indications:")
    for indication in indications[:5]:
        print(f"  - {indication[:100]}...")
    
    # Check if we're meeting targets
    phase_2_count = sum(count for phase, count in phase_counts.items() if 'Phase 2' in str(phase) or 'phase-2' in str(phase))
    phase_3_count = sum(count for phase, count in phase_counts.items() if 'Phase 3' in str(phase) or 'phase-3' in str(phase))
    under_review_count = sum(count for phase, count in phase_counts.items() if 'Under Review' in str(phase) or 'under-review' in str(phase))
    
    print(f"\nTarget Analysis:")
    print(f"  Phase 2 programs: {phase_2_count} (target: 50+)")
    print(f"  Phase 3 programs: {phase_3_count} (target: 30+)")
    print(f"  Under Review programs: {under_review_count} (target: 5+)")
    print(f"  Total: {phase_2_count + phase_3_count + under_review_count} (target: 85+)")
    
    if phase_2_count + phase_3_count + under_review_count >= 85:
        print("✓ TARGET ACHIEVED!")
    else:
        print("✗ Still below target - need more extraction")

if __name__ == "__main__":
    analyze_merck_results()