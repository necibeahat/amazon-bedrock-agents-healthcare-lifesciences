"""Ontology mapping component for the Data Harmonizer Agent."""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from ...models.harmonization import EnrichedData, OntologyMapping, UnifiedDataModel
from ...models.pipeline_data import RawPipelineData

logger = logging.getLogger(__name__)


class OntologyMapper:
    """Maps pharmaceutical data to biomedical ontologies."""
    
    def __init__(self):
        """Initialize the ontology mapper."""
        # Ontology mapping patterns and rules
        self.ontology_patterns = {
            'MONDO': {
                'description': 'Monarch Disease Ontology',
                'patterns': self._get_mondo_patterns(),
                'prefix': 'MONDO:'
            },
            'ChEBI': {
                'description': 'Chemical Entities of Biological Interest',
                'patterns': self._get_chebi_patterns(),
                'prefix': 'CHEBI:'
            },
            'EFO': {
                'description': 'Experimental Factor Ontology',
                'patterns': self._get_efo_patterns(),
                'prefix': 'EFO:'
            },
            'NCIT': {
                'description': 'NCI Thesaurus',
                'patterns': self._get_ncit_patterns(),
                'prefix': 'NCIT:'
            },
            'MeSH': {
                'description': 'Medical Subject Headings',
                'patterns': self._get_mesh_patterns(),
                'prefix': 'MESH:'
            },
            'ATC': {
                'description': 'Anatomical Therapeutic Chemical Classification',
                'patterns': self._get_atc_patterns(),
                'prefix': 'ATC:'
            },
            'ICD10': {
                'description': 'International Classification of Diseases 10th Revision',
                'patterns': self._get_icd10_patterns(),
                'prefix': 'ICD10:'
            },
            'SNOMED': {
                'description': 'Systematized Nomenclature of Medicine Clinical Terms',
                'patterns': self._get_snomed_patterns(),
                'prefix': 'SCTID:'
            }
        }
        
        # Field to ontology mapping preferences
        self.field_ontology_preferences = {
            'indication': ['MONDO', 'ICD10', 'SNOMED', 'MeSH'],
            'therapeutic_area': ['EFO', 'MeSH', 'NCIT'],
            'compound_name': ['ChEBI', 'NCIT'],
            'compound_type': ['ChEBI', 'EFO'],
            'mechanism_of_action': ['NCIT', 'MeSH'],
            'development_phase': ['EFO', 'NCIT'],
            'regulatory_status': ['NCIT', 'EFO']
        }
    
    def apply_ontologies(self, raw_data: RawPipelineData, unified_model: UnifiedDataModel) -> EnrichedData:
        """Apply ontology mappings to raw data using unified model.
        
        Args:
            raw_data: Raw pipeline data to enrich
            unified_model: Unified model for field mapping
            
        Returns:
            EnrichedData with ontology mappings applied
        """
        logger.debug(f"Applying ontologies to data from {raw_data.source.company}")
        
        # Transform raw data to unified format
        unified_data = self._transform_to_unified_format(raw_data, unified_model)
        
        # Apply ontology mappings
        ontology_mappings = []
        
        for field_name, value in unified_data.items():
            if value and isinstance(value, str) and value.strip():
                mappings = self._map_field_to_ontologies(field_name, value.strip())
                ontology_mappings.extend(mappings)
        
        # Calculate confidence score
        confidence_score = self._calculate_enrichment_confidence(
            unified_data, ontology_mappings
        )
        
        enriched_data = EnrichedData(
            original_data=raw_data.content.extracted_data,
            unified_data=unified_data,
            ontology_mappings=ontology_mappings,
            enrichment_metadata={
                'source_company': raw_data.source.company,
                'source_url': str(raw_data.source.url),
                'transformation_method': 'unified_model_mapping',
                'ontology_mapper_version': '1.0',
                'total_mappings': len(ontology_mappings),
                'mapped_fields': list(set(mapping.field_name for mapping in ontology_mappings))
            },
            confidence_score=confidence_score
        )
        
        logger.debug(f"Applied {len(ontology_mappings)} ontology mappings with confidence {confidence_score:.3f}")
        return enriched_data
    
    def _transform_to_unified_format(self, raw_data: RawPipelineData, unified_model: UnifiedDataModel) -> Dict[str, Any]:
        """Transform raw data to unified format using field mappings.
        
        Args:
            raw_data: Raw pipeline data
            unified_model: Unified model with field mappings
            
        Returns:
            Dictionary with data in unified format
        """
        unified_data = {}
        source_company = raw_data.source.company
        
        # Get field mappings for this source
        source_mappings = unified_model.field_mappings.get(source_company, {})
        
        # Extract pipeline entries from raw data
        pipeline_entries = raw_data.content.extracted_data.get('pipeline_entries', [])
        
        if not pipeline_entries:
            # If no pipeline entries, try to use the entire extracted data
            pipeline_entries = [raw_data.content.extracted_data]
        
        # Process the first entry (or combine multiple entries)
        if pipeline_entries:
            source_data = pipeline_entries[0] if len(pipeline_entries) == 1 else self._combine_entries(pipeline_entries)
            
            # Map source fields to unified fields
            for source_field, unified_field in source_mappings.items():
                if source_field in source_data:
                    value = source_data[source_field]
                    if value is not None and value != '':
                        unified_data[unified_field] = value
            
            # Add standard fields that might not be in mappings
            unified_data['company'] = source_company
            unified_data['source_url'] = str(raw_data.source.url)
            
            # Add metadata fields
            if 'last_updated' not in unified_data:
                unified_data['last_updated'] = raw_data.source.collected_at.isoformat()
        
        return unified_data
    
    def _combine_entries(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Combine multiple pipeline entries into a single entry.
        
        Args:
            entries: List of pipeline entries
            
        Returns:
            Combined entry dictionary
        """
        combined = {}
        
        for entry in entries:
            if isinstance(entry, dict):
                for key, value in entry.items():
                    if value is not None and value != '':
                        if key not in combined:
                            combined[key] = value
                        elif isinstance(combined[key], list):
                            if value not in combined[key]:
                                combined[key].append(value)
                        elif combined[key] != value:
                            combined[key] = [combined[key], value]
        
        return combined
    
    def _map_field_to_ontologies(self, field_name: str, value: str) -> List[OntologyMapping]:
        """Map a field value to relevant ontologies.
        
        Args:
            field_name: Name of the field
            value: Value to map
            
        Returns:
            List of OntologyMapping objects
        """
        mappings = []
        
        # Get preferred ontologies for this field
        preferred_ontologies = self.field_ontology_preferences.get(field_name, [])
        
        # If no preferences, try all ontologies
        if not preferred_ontologies:
            preferred_ontologies = list(self.ontology_patterns.keys())
        
        # Try to map to each preferred ontology
        for ontology_name in preferred_ontologies:
            ontology_id, confidence = self._match_to_ontology(value, ontology_name)
            
            if ontology_id and confidence > 0.3:  # Only include mappings with reasonable confidence
                mapping = OntologyMapping(
                    field_name=field_name,
                    original_value=value,
                    ontology_mappings={ontology_name: ontology_id},
                    confidence_scores={ontology_name: confidence}
                )
                mappings.append(mapping)
        
        return mappings
    
    def _match_to_ontology(self, value: str, ontology_name: str) -> Tuple[Optional[str], float]:
        """Match a value to a specific ontology.
        
        Args:
            value: Value to match
            ontology_name: Name of the ontology
            
        Returns:
            Tuple of (ontology_id, confidence_score)
        """
        if ontology_name not in self.ontology_patterns:
            return None, 0.0
        
        ontology_info = self.ontology_patterns[ontology_name]
        patterns = ontology_info['patterns']
        prefix = ontology_info['prefix']
        
        value_lower = value.lower().strip()
        best_match = None
        best_confidence = 0.0
        
        # Try to match against patterns
        for pattern_key, pattern_info in patterns.items():
            confidence = self._calculate_pattern_match_confidence(value_lower, pattern_info)
            
            if confidence > best_confidence:
                best_confidence = confidence
                best_match = f"{prefix}{pattern_info.get('id', pattern_key)}"
        
        return best_match, best_confidence
    
    def _calculate_pattern_match_confidence(self, value: str, pattern_info: Dict) -> float:
        """Calculate confidence score for pattern matching.
        
        Args:
            value: Value to match
            pattern_info: Pattern information dictionary
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Exact match
        if 'exact' in pattern_info and value == pattern_info['exact'].lower():
            return 1.0
        
        # Keyword matching
        if 'keywords' in pattern_info:
            keywords = pattern_info['keywords']
            if isinstance(keywords, str):
                keywords = [keywords]
            
            matched_keywords = sum(1 for keyword in keywords if keyword.lower() in value)
            if matched_keywords > 0:
                return min(0.9, matched_keywords / len(keywords) * 0.8 + 0.1)
        
        # Pattern matching
        if 'pattern' in pattern_info:
            pattern = pattern_info['pattern']
            if re.search(pattern, value, re.IGNORECASE):
                return 0.7
        
        # Partial match
        if 'partial' in pattern_info:
            partial_terms = pattern_info['partial']
            if isinstance(partial_terms, str):
                partial_terms = [partial_terms]
            
            for term in partial_terms:
                if term.lower() in value:
                    return 0.5
        
        return 0.0
    
    def _calculate_enrichment_confidence(
        self, 
        unified_data: Dict[str, Any], 
        ontology_mappings: List[OntologyMapping]
    ) -> float:
        """Calculate confidence score for the enrichment process.
        
        Args:
            unified_data: Data in unified format
            ontology_mappings: List of ontology mappings
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        if not unified_data:
            return 0.0
        
        # Data completeness score
        important_fields = ['compound_name', 'indication', 'development_phase', 'company']
        present_important_fields = sum(1 for field in important_fields if unified_data.get(field))
        completeness_score = present_important_fields / len(important_fields)
        
        # Ontology mapping score
        if ontology_mappings:
            avg_mapping_confidence = sum(
                max(mapping.confidence_scores.values()) 
                for mapping in ontology_mappings
            ) / len(ontology_mappings)
            
            # Coverage score (how many fields have mappings)
            mapped_fields = set(mapping.field_name for mapping in ontology_mappings)
            mappable_fields = set(unified_data.keys()) & set(self.field_ontology_preferences.keys())
            coverage_score = len(mapped_fields) / len(mappable_fields) if mappable_fields else 0.0
            
            mapping_score = (avg_mapping_confidence * 0.7 + coverage_score * 0.3)
        else:
            mapping_score = 0.0
        
        # Overall confidence
        confidence = completeness_score * 0.6 + mapping_score * 0.4
        
        return round(confidence, 3)
    
    # Ontology pattern definitions
    def _get_mondo_patterns(self) -> Dict:
        """Get MONDO (disease) ontology patterns."""
        return {
            'cancer': {'keywords': ['cancer', 'carcinoma', 'tumor', 'malignancy'], 'id': '0004992'},
            'diabetes': {'keywords': ['diabetes'], 'id': '0005015'},
            'alzheimer': {'keywords': ['alzheimer'], 'id': '0004975'},
            'hypertension': {'keywords': ['hypertension', 'high blood pressure'], 'id': '0005044'},
            'depression': {'keywords': ['depression'], 'id': '0002050'},
            'asthma': {'keywords': ['asthma'], 'id': '0004979'},
            'arthritis': {'keywords': ['arthritis'], 'id': '0005015'},
            'heart_disease': {'keywords': ['heart disease', 'cardiac', 'cardiovascular'], 'id': '0005267'}
        }
    
    def _get_chebi_patterns(self) -> Dict:
        """Get ChEBI (chemical) ontology patterns."""
        return {
            'small_molecule': {'keywords': ['small molecule', 'compound'], 'id': '25367'},
            'protein': {'keywords': ['protein', 'antibody'], 'id': '36080'},
            'inhibitor': {'keywords': ['inhibitor'], 'id': '35222'},
            'agonist': {'keywords': ['agonist'], 'id': '48705'},
            'antagonist': {'keywords': ['antagonist'], 'id': '48706'}
        }
    
    def _get_efo_patterns(self) -> Dict:
        """Get EFO (experimental factor) ontology patterns."""
        return {
            'clinical_trial': {'keywords': ['clinical trial', 'phase'], 'id': '0001427'},
            'therapeutic_area': {'keywords': ['therapeutic', 'treatment'], 'id': '0000727'},
            'biomarker': {'keywords': ['biomarker'], 'id': '0001444'}
        }
    
    def _get_ncit_patterns(self) -> Dict:
        """Get NCIT (NCI thesaurus) ontology patterns."""
        return {
            'phase_1': {'keywords': ['phase 1', 'phase i'], 'id': 'C15600'},
            'phase_2': {'keywords': ['phase 2', 'phase ii'], 'id': 'C15601'},
            'phase_3': {'keywords': ['phase 3', 'phase iii'], 'id': 'C15602'},
            'preclinical': {'keywords': ['preclinical'], 'id': 'C142681'},
            'approved': {'keywords': ['approved', 'marketed'], 'id': 'C25425'}
        }
    
    def _get_mesh_patterns(self) -> Dict:
        """Get MeSH (medical subject headings) ontology patterns."""
        return {
            'neoplasms': {'keywords': ['cancer', 'tumor', 'neoplasm'], 'id': 'D009369'},
            'cardiovascular': {'keywords': ['cardiovascular', 'heart'], 'id': 'D002318'},
            'nervous_system': {'keywords': ['neurological', 'brain'], 'id': 'D009422'},
            'immunology': {'keywords': ['immune', 'immunology'], 'id': 'D007154'}
        }
    
    def _get_atc_patterns(self) -> Dict:
        """Get ATC (anatomical therapeutic chemical) ontology patterns."""
        return {
            'antineoplastic': {'keywords': ['cancer', 'oncology'], 'id': 'L01'},
            'cardiovascular': {'keywords': ['cardiovascular', 'heart'], 'id': 'C'},
            'nervous_system': {'keywords': ['neurological', 'cns'], 'id': 'N'},
            'anti_infective': {'keywords': ['antibiotic', 'antiviral'], 'id': 'J'}
        }
    
    def _get_icd10_patterns(self) -> Dict:
        """Get ICD-10 ontology patterns."""
        return {
            'neoplasms': {'keywords': ['cancer', 'tumor'], 'id': 'C00-D49'},
            'circulatory': {'keywords': ['cardiovascular', 'heart'], 'id': 'I00-I99'},
            'respiratory': {'keywords': ['respiratory', 'lung'], 'id': 'J00-J99'},
            'digestive': {'keywords': ['digestive', 'gastrointestinal'], 'id': 'K00-K95'}
        }
    
    def _get_snomed_patterns(self) -> Dict:
        """Get SNOMED CT ontology patterns."""
        return {
            'disorder': {'keywords': ['disorder', 'disease'], 'id': '64572001'},
            'procedure': {'keywords': ['procedure', 'treatment'], 'id': '71388002'},
            'substance': {'keywords': ['drug', 'medication'], 'id': '105590001'},
            'finding': {'keywords': ['finding', 'symptom'], 'id': '404684003'}
        }