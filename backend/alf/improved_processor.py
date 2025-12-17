"""
Regulatory Data Cleaning Pipeline - Improved Version
=====================================================

Addresses the quality issues identified in the previous implementation:
- Chunks averaging 146 words (target: 400-800 words)
- 55% of chunks ending mid-list (target: 0%)
- Missing parent-child relationships (target: 100% linked)

Built following the AI Data Readiness Playbook methodology.
"""

import re
import json
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Tuple
from pathlib import Path
from enum import Enum
from datetime import datetime


# =============================================================================
# CONFIGURATION
# =============================================================================

class ChunkConfig:
    """Chunking parameters aligned with Playbook benchmarks."""
    MIN_CHUNK_WORDS = 400      # Minimum target
    MAX_CHUNK_WORDS = 800      # Maximum target
    OVERLAP_WORDS = 50         # Context preservation
    ABSOLUTE_MIN_WORDS = 150   # Below this, merge with parent/sibling
    ABSOLUTE_MAX_WORDS = 1200  # Above this, must split (but smartly)


class QualityThresholds:
    """Production readiness thresholds from Playbook Phase 7."""
    MIN_HIT_RATE = 0.85
    MAX_HALLUCINATION_RATE = 0.05
    MIN_CITATION_ACCURACY = 0.95
    TARGET_CHUNK_SIZE_COMPLIANCE = 0.90  # 90% of chunks in 400-800 range


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class DocumentType(Enum):
    """Supported regulatory document formats."""
    IDAPA = "idapa"
    IDAHO_CODE = "idaho_code"
    FDA_FOOD_CODE = "food_code"
    ADA_GUIDELINES = "ada_guidelines"
    REFERENCE_LINKS = "reference_links"
    UNKNOWN = "unknown"


@dataclass
class Section:
    """Represents a parsed section with hierarchy information."""
    section_number: str
    title: str
    content: str
    level: int  # Hierarchy depth (1 = top, 2 = subsection, etc.)
    parent_section: Optional[str] = None
    children: List[str] = field(default_factory=list)
    source_file: str = ""
    page_number: Optional[int] = None
    effective_date: Optional[str] = None

    @property
    def word_count(self) -> int:
        return len(self.content.split())

    @property
    def full_citation(self) -> str:
        return f"{self.source_file} § {self.section_number}"


@dataclass
class Chunk:
    """A semantically complete chunk ready for embedding."""
    chunk_id: str
    content: str

    # Hierarchy & traceability
    section_number: str
    section_title: str
    parent_chunk_id: Optional[str]
    child_chunk_ids: List[str]
    position_in_section: int  # "3 of 7"
    total_in_section: int

    # Metadata for filtering
    source_document: str
    jurisdiction: str
    document_type: str
    effective_date: Optional[str]
    category: str
    topic_tags: List[str]
    facility_types: List[str]

    # Quality tracking
    word_count: int
    has_complete_lists: bool  # False if any list was split
    semantic_boundary: str  # "section_end", "paragraph_end", "sentence_end"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class QualityReport:
    """Quality metrics for a processing run."""
    total_chunks: int
    chunks_in_target_range: int  # 400-800 words
    chunks_below_minimum: int    # < 150 words
    chunks_above_maximum: int    # > 1200 words
    chunks_with_split_lists: int
    chunks_with_parent_links: int
    orphaned_chunks: int

    @property
    def size_compliance_rate(self) -> float:
        return self.chunks_in_target_range / self.total_chunks if self.total_chunks > 0 else 0

    @property
    def list_integrity_rate(self) -> float:
        return 1 - (self.chunks_with_split_lists / self.total_chunks) if self.total_chunks > 0 else 0

    @property
    def hierarchy_coverage_rate(self) -> float:
        return self.chunks_with_parent_links / self.total_chunks if self.total_chunks > 0 else 0

    def passes_production_threshold(self) -> Tuple[bool, List[str]]:
        """Check against Playbook Phase 7 thresholds."""
        issues = []

        if self.size_compliance_rate < QualityThresholds.TARGET_CHUNK_SIZE_COMPLIANCE:
            issues.append(f"Chunk size compliance: {self.size_compliance_rate:.1%} (target: 90%)")

        if self.list_integrity_rate < 1.0:
            issues.append(f"List integrity: {self.list_integrity_rate:.1%} (target: 100%)")

        if self.hierarchy_coverage_rate < 1.0:
            issues.append(f"Hierarchy coverage: {self.hierarchy_coverage_rate:.1%} (target: 100%)")

        if self.orphaned_chunks > 0:
            issues.append(f"Orphaned chunks: {self.orphaned_chunks} (target: 0)")

        return len(issues) == 0, issues


# =============================================================================
# PHASE 1: PARSING & EXTRACTION
# =============================================================================

