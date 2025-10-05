import re
from typing import Optional

try:
    from nameparser import HumanName
    HAS_NAMEPARSER = True
  
except ImportError:
    HAS_NAMEPARSER = False


class EntityClassification:
    """
    Goal:
     - first sanity check, pre DB lookup
     - return None if unsure, return "Company" | "Person" if we are 95-100% sure
    """

    # Legal entity suffixes (MUST be company)
    LEGAL_SUFFIXES = re.compile(
        r'\b(?:LLC|L\.L\.C\.?|Inc\.?|Ltd\.?|Corp\.?|Corporation|LP|LLP|GmbH|AG|SA|PLC|Plc)\b',
        re.IGNORECASE
    )

    # Strong company keywords
    COMPANY_KEYWORDS = re.compile(
        r'\b(?:Bank|Financial|Capital|Fund|Funding|Advisory|Advisors|Consulting|'
        r'Investment|Insurance|Asset|Credit|Equity|Securities|Realty|Properties|'
        r'International|Global|Management|Wealth|Group|Industries|Solutions|'
        r'Technologies|Systems|Services|Trust|Estate|Foundation|Association|'
        r'Society|Institute|Holdings|Partners|Ventures|Company|Associates)\b',
        re.IGNORECASE
    )

    # Company structure patterns
    COMPANY_STRUCTURE = re.compile(
        r'&\s*(?:Co|Sons|Brothers|Associates)|'  # X & Co
        r'/[A-Z]{2}(?:\s|$)|'  # State codes /IN
        r'\b[A-Z]{3,}\b\s+(?:Bank|Capital|Group|Financial|Consulting|Advisory|Partners)|'  # ABC Bank
        r'(?:^|\s)[A-Z]\.(?:[A-Z]\.)+',  # J.P. Morgan
        re.IGNORECASE
    )

    # Hard disqualifiers for person names
    NOT_PERSON = re.compile(
        r'\d{2,}|'  # 2+ digits
        r'[@#$%&*+=<>]|'  # Special chars
        r'https?://|www\.|\.(?:com|org|net|biz|info)\b'  # URLs
    )

    # Strong person indicators
    PERSON_TITLES = re.compile(
        r'^(?:Mr|Mrs|Ms|Miss|Dr|Prof|Professor|Sir|Dame|Lord|Lady)\.?\s',
        re.IGNORECASE
    )

    PERSON_SUFFIXES = re.compile(
        r'\b(?:Jr|Sr|II|III|IV|V|PhD|MD|CPA|Esq|MBA|DDS|DVM)\.?$',
        re.IGNORECASE
    )

    def __init__(self, name_resolver=None):
        """
        Args:
            name_resolver: Optional resolver with resolve_name_g() method
        """
        self.name_resolver = name_resolver

    def classify(self, text: str) -> Optional[str]:
        """
        Classify entity as "Company", "Person", or None.

        Returns:
            "Company" | "Person" | None
        """
        if not text or not text.strip():
            return None

        text = text.strip()

        # ═══════════════════════════════════════════════════════════
        # PHASE 1: ABSOLUTE COMPANY INDICATORS (100% confidence)
        # ═══════════════════════════════════════════════════════════

        # Legal suffixes = always company
        if self.LEGAL_SUFFIXES.search(text):
            return "Company"

        # Company structure patterns (& Co, state codes, initials)
        if self.COMPANY_STRUCTURE.search(text):
            return "Company"

        # Multiple company keywords = definitely company
        company_keyword_count = len(self.COMPANY_KEYWORDS.findall(text))
        if company_keyword_count >= 2:
            return "Company"

        # Single strong company keyword + not person-like structure
        if company_keyword_count == 1:
            words = text.split()
            # "Goldman Sachs Bank" = company, but "John Banking" = unclear
            if len(words) >= 2 or any(w[0].isupper() and len(w) <= 3 for w in words):
                return "Company"

        # ═══════════════════════════════════════════════════════════
        # PHASE 2: ABSOLUTE PERSON INDICATORS (100% confidence)
        # ═══════════════════════════════════════════════════════════

        # Titles at start = person
        if self.PERSON_TITLES.search(text):
            return "Person"

        # Suffixes at end = person
        if self.PERSON_SUFFIXES.search(text):
            return "Person"

        # ═══════════════════════════════════════════════════════════
        # PHASE 3: DISQUALIFIERS
        # ═══════════════════════════════════════════════════════════

        # Hard disqualifiers (URLs, emails, numbers)
        if self.NOT_PERSON.search(text):
            return None

        # ═══════════════════════════════════════════════════════════
        # PHASE 4: STRUCTURAL HEURISTICS
        # ═══════════════════════════════════════════════════════════

        words = text.split()

        # 2-4 capitalized words with no company indicators
        if 2 <= len(words) <= 4:
            # All words capitalized and reasonable length
            if all(len(w) >= 2 and w[0].isupper() for w in words):
                # Check for company words
                company_words = {'and', 'the', 'of', 'Associates', 'Group', 'Partners',
                                 'Company', 'Management', 'Trust', 'Fund'}
                has_company_word = any(w in company_words for w in words)

                # Check if any word is a company keyword
                has_company_keyword = any(self.COMPANY_KEYWORDS.search(w) for w in words)

                # If no company indicators at all
                if not has_company_word and not has_company_keyword:
                    # 3-4 words = very likely person (e.g., "Marie Curie Smith")
                    if len(words) >= 3:
                        return "Person"

                    # 2 words: check with HumanName if available
                    if len(words) == 2:
                        if HAS_NAMEPARSER and self._is_valid_person_via_parser(text):
                            return "Person"
                        # Without HumanName validation, 2 words are ambiguous
                        # "John Smith" vs "Morgan Stanley"
                        return None

        # Single capitalized word (5-20 chars) - try HumanName
        if len(words) == 1 and 5 <= len(text) <= 20 and text[0].isupper():
            if HAS_NAMEPARSER and self._is_valid_person_via_parser(text):
                return "Person"
            # Could be company name like "Google", "Tesla"
            return None

        # ═══════════════════════════════════════════════════════════
        # PHASE 5: HUMANNAME FALLBACK
        # ═══════════════════════════════════════════════════════════

        # If we got here and still uncertain, try HumanName
        if HAS_NAMEPARSER and self._is_valid_person_via_parser(text):
            return "Person"

        # Default: uncertain
        return None

    def _is_valid_person_via_parser(self, text: str) -> bool:
        """
        Validate person name structure using HumanName parser.
        """
        if not HAS_NAMEPARSER:
            return False

        try:
            name = HumanName(text)

            # Must have first name
            if not name.first:
                return False

            # Validate with name resolver if available
            if self.name_resolver:
                if not self.name_resolver.resolve_name_g(name.first):
                    return False

            # Reject title/suffix without last name (might be company)
            if (name.title or name.suffix) and not name.last:
                return False

            # First + Last = person
            if name.first and name.last:
                return True

            # Single name with resolver validation
            if name.first and self.name_resolver:
                return True

            return False

        except Exception:
            return False


