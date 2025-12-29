"""Duplicate resolution component for the Data Harmonizer Agent."""

import logging
from collections import defaultdict
from typing import Any, Dict, List, Set, Tuple

from ...models.harmonization import DeduplicatedData, DuplicateGroup, EnrichedData

logger = logging.getLogger(__name__)


class DuplicateResolver:
    """Resolves duplicate entries in enriched pharmaceutical data."""
    
    def __init__(self):
        """Initialize the duplicate resolver."""
        # Field weights for similarity calculation
        self.field_weights = {
            'compound_name': 0.3,
            'indication': 0.25,
            'company': 0.15,
            'development_phase': 0.1,
            'therapeutic_area': 0.1,
            'mechanism_of_action': 0.05,
            'internal_id': 0.05
        }
        
        # Similarity thresholds
        self.similarity_thresholds = {
            'high': 0.85,    # Very likely duplicates
            'medium': 0.70,  # Possible duplicates
            'low': 0.55      # Unlikely but worth checking
        }
        
        # Normalization patterns for better matching
        self.normalization_patterns = {
            'compound_name': [
                (r'\s+', ' '),  # Multiple spaces to single space
                (r'[^\w\s-]', ''),  # Remove special characters except hyphens
                (r'\b(the|a|an)\b', ''),  # Remove articles
            ],
            'indication': [
                (r'\s+', ' '),
                (r'[^\w\s-]', ''),
                (r'\b(disease|disorder|syndrome|condition)\b', ''),  # Remove common suffixes
            ],
            'company': [
                (r'\s+', ' '),
                (r'[^\w\s&-]', ''),
                (r'\b(inc|ltd|llc|corp|corporation|company|co)\b', ''),  # Remove company suffixes
            ]
        }
    
    def resolve_duplicates(self, enriched_data_list: List[EnrichedData]) -> DeduplicatedData:
        """Resolve duplicate entries in enriched data.
        
        Args:
            enriched_data_list: List of enriched data entries
            
        Returns:
            DeduplicatedData with resolved duplicates
        """
        logger.info(f"Resolving duplicates in {len(enriched_data_list)} enriched data entries")
        
        if not enriched_data_list:
            return DeduplicatedData(
                canonical_entries=[],
                duplicate_groups=[],
                total_original_entries=0,
                total_canonical_entries=0,
                deduplication_metadata={'method': 'empty_input'}
            )
        
        # Find duplicate groups
        duplicate_groups = self._find_duplicate_groups(enriched_data_list)
        
        # Create canonical entries
        canonical_entries = self._create_canonical_entries(enriched_data_list, duplicate_groups)
        
        # Enrich canonical entries with additional metadata
        enriched_canonical_entries = self._enrich_canonical_entries(canonical_entries, duplicate_groups)
        
        # Calculate deduplication statistics
        deduplication_metadata = self._calculate_deduplication_metadata(
            enriched_data_list, duplicate_groups, canonical_entries
        )
        
        deduplicated_data = DeduplicatedData(
            canonical_entries=enriched_canonical_entries,
            duplicate_groups=duplicate_groups,
            total_original_entries=len(enriched_data_list),
            total_canonical_entries=len(canonical_entries),
            deduplication_metadata=deduplication_metadata
        )
        
        logger.info(
            f"Duplicate resolution complete: {len(enriched_data_list)} -> {len(canonical_entries)} entries, "
            f"{len(duplicate_groups)} duplicate groups"
        )
        
        return deduplicated_data
    
    def _find_duplicate_groups(self, enriched_data_list: List[EnrichedData]) -> List[DuplicateGroup]:
        """Find groups of duplicate entries.
        
        Args:
            enriched_data_list: List of enriched data entries
            
        Returns:
            List of DuplicateGroup objects
        """
        duplicate_groups = []
        processed_ids = set()
        
        for i, entry1 in enumerate(enriched_data_list):
            if entry1.id in processed_ids:
                continue
            
            # Find all entries similar to this one
            similar_entries = [entry1]
            similar_ids = {entry1.id}
            
            for j, entry2 in enumerate(enriched_data_list[i+1:], i+1):
                if entry2.id in processed_ids:
                    continue
                
                similarity_score = self._calculate_similarity(entry1, entry2)
                
                if similarity_score >= self.similarity_thresholds['medium']:
                    similar_entries.append(entry2)
                    similar_ids.add(entry2.id)
            
            # If we found duplicates, create a duplicate group
            if len(similar_entries) > 1:
                # Choose canonical entry (highest confidence score)
                canonical_entry = max(similar_entries, key=lambda x: x.confidence_score)
                
                # Calculate group similarity score
                group_similarity = self._calculate_group_similarity(similar_entries)
                
                duplicate_group = DuplicateGroup(
                    entries=list(similar_ids),
                    canonical_entry_id=canonical_entry.id,
                    similarity_score=group_similarity,
                    resolution_method='confidence_based'
                )
                duplicate_groups.append(duplicate_group)
                
                # Mark all entries in this group as processed
                processed_ids.update(similar_ids)
            else:
                # Single entry, mark as processed
                processed_ids.add(entry1.id)
        
        return duplicate_groups
    
    def _calculate_similarity(self, entry1: EnrichedData, entry2: EnrichedData) -> float:
        """Calculate similarity score between two enriched data entries.
        
        Args:
            entry1: First enriched data entry
            entry2: Second enriched data entry
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        data1 = entry1.unified_data
        data2 = entry2.unified_data
        
        total_weight = 0.0
        weighted_similarity = 0.0
        
        # Compare each field with its weight
        for field, weight in self.field_weights.items():
            if field in data1 and field in data2:
                value1 = data1[field]
                value2 = data2[field]
                
                if value1 and value2:
                    field_similarity = self._calculate_field_similarity(field, value1, value2)
                    weighted_similarity += field_similarity * weight
                    total_weight += weight
        
        # Normalize by total weight
        if total_weight > 0:
            similarity = weighted_similarity / total_weight
        else:
            similarity = 0.0
        
        # Bonus for ontology mapping overlap
        ontology_bonus = self._calculate_ontology_overlap_bonus(entry1, entry2)
        similarity = min(1.0, similarity + ontology_bonus)
        
        return round(similarity, 3)
    
    def _calculate_field_similarity(self, field_name: str, value1: Any, value2: Any) -> float:
        """Calculate similarity between two field values.
        
        Args:
            field_name: Name of the field
            value1: First value
            value2: Second value
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if value1 == value2:
            return 1.0
        
        # Convert to strings for comparison
        str1 = str(value1).strip().lower()
        str2 = str(value2).strip().lower()
        
        if not str1 or not str2:
            return 0.0
        
        # Normalize strings based on field type
        if field_name in self.normalization_patterns:
            str1 = self._normalize_string(str1, field_name)
            str2 = self._normalize_string(str2, field_name)
        
        # Exact match after normalization
        if str1 == str2:
            return 1.0
        
        # Calculate string similarity
        return self._calculate_string_similarity(str1, str2)
    
    def _normalize_string(self, text: str, field_name: str) -> str:
        """Normalize a string based on field-specific patterns.
        
        Args:
            text: Text to normalize
            field_name: Name of the field
            
        Returns:
            Normalized text
        """
        import re
        
        normalized = text.lower().strip()
        
        if field_name in self.normalization_patterns:
            for pattern, replacement in self.normalization_patterns[field_name]:
                normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
        
        return normalized.strip()
    
    def _calculate_string_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings using multiple methods.
        
        Args:
            str1: First string
            str2: Second string
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Jaccard similarity (word-based)
        words1 = set(str1.split())
        words2 = set(str2.split())
        
        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        jaccard_similarity = intersection / union if union > 0 else 0.0
        
        # Levenshtein similarity (character-based)
        levenshtein_similarity = self._levenshtein_similarity(str1, str2)
        
        # Substring similarity
        substring_similarity = self._substring_similarity(str1, str2)
        
        # Weighted combination
        similarity = (
            jaccard_similarity * 0.5 +
            levenshtein_similarity * 0.3 +
            substring_similarity * 0.2
        )
        
        return round(similarity, 3)
    
    def _levenshtein_similarity(self, str1: str, str2: str) -> float:
        """Calculate Levenshtein similarity between two strings.
        
        Args:
            str1: First string
            str2: Second string
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if str1 == str2:
            return 1.0
        
        len1, len2 = len(str1), len(str2)
        if len1 == 0 or len2 == 0:
            return 0.0
        
        # Create distance matrix
        matrix = [[0] * (len2 + 1) for _ in range(len1 + 1)]
        
        # Initialize first row and column
        for i in range(len1 + 1):
            matrix[i][0] = i
        for j in range(len2 + 1):
            matrix[0][j] = j
        
        # Fill the matrix
        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                if str1[i-1] == str2[j-1]:
                    cost = 0
                else:
                    cost = 1
                
                matrix[i][j] = min(
                    matrix[i-1][j] + 1,      # deletion
                    matrix[i][j-1] + 1,      # insertion
                    matrix[i-1][j-1] + cost  # substitution
                )
        
        # Convert distance to similarity
        max_len = max(len1, len2)
        distance = matrix[len1][len2]
        similarity = 1.0 - (distance / max_len)
        
        return max(0.0, similarity)
    
    def _substring_similarity(self, str1: str, str2: str) -> float:
        """Calculate substring similarity between two strings.
        
        Args:
            str1: First string
            str2: Second string
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if str1 in str2 or str2 in str1:
            shorter = min(len(str1), len(str2))
            longer = max(len(str1), len(str2))
            return shorter / longer if longer > 0 else 0.0
        
        return 0.0
    
    def _calculate_ontology_overlap_bonus(self, entry1: EnrichedData, entry2: EnrichedData) -> float:
        """Calculate bonus score based on ontology mapping overlap.
        
        Args:
            entry1: First enriched data entry
            entry2: Second enriched data entry
            
        Returns:
            Bonus score between 0.0 and 0.2
        """
        mappings1 = {
            (m.field_name, ontology, ont_id) 
            for m in entry1.ontology_mappings 
            for ontology, ont_id in m.ontology_mappings.items()
        }
        
        mappings2 = {
            (m.field_name, ontology, ont_id) 
            for m in entry2.ontology_mappings 
            for ontology, ont_id in m.ontology_mappings.items()
        }
        
        if not mappings1 or not mappings2:
            return 0.0
        
        overlap = len(mappings1.intersection(mappings2))
        total = len(mappings1.union(mappings2))
        
        if total > 0:
            overlap_ratio = overlap / total
            return min(0.2, overlap_ratio * 0.2)  # Max 0.2 bonus
        
        return 0.0
    
    def _calculate_group_similarity(self, entries: List[EnrichedData]) -> float:
        """Calculate average similarity within a group of entries.
        
        Args:
            entries: List of entries in the group
            
        Returns:
            Average similarity score
        """
        if len(entries) < 2:
            return 1.0
        
        similarities = []
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                similarity = self._calculate_similarity(entries[i], entries[j])
                similarities.append(similarity)
        
        return sum(similarities) / len(similarities) if similarities else 0.0
    
    def _create_canonical_entries(
        self, 
        enriched_data_list: List[EnrichedData], 
        duplicate_groups: List[DuplicateGroup]
    ) -> List[EnrichedData]:
        """Create list of canonical entries from original data and duplicate groups.
        
        Args:
            enriched_data_list: Original list of enriched data
            duplicate_groups: List of identified duplicate groups
            
        Returns:
            List of canonical entries
        """
        canonical_entries = []
        grouped_ids = set()
        
        # Add canonical entries from duplicate groups
        for group in duplicate_groups:
            canonical_entry = next(
                entry for entry in enriched_data_list 
                if entry.id == group.canonical_entry_id
            )
            canonical_entries.append(canonical_entry)
            grouped_ids.update(group.entries)
        
        # Add entries that are not part of any duplicate group
        for entry in enriched_data_list:
            if entry.id not in grouped_ids:
                canonical_entries.append(entry)
        
        return canonical_entries
    
    def _enrich_canonical_entries(
        self, 
        canonical_entries: List[EnrichedData], 
        duplicate_groups: List[DuplicateGroup]
    ) -> List[EnrichedData]:
        """Enrich canonical entries with additional metadata from duplicate resolution.
        
        Args:
            canonical_entries: List of canonical entries
            duplicate_groups: List of duplicate groups
            
        Returns:
            List of enriched canonical entries
        """
        # Create mapping from canonical entry ID to duplicate group
        canonical_to_group = {
            group.canonical_entry_id: group 
            for group in duplicate_groups
        }
        
        enriched_entries = []
        
        for entry in canonical_entries:
            # Create a copy of the entry
            enriched_entry = EnrichedData(
                id=entry.id,
                original_data=entry.original_data,
                unified_data=entry.unified_data.copy(),
                ontology_mappings=entry.ontology_mappings,
                enrichment_metadata=entry.enrichment_metadata.copy(),
                confidence_score=entry.confidence_score,
                enriched_at=entry.enriched_at
            )
            
            # Add duplicate resolution metadata
            if entry.id in canonical_to_group:
                group = canonical_to_group[entry.id]
                enriched_entry.enrichment_metadata.update({
                    'is_canonical_entry': True,
                    'duplicate_group_id': str(group.id),
                    'duplicate_count': len(group.entries) - 1,  # Exclude canonical entry itself
                    'group_similarity_score': group.similarity_score,
                    'resolution_method': group.resolution_method
                })
            else:
                enriched_entry.enrichment_metadata.update({
                    'is_canonical_entry': True,
                    'duplicate_count': 0,
                    'resolution_method': 'no_duplicates_found'
                })
            
            enriched_entries.append(enriched_entry)
        
        return enriched_entries
    
    def _calculate_deduplication_metadata(
        self,
        original_entries: List[EnrichedData],
        duplicate_groups: List[DuplicateGroup],
        canonical_entries: List[EnrichedData]
    ) -> Dict[str, Any]:
        """Calculate metadata about the deduplication process.
        
        Args:
            original_entries: Original list of entries
            duplicate_groups: List of duplicate groups
            canonical_entries: List of canonical entries
            
        Returns:
            Dictionary with deduplication metadata
        """
        total_duplicates_removed = len(original_entries) - len(canonical_entries)
        
        # Group statistics
        group_sizes = [len(group.entries) for group in duplicate_groups]
        avg_group_size = sum(group_sizes) / len(group_sizes) if group_sizes else 0.0
        max_group_size = max(group_sizes) if group_sizes else 0
        
        # Similarity statistics
        similarity_scores = [group.similarity_score for group in duplicate_groups]
        avg_similarity = sum(similarity_scores) / len(similarity_scores) if similarity_scores else 0.0
        
        # Company distribution
        company_distribution = defaultdict(int)
        for entry in canonical_entries:
            company = entry.unified_data.get('company', 'Unknown')
            company_distribution[company] += 1
        
        return {
            'deduplication_method': 'similarity_based_clustering',
            'total_original_entries': len(original_entries),
            'total_canonical_entries': len(canonical_entries),
            'total_duplicates_removed': total_duplicates_removed,
            'deduplication_rate': total_duplicates_removed / len(original_entries) if original_entries else 0.0,
            'duplicate_groups_count': len(duplicate_groups),
            'average_group_size': round(avg_group_size, 2),
            'max_group_size': max_group_size,
            'average_group_similarity': round(avg_similarity, 3),
            'similarity_threshold_used': self.similarity_thresholds['medium'],
            'company_distribution': dict(company_distribution),
            'resolver_version': '1.0'
        }