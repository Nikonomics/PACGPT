"""
Idaho ALF Regulation Text Processor
Extracts and chunks regulatory text files by section with metadata.
"""

import re
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


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
        source_file: Optional[str] = None
    ):
        self.chunk_id = chunk_id
        self.content = content.strip()
        self.citation = citation
        self.section_title = section_title
        self.category = category
        self.state = state
        self.effective_date = effective_date
        self.source_file = source_file

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
            "source_file": self.source_file
        }


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

        return "general"

    def extract_section_number(self, text: str) -> Optional[int]:
        """Extract section number from text like '100.' or 'Section 100'."""
        # Match patterns like "100.", "Section 100", "100 -"
        patterns = [
            r"^(\d{3,4})\.",  # "100."
            r"Section\s+(\d{3,4})",  # "Section 100"
            r"^(\d{3,4})\s*[-–—]"  # "100 -" or "100 –"
        ]

        for pattern in patterns:
            match = re.search(pattern, text.strip())
            if match:
                return int(match.group(1))

        return None

    def chunk_by_sections(self, text: str, source_file: str) -> List[RegulationChunk]:
        """
        Chunk text by regulation sections.
        Each section (e.g., 100., 101., etc.) becomes a chunk.
        Skips table of contents and only processes actual regulatory content.
        """
        chunks = []
        lines = text.split('\n')

        current_section = None
        current_content = []
        current_title = ""
        in_toc = True  # Start by assuming we're in table of contents

        # Pattern to match ALL CAPS section headers like "100. LICENSING REQUIREMENTS."
        section_header_pattern = r'^(\d{3,4})\.\s+([A-Z][A-Z\s\-,&()]+)\.'
        # Pattern to match RESERVED sections
        reserved_pattern = r'^\d{3,4}\s*--\s*\d{3,4}\.\s*\(RESERVED\)'

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Detect when we've moved past the table of contents
            # Look for the first ALL CAPS section header
            if in_toc and re.match(section_header_pattern, line_stripped):
                in_toc = False

            # Skip lines if we're still in table of contents
            if in_toc:
                continue

            # Check if this is a RESERVED section marker
            if re.match(reserved_pattern, line_stripped):
                # Save current section before hitting reserved
                if current_section is not None and current_content:
                    chunk = self._create_chunk(
                        current_section,
                        current_title,
                        '\n'.join(current_content),
                        source_file
                    )
                    if chunk:
                        chunks.append(chunk)

                # Reset for next section
                current_section = None
                current_content = []
                current_title = ""
                continue

            # Check if this line is an ALL CAPS section header
            match = re.match(section_header_pattern, line_stripped)

            if match:
                # Save previous section if exists
                if current_section is not None and current_content:
                    chunk = self._create_chunk(
                        current_section,
                        current_title,
                        '\n'.join(current_content),
                        source_file
                    )
                    if chunk:
                        chunks.append(chunk)

                # Start new section
                current_section = int(match.group(1))
                current_title = match.group(2).strip()
                current_content = [line_stripped]  # Include header in content

            elif current_section is not None:
                # Add all content to current section until we hit a new section
                current_content.append(line_stripped)

        # Don't forget the last section
        if current_section is not None and current_content:
            chunk = self._create_chunk(
                current_section,
                current_title,
                '\n'.join(current_content),
                source_file
            )
            if chunk:
                chunks.append(chunk)

        return chunks

    def _create_chunk(
        self,
        section_num: int,
        section_title: str,
        content: str,
        source_file: str
    ) -> Optional[RegulationChunk]:
        """Create a RegulationChunk from section data."""

        # Skip very short sections (likely just headers)
        if len(content.strip()) < 100:
            return None

        # Skip sections that are themselves RESERVED (title contains RESERVED)
        if "RESERVED" in section_title.upper():
            return None

        # Determine document type from filename (more specific matching - longest first!)
        if "IDAPA 16.02.19" in source_file:
            doc_prefix = "idapa_16.02.19"
            citation_prefix = "IDAPA 16.02.19"
        elif "IDAPA 16.02.1" in source_file:
            doc_prefix = "idapa_16.02.01"
            citation_prefix = "IDAPA 16.02.01"
        elif "IDAPA 16.05.01" in source_file:
            doc_prefix = "idapa_16.05.01"
            citation_prefix = "IDAPA 16.05.01"
        elif "IDAPA 16.05.06" in source_file:
            doc_prefix = "idapa_16.05.06"
            citation_prefix = "IDAPA 16.05.06"
        elif "IDAPA 16.txt" in source_file or "IDAPA 16 " in source_file:
            doc_prefix = "idapa_16.03.22"
            citation_prefix = "IDAPA 16.03.22"
        elif "IDAPA 24.34.01" in source_file:
            doc_prefix = "idapa_24.34.01"
            citation_prefix = "IDAPA 24.34.01"
        elif "IDAPA 24.39.30" in source_file:
            doc_prefix = "idapa_24.39.30"
            citation_prefix = "IDAPA 24.39.30"
        elif "IDAPA 24" in source_file:
            doc_prefix = "idapa_24"
            citation_prefix = "IDAPA 24"
        elif "TITLE 39" in source_file:
            doc_prefix = "title_39"
            citation_prefix = "TITLE 39"
        else:
            doc_prefix = "idaho_reg"
            citation_prefix = "IDAPA"

        chunk_id = f"{doc_prefix}_{section_num}"
        citation = f"{citation_prefix}.{section_num:03d}"
        category = self.determine_category(section_num, section_title)

        return RegulationChunk(
            chunk_id=chunk_id,
            content=content,
            citation=citation,
            section_title=section_title,
            category=category,
            state="Idaho",
            effective_date="2025",  # Update with actual date from document
            source_file=source_file
        )

    def process_file(self, filename: str) -> List[RegulationChunk]:
        """Process a single regulation text file."""
        file_path = self.raw_data_dir / filename

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        print(f"Processing {filename}...")

        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()

        chunks = self.chunk_by_sections(text, filename)

        print(f"  Created {len(chunks)} chunks from {filename}")

        return chunks

    def process_all_files(self) -> Dict[str, List[RegulationChunk]]:
        """Process all text files in the raw data directory."""
        all_chunks = {}

        for txt_file in self.raw_data_dir.glob("*.txt"):
            chunks = self.process_file(txt_file.name)
            all_chunks[txt_file.name] = chunks

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
            print(f"  Content preview: {chunk.content[:200]}...")
            print(f"{'-'*80}\n")


