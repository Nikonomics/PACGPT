"""
Idaho ALF Regulation Text Processor
Extracts and chunks regulatory text files by section with metadata.
Supports multiple document formats: IDAPA, Food Code, Idaho Code, ADA Guidelines.
"""

import re
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime


# Constants for chunking
MAX_CHUNK_SIZE = 1500  # Maximum characters per chunk
MIN_CHUNK_SIZE = 500   # Minimum characters per chunk (avoid tiny chunks)
OVERLAP_SIZE = 150     # Characters to overlap between chunks

# Abbreviations that should NOT trigger sentence splits
ABBREVIATIONS = {
    'Dr.', 'Mr.', 'Mrs.', 'Ms.', 'Jr.', 'Sr.', 'Prof.', 'Rev.',
    'e.g.', 'i.e.', 'etc.', 'vs.', 'viz.', 'al.',
    'No.', 'Nos.', 'Sec.', 'sec.', 'Secs.', 'Fig.', 'Figs.',
    'Vol.', 'Vols.', 'Ch.', 'Chs.', 'Art.', 'Arts.',
    'Corp.', 'Inc.', 'Ltd.', 'Co.', 'Bros.',
    'U.S.', 'U.S.A.', 'U.S.C.', 'C.F.R.', 'CFR.', 'F.R.',
    'Ave.', 'Blvd.', 'St.', 'Rd.', 'Ct.', 'Pl.',
    'Jan.', 'Feb.', 'Mar.', 'Apr.', 'Jun.', 'Jul.', 'Aug.', 'Sep.', 'Sept.', 'Oct.', 'Nov.', 'Dec.',
    'a.m.', 'p.m.', 'A.M.', 'P.M.',
    'Ph.D.', 'M.D.', 'B.A.', 'M.A.', 'B.S.', 'M.S.', 'J.D.', 'LL.B.', 'R.N.', 'L.P.N.',
    'approx.', 'dept.', 'div.', 'est.', 'govt.', 'natl.', 'intl.',
    'min.', 'max.', 'temp.', 'req.', 'spec.', 'std.',
    'para.', 'paras.', 'subpara.', 'subparas.',
}


class RegulationChunk:
    """Represents a single chunk of regulatory text with metadata."""

    def __init__(
        self,
        chunk_id: str,
        content: str,
        citation: str,
        section_title: str,
        category: str,
        state: str = "Idaho",
        effective_date: Optional[str] = None,
        source_file: Optional[str] = None,
        chunk_index: int = 0,
        total_chunks: int = 1
    ):
        self.chunk_id = chunk_id
        self.content = content.strip()
        self.citation = citation
        self.section_title = section_title
        self.category = category
        self.state = state
        self.effective_date = effective_date
        self.source_file = source_file
        self.chunk_index = chunk_index
        self.total_chunks = total_chunks

    def to_dict(self) -> Dict:
        """Convert chunk to dictionary format."""
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "citation": self.citation,
            "section_title": self.section_title,
            "category": self.category,
            "state": self.state,
            "effective_date": self.effective_date,
            "source_file": self.source_file,
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks
        }