class DocumentParser:
    """
    Parse regulatory documents while preserving structure.

    Key improvements over previous version:
    - Detects full hierarchy (sections, subsections, paragraphs)
    - Preserves list structure for semantic integrity
    - Tracks parent-child relationships during parsing
    """

    # Document type detection patterns
    TYPE_PATTERNS = {
        DocumentType.IDAPA: [
            r'IDAPA\s+\d+',
            r'^\d{3}\.\s+[A-Z][A-Z\s\-,&()]+\.',
        ],
        DocumentType.IDAHO_CODE: [
            r'^\d{2}-\d{4}\.',
            r'TITLE\s+\d+',
        ],
        DocumentType.FDA_FOOD_CODE: [
            r'^\d-\d{3}\.\d{2}',
            r'Food Code',
        ],
        DocumentType.ADA_GUIDELINES: [
            r'^\d\.\d+\.\d+',
            r'ADA.*Guidelines',
        ],
    }

    # Section header patterns by document type
    SECTION_PATTERNS = {
        DocumentType.IDAPA: {
            'level_1': r'^(\d{3})\.\s+([A-Z][A-Z\s\-,&()]+)\.',  # 100. LICENSING.
            'level_2': r'^(\d{2})\.\s+([A-Z][A-Za-z\s\-,&()]+)',  # 01. General Requirements
            'level_3': r'^([a-z])\.\s+',  # a. Specific item
        },
        DocumentType.IDAHO_CODE: {
            'level_1': r'^(\d{2}-\d{4})\.\s+([A-Z][A-Z\s\-,&()]+)',  # 39-3301. DEFINITIONS
        },
        DocumentType.FDA_FOOD_CODE: {
            'level_1': r'^(\d-\d{3}\.\d{2})\s+([A-Z][A-Za-z\s\-,]+)',  # 3-201.11 Temperature
        },
        DocumentType.ADA_GUIDELINES: {
            'level_1': r'^(\d\.\d+)\s+([A-Z][A-Za-z\s]+)',  # 4.1 Application
            'level_2': r'^(\d\.\d+\.\d+)\s+([A-Za-z\s]+)',  # 4.1.1 Buildings
        },
    }

    # List detection patterns (critical for semantic integrity)
    LIST_PATTERNS = [
        r'^\s*\([a-z]\)',      # (a) (b) (c)
        r'^\s*\(\d+\)',        # (1) (2) (3)
        r'^\s*[a-z]\.\s',      # a. b. c.
        r'^\s*\d+\.\s',        # 1. 2. 3.
        r'^\s*[ivx]+\.\s',     # i. ii. iii.
        r'^\s*•\s',            # bullet points
        r'^\s*-\s',            # dashes
    ]

    def __init__(self):
        self.list_pattern = re.compile('|'.join(self.LIST_PATTERNS), re.MULTILINE)

    def detect_document_type(self, content: str, filename: str) -> DocumentType:
        """Identify document format from content and filename."""
        filename_lower = filename.lower()

        # Check filename hints first
        if 'idapa' in filename_lower:
            return DocumentType.IDAPA
        if 'title' in filename_lower and any(c.isdigit() for c in filename):
            return DocumentType.IDAHO_CODE
        if 'food' in filename_lower and 'code' in filename_lower:
            return DocumentType.FDA_FOOD_CODE
        if 'ada' in filename_lower:
            return DocumentType.ADA_GUIDELINES
        if filename_lower.endswith('.json'):
            return DocumentType.REFERENCE_LINKS

        # Check content patterns
        for doc_type, patterns in self.TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, content, re.MULTILINE):
                    return doc_type

        return DocumentType.UNKNOWN

    def parse_document(self, content: str, filename: str) -> List[Section]:
        """
        Parse document into hierarchical sections.

        Returns sections with parent-child relationships established.
        """
        doc_type = self.detect_document_type(content, filename)

        if doc_type == DocumentType.REFERENCE_LINKS:
            return self._parse_reference_links(content, filename)

        patterns = self.SECTION_PATTERNS.get(doc_type, self.SECTION_PATTERNS[DocumentType.IDAPA])

        sections = []
        current_parents = {}  # Track parent at each level

        # Split content into lines for processing
        lines = content.split('\n')
        current_section = None
        current_content = []

        for line in lines:
            # Check for section headers at each level
            new_section = None
            level = 0

            for level_name, pattern in patterns.items():
                match = re.match(pattern, line.strip())
                if match:
                    level = int(level_name.split('_')[1])
                    section_num = match.group(1)
                    title = match.group(2) if len(match.groups()) > 1 else ""

                    new_section = Section(
                        section_number=section_num,
                        title=title.strip(),
                        content="",
                        level=level,
                        source_file=filename,
                    )
                    break

            if new_section:
                # Save previous section
                if current_section:
                    current_section.content = '\n'.join(current_content).strip()
                    if current_section.content and len(current_section.content) > 100:
                        sections.append(current_section)

                # Set parent relationship
                if level > 1 and level - 1 in current_parents:
                    new_section.parent_section = current_parents[level - 1].section_number
                    current_parents[level - 1].children.append(new_section.section_number)

                # Update parent tracking
                current_parents[level] = new_section
                # Clear deeper levels
                for l in list(current_parents.keys()):
                    if l > level:
                        del current_parents[l]

                current_section = new_section
                current_content = [line]
            elif current_section:
                current_content.append(line)

        # Don't forget the last section
        if current_section:
            current_section.content = '\n'.join(current_content).strip()
            if current_section.content and len(current_section.content) > 100:
                sections.append(current_section)

        return sections

    def _parse_reference_links(self, content: str, filename: str) -> List[Section]:
        """Parse JSON reference document."""
        try:
            data = json.loads(content)
            sections = []
            for i, item in enumerate(data):
                sections.append(Section(
                    section_number=f"REF-{i+1:03d}",
                    title=item.get('title', 'Reference'),
                    content=json.dumps(item, indent=2),
                    level=1,
                    source_file=filename,
                ))
            return sections
        except json.JSONDecodeError:
            return []


