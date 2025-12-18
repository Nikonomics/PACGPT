"""
State Configuration Module
==========================

Add new states by creating a new StateConfig entry.
The processor will automatically detect and handle documents from any configured state.

To add a new state:
1. Examine sample documents to identify section header patterns
2. Copy an existing config and modify patterns
3. Add to STATE_CONFIGS dictionary
4. Run tests to verify
"""

from dataclasses import dataclass, field
from typing import Dict, List, Pattern
import re


@dataclass
class StateConfig:
    """Configuration for a state's regulatory document format."""

    # State identification
    state_name: str
    state_abbrev: str

    # Document detection - patterns that identify this state's docs
    filename_patterns: List[str]  # Patterns to match in filename
    content_patterns: List[str]   # Patterns to match in content

    # Section header patterns by hierarchy level
    # level_1 = main sections, level_2 = subsections, etc.
    section_patterns: Dict[str, str]

    # Agency normalization (state-specific terms -> standard abbreviation)
    agency_mappings: Dict[str, str] = field(default_factory=dict)

    # Citation format pattern (for extraction)
    citation_pattern: str = ""

    def compile_patterns(self) -> Dict[str, Pattern]:
        """Compile regex patterns for performance."""
        return {
            level: re.compile(pattern)
            for level, pattern in self.section_patterns.items()
        }


# =============================================================================
# STATE CONFIGURATIONS
# =============================================================================

IDAHO_CONFIG = StateConfig(
    state_name="Idaho",
    state_abbrev="ID",

    filename_patterns=[
        r'idapa',
        r'idaho',
        r'title\s*39',
        r'title\s*74',
    ],

    content_patterns=[
        r'IDAPA\s+\d+',
        r'Idaho\s+Code',
        r'Idaho\s+Department',
    ],

    section_patterns={
        'level_1': r'^(\d{3})\.\s+([A-Z][A-Z\s\-,&()]+)\.',      # 100. LICENSING.
        'level_2': r'^(\d{2})\.\s+([A-Z][A-Za-z\s\-,&()]+)',     # 01. General Requirements
        'level_3': r'^([a-z])\.\s+',                              # a. Specific item
    },

    agency_mappings={
        'Idaho Department of Health and Welfare': 'IDHW',
        'Idaho Department of Health & Welfare': 'IDHW',
        'State of Idaho': 'Idaho',
        'Board of Health and Welfare': 'IDHW Board',
    },

    citation_pattern=r'IDAPA\s+(\d+\.\d+\.\d+)',
)


IDAHO_CODE_CONFIG = StateConfig(
    state_name="Idaho",
    state_abbrev="ID",

    filename_patterns=[
        r'title\s*39',           # Idaho Title 39 (Health and Safety)
        r'title\s*74',           # Idaho Title 74 (Transparent Government)
        r'idaho.*chapter',       # Idaho + chapter
    ],

    content_patterns=[
        r'^\d{2}-\d{4}\.',           # Idaho Code section format (e.g., 39-3301.)
        r'Idaho\s+Code',             # Explicit "Idaho Code" reference
        r'I\.C\.\s+§',               # Idaho Code citation format
    ],

    section_patterns={
        'level_1': r'^(\d{2}-\d{4})\.\s+([A-Z][A-Z\s\-,&()]+)',  # 39-3301. DEFINITIONS
        'level_2': r'^\((\d+)\)\s+',                              # (1) Subsection
    },

    agency_mappings={
        'Idaho Department of Health and Welfare': 'IDHW',
    },

    citation_pattern=r'(?:Idaho\s+Code|I\.C\.)\s+§?\s*(\d+-\d+)',
)


# =============================================================================
# EXAMPLE: ADDING A NEW STATE (WASHINGTON)
# =============================================================================

WASHINGTON_CONFIG = StateConfig(
    state_name="Washington",
    state_abbrev="WA",

    filename_patterns=[
        r'WA\s',          # Files starting with "WA "
        r'wac',           # Washington Administrative Code
        r'rcw',           # Revised Code of Washington
        r'washington',
    ],

    content_patterns=[
        r'WAC\s+\d+',
        r'RCW\s+\d+',
        r'\d+-\d+[A-Z]?-\d+',  # WAC section numbers like 388-78A-2010
        r'Washington\s+State',
        r'Department\s+of\s+Social\s+and\s+Health\s+Services',
        r'DSHS',
        r'ALTSA',
    ],

    section_patterns={
        # WAC format: 388-78A-2010Purpose. OR WAC 246-840-910Purpose. OR 388-112A-0010What...?
        # Handles: with/without WAC prefix, titles ending in . or ?
        'level_1': r'^(?:WAC\s+)?(\d+-\d+[A-Z]?-\d+)([A-Z][A-Za-z\s\-,—\'?]+)[.?]',
        # RCW format: RCW 18.20.010 or 18.20.010
        'level_2': r'^(?:RCW\s+)?(\d+\.\d+\.\d+)\s*([A-Z][A-Za-z\s\-,—\']+)',
        'level_3': r'^\((\d+)\)\s+',
    },

    agency_mappings={
        'Department of Social and Health Services': 'DSHS',
        'Washington State Department of Health': 'WA DOH',
        'Department of Health': 'WA DOH',
        'State of Washington': 'Washington',
        'Aging and Long-Term Support Administration': 'ALTSA',
        'Residential Care Services': 'RCS',
        'Department of Labor and Industries': 'L&I',
    },

    citation_pattern=r'WAC\s+(\d+-\d+[A-Z]?-\d+)|RCW\s+(\d+\.\d+\.\d+)',
)


