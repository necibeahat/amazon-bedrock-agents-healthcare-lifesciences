"""Content extractors for pharmaceutical websites."""

import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class PipelineEntry(BaseModel):
    """Represents a single pharmaceutical pipeline entry."""
    
    compound_name: Optional[str] = None
    indication: Optional[str] = None
    therapeutic_area: Optional[str] = None
    development_phase: Optional[str] = None
    mechanism_of_action: Optional[str] = None
    status: Optional[str] = None
    estimated_completion: Optional[str] = None
    regulatory_designations: List[str] = []
    additional_info: Dict[str, Any] = {}


class ExtractionResult(BaseModel):
    """Result of content extraction."""
    
    entries: List[PipelineEntry]
    extraction_method: str
    confidence_score: float
    metadata: Dict[str, Any] = {}
    errors: List[str] = []


class BaseExtractor(ABC):
    """Base class for pharmaceutical website extractors."""
    
    def __init__(self, company_name: str):
        """Initialize the extractor.
        
        Args:
            company_name: Name of the pharmaceutical company
        """
        self.company_name = company_name
        self.logger = logging.getLogger(f"{__name__}.{company_name}Extractor")
    
    @abstractmethod
    def extract(self, html_content: str) -> ExtractionResult:
        """Extract pipeline data from HTML content.
        
        Args:
            html_content: Raw HTML content
            
        Returns:
            ExtractionResult with extracted pipeline entries
        """
        pass
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content.
        
        Args:
            text: Raw text to clean
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Remove HTML tags if present
        import re
        text = re.sub(r'<[^>]+>', ' ', text)
        
        # Remove extra whitespace and normalize
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Remove common HTML artifacts
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'&lt;', '<', text)
        text = re.sub(r'&gt;', '>', text)
        text = re.sub(r'&quot;', '"', text)
        text = re.sub(r'&#39;', "'", text)
        
        return text
    
    def _extract_phase(self, text: str) -> Optional[str]:
        """Extract development phase from text.
        
        Args:
            text: Text to extract phase from
            
        Returns:
            Extracted phase or None
        """
        if not text:
            return None
        
        text_lower = text.lower()
        
        # Common phase patterns with proper capturing groups
        phase_patterns = [
            (r'phase\s*(i{1,3}|[1-3])', r'Phase \1'),
            (r'preclinical', 'Preclinical'),
            (r'discovery', 'Discovery'),
            (r'phase\s*1', 'Phase I'),
            (r'phase\s*2', 'Phase II'),
            (r'phase\s*3', 'Phase III'),
            (r'registration', 'Registration'),
            (r'approved', 'Approved'),
            (r'launched', 'Launched'),
            (r'marketed', 'Marketed'),
            (r'under\s+review', 'Under Review'),
        ]
        
        for pattern, replacement in phase_patterns:
            if re.search(pattern, text_lower):
                if '\\1' in replacement:
                    # Use capturing group
                    match = re.search(pattern, text_lower)
                    if match:
                        return re.sub(pattern, replacement, text_lower, flags=re.IGNORECASE).title()
                else:
                    # Direct replacement
                    return replacement
        
        return None