# =============================================================================
# PHASE 2: CLEANING & NORMALIZATION
# =============================================================================

class ContentCleaner:
    """
    Clean and normalize content while preserving semantic structure.

    Follows Playbook Phase 2 requirements:
    - Remove headers/footers/page numbers (100% target)
    - Normalize dates to YYYY-MM-DD (100% target)
    - Normalize citations to standard format (100% target)
    """

    # Patterns for removal
    NOISE_PATTERNS = [
        r'Page\s+\d+\s+of\s+\d+',
        r'^\s*\d+\s*$',  # Standalone page numbers
        r'CONFIDENTIAL',
        r'---+',
        r'___+',
        r'\[Table of Contents\]',
        r'RESERVED\.',
    ]

    # Date normalization patterns (callable patterns handled separately)
    DATE_PATTERNS = [
        (r'\((\d{1,2})-(\d{1,2})-(\d{2})\)', lambda m: f'[eff. 20{m.group(3)}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}]'),  # (3-15-22) -> [eff. 2022-03-15]
        (r'(\d{1,2})/(\d{1,2})/(\d{4})', lambda m: f'{m.group(3)}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}'),  # 3/15/2024 -> 2024-03-15
    ]

    # Month name pattern (handled with method)
    MONTH_DATE_PATTERN = r'(\w+)\s+(\d{1,2}),?\s+(\d{4})'  # January 15, 2024

    # Citation normalization
    CITATION_PATTERNS = [
        (r'§\s*(\d+)', r'§ \1'),  # Normalize section symbol spacing
        (r'42\s+CFR\s+§?\s*(\d+)', r'42 CFR § \1'),  # Federal citations
        (r'IDAPA\s+(\d+)\.(\d+)\.(\d+)', r'IDAPA \1.\2.\3'),  # Idaho admin code
    ]

    # Normalization dictionary (from Playbook Phase 2)
    NORMALIZATION_DICT = {
        # Agencies
        'Centers for Medicare & Medicaid Services': 'CMS',
        'Idaho Department of Health and Welfare': 'IDHW',
        'Idaho Department of Health & Welfare': 'IDHW',

        # Facility types
        'Skilled Nursing Facility': 'SNF',
        'skilled nursing facility': 'SNF',
        'nursing home': 'SNF',
        'Assisted Living Facility': 'ALF',
        'assisted living facility': 'ALF',
        'Residential Care Facility': 'RCF',

        # States
        'State of Idaho': 'Idaho',
        'ID': 'Idaho',
    }

    def __init__(self):
        self.noise_pattern = re.compile('|'.join(self.NOISE_PATTERNS), re.IGNORECASE)

    def clean(self, content: str) -> str:
        """Apply all cleaning transformations."""
        content = self._remove_noise(content)
        content = self._normalize_dates(content)
        content = self._normalize_citations(content)
        content = self._apply_normalization_dict(content)
        content = self._format_lists(content)
        content = self._clean_whitespace(content)
        return content

    def _remove_noise(self, content: str) -> str:
        """Remove headers, footers, page numbers."""
        lines = content.split('\n')
        cleaned_lines = []

        for line in lines:
            if not self.noise_pattern.search(line):
                cleaned_lines.append(line)

        return '\n'.join(cleaned_lines)

    def _normalize_dates(self, content: str) -> str:
        """Convert all dates to YYYY-MM-DD format."""
        # Handle standard patterns (may be callable)
        for pattern, replacement in self.DATE_PATTERNS:
            content = re.sub(pattern, replacement, content)

        # Handle month name dates separately
        content = re.sub(self.MONTH_DATE_PATTERN, self._month_to_date, content)

        return content

    def _month_to_date(self, match) -> str:
        """Convert month name dates to ISO format."""
        months = {
            'january': '01', 'february': '02', 'march': '03', 'april': '04',
            'may': '05', 'june': '06', 'july': '07', 'august': '08',
            'september': '09', 'october': '10', 'november': '11', 'december': '12'
        }
        month = months.get(match.group(1).lower(), '01')
        day = match.group(2).zfill(2)
        year = match.group(3)
        return f'{year}-{month}-{day}'

    def _normalize_citations(self, content: str) -> str:
        """Standardize citation formats."""
        for pattern, replacement in self.CITATION_PATTERNS:
            content = re.sub(pattern, replacement, content)
        return content

    def _apply_normalization_dict(self, content: str) -> str:
        """Apply terminology normalization."""
        for original, normalized in self.NORMALIZATION_DICT.items():
            content = content.replace(original, normalized)
        return content

    def _format_lists(self, content: str) -> str:
        """Improve list formatting for readability."""
        # Add line breaks before list items for cleaner structure
        list_markers = [
            (r'([.;:])\s*([a-z])\.\s+', r'\1\n\n\2. '),  # a. b. c.
            (r'([.;:])\s*\(([a-z])\)\s+', r'\1\n\n(\2) '),  # (a) (b) (c)
            (r'([.;:])\s*(\d+)\.\s+', r'\1\n\n\2. '),  # 1. 2. 3.
        ]
        for pattern, replacement in list_markers:
            content = re.sub(pattern, replacement, content)
        return content

    def _clean_whitespace(self, content: str) -> str:
        """Remove excessive whitespace while preserving structure."""
        # Collapse multiple blank lines to max 2
        content = re.sub(r'\n{4,}', '\n\n\n', content)
        # Remove trailing whitespace from lines
        content = '\n'.join(line.rstrip() for line in content.split('\n'))
        return content.strip()