# =============================================================================
# EXAMPLE: ADDING ANOTHER STATE (OREGON)
# =============================================================================

OREGON_CONFIG = StateConfig(
    state_name="Oregon",
    state_abbrev="OR",

    filename_patterns=[
        r'^OR\s',         # Files starting with "OR "
        r'oar',           # Oregon Administrative Rules
        r'ors',           # Oregon Revised Statutes
        r'oregon',
    ],

    content_patterns=[
        r'\d{3}-\d{3}-\d{4}',     # OAR section format (407-007-0000)
        r'OAR\s+\d+',
        r'ORS\s+\d+',
        r'Oregon\s+Health\s+Authority',
        r'Oregon\s+Department\s+of\s+Human\s+Services',
        r'ODHS',
        r'OHA',
    ],

    section_patterns={
        # OAR format: 407-007-0000Purpose and Scope or just 407-007-0000 on its own line
        # Handles: with/without OAR prefix, title may be on same or next line
        'level_1': r'^(?:OAR\s+)?(\d{3}-\d{3}-\d{4})([A-Z][A-Za-z\s\-,;()\'\&\.]+)?',
        # ORS format: 443.001 or ORS 443.001
        'level_2': r'^(?:ORS\s+)?(\d{3}\.\d{3})\s*([A-Z][A-Za-z\s\-,;()\']+)?',
        'level_3': r'^\((\d+)\)\s+',
    },

    agency_mappings={
        'Oregon Health Authority': 'OHA',
        'Oregon Department of Human Services': 'ODHS',
        'Department of Human Services': 'ODHS',
        'State of Oregon': 'Oregon',
        'Bureau of Labor and Industries': 'BOLI',
    },

    citation_pattern=r'OAR\s+(\d{3}-\d{3}-\d{4})|ORS\s+(\d{3}\.\d{3})',
)


# =============================================================================
# ARIZONA CONFIGURATION
# =============================================================================

ARIZONA_CONFIG = StateConfig(
    state_name="Arizona",
    state_abbrev="AZ",

    filename_patterns=[
        r'^AZ\s',         # Files starting with "AZ "
        r'arizona',
        r'a\.a\.c',       # Arizona Administrative Code
        r'a\.r\.s',       # Arizona Revised Statutes
    ],

    content_patterns=[
        r'R\d+-\d+-\d+',              # AAC section format (R9-10-801)
        r'A\.A\.C\.',                 # Arizona Administrative Code
        r'A\.R\.S\.',                 # Arizona Revised Statutes
        r'\d{2}-\d{3,4}',             # ARS section format (36-401)
        r'Arizona\s+Department\s+of\s+Health',
        r'ADHS',
        r'Arizona\s+Revised\s+Statutes',
    ],

    section_patterns={
        # AAC format: R9-10-801 Definitions or R9-10-801.Definitions
        'level_1': r'^R(\d+-\d+-\d+)\.?\s*([A-Z][A-Za-z\s\-,;()\'\&]+)?',
        # ARS format: 36-401. or 36-446.04.
        'level_2': r'^(\d{2}-\d{3,4}(?:\.\d{2})?)\.?\s*([A-Z][A-Za-z\s\-,;()\']+)?',
        # Subsection: A. B. C. or 1. 2. 3. or (a) (b) (c)
        'level_3': r'^([A-Z])\.\s+|^(\d+)\.\s+|^\(([a-z])\)\s+',
    },

    agency_mappings={
        'Arizona Department of Health Services': 'ADHS',
        'Department of Health Services': 'ADHS',
        'Board of Examiners of Nursing Care Institution Administrators and Assisted Living Facility Managers': 'NCIA Board',
        'State of Arizona': 'Arizona',
        'Arizona Health Care Cost Containment System': 'AHCCCS',
        'Adult Protective Services': 'APS',
    },

    citation_pattern=r'R(\d+-\d+-\d+)|A\.R\.S\.\s*§?\s*(\d+-\d+)',
)


# =============================================================================
# FEDERAL CONFIGURATIONS (Apply to all states)
# =============================================================================

FDA_FOOD_CODE_CONFIG = StateConfig(
    state_name="Federal",
    state_abbrev="US",

    filename_patterns=[
        r'food\s*code',
        r'fda',
        r'public\s*health',
    ],

    content_patterns=[
        r'^\d-\d{3}\.\d{2}',
        r'Food\s+Code',
        r'FDA',
    ],

    section_patterns={
        'level_1': r'^(\d-\d{3}\.\d{2})\s+([A-Z][A-Za-z\s\-,]+)',  # 3-201.11 Temperature
        'level_2': r'^\(([A-Z])\)\s+',                              # (A) Subsection
    },

    agency_mappings={
        'Food and Drug Administration': 'FDA',
        'U.S. Public Health Service': 'USPHS',
    },

    citation_pattern=r'Food\s+Code\s+§?\s*(\d-\d{3}\.\d{2})',
)


