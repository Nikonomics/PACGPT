# Regulatory Data Cleaning Pipeline - Usage Guide

## Overview

This pipeline addresses the quality issues identified in your previous implementation:

| Issue | Previous | Target | This Pipeline |
|-------|----------|--------|---------------|
| Chunk size | 146 words avg | 400-800 words | ✅ Semantic-aware sizing |
| Mid-list splits | 55% | 0% | ✅ List boundary detection |
| Parent-child links | Missing | 100% | ✅ Hierarchy preservation |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    RegulatoryDataPipeline                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Phase 1: Parsing           Phase 2: Cleaning                   │
│  ┌─────────────────┐        ┌─────────────────┐                │
│  │ DocumentParser  │   →    │ ContentCleaner  │                │
│  │ - Type detect   │        │ - Noise removal │                │
│  │ - Hierarchy     │        │ - Date normalize│                │
│  │ - Parent-child  │        │ - Citation std  │                │
│  └─────────────────┘        └─────────────────┘                │
│           │                          │                          │
│           ▼                          ▼                          │
│  Phase 3: Chunking          Phase 4: Tagging                   │
│  ┌─────────────────┐        ┌─────────────────┐                │
│  │ SemanticChunker │   →    │ MetadataTagger  │                │
│  │ - List blocks   │        │ - Jurisdiction  │                │
│  │ - Size targets  │        │ - Citations     │                │
│  │ - Overlap       │        │ - Categories    │                │
│  └─────────────────┘        └─────────────────┘                │
│           │                          │                          │
│           ▼                          ▼                          │
│  ┌─────────────────────────────────────────────┐               │
│  │            QualityValidator                  │               │
│  │  - Size compliance rate                      │               │
│  │  - List integrity rate                       │               │
│  │  - Hierarchy coverage rate                   │               │
│  └─────────────────────────────────────────────┘               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start with Claude Code

### Step 1: Copy to your project

```bash
# From your project root
cp regulatory_data_cleaner.py backend/alf/

# Or integrate into existing structure
cp regulatory_data_cleaner.py backend/alf/improved_processor.py
```

### Step 2: Process your documents

```python
from improved_processor import RegulatoryDataPipeline, print_quality_report

# Initialize
pipeline = RegulatoryDataPipeline()

# Process all documents
chunks, report = pipeline.process_directory(
    input_dir="backend/alf/data/raw/",
    output_file="backend/alf/data/processed/chunks_v2.json"
)

# Check quality
print_quality_report(report)
```

### Step 3: Validate against Golden Questions

```python
# After processing, test retrieval accuracy
from quality_tester import GoldenQuestionTester

tester = GoldenQuestionTester(chunks)
results = tester.run_test_suite("golden_questions.csv")

print(f"Hit Rate: {results['hit_rate']:.1%}")  # Target: >85%
```

## Key Improvements Explained

### 1. List Integrity (0% Split Target)

**Previous approach** split on character count, breaking lists mid-item:
```
# BAD: Chunk ends here
"...facilities must provide:
a. 24-hour supervision;
b. Assistance with"

# Next chunk starts
"activities of daily living;
c. Medication management;"
```

**New approach** detects list blocks and keeps them together:
```python
def _identify_list_blocks(self, content: str) -> List[Tuple[int, int]]:
    """Find start and end positions of list blocks."""
    # Detects: (a), (1), a., 1., i., •, -
    # Returns block boundaries that CANNOT be split
```

### 2. Semantic Chunking (400-800 Word Target)

**Previous approach**: Fixed 1500 character limit → ~146 word average

**New approach**: Hierarchical strategy based on content structure

```python
# Configuration
MIN_CHUNK_WORDS = 400   # Don't create tiny chunks
MAX_CHUNK_WORDS = 800   # Split if exceeds this
OVERLAP_WORDS = 50      # Context preservation

# Decision logic
if section.word_count <= MAX_CHUNK_WORDS:
    return [single_chunk]  # Keep together
else:
    return split_at_semantic_boundaries()  # Never mid-list
```

### 3. Parent-Child Hierarchy

**Previous approach**: Flat structure, no relationships

**New approach**: Full hierarchy tracking during parsing

```python
@dataclass
class Chunk:
    section_number: str
    parent_chunk_id: Optional[str]      # Link to parent
    child_chunk_ids: List[str]          # Links to children
    position_in_section: int            # "3 of 7"
    total_in_section: int
```

