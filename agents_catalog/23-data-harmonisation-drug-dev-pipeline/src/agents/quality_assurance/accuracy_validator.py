"""Accuracy validator for checking data against external reference sources."""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

from ...models.harmonization import EnrichedData
from ...models.quality_assurance import (
    AccuracyValidation,
    ExternalReference,
)

logger = logging.getLogger(__name__)


class AccuracyValidator:
    """Component for validating data accuracy against external sources."""
    
    def __init__(self):
        """Initialize the accuracy validator."""
        self.name = "AccuracyValidator"
        
        # External reference sources (in a real implementation, these would be actual APIs)
        self.reference_sources = {
            "compound_name": [
                ExternalReference(
                    source_name="ChEBI Database",
                    source_url="https://www.ebi.ac.uk/chebi/",
                    api_endpoint="https://www.ebi.ac.uk/chebi/searchId.do",
                    confidence_level=0.9,
                    access_method="api"
                ),
                ExternalReference(
                    source_name="PubChem",
                    source_url="https://pubchem.ncbi.nlm.nih.gov/",
                    api_endpoint="https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name",
                    confidence_level=0.85,
                    access_method="api"
                )
            ],
            "indication": [
                ExternalReference(
                    source_name="MONDO Disease Ontology",
                    source_url="https://mondo.monarchinitiative.org/",
                    api_endpoint="https://api.monarchinitiative.org/api/search/entity",
                    confidence_level=0.9,
                    access_method="api"
                ),
                ExternalReference(
                    source_name="ICD-10",
                    source_url="https://icd.who.int/browse10/2019/en",
                    confidence_level=0.95,
                    access_method="manual"
                )
            ],
            "therapeutic_area": [
                ExternalReference(
                    source_name="ATC Classification",
                    source_url="https://www.whocc.no/atc_ddd_index/",
                    confidence_level=0.9,
                    access_method="manual"
                )
            ]
        }
        
        # Cache for external lookups to avoid repeated API calls
        self._lookup_cache = {}
        
        # HTTP session for API calls
        self._session = None
        
        logger.debug(f"Initialized {self.name} with {len(self.reference_sources)} reference source types")
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={"User-Agent": "PharmaAgent/1.0"}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()
    
    async def validate_accuracy(
        self, 
        data: List[EnrichedData], 
        fields_to_validate: Optional[List[str]] = None
    ) -> List[AccuracyValidation]:
        """Validate data accuracy against external reference sources.
        
        Args:
            data: List of enriched data entries to validate
            fields_to_validate: Optional list of specific fields to validate
            
        Returns:
            List of accuracy validation results
        """
        logger.info(f"Validating accuracy for {len(data)} records")
        
        if not data:
            return []
        
        # Use all available fields if none specified
        if fields_to_validate is None:
            fields_to_validate = list(self.reference_sources.keys())
        
        # Initialize session if not already done
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"User-Agent": "PharmaAgent/1.0"}
            )
        
        validations = []
        
        # Process entries in batches to avoid overwhelming external APIs
        batch_size = 10
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            batch_validations = await self._validate_batch(batch, fields_to_validate)
            validations.extend(batch_validations)
            
            # Small delay between batches to be respectful to external APIs
            if i + batch_size < len(data):
                await asyncio.sleep(0.5)
        
        return validations
    
    async def _validate_batch(
        self, 
        batch: List[EnrichedData], 
        fields_to_validate: List[str]
    ) -> List[AccuracyValidation]:
        """Validate a batch of entries."""
        validations = []
        
        # Create validation tasks for concurrent execution
        tasks = []
        for entry in batch:
            for field_name in fields_to_validate:
                if field_name in self.reference_sources:
                    task = self._validate_field_accuracy(entry, field_name)
                    tasks.append(task)
        
        # Execute tasks concurrently
        if tasks:
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.warning(f"Validation task failed: {result}")
                elif isinstance(result, list):
                    validations.extend(result)
        
        return validations
    
    async def _validate_field_accuracy(
        self, 
        entry: EnrichedData, 
        field_name: str
    ) -> List[AccuracyValidation]:
        """Validate accuracy for a specific field in an entry.
        
        Args:
            entry: EnrichedData entry to validate
            field_name: Name of the field to validate
            
        Returns:
            List of accuracy validations for the field
        """
        validations = []
        
        # Get the field value
        field_value = self._get_field_value(entry, field_name)
        if field_value is None:
            return validations
        
        # Validate against each reference source for this field
        reference_sources = self.reference_sources.get(field_name, [])
        
        for reference_source in reference_sources:
            validation = await self._validate_against_source(
                field_name, field_value, reference_source
            )
            if validation:
                validations.append(validation)
        
        return validations
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def _validate_against_source(
        self, 
        field_name: str, 
        field_value: Any, 
        reference_source: ExternalReference
    ) -> Optional[AccuracyValidation]:
        """Validate a field value against a specific reference source.
        
        Args:
            field_name: Name of the field being validated
            field_value: Value to validate
            reference_source: External reference source to validate against
            
        Returns:
            AccuracyValidation result or None if validation couldn't be performed
        """
        try:
            # Check cache first
            cache_key = f"{reference_source.source_name}:{field_name}:{field_value}"
            if cache_key in self._lookup_cache:
                cached_result = self._lookup_cache[cache_key]
                return AccuracyValidation(
                    field_name=field_name,
                    original_value=field_value,
                    reference_value=cached_result["reference_value"],
                    external_source=reference_source,
                    is_accurate=cached_result["is_accurate"],
                    confidence_score=cached_result["confidence_score"],
                    discrepancy_details=cached_result.get("discrepancy_details")
                )
            
            # Perform validation based on access method
            if reference_source.access_method == "api" and reference_source.api_endpoint:
                reference_value, is_accurate, confidence_score = await self._validate_via_api(
                    field_name, field_value, reference_source
                )
            else:
                # Fall back to simulation for non-API sources
                reference_value, is_accurate, confidence_score = await self._simulate_reference_lookup(
                    field_name, field_value, reference_source
                )
            
            # Cache the result
            self._lookup_cache[cache_key] = {
                "reference_value": reference_value,
                "is_accurate": is_accurate,
                "confidence_score": confidence_score,
                "discrepancy_details": None if is_accurate else f"Expected '{reference_value}', found '{field_value}'"
            }
            
            discrepancy_details = None
            if not is_accurate and reference_value:
                discrepancy_details = f"Expected '{reference_value}', found '{field_value}'"
            
            return AccuracyValidation(
                field_name=field_name,
                original_value=field_value,
                reference_value=reference_value,
                external_source=reference_source,
                is_accurate=is_accurate,
                confidence_score=confidence_score,
                discrepancy_details=discrepancy_details
            )
            
        except Exception as e:
            logger.warning(f"Failed to validate {field_name} against {reference_source.source_name}: {e}")
            return None
    
    async def _validate_via_api(
        self, 
        field_name: str, 
        field_value: Any, 
        reference_source: ExternalReference
    ) -> tuple[Optional[Any], bool, float]:
        """Validate via external API call.
        
        Args:
            field_name: Name of the field being validated
            field_value: Value to validate
            reference_source: External reference source with API endpoint
            
        Returns:
            Tuple of (reference_value, is_accurate, confidence_score)
        """
        if not self._session:
            # Fall back to simulation if no session
            return await self._simulate_reference_lookup(field_name, field_value, reference_source)
        
        try:
            # This is a placeholder for actual API integration
            # In a real implementation, you would make actual API calls here
            
            # For demonstration, we'll simulate API calls with some realistic behavior
            await asyncio.sleep(0.1)  # Simulate network delay
            
            # Simulate API response based on source
            if "chebi" in reference_source.source_name.lower():
                return await self._simulate_chebi_api(field_value)
            elif "pubchem" in reference_source.source_name.lower():
                return await self._simulate_pubchem_api(field_value)
            elif "mondo" in reference_source.source_name.lower():
                return await self._simulate_mondo_api(field_value)
            else:
                # Generic API simulation
                return await self._simulate_generic_api(field_value, reference_source.confidence_level)
                
        except Exception as e:
            logger.warning(f"API validation failed for {reference_source.source_name}: {e}")
            # Fall back to simulation
            return await self._simulate_reference_lookup(field_name, field_value, reference_source)
    
    async def _simulate_chebi_api(self, compound_name: str) -> tuple[Optional[str], bool, float]:
        """Simulate ChEBI API response."""
        compound_lower = str(compound_name).lower().strip()
        
        # Known compounds in ChEBI
        known_compounds = {
            "aspirin": ("aspirin", True, 0.95),
            "ibuprofen": ("ibuprofen", True, 0.95),
            "paracetamol": ("paracetamol", True, 0.95),
            "acetaminophen": ("paracetamol", True, 0.90),  # Alternative name
            "caffeine": ("caffeine", True, 0.95),
            "morphine": ("morphine", True, 0.95),
        }
        
        if compound_lower in known_compounds:
            return known_compounds[compound_lower]
        
        # Check for pharmaceutical naming patterns
        if any(suffix in compound_lower for suffix in ["mab", "nib", "tinib", "zumab"]):
            return compound_name, True, 0.8
        
        # Unknown compound
        return None, False, 0.7
    
    async def _simulate_pubchem_api(self, compound_name: str) -> tuple[Optional[str], bool, float]:
        """Simulate PubChem API response."""
        compound_lower = str(compound_name).lower().strip()
        
        # PubChem has a broader database
        if len(compound_lower) >= 3 and compound_lower.isalpha():
            # Most chemical names would be found in PubChem
            return compound_name, True, 0.85
        
        return None, False, 0.6
    
    async def _simulate_mondo_api(self, indication: str) -> tuple[Optional[str], bool, float]:
        """Simulate MONDO API response."""
        indication_lower = str(indication).lower().strip()
        
        # Known disease terms
        disease_terms = [
            "cancer", "diabetes", "hypertension", "depression", "alzheimer",
            "parkinson", "arthritis", "sclerosis", "asthma", "copd"
        ]
        
        if any(term in indication_lower for term in disease_terms):
            return indication, True, 0.9
        
        # Check for medical suffixes
        medical_suffixes = ["itis", "osis", "emia", "pathy", "syndrome", "disease"]
        if any(suffix in indication_lower for suffix in medical_suffixes):
            return indication, True, 0.8
        
        return None, False, 0.5
    
    async def _simulate_generic_api(
        self, 
        value: Any, 
        base_confidence: float
    ) -> tuple[Optional[Any], bool, float]:
        """Simulate generic API response."""
        # Simple validation based on value characteristics
        value_str = str(value).strip()
        
        if len(value_str) >= 3:
            return value, True, base_confidence * 0.8
        
        return None, False, base_confidence * 0.5
    
    async def _simulate_reference_lookup(
        self, 
        field_name: str, 
        field_value: Any, 
        reference_source: ExternalReference
    ) -> tuple[Optional[Any], bool, float]:
        """Simulate looking up a value in an external reference source.
        
        This is a placeholder implementation. In a real system, this would:
        - Make API calls to external databases
        - Query local reference databases
        - Use fuzzy matching for approximate matches
        
        Args:
            field_name: Name of the field being validated
            field_value: Value to look up
            reference_source: External reference source
            
        Returns:
            Tuple of (reference_value, is_accurate, confidence_score)
        """
        field_value_str = str(field_value).lower().strip()
        
        # Simulate validation with some basic rules and known values
        if field_name == "compound_name":
            return await self._simulate_compound_validation(field_value_str, reference_source)
        elif field_name == "indication":
            return await self._simulate_indication_validation(field_value_str, reference_source)
        elif field_name == "therapeutic_area":
            return await self._simulate_therapeutic_area_validation(field_value_str, reference_source)
        
        # Default: assume accurate with moderate confidence
        return field_value, True, 0.7
    
    async def _simulate_compound_validation(
        self, 
        compound_name: str, 
        reference_source: ExternalReference
    ) -> tuple[Optional[str], bool, float]:
        """Simulate compound name validation."""
        
        # Known valid compound patterns (in reality, this would be a comprehensive database)
        valid_patterns = [
            "mab",  # monoclonal antibodies
            "nib",  # kinase inhibitors
            "tinib", # tyrosine kinase inhibitors
            "zumab", # humanized monoclonal antibodies
            "ximab", # chimeric monoclonal antibodies
        ]
        
        # Check if compound follows known naming patterns
        follows_pattern = any(pattern in compound_name for pattern in valid_patterns)
        
        # Simulate some known compounds
        known_compounds = {
            "pembrolizumab": ("pembrolizumab", True, 0.95),
            "imatinib": ("imatinib", True, 0.95),
            "bevacizumab": ("bevacizumab", True, 0.95),
            "trastuzumab": ("trastuzumab", True, 0.95),
            "rituximab": ("rituximab", True, 0.95),
        }
        
        if compound_name in known_compounds:
            return known_compounds[compound_name]
        
        # Check for common misspellings or variations
        if follows_pattern:
            return compound_name, True, 0.8
        
        # Check for obviously invalid names
        if len(compound_name) < 3 or not compound_name.isalpha():
            return None, False, 0.9
        
        # Default: assume valid but with lower confidence
        return compound_name, True, 0.6
    
    async def _simulate_indication_validation(
        self, 
        indication: str, 
        reference_source: ExternalReference
    ) -> tuple[Optional[str], bool, float]:
        """Simulate indication validation."""
        
        # Known valid indications
        valid_indications = {
            "cancer", "diabetes", "hypertension", "depression", "alzheimer's disease",
            "parkinson's disease", "rheumatoid arthritis", "multiple sclerosis",
            "breast cancer", "lung cancer", "colorectal cancer", "melanoma",
            "heart failure", "stroke", "asthma", "copd", "migraine"
        }
        
        # Check for exact matches
        if indication in valid_indications:
            return indication, True, 0.95
        
        # Check for partial matches
        for valid_indication in valid_indications:
            if valid_indication in indication or indication in valid_indication:
                return valid_indication, True, 0.8
        
        # Check for common medical terms
        medical_terms = ["disease", "syndrome", "disorder", "cancer", "tumor", "infection"]
        has_medical_term = any(term in indication for term in medical_terms)
        
        if has_medical_term:
            return indication, True, 0.7
        
        # Check for obviously invalid indications
        if len(indication) < 3 or indication.isdigit():
            return None, False, 0.9
        
        # Default: assume valid but with lower confidence
        return indication, True, 0.5
    
    async def _simulate_therapeutic_area_validation(
        self, 
        therapeutic_area: str, 
        reference_source: ExternalReference
    ) -> tuple[Optional[str], bool, float]:
        """Simulate therapeutic area validation."""
        
        # Known valid therapeutic areas
        valid_areas = {
            "oncology", "neurology", "cardiology", "immunology", "infectious diseases",
            "endocrinology", "respiratory", "gastroenterology", "dermatology", 
            "ophthalmology", "psychiatry", "rheumatology", "hematology", "nephrology"
        }
        
        # Check for exact matches
        if therapeutic_area in valid_areas:
            return therapeutic_area, True, 0.95
        
        # Check for partial matches
        for valid_area in valid_areas:
            if valid_area in therapeutic_area or therapeutic_area in valid_area:
                return valid_area, True, 0.8
        
        # Check for common variations
        area_variations = {
            "cancer": "oncology",
            "heart": "cardiology",
            "brain": "neurology",
            "lung": "respiratory",
            "kidney": "nephrology",
            "blood": "hematology"
        }
        
        for variation, standard in area_variations.items():
            if variation in therapeutic_area:
                return standard, True, 0.7
        
        # Default: assume valid but with lower confidence
        return therapeutic_area, True, 0.5
    
    def _get_field_value(self, entry: EnrichedData, field_name: str) -> Any:
        """Get field value from enriched data entry."""
        # Try unified_data first
        if field_name in entry.unified_data:
            return entry.unified_data[field_name]
        
        # Try nested fields in unified_data
        for key, value in entry.unified_data.items():
            if isinstance(value, dict) and field_name in value:
                return value[field_name]
        
        # Try original_data as fallback
        if field_name in entry.original_data:
            return entry.original_data[field_name]
        
        return None
    
    def clear_cache(self):
        """Clear the lookup cache."""
        self._lookup_cache.clear()
        logger.info("Accuracy validation cache cleared")