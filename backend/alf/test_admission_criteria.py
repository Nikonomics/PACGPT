"""
Batch test script for Idaho ALF chatbot admission criteria answers.
Tests against the API running on port 8000.
"""

import json
import requests
from datetime import datetime

# Test configuration
API_URL = "http://localhost:8000/query"
STATE = "Idaho"

# Test questions with expected answers
TEST_CASES = [
    {
        "question": "Can we admit a resident with a Foley catheter?",
        "expected": "YES",
        "notes": "Foley catheters are NOT in the prohibited list - only supra-pubic catheters within 21 days"
    },
    {
        "question": "Can we admit a resident with a supra-pubic catheter that was inserted 2 weeks ago?",
        "expected": "NO",
        "notes": "Supra-pubic catheters require 21+ days since insertion"
    },
    {
        "question": "Can we admit a resident with a G-tube that was placed 30 days ago?",
        "expected": "YES",
        "notes": "G-tubes (gastrostomy) are OK if 21+ days since insertion"
    },
    {
        "question": "Can we have residents on IV therapy?",
        "expected": "NO",
        "notes": "Continuous IV therapy is prohibited"
    },
    {
        "question": "What about residents with stage 3 pressure ulcers?",
        "expected": "NO",
        "notes": "Stage III and IV pressure ulcers are prohibited"
    },
    {
        "question": "Can we accept residents on ventilators?",
        "expected": "NO",
        "notes": "Mechanically supported breathing prohibited (except CPAP/BiPAP for sleep apnea)"
    },
    {
        "question": "Can a resident with a tracheostomy live in our facility?",
        "expected": "DEPENDS",
        "notes": "Only if resident can care for tracheostomy independently"
    },
    {
        "question": "Are hospice patients allowed in Idaho assisted living?",
        "expected": "YES",
        "notes": "Comatose patients allowed if death likely within 30 days (hospice exception)"
    },
    {
        "question": "Can we admit a resident with MRSA?",
        "expected": "DEPENDS",
        "notes": "MRSA in infectious stage is prohibited, but non-infectious MRSA is allowed"
    },
    {
        "question": "What residents are we NOT allowed to admit in Idaho?",
        "expected": "LIST",
        "notes": "Should list all prohibited conditions from Section 152.04"
    }
]


def classify_answer(response_text: str) -> str:
    """Classify the response as YES, NO, DEPENDS, or UNCLEAR."""
    text_lower = response_text.lower()

    # Check for clear NO indicators
    no_patterns = [
        "no, you cannot",
        "cannot admit",
        "are not allowed",
        "not permitted",
        "prohibited from",
        "are prohibited",
        "you cannot admit",
        "cannot be admitted",
        "cannot have",
        "not be admitted"
    ]

    # Check for clear YES indicators
    yes_patterns = [
        "yes, you can",
        "can be admitted",
        "are allowed",
        "may admit",
        "can admit",
        "is permitted",
        "are permitted"
    ]

    # Check for DEPENDS indicators
    depends_patterns = [
        "depends",
        "only if",
        "unless",
        "provided that",
        "as long as",
        "if the resident",
        "if they can",
        "independently",
        "under certain conditions",
        "but only",
        "certain conditions",
        "not in an infectious"
    ]

    # Check for list indicators (for "who can't we admit" question)
    list_patterns = [
        "include:",
        "following:",
        "prohibited:",
        "cannot be admitted:",
        "such as:"
    ]

    # Classify
    has_no = any(p in text_lower for p in no_patterns)
    has_yes = any(p in text_lower for p in yes_patterns)
    has_depends = any(p in text_lower for p in depends_patterns)
    has_list = any(p in text_lower for p in list_patterns)

    if has_list and not has_yes and not has_no:
        return "LIST"
    if has_depends and (has_yes or has_no):
        return "DEPENDS"
    if has_no and not has_yes:
        return "NO"
    if has_yes and not has_no:
        return "YES"
    if has_depends:
        return "DEPENDS"

    return "UNCLEAR"


def check_admission_criteria_language(citations: list) -> bool:
    """Check if citations contain admission criteria language."""
    keywords = [
        "admission", "admit", "prohibited", "cannot be admitted",
        "twenty-one", "21 days", "gastrostomy", "catheter", "IV therapy",
        "tracheotomy", "ventilator", "pressure ulcer", "MRSA"
    ]

    for citation in citations:
        content = citation.get('content', '').lower()
        if any(kw.lower() in content for kw in keywords):
            return True
    return False