class SentenceSplitter:
    """Handles intelligent sentence boundary detection."""

    @staticmethod
    def is_abbreviation(text: str, pos: int) -> bool:
        """Check if a period at position pos is part of an abbreviation."""
        # Look backwards to find the word before the period
        start = pos
        while start > 0 and (text[start-1].isalpha() or text[start-1] == '.'):
            start -= 1

        word = text[start:pos+1]

        # Check against known abbreviations
        for abbrev in ABBREVIATIONS:
            if word.endswith(abbrev) or word == abbrev:
                return True

        # Check for single letter abbreviations like "A." or initials
        if len(word) == 2 and word[0].isupper() and word[1] == '.':
            return True

        return False

    @staticmethod
    def is_decimal_number(text: str, pos: int) -> bool:
        """Check if a period is part of a decimal number."""
        if pos == 0 or pos >= len(text) - 1:
            return False
        return text[pos-1].isdigit() and text[pos+1].isdigit()

    @staticmethod
    def split_into_sentences(text: str) -> List[str]:
        """Split text into sentences with smart boundary detection."""
        sentences = []
        current = []
        i = 0

        while i < len(text):
            char = text[i]
            current.append(char)

            # Check for sentence-ending punctuation
            if char in '.!?':
                # Skip if this is an abbreviation
                if char == '.' and SentenceSplitter.is_abbreviation(text, i):
                    i += 1
                    continue

                # Skip if this is a decimal number
                if char == '.' and SentenceSplitter.is_decimal_number(text, i):
                    i += 1
                    continue

                # Look ahead for proper sentence end (space + capital or end of text)
                j = i + 1
                # Skip whitespace
                while j < len(text) and text[j] in ' \t\n':
                    j += 1

                # Check if next char is uppercase or end of text
                if j >= len(text) or text[j].isupper() or text[j] in '("\'':
                    # Include trailing whitespace in current sentence
                    while i + 1 < len(text) and text[i + 1] in ' \t\n':
                        i += 1
                        current.append(text[i])

                    sentence = ''.join(current).strip()
                    if sentence:
                        sentences.append(sentence)
                    current = []

            i += 1

        # Don't forget the last sentence
        if current:
            sentence = ''.join(current).strip()
            if sentence:
                sentences.append(sentence)

        return sentences


class ChunkSplitter:
    """Handles splitting large sections into smaller chunks with overlap."""

    @staticmethod
    def split_with_overlap(
        content: str,
        section_header: str,
        max_size: int = MAX_CHUNK_SIZE,
        overlap_size: int = OVERLAP_SIZE
    ) -> List[str]:
        """
        Split content into chunks of max_size with overlap.
        Each chunk preserves the section header for context.
        """
        header_len = len(section_header) + 1  # +1 for newline

        if len(content) + header_len <= max_size:
            return [content]

        sentences = SentenceSplitter.split_into_sentences(content)

        # If sentence splitting didn't work, fall back to character-based splitting
        if not sentences or len(sentences) == 1:
            return ChunkSplitter.split_by_characters(content, section_header, max_size, overlap_size)

        chunks = []
        current_chunk = []
        current_size = header_len
        overlap_sentences = []

        for sentence in sentences:
            sentence_len = len(sentence) + 1  # +1 for space

            # If a single sentence is too long, split it by characters
            if sentence_len + header_len > max_size:
                # First, save current chunk if it exists
                if current_chunk:
                    chunk_content = section_header + "\n" + ' '.join(current_chunk)
                    chunks.append(chunk_content)
                    current_chunk = []
                    current_size = header_len

                # Split the long sentence by characters
                char_chunks = ChunkSplitter.split_by_characters(
                    sentence, section_header, max_size, overlap_size
                )
                chunks.extend(char_chunks)
                continue

            # If adding this sentence would exceed max size
            if current_size + sentence_len > max_size and current_chunk:
                # Create chunk with header
                chunk_content = section_header + "\n" + ' '.join(current_chunk)
                chunks.append(chunk_content)

                # Calculate overlap - take last sentences up to overlap_size
                overlap_sentences = []
                overlap_len = 0
                for s in reversed(current_chunk):
                    if overlap_len + len(s) + 1 <= overlap_size:
                        overlap_sentences.insert(0, s)
                        overlap_len += len(s) + 1
                    else:
                        break

                # Start new chunk with overlap
                current_chunk = overlap_sentences.copy()
                current_size = header_len + sum(len(s) + 1 for s in current_chunk)

            current_chunk.append(sentence)
            current_size += sentence_len

        # Don't forget the last chunk
        if current_chunk:
            chunk_content = section_header + "\n" + ' '.join(current_chunk)
            chunks.append(chunk_content)

        return chunks

    @staticmethod
    def split_by_characters(
        content: str,
        section_header: str,
        max_size: int = MAX_CHUNK_SIZE,
        overlap_size: int = OVERLAP_SIZE
    ) -> List[str]:
        """
        Fall back to character-based splitting when sentences are too long.
        Tries to split at word boundaries.
        """
        header_len = len(section_header) + 1
        available_size = max_size - header_len

        if len(content) <= available_size:
            return [content]

        chunks = []
        start = 0

        while start < len(content):
            end = start + available_size

            if end >= len(content):
                # Last chunk
                chunk_text = content[start:]
                chunks.append(section_header + "\n" + chunk_text)
                break

            # Try to find a word boundary (space, newline) near the end
            boundary = end
            for i in range(end, max(start, end - 100), -1):
                if content[i] in ' \n\t':
                    boundary = i
                    break

            chunk_text = content[start:boundary]
            chunks.append(section_header + "\n" + chunk_text)

            # Calculate overlap start
            overlap_start = max(start, boundary - overlap_size)
            start = overlap_start if overlap_start > start else boundary

        return chunks