# =============================================================================
# PHASE 3: SEMANTIC CHUNKING
# =============================================================================

class SemanticChunker:
    """
    Split content into semantically complete chunks.

    Key improvements over previous version:
    - NEVER splits mid-list (0% split lists target)
    - Maintains parent-child relationships
    - Targets 400-800 word chunks
    - Uses intelligent sentence boundaries
    """

    def __init__(self, config: ChunkConfig = None):
        self.config = config or ChunkConfig()
        self.list_pattern = re.compile(
            r'^\s*(?:\([a-z]\)|\(\d+\)|[a-z]\.|[ivx]+\.|•|-)\s',
            re.MULTILINE
        )

    def chunk_section(self, section: Section) -> List[Chunk]:
        """
        Convert a section into one or more semantically complete chunks.

        Strategy:
        1. If section fits in target range (400-800 words), keep as single chunk
        2. If section is too large, find semantic boundaries (paragraph ends, list ends)
        3. Never split a list - keep entire list together
        4. Use overlap for context preservation when splitting
        """
        word_count = section.word_count

        # Case 1: Section fits in target range - keep as single chunk
        if self.config.MIN_CHUNK_WORDS <= word_count <= self.config.MAX_CHUNK_WORDS:
            return [self._create_chunk(section, section.content, 1, 1)]

        # Case 2: Section is too small - flag for merging (handled at higher level)
        if word_count < self.config.ABSOLUTE_MIN_WORDS:
            # Still create chunk, but mark it for potential merging
            return [self._create_chunk(section, section.content, 1, 1)]

        # Case 3: Section is too large - split at semantic boundaries
        return self._split_large_section(section)

    def _split_large_section(self, section: Section) -> List[Chunk]:
        """Split oversized section at semantic boundaries, preserving lists."""
        content = section.content

        # Identify all lists in the content (these must stay together)
        list_blocks = self._identify_list_blocks(content)

        # Split content into semantic units (paragraphs, list blocks)
        units = self._split_into_units(content, list_blocks)

        # Combine units into chunks that meet size requirements
        chunks = []
        current_content = []
        current_word_count = 0

        for unit in units:
            unit_words = len(unit.split())

            # If adding this unit would exceed max, finalize current chunk
            if current_word_count + unit_words > self.config.ABSOLUTE_MAX_WORDS and current_content:
                chunk_text = '\n\n'.join(current_content)
                chunks.append(chunk_text)

                # Start new chunk with overlap
                overlap_text = self._get_overlap_text(current_content)
                current_content = [overlap_text, unit] if overlap_text else [unit]
                current_word_count = len(' '.join(current_content).split())
            else:
                current_content.append(unit)
                current_word_count += unit_words

        # Don't forget the last chunk
        if current_content:
            chunk_text = '\n\n'.join(current_content)
            chunks.append(chunk_text)

        # Convert to Chunk objects
        total_chunks = len(chunks)
        return [
            self._create_chunk(section, chunk_content, i + 1, total_chunks)
            for i, chunk_content in enumerate(chunks)
        ]

    def _identify_list_blocks(self, content: str) -> List[Tuple[int, int]]:
        """Find start and end positions of list blocks."""
        lines = content.split('\n')
        list_blocks = []
        in_list = False
        list_start = 0

        for i, line in enumerate(lines):
            is_list_item = bool(self.list_pattern.match(line))

            if is_list_item and not in_list:
                # Starting a new list
                in_list = True
                list_start = i
            elif not is_list_item and in_list:
                # Ending a list (non-empty line that's not a list item)
                if line.strip():  # Don't end on blank lines within list
                    list_blocks.append((list_start, i))
                    in_list = False

        # Handle list at end of content
        if in_list:
            list_blocks.append((list_start, len(lines)))

        return list_blocks

    def _split_into_units(self, content: str, list_blocks: List[Tuple[int, int]]) -> List[str]:
        """Split content into atomic semantic units (paragraphs and complete lists)."""
        lines = content.split('\n')
        units = []
        current_unit = []

        # Convert list_blocks to line indices for easy lookup
        list_lines = set()
        for start, end in list_blocks:
            for i in range(start, end):
                list_lines.add(i)

        for i, line in enumerate(lines):
            if i in list_lines:
                # Line is part of a list - accumulate
                current_unit.append(line)
            elif not line.strip():
                # Blank line - potential paragraph break
                if current_unit:
                    units.append('\n'.join(current_unit))
                    current_unit = []
            else:
                # Regular paragraph line
                current_unit.append(line)

        # Don't forget last unit
        if current_unit:
            units.append('\n'.join(current_unit))

        return [u for u in units if u.strip()]

    def _get_overlap_text(self, chunks: List[str]) -> str:
        """Get overlap text from end of previous chunk for context."""
        if not chunks:
            return ""

        last_chunk = chunks[-1]
        words = last_chunk.split()

        if len(words) <= self.config.OVERLAP_WORDS:
            return last_chunk

        # Find sentence boundary near overlap target
        overlap_text = ' '.join(words[-self.config.OVERLAP_WORDS:])

        # Try to start at sentence boundary
        sentences = re.split(r'(?<=[.!?])\s+', last_chunk)
        if len(sentences) > 1:
            return sentences[-1]

        return overlap_text

    def _create_chunk(self, section: Section, content: str, position: int, total: int) -> Chunk:
        """Create a properly structured Chunk object."""
        word_count = len(content.split())
        has_complete_lists = not self._has_incomplete_list(content)

        # Determine semantic boundary type
        if content.rstrip().endswith('.'):
            boundary = "sentence_end"
        elif position == total:
            boundary = "section_end"
        else:
            boundary = "paragraph_end"

        return Chunk(
            chunk_id=self._generate_chunk_id(section, position),
            content=content,
            section_number=section.section_number,
            section_title=section.title,
            parent_chunk_id=section.parent_section,
            child_chunk_ids=section.children,
            position_in_section=position,
            total_in_section=total,
            source_document=section.source_file,
            jurisdiction="Idaho",  # Default, can be overridden by tagger
            document_type="regulation",  # Default
            effective_date=section.effective_date,
            category=self._infer_category(section.section_number, content),
            topic_tags=self._extract_topics(content),
            facility_types=self._extract_facility_types(content),
            word_count=word_count,
            has_complete_lists=has_complete_lists,
            semantic_boundary=boundary,
        )

    def _generate_chunk_id(self, section: Section, position: int) -> str:
        """Generate stable, traceable chunk ID."""
        base = f"{section.source_file}_{section.section_number}_{position}"
        hash_suffix = hashlib.md5(base.encode()).hexdigest()[:8]
        return f"CHK_{section.section_number}_{position}_{hash_suffix}"

    def _has_incomplete_list(self, content: str) -> bool:
        """Check if content ends mid-list."""
        lines = content.strip().split('\n')
        if not lines:
            return False

        # Get the last non-empty line
        last_line = None
        for line in reversed(lines):
            if line.strip():
                last_line = line.strip()
                break

        if not last_line:
            return False

        # Check if last line is a list item
        if not self.list_pattern.match(last_line):
            return False  # Not a list item, so not an incomplete list

        # List item is complete if it ends with proper punctuation
        # Also consider effective date notations as valid endings
        valid_endings = (
            '.', ';', ':', '!', '?',
            ')',  # For things like "(7-1-24)"
            ']',  # For things like "[eff. 2024-01-01]"
        )

        # Check if line ends with valid punctuation
        if last_line.rstrip().endswith(valid_endings):
            return False  # List is complete

        # Check for effective date pattern at the end
        if re.search(r'\(\d{1,2}-\d{1,2}-\d{2,4}\)\s*$', last_line):
            return False  # Ends with effective date
        if re.search(r'\[eff\.[^\]]+\]\s*$', last_line):
            return False  # Ends with formatted effective date

        return True  # List appears incomplete

    def _infer_category(self, section_number: str, content: str) -> str:
        """Infer category from section number and content."""
        # IDAPA section number ranges
        try:
            num = int(re.search(r'(\d+)', section_number).group(1))

            if 100 <= num < 150:
                return "licensing"
            elif 200 <= num < 250:
                return "administration"
            elif 300 <= num < 400:
                return "physical_plant"
            elif 400 <= num < 500:
                return "staffing"
            elif 500 <= num < 600:
                return "resident_care"
            elif 600 <= num < 700:
                return "medications"
            elif 700 <= num < 800:
                return "food_service"
            elif 800 <= num < 900:
                return "records"
        except (AttributeError, ValueError):
            pass

        # Keyword-based fallback
        content_lower = content.lower()
        if any(w in content_lower for w in ['staff', 'employee', 'personnel', 'nurse']):
            return "staffing"
        if any(w in content_lower for w in ['medication', 'drug', 'pharmacy']):
            return "medications"
        if any(w in content_lower for w in ['resident', 'care', 'assessment']):
            return "resident_care"

        return "general"

    def _extract_topics(self, content: str) -> List[str]:
        """Extract topic tags from content."""
        topics = []
        content_lower = content.lower()

        topic_keywords = {
            'staffing': ['staff', 'employee', 'personnel', 'nurse', 'administrator'],
            'medications': ['medication', 'drug', 'pharmacy', 'prescription'],
            'safety': ['fire', 'emergency', 'safety', 'evacuation'],
            'nutrition': ['food', 'meal', 'diet', 'nutrition'],
            'rights': ['rights', 'dignity', 'privacy', 'abuse'],
            'documentation': ['record', 'document', 'report', 'log'],
            'infection_control': ['infection', 'sanitation', 'hygiene'],
            'physical_plant': ['building', 'room', 'square feet', 'bathroom'],
        }

        for topic, keywords in topic_keywords.items():
            if any(kw in content_lower for kw in keywords):
                topics.append(topic)

        return topics if topics else ['general']

    def _extract_facility_types(self, content: str) -> List[str]:
        """Extract applicable facility types from content."""
        facilities = []
        content_lower = content.lower()

        if any(w in content_lower for w in ['assisted living', 'alf', 'residential care']):
            facilities.append('ALF')
        if any(w in content_lower for w in ['skilled nursing', 'snf', 'nursing facility']):
            facilities.append('SNF')
        if any(w in content_lower for w in ['memory care', 'dementia']):
            facilities.append('Memory Care')

        return facilities if facilities else ['All']


