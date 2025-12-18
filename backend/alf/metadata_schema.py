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

    "Washington": {
        "WA Chapter 388-78A WAC_.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Washington",
            "document_category": DocumentCategory.REGULATION,
            "source_agency": "DSHS",
            "applies_to": ["ALF"],
            "description": "Washington ALF Licensing Rules (main document)",
        },
        "WA Chapter 388-112A WAC_.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Washington",
            "document_category": DocumentCategory.REGULATION,
            "source_agency": "DSHS",
            "applies_to": ["ALF", "SNF"],
            "description": "Long-term care services training requirements",
        },
        "WA Chapter 246-338 WAC_.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Washington",
            "document_category": DocumentCategory.REGULATION,
            "source_agency": "WA DOH",
            "applies_to": ["ALF", "SNF"],
            "description": "Medical Test Site rules (WA CLIA alternative)",
        },
        "WA WAC 246-840-910_.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Washington",
            "document_category": DocumentCategory.REGULATION,
            "source_agency": "WA DOH",
            "applies_to": ["ALF", "SNF"],
            "description": "RN delegation authority (includes insulin)",
        },
        "WA WAC 296-128-245_.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Washington",
            "document_category": DocumentCategory.REGULATION,
            "source_agency": "L&I",
            "applies_to": ["ALF"],
            "description": "Sleep time rules (5-hour uninterrupted)",
        },
        "WA Chapter 18.20 RCW_ ASSISTED LIVING FACILITIES.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Washington",
            "document_category": DocumentCategory.STATUTE,
            "source_agency": "WA Legislature",
            "applies_to": ["ALF"],
            "description": "Washington ALF enabling statute",
        },
        "WA Chapter 70.129 RCW_ LONG-TERM CARE RESIDENT RIGHTS.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Washington",
            "document_category": DocumentCategory.STATUTE,
            "source_agency": "WA Legislature",
            "applies_to": ["ALF", "SNF"],
            "description": "Long-term care resident rights",
        },
        "WA Chapter 74.34 RCW_ ABUSE OF VULNERABLE ADULTS.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Washington",
            "document_category": DocumentCategory.STATUTE,
            "source_agency": "WA Legislature",
            "applies_to": ["ALF", "SNF", "All"],
            "description": "Abuse of vulnerable adults reporting and protection",
        },
        "WA Title 246 WAC_.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Washington",
            "document_category": DocumentCategory.REGULATION,
            "source_agency": "WA DOH",
            "applies_to": ["All"],
            "description": "WA Department of Health rules (multiple chapters)",
        },
    },

    "Oregon": {
        "OR 411-054.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Oregon",
            "document_category": DocumentCategory.REGULATION,
            "source_agency": "ODHS",
            "applies_to": ["ALF"],
            "description": "Oregon ALF Licensing Rules (OAR 411-054)",
        },
        "OR Oregon Secretary of State Administrative Rules.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Oregon",
            "document_category": DocumentCategory.REGULATION,
            "source_agency": "ODHS",
            "applies_to": ["ALF"],
            "description": "Memory Care Communities endorsement (OAR 411-057)",
        },
        "OR Human Services Oregon Secretary of State Administrative Rules.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Oregon",
            "document_category": DocumentCategory.REGULATION,
            "source_agency": "ODHS",
            "applies_to": ["ALF", "SNF", "All"],
            "description": "Criminal history and abuse checks (OAR 407-007)",
        },
        "OR Sleep Timing Oregon Secretary of State Administrative Rules.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Oregon",
            "document_category": DocumentCategory.REGULATION,
            "source_agency": "BOLI",
            "applies_to": ["ALF"],
            "description": "Sleep time and working conditions rules (OAR 839-020)",
        },
        "OR foodsanitationrulesweb.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Oregon",
            "document_category": DocumentCategory.CODE,
            "source_agency": "OHA",
            "applies_to": ["ALF", "SNF", "All"],
            "description": "Oregon Food Sanitation Rules",
        },
        "OR ors443.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Oregon",
            "document_category": DocumentCategory.STATUTE,
            "source_agency": "OR Legislature",
            "applies_to": ["ALF"],
            "description": "Oregon Residential Care enabling statute (ORS 443)",
        },
        "OR ors678.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Oregon",
            "document_category": DocumentCategory.STATUTE,
            "source_agency": "OR Legislature",
            "applies_to": ["ALF", "SNF"],
            "description": "Nurses and Long Term Care Administrators (ORS 678)",
        },
    },

    "Arizona": {
        # Administrative Code (AAC) - Main regulatory document
        "AZ article-8.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Arizona",
            "document_category": DocumentCategory.REGULATION,
            "source_agency": "ADHS",
            "applies_to": ["ALF"],
            "description": "Arizona ALF Licensing Rules (A.A.C. Title 9, Ch 10, Article 8)",
        },
        "AZ 9-10.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Arizona",
            "document_category": DocumentCategory.REGULATION,
            "source_agency": "ADHS",
            "applies_to": ["ALF", "SNF"],
            "description": "ADHS Health Care Institutions Licensing (A.A.C. Title 9, Ch 10)",
        },
        "AZ 9-08.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Arizona",
            "document_category": DocumentCategory.REGULATION,
            "source_agency": "ADHS",
            "applies_to": ["All"],
            "description": "ADHS Food, Recreational, and Institutional Sanitation (A.A.C. Title 9, Ch 8)",
        },
        "AZ 4-33.txt": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Arizona",
            "document_category": DocumentCategory.REGULATION,
            "source_agency": "NCIA Board",
            "applies_to": ["ALF", "SNF"],
            "description": "Manager & Caregiver Certification (A.A.C. Title 4, Ch 33)",
        },
        # Statutes (ARS) - HTML files
        "AZ 36-401 - Definitions_ adult foster care.html": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Arizona",
            "document_category": DocumentCategory.STATUTE,
            "source_agency": "AZ Legislature",
            "applies_to": ["ALF"],
            "description": "Health Care Institutions Definitions (A.R.S. § 36-401)",
        },
        "AZ 36-405 - Powers and duties of the director.html": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Arizona",
            "document_category": DocumentCategory.STATUTE,
            "source_agency": "AZ Legislature",
            "applies_to": ["ALF", "SNF"],
            "description": "Director Powers and Duties (A.R.S. § 36-405)",
        },
        "AZ 36-411 - Residential care institutions_ nursing care institutions_ home health agencies_ fingerprinting requirements_ exemptions_ definitions.html": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Arizona",
            "document_category": DocumentCategory.STATUTE,
            "source_agency": "AZ Legislature",
            "applies_to": ["ALF", "SNF"],
            "description": "Background Check Requirements (A.R.S. § 36-411)",
        },
        "AZ 36-446 - Definitions.html": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Arizona",
            "document_category": DocumentCategory.STATUTE,
            "source_agency": "AZ Legislature",
            "applies_to": ["ALF", "SNF"],
            "description": "Administrator/Manager Certification Definitions (A.R.S. § 36-446)",
        },
        "AZ 36-446.04 - Qualifications_ period of validity_ exemption.html": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Arizona",
            "document_category": DocumentCategory.STATUTE,
            "source_agency": "AZ Legislature",
            "applies_to": ["ALF", "SNF"],
            "description": "Manager Qualification Requirements (A.R.S. § 36-446.04)",
        },
        "AZ 36-446.07 - Disciplinary actions_ grounds for disciplinary action_ renewal_ continuing education_ inactive status_ hearings_ settlement_ judicial review_ admission by default_ military members.html": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Arizona",
            "document_category": DocumentCategory.STATUTE,
            "source_agency": "AZ Legislature",
            "applies_to": ["ALF", "SNF"],
            "description": "Manager Disciplinary Actions (A.R.S. § 36-446.07)",
        },
        "AZ 36-446.14 - Referral agencies_ assisted living facilities and assisted living homes_ disclosure_ acknowledgement_ fee_ notice_ requirements_ civil penalty_ definitions.html": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Arizona",
            "document_category": DocumentCategory.STATUTE,
            "source_agency": "AZ Legislature",
            "applies_to": ["ALF"],
            "description": "Referral Agency Requirements (A.R.S. § 36-446.14)",
        },
        "AZ 36-446.15 - Assisted living facility caregivers_ training and competency requirements_ medication administration_ testing.html": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Arizona",
            "document_category": DocumentCategory.STATUTE,
            "source_agency": "AZ Legislature",
            "applies_to": ["ALF"],
            "description": "Caregiver Training Requirements (A.R.S. § 36-446.15)",
        },
        "AZ 36-446.16 - Assisted living facility caregivers_ training requirements_ board standards_ definition.html": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Arizona",
            "document_category": DocumentCategory.STATUTE,
            "source_agency": "AZ Legislature",
            "applies_to": ["ALF"],
            "description": "Caregiver Training Board Standards (A.R.S. § 36-446.16)",
        },
        "AZ 36-450 - Definitions.html": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Arizona",
            "document_category": DocumentCategory.STATUTE,
            "source_agency": "AZ Legislature",
            "applies_to": ["ALF", "SNF"],
            "description": "Reporting Procedures Definitions (A.R.S. § 36-450)",
        },
        "AZ 36-450.02 - Nonretaliatory policy_ definition.html": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Arizona",
            "document_category": DocumentCategory.STATUTE,
            "source_agency": "AZ Legislature",
            "applies_to": ["ALF", "SNF"],
            "description": "Whistleblower Non-retaliation (A.R.S. § 36-450.02)",
        },
        "AZ 46-451 - Definitions_ program goals.html": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Arizona",
            "document_category": DocumentCategory.STATUTE,
            "source_agency": "AZ Legislature",
            "applies_to": ["ALF", "SNF", "All"],
            "description": "Adult Protective Services Definitions (A.R.S. § 46-451)",
        },
        "AZ 46-454 - Duty to report abuse, neglect and exploitation of vulnerable adults_ duty to make medical records available_ violation_ classification.html": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Arizona",
            "document_category": DocumentCategory.STATUTE,
            "source_agency": "AZ Legislature",
            "applies_to": ["ALF", "SNF", "All"],
            "description": "Mandatory Abuse Reporting (A.R.S. § 46-454)",
        },
        "AZ 46-459 - Adult protective services registry.html": {
            "jurisdiction_type": JurisdictionType.STATE,
            "jurisdiction": "Arizona",
            "document_category": DocumentCategory.STATUTE,
            "source_agency": "AZ Legislature",
            "applies_to": ["ALF", "SNF", "All"],
            "description": "APS Registry (A.R.S. § 46-459)",
        },
    },
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