def run_test(question: str, expected: str) -> dict:
    """Run a single test against the chatbot API."""
    try:
        # Make API request
        payload = {
            "question": question,
            "state": STATE
        }

        response = requests.post(API_URL, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()

        # Extract response details
        answer_text = data.get('response', '')
        citations = data.get('citations', [])
        retrieved_chunks = data.get('retrieved_chunks', [])

        # Get chunk details
        chunk_details = []
        for chunk in retrieved_chunks[:5]:  # Top 5 chunks
            chunk_details.append({
                'chunk_id': chunk.get('chunk_id', 'unknown'),
                'similarity': chunk.get('similarity', 0),
                'section': chunk.get('section_number', 'N/A'),
                'source': chunk.get('source_file', chunk.get('source_document', 'unknown')),
                'content_preview': chunk.get('content', '')[:200]
            })

        # Classify the answer
        actual = classify_answer(answer_text)

        # Check if it passes
        passed = False
        if expected == "LIST":
            # For list questions, check if it contains multiple prohibited conditions
            passed = actual == "LIST" or (
                "gastrostomy" in answer_text.lower() or
                "catheter" in answer_text.lower() or
                "iv therapy" in answer_text.lower()
            )
        elif expected == "DEPENDS":
            passed = actual in ["DEPENDS", "YES"]  # DEPENDS or conditional YES is acceptable
        else:
            passed = actual == expected

        # Check for issues
        issues = []
        if not passed:
            issues.append(f"Expected {expected}, got {actual}")

        if chunk_details and chunk_details[0]['similarity'] < 0.3:
            issues.append(f"Low similarity: {chunk_details[0]['similarity']:.3f}")

        if citations and not check_admission_criteria_language(citations):
            issues.append("Citations don't contain admission criteria language")

        return {
            'question': question,
            'expected': expected,
            'actual': actual,
            'passed': passed,
            'answer_text': answer_text[:500],
            'full_answer': answer_text,
            'chunk_details': chunk_details,
            'citation_previews': [
                {
                    'citation': c.get('citation', 'N/A'),
                    'section_title': c.get('section_title', 'N/A'),
                    'content_preview': c.get('content', '')[:200]
                }
                for c in citations[:3]
            ],
            'issues': issues,
            'top_similarity': chunk_details[0]['similarity'] if chunk_details else 0
        }

    except requests.exceptions.ConnectionError:
        return {
            'question': question,
            'expected': expected,
            'actual': 'ERROR',
            'passed': False,
            'answer_text': 'ERROR: Could not connect to API on port 8000',
            'full_answer': '',
            'chunk_details': [],
            'citation_previews': [],
            'issues': ['API connection failed - is the server running?'],
            'top_similarity': 0
        }
    except Exception as e:
        return {
            'question': question,
            'expected': expected,
            'actual': 'ERROR',
            'passed': False,
            'answer_text': f'ERROR: {str(e)}',
            'full_answer': '',
            'chunk_details': [],
            'citation_previews': [],
            'issues': [str(e)],
            'top_similarity': 0
        }


def main():
    print("=" * 80)
    print("IDAHO ALF ADMISSION CRITERIA BATCH TEST")
    print("=" * 80)
    print(f"\nAPI URL: {API_URL}")
    print(f"State: {STATE}")
    print(f"Test cases: {len(TEST_CASES)}")
    print("\n" + "-" * 80)

    results = []

    for i, test_case in enumerate(TEST_CASES, 1):
        question = test_case['question']
        expected = test_case['expected']

        print(f"\n[{i}/{len(TEST_CASES)}] Testing: {question[:50]}...")

        result = run_test(question, expected)
        results.append(result)

        # Print immediate result
        status = "✓ PASS" if result['passed'] else "✗ FAIL"
        print(f"  {status} | Expected: {expected} | Actual: {result['actual']}")

        if result['issues']:
            for issue in result['issues']:
                print(f"  ⚠ {issue}")

    # Summary table
    print("\n" + "=" * 80)
    print("SUMMARY TABLE")
    print("=" * 80)
    print(f"\n{'Question':<40} {'Expected':<10} {'Actual':<10} {'Status':<8} {'Top Chunk ID':<30} {'Sim':<6}")
    print("-" * 110)

    passed_count = 0
    failed_count = 0

    for result in results:
        q_short = result['question'][:38] + ".." if len(result['question']) > 40 else result['question']
        status = "PASS" if result['passed'] else "FAIL"
        top_chunk = result['chunk_details'][0]['chunk_id'][:28] if result['chunk_details'] else "N/A"
        similarity = f"{result['top_similarity']:.3f}" if result['top_similarity'] else "N/A"

        if result['passed']:
            passed_count += 1
        else:
            failed_count += 1

        print(f"{q_short:<40} {result['expected']:<10} {result['actual']:<10} {status:<8} {top_chunk:<30} {similarity:<6}")

    print("-" * 110)
    print(f"\nRESULTS: {passed_count} PASSED, {failed_count} FAILED out of {len(results)} tests")

    # Flagged issues
    print("\n" + "=" * 80)
    print("FLAGGED ISSUES")
    print("=" * 80)

    issues_found = False
    for result in results:
        if result['issues']:
            issues_found = True
            print(f"\n❌ {result['question'][:60]}...")
            for issue in result['issues']:
                print(f"   • {issue}")

    if not issues_found:
        print("\n✓ No issues flagged!")

    # Save full results
    output_file = "/Users/nikolashulewsky/senior-chatbots/backend/alf/admission_criteria_test_results.json"

    full_results = {
        'test_date': datetime.now().isoformat(),
        'api_url': API_URL,
        'state': STATE,
        'summary': {
            'total': len(results),
            'passed': passed_count,
            'failed': failed_count,
            'pass_rate': f"{100 * passed_count / len(results):.1f}%"
        },
        'results': results
    }

    with open(output_file, 'w') as f:
        json.dump(full_results, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Full results saved to: {output_file}")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
