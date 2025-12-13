"""
Process US Public Health Food Code to extract temperature-related sections.
"""

import re
import json
from pathlib import Path
from typing import List, Dict

def process_food_code(input_file: str, output_file: str):
    """Process the US Public Health Food Code and extract chunks."""
    
    print(f"Processing {input_file}...")
    
    # Read the file
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split into sections (looking for patterns like "3-501", "4-302", etc.)
    section_pattern = r'(\d+-\d+\s+[^\n]+)'
    sections = re.findall(section_pattern, content)
    
    print(f"Found {len(sections)} sections")
    
    # Find temperature-related sections
    temperature_keywords = [
        'temperature', 'cooking', 'holding', 'cooling', 'reheating',
        'cold holding', 'hot holding', 'time/temperature', 'time temperature',
        '135', '41', '165', '145', '155', '140'
    ]
    
    chunks = []
    chunk_id = 1
    
    # Split content by section headers
    parts = re.split(r'(\d+-\d+\s+[^\n]+)', content)
    
    for i in range(1, len(parts), 2):
        if i + 1 < len(parts):
            section_header = parts[i].strip()
            section_content = parts[i + 1].strip()
            
            # Check if section is temperature-related
            is_temp_related = any(keyword.lower() in section_content.lower() for keyword in temperature_keywords)
            
            if is_temp_related and len(section_content) > 100:
                # Extract section number (e.g., "3-501")
                section_match = re.match(r'(\d+-\d+)', section_header)
                if section_match:
                    section_num = section_match.group(1)
                    
                    # Create chunk
                    chunk = {
                        "chunk_id": f"food_code_{chunk_id}",
                        "content": section_content[:2000],  # Limit to 2000 chars
                        "citation": f"US Food Code {section_num}",
                        "section_title": section_header,
                        "category": "dietary",
                        "state": "Federal",
                        "effective_date": "2022-01-01",
                        "source_file": "US Public Health Food Code.txt"
                    }
                    chunks.append(chunk)
                    chunk_id += 1
    
    print(f"Created {len(chunks)} temperature-related chunks")
    
    # Save chunks
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)
    
    print(f"Saved to {output_file}")
    
    return chunks


if __name__ == "__main__":
    base_dir = Path(__file__).parent.parent
    input_file = base_dir / "data" / "raw" / "US Public Health Food Code.txt"
    output_file = base_dir / "data" / "processed" / "food_code_chunks.json"
    
    chunks = process_food_code(str(input_file), str(output_file))
    
    print(f"\n{'='*80}")
    print("FOOD CODE CHUNKS SUMMARY")
    print(f"{'='*80}\n")
    print(f"Total chunks: {len(chunks)}")
    print("\nSample chunks:")
    for i, chunk in enumerate(chunks[:5], 1):
        print(f"\n{i}. {chunk['citation']}")
        print(f"   {chunk['section_title']}")
        print(f"   Content: {chunk['content'][:200]}...")