class ContentFormatter:
    """Formats regulation content for better readability."""

    @staticmethod
    def format_content(content: str, section_title: str = "") -> str:
        """
        Format content to be more readable:
        - Add line breaks before list items (a., b., c., 01., 02., etc.)
        - Remove redundant repeated section headers
        - Clean up date codes
        """
        formatted = content

        # Remove redundant section title if it appears at the start of content
        if section_title:
            title_pattern = re.escape(section_title.upper())
            formatted = re.sub(rf'^\s*{title_pattern}\s*', '', formatted, flags=re.IGNORECASE)

        # Add line breaks before lettered list items: a., b., c., etc.
        # Match any context before a lowercase letter followed by period and space
        formatted = re.sub(r'\s+([a-z])\.\s+(?=[A-Z])', r'\n\n\1. ', formatted)

        # Add line breaks before numbered subsections: 01., 02., 1., 2., etc.
        formatted = re.sub(r'\s+(0[1-9]|[1-9][0-9]?)\.\s+(?=[A-Z])', r'\n\n\1. ', formatted)

        # Add line breaks before roman numeral items: i., ii., iii., iv., etc.
        formatted = re.sub(r'\s+(i{1,3}|iv|vi{0,3}|ix|x)\.\s+(?=[A-Z])', r'\n\n\1. ', formatted, flags=re.IGNORECASE)

        # Format date codes to be less intrusive: (3-15-22) -> [eff. 3-15-22]
        formatted = re.sub(r'\s*\((\d{1,2}-\d{1,2}-\d{2,4})\)', r' *[eff. \1]*', formatted)

        # Clean up any excessive whitespace
        formatted = re.sub(r'\n{3,}', '\n\n', formatted)
        formatted = re.sub(r'  +', ' ', formatted)

        return formatted.strip()