ADA_CONFIG = StateConfig(
    state_name="Federal",
    state_abbrev="US",

    filename_patterns=[
        r'ada',
        r'accessibility',
        r'disabilities',
    ],

    content_patterns=[
        r'ADA',
        r'Americans\s+with\s+Disabilities',
        r'Accessibility\s+Guidelines',
        r'^\d\.\d+\.\d+',
    ],

    section_patterns={
        'level_1': r'^(\d\.\d+)\s+([A-Z][A-Za-z\s]+)',            # 4.1 Application
        'level_2': r'^(\d\.\d+\.\d+)\s+([A-Za-z\s]+)',            # 4.1.1 Buildings
        'level_3': r'^\((\d+)\)\s+',
    },

    agency_mappings={
        'Department of Justice': 'DOJ',
        'Access Board': 'USAB',
    },

    citation_pattern=r'ADA\s+(?:§|Section)?\s*(\d+\.\d+)',
)


CMS_CONFIG = StateConfig(
    state_name="Federal",
    state_abbrev="US",

    filename_patterns=[
        r'cms',
        r'42\s*cfr',
        r'medicare',
        r'medicaid',
    ],

    content_patterns=[
        r'42\s+CFR',
        r'CMS',
        r'Centers\s+for\s+Medicare',
        r'§\s*483',
    ],

    section_patterns={
        'level_1': r'^§?\s*(\d{3}\.\d+)\s+(.+?)\.?\s*$',          # § 483.10 Resident Rights
        'level_2': r'^\(([a-z])\)\s+',                            # (a) Subsection
        'level_3': r'^\((\d+)\)\s+',                              # (1) Sub-subsection
    },

    agency_mappings={
        'Centers for Medicare & Medicaid Services': 'CMS',
        'Centers for Medicare and Medicaid Services': 'CMS',
        'Department of Health and Human Services': 'HHS',
    },

    citation_pattern=r'42\s+CFR\s+§?\s*(\d{3}\.\d+)',
)


# =============================================================================
# MASTER CONFIGURATION REGISTRY
# =============================================================================

STATE_CONFIGS = {
    # State-specific regulations
    'idaho_idapa': IDAHO_CONFIG,
    'idaho_code': IDAHO_CODE_CONFIG,
    'washington': WASHINGTON_CONFIG,
    'oregon': OREGON_CONFIG,
    'arizona': ARIZONA_CONFIG,

    # Federal (apply everywhere)
    'fda_food_code': FDA_FOOD_CODE_CONFIG,
    'ada': ADA_CONFIG,
    'cms': CMS_CONFIG,
}


def detect_config(content: str, filename: str) -> StateConfig:
    """
    Detect which state/federal config applies to a document.

    Returns the matching StateConfig or None if no match.
    """
    filename_lower = filename.lower()

    for config_name, config in STATE_CONFIGS.items():
        # Check filename patterns
        for pattern in config.filename_patterns:
            if re.search(pattern, filename_lower, re.IGNORECASE):
                return config

        # Check content patterns
        for pattern in config.content_patterns:
            if re.search(pattern, content, re.MULTILINE | re.IGNORECASE):
                return config

    # Default to Idaho IDAPA if no match (for backwards compatibility)
    return IDAHO_CONFIG


def get_all_agency_mappings() -> Dict[str, str]:
    """Combine all agency mappings from all configs."""
    combined = {}
    for config in STATE_CONFIGS.values():
        combined.update(config.agency_mappings)
    return combined


# =============================================================================
# TEMPLATE FOR ADDING NEW STATES
# =============================================================================

NEW_STATE_TEMPLATE = '''
# Copy this template and fill in for your state

{STATE_NAME}_CONFIG = StateConfig(
    state_name="{State Name}",
    state_abbrev="{XX}",

    filename_patterns=[
        r'pattern1',  # e.g., state admin code abbreviation
        r'pattern2',  # e.g., state name
    ],

    content_patterns=[
        r'pattern1',  # e.g., "WAC \d+" for Washington
        r'pattern2',  # e.g., state agency name
    ],

    section_patterns={{
        'level_1': r'pattern_for_main_sections',
        'level_2': r'pattern_for_subsections',
        'level_3': r'pattern_for_sub_subsections',
    }},

    agency_mappings={{
        'Full Agency Name': 'ABBREV',
    }},

    citation_pattern=r'citation_format_pattern',
)

# Then add to STATE_CONFIGS:
# '{state_name}': {STATE_NAME}_CONFIG,
'''


def print_new_state_template():
    """Print the template for adding a new state."""
    print(NEW_STATE_TEMPLATE)


if __name__ == "__main__":
    print("Configured states/jurisdictions:")
    for name, config in STATE_CONFIGS.items():
        print(f"  - {name}: {config.state_name} ({config.state_abbrev})")

    print("\n" + "="*50)
    print("Template for adding new states:")
    print_new_state_template()