This enables:
- Navigation: "Show me the parent regulation"
- Context: "What other requirements are in this section?"
- Completeness: "Am I seeing all parts of this rule?"

## Integration with Existing txt_processor.py

You have two options:

### Option A: Replace entirely

```python
# backend/alf/txt_processor.py
from improved_processor import RegulatoryDataPipeline

def process_all_documents():
    pipeline = RegulatoryDataPipeline()
    chunks, report = pipeline.process_directory(
        "data/raw/",
        "data/processed/all_chunks.json"
    )
    return chunks
```

### Option B: Hybrid approach

Keep your existing parsing (which works), replace chunking:

```python
# In your existing txt_processor.py
from improved_processor import SemanticChunker, ContentCleaner

class TxtProcessor:
    def __init__(self):
        self.cleaner = ContentCleaner()
        self.chunker = SemanticChunker()  # Replace your ChunkSplitter

    def process_section(self, section):
        # Your existing parsing...

        # New cleaning
        content = self.cleaner.clean(section.content)

        # New chunking (won't split lists)
        chunks = self.chunker.chunk_section(section)

        return chunks
```

## Quality Validation Workflow

### Before Processing

```bash
# Check your current state
python -c "
from improved_processor import QualityValidator
import json

with open('data/processed/all_chunks.json') as f:
    current_chunks = json.load(f)

# Quick assessment
total = len(current_chunks)
word_counts = [len(c['content'].split()) for c in current_chunks]
avg_words = sum(word_counts) / total

print(f'Current chunks: {total}')
print(f'Average words: {avg_words:.0f}')
print(f'In 400-800 range: {sum(1 for wc in word_counts if 400 <= wc <= 800) / total:.1%}')
"
```

### After Processing

```python
from improved_processor import (
    RegulatoryDataPipeline,
    QualityValidator,
    print_quality_report
)

# Process
pipeline = RegulatoryDataPipeline()
chunks, report = pipeline.process_directory("data/raw/", "data/processed/chunks_v2.json")

# Detailed analysis
detailed = pipeline.validator.detailed_analysis(chunks)
print_quality_report(report, detailed)

# Check production readiness
passes, issues = report.passes_production_threshold()
if not passes:
    print("\n⚠️ Address these before production:")
    for issue in issues:
        print(f"  - {issue}")
```

## Document Type Support

| Document | Detection Pattern | Chunking Strategy |
|----------|-------------------|-------------------|
| IDAPA 16.03.22 (ALF) | `^\d{3}\. TITLE.` | Hierarchical |
| IDAPA 16.02.19 (Food) | Same | Hierarchical |
| Idaho Code Title 39 | `^\d{2}-\d{4}.` | Hierarchical |
| FDA Food Code | `^\d-\d{3}\.\d{2}` | Hierarchical |
| ADA Guidelines | `^\d\.\d+` | Hierarchical |

## Troubleshooting

### Issue: Still seeing split lists

Check your list patterns match your documents:
```python
# In SemanticChunker, add custom patterns if needed:
LIST_PATTERNS = [
    r'^\s*\([a-z]\)',      # (a) (b) (c)
    r'^\s*\(\d+\)',        # (1) (2) (3)
    # Add your custom patterns:
    r'^\s*[A-Z]\.\s',      # A. B. C. (capital letters)
]
```

### Issue: Chunks too small

Adjust the config:
```python
from improved_processor import ChunkConfig, RegulatoryDataPipeline

config = ChunkConfig()
config.MIN_CHUNK_WORDS = 300    # Lower minimum
config.ABSOLUTE_MIN_WORDS = 100  # Allow smaller orphans

pipeline = RegulatoryDataPipeline(config)
```

### Issue: Missing hierarchy

Check document format is recognized:
```python
from improved_processor import DocumentParser

parser = DocumentParser()
doc_type = parser.detect_document_type(content, filename)
print(f"Detected as: {doc_type}")  # Should not be UNKNOWN
```

## Next Steps

1. **Run on your data**: Process all 12 source documents
2. **Compare quality**: Before/after metrics
3. **Test retrieval**: Use Golden Questions to measure hit rate
4. **Iterate**: Adjust patterns for any edge cases

## Files Created

- `improved_processor.py` - Main pipeline module
- `USAGE_GUIDE.md` - This documentation
- `test_pipeline.py` - Validation tests