def main():
    """Main processing pipeline."""

    # Set up paths
    base_dir = Path("/Users/nikolashulewsky/snf-news-aggregator/idaho-alf-chatbot")
    raw_dir = base_dir / "data" / "raw"
    processed_dir = base_dir / "data" / "processed"

    # Initialize processor
    processor = IDAPATextProcessor(str(raw_dir), str(processed_dir))

    # Process IDAPA 16 (main document)
    print("\n" + "="*80)
    print("PROCESSING IDAHO ALF REGULATIONS")
    print("="*80 + "\n")

    chunks_idapa16 = processor.process_file("IDAPA 16.txt")

    # Preview some chunks
    processor.preview_chunks(chunks_idapa16, num_samples=5)

    # Save chunks
    processor.save_chunks(chunks_idapa16, "idapa_16_chunks.json")

    # Process all files
    print("\n" + "="*80)
    print("PROCESSING ALL REGULATION FILES")
    print("="*80 + "\n")

    all_chunks_by_file = processor.process_all_files()

    # Combine all chunks
    all_chunks = []
    for filename, chunks in all_chunks_by_file.items():
        all_chunks.extend(chunks)

    # Save combined chunks
    processor.save_chunks(all_chunks, "all_chunks.json")

    # Print summary statistics
    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)
    print(f"Total files processed: {len(all_chunks_by_file)}")
    print(f"Total chunks created: {len(all_chunks)}")

    # Category breakdown
    category_counts = {}
    for chunk in all_chunks:
        category_counts[chunk.category] = category_counts.get(chunk.category, 0) + 1

    print("\nChunks by category:")
    for category, count in sorted(category_counts.items()):
        print(f"  {category}: {count}")

    print("\n" + "="*80)
    print("PROCESSING COMPLETE!")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
