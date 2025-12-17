"""
Metadata Schema for Multi-State Regulatory Chatbot
==================================================

This schema ensures federal regulations are processed ONCE and shared
across all states, while state-specific regulations are tagged appropriately.

Key Fields:
- jurisdiction_type: "federal" or "state"
- jurisdiction: Specific state name OR "All" for federal
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class JurisdictionType(Enum):
    """Federal applies to all states; State is state-specific."""
    FEDERAL = "federal"
    STATE = "state"


class DocumentCategory(Enum):
    """High-level document categories."""
    REGULATION = "regulation"           # Enforceable rules (IDAPA, WAC, CFR)
    STATUTE = "statute"                 # Laws (Idaho Code, RCW)
    GUIDANCE = "guidance"               # Non-binding guidance documents
    CODE = "code"                       # Technical codes (Food Code, Building Code)
    STANDARD = "standard"               # Standards (ADA Guidelines)


# =============================================================================
# FEDERAL DOCUMENT REGISTRY
# =============================================================================

# These documents are processed ONCE and tagged with jurisdiction="All"
# When adding a new state, these are SKIPPED (already processed)

FEDERAL_DOCUMENTS = {
    # FDA Food Code
    "US Public Health Food Code.txt": {
        "jurisdiction_type": JurisdictionType.FEDERAL,
        "jurisdiction": "All",
        "document_category": DocumentCategory.CODE,
        "source_agency": "FDA",
        "applies_to": ["ALF", "SNF", "All"],
        "description": "Food safety requirements for food service establishments",
    },

    # ADA Guidelines
    "ADA Accessibility Guidelines for Buildings and Facilities.txt": {
        "jurisdiction_type": JurisdictionType.FEDERAL,
        "jurisdiction": "All",
        "document_category": DocumentCategory.STANDARD,
        "source_agency": "DOJ",
        "applies_to": ["ALF", "SNF", "All"],
        "description": "Accessibility requirements for buildings and facilities",
    },

    # Add future federal documents here:
    # "42 CFR Part 483.txt": {
    #     "jurisdiction_type": JurisdictionType.FEDERAL,
    #     "jurisdiction": "All",
    #     "document_category": DocumentCategory.REGULATION,
    #     "source_agency": "CMS",
    #     "applies_to": ["SNF"],
    #     "description": "Requirements for Long Term Care Facilities",
    # },
}


# =============================================================================
# STATE DOCUMENT REGISTRY
# =============================================================================

# Each state has its own document registry
# Add new states as dictionary entries

STATE_DOCUMENTS = {
    "Idaho": {
        "IDAPA 16.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Idaho",
            "document_category": DocumentCategory.REGULATION,
            "source_agency": "IDHW",
            "applies_to": ["ALF"],
            "description": "Idaho Residential Care/Assisted Living Facility Rules",
        },
        "IDAPA 16.02.19 food code.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Idaho",
            "document_category": DocumentCategory.CODE,
            "source_agency": "IDHW",
            "applies_to": ["ALF", "SNF", "All"],
            "description": "Idaho Food Code (state adoption of FDA code)",
        },
        "IDAPA 16.05.01 use and disclosure of department records.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Idaho",
            "document_category": DocumentCategory.REGULATION,
            "source_agency": "IDHW",
            "applies_to": ["All"],
            "description": "Records disclosure requirements",
        },
        "IDAPA 16.05.06 criminal history background checks.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Idaho",
            "document_category": DocumentCategory.REGULATION,
            "source_agency": "IDHW",
            "applies_to": ["ALF", "SNF", "All"],
            "description": "Background check requirements for caregivers",
        },
        "IDAPA 16.02.10 Idaho Reportable Diseases.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Idaho",
            "document_category": DocumentCategory.REGULATION,
            "source_agency": "IDHW",
            "applies_to": ["All"],
            "description": "Disease reporting requirements",
        },
        "IDAPA 24.34.01 idaho board of nursing.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Idaho",
            "document_category": DocumentCategory.REGULATION,
            "source_agency": "Idaho Board of Nursing",
            "applies_to": ["ALF", "SNF"],
            "description": "Nursing licensure and practice rules",
        },
        "IDAPA 24.39.30 rules of building safety.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Idaho",
            "document_category": DocumentCategory.REGULATION,
            "source_agency": "DBS",
            "applies_to": ["All"],
            "description": "Building safety requirements",
        },
        "TITLE 39 - Chapter 33 Idaho Residential Care or Assisted Living Act.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Idaho",
            "document_category": DocumentCategory.STATUTE,
            "source_agency": "Idaho Legislature",
            "applies_to": ["ALF"],
            "description": "Idaho's assisted living enabling statute",
        },
        "Title 74 Transparent and Ethical Government - Chapter 1 Public Records Act.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Idaho",
            "document_category": DocumentCategory.STATUTE,
            "source_agency": "Idaho Legislature",
            "applies_to": ["All"],
            "description": "Public records requirements",
        },
    },

    # Add new states here:
    # "Washington": {
    #     "WAC 388-78A.txt": {...},
    # },
}


# =============================================================================
# CHUNK METADATA SCHEMA
# =============================================================================

@dataclass
class ChunkMetadata:
    """
    Complete metadata schema for a chunk.

    This ensures consistent tagging across all documents and states.
    """

    # === IDENTIFICATION ===
    chunk_id: str                           # Unique identifier
    source_document: str                    # Original filename

    # === JURISDICTION (Critical for multi-state) ===
    jurisdiction_type: str                  # "federal" or "state"
    jurisdiction: str                       # State name OR "All" for federal

    # === DOCUMENT INFO ===
    document_category: str                  # regulation, statute, guidance, code, standard
    source_agency: str                      # IDHW, FDA, CMS, etc.
    effective_date: Optional[str]           # YYYY-MM-DD format

    # === HIERARCHY ===
    section_number: str
    section_title: str
    parent_chunk_id: Optional[str]
    child_chunk_ids: List[str]
    position_in_section: int                # e.g., 1 of 3
    total_in_section: int

    # === CLASSIFICATION ===
    category: str                           # staffing, medications, etc.
    topic_tags: List[str]                   # Multiple topics
    facility_types: List[str]               # ALF, SNF, Memory Care, All

    # === QUALITY TRACKING ===
    word_count: int
    has_complete_lists: bool
    semantic_boundary: str                  # section_end, paragraph_end, sentence_end

    # === CITATION ===
    citation: str                           # Full citation string

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "chunk_id": self.chunk_id,
            "source_document": self.source_document,
            "jurisdiction_type": self.jurisdiction_type,
            "jurisdiction": self.jurisdiction,
            "document_category": self.document_category,
            "source_agency": self.source_agency,
            "effective_date": self.effective_date,
            "section_number": self.section_number,
            "section_title": self.section_title,
            "parent_chunk_id": self.parent_chunk_id,
            "child_chunk_ids": self.child_chunk_ids,
            "position_in_section": self.position_in_section,
            "total_in_section": self.total_in_section,
            "category": self.category,
            "topic_tags": self.topic_tags,
            "facility_types": self.facility_types,
            "word_count": self.word_count,
            "has_complete_lists": self.has_complete_lists,
            "semantic_boundary": self.semantic_boundary,
            "citation": self.citation,
        }


# =============================================================================
# RETRIEVAL QUERY HELPERS
# =============================================================================

def get_jurisdiction_filter(state: str) -> Dict:
    """
    Get the filter for retrieving chunks relevant to a specific state.

    Returns chunks where:
    - jurisdiction = state_name (state-specific)
    - OR jurisdiction = "All" (federal, applies everywhere)

    Usage in vector DB query:
        filter = get_jurisdiction_filter("Idaho")
        results = vector_db.query(embedding, filter=filter)
    """
    return {
        "$or": [
            {"jurisdiction": state},
            {"jurisdiction": "All"}
        ]
    }


def get_facility_filter(facility_type: str, state: str) -> Dict:
    """
    Get filter for a specific facility type in a specific state.

    Usage:
        filter = get_facility_filter("ALF", "Idaho")
    """
    return {
        "$and": [
            {
                "$or": [
                    {"jurisdiction": state},
                    {"jurisdiction": "All"}
                ]
            },
            {
                "$or": [
                    {"facility_types": {"$in": [facility_type]}},
                    {"facility_types": {"$in": ["All"]}}
                ]
            }
        ]
    }


# =============================================================================
# PROCESSING HELPERS
# =============================================================================

def is_federal_document(filename: str) -> bool:
    """Check if a document is federal (should be processed once, shared across states)."""
    return filename in FEDERAL_DOCUMENTS


def get_document_metadata(filename: str, state: str = None) -> Optional[Dict]:
    """
    Get pre-defined metadata for a document.

    Checks federal docs first, then state-specific.
    """
    # Check federal documents
    if filename in FEDERAL_DOCUMENTS:
        return FEDERAL_DOCUMENTS[filename]

    # Check state documents
    if state and state in STATE_DOCUMENTS:
        if filename in STATE_DOCUMENTS[state]:
            return STATE_DOCUMENTS[state][filename]

    # Check all states if no specific state provided
    for state_name, docs in STATE_DOCUMENTS.items():
        if filename in docs:
            return docs[filename]

    return None


def get_documents_for_state(state: str) -> List[str]:
    """Get list of state-specific documents to process for a state."""
    if state in STATE_DOCUMENTS:
        return list(STATE_DOCUMENTS[state].keys())
    return []


def get_all_federal_documents() -> List[str]:
    """Get list of all federal documents."""
    return list(FEDERAL_DOCUMENTS.keys())


# =============================================================================
# NEW STATE SETUP
# =============================================================================

def get_new_state_checklist(state: str) -> str:
    """Generate a checklist for adding a new state."""
    return f"""
    Adding {state} to the Regulatory Chatbot
    =========================================

    [ ] 1. Collect {state} regulatory documents
    [ ] 2. Add document entries to STATE_DOCUMENTS["{state}"]
    [ ] 3. Add state config to state_configs.py
    [ ] 4. Process ONLY {state} documents (federal already done)
    [ ] 5. Verify jurisdiction tags are correct
    [ ] 6. Test retrieval with {state}-specific queries
    [ ] 7. Test that federal docs are included in {state} results

    Documents to process:
    - State regulations (administrative code)
    - State statutes (laws)
    - State-specific guidance

    Documents to SKIP (already processed):
    - FDA Food Code
    - ADA Guidelines
    - CMS Federal Regulations
    """


if __name__ == "__main__":
    print("Federal Documents (process once, shared across all states):")
    for doc in get_all_federal_documents():
        print(f"  - {doc}")

    print("\nState Documents:")
    for state, docs in STATE_DOCUMENTS.items():
        print(f"\n  {state}:")
        for doc in docs:
            print(f"    - {doc}")

    print("\nSample filter for Idaho query:")
    print(f"  {get_jurisdiction_filter('Idaho')}")

    print("\nSample filter for Idaho ALF query:")
    print(f"  {get_facility_filter('ALF', 'Idaho')}")