class IDAPATextProcessor:
    """Processes IDAPA regulation text files into structured chunks."""

    # Category mapping based on section numbers and keywords
    CATEGORY_MAPPING = {
        "000-049": "administrative",
        "050-099": "variances",
        "100-149": "licensing",
        "150-215": "policies",
        "216-249": "admission_discharge",
        "250-304": "physical_plant",
        "305-318": "nursing_assessment",
        "319-329": "service_agreements",
        "330-399": "records",
        "400-499": "staffing",
        "500-599": "resident_care",
        "600-699": "medications",
        "700-799": "dietary",
        "800-899": "infection_control",
        "900-999": "enforcement"
    }

    def __init__(self, raw_data_dir: str, processed_data_dir: str):
        self.raw_data_dir = Path(raw_data_dir)
        self.processed_data_dir = Path(processed_data_dir)
        self.processed_data_dir.mkdir(parents=True, exist_ok=True)

    def determine_category(self, section_num: int, title: str) -> str:
        """Determine category based on section number and title."""
        # First try section number ranges
        for range_str, category in self.CATEGORY_MAPPING.items():
            if "-" in range_str:
                start, end = map(int, range_str.split("-"))
                if start <= section_num <= end:
                    return category

        # Fallback to keyword matching in title
        title_lower = title.lower()
        if any(word in title_lower for word in ["staff", "personnel", "employee"]):
            return "staffing"
        elif any(word in title_lower for word in ["medication", "drug", "pharmaceutical"]):
            return "medications"
        elif any(word in title_lower for word in ["food", "meal", "diet", "nutrition"]):
            return "dietary"
        elif any(word in title_lower for word in ["building", "physical", "construction", "fire"]):
            return "physical_plant"
        elif any(word in title_lower for word in ["license", "licensing", "permit"]):
            return "licensing"
        elif any(word in title_lower for word in ["resident", "care", "service"]):
            return "resident_care"
        elif any(word in title_lower for word in ["admission", "discharge", "agreement"]):
            return "admission_discharge"
        elif any(word in title_lower for word in ["nursing", "assessment", "health"]):
            return "nursing_assessment"
        elif any(word in title_lower for word in ["infection", "sanitation", "hygiene"]):
            return "infection_control"
        elif any(word in title_lower for word in ["enforcement", "violation", "penalty"]):
            return "enforcement"
        elif any(word in title_lower for word in ["record", "document", "disclosure"]):
            return "records"
        elif any(word in title_lower for word in ["definition", "purpose", "scope", "authority"]):
            return "administrative"

        return "general"

    def determine_category_from_title(self, title: str) -> str:
        """Determine category purely from title keywords."""
        return self.determine_category(0, title)

    def detect_document_type(self, filename: str, content: str) -> str:
        """Detect the type of document based on filename and content."""
        filename_lower = filename.lower()

        # Check IDAPA first (before food code check, since IDAPA 16.02.19 is "food code" but in IDAPA format)
        if "idapa" in filename_lower:
            return "idapa"
        elif "title 39" in filename_lower or "title 74" in filename_lower:
            return "idaho_code"
        elif "ada" in filename_lower or "accessibility" in filename_lower:
            return "ada_guidelines"
        elif "additional referenced" in filename_lower:
            return "reference_links"
        elif "food code" in filename_lower or "public health food" in filename_lower:
            return "food_code"
        else:
            # Try to detect from content
            if re.search(r'^\d{1,2}-\d{3}\.\d{2}\s', content, re.MULTILINE):
                return "food_code"
            elif re.search(r'^\d{2}-\d{4}\.\s+[A-Z]', content, re.MULTILINE):
                return "idaho_code"
            elif re.search(r'^\d+\.\d+\.?\d*\*?\s+[A-Z]', content, re.MULTILINE):
                return "ada_guidelines"
            else:
                return "idapa"

    def chunk_by_sections_idapa(self, text: str, source_file: str) -> List[RegulationChunk]:
        """
        Chunk IDAPA-format text by regulation sections.
        Format: 100. SECTION TITLE IN ALL CAPS.
        """
        chunks = []
        lines = text.split('\n')

        current_section = None
        current_content = []
        current_title = ""
        in_toc = True

        # Pattern to match ALL CAPS section headers like "100. LICENSING REQUIREMENTS."
        section_header_pattern = r'^(\d{3,4})\.\s+([A-Z][A-Z\s\-,&()]+)\.'
        reserved_pattern = r'^\d{3,4}\s*--\s*\d{3,4}\.\s*\(RESERVED\)'

        for line in lines:
            line_stripped = line.strip()

            # Detect when we've moved past the table of contents
            if in_toc and re.match(section_header_pattern, line_stripped):
                in_toc = False

            if in_toc:
                continue

            # Check if this is a RESERVED section marker
            if re.match(reserved_pattern, line_stripped):
                if current_section is not None and current_content:
                    section_chunks = self._create_chunks_with_splitting(
                        current_section, current_title,
                        '\n'.join(current_content), source_file, "idapa"
                    )
                    chunks.extend(section_chunks)
                current_section = None
                current_content = []
                current_title = ""
                continue

            # Check if this line is an ALL CAPS section header
            match = re.match(section_header_pattern, line_stripped)

            if match:
                if current_section is not None and current_content:
                    section_chunks = self._create_chunks_with_splitting(
                        current_section, current_title,
                        '\n'.join(current_content), source_file, "idapa"
                    )
                    chunks.extend(section_chunks)

                current_section = int(match.group(1))
                current_title = match.group(2).strip()
                current_content = [line_stripped]

            elif current_section is not None:
                current_content.append(line_stripped)

        # Don't forget the last section
        if current_section is not None and current_content:
            section_chunks = self._create_chunks_with_splitting(
                current_section, current_title,
                '\n'.join(current_content), source_file, "idapa"
            )
            chunks.extend(section_chunks)

        return chunks

    def chunk_by_sections_food_code(self, text: str, source_file: str) -> List[RegulationChunk]:
        """
        Chunk Food Code format text.
        Format: 3-201.11 Title Text
        """
        chunks = []

        # Skip table of contents and preface - find where actual content starts
        # Look for first chapter heading like "Chapter 1" followed by actual section
        chapter_start = re.search(r'\n3-1\s+CHARACTERISTICS\s*\n', text)
        if chapter_start:
            # Find actual content start (after TOC)
            content_match = re.search(r'\n3-101\s+Condition\s*\n', text[chapter_start.end():])
            if content_match:
                text = text[chapter_start.end() + content_match.start():]

        # Pattern for Food Code sections: 3-201.11, 4-101.11, etc.
        section_pattern = r'^(\d-\d{3}\.\d{2})\s+(.+?)(?=\n|\.|$)'

        # Split by main sections
        sections = re.split(r'\n(?=\d-\d{3}\.\d{2}\s)', text)

        for section_text in sections:
            section_text = section_text.strip()
            if not section_text:
                continue

            # Extract section number and title
            match = re.match(r'^(\d-\d{3}\.\d{2})\s+(.+?)(?:\n|\.)', section_text)
            if match:
                section_num = match.group(1)
                section_title = match.group(2).strip()
                content = section_text

                # Create chunks with splitting if needed
                section_chunks = self._create_chunks_with_splitting(
                    section_num, section_title, content, source_file, "food_code"
                )
                chunks.extend(section_chunks)

        return chunks

    def chunk_by_sections_idaho_code(self, text: str, source_file: str) -> List[RegulationChunk]:
        """
        Chunk Idaho Code format text (Title 39, Title 74).
        Format: 39-3301. SECTION TITLE.
        """
        chunks = []

        # Determine which title this is
        title_match = re.search(r'TITLE\s+(\d+)', text)
        title_num = title_match.group(1) if title_match else "0"

        # Pattern: 39-3301. TITLE TEXT.
        section_pattern = rf'^({title_num}-\d+)\.\s+([A-Z][A-Z\s\-,&()]+)\.'

        lines = text.split('\n')
        current_section = None
        current_content = []
        current_title = ""

        for line in lines:
            line_stripped = line.strip()

            match = re.match(section_pattern, line_stripped)

            if match:
                # Save previous section
                if current_section is not None and current_content:
                    section_chunks = self._create_chunks_with_splitting(
                        current_section, current_title,
                        '\n'.join(current_content), source_file, "idaho_code"
                    )
                    chunks.extend(section_chunks)

                current_section = match.group(1)
                current_title = match.group(2).strip()
                current_content = [line_stripped]
            elif current_section is not None:
                current_content.append(line_stripped)

        # Last section
        if current_section is not None and current_content:
            section_chunks = self._create_chunks_with_splitting(
                current_section, current_title,
                '\n'.join(current_content), source_file, "idaho_code"
            )
            chunks.extend(section_chunks)

        return chunks

    def chunk_by_sections_ada(self, text: str, source_file: str) -> List[RegulationChunk]:
        """
        Chunk ADA Accessibility Guidelines format.
        Format: 4.1.1 Section Title or 4.1.1* Section Title
        """
        chunks = []

        # Skip table of contents - find where content starts
        content_start = re.search(r'\n1\.\s*PURPOSE\s*\n', text, re.IGNORECASE)
        if content_start:
            text = text[content_start.start():]

        # Pattern: 4.1.1 or 4.1.1* followed by title
        section_pattern = r'^(\d+\.[\d.]+\*?)\s+(.+?)(?:\n|$)'

        lines = text.split('\n')
        current_section = None
        current_content = []
        current_title = ""

        for line in lines:
            line_stripped = line.strip()

            # Skip page numbers and short lines
            if re.match(r'^\d+$', line_stripped) or len(line_stripped) < 3:
                continue

            match = re.match(section_pattern, line_stripped)

            if match:
                # Save previous section
                if current_section is not None and current_content:
                    section_chunks = self._create_chunks_with_splitting(
                        current_section, current_title,
                        '\n'.join(current_content), source_file, "ada"
                    )
                    chunks.extend(section_chunks)

                current_section = match.group(1)
                current_title = match.group(2).strip()
                current_content = [line_stripped]
            elif current_section is not None:
                current_content.append(line_stripped)

        # Last section
        if current_section is not None and current_content:
            section_chunks = self._create_chunks_with_splitting(
                current_section, current_title,
                '\n'.join(current_content), source_file, "ada"
            )
            chunks.extend(section_chunks)

        return chunks

    def chunk_reference_links(self, text: str, source_file: str) -> List[RegulationChunk]:
        """Process reference links document - handles JSON format."""
        chunks = []

        # Try to parse as JSON first
        try:
            data = json.loads(text)
            references = data.get('regulatory_references', [])

            for i, ref in enumerate(references):
                ref_code = ref.get('reference_code', f'Reference {i+1}')
                full_title = ref.get('full_title', '')
                doc_type = ref.get('document_type', '')
                notes = ref.get('notes', '')
                primary_url = ref.get('primary_url', '')
                alternate_urls = ref.get('alternate_urls', [])
                cost = ref.get('cost', '')
                access_type = ref.get('access_type', '')

                # Build content text
                content_parts = [
                    f"Reference Code: {ref_code}",
                    f"Full Title: {full_title}",
                    f"Document Type: {doc_type}",
                    f"Access: {access_type}",
                ]
                if cost:
                    content_parts.append(f"Cost: {cost}")
                if primary_url:
                    content_parts.append(f"URL: {primary_url}")
                if alternate_urls:
                    content_parts.append(f"Alternate URLs: {', '.join(alternate_urls)}")
                if notes:
                    content_parts.append(f"Notes: {notes}")

                content = '\n'.join(content_parts)

                chunk = RegulationChunk(
                    chunk_id=f"ref_{ref_code.replace(' ', '_').replace('.', '_').lower()}",
                    content=content,
                    citation=ref_code,
                    section_title=full_title[:50] if full_title else ref_code,
                    category="references",
                    state="Idaho",
                    effective_date="2025",
                    source_file=source_file,
                    chunk_index=0,
                    total_chunks=1
                )
                chunks.append(chunk)

            return chunks

        except json.JSONDecodeError:
            pass

        # Fall back to text-based parsing
        sections = re.split(r'\n(?=[A-Z][A-Z\s]+:?\n)', text)

        for i, section in enumerate(sections):
            section = section.strip()
            if not section or len(section) < 50:
                continue

            lines = section.split('\n')
            title = lines[0].strip()[:50] if lines else f"Reference Links {i+1}"

            chunk = RegulationChunk(
                chunk_id=f"ref_links_{i}",
                content=section,
                citation=f"Reference Links",
                section_title=title,
                category="references",
                state="Idaho",
                effective_date="2025",
                source_file=source_file,
                chunk_index=0,
                total_chunks=1
            )
            chunks.append(chunk)

        return chunks

    def _create_chunks_with_splitting(
        self,
        section_id,
        section_title: str,
        content: str,
        source_file: str,
        doc_type: str
    ) -> List[RegulationChunk]:
        """Create chunks, splitting large sections if needed."""

        # Skip very short sections
        if len(content.strip()) < 100:
            return []

        # Skip RESERVED sections
        if "RESERVED" in section_title.upper():
            return []

        # Determine citation and id prefix based on document type and source file
        citation_prefix, doc_prefix = self._get_prefixes(source_file, doc_type)

        # Create section header for context
        section_header = f"{section_id}. {section_title}"

        # Split into chunks if content is too large
        if len(content) > MAX_CHUNK_SIZE:
            chunk_contents = ChunkSplitter.split_with_overlap(
                content, section_header, MAX_CHUNK_SIZE, OVERLAP_SIZE
            )
        else:
            chunk_contents = [content]

        chunks = []
        total_chunks = len(chunk_contents)

        for i, chunk_content in enumerate(chunk_contents):
            # Determine category
            if doc_type == "idapa" and isinstance(section_id, int):
                category = self.determine_category(section_id, section_title)
            else:
                category = self.determine_category_from_title(section_title)

            # Create chunk ID
            if total_chunks > 1:
                chunk_id = f"{doc_prefix}_{section_id}_part{i+1}"
                citation = f"{citation_prefix}.{section_id} (Part {i+1}/{total_chunks})"
            else:
                chunk_id = f"{doc_prefix}_{section_id}"
                citation = f"{citation_prefix}.{section_id}"

            # Format content for better readability
            formatted_content = ContentFormatter.format_content(chunk_content, section_title)

            chunk = RegulationChunk(
                chunk_id=chunk_id,
                content=formatted_content,
                citation=citation,
                section_title=section_title,
                category=category,
                state="Idaho",
                effective_date="2025",
                source_file=source_file,
                chunk_index=i,
                total_chunks=total_chunks
            )
            chunks.append(chunk)

        return chunks

    def _get_prefixes(self, source_file: str, doc_type: str) -> Tuple[str, str]:
        """Get citation and document ID prefixes based on source file."""

        # More specific matching first
        if "IDAPA 16.02.19" in source_file:
            return "IDAPA 16.02.19", "idapa_16.02.19"
        elif "IDAPA 16.02.1" in source_file:
            return "IDAPA 16.02.01", "idapa_16.02.01"
        elif "IDAPA 16.05.01" in source_file:
            return "IDAPA 16.05.01", "idapa_16.05.01"
        elif "IDAPA 16.05.06" in source_file:
            return "IDAPA 16.05.06", "idapa_16.05.06"
        elif "IDAPA 16.txt" in source_file or "IDAPA 16 " in source_file:
            return "IDAPA 16.03.22", "idapa_16.03.22"
        elif "IDAPA 24.34.01" in source_file:
            return "IDAPA 24.34.01", "idapa_24.34.01"
        elif "IDAPA 24.39.30" in source_file:
            return "IDAPA 24.39.30", "idapa_24.39.30"
        elif "IDAPA 24" in source_file:
            return "IDAPA 24", "idapa_24"
        elif "TITLE 39" in source_file:
            return "Idaho Code Title 39", "idaho_code_39"
        elif "Title 74" in source_file:
            return "Idaho Code Title 74", "idaho_code_74"
        elif "ADA" in source_file or "Accessibility" in source_file:
            return "ADA Guidelines", "ada"
        elif "Food Code" in source_file or "Public Health Food" in source_file:
            return "FDA Food Code", "fda_food_code"
        else:
            return "Idaho Regulation", "idaho_reg"

    def process_file(self, filename: str) -> List[RegulationChunk]:
        """Process a single regulation text file based on its format."""
        file_path = self.raw_data_dir / filename

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        print(f"Processing {filename}...")

        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()

        # Detect document type and use appropriate parser
        doc_type = self.detect_document_type(filename, text)

        if doc_type == "food_code":
            chunks = self.chunk_by_sections_food_code(text, filename)
        elif doc_type == "idaho_code":
            chunks = self.chunk_by_sections_idaho_code(text, filename)
        elif doc_type == "ada_guidelines":
            chunks = self.chunk_by_sections_ada(text, filename)
        elif doc_type == "reference_links":
            chunks = self.chunk_reference_links(text, filename)
        else:  # idapa
            chunks = self.chunk_by_sections_idapa(text, filename)

        print(f"  Type: {doc_type}, Created {len(chunks)} chunks from {filename}")

        return chunks

    def process_all_files(self) -> Dict[str, List[RegulationChunk]]:
        """Process all text files in the raw data directory."""
        all_chunks = {}

        for txt_file in self.raw_data_dir.glob("*.txt"):
            try:
                chunks = self.process_file(txt_file.name)
                all_chunks[txt_file.name] = chunks
            except Exception as e:
                print(f"  Error processing {txt_file.name}: {e}")

        return all_chunks

    def save_chunks(self, chunks: List[RegulationChunk], output_filename: str = "chunks.json"):
        """Save chunks to JSON file."""
        output_path = self.processed_data_dir / output_filename

        chunks_data = [chunk.to_dict() for chunk in chunks]

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(chunks_data, f, indent=2, ensure_ascii=False)

        print(f"Saved {len(chunks)} chunks to {output_path}")

        return output_path

    def preview_chunks(self, chunks: List[RegulationChunk], num_samples: int = 5):
        """Print preview of sample chunks."""
        print(f"\n{'='*80}")
        print(f"PREVIEW: Showing {min(num_samples, len(chunks))} of {len(chunks)} chunks")
        print(f"{'='*80}\n")

        for i, chunk in enumerate(chunks[:num_samples]):
            print(f"Chunk {i+1}:")
            print(f"  ID: {chunk.chunk_id}")
            print(f"  Citation: {chunk.citation}")
            print(f"  Title: {chunk.section_title}")
            print(f"  Category: {chunk.category}")
            print(f"  Content length: {len(chunk.content)} chars")
            print(f"  Chunk: {chunk.chunk_index + 1}/{chunk.total_chunks}")
            print(f"  Content preview: {chunk.content[:200]}...")
            print(f"{'-'*80}\n")