# =============================================================================
# PHASE 4: METADATA ENRICHMENT
# =============================================================================

class MetadataTagger:
    """
    Enrich chunks with metadata for filtering and retrieval.

    Follows Playbook Phase 4 requirements:
    - Jurisdiction accuracy >95%
    - Topic tag coverage 100%
    - Citation extraction >90%
    """

    # Citation patterns
    CITATION_PATTERNS = {
        'federal': r'42\s+CFR\s+§?\s*(\d+\.?\d*)',
        'idapa': r'IDAPA\s+(\d+\.\d+\.\d+)',
        'idaho_code': r'(?:Idaho Code|I\.C\.)\s+§?\s*(\d+-\d+)',
        'ada': r'ADA\s+(?:§|Section)?\s*(\d+\.\d+)',
    }

    # Jurisdiction indicators
    JURISDICTION_INDICATORS = {
        'Idaho': ['Idaho', 'IDAPA', 'I.C.', 'IDHW'],
        'Federal': ['CMS', 'Medicare', 'Medicaid', '42 CFR', 'FDA'],
        'ADA': ['ADA', 'Americans with Disabilities'],
    }

    def enrich_chunk(self, chunk: Chunk) -> Chunk:
        """Add comprehensive metadata to chunk."""
        content = chunk.content

        # Extract citations
        citations = self._extract_citations(content)
        if citations:
            # Add to chunk (would need to extend Chunk dataclass)
            pass

        # Refine jurisdiction
        chunk.jurisdiction = self._determine_jurisdiction(content, chunk.source_document)

        # Extract effective date if present
        effective_date = self._extract_effective_date(content)
        if effective_date:
            chunk.effective_date = effective_date

        return chunk

    def _extract_citations(self, content: str) -> List[Dict[str, str]]:
        """Extract all citations from content."""
        citations = []

        for citation_type, pattern in self.CITATION_PATTERNS.items():
            matches = re.findall(pattern, content)
            for match in matches:
                citations.append({
                    'type': citation_type,
                    'reference': match,
                })

        return citations

    def _determine_jurisdiction(self, content: str, source_file: str) -> str:
        """Determine applicable jurisdiction."""
        # Check source file first
        source_lower = source_file.lower()
        if 'idapa' in source_lower or 'idaho' in source_lower:
            return 'Idaho'
        if 'ada' in source_lower:
            return 'Federal-ADA'
        if 'food code' in source_lower:
            return 'Federal-FDA'

        # Check content for indicators
        for jurisdiction, indicators in self.JURISDICTION_INDICATORS.items():
            if any(ind in content for ind in indicators):
                return jurisdiction

        return 'Unknown'

    def _extract_effective_date(self, content: str) -> Optional[str]:
        """Extract effective date from content."""
        patterns = [
            r'\[eff\.\s*(\d{4}-\d{2}-\d{2})\]',
            r'effective\s+(\d{4}-\d{2}-\d{2})',
            r'effective\s+(\w+\s+\d{1,2},?\s+\d{4})',
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1)

        return None