# ═══════════════════════════════════════════════════════════════
# TESTING
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    class MockNameResolver:
        VALID_NAMES = {
            'john', 'jane', 'michael', 'sarah', 'robert', 'marie',
            'bill', 'david', 'elizabeth', 'james', 'mary', 'william'
        }

        def resolve_name_g(self, name: str) -> bool:
            return name.lower() in self.VALID_NAMES


    resolver = MockNameResolver()
    classifier = EntityClassification(name_resolver=resolver)

    test_cases = [
        # ===== COMPANIES =====
        ("Apple Inc", "Company"),
        ("Microsoft Corporation", "Company"),
        ("Goldman Sachs Group", "Company"),
        ("ADS Consulting/IN", "Company"),
        ("Busey Bank", "Company"),
        ("CapM Funding", "Company"),
        ("Clearwater Financial", "Company"),
        ("FHN Financial Municipal Advisors", "Company"),
        ("First River Advisory L.L.C.", "Company"),
        ("J.P. Morgan & Co", "Company"),
        ("Morgan Stanley", "Company"),
        ("Blackstone Group", "Company"),
        ("Goldman Sachs", "Company"),

        # ===== PERSONS =====
        ("John Smith", "Person"),
        ("Dr. Jane Doe", "Person"),
        ("Robert Smith Jr.", "Person"),
        ("Marie Curie", "Person"),
        ("Bill Gates III", "Person"),
        ("Sarah Johnson", "Person"),
        ("Michael Bloomberg", "Person"),
        ("Warren Buffett", "Person"),
        ("James Smith MD", "Person"),
        ("Elizabeth Warren PhD", "Person"),

        # ===== AMBIGUOUS (None) =====
        ("Google", None),
        ("Tesla", None),
        ("Amazon", None),
        ("Bloomberg", None),  # Could be person or company
        ("Smith", None),  # Single surname
        ("Morgan Stanley", None),  # Ambiguous without context
        ("Goldman Sachs", None),  # Ambiguous without context
    ]

    print("=" * 70)
    print("CLASSIFICATION RESULTS")
    print("=" * 70)

    correct = 0
    total = len(test_cases)

    for text, expected in test_cases:
        result = classifier.classify(text)
        status = "✓" if result == expected else "✗"
        if result == expected:
            correct += 1
        print(f"{status} {text:40} -> {result} (expected: {expected})")

    print("=" * 70)
    print(f"Accuracy: {correct}/{total} ({100 * correct / total:.1f}%)")
    print("=" * 70)

  