def deduplicate_chunks(chunks: List[RegulationChunk]) -> List[RegulationChunk]:
    """Remove duplicate chunks based on content similarity."""
    seen_content = {}
    unique_chunks = []

    for chunk in chunks:
        # Normalize content for comparison
        normalized = ' '.join(chunk.content.lower().split())

        # Check for exact or near-duplicate
        is_duplicate = False
        for seen_normalized, seen_chunk in seen_content.items():
            # If content is very similar (>90% overlap), skip
            if normalized == seen_normalized:
                is_duplicate = True
                break
            # Check for substring relationship
            if len(normalized) > 100 and len(seen_normalized) > 100:
                if normalized in seen_normalized or seen_normalized in normalized:
                    is_duplicate = True
                    break

        if not is_duplicate:
            seen_content[normalized] = chunk
            unique_chunks.append(chunk)

    return unique_chunks


def main():
    """Main processing pipeline."""

    # Set up paths
    base_dir = Path("/Users/nikolashulewsky/senior-chatbots/backend/alf")
    raw_dir = base_dir / "data" / "raw"
    processed_dir = base_dir / "data" / "processed"

    # Initialize processor
    processor = IDAPATextProcessor(str(raw_dir), str(processed_dir))

    print("\n" + "="*80)
    print("PROCESSING ALL REGULATION FILES")
    print("="*80 + "\n")

    all_chunks_by_file = processor.process_all_files()

    # Combine all chunks
    all_chunks = []
    for filename, chunks in all_chunks_by_file.items():
        all_chunks.extend(chunks)

    print(f"\nTotal chunks before deduplication: {len(all_chunks)}")

    # Deduplicate
    unique_chunks = deduplicate_chunks(all_chunks)
    print(f"Total chunks after deduplication: {len(unique_chunks)}")

    # Preview some chunks
    processor.preview_chunks(unique_chunks, num_samples=5)

    # Save combined chunks
    processor.save_chunks(unique_chunks, "all_chunks.json")

    # Print summary statistics
    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)
    print(f"Total files processed: {len(all_chunks_by_file)}")
    print(f"Total unique chunks: {len(unique_chunks)}")

    # Source file breakdown
    source_counts = {}
    for chunk in unique_chunks:
        source = chunk.source_file
        source_counts[source] = source_counts.get(source, 0) + 1

    print("\nChunks by source file:")
    for source, count in sorted(source_counts.items()):
        print(f"  {count:4d}: {source}")

    # Category breakdown
    category_counts = {}
    for chunk in unique_chunks:
        category_counts[chunk.category] = category_counts.get(chunk.category, 0) + 1

    print("\nChunks by category:")
    for category, count in sorted(category_counts.items()):
        print(f"  {count:4d}: {category}")

    # Chunk size statistics
    sizes = [len(chunk.content) for chunk in unique_chunks]
    print(f"\nChunk size statistics:")
    print(f"  Min: {min(sizes)} chars")
    print(f"  Max: {max(sizes)} chars")
    print(f"  Avg: {sum(sizes) // len(sizes)} chars")

    # Count multi-part chunks
    multi_part = sum(1 for c in unique_chunks if c.total_chunks > 1)
    print(f"\nMulti-part chunks: {multi_part}")

    print("\n" + "="*80)
    print("PROCESSING COMPLETE!")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
