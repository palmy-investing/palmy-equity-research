try:
    from nameparser import HumanName
    HAS_NAMEPARSER = True

except ImportError:
    HAS_NAMEPARSER = False


class EntityClassifier:
    """
    Goal:
     - first sanity check, pre DB lookup
     - return None if unsure, return "Company" | "Person" if we are 95-100% sure
    """

    # todo add more
    COMMON_TWO_WORD_FAILURES = {
        "MORGAN STANLEY",
        "MERRILL LYNCH",
        "GOLDMAN SACHS",
        "CHARLES SCHWAB",
        "RAYMOND JAMES",
        "EDWARD JONES",
        "JOHNSON JOHNSON",
        "WELLS FARGO",
        "LAZARD FRERES",
        "PERELLA WEINBERG",
        "SANDLER O'NEILL",
        "CANTOR FITZGERALD",
        "LEHMAN BROTHERS",
        "BROWN FORMAN",
        "CITIGROUP SMITH",
        "DELOITTE TOUCHE",
        "KPMG PEAT",
        "ERNST YOUNG",
        "PRICE WATERHOUSE",
        "BARRINGTON HALL",
    }

    # Legal entity suffixes (MUST be company)
    LEGAL_SUFFIXES = re.compile(
        r'\b(?:LLC|L\.L\.C\.?|Ltd\.?|LP|LLP|GmbH|AG|SA|PLC|Plc|Co\.?|'
        r'Corp(?:\.|oration)?|Inc(?:\.|orporat(?:ed|ion|e|\.))?)\b',
        re.IGNORECASE
    )

    # Strong company keywords
    COMPANY_KEYWORDS = re.compile(
        r'\b(?:Bank|Financial|Capital|Fund|Funding|Advisory|Advisors|Consulting|'
        r'Investment|Insurance|Asset|Credit|Equity|Securities|Realty|Properties|'
        r'International|Global|Management|Markets|Wealth|Group|Industries|Solutions|'
        r'Technologies|Systems|Services|Trust|Estate|Foundation|Association|'
        r'Society|Institute|Holdings|Societe|Partners|Ventures|Company|Associates)\b',
        re.IGNORECASE
    )

    # Company structure patterns
    COMPANY_STRUCTURE = re.compile(
        r'&\s*(?:Co|Sons|Brothers|Associates)|'  # X & Co 
        r'/[A-Z]{2,4}(?:\s|$)|'  # State codes /IN but also longer /MSD
        r'\b[A-Z]{3,}\b\s+(?:Bank|Capital|Group|Advisor|Financial|Consulting|Advisory|Partners)|'  # ABC Bank
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

    REGIMES = {

        # --- Registered Investment Companies (’40 Act) ---
        "N-1A": "is_oef",
        "N-2": "is_bdc",
        "N-3": "is_insurance",
        "N-4": "is_insurance",
        "N-6": "is_insurance",
        "N-8B": "is_uit",  # alias for N-8B-2
        "N-8B-2": "is_uit",
        "N-54A": "is_bdc",
        "N-MFP": "is_mmf",
        "N-MFP2": "is_mmf",

        # --- Real Estate ---
        "S-11": "is_rt",

        # --- Insurance / ADR / Foreign ---
        "F-6": "is_adr_shell",
        "F-1": "is_fpi",
        "F-3": "is_fpi",
        "F-4": "is_fpi",
        "F-10": "is_fpi",
        "20-F": "is_fpi",
        "6-K": "is_fpi",
        "40-F": "is_fpi",

        # --- Market Infrastructure ---
        "1-SRO": "is_sro",
        "SBSEF": "is_sbsef",
        "SDR": "is_sdr",

        # --- Advisers ---
        "ADV": "is_ria",  # includes ADV, ADV-W, ADV-E etc.

    }

    def __init__(self, name_resolver=None):
        """
        Args:
            name_resolver: Optional resolver with resolve_name_g() method
        """
        self.name_resolver = name_resolver
    
    def classify(self, text, forms=None):
        """ 
        
         if forms = None
         -> Use classify_by_re with text
         
         if forms
         -> Use classify_by_forms; If no match use classify_by_re 
        
         may return
            - set (list of Company flags) - if forms
            - str (Company | Person) regex classification
            - None (regex classification of being too unsure)
            
        """
        
        if forms:
            x = self.classify_by_forms(forms=forms)
            
            if x:
                return x
            
            # --- no lag found 
            
        y = self.classify_by_re(text)
        return y
        
    def classify_by_re(self, text: str):
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
                company_words = {
                    'and', 'the', 'of', 'Associates', 'Group', 'Partners',
                    'Company', 'Management', 'Trust', 'Fund', 'International'
                }

                has_company_word = any(w in company_words for w in words)

                # Check if any word is a company keyword
                has_company_keyword = any(self.COMPANY_KEYWORDS.search(w) for w in words)

                # If has company indicators, already caught in Phase 1
                # If no company indicators:
                if not has_company_word and not has_company_keyword:

                    # Use HumanName parser for validation
                    if HAS_NAMEPARSER and self._is_valid_person_via_parser(text):

                        if text.upper() in self.COMMON_TWO_WORD_FAILURES:
                            return "Company"

                        return "Person"

                    # Without parser validation, 2-4 words are ambiguous
                    # Could be either one
                    return None

                return "Company"

        # 5+ words = almost always company (departments, long company names)
        if len(words) >= 5:
            return "Company"

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

    def classify_by_forms(self, forms: set) -> list:
        """
        
         forms expect a set of form types, not a list, e.g.
            {"ADV", "40-F", }
         
         see IDX Parser usage
        
         Returns one of
            FOREIGN_FORMS.values() or None
        
         Goal: 
            - Classification of IDX entries by collected forms per parse run
            - Avoiding false classifications of .classify() & reducing regex usage,
             e.g. Person <> But a Person has a "is_insurance" flag --> FRAUD
            
        """
        return [i for f in forms if (i := self.REGIMES.get(f))]
    
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

            # Reject title/suffix without last name (might be company)
            if (name.title or name.suffix) and not name.last:
                return False

            # First + Last = likely person
            if name.first and name.last:
                # Validate with name resolver if available
                if self.name_resolver:
                    # Check if first name is valid
                    if self.name_resolver.resolve_name_g(name.first):
                        return True
                    # Name resolver says it's not a valid first name
                    return False
                # No resolver, trust HumanName parser
                return True

            # Single name with resolver validation
            if name.first and self.name_resolver:
                return self.name_resolver.resolve_name_g(name.first)

            return False

        except Exception:
            return False

ENTS = EntityClassifier()
classifier = ENTS

FAILURES = [

    # ===== Some finish company names =====
    ("Kone- ja Siltarakennus Oy", "Company"),
    ("Chymos Oy", "Company"),
    ("Sisu Auto Ab", "Company"),
    ("Tana Oy", "Company"),
    ("Eniram Oy", "Company"),

    # ===== Weird / obscure Finnish company failures =====
    ("Yhtiö X Oy", "Company"),  # Placeholder company
    ("Kummallinen Firma Oy", "Company"),  # 'Weird Company' in Finnish
    ("Sateenkaari Teknologia Ab", "Company"),  # Rainbow Technology
    ("Lumottu Laiva Oy", "Company"),  # 'Enchanted Ship'
    ("Hämärä Innovaatio Oy", "Company"),  # 'Dim Innovation'

    # ===== Weird name structures =====
    ("X Æ A-12", "Person"),  # Elon Musk's kid

    # ===== (First Name, Company Identifier) =====
    ("Peter bank", None),  # Should be None / Unknown

    # ===== Foreign company names that look like persons without a special re-usable lookup such as "Societe" =====
    ("BNP Paribas", "Company"),

]

# just to showcase some of the positive ones ---- you may test:
SPECIAL_BUT_SUCCESSFUL = [
    ("Societe Generale", "Company"),    # Weird name
    ("Morgan Stanley", "Company"),      # Lookup
    ("John Doe Jr. Sr.", "Person"),     # Multiple suffixes
    ("Maria De La Cruz", "Person"),     # Spanish naming
    ("Jean-Pierre Dupont", "Person"),   # French hyphenated
    ("Van Der Berg", "Person"),         # Dutch prefix
]


print("=" * 70)
print("CLASSIFICATION RESULTS")
print("=" * 70)

correct = 0
total = len(FAILURES)

for text, expected in FAILURES:
    result = classifier.classify(text)
    status = "✓" if result == expected else "✗"
    if result == expected:
        correct += 1
    print(f"{status} {text:45} -> {result} (expected: {expected})")

print("=" * 70)
print(f"Accuracy: {correct}/{total} ({100*correct/total:.1f}%)")
print("=" * 70)


"""

Ran a test on MPAs -- good output (Part 1 is the execution of the failure classes - which this parser is not meant to address)

palmyAI\parsers\EDGAR_structured.py
======================================================================
CLASSIFICATION RESULTS
======================================================================
✗ Kone- ja Siltarakennus Oy                     -> Person (expected: Company)
✗ Chymos Oy                                     -> Person (expected: Company)
✗ Sisu Auto Ab                                  -> Person (expected: Company)
✗ Tana Oy                                       -> Person (expected: Company)
✗ Eniram Oy                                     -> Person (expected: Company)
✗ Yhtiö X Oy                                    -> Person (expected: Company)
✗ Kummallinen Firma Oy                          -> Person (expected: Company)
✗ Sateenkaari Teknologia Ab                     -> Person (expected: Company)
✗ Lumottu Laiva Oy                              -> Person (expected: Company)
✗ Hämärä Innovaatio Oy                          -> Person (expected: Company)
✗ X Æ A-12                                      -> None (expected: Person)
✗ Peter bank                                    -> Company (expected: None)
✗ BNP Paribas                                   -> Person (expected: Company)
======================================================================
Accuracy: 0/13 (0.0%)
======================================================================

&PARTNERS is a None
30 Three Sixty Public Finance, Inc. is a Company
A. M. Peche & Associates LLC is a Company
A.BRIDGE REALVEST SECURITIES CORPORATION is a Company
Acacia Financial Group, Inc. is a Company
ACS Management & Consulting LLC is a Company
ADS Consulting/IN is a Company
AE2S Nexus, LLC is a Company
AGECROFT PARTNERS, LLC is a Company
Agentis Capital Advisors Ltd. is a Company
AKF Consulting LLC is a Company
AMD CAPITAL, LLC is a Company
American Deposit Management LLC is a Company
Ameritas Investment Company, LLC /ADV is a Company
AMKO Advisors, LLC is a Company
Ampersand Public Advisors, LLC is a Company
Ankura Consulting Group, LLC is a Company
Argent Advisors, Inc. is a Company
ARK Global LLC is a Company
Armadale Capital Inc. is a Company
Arrow Partners, Inc. is a Company
Ascension Capital Enterprises, LLC is a Company
ASCENSUS INVESTMENT ADVISORS, LLC is a Company
Austin Meade Financial Ltd. is a Company
Avant Energy, Inc. is a Company
B. C. ZIEGLER AND COMPANY is a Company
BACKSTROM MCCARLEY BERRY & CO., LLC is a Company
Baker Group LP is a Company
BAKER TILLY MUNICIPAL ADVISORS, LLC is a Company
Barclays Capital INC is a Company
Bartle Wells Associates is a Company
Bayshore Consulting Group, Inc. is a Company
Becker Capital & Finance LLC is a Company
Bendzinski & Co. Municipal Finance Advisors is a Company
Bernard P. Donegan, Inc. is a Company
BGC Partners Advisory LLC is a Company
BJH Advisors, LLC is a Company
BlackRock Institutional Trust Company, N.A. is a Company
Blitch Associates, Inc. is a Company
Blue Rose Capital Advisors, LLC is a Company
BLUESTEM CAPITAL PARTNERS, INC. is a Company
None is a None
BLX Group LLC is a Company
BOK FINANCIAL SECURITIES, INC. is a Company
Bondry Management Consultants, LLC is a Company
Bosque Advisors, LLC is a Company
Bradley Payne LLC is a Company
Bretwood Capital Partners is a Company
Bridge Strategic Partners LLC is a Company
Bridgeport Partners, LLC is a Company
Brookhurst Development Corp is a Company
Buck Financial Advisors LLC is a Company
Building Hope Services, LLC is a Company
Busey Bank is a Company
C Financial Investment, Inc. is a Company
CABRERA CAPITAL MARKETS, LLC is a Company
Caine Mitter & Associates Inc is a Company
Caldwell Flores Winters, Inc. is a Company
Calhoun Baker Inc. is a Company
California Municipal Advisors LLC is a Company
Callowhill Capital Advisors LLC is a Company
Campanile Group, Inc. is a Company
Capital Markets Advisors, LLC is a Company
Capitol Public Finance Group, LLC is a Company
CapM Funding is a Company
CARTY, HARDING & HEARN, INC. is a Company
Cascade Capital Advisors, LLC is a Company
CE Jones Consulting LLC is a Company
Cedar Ventures LLC/DE is a Company
Cender & Company, L.L.C. is a Company
Centro Civica, LLC is a Company
CFW Advisory Services, LLC is a Company
cfX Inc is a Company
Chatham Hedging Advisors, LLC is a Company
Children First Capital Advisors LLC is a Company
CHITKARA RAVI is a Person
Choice Advisors LLC is a Company
CHURCHILL STATESIDE SECURITIES, LLC is a Company
CIM INVESTMENT MANAGEMENT INC is a Company
Clary Consulting Co is a Company
CLB Porter, LLC is a Company
CLEAN ENERGY CAPITAL SECURITIES LLC is a Company
Clear Scope Advisors, Inc. is a Company
Clearwater Financial is a Company
COLLIERS SECURITIES LLC is a Company
COLORADO FINANCIAL SERVICE CORPORATION is a Company
Columbia Capital Management, LLC is a Company
Comer Capital Group, LLC is a Company
Community Concepts Group, Inc. is a Company
Community Development Associates, LLC is a Company
Compass Municipal Advisors, LLC is a Company
Concord Public Financial Advisors, Inc. is a Company
Cornerstone Health Advisors LLC is a Company
CREWS & ASSOCIATES, INC. is a Company
CRF Financial Group, Inc is a Company
CRITO CAPITAL LLC is a Company
Crowe LLP is a Company
CSG Advisors Inc is a Company
CTBH Partners LLC is a Company
Cumberland Securities Company, Inc. is a Company
D.A. DAVIDSON & CO. is a Company
DA Group, Inc. is a Company
Dale Scott & Co., Inc. is a Company
DARBY JAMES JOSEPH is a Person
DAVENPORT & Co LLC is a Company
David Drown Associates, Inc. is a Company
David Taussig & Associates is a Company
Daylight Capital Advisors, LLC is a Company
DEC Associates Inc is a Company
Del Rio Advisors, LLC is a Company
DERIVATIVE ADVISORS, LLC is a Company
Derivative Logic, Inc. is a Company
Development Planning & Financing Group, INC is a Company
DiPerna & Company, LLC is a Company
DIXWORKS LLC is a Company
Eastshore Consulting LLC is a Company
Echo Financial Products LLC is a Company
Echo Valley Advisors, LLC is a Company
Economic Development Group, Ltd. is a Company
EFG Consulting LLC is a Company
Ehlers & Associates, Inc. is a Company
Environmental Attribute Advisors LLC is a Company
Eppinger & Associates, LLC is a Company
Ernst & Young Infrastructure Advisors, LLC is a Company
ESTRADA HINOJOSA & COMPANY, INC. is a Company
Evercrest Advisors, LLC is a Company
Excelsior Capital Advisory Services LLC is a Company
FHN Financial Municipal Advisors is a Company
Fieldman, Rolapp & Associates, Inc. is a Company
FIFTH THIRD SECURITIES, INC. is a Company
Financial Advisory Investment Management Group, LLC is a Company
Financial Solutions Group, Inc. is a Company
First American Financial Advisors, Inc. is a Company
FIRST HAWAIIAN BANK is a Company
FIRST KENTUCKY SECURITIES CORPORATION is a Company
First River Advisory L.L.C. is a Company
First Security Municipal Advisors, Inc. is a Company
First Tryon Advisors, LLC is a Company
Fiscal Advisors & Marketing, Inc is a Company
Fiscal Strategies Group, Inc. is a Company
Fisher Robert W. E. is a Person
Ford & Associates,Inc. is a Company
Frasca & Associates, LLC is a Company
Froggatte & Co is a Company
Frontier One LLC is a Company
FROST BANK /MSD is a Company
FSL Public Finance, LLC is a Company
FTG Advisors, LLC is a Company
G Capital Investment Group Inc. is a Company
G.L. Hicks Financial, LLC is a Company
GALLAGHER SECURITIES, INC is a Company
GB ASSOCIATES LLC is a Company
Genesis Marketing Group, Inc. is a Company
GLC Municipal Advisors LLC is a Company
GOLDMAN SACHS & CO. LLC is a Company
Goodwin Consulting Group, Inc. is a Company
Government Capital Management, LLC is a Company
GOVERNMENT CAPITAL SECURITIES CORPORATION is a Company
Government Consultants, Inc. is a Company
Government Finance Group LLC is a Company
Government Financial Strategies inc. is a Company
GovRates, Inc. is a Company
GPM Municipal Advisors, LLC is a Company
Granite Municipal Advisors LLC is a Company
Grant & Associates LLC is a Company
Great Disclosure LLC is a Company
Greenland Risk Management LLC is a Company
Grigsby & Associates, INc. is a Company
GUARDIAN ADVISORS LLC is a Company
GUGGENHEIM SECURITIES, LLC is a Company
H G Wilson Municipal Finance, Inc. is a Company
Hamlin Capital Advisors, LLC is a Company
Hancock Whitney Bank Municipal Advisors Group is a Company
Harrell & Co Advisors, LLC is a Company
Harrington Rodney Jay is a Person
Harris & Associates, Inc. is a Company
Hayat Brown, LLC is a Company
Hedge Point Financial, LLC is a Company
Hendrickson Mark Allan is a Person
HERBERT J. SIMS & CO, INC. is a Company
HERITAGE FINANCIAL SYSTEMS, LLC is a Company
HILLTOP SECURITIES INC. is a Company
Hobbs, Ong & Associates, Inc. is a Company
Howard Joy A is a Person
HUNTINGTON SECURITIES, INC. is a Company
Huron Public Finance Advisory LLC is a Company
Independent Public Advisors, LLC is a Company
INEO CAPITAL, LLC is a Company
Innovative Capital is a Company
INSTITUTIONAL BOND NETWORK, LLC is a Company
IRON LION LLC is a Company
IRR Corporate & Public Finance, LLC is a Company
Isosceles & Co is a Company
JANNEY MONTGOMERY SCOTT LLC is a Company
JFBP, LLC is a Company
JNA Consulting Group, LLC is a Company
John W. Meyer PhD is a Person
Johnson Research Group, Inc. is a Company
JONES LANG LASALLE SECURITIES, LLC is a Company
K-12 Capital Advisors, LLC is a Company
Kaiser Wealth Management is a Company
KANE, MCKENNA CAPITAL, INC. is a Company
Kaufman, Hall & Associates, LLC is a Company
Kensington CA, LLC is a Company
Kentucky Association of Counties is a Company
Key Charter Advisors, LLC is a Company
KEYBANC CAPITAL MARKETS INC. is a Company
KeyBank Municipal Advisor Department is a Company
Keygent LLC is a Company
Keystone MA Group, LLC is a Company
Kidwell & Co is a Company
Kings Financial Consulting Inc is a Company
KIPLING JONES & CO., LTD. is a Company
KLEINPETER FINANCIAL GROUP LLC is a Company
Knight & Day Group, LLC is a Company
KNN PUBLIC FINANCE, LLC is a Company
Kosan Associates is a Company
Kosmont Transactions Services, Inc. is a Company
Kovack Municipal Group LLC is a Company
KPM Financial, LLC is a Company
L.J. HART & Co is a Company
Laird Thomas is a Person
Lamont Financial Services Corp is a Company
LARSEN WURZEL & ASSOCIATES INC is a Company
Larson Consulting Services, LLC is a Company
Latitude Financial Management, LLC is a Company
Launch Development Finance Advisors, LLC is a Company
Leora Consulting LLC is a Company
Lexton Infrastructure Solutions LLC is a Company
Liberty Capital Services, LLC is a Company
Live Oak Public Finance, LLC is a Company
Local Government Solutions, LLC is a Company
London Witte Group, LLC is a Company
Lone Star PACE LLC is a Company
Longhouse Capital Advisors, LLC is a Company
LRB PUBLIC FINANCE ADVISORS, INC. is a Company
Lucrum Capital Advisors, Inc. is a Company
M.E. ALLISON & CO., INC. is a Company
MACQUARIE CAPITAL (USA) INC. is a Company
Majors Group is a Company
Marathon Capital Strategies, LLC is a Company
MAS Financial Advisory Services LLC is a Company
Masterson Advisors LLC is a Company
Matrix Capital Markets Group, Inc. is a Company
Meierhenry Sargent LLP is a Company
MEKETA INVESTMENT GROUP INC /ADV is a Company
Melio & Company, LLC is a Company
Mercator Advisors LLC is a Company
Meristem Advisors LLC is a Company
MESIROW FINANCIAL, INC. is a Company
MFCI,LLC is a Company
MGIC Corp is a Company
Mission Trail Advisors, LLC is a Company
Mohanty Gargiulo LLC is a Company
MOMENTUS SECURITIES LLC is a Company
Montague DeRose & Associates, LLC is a Company
Moody Reid Financial Advisors LP is a Company
Moors & Cabot, Inc. is a Company
MULTI-BANK SECURITIES, INC. is a Company
MuniCap, Inc. is a Company
Municipal Advisors Group of Boston, Inc. is a Company
Municipal Advisors of Mississippi, Inc. is a Company
MUNICIPAL ADVISORY SOLUTIONS LLC is a Company
Municipal Capital Advisors LLC is a Company
MUNICIPAL CAPITAL MARKETS GROUP, INC. is a Company
Municipal Finance Services, Inc. is a Company
Municipal Resource Advisors, LLC is a Company
Municipal Solutions, Inc. is a Company
MuniGroup, LLC is a Company
Munistat Services, Inc. is a Company
Murdock Consulting LLC is a Company
MW Financial Advisory Services LLC is a Company
National Capital Resources, LLC is a Company
National Healthcare Capital LLC is a Company
NBS Government Finance Group is a Company
Neuberger Berman Trust Co National Association is a Company
NHA Advisors, LLC is a Company
Nickel Hayden Advisors, LLC is a Company
North Slope Capital Advisors, Inc. is a Company
Northeast Municipal Advisors LLC is a Company
NORTHLAND SECURITIES, INC. is a Company
NORTHWEST MUNICIPAL ADVISORS, INC. is a Company
Not for Profit Capital Strategies, LLC is a Company
Nutshell Associates, LLC is a Company
NW Financial Group, LLC is a Company
O.W. Krohn & Associates, LLP is a Company
Oakdale Municipal Advisors, LLC is a Company
Omnicap Group LLC is a Company
OP Capital Advisors, LLC is a Company
Optimal Capital Group llc is a Company
Oyster River Capital LP is a Company
P3 Municipal Advisors LLC is a Company
Partner Capital Advisors LLC is a Company
Patriot Advisors LLC is a Company
Pearl Creek Advisors, LLC is a Company
Perseverance Capital Advisors LLC is a Company
Peter J. Ross is a Person
Peters Franklin, LTD is a Company
PFM CALIFORNIA ADVISORS LLC is a Company
PFM FINANCIAL ADVISORS LLC is a Company
PFM Swap Advisors LLC is a Company
Phoenix Capital Partners, LLP is a Company
PICKWICK CAPITAL PARTNERS, LLC is a Company
Pilewski Financial, LLC is a Company
PIPER SANDLER & CO. is a Company
PMA Securities, LLC is a Company
PolyChronic PMC, LLC is a Company
Pop-Lazic & Co. LLC is a Company
Porter, White & Company, Inc is a Company
Post Oak Municipal Advisors, LLC is a Company
Project Finance Advisory Ltd is a Company
Public Economics, Inc. is a Company
Public Finance & Energy Advisors, LLC is a Company
Public Finance Group LLC is a Company
Public Resources Advisory Group, Inc. is a Company
Query & Associates LLC is a Company
R. G. Timbs, Inc. is a Company
Raftelis Financial Consultants, Inc. is a Company
Ranson Financial Corp is a Company
Ranson Financial Group, LLC is a Company
Rathmann & Associates, L.P. is a Company
RAYMOND JAMES & ASSOCIATES, INC. is a Company
RBC Capital Markets, LLC is a Company
RebelGroup Americas, Inc. is a Company
REEDY FINANCIAL GROUP, PC is a Company
Rice Advisory, LLC is a Company
Ridgeline Municipal Strategies, LLC is a Company
RM&P, LLC is a Company
ROBERT W. BAIRD & CO. Inc is a Company
Roberts Consulting, LLC is a Company
Rockfleet Financial Services, Inc. is a Company
Rockmill Financial Consulting, LLC is a Company
ROOSEVELT & CROSS, INCORPORATED is a Company
ROTHSCHILD & CO US INC. is a Company
Rothstein Group, LLC. is a Company
RoundTable Funding LLC is a Company
RSA Advisors, LLC is a Company
RSI Group LLC is a Company
RTM Asset Management LLC is a Company
S L Capital Strategies LLC is a Company
S.B. Clark, Inc. is a Company
S.P. Yount Financial, LLC is a Company
SAMCO CAPITAL MARKETS, INC. is a Company
SAMUEL A. RAMIREZ & COMPANY, INC. is a Company
SB Friedman Development Advisors, LLC is a Company
Sentry Financial Services is a Company
SENTRY MANAGEMENT INC                                   /ADV is a Company
SG AMERICAS SECURITIES, LLC is a Company
Shining Light Consulting LLC is a Company
SIEBERT WILLIAMS SHANK & CO., LLC is a Company
Sierra Management Group, LLC is a Company
SISUNG SECURITIES CORPORATION is a Company
SJ ADVISORS LLC is a Company
SOA Financial is a Company
South Avenue Investment Partners, LLC is a Company
Southeastern Investment Securities LLC is a Company
SOUTHSTATE|DUNCANWILLIAMS SECURITIES CORP. is a Company
Special Districts Association of Oregon Advisory Services LLC is a Company
Specialized Public Finance Inc. is a Company
Speer Financial, Inc. is a Company
Sperry Capital, Inc. is a Company
Standard International Group Inc. is a Company
Stanley P. Stone & Associates, Inc. is a Company
Starling Impact Advisors LLC is a Company
STARSHAK WINZENBURG & CO is a Company
Stephen H. McDonald & Associates, Inc. is a Company
Stephen L. Smith Corp. is a Company
STEPHENS INC /AR/ is a Company
steven gortler is a Person
Stewart Carr LLC is a Company
STIFEL, NICOLAUS & COMPANY, INCORPORATED is a Company
Sturges Co is a Company
Sudsina & Associates, LLC is a Company
Sustainable Capital Advisors, LLC is a Company
Sutter Capital Partners, LLC is a Company
Sycamore Advisors, LLC is a Company
Synovus Securities, Inc. is a Company
Systima Capital Management LLC is a Company
TCBI SECURITIES, INC. is a Company
TenSquare LLC is a Company
Terminus Municipal Advisors, LLC is a Company
THE GMS GROUP, LLC is a Company
Therber, Brock & Associates, LLC is a Company
Think Forward Financial Group LLC is a Company
THORNTON FARISH INC. is a Company
TIAA-CREF Tuition Financing, Inc. is a Company
Tierra Financial Advisors, LLC is a Company
TIJERINA FINANCIAL CONSULTING LLC is a Company
Toni Hackett Antrum is a Person
Torain Group is a Company
TRAILMARK INC. is a Company
TRB CAPITAL MARKETS, LLC is a Company
Trilogy Consulting, LLC is a Company
Trinity Capital Resources, LLC is a Company
UMB FINANCIAL SERVICES, INC. is a Company
UniBank Fiscal Advisory Services, Inc. is a Company
UNION BANK & TRUST CO /NE/ is a Company
URBAN FUTURES, INC. is a Company
USCA Municipal Advisors LLC is a Company
VANGUARD ADVISERS INC is a Company
Virginia Local Government Finance Corp is a Company
VIUM Capital MA, LLC is a Company
W J Fawell LLC is a Company
Warbird Municipal Advisors, LLC is a Company
Water Finance Exchange Municipal Advisors, Inc. is a Company
Water Street Public Finance, LLC is a Company
Waters & Company, LLC is a Company
Webb Municipal Finance, LLC is a Company
West Point Financing, Inc is a Company
Willdan Financial Services is a Company
William Euphrat Municipal Finance, Inc. is a Company
Winters & Co Advisors, LLC is a Company
Wisconsin Public Finance Professionals, LLC is a Company
WULFF, HANSEN & CO. is a Company
YOUNG AMERICA CAPITAL, LLC is a Company
Yuba Group LLC is a Company
ZIONS BANCORPORATION,N.A. /MSD is a Company
Zions Public Finance, Inc. is a Company
Zomermaand Financial Advisory Services, L.L.C. is a Company

Process finished with exit code 0


"""

"""

 I would advice against:
  - Using this parser as-is without the support of your database and existing records
  - Spawning new records based on it's outcome, except the dataset you parse is obversable for humans, i.e. MPAs

 Feel free to share further failures 

"""