"""

======================================================================
CLASSIFICATION RESULTS
======================================================================
  
✓ Apple Inc                                -> Company (expected: Company)
✓ Microsoft Corporation                    -> Company (expected: Company)
✓ Goldman Sachs Group                      -> Company (expected: Company)
✓ ADS Consulting/IN                        -> Company (expected: Company)
✓ Busey Bank                               -> Company (expected: Company)
✓ CapM Funding                             -> Company (expected: Company)
✓ Clearwater Financial                     -> Company (expected: Company)
✓ FHN Financial Municipal Advisors         -> Company (expected: Company)
✓ First River Advisory L.L.C.              -> Company (expected: Company)
✓ J.P. Morgan & Co                         -> Company (expected: Company)
✗ Morgan Stanley                           -> None (expected: Company)
✓ Blackstone Group                         -> Company (expected: Company)
✗ Goldman Sachs                            -> None (expected: Company)
✓ John Smith                               -> Person (expected: Person)
✓ Dr. Jane Doe                             -> Person (expected: Person)
✓ Robert Smith Jr.                         -> Person (expected: Person)
✓ Marie Curie                              -> Person (expected: Person)
✓ Bill Gates III                           -> Person (expected: Person)
✓ Sarah Johnson                            -> Person (expected: Person)
✓ Michael Bloomberg                        -> Person (expected: Person)
✗ Warren Buffett                           -> None (expected: Person)
✓ James Smith MD                           -> Person (expected: Person)
✓ Elizabeth Warren PhD                     -> Person (expected: Person)
✓ Google                                   -> None (expected: None)
✓ Tesla                                    -> None (expected: None)
✓ Amazon                                   -> None (expected: None)
✓ Bloomberg                                -> None (expected: None)
✓ Smith                                    -> None (expected: None)
✓ Morgan Stanley                           -> None (expected: None)
✓ Goldman Sachs                            -> None (expected: None)

======================================================================
Accuracy: 27/30 (90.0%)
======================================================================
  
"""

"""

- Good accuracy 
- May use it as a pre-check for a raw "name"
- If it returns None, we know, that the DB has to do some query lookups (and hope to match by other conditions - dependant on the execution context, e.g. by a CIK/CRD that already holds the Entity Class)
  
"""

          
          