# =============================================================================
# QUALITY VALIDATION
# =============================================================================

class QualityValidator:
    """
    Validate processing output against Playbook benchmarks.

    Phase 7 Production Readiness Thresholds:
    - Hit Rate: >85%
    - Hallucination: <5%
    - Chunk size compliance: >90% in 400-800 word range
    """

    def __init__(self, config: ChunkConfig = None):
        self.config = config or ChunkConfig()

    def validate_chunks(self, chunks: List[Chunk]) -> QualityReport:
        """Generate quality report for chunk collection."""
        total = len(chunks)

        in_range = sum(
            1 for c in chunks
            if self.config.MIN_CHUNK_WORDS <= c.word_count <= self.config.MAX_CHUNK_WORDS
        )

        below_min = sum(1 for c in chunks if c.word_count < self.config.ABSOLUTE_MIN_WORDS)
        above_max = sum(1 for c in chunks if c.word_count > self.config.ABSOLUTE_MAX_WORDS)

        split_lists = sum(1 for c in chunks if not c.has_complete_lists)

        with_parents = sum(1 for c in chunks if c.parent_chunk_id is not None)
        orphaned = sum(
            1 for c in chunks
            if c.parent_chunk_id is None and c.position_in_section == 1
        )

        return QualityReport(
            total_chunks=total,
            chunks_in_target_range=in_range,
            chunks_below_minimum=below_min,
            chunks_above_maximum=above_max,
            chunks_with_split_lists=split_lists,
            chunks_with_parent_links=with_parents,
            orphaned_chunks=orphaned,
        )

    def detailed_analysis(self, chunks: List[Chunk]) -> Dict:
        """Generate detailed quality analysis."""
        word_counts = [c.word_count for c in chunks]

        return {
            'total_chunks': len(chunks),
            'word_count_stats': {
                'min': min(word_counts) if word_counts else 0,
                'max': max(word_counts) if word_counts else 0,
                'mean': sum(word_counts) / len(word_counts) if word_counts else 0,
                'median': sorted(word_counts)[len(word_counts)//2] if word_counts else 0,
            },
            'size_distribution': {
                'under_150': sum(1 for wc in word_counts if wc < 150),
                '150_400': sum(1 for wc in word_counts if 150 <= wc < 400),
                '400_800': sum(1 for wc in word_counts if 400 <= wc <= 800),
                '800_1200': sum(1 for wc in word_counts if 800 < wc <= 1200),
                'over_1200': sum(1 for wc in word_counts if wc > 1200),
            },
            'semantic_boundaries': {
                'section_end': sum(1 for c in chunks if c.semantic_boundary == 'section_end'),
                'paragraph_end': sum(1 for c in chunks if c.semantic_boundary == 'paragraph_end'),
                'sentence_end': sum(1 for c in chunks if c.semantic_boundary == 'sentence_end'),
            },
            'list_integrity': {
                'complete': sum(1 for c in chunks if c.has_complete_lists),
                'split': sum(1 for c in chunks if not c.has_complete_lists),
            },
            'categories': {
                cat: sum(1 for c in chunks if c.category == cat)
                for cat in set(c.category for c in chunks)
            },
        }


# =============================================================================
# MAIN PIPELINE
# =============================================================================

class RegulatoryDataPipeline:
    """
    Complete data cleaning pipeline following AI Data Readiness Playbook.

    Phases covered:
    - Phase 1: Parsing & Extraction
    - Phase 2: Cleaning & Normalization
    - Phase 3: Chunking
    - Phase 4: Metadata & Tagging
    - Phase 7: Quality Validation (subset)
    """

    def __init__(self, config: ChunkConfig = None):
        self.config = config or ChunkConfig()
        self.parser = DocumentParser()
        self.cleaner = ContentCleaner()
        self.chunker = SemanticChunker(self.config)
        self.tagger = MetadataTagger()
        self.validator = QualityValidator(self.config)

    def process_document(self, content: str, filename: str) -> List[Chunk]:
        """Process a single document through the full pipeline."""
        # Phase 1: Parse into sections
        sections = self.parser.parse_document(content, filename)

        # Phase 2: Clean each section
        for section in sections:
            section.content = self.cleaner.clean(section.content)

        # Phase 2.5: Merge small sections to meet size targets
        sections = self._merge_small_sections(sections)

        # Phase 3: Chunk sections
        all_chunks = []
        for section in sections:
            chunks = self.chunker.chunk_section(section)
            all_chunks.extend(chunks)

        # Phase 4: Enrich with metadata
        for chunk in all_chunks:
            self.tagger.enrich_chunk(chunk)

        return all_chunks

    def _merge_small_sections(self, sections: List[Section]) -> List[Section]:
        """
        Merge small sections with their parents or siblings to meet size targets.

        Strategy:
        - If a section is below MIN_CHUNK_WORDS and has a parent, merge into parent
        - If no parent, merge with previous sibling
        - Preserve hierarchy metadata even when merging content
        """
        if not sections:
            return sections

        min_words = self.config.MIN_CHUNK_WORDS
        merged_sections = []
        pending_content = []
        pending_metadata = []

        for i, section in enumerate(sections):
            word_count = section.word_count

            # If section is large enough, finalize any pending content first
            if word_count >= min_words:
                if pending_content:
                    # Create merged section from pending
                    merged = self._create_merged_section(pending_content, pending_metadata)
                    if merged:
                        merged_sections.append(merged)
                    pending_content = []
                    pending_metadata = []

                merged_sections.append(section)
            else:
                # Section is too small - accumulate for merging
                pending_content.append(section.content)
                pending_metadata.append(section)

                # Check if accumulated content is now large enough
                total_words = sum(len(c.split()) for c in pending_content)
                if total_words >= min_words:
                    merged = self._create_merged_section(pending_content, pending_metadata)
                    if merged:
                        merged_sections.append(merged)
                    pending_content = []
                    pending_metadata = []

        # Handle any remaining pending content
        if pending_content:
            merged = self._create_merged_section(pending_content, pending_metadata)
            if merged:
                merged_sections.append(merged)

        return merged_sections

    def _create_merged_section(self, contents: List[str], sections: List[Section]) -> Optional[Section]:
        """Create a merged section from multiple small sections."""
        if not sections:
            return None

        # Use first section as base, combine content from all
        base = sections[0]

        # Build combined title showing section range
        if len(sections) > 1:
            section_numbers = [s.section_number for s in sections]
            title = f"{sections[0].title} through {sections[-1].title}"
        else:
            title = base.title

        # Combine content with clear section markers
        combined_content = []
        for section in sections:
            if section.title:
                combined_content.append(f"\n{section.section_number}. {section.title}\n")
            combined_content.append(section.content)

        return Section(
            section_number=base.section_number,
            title=title,
            content='\n\n'.join(combined_content),
            level=base.level,
            parent_section=base.parent_section,
            children=[c for s in sections for c in s.children],
            source_file=base.source_file,
            page_number=base.page_number,
            effective_date=base.effective_date,
        )

    def process_directory(self, input_dir: str, output_file: str) -> Tuple[List[Chunk], QualityReport]:
        """Process all documents in a directory."""
        input_path = Path(input_dir)
        all_chunks = []

        # Process each file
        for file_path in input_path.glob('*.txt'):
            print(f"Processing: {file_path.name}")

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            chunks = self.process_document(content, file_path.name)
            all_chunks.extend(chunks)
            print(f"  → Generated {len(chunks)} chunks")

        # Deduplicate
        all_chunks = self._deduplicate(all_chunks)
        print(f"\nTotal unique chunks: {len(all_chunks)}")

        # Validate quality
        report = self.validator.validate_chunks(all_chunks)

        # Save output
        output_data = [chunk.to_dict() for chunk in all_chunks]
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)

        return all_chunks, report

    def _deduplicate(self, chunks: List[Chunk]) -> List[Chunk]:
        """Remove duplicate chunks."""
        seen_content = set()
        unique_chunks = []

        for chunk in chunks:
            # Normalize content for comparison
            normalized = ' '.join(chunk.content.lower().split())

            if normalized not in seen_content:
                seen_content.add(normalized)
                unique_chunks.append(chunk)

        return unique_chunks


