# Adding New States to the Regulatory Chatbot

## Overview

This guide walks through adding a new state's regulations to the chatbot. The core processing methodology (semantic chunking, list preservation, 400-800 word targets) stays the same—you just need to teach the parser to recognize the new state's document format.

---

## What Stays the Same (Federal Documents)

These documents work for ALL states without modification:
- FDA Food Code
- ADA Accessibility Guidelines
- CMS Federal Regulations (42 CFR)

---

## What Needs Configuration Per State

| Component | Why It's Different |
|-----------|-------------------|
| Section header patterns | Each state formats regulations differently (e.g., Idaho uses "100. TITLE." vs Washington uses "WAC 388-78A-2010") |
| Document type detection | Filename and content patterns to identify state docs |
| Jurisdiction tagging | Tag chunks with correct state name |
| Agency abbreviations | State-specific agencies (IDHW, DSHS, OHA, etc.) |
| Citation format | How regulations are cited in that state |

---

## Step-by-Step Process

### Step 1: Gather Source Documents

Collect the state's regulatory documents:
- Administrative code (regulations with detailed requirements)
- State statutes (laws governing facilities)
- Any state-specific guidance documents

Place them in: `backend/alf/data/raw/`

### Step 2: Analyze Document Format

Open a sample document and identify:

1. **Section header pattern** - How are sections numbered?
   - Idaho IDAPA: `100. LICENSING REQUIREMENTS.`
   - Washington WAC: `WAC 388-78A-2010 Definitions.`
   - Oregon OAR: `OAR 411-054-0010 Purpose`

2. **Subsection pattern** - How are subsections numbered?
   - Idaho: `01. General Requirements`
   - Washington: `(1) Subsection text`

3. **List item pattern** - Usually standard: `(a)`, `(1)`, `a.`, etc.

4. **Citation format** - How does the state reference its own regulations?

### Step 3: Update state_configs.py

Add a new StateConfig entry:

```python
NEWSTATE_CONFIG = StateConfig(
    state_name="New State",
    state_abbrev="NS",

    filename_patterns=[
        r'nac',           # State admin code abbreviation
        r'newstate',
    ],

    content_patterns=[
        r'NAC\s+\d+',     # Pattern in content
        r'New\s+State\s+Department',
    ],

    section_patterns={
        'level_1': r'^NAC\s+(\d+-\d+)\s+(.+?)\.?\s*$',
        'level_2': r'^\((\d+)\)\s+',
        'level_3': r'^\(([a-z])\)\s+',
    },

    agency_mappings={
        'New State Department of Health': 'NSDH',
    },

    citation_pattern=r'NAC\s+(\d+-\d+)',
)

# Add to STATE_CONFIGS dictionary:
STATE_CONFIGS['newstate'] = NEWSTATE_CONFIG
```

### Step 4: Test the Configuration

```bash
cd backend/alf
python3 test_pipeline.py
```

All 6 tests should still pass.

### Step 5: Process New Documents

```bash
python3 -c "
from improved_processor import RegulatoryDataPipeline, print_quality_report

pipeline = RegulatoryDataPipeline()
chunks, report = pipeline.process_directory(
    'data/raw/',
    'data/processed/chunks_v2.json'
)
print_quality_report(report)
"
```

### Step 6: Regenerate Embeddings

```bash
# Your embedding generation script
python3 generate_embeddings.py
```

### Step 7: Test Retrieval

Run test queries specific to the new state's content to verify retrieval works.

---

## Claude Code Prompt for Adding New States

Copy this prompt when you're ready to add a new state:

```
I'm adding [STATE NAME] regulations to the chatbot.

1. Look at the raw regulation files I've added to data/raw/
2. Identify the section header patterns (how are sections numbered?)
3. Update state_configs.py to add a new StateConfig for [STATE NAME]:
   - Document detection patterns (filename and content)
   - Section header patterns (level_1, level_2, level_3)
   - Agency abbreviation mappings
   - Citation format pattern

4. Update improved_processor.py to import and use the new config

5. Run test_pipeline.py to make sure existing tests still pass

6. Process all documents (old + new) and show me:
   - Total chunk count
   - Quality metrics (% in 400-800 word range)
   - Breakdown by jurisdiction

7. Regenerate embeddings for the updated chunks
```

---

## Common State Regulation Formats

### Washington (WAC - Washington Administrative Code)
```
Pattern: WAC 388-78A-2010
Format: WAC [chapter]-[section]-[subsection]
Example: WAC 388-78A-2010 Definitions.
```

### Oregon (OAR - Oregon Administrative Rules)
```
Pattern: OAR 411-054-0010
Format: OAR [chapter]-[division]-[rule]
Example: OAR 411-054-0010 Purpose and Scope.
```

### California (CCR - California Code of Regulations)
```
Pattern: 22 CCR § 87101
Format: [title] CCR § [section]
Example: 22 CCR § 87101 Definitions.
```

### Texas (TAC - Texas Administrative Code)
```
Pattern: 26 TAC § 553.1
Format: [title] TAC § [chapter].[section]
Example: 26 TAC § 553.1 Purpose.
```

### Florida (FAC - Florida Administrative Code)
```
Pattern: 59A-36.001
Format: [chapter]-[part].[section]
Example: 59A-36.001 Definitions.
```

---

## Checklist for New State

- [ ] Source documents collected in `data/raw/`
- [ ] Section header patterns identified
- [ ] StateConfig added to `state_configs.py`
- [ ] `improved_processor.py` updated to use new config
- [ ] `test_pipeline.py` passes (6/6)
- [ ] Documents processed with quality report reviewed
- [ ] Embeddings regenerated
- [ ] Test queries return correct results for new state
- [ ] Jurisdiction filter works in UI (if applicable)

---

## Troubleshooting

### Chunks are too small for new state
The section patterns might be too granular. Try:
- Combining level_2 and level_3 patterns
- Adjusting MIN_CHUNK_WORDS in ChunkConfig

### Wrong jurisdiction being tagged
Check that content_patterns are specific enough to distinguish from other states.

### Lists being split
The list patterns in SemanticChunker should work universally, but if the new state uses unusual list formatting, add patterns to LIST_PATTERNS.

### Low retrieval accuracy
Run the 5-query test and check:
- Are the right documents being retrieved?
- Is the jurisdiction filter working?
- Are chunks semantically complete?