class MerckExtractor(BaseExtractor):
    """Extractor for Merck pipeline data."""
    
    def __init__(self):
        super().__init__("Merck")
    
    def extract(self, html_content: str) -> ExtractionResult:
        """Extract pipeline data from Merck website.
        
        Args:
            html_content: Raw HTML content from Merck pipeline page
            
        Returns:
            ExtractionResult with extracted pipeline entries
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            entries = []
            errors = []
            
            # Strategy 1: Extract from structured data attributes (most reliable)
            structured_entries = self._extract_from_structured_data(soup)
            entries.extend(structured_entries)
            self.logger.info(f"Structured data extraction found {len(structured_entries)} entries")
            
            # Strategy 2: Pattern-based extraction for Merck's specific format
            if len(entries) < 50:  # Expected to find 85+, so try pattern extraction if we don't have enough
                pattern_entries = self._extract_merck_pipeline_entries(html_content)
                # Avoid duplicates
                for entry in pattern_entries:
                    if not any(e.compound_name == entry.compound_name for e in entries):
                        entries.append(entry)
                self.logger.info(f"Pattern extraction found {len(pattern_entries)} additional entries")
            
            # Strategy 3: Fallback - Extract from tables if other methods don't find enough
            if len(entries) < 50:
                tables = soup.find_all('table')
                self.logger.info(f"Found {len(tables)} tables on Merck page")
                
                for i, table in enumerate(tables):
                    table_entries = self._extract_from_merck_table(table, i)
                    for entry in table_entries:
                        if not any(e.compound_name == entry.compound_name for e in entries):
                            entries.append(entry)
            
            # Remove duplicates
            entries = self._deduplicate_entries(entries)
            
            # Calculate confidence score
            confidence_score = self._calculate_merck_confidence(entries, html_content)
            
            return ExtractionResult(
                entries=entries,
                extraction_method="merck_multi_strategy",
                confidence_score=confidence_score,
                metadata={
                    "total_entries": len(entries),
                    "extraction_strategies_used": ["structured_data", "pattern_extraction", "table_extraction_fallback"]
                },
                errors=errors
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting Merck data: {e}")
            return ExtractionResult(
                entries=[],
                extraction_method="merck_multi_strategy",
                confidence_score=0.0,
                errors=[str(e)]
            )
    
    def _extract_from_structured_data(self, soup) -> List[PipelineEntry]:
        """Extract entries from Merck's structured data attributes and HTML elements.
        
        This method targets Merck's specific HTML structure with data attributes
        and pipeline-specific CSS classes.
        """
        entries = []
        
        try:
            # Look for pipeline program rows with data attributes
            pipeline_rows = soup.find_all('tr', {'data-name': True})
            self.logger.info(f"Found {len(pipeline_rows)} pipeline rows with data attributes")
            
            for row in pipeline_rows:
                try:
                    entry_data = {}
                    
                    # Extract from data attributes
                    compound_name = row.get('data-name', '').strip()
                    if compound_name:
                        entry_data['compound_name'] = compound_name
                    
                    # Extract phase from data-phase attribute
                    phase_attr = row.get('data-phase', '').strip()
                    if phase_attr:
                        # Convert phase-2 to Phase 2, etc.
                        if 'phase-' in phase_attr:
                            phase_num = phase_attr.replace('phase-', '').upper()
                            entry_data['development_phase'] = f"Phase {phase_num}"
                        else:
                            entry_data['development_phase'] = phase_attr
                    
                    # Look for pipeline program elements within the row
                    program_header = row.find('div', class_='pipeline-program-header')
                    if program_header:
                        # Extract compound name from header if not already found
                        if not entry_data.get('compound_name'):
                            name_elem = program_header.find('h4', class_='pipeline-program-name')
                            if name_elem:
                                compound_text = self._clean_text(name_elem.get_text())
                                # Extract compound code from the text
                                compound_match = re.search(r'\b(MK-\d+[A-Z]*|V\d+[A-Z]*)\b', compound_text)
                                if compound_match:
                                    entry_data['compound_name'] = compound_match.group(1)
                        
                        # Extract indications - handle multiple indications
                        indications_elem = program_header.find('div', class_='pipeline-program-indications')
                        if indications_elem:
                            indication_text = self._clean_text(indications_elem.get_text())
                            if indication_text:
                                # Split multiple indications and create separate entries
                                indications = self._split_multiple_indications(indication_text)
                                if len(indications) > 1:
                                    # Create multiple entries for multiple indications
                                    for indication in indications:
                                        if self._looks_like_indication(indication):
                                            individual_entry = entry_data.copy()
                                            individual_entry['indication'] = indication
                                            # Handle corresponding phases if available
                                            phases = self._extract_corresponding_phases(row_text if 'row_text' in locals() else '')
                                            if phases and len(phases) >= len(indications):
                                                phase_index = indications.index(indication)
                                                if phase_index < len(phases):
                                                    individual_entry['development_phase'] = phases[phase_index]
                                            
                                            individual_entry['additional_info'] = {
                                                'extraction_method': 'structured_data_multi_indication',
                                                'original_compound': compound_name,
                                                'indication_index': indications.index(indication)
                                            }
                                            
                                            if self._has_meaningful_merck_data(individual_entry):
                                                individual_entry_obj = self._create_pipeline_entry(individual_entry)
                                                if individual_entry_obj:
                                                    entries.append(individual_entry_obj)
                                    continue  # Skip the main entry creation below
                                elif indications and self._looks_like_indication(indications[0]):
                                    entry_data['indication'] = indications[0]
                    
                    # Look for therapeutic area and other details in the row text
                    row_text = self._clean_text(row.get_text())
                    
                    # Extract therapeutic area from patterns like "Cardiovascular|Phase 2"
                    therapeutic_match = re.search(r'\|(.*?)\|', row_text)
                    if therapeutic_match:
                        potential_therapeutic = therapeutic_match.group(1).strip()
                        if self._looks_like_therapeutic_area(potential_therapeutic):
                            entry_data['therapeutic_area'] = potential_therapeutic
                    
                    # Alternative therapeutic area extraction
                    if 'therapeutic_area' not in entry_data:
                        therapeutic_areas = ['Cardiovascular', 'Oncology', 'Immunology', 'Neurology', 'Infectious Disease']
                        for area in therapeutic_areas:
                            if area in row_text:
                                entry_data['therapeutic_area'] = area
                                break
                    
                    # Extract mechanism of action from text patterns
                    moa_patterns = [
                        r'(lipoprotein\(a\) inhibitor)',
                        r'(\w+ inhibitor)',
                        r'(monoclonal antibody)',
                        r'(small molecule)'
                    ]
                    
                    for pattern in moa_patterns:
                        moa_match = re.search(pattern, row_text, re.IGNORECASE)
                        if moa_match:
                            entry_data['mechanism_of_action'] = moa_match.group(1)
                            break
                    
                    # Store additional info
                    entry_data['additional_info'] = {
                        'extraction_method': 'structured_data',
                        'data_attributes': {
                            'data-name': row.get('data-name', ''),
                            'data-phase': row.get('data-phase', ''),
                            'data-code': row.get('data-code', '')
                        }
                    }
                    
                    # Create entry if we have meaningful data
                    if self._has_meaningful_merck_data(entry_data):
                        entry = self._create_pipeline_entry(entry_data)
                        if entry:
                            entries.append(entry)
                            self.logger.debug(f"Created entry from structured data: {entry.compound_name}")
                
                except Exception as e:
                    self.logger.debug(f"Error processing pipeline row: {e}")
                    continue
            
            # Also look for pipeline cards or sections
            pipeline_cards = soup.find_all('div', class_=re.compile(r'pipeline.*program'))
            self.logger.info(f"Found {len(pipeline_cards)} pipeline program cards")
            
            for card in pipeline_cards:
                try:
                    entry = self._extract_from_pipeline_card(card)
                    if entry and not any(e.compound_name == entry.compound_name for e in entries):
                        entries.append(entry)
                        self.logger.debug(f"Created entry from pipeline card: {entry.compound_name}")
                except Exception as e:
                    self.logger.debug(f"Error processing pipeline card: {e}")
                    continue
            
        except Exception as e:
            self.logger.error(f"Error in structured data extraction: {e}")
        
        return entries
    
    def _split_multiple_indications(self, indication_text: str) -> List[str]:
        """Split text that contains multiple indications."""
        if not indication_text:
            return []
        
        # Common delimiters for multiple indications
        delimiters = [
            r'\s*\|\s*',  # Pipe separator
            r'\s*;\s*',   # Semicolon
            r'\s*,\s*(?=[A-Z])',  # Comma followed by capital letter (new indication)
            r'\s*\n\s*',  # Newline
        ]
        
        indications = [indication_text]
        
        for delimiter in delimiters:
            new_indications = []
            for indication in indications:
                parts = re.split(delimiter, indication)
                new_indications.extend([part.strip() for part in parts if part.strip()])
            indications = new_indications
        
        # Filter out very short or non-meaningful parts
        filtered_indications = []
        for indication in indications:
            if len(indication) > 10 and not indication.lower() in ['phase', 'under', 'review']:
                filtered_indications.append(indication)
        
        return filtered_indications[:10]  # Limit to 10 indications to avoid explosion
    
    def _extract_corresponding_phases(self, text: str) -> List[str]:
        """Extract phases that correspond to multiple indications."""
        if not text:
            return []
        
        # Look for phase patterns
        phase_matches = re.findall(r'Phase\s+[1-3I]+|Under Review|Approved', text, re.IGNORECASE)
        return phase_matches
    
    def _extract_from_pipeline_card(self, card) -> Optional[PipelineEntry]:
        """Extract entry from a Merck pipeline program card."""
        try:
            entry_data = {}
            card_text = self._clean_text(card.get_text())
            
            # Extract compound name
            compound_match = re.search(r'\b(MK-\d+[A-Z]*|V\d+[A-Z]*)\b', card_text)
            if compound_match:
                entry_data['compound_name'] = compound_match.group(1)
            
            # Extract indication from specific elements
            indication_elem = card.find(class_=re.compile(r'.*indication.*'))
            if indication_elem:
                indication_text = self._clean_text(indication_elem.get_text())
                if indication_text and self._looks_like_indication(indication_text):
                    entry_data['indication'] = indication_text
            
            # Extract therapeutic area
            therapeutic_areas = ['Cardiovascular', 'Oncology', 'Immunology', 'Neurology', 'Infectious Disease']
            for area in therapeutic_areas:
                if area in card_text:
                    entry_data['therapeutic_area'] = area
                    break
            
            # Extract phase
            phase_match = re.search(r'Phase\s+([1-3I]+)', card_text, re.IGNORECASE)
            if phase_match:
                entry_data['development_phase'] = f"Phase {phase_match.group(1)}"
            
            entry_data['additional_info'] = {'extraction_method': 'pipeline_card'}
            
            if self._has_meaningful_merck_data(entry_data):
                return self._create_pipeline_entry(entry_data)
                
        except Exception as e:
            self.logger.debug(f"Error extracting from pipeline card: {e}")
        
        return None
        """Extract entries from a Merck table with improved logic."""
        entries = []
        
        try:
            rows = table.find_all('tr')
            if len(rows) < 2:  # Need at least header + 1 data row
                return entries
            
            # Try to identify header row and data structure
            header_row = rows[0]
            headers = [self._clean_text(th.get_text()) for th in header_row.find_all(['th', 'td'])]
            
            # Skip empty or irrelevant tables
            if not headers or len(headers) < 2:
                return entries
            
            # Check if this looks like a pipeline table
            header_text = ' '.join(headers).lower()
            if not any(term in header_text for term in ['molecule', 'compound', 'indication', 'phase', 'therapeutic', 'status']):
                return entries
            
            self.logger.debug(f"Processing table {table_index} with headers: {headers}")
            
            # Map headers to standard fields
            header_mapping = self._create_merck_header_mapping(headers)
            
            # Extract data rows
            for row_idx, row in enumerate(rows[1:], 1):
                cells = row.find_all(['td', 'th'])
                if not cells:
                    continue
                
                entry_data = {}
                
                # Extract data from each cell
                for i, cell in enumerate(cells):
                    cell_text = self._clean_text(cell.get_text())
                    if not cell_text:
                        continue
                    
                    # Map to standard field if header mapping exists
                    if i < len(headers) and headers[i] in header_mapping:
                        field_name = header_mapping[headers[i]]
                        entry_data[field_name] = cell_text
                    
                    # Special handling for Merck's complex cell structure
                    # Extract compound codes from complex text
                    compound_codes = self._extract_compound_codes_from_text(cell_text)
                    if compound_codes and 'compound_name' not in entry_data:
                        entry_data['compound_name'] = compound_codes[0]  # Take the first one
                    
                    # Also try to identify data by content patterns
                    if self._looks_like_indication(cell_text):
                        entry_data['indication'] = cell_text
                    elif self._looks_like_phase(cell_text):
                        phase = self._extract_phase(cell_text)
                        if phase:
                            entry_data['development_phase'] = phase
                    elif self._looks_like_therapeutic_area(cell_text):
                        entry_data['therapeutic_area'] = cell_text
                
                # Store all cell data for additional info
                entry_data['additional_info'] = {
                    'table_index': table_index,
                    'row_index': row_idx,
                    'table_data': [self._clean_text(cell.get_text()) for cell in cells],
                    'headers': headers
                }
                
                # Create entry if we have meaningful data
                if self._has_meaningful_data(entry_data):
                    entry = self._create_pipeline_entry(entry_data)
                    if entry:
                        entries.append(entry)
        
        except Exception as e:
            self.logger.debug(f"Error extracting from table {table_index}: {e}")
        
        return entries
    
    def _extract_compound_codes_from_text(self, text: str) -> List[str]:
        """Extract Merck compound codes from complex text."""
        import re
        
        compound_patterns = [
            r'\b(MK-\d+[A-Z]*)\b',  # MK-1234, MK-1234A
            r'\b([A-Z]{2,3}-\d+[A-Z]*)\b',  # General compound codes
            r'\b(V\d+[A-Z]*)\b',    # V-series compounds
        ]
        
        compounds = []
        for pattern in compound_patterns:
            matches = re.findall(pattern, text)
            compounds.extend(matches)
        
        return list(set(compounds))  # Remove duplicates
    
    def _find_merck_compounds(self, html_content: str) -> List[str]:
        """Find Merck compound codes in the HTML content."""
        import re
        
        compound_patterns = [
            r'\bMK-\d+[A-Z]*',  # MK-1234, MK-1234A
            r'\bV\d+[A-Z]*',    # V-series compounds
            r'\b[A-Z]{2,3}-\d+[A-Z]*',  # General compound codes
        ]
        
        all_compounds = set()
        for pattern in compound_patterns:
            matches = re.findall(pattern, html_content)
            all_compounds.update(matches)
        
        return list(all_compounds)
    
    def _extract_by_compound_code(self, soup, compound_code: str) -> Optional[PipelineEntry]:
        """Extract pipeline entry by finding context around a compound code."""
        try:
            import re
            # Find elements containing the compound code
            elements = soup.find_all(string=re.compile(re.escape(compound_code)))
            
            for element in elements:
                if hasattr(element, 'parent'):
                    # Get the parent container
                    container = element.parent
                    
                    # Look for a table row or larger container
                    for _ in range(5):  # Go up max 5 levels
                        if container.name == 'tr':  # Found table row
                            return self._extract_from_table_row(container, compound_code)
                        elif container.parent:
                            container = container.parent
                        else:
                            break
                    
                    # If not in table, extract from general container
                    entry = self._extract_from_container(container, compound_code)
                    if entry:
                        return entry
            
        except Exception as e:
            self.logger.debug(f"Error extracting by compound code {compound_code}: {e}")
        
        return None
    
    def _extract_from_table_row(self, row: Tag, compound_code: str) -> Optional[PipelineEntry]:
        """Extract data from a table row containing a compound code."""
        try:
            cells = row.find_all(['td', 'th'])
            entry_data = {'compound_name': compound_code}
            
            for cell in cells:
                cell_text = self._clean_text(cell.get_text())
                if not cell_text or cell_text == compound_code:
                    continue
                
                if self._looks_like_indication(cell_text):
                    entry_data['indication'] = cell_text
                elif self._looks_like_phase(cell_text):
                    phase = self._extract_phase(cell_text)
                    if phase:
                        entry_data['development_phase'] = phase
                elif self._looks_like_therapeutic_area(cell_text):
                    entry_data['therapeutic_area'] = cell_text
                elif 'modality' not in entry_data and any(term in cell_text.lower() for term in ['molecule', 'antibody', 'vaccine']):
                    entry_data['mechanism_of_action'] = cell_text
            
            entry_data['additional_info'] = {
                'extraction_method': 'table_row',
                'row_data': [self._clean_text(cell.get_text()) for cell in cells]
            }
            
            return self._create_pipeline_entry(entry_data)
            
        except Exception as e:
            self.logger.debug(f"Error extracting from table row: {e}")
        
        return None
    
    def _extract_from_container(self, container: Tag, compound_code: str) -> Optional[PipelineEntry]:
        """Extract data from a general container."""
        try:
            text = self._clean_text(container.get_text())
            entry_data = {'compound_name': compound_code}
            
            # Look for patterns in the text
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if not line or line == compound_code:
                    continue
                
                if self._looks_like_indication(line):
                    entry_data['indication'] = line
                elif self._looks_like_phase(line):
                    phase = self._extract_phase(line)
                    if phase:
                        entry_data['development_phase'] = phase
                elif self._looks_like_therapeutic_area(line):
                    entry_data['therapeutic_area'] = line
            
            entry_data['additional_info'] = {
                'extraction_method': 'container',
                'full_text': text
            }
            
            if len(entry_data) > 2:  # More than just compound_name and additional_info
                return self._create_pipeline_entry(entry_data)
            
        except Exception as e:
            self.logger.debug(f"Error extracting from container: {e}")
        
        return None
    
    def _extract_by_phases(self, soup) -> List[PipelineEntry]:
        """Extract entries by looking for phase mentions."""
        entries = []
        
        try:
            import re
            phase_patterns = ['Phase 1', 'Phase 2', 'Phase 3', 'Phase I', 'Phase II', 'Phase III']
            
            for phase_text in phase_patterns:
                elements = soup.find_all(string=re.compile(re.escape(phase_text), re.I))
                
                for element in elements:
                    if hasattr(element, 'parent'):
                        container = element.parent
                        
                        # Go up to find meaningful container
                        for _ in range(3):
                            if container.parent and container.name in ['span', 'small']:
                                container = container.parent
                            else:
                                break
                        
                        entry = self._extract_from_phase_context(container, phase_text)
                        if entry:
                            entries.append(entry)
        
        except Exception as e:
            self.logger.debug(f"Error extracting by phases: {e}")
        
        return entries
    
    def _extract_from_phase_context(self, container: Tag, phase_text: str) -> Optional[PipelineEntry]:
        """Extract entry from context around a phase mention."""
        try:
            text = self._clean_text(container.get_text())
            entry_data = {'development_phase': phase_text}
            
            # Look for compound codes in the same context
            import re
            compound_match = re.search(r'\b(MK-\d+[A-Z]*|V\d+[A-Z]*|[A-Z]{2,3}-\d+[A-Z]*)\b', text)
            if compound_match:
                entry_data['compound_name'] = compound_match.group(1)
            
            # Look for indications
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if self._looks_like_indication(line) and phase_text not in line:
                    entry_data['indication'] = line
                    break
            
            entry_data['additional_info'] = {
                'extraction_method': 'phase_context',
                'context_text': text
            }
            
            if 'compound_name' in entry_data or 'indication' in entry_data:
                return self._create_pipeline_entry(entry_data)
            
        except Exception as e:
            self.logger.debug(f"Error extracting from phase context: {e}")
        
        return None
    
    def _extract_by_indications(self, soup) -> List[PipelineEntry]:
        """Extract entries by looking for medical indications."""
        entries = []
        
        try:
            # Common indication terms for Merck
            indication_terms = [
                'cancer', 'carcinoma', 'tumor', 'oncology', 'leukemia', 'lymphoma',
                'diabetes', 'cardiovascular', 'atherosclerosis', 'hypertension',
                'alzheimer', 'dementia', 'infectious disease', 'HIV', 'hepatitis'
            ]
            
            for term in indication_terms:
                elements = soup.find_all(string=re.compile(term, re.I))
                
                for element in elements[:5]:  # Limit to avoid too many duplicates
                    if hasattr(element, 'parent'):
                        container = element.parent
                        
                        # Go up to find meaningful container
                        for _ in range(3):
                            if container.parent:
                                container = container.parent
                            else:
                                break
                        
                        entry = self._extract_from_indication_context(container, term)
                        if entry:
                            entries.append(entry)
        
        except Exception as e:
            self.logger.debug(f"Error extracting by indications: {e}")
        
        return entries
    
    def _extract_from_indication_context(self, container: Tag, indication_term: str) -> Optional[PipelineEntry]:
        """Extract entry from context around an indication mention."""
        try:
            text = self._clean_text(container.get_text())
            entry_data = {}
            
            # Look for compound codes in the same context
            import re
            compound_match = re.search(r'\b(MK-\d+[A-Z]*|V\d+[A-Z]*|[A-Z]{2,3}-\d+[A-Z]*)\b', text)
            if compound_match:
                entry_data['compound_name'] = compound_match.group(1)
            
            # Look for the full indication text
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if indication_term.lower() in line.lower() and self._looks_like_indication(line):
                    entry_data['indication'] = line
                    break
            
            # Look for phase information
            phase_match = re.search(r'Phase\s+([1-3I]+)', text, re.I)
            if phase_match:
                entry_data['development_phase'] = f"Phase {phase_match.group(1)}"
            
            entry_data['additional_info'] = {
                'extraction_method': 'indication_context',
                'context_text': text[:200]  # Limit text length
            }
            
            if 'compound_name' in entry_data or 'indication' in entry_data:
                return self._create_pipeline_entry(entry_data)
            
        except Exception as e:
            self.logger.debug(f"Error extracting from indication context: {e}")
        
        return None
    
    def _create_merck_header_mapping(self, headers: List[str]) -> Dict[str, str]:
        """Create mapping from Merck table headers to standard field names."""
        mapping = {}
        
        for header in headers:
            header_lower = header.lower()
            
            if any(term in header_lower for term in ['molecule', 'compound', 'drug', 'name']):
                mapping[header] = 'compound_name'
            elif any(term in header_lower for term in ['indication', 'disease', 'condition']):
                mapping[header] = 'indication'
            elif any(term in header_lower for term in ['phase', 'stage', 'status']):
                mapping[header] = 'development_phase'
            elif any(term in header_lower for term in ['therapeutic', 'area', 'category']):
                mapping[header] = 'therapeutic_area'
            elif any(term in header_lower for term in ['modality', 'mechanism', 'action']):
                mapping[header] = 'mechanism_of_action'
        
        return mapping
    
    def _looks_like_therapeutic_area(self, text: str) -> bool:
        """Check if text looks like a therapeutic area."""
        if not text or len(text) > 100:
            return False
        
        therapeutic_areas = [
            'oncology', 'cardiovascular', 'neurology', 'immunology', 'infectious disease',
            'diabetes', 'respiratory', 'dermatology', 'ophthalmology', 'psychiatry'
        ]
        
        text_lower = text.lower()
        return any(area in text_lower for area in therapeutic_areas)
    
    def _has_meaningful_data(self, entry_data: Dict) -> bool:
        """Check if entry data has meaningful pharmaceutical information."""
        # Must have at least compound name or indication
        if not (entry_data.get('compound_name') or entry_data.get('indication')):
            return False
        
        # Skip entries that are just headers or navigation
        compound_name = entry_data.get('compound_name', '')
        if compound_name.lower() in ['molecule name', 'compound', 'drug', 'name', '']:
            return False
        
        return True
    
    def _deduplicate_entries(self, entries: List[PipelineEntry]) -> List[PipelineEntry]:
        """Remove duplicate entries based on compound name and indication."""
        seen = set()
        unique_entries = []
        
        for entry in entries:
            # Create a key based on compound name and indication
            key = (
                entry.compound_name or '',
                entry.indication or ''
            )
            
            if key not in seen and key != ('', ''):
                seen.add(key)
                unique_entries.append(entry)
        
        return unique_entries
    
    def _extract_merck_pipeline_entries(self, html_content: str) -> List[PipelineEntry]:
        """Extract pipeline entries using Merck's specific data patterns.
        
        Args:
            html_content: Raw HTML content
            
        Returns:
            List of extracted pipeline entries
        """
        entries = []
        
        try:
            # Merck's pipeline data follows specific patterns
            # Pattern 1: "CompoundName Indication Therapeutic area: Area Mechanism of Action: MOA Modality: Modality"
            # Pattern 2: "CompoundName (OtherName) Indication (NCT...) Therapeutic area: Area"
            
            # Split content into potential entry blocks
            # Look for compound code patterns as entry separators - improved to avoid false positives
            compound_pattern = r'\b(MK-\d+[A-Z]*|V\d+[A-Z]*)\b'  # More specific for Merck compounds
            
            # Find all compound codes and their positions
            compound_matches = list(re.finditer(compound_pattern, html_content))
            self.logger.info(f"Found {len(compound_matches)} compound code matches")
            
            for i, match in enumerate(compound_matches):
                compound_code = match.group(1)
                start_pos = match.start()
                
                # Determine the end position for this entry (start of next compound or end of content)
                if i + 1 < len(compound_matches):
                    end_pos = compound_matches[i + 1].start()
                else:
                    end_pos = start_pos + 2000  # Take next 2000 characters
                
                # Extract the text block for this compound
                text_block = html_content[start_pos:end_pos]
                
                # Parse the entry from this text block
                entry = self._parse_merck_entry_block(compound_code, text_block)
                if entry:
                    entries.append(entry)
            
            self.logger.info(f"Pattern extraction created {len(entries)} entries")
            
        except Exception as e:
            self.logger.error(f"Error in pattern extraction: {e}")
        
        return entries
    
    def _parse_merck_entry_block(self, compound_code: str, text_block: str) -> Optional[PipelineEntry]:
        """Parse a single Merck entry from a text block.
        
        Args:
            compound_code: The compound code (e.g., MK-1234)
            text_block: Text block containing the compound information
            
        Returns:
            PipelineEntry if successfully parsed, None otherwise
        """
        try:
            entry_data = {
                'compound_name': compound_code,
                'additional_info': {'extraction_method': 'pattern_based'}
            }
            
            # Clean the text block
            clean_text = self._clean_text(text_block)
            
            # Extract therapeutic area
            therapeutic_match = re.search(r'Therapeutic area:\s*([^.]+?)(?:\s+Mechanism|$)', clean_text, re.IGNORECASE)
            if therapeutic_match:
                entry_data['therapeutic_area'] = therapeutic_match.group(1).strip()
            
            # Extract mechanism of action
            moa_match = re.search(r'Mechanism of Action:\s*([^.]+?)(?:\s+Modality|$)', clean_text, re.IGNORECASE)
            if moa_match:
                entry_data['mechanism_of_action'] = moa_match.group(1).strip()
            
            # Extract modality
            modality_match = re.search(r'Modality:\s*([^.]+?)(?:\s|$)', clean_text, re.IGNORECASE)
            if modality_match:
                entry_data['additional_info']['modality'] = modality_match.group(1).strip()
            
            # Extract indication (look for medical terms before "Therapeutic area")
            # Common pattern: "CompoundName Indication Therapeutic area"
            indication_pattern = rf'{re.escape(compound_code)}\s+([^.]+?)\s+Therapeutic area'
            indication_match = re.search(indication_pattern, clean_text, re.IGNORECASE)
            if indication_match:
                potential_indication = indication_match.group(1).strip()
                # Clean up the indication
                potential_indication = re.sub(r'\([^)]*\)', '', potential_indication).strip()  # Remove parentheses
                # Ensure potential_indication is a string before calling _looks_like_indication
                if isinstance(potential_indication, str) and self._looks_like_indication(potential_indication):
                    entry_data['indication'] = potential_indication
            
            # Alternative indication extraction - look for medical terms in the text
            if 'indication' not in entry_data:
                indication_patterns = [
                    r'(atherosclerosis)',
                    r'(cancer|carcinoma|tumor|leukemia|lymphoma)',
                    r'(diabetes|diabetic)',
                    r'(alzheimer|dementia)',
                    r'(hypertension|cardiovascular)',
                    r'(arthritis|rheumatoid)',
                    r'([A-Z][a-z]+ [a-z]+ cancer)',
                    r'([A-Z][a-z]+, uncomplicated)'
                ]
                
                for pattern in indication_patterns:
                    match = re.search(pattern, clean_text, re.IGNORECASE)
                    if match:
                        indication_text = match.group(1)
                        # Ensure indication_text is a string before calling _looks_like_indication
                        if isinstance(indication_text, str) and self._looks_like_indication(indication_text):
                            entry_data['indication'] = indication_text
                            break
            
            # Extract development phase from status information
            phase_patterns = [
                r'Under Review\s*\([^)]*\)',
                r'Phase\s+([1-3I]+)',
                r'(Phase\s+[1-3I]+)',
                r'(Under Review)',
                r'(Approved)',
                r'(Launched)'
            ]
            
            for pattern in phase_patterns:
                phase_match = re.search(pattern, clean_text, re.IGNORECASE)
                if phase_match:
                    if 'Under Review' in phase_match.group(0):
                        entry_data['development_phase'] = 'Under Review'
                    elif 'Phase' in phase_match.group(0):
                        entry_data['development_phase'] = phase_match.group(0)
                    else:
                        entry_data['development_phase'] = phase_match.group(1)
                    break
            
            # Look for NCT numbers (clinical trial identifiers)
            nct_matches = re.findall(r'NCT\d+', clean_text)
            if nct_matches:
                entry_data['additional_info']['clinical_trials'] = nct_matches
            
            # Create entry if we have meaningful data
            if self._has_meaningful_merck_data(entry_data):
                return self._create_pipeline_entry(entry_data)
            
        except Exception as e:
            self.logger.debug(f"Error parsing entry block for {compound_code}: {e}")
            import traceback
            self.logger.debug(f"Traceback: {traceback.format_exc()}")
        
        return None
    
    def _has_meaningful_merck_data(self, entry_data: Dict) -> bool:
        """Check if Merck entry data has meaningful pharmaceutical information.
        
        This is more lenient than the general _has_meaningful_data method
        to account for Merck's specific data structure.
        """
        # Must have compound name
        if not entry_data.get('compound_name'):
            return False
        
        # Must have at least one of: indication, therapeutic_area, or mechanism_of_action
        meaningful_fields = [
            entry_data.get('indication'),
            entry_data.get('therapeutic_area'),
            entry_data.get('mechanism_of_action')
        ]
        
        return any(field for field in meaningful_fields)
        
        return any(field for field in meaningful_fields)
    
    def _calculate_merck_confidence(self, entries: List[PipelineEntry], html_content: str) -> float:
        """Calculate confidence score for Merck extraction."""
        if not entries:
            return 0.0
        
        base_score = 0.4  # Base score for finding entries
        
        # Bonus for having compound names (Merck uses specific codes)
        entries_with_names = sum(1 for e in entries if e.compound_name and 'MK-' in str(e.compound_name))
        if entries_with_names > 0:
            base_score += 0.3
        
        # Bonus for having indications
        entries_with_indications = sum(1 for e in entries if e.indication)
        if entries_with_indications > 0:
            indication_ratio = entries_with_indications / len(entries)
            base_score += indication_ratio * 0.2
        
        # Bonus for having phases
        entries_with_phases = sum(1 for e in entries if e.development_phase)
        if entries_with_phases > 0:
            phase_ratio = entries_with_phases / len(entries)
            base_score += phase_ratio * 0.1
        
        # Check if we're getting close to expected numbers
        expected_total = 85  # 50+ Phase 2 + 30+ Phase 3 + 5+ under review
        if len(entries) >= expected_total * 0.5:  # At least 50% of expected
            base_score += 0.1
        if len(entries) >= expected_total * 0.8:  # At least 80% of expected
            base_score += 0.1
        
        return min(1.0, base_score)
    
    def _extract_from_table(self, table: Tag) -> List[PipelineEntry]:
        """Extract entries from a table element."""
        entries = []
        
        try:
            rows = table.find_all('tr')
            if len(rows) < 2:  # Need at least header + 1 data row
                return entries
            
            # Try to identify header row
            header_row = rows[0]
            headers = [self._clean_text(th.get_text()) for th in header_row.find_all(['th', 'td'])]
            
            # Map common header variations to standard fields
            header_mapping = self._create_header_mapping(headers)
            
            # Extract data rows
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                if len(cells) != len(headers):
                    continue
                
                entry_data = {}
                for i, cell in enumerate(cells):
                    if i < len(headers) and headers[i] in header_mapping:
                        field_name = header_mapping[headers[i]]
                        entry_data[field_name] = self._clean_text(cell.get_text())
                
                if entry_data:
                    entry = self._create_pipeline_entry(entry_data)
                    if entry:
                        entries.append(entry)
        
        except Exception as e:
            self.logger.debug(f"Error extracting from table: {e}")
        
        return entries
    
    def _extract_from_section(self, section: Tag) -> List[PipelineEntry]:
        """Extract entries from a section element."""
        entries = []
        
        try:
            # Look for nested elements that might contain pipeline info
            items = section.find_all(['div', 'p', 'span'], recursive=True)
            
            current_entry = {}
            for item in items:
                text = self._clean_text(item.get_text())
                if not text:
                    continue
                
                # Try to identify what type of information this is
                if self._looks_like_compound_name(text):
                    if current_entry:
                        entry = self._create_pipeline_entry(current_entry)
                        if entry:
                            entries.append(entry)
                    current_entry = {"compound_name": text}
                elif self._looks_like_indication(text):
                    current_entry["indication"] = text
                elif self._looks_like_phase(text):
                    current_entry["development_phase"] = text
            
            # Don't forget the last entry
            if current_entry:
                entry = self._create_pipeline_entry(current_entry)
                if entry:
                    entries.append(entry)
        
        except Exception as e:
            self.logger.debug(f"Error extracting from section: {e}")
        
        return entries
    
    def _extract_from_list(self, list_elem: Tag) -> List[PipelineEntry]:
        """Extract entries from a list element."""
        entries = []
        
        try:
            items = list_elem.find_all('li')
            
            for item in items:
                text = self._clean_text(item.get_text())
                if not text:
                    continue
                
                # Try to parse structured list items
                entry_data = self._parse_list_item_text(text)
                if entry_data:
                    entry = self._create_pipeline_entry(entry_data)
                    if entry:
                        entries.append(entry)
        
        except Exception as e:
            self.logger.debug(f"Error extracting from list: {e}")
        
        return entries
    
    def _create_header_mapping(self, headers: List[str]) -> Dict[str, str]:
        """Create mapping from table headers to standard field names."""
        mapping = {}
        
        for header in headers:
            header_lower = header.lower()
            
            if any(term in header_lower for term in ['compound', 'drug', 'product', 'name']):
                mapping[header] = 'compound_name'
            elif any(term in header_lower for term in ['indication', 'disease', 'condition']):
                mapping[header] = 'indication'
            elif any(term in header_lower for term in ['phase', 'stage', 'development']):
                mapping[header] = 'development_phase'
            elif any(term in header_lower for term in ['therapeutic', 'area', 'category']):
                mapping[header] = 'therapeutic_area'
            elif any(term in header_lower for term in ['mechanism', 'action', 'moa']):
                mapping[header] = 'mechanism_of_action'
            elif any(term in header_lower for term in ['status', 'state']):
                mapping[header] = 'status'
        
        return mapping
    
    def _create_pipeline_entry(self, entry_data: Dict[str, str]) -> Optional[PipelineEntry]:
        """Create a PipelineEntry from extracted data."""
        if not entry_data or not any(entry_data.values()):
            return None
        
        # Extract phase if present in any field (but skip non-string values like additional_info)
        phase = None
        for key, value in entry_data.items():
            if value and isinstance(value, str) and key != 'additional_info':
                extracted_phase = self._extract_phase(value)
                if extracted_phase:
                    phase = extracted_phase
                    break
        
        return PipelineEntry(
            compound_name=entry_data.get('compound_name'),
            indication=entry_data.get('indication'),
            therapeutic_area=entry_data.get('therapeutic_area'),
            development_phase=phase or entry_data.get('development_phase'),
            mechanism_of_action=entry_data.get('mechanism_of_action'),
            status=entry_data.get('status'),
            additional_info=entry_data.get('additional_info', {})
        )
    
    def _looks_like_compound_name(self, text: str) -> bool:
        """Check if text looks like a compound name."""
        if not text or len(text) > 100:
            return False
        
        # Common patterns for compound names
        patterns = [
            r'^[A-Z]{2,}-\d+',  # e.g., MK-1234
            r'^\w+mab$',        # monoclonal antibodies
            r'^\w+ib$',         # kinase inhibitors
            r'^\w+zumab$',      # humanized antibodies
        ]
        
        for pattern in patterns:
            if re.match(pattern, text):
                return True
        
        # Check for Merck-specific compound codes
        if re.search(r'\b(MK-\d+[A-Z]*|V\d+[A-Z]*)\b', text):
            return True
        
        return False
    
    def _looks_like_indication(self, text: str) -> bool:
        """Check if text looks like a medical indication."""
        if not text:
            return False
        
        indication_terms = [
            'cancer', 'diabetes', 'alzheimer', 'hypertension', 'arthritis',
            'infection', 'disease', 'syndrome', 'disorder', 'condition'
        ]
        
        text_lower = text.lower()
        return any(term in text_lower for term in indication_terms)
    
    def _looks_like_phase(self, text: str) -> bool:
        """Check if text looks like a development phase."""
        if not text:
            return False
        
        phase_terms = ['phase', 'preclinical', 'discovery', 'registration', 'approved']
        text_lower = text.lower()
        return any(term in text_lower for term in phase_terms)
    
    def _parse_list_item_text(self, text: str) -> Dict[str, str]:
        """Parse structured text from a list item."""
        entry_data = {}
        
        # Try to split on common delimiters
        parts = re.split(r'[:\-–—]', text, maxsplit=1)
        if len(parts) == 2:
            left, right = parts
            left = self._clean_text(left)
            right = self._clean_text(right)
            
            if self._looks_like_compound_name(left):
                entry_data['compound_name'] = left
                entry_data['indication'] = right
            elif self._looks_like_indication(left):
                entry_data['indication'] = left
                entry_data['compound_name'] = right
        
        return entry_data
    
    def _calculate_confidence(self, entries: List[PipelineEntry], html_content: str) -> float:
        """Calculate confidence score for extraction."""
        if not entries:
            return 0.0
        
        score = 0.5  # Base score for finding entries
        
        # Bonus for having compound names
        entries_with_names = sum(1 for e in entries if e.compound_name)
        if entries_with_names > 0:
            score += 0.2
        
        # Bonus for having indications
        entries_with_indications = sum(1 for e in entries if e.indication)
        if entries_with_indications > 0:
            score += 0.2
        
        # Bonus for having phases
        entries_with_phases = sum(1 for e in entries if e.development_phase)
        if entries_with_phases > 0:
            score += 0.1
        
        return min(1.0, score)
    
    def _get_strategies_used(self, entries: List[PipelineEntry]) -> List[str]:
        """Get list of extraction strategies that found entries."""
        strategies = []
        if entries:
            strategies.append("adaptive_extraction")
        return strategies


class NovoNordiskExtractor(BaseExtractor):
    """Extractor for Novo Nordisk pipeline data."""
    
    def __init__(self):
        super().__init__("Novo Nordisk")
    
    def extract(self, html_content: str) -> ExtractionResult:
        """Extract pipeline data from Novo Nordisk website.
        
        Note: Novo Nordisk website appears to use heavy JavaScript or has anti-scraping measures,
        returning minimal static content. This extractor attempts multiple strategies but may
        return limited results due to these technical limitations.
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            entries = []
            errors = []
            
            # Check if we got minimal content (likely JavaScript-heavy site)
            content_size = len(html_content.strip())
            text_content = soup.get_text().strip()
            
            self.logger.info(f"Novo Nordisk content size: {content_size} bytes")
            self.logger.info(f"Text content preview: {text_content[:200]}...")
            
            if content_size < 1000:
                errors.append("Website returned minimal content - likely requires JavaScript or has anti-scraping measures")
                self.logger.warning("Novo Nordisk website returned minimal content")
            
            # Strategy 1: Look for any pipeline-related content in the available text
            entries.extend(self._extract_from_text_content(text_content))
            
            # Strategy 2: Look for structured data or hidden elements
            entries.extend(self._extract_from_structured_data(soup))
            
            # Strategy 3: Look for any pharmaceutical terms or compound codes
            entries.extend(self._extract_pharmaceutical_terms(text_content))
            
            # Strategy 4: Check for alternative data sources or API endpoints
            api_entries = self._check_for_api_data(soup)
            entries.extend(api_entries)
            
            # Remove duplicates
            entries = self._deduplicate_entries(entries)
            
            # Calculate confidence score
            confidence_score = self._calculate_novo_confidence(entries, content_size, errors)
            
            return ExtractionResult(
                entries=entries,
                extraction_method="novo_nordisk_multi_strategy",
                confidence_score=confidence_score,
                metadata={
                    "total_entries": len(entries),
                    "content_size_bytes": content_size,
                    "text_content_length": len(text_content),
                    "extraction_strategies_used": [
                        "text_content_analysis",
                        "structured_data_search", 
                        "pharmaceutical_term_extraction",
                        "api_endpoint_detection"
                    ],
                    "website_limitations": "JavaScript-heavy or anti-scraping measures detected"
                },
                errors=errors
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting Novo Nordisk data: {e}")
            return ExtractionResult(
                entries=[],
                extraction_method="novo_nordisk_multi_strategy",
                confidence_score=0.0,
                errors=[str(e)]
            )
    
    def _extract_from_text_content(self, text_content: str) -> List[PipelineEntry]:
        """Extract pipeline entries from available text content."""
        entries = []
        
        try:
            if not text_content or len(text_content) < 50:
                return entries
            
            # Look for mentions of therapeutic areas that Novo Nordisk focuses on
            therapeutic_areas = {
                'diabetes': 'Diabetes',
                'obesity': 'Obesity', 
                'cardiovascular': 'Cardiovascular',
                'rare blood': 'Rare Blood Disorders',
                'endocrine': 'Endocrine Disorders',
                'chronic': 'Chronic Diseases'
            }
            
            found_areas = []
            text_lower = text_content.lower()
            
            for term, area in therapeutic_areas.items():
                if term in text_lower:
                    found_areas.append(area)
            
            # Create entries based on known Novo Nordisk focus areas
            if found_areas:
                for area in found_areas:
                    entry = PipelineEntry(
                        compound_name=None,  # Not available from minimal content
                        indication=None,     # Not available from minimal content
                        therapeutic_area=area,
                        development_phase=None,
                        mechanism_of_action=None,
                        status="In Development",  # Inferred from R&D pipeline context
                        additional_info={
                            'extraction_method': 'text_content_inference',
                            'source_text': text_content[:200],
                            'confidence': 'low',
                            'note': 'Inferred from therapeutic area mentions in minimal content'
                        }
                    )
                    entries.append(entry)
            
        except Exception as e:
            self.logger.debug(f"Error extracting from text content: {e}")
        
        return entries
    
    def _extract_from_structured_data(self, soup) -> List[PipelineEntry]:
        """Look for any structured data, JSON-LD, or hidden elements."""
        entries = []
        
        try:
            # Look for JSON-LD structured data
            json_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_scripts:
                try:
                    import json
                    data = json.loads(script.string)
                    # Look for any pharmaceutical or pipeline-related data
                    if isinstance(data, dict):
                        entries.extend(self._extract_from_json_data(data))
                except (json.JSONDecodeError, AttributeError):
                    continue
            
            # Look for data attributes that might contain pipeline info
            elements_with_data = soup.find_all(attrs=lambda x: x and any(
                key.startswith('data-') and any(term in key.lower() for term in ['pipeline', 'drug', 'compound', 'phase'])
                for key in x.keys()
            ))
            
            for element in elements_with_data:
                entry = self._extract_from_data_attributes(element)
                if entry:
                    entries.append(entry)
            
            # Look for hidden or dynamically loaded content indicators
            hidden_elements = soup.find_all(attrs={'style': lambda x: x and 'display:none' in x.replace(' ', '')})
            for element in hidden_elements:
                text = self._clean_text(element.get_text())
                if text and any(term in text.lower() for term in ['pipeline', 'phase', 'clinical', 'development']):
                    entry = PipelineEntry(
                        compound_name=None,
                        indication=None,
                        therapeutic_area=None,
                        development_phase=None,
                        additional_info={
                            'extraction_method': 'hidden_content',
                            'hidden_text': text[:200],
                            'note': 'Found in hidden HTML element'
                        }
                    )
                    entries.append(entry)
            
        except Exception as e:
            self.logger.debug(f"Error extracting structured data: {e}")
        
        return entries
    
    def _extract_pharmaceutical_terms(self, text_content: str) -> List[PipelineEntry]:
        """Extract any pharmaceutical compound codes or drug names from text."""
        entries = []
        
        try:
            if not text_content:
                return entries
            
            import re
            
            # Look for common pharmaceutical compound patterns
            compound_patterns = [
                r'\b(NN\d+[A-Z]*)\b',      # Novo Nordisk compounds (NN1234)
                r'\b([A-Z]{2,3}-\d+[A-Z]*)\b',  # General compound codes
                r'\b(semaglutide|liraglutide|insulin|ozempic|wegovy|victoza)\b',  # Known NN drugs
            ]
            
            found_compounds = set()
            for pattern in compound_patterns:
                matches = re.findall(pattern, text_content, re.IGNORECASE)
                found_compounds.update(matches)
            
            # Create entries for found compounds
            for compound in found_compounds:
                # Try to determine therapeutic area based on known NN compounds
                therapeutic_area = self._get_therapeutic_area_for_compound(compound.lower())
                
                entry = PipelineEntry(
                    compound_name=compound,
                    indication=None,
                    therapeutic_area=therapeutic_area,
                    development_phase=None,
                    additional_info={
                        'extraction_method': 'pharmaceutical_term_extraction',
                        'confidence': 'medium' if compound.lower() in ['semaglutide', 'liraglutide', 'insulin'] else 'low',
                        'note': 'Extracted from text content using pattern matching'
                    }
                )
                entries.append(entry)
            
        except Exception as e:
            self.logger.debug(f"Error extracting pharmaceutical terms: {e}")
        
        return entries
    
    def _check_for_api_data(self, soup) -> List[PipelineEntry]:
        """Check for API endpoints or AJAX calls that might contain pipeline data."""
        entries = []
        
        try:
            # Look for script tags that might contain API endpoints
            scripts = soup.find_all('script')
            api_patterns = [
                r'api[./]pipeline',
                r'pipeline[./]data',
                r'clinical[./]trials',
                r'research[./]development'
            ]
            
            found_apis = []
            for script in scripts:
                if script.string:
                    script_text = script.string
                    for pattern in api_patterns:
                        import re
                        matches = re.findall(pattern, script_text, re.IGNORECASE)
                        found_apis.extend(matches)
            
            # If we found potential API endpoints, create a placeholder entry
            if found_apis:
                entry = PipelineEntry(
                    compound_name=None,
                    indication=None,
                    therapeutic_area=None,
                    development_phase=None,
                    additional_info={
                        'extraction_method': 'api_endpoint_detection',
                        'potential_apis': found_apis[:5],  # Limit to first 5
                        'note': 'Detected potential API endpoints for pipeline data'
                    }
                )
                entries.append(entry)
            
        except Exception as e:
            self.logger.debug(f"Error checking for API data: {e}")
        
        return entries
    
    def _extract_from_json_data(self, json_data: dict) -> List[PipelineEntry]:
        """Extract pipeline data from JSON-LD or other JSON structures."""
        entries = []
        
        try:
            # Recursively search for pharmaceutical-related data
            def search_json(obj, path=""):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        new_path = f"{path}.{key}" if path else key
                        if any(term in key.lower() for term in ['pipeline', 'drug', 'compound', 'clinical', 'phase']):
                            # Found potentially relevant data
                            if isinstance(value, str) and len(value) > 5:
                                entry = PipelineEntry(
                                    compound_name=value if 'compound' in key.lower() else None,
                                    indication=value if 'indication' in key.lower() else None,
                                    development_phase=value if 'phase' in key.lower() else None,
                                    additional_info={
                                        'extraction_method': 'json_structured_data',
                                        'json_path': new_path,
                                        'json_value': str(value)[:100]
                                    }
                                )
                                entries.append(entry)
                        search_json(value, new_path)
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        search_json(item, f"{path}[{i}]")
            
            search_json(json_data)
            
        except Exception as e:
            self.logger.debug(f"Error extracting from JSON data: {e}")
        
        return entries
    
    def _extract_from_data_attributes(self, element) -> Optional[PipelineEntry]:
        """Extract pipeline data from HTML element data attributes."""
        try:
            entry_data = {}
            
            # Check all data attributes
            for attr_name, attr_value in element.attrs.items():
                if attr_name.startswith('data-'):
                    attr_lower = attr_name.lower()
                    if 'compound' in attr_lower or 'drug' in attr_lower:
                        entry_data['compound_name'] = str(attr_value)
                    elif 'indication' in attr_lower or 'disease' in attr_lower:
                        entry_data['indication'] = str(attr_value)
                    elif 'phase' in attr_lower:
                        entry_data['development_phase'] = str(attr_value)
                    elif 'therapeutic' in attr_lower:
                        entry_data['therapeutic_area'] = str(attr_value)
            
            if entry_data:
                entry_data['additional_info'] = {
                    'extraction_method': 'data_attributes',
                    'element_tag': element.name,
                    'all_data_attrs': {k: v for k, v in element.attrs.items() if k.startswith('data-')}
                }
                return self._create_pipeline_entry(entry_data)
            
        except Exception as e:
            self.logger.debug(f"Error extracting from data attributes: {e}")
        
        return None
    
    def _get_therapeutic_area_for_compound(self, compound_name: str) -> Optional[str]:
        """Get therapeutic area for known Novo Nordisk compounds."""
        compound_mapping = {
            'semaglutide': 'Diabetes/Obesity',
            'liraglutide': 'Diabetes/Obesity', 
            'insulin': 'Diabetes',
            'ozempic': 'Diabetes',
            'wegovy': 'Obesity',
            'victoza': 'Diabetes',
            'rybelsus': 'Diabetes',
            'saxenda': 'Obesity'
        }
        
        return compound_mapping.get(compound_name.lower())
    
    def _deduplicate_entries(self, entries: List[PipelineEntry]) -> List[PipelineEntry]:
        """Remove duplicate entries based on available data."""
        if not entries:
            return entries
        
        seen = set()
        unique_entries = []
        
        for entry in entries:
            # Create a key based on available non-None fields
            key_parts = []
            if entry.compound_name:
                key_parts.append(entry.compound_name.lower())
            if entry.indication:
                key_parts.append(entry.indication.lower())
            if entry.therapeutic_area:
                key_parts.append(entry.therapeutic_area.lower())
            
            key = '|'.join(key_parts) if key_parts else str(id(entry))
            
            if key not in seen:
                seen.add(key)
                unique_entries.append(entry)
        
        return unique_entries
    
    def _calculate_novo_confidence(self, entries: List[PipelineEntry], content_size: int, errors: List[str]) -> float:
        """Calculate confidence score for Novo Nordisk extraction."""
        if not entries:
            return 0.0
        
        base_score = 0.1  # Very low base score due to website limitations
        
        # Penalty for minimal content
        if content_size < 1000:
            base_score = max(0.05, base_score - 0.05)
        
        # Bonus for finding any meaningful data despite limitations
        if entries:
            base_score += 0.2
        
        # Bonus for finding compound names
        entries_with_compounds = sum(1 for e in entries if e.compound_name)
        if entries_with_compounds > 0:
            base_score += 0.2
        
        # Bonus for finding therapeutic areas
        entries_with_areas = sum(1 for e in entries if e.therapeutic_area)
        if entries_with_areas > 0:
            base_score += 0.1
        
        # Penalty for errors
        if errors:
            base_score = max(0.05, base_score - len(errors) * 0.05)
        
        return min(1.0, base_score)
    
    def _create_pipeline_entry(self, entry_data: Dict[str, str]) -> Optional[PipelineEntry]:
        """Create a PipelineEntry from extracted data."""
        if not entry_data or not any(v for v in entry_data.values() if v and v != entry_data.get('additional_info')):
            return None
        
        return PipelineEntry(
            compound_name=entry_data.get('compound_name'),
            indication=entry_data.get('indication'),
            therapeutic_area=entry_data.get('therapeutic_area'),
            development_phase=entry_data.get('development_phase'),
            mechanism_of_action=entry_data.get('mechanism_of_action'),
            status=entry_data.get('status'),
            additional_info=entry_data.get('additional_info', {})
        )


class NovartisExtractor(BaseExtractor):
    """Extractor for Novartis pipeline data."""
    
    def __init__(self):
        super().__init__("Novartis")
        self.base_url = "https://www.novartis.com/research-development/novartis-pipeline"
        self.total_pages = 5  # Pages 0-4
    
    def extract(self, html_content: str) -> ExtractionResult:
        """Extract pipeline data from Novartis website."""
        try:
            import requests
            import time
            
            all_entries = []
            errors = []
            pages_processed = 0
            
            # Extract from all pages (0-4)
            for page in range(self.total_pages):
                try:
                    page_url = f"{self.base_url}?page={page}"
                    self.logger.info(f"Extracting from Novartis page {page}: {page_url}")
                    
                    # Add delay between requests to be respectful
                    if page > 0:
                        time.sleep(2)
                    
                    # Fetch the page
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                    }
                    response = requests.get(page_url, headers=headers, timeout=30)
                    response.raise_for_status()
                    
                    # Parse the page
                    page_entries = self._extract_from_page(response.text, page)
                    all_entries.extend(page_entries)
                    pages_processed += 1
                    
                    self.logger.info(f"Extracted {len(page_entries)} entries from page {page}")
                    
                except Exception as e:
                    error_msg = f"Error extracting from page {page}: {e}"
                    self.logger.error(error_msg)
                    errors.append(error_msg)
            
            # Calculate confidence score
            confidence_score = self._calculate_confidence(all_entries, pages_processed)
            
            return ExtractionResult(
                entries=all_entries,
                extraction_method="novartis_paginated",
                confidence_score=confidence_score,
                metadata={
                    "total_entries": len(all_entries),
                    "pages_processed": pages_processed,
                    "total_pages": self.total_pages,
                    "extraction_strategies_used": ["paginated_extraction", "table_parsing", "card_parsing"]
                },
                errors=errors
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting Novartis data: {e}")
            return ExtractionResult(
                entries=[],
                extraction_method="novartis_paginated",
                confidence_score=0.0,
                errors=[str(e)]
            )
    
    def _extract_from_page(self, html_content: str, page_number: int) -> List[PipelineEntry]:
        """Extract pipeline entries from a single page."""
        entries = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Strategy 1: Look for pipeline cards/items with specific Novartis structure
            # Based on the test output, Novartis has divs with compound codes and names
            pipeline_cards = soup.find_all(['div', 'article', 'section'])
            
            for card in pipeline_cards:
                entry = self._extract_novartis_card(card)
                if entry:
                    entries.append(entry)
            
            # Strategy 2: Look for text patterns that match pharmaceutical data
            # Extract compound codes (like AAA601, DAK539, KAE609)
            compound_pattern = r'\b[A-Z]{2,4}\d{3,4}\b'
            text_content = soup.get_text()
            
            import re
            compound_matches = re.findall(compound_pattern, text_content)
            
            # For each compound code found, try to extract surrounding context
            for compound_code in set(compound_matches):  # Remove duplicates
                entry = self._extract_by_compound_code(soup, compound_code)
                if entry and not any(e.compound_name == entry.compound_name for e in entries):
                    entries.append(entry)
            
            # Strategy 3: Look for specific pharmaceutical terms and extract context
            pharma_indicators = [
                'Phase 1', 'Phase 2', 'Phase 3', 'Phase I', 'Phase II', 'Phase III',
                'Oncology', 'Hematology', 'Cardiovascular', 'Neurology', 'Immunology'
            ]
            
            for indicator in pharma_indicators:
                elements = soup.find_all(string=re.compile(re.escape(indicator), re.I))
                for element in elements:
                    if hasattr(element, 'parent'):
                        entry = self._extract_from_context(element.parent, indicator)
                        if entry and not any(e.compound_name == entry.compound_name for e in entries):
                            entries.append(entry)
            
            # Add page metadata to entries
            for entry in entries:
                entry.additional_info['source_page'] = page_number
                entry.additional_info['source_url'] = f"{self.base_url}?page={page_number}"
            
        except Exception as e:
            self.logger.error(f"Error extracting from page {page_number}: {e}")
        
        return entries
    
    def _extract_novartis_card(self, card_element) -> Optional[PipelineEntry]:
        """Extract pipeline entry from a Novartis-specific card element."""
        try:
            card_text = self._clean_text(card_element.get_text())
            if not card_text or len(card_text) < 20:
                return None
            
            entry_data = {}
            
            # Look for compound codes (AAA601, DAK539, etc.)
            import re
            compound_match = re.search(r'\b([A-Z]{2,4}\d{3,4})\b', card_text)
            if compound_match:
                entry_data['compound_name'] = compound_match.group(1)
            
            # Look for drug names (usually after compound code)
            # Pattern: compound code followed by drug name
            drug_name_match = re.search(r'\b[A-Z]{2,4}\d{3,4}\s*\n?\s*([a-z][a-zA-Z]+)', card_text)
            if drug_name_match:
                drug_name = drug_name_match.group(1)
                if drug_name not in ['phase', 'oncology', 'cardiovascular']:  # Exclude common non-drug terms
                    if 'compound_name' in entry_data:
                        entry_data['compound_name'] += f" ({drug_name})"
                    else:
                        entry_data['compound_name'] = drug_name
            
            # Look for indications (medical conditions)
            indication_patterns = [
                r'(cancer|carcinoma|tumor|leukemia|lymphoma)',
                r'(diabetes|diabetic)',
                r'(alzheimer|dementia)',
                r'(hypertension|cardiovascular)',
                r'(arthritis|rheumatoid)',
                r'(myelofibrosis|malaria)',
                r'([A-Z][a-z]+ [a-z]+ tumors?)',
                r'([A-Z][a-z]+, uncomplicated)'
            ]
            
            for pattern in indication_patterns:
                match = re.search(pattern, card_text, re.IGNORECASE)
                if match:
                    entry_data['indication'] = match.group(1)
                    break
            
            # Look for therapeutic areas
            therapeutic_areas = [
                'Oncology: Solid Tumors', 'Oncology: Hematology', 'Oncology',
                'Cardiovascular, Renal and Metabolic', 'Cardiovascular',
                'Immunology', 'Neurology', 'In-market Brands and Global Health'
            ]
            
            for area in therapeutic_areas:
                if area in card_text:
                    entry_data['therapeutic_area'] = area
                    break
            
            # Look for phases
            phase_match = re.search(r'Phase\s+([1-3I]+)', card_text, re.IGNORECASE)
            if phase_match:
                phase_num = phase_match.group(1)
                entry_data['development_phase'] = f"Phase {phase_num}"
            
            # Look for mechanism of action (usually short technical terms)
            moa_patterns = [
                r'(BET inhibitor)',
                r'(PfATP[A-Za-z0-9]+)',
                r'([A-Z]{2,}[0-9]+ inhibitor)',
                r'(monoclonal antibody)',
                r'(kinase inhibitor)'
            ]
            
            for pattern in moa_patterns:
                match = re.search(pattern, card_text)
                if match:
                    entry_data['mechanism_of_action'] = match.group(1)
                    break
            
            # Store full text for additional analysis
            entry_data['additional_info'] = {'full_text': card_text}
            
            # Only create entry if we have meaningful data
            if len(entry_data) > 1:  # More than just additional_info
                return self._create_pipeline_entry(entry_data)
                
        except Exception as e:
            self.logger.debug(f"Error extracting from Novartis card: {e}")
        
        return None
    
    def _extract_by_compound_code(self, soup, compound_code: str) -> Optional[PipelineEntry]:
        """Extract pipeline entry by finding context around a compound code."""
        try:
            # Find elements containing the compound code
            elements = soup.find_all(string=re.compile(re.escape(compound_code)))
            
            for element in elements:
                if hasattr(element, 'parent'):
                    # Get the parent container
                    container = element.parent
                    
                    # Look for a larger container that might have all the info
                    for _ in range(3):  # Go up max 3 levels
                        if container.parent:
                            container = container.parent
                        else:
                            break
                    
                    # Extract from this container
                    entry = self._extract_novartis_card(container)
                    if entry and compound_code in str(entry.compound_name or ''):
                        return entry
            
        except Exception as e:
            self.logger.debug(f"Error extracting by compound code {compound_code}: {e}")
        
        return None
    
    def _extract_from_context(self, element, indicator: str) -> Optional[PipelineEntry]:
        """Extract pipeline entry from context around a pharmaceutical indicator."""
        try:
            # Get surrounding context
            container = element
            
            # Go up to find a container with more context
            for _ in range(2):
                if container.parent:
                    container = container.parent
                else:
                    break
            
            entry = self._extract_novartis_card(container)
            if entry:
                # Ensure the indicator is reflected in the entry
                if 'Phase' in indicator and not entry.development_phase:
                    entry.development_phase = indicator
                elif any(term in indicator for term in ['Oncology', 'Cardiovascular', 'Neurology']) and not entry.therapeutic_area:
                    entry.therapeutic_area = indicator
                
                return entry
                
        except Exception as e:
            self.logger.debug(f"Error extracting from context {indicator}: {e}")
        
        return None
    
    def _extract_from_card(self, card_element) -> Optional[PipelineEntry]:
        """Extract pipeline entry from a card-like element."""
        try:
            entry_data = {}
            
            # Look for headings that might contain compound names
            headings = card_element.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            for heading in headings:
                text = self._clean_text(heading.get_text())
                if text and len(text) < 100:  # Reasonable compound name length
                    entry_data['compound_name'] = text
                    break
            
            # Look for text that might be indications
            text_elements = card_element.find_all(['p', 'span', 'div'], string=re.compile(r'cancer|diabetes|disease|syndrome|disorder', re.I))
            for elem in text_elements:
                text = self._clean_text(elem.get_text())
                if self._looks_like_indication(text):
                    entry_data['indication'] = text
                    break
            
            # Look for phase information
            phase_elements = card_element.find_all(string=re.compile(r'phase|preclinical|approved|registration', re.I))
            for elem in phase_elements:
                if hasattr(elem, 'parent'):
                    text = self._clean_text(elem.parent.get_text())
                    phase = self._extract_phase(text)
                    if phase:
                        entry_data['development_phase'] = phase
                        break
            
            # Look for any additional structured data
            data_attrs = card_element.find_all(attrs={'data-compound': True})
            for attr_elem in data_attrs:
                if attr_elem.get('data-compound'):
                    entry_data['compound_name'] = attr_elem.get('data-compound')
                if attr_elem.get('data-indication'):
                    entry_data['indication'] = attr_elem.get('data-indication')
                if attr_elem.get('data-phase'):
                    entry_data['development_phase'] = attr_elem.get('data-phase')
            
            # Collect all text for additional info
            all_text = self._clean_text(card_element.get_text())
            if all_text:
                entry_data['additional_info'] = {'full_text': all_text}
            
            if entry_data:
                return self._create_pipeline_entry(entry_data)
                
        except Exception as e:
            self.logger.debug(f"Error extracting from card: {e}")
        
        return None
    
    def _extract_from_table(self, table) -> List[PipelineEntry]:
        """Extract entries from a table element."""
        entries = []
        
        try:
            rows = table.find_all('tr')
            if len(rows) < 2:  # Need at least header + 1 data row
                return entries
            
            # Try to identify header row
            header_row = rows[0]
            headers = [self._clean_text(th.get_text()) for th in header_row.find_all(['th', 'td'])]
            
            # Map headers to standard fields
            header_mapping = self._create_header_mapping(headers)
            
            # Extract data rows
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                if len(cells) != len(headers):
                    continue
                
                entry_data = {}
                for i, cell in enumerate(cells):
                    if i < len(headers) and headers[i] in header_mapping:
                        field_name = header_mapping[headers[i]]
                        cell_text = self._clean_text(cell.get_text())
                        if cell_text:
                            entry_data[field_name] = cell_text
                
                # Also collect all cell data for additional info
                entry_data['additional_info'] = {
                    'table_data': [self._clean_text(cell.get_text()) for cell in cells]
                }
                
                if entry_data:
                    entry = self._create_pipeline_entry(entry_data)
                    if entry:
                        entries.append(entry)
        
        except Exception as e:
            self.logger.debug(f"Error extracting from table: {e}")
        
        return entries
    
    def _extract_from_list(self, list_elem) -> List[PipelineEntry]:
        """Extract entries from a list element."""
        entries = []
        
        try:
            items = list_elem.find_all('li')
            
            for item in items:
                text = self._clean_text(item.get_text())
                if not text or len(text) < 10:  # Skip very short items
                    continue
                
                # Try to parse structured list items
                entry_data = self._parse_list_item_text(text)
                if entry_data:
                    entry = self._create_pipeline_entry(entry_data)
                    if entry:
                        entries.append(entry)
        
        except Exception as e:
            self.logger.debug(f"Error extracting from list: {e}")
        
        return entries
    
    def _extract_from_generic_element(self, element) -> Optional[PipelineEntry]:
        """Extract from any generic element that might contain pipeline data."""
        try:
            text = self._clean_text(element.get_text())
            if not text or len(text) < 20:
                return None
            
            entry_data = {'additional_info': {'raw_text': text}}
            
            # Try to extract structured information
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                if self._looks_like_compound_name(line) and 'compound_name' not in entry_data:
                    entry_data['compound_name'] = line
                elif self._looks_like_indication(line) and 'indication' not in entry_data:
                    entry_data['indication'] = line
                elif self._looks_like_phase(line) and 'development_phase' not in entry_data:
                    phase = self._extract_phase(line)
                    if phase:
                        entry_data['development_phase'] = phase
            
            if len(entry_data) > 1:  # More than just additional_info
                return self._create_pipeline_entry(entry_data)
                
        except Exception as e:
            self.logger.debug(f"Error extracting from generic element: {e}")
        
        return None
    
    def _create_header_mapping(self, headers: List[str]) -> Dict[str, str]:
        """Create mapping from table headers to standard field names."""
        mapping = {}
        
        for header in headers:
            header_lower = header.lower()
            
            if any(term in header_lower for term in ['compound', 'drug', 'product', 'name', 'asset']):
                mapping[header] = 'compound_name'
            elif any(term in header_lower for term in ['indication', 'disease', 'condition', 'target']):
                mapping[header] = 'indication'
            elif any(term in header_lower for term in ['phase', 'stage', 'development', 'status']):
                mapping[header] = 'development_phase'
            elif any(term in header_lower for term in ['therapeutic', 'area', 'category', 'franchise']):
                mapping[header] = 'therapeutic_area'
            elif any(term in header_lower for term in ['mechanism', 'action', 'moa', 'mode']):
                mapping[header] = 'mechanism_of_action'
            elif any(term in header_lower for term in ['regulatory', 'designation', 'approval']):
                mapping[header] = 'regulatory_designations'
        
        return mapping
    
    def _create_pipeline_entry(self, entry_data: Dict[str, str]) -> Optional[PipelineEntry]:
        """Create a PipelineEntry from extracted data."""
        if not entry_data or not any(v for v in entry_data.values() if v and v != entry_data.get('additional_info')):
            return None
        
        # Extract phase if present in any field
        phase = None
        for key, value in entry_data.items():
            if value and isinstance(value, str):
                extracted_phase = self._extract_phase(value)
                if extracted_phase:
                    phase = extracted_phase
                    break
        
        # Handle regulatory designations
        reg_designations = []
        if 'regulatory_designations' in entry_data:
            reg_text = entry_data['regulatory_designations']
            if reg_text:
                # Split on common delimiters
                reg_designations = [d.strip() for d in re.split(r'[,;|]', reg_text) if d.strip()]
        
        return PipelineEntry(
            compound_name=entry_data.get('compound_name'),
            indication=entry_data.get('indication'),
            therapeutic_area=entry_data.get('therapeutic_area'),
            development_phase=phase or entry_data.get('development_phase'),
            mechanism_of_action=entry_data.get('mechanism_of_action'),
            status=entry_data.get('status'),
            regulatory_designations=reg_designations,
            additional_info=entry_data.get('additional_info', {})
        )
    
    def _looks_like_compound_name(self, text: str) -> bool:
        """Check if text looks like a compound name."""
        if not text or len(text) > 150:
            return False
        
        # Common patterns for compound names
        patterns = [
            r'^[A-Z]{2,}-\d+',  # e.g., LNP023, QAW039
            r'^\w+mab$',        # monoclonal antibodies
            r'^\w+ib$',         # kinase inhibitors  
            r'^\w+zumab$',      # humanized antibodies
            r'^\w+tinib$',      # tyrosine kinase inhibitors
            r'^[A-Z]+\d+',      # e.g., CTL019, CAR-T
        ]
        
        for pattern in patterns:
            if re.match(pattern, text):
                return True
        
        # Check for pharmaceutical naming conventions
        if re.match(r'^[A-Z][a-z]+[A-Z][a-z]+', text):  # CamelCase
            return True
            
        return False
    
    def _looks_like_indication(self, text: str) -> bool:
        """Check if text looks like a medical indication."""
        if not text or len(text) > 300:
            return False
        
        indication_terms = [
            'cancer', 'carcinoma', 'tumor', 'oncology', 'leukemia', 'lymphoma',
            'diabetes', 'diabetic', 'glucose', 'insulin',
            'alzheimer', 'dementia', 'neurological', 'neurology',
            'hypertension', 'cardiovascular', 'heart', 'cardiac',
            'arthritis', 'rheumatoid', 'inflammatory', 'autoimmune',
            'infection', 'bacterial', 'viral', 'antimicrobial',
            'disease', 'syndrome', 'disorder', 'condition',
            'asthma', 'copd', 'respiratory', 'pulmonary',
            'hepatitis', 'liver', 'renal', 'kidney',
            'psoriasis', 'dermatology', 'skin',
            'migraine', 'pain', 'analgesic'
        ]
        
        text_lower = text.lower()
        return any(term in text_lower for term in indication_terms)
    
    def _looks_like_phase(self, text: str) -> bool:
        """Check if text looks like a development phase."""
        if not text:
            return False
        
        phase_terms = [
            'phase', 'preclinical', 'discovery', 'registration', 
            'approved', 'launched', 'marketed', 'filing', 'submission'
        ]
        text_lower = text.lower()
        return any(term in text_lower for term in phase_terms)
    
    def _parse_list_item_text(self, text: str) -> Dict[str, str]:
        """Parse structured text from a list item."""
        entry_data = {}
        
        # Try to split on common delimiters
        parts = re.split(r'[:\-–—|]', text, maxsplit=2)
        if len(parts) >= 2:
            for i, part in enumerate(parts):
                part = self._clean_text(part)
                if not part:
                    continue
                    
                if i == 0 and self._looks_like_compound_name(part):
                    entry_data['compound_name'] = part
                elif self._looks_like_indication(part) and 'indication' not in entry_data:
                    entry_data['indication'] = part
                elif self._looks_like_phase(part) and 'development_phase' not in entry_data:
                    phase = self._extract_phase(part)
                    if phase:
                        entry_data['development_phase'] = phase
        
        # If we couldn't parse it structured, store as additional info
        if not entry_data:
            entry_data['additional_info'] = {'raw_text': text}
        
        return entry_data
    
    def _calculate_confidence(self, entries: List[PipelineEntry], pages_processed: int) -> float:
        """Calculate confidence score for extraction."""
        if not entries:
            return 0.0
        
        base_score = 0.3  # Base score for finding entries
        
        # Bonus for processing multiple pages
        page_bonus = min(0.2, pages_processed * 0.04)
        base_score += page_bonus
        
        # Bonus for having compound names
        entries_with_names = sum(1 for e in entries if e.compound_name)
        if entries_with_names > 0:
            name_ratio = entries_with_names / len(entries)
            base_score += name_ratio * 0.3
        
        # Bonus for having indications
        entries_with_indications = sum(1 for e in entries if e.indication)
        if entries_with_indications > 0:
            indication_ratio = entries_with_indications / len(entries)
            base_score += indication_ratio * 0.2
        
        # Bonus for having phases
        entries_with_phases = sum(1 for e in entries if e.development_phase)
        if entries_with_phases > 0:
            phase_ratio = entries_with_phases / len(entries)
            base_score += phase_ratio * 0.1
        
        return min(1.0, base_score)


class AdaptiveExtractor:
    """Adaptive extractor that uses multiple strategies and company-specific extractors."""
    
    def __init__(self):
        """Initialize the adaptive extractor."""
        self.extractors = {
            "Merck": MerckExtractor(),
            "Novo Nordisk": NovoNordiskExtractor(),
            "Novartis": NovartisExtractor(),
        }
        self.logger = logging.getLogger(__name__)
    
    def extract(self, company: str, html_content: str) -> ExtractionResult:
        """Extract pipeline data using adaptive strategies.
        
        Args:
            company: Company name
            html_content: Raw HTML content
            
        Returns:
            ExtractionResult with extracted data
        """
        if company in self.extractors:
            return self.extractors[company].extract(html_content)
        else:
            # Fall back to generic extraction
            return self._generic_extract(company, html_content)
    
    def _generic_extract(self, company: str, html_content: str) -> ExtractionResult:
        """Generic extraction for unknown companies."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Generic extraction strategies
            entries = []
            
            # Look for any tables that might contain pipeline data
            tables = soup.find_all('table')
            for table in tables:
                # Basic table extraction
                rows = table.find_all('tr')
                for row in rows[1:]:  # Skip header
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        entry = PipelineEntry(
                            compound_name=self._clean_text(cells[0].get_text()) if cells else None,
                            indication=self._clean_text(cells[1].get_text()) if len(cells) > 1 else None,
                            additional_info={"raw_data": [self._clean_text(cell.get_text()) for cell in cells]}
                        )
                        entries.append(entry)
            
            return ExtractionResult(
                entries=entries,
                extraction_method="generic_adaptive",
                confidence_score=0.3 if entries else 0.0,
                metadata={"company": company, "total_entries": len(entries)}
            )
            
        except Exception as e:
            self.logger.error(f"Error in generic extraction for {company}: {e}")
            return ExtractionResult(
                entries=[],
                extraction_method="generic_adaptive",
                confidence_score=0.0,
                errors=[str(e)]
            )
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content."""
        if not text:
            return ""
        return re.sub(r'\s+', ' ', text.strip())