# =============================================================================
# CLI & REPORTING
# =============================================================================

def print_quality_report(report: QualityReport, detailed: Dict = None):
    """Print formatted quality report."""
    print("\n" + "="*60)
    print("QUALITY REPORT - AI Data Readiness Playbook Benchmarks")
    print("="*60)

    print(f"\nTotal Chunks: {report.total_chunks}")

    print(f"\n📏 CHUNK SIZE COMPLIANCE")
    print(f"   Target range (400-800 words): {report.chunks_in_target_range} "
          f"({report.size_compliance_rate:.1%})")
    print(f"   Below minimum (<150):         {report.chunks_below_minimum}")
    print(f"   Above maximum (>1200):        {report.chunks_above_maximum}")

    print(f"\n📋 LIST INTEGRITY")
    print(f"   Complete lists: {report.total_chunks - report.chunks_with_split_lists}")
    print(f"   Split lists:    {report.chunks_with_split_lists} "
          f"(integrity: {report.list_integrity_rate:.1%})")

    print(f"\n🔗 HIERARCHY COVERAGE")
    print(f"   With parent links: {report.chunks_with_parent_links}")
    print(f"   Orphaned chunks:   {report.orphaned_chunks}")

    # Check against production thresholds
    passes, issues = report.passes_production_threshold()

    print(f"\n{'✅' if passes else '❌'} PRODUCTION READINESS")
    if passes:
        print("   All benchmarks met!")
    else:
        print("   Issues to address:")
        for issue in issues:
            print(f"   • {issue}")

    if detailed:
        print(f"\n📊 DETAILED STATISTICS")
        stats = detailed['word_count_stats']
        print(f"   Word count: min={stats['min']}, max={stats['max']}, "
              f"mean={stats['mean']:.0f}, median={stats['median']}")

        print(f"\n   Size distribution:")
        dist = detailed['size_distribution']
        for range_name, count in dist.items():
            pct = count / report.total_chunks * 100
            bar = "█" * int(pct / 5)
            print(f"     {range_name:12s}: {count:4d} ({pct:5.1f}%) {bar}")


def main():
    """Example usage of the pipeline."""
    print("Regulatory Data Cleaning Pipeline")
    print("Following AI Data Readiness Playbook methodology\n")

    # Initialize pipeline
    pipeline = RegulatoryDataPipeline()

    # Example: Process a sample document
    sample_content = """
    100. LICENSING REQUIREMENTS.

    All assisted living facilities must obtain a license from the
    Department of Health and Welfare before beginning operations.

    01. Application Process. The administrator must submit:

    a. Completed application form;

    b. Floor plan of the facility showing:
       (1) Resident rooms;
       (2) Common areas;
       (3) Emergency exits;

    c. Proof of liability insurance;

    d. Background check results for all staff. (3-15-22)

    02. Renewal Requirements. Licenses must be renewed annually.
    The renewal application must be submitted at least 60 days
    before the expiration date. Failure to renew on time may
    result in penalties or license revocation.
    """

    chunks = pipeline.process_document(sample_content, "sample_idapa.txt")

    print(f"Generated {len(chunks)} chunks:\n")
    for chunk in chunks:
        print(f"ID: {chunk.chunk_id}")
        print(f"Section: {chunk.section_number} - {chunk.section_title}")
        print(f"Words: {chunk.word_count} | Boundary: {chunk.semantic_boundary}")
        print(f"Lists intact: {chunk.has_complete_lists}")
        print(f"Content preview: {chunk.content[:200]}...")
        print("-" * 40)

    # Validate
    report = pipeline.validator.validate_chunks(chunks)
    detailed = pipeline.validator.detailed_analysis(chunks)
    print_quality_report(report, detailed)


if __name__ == "__main__":
    main()
