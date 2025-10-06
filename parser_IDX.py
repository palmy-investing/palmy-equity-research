
class ParserIDX:
    """ Makes multi-register ready """

    def __init__(self, start, end):
        """ """

        self.counted__persons = 0
        self.counted__companies = 0
        self.counted__none = 0
        self.counted__flags = {}        # works diff. see classify()

        print(f"=========== Requesting ================ ")

        self.small_db = {}
        self.links = []

        for year in range(start, end + 1):  # include end year
            for quarter in range(1, 5):  # Q1–Q4
                links = self._scrape_form_idx_links(year, quarter)  # should return a list
                self.links.extend(links)  # flatten instead of append

        if not self.links:
            raise Exception(f"No urls extracted for year: {start}, until: {end}")

        print("=========== Done - Ready for Action ===============")

    @staticmethod
    def _scrape_form_idx_links(year: int, quarter: int) -> list:
        """
        Scrape SEC daily-index directory for all form*.idx files.

        Args:
            year (int): Full year (e.g., 1994, 2014, 2025).
            quarter (int): Quarter number (1–4).

        Returns:
            list: URLs of all company*.idx files.
        """

        base_url = f"https://www.sec.gov/Archives/edgar/daily-index/{year}/QTR{quarter}/"
        response = Request(base_url).fetch(as_json=False)

        try:
            html = response.text if hasattr(response, "text") else response.read().decode("utf-8", errors="ignore")
        except Exception as E:
            print(f"{year} - {quarter} does not work:")
            print(base_url)
            return []

        # Extract only company*.idx links
        links = re.findall(r'href="(company[^"]*?\.idx)"', html, re.IGNORECASE)

        # Build absolute URLs
        urls = [base_url + link for link in links]

        return urls

    def parse_idx_day(self, enum):

        url = self.links[enum]

        response = Request(url).fetch(as_json=False)
        text = response.text if hasattr(response, "text") else response.read().decode("utf-8", errors="ignore")
        lines = text.splitlines()

        # Find the start of data (after the dashed line)
        start_index = 0
        for i, line in enumerate(lines):
            if line.startswith("----"):
                start_index = i + 1
                break

        if start_index == 0:
            print(f"Warning: Could not find data start marker in {url}")
            return

        # Parse each data line
        for line_num, line in enumerate(lines[start_index:], start_index + 1):

            if not line.strip():
                continue

            parsed = parse_idx_line(line)

            if not parsed:
                continue

            # Extract accession number
            accs = extract_acc(parsed["file_name"])

            # idea as we use company.idx now
            # keep one main body :
            # cik: {"name": ... and new: add forms: [] <... using later for flags on create or if cik in DB flagship !}

            cik = parsed["cik"]

            # --- our current code was written for company.idx on the -- parse_idx_line level
            # so just swap these two and it works --- skipped the rework here
            name = parsed["company_raw"]
            ft = parsed["form_type"]

            form = {
                "accs": accs,
                "filed": parsed["date_filed"],
                "type": ft
            }

            if not self.small_db.get(cik):
                self.small_db[cik] = {
                    "original_name": name,
                    "other_names": [],
                #    Doing this at the end with full forms= backup
                    "entity": None,

                    "forms": [form]
                }
                continue

            record = self.small_db[cik]
            names = ["original_name"] + record["other_names"]

            if name not in names:
                # -- tracking name changes per CIK --- e.g. Zuckerberg Max --- Zuckerberg Marx
                self.small_db[cik]["other_names"].append(form)

            fts = [f.get("type") for f in record["forms"]]

            # already part
            if ft not in fts:
                # new form type == regime info
                self.small_db[cik]["forms"].append(form)

    def parse(self, describe=False):
        """ """

        # :10 while testing
        for i, _ in enumerate(self.links[:10]):
            self.parse_idx_day(i)

        # classify ents
        self.classify()

        if not describe:
            return self.small_db

        self.describe()

    def classify(self):
        """ calls ENTS.classify() with forms on each unique CIK """

        for k in self.small_db.keys():
            vals = self.small_db[k]
            types = [i["type"] for i in vals["forms"]]
            ent = ENTS.classify(vals["original_name"], forms=types)
            self.small_db[k]["entity"] = ent

            if ent is None:
                self.counted__none += 1

            elif ent == "Company":
                self.counted__companies += 1

            elif ent == "Person":
                self.counted__persons += 1

            else:
                # flags
                if self.counted__flags.get(ent):
                    self.counted__flags[ent] += 1
                else:
                    self.counted__flags[ent] = 1

    def describe(self):
        """ """
          
        for k, i in self.small_db.items():
            print(i["entity"], i["original_name"])

        # print summary

        print("ADDITIVE COUNT ( INCLUDES PREVIOUS COUNT )")

        print(f"Persons: {self.counted__persons}")
        print(f"Companies: {self.counted__companies}")
        print(f"None: {self.counted__none}")
        print("Other flags:")

        for flag, count in self.counted__flags.items():
            print(f"  {flag}: {count}")

        print("TOTAL: ")
        print(len(self.small_db))

        print("============ CLOSED ==============")


# ---------- idx

start = 2024
end = 2025
 
ParserIDX(start=start, end=end).parse(describe=True)


"""

Results (last 200-300 records out of 20.000 in total)

Person Smith Barbara
Person Smits Hanneke
Company SoFi Technologies, Inc.
Company Solimar Fund LP
Company Southport Acquisition Corp
Company Sovos Brands, Inc.
Person Sponsel David
Company SpringTide Ventures Fund II LP
Company Star Holdings
Company Starco Brands, Inc.
Company State Farm Classic Insurance Co
Company State Farm County Mutual Insurance Co of Texas
Company State Farm Florida Insurance Co
Company State Farm General Insurance Co
Company State Farm Guaranty Insurance Co
Company State Farm Indemnity Co
Company State Farm Lloyds
Person Steele Toni S
Company Steigerwald, Gordon & Koch Inc.
Company StepStone Private Equity LP Secondary Opportunities Ltd
Company StepStone Private Venture & Growth Fund
Company Sterneck Capital Management, LLC
Person Sternlieb Paul
Person Stetson David J.
Person Stewart Niccole
Person Stimart Tryn
Company Stokes Capital Advisors, LLC
Company Stone Ridge Opportunities Fund Feeder LP
Company Stone Ridge Opportunities Fund LP
Person Stout Stephen
Person Straber Renee
Company Strategic Wealth Investment Group, LLC
Person Suever Catherine A
Person Sullivan Lori L
Person Sullivan Timothy Eugene
Company SusGlobal Energy Corp.
Company Sware Convertible Note Round, a Series of Vauban Platform LP
Company Synchrony Card Funding, LLC
Company Synchrony Card Issuance Trust
Company Systems Biology Research Group LLC
Company T. Rowe Price Macro & Absolute Return Strategies Fund LLC
Company T. Rowe Price Macro & Absolute Return Strategies Offshore Fu
('is_fpi',) TAKEDA PHARMACEUTICAL CO LTD
Company TALOS ENERGY INC.
Company TCG Crossover GP II, LLC
Company TECOGEN INC.
Company TETON WESTWOOD FUNDS
Company THFF II REIT LLC
Company THOMPSON INVESTMENT MANAGEMENT, INC.
Company TOP MARK HEALTH PARTNERS LP
Company TRANS LUX Corp
Company TRULEUM, INC.
('is_fpi',) TRX GOLD Corp
Person Tabone Ryan
Company Tangram Impact Fund LP
Person Taylor Alan
Person Taylor Bruce C.
Company Taylor Family Investments, LLC
Person Tennican Elizabeth
Company Texas Mineral Resources Corp.
Company Thread Magic, Inc.
Person Thronson Susan
Person Thurman Alex R.
Person Timm Mark Allen
Person Titterton Lewis H jr
Company Top Mark Capital Partners LP
Company Topel & Distasi Wealth Management, LLC
Company Topia Inc.
Person Townsend Adam J.
Company Trellis Advisors, LLC
Person Trettel James
Company Tributary Capital Management, LLC
Company Triller Corp.
Company Trilogy Master Fund Ltd
Company Trion Fund II Preferred Equity LLC
Company Trion Fund III Preferred Equity LLC
Person Trojan Greg
Company TrueCar, Inc.
Person Turpen Michael C.
Company Twele Capital Management, Inc.
Company U.S. GoldMining Inc.
Company UNDISCOVERED MANAGERS FUNDS
Company UPAY
Company URANIUM ENERGY CORP
Company Ulland Investment Advisors, LLC
Company Unity Growth Series Fund LLC - Fund 003
Company Unity Growth Series Fund LLC - Fund 004
Company Unity Growth Series Fund LLC - Fund 006
Company Universa Black Swan Protection Protocol L LP
Company Universa Black Swan Protection Protocol XII L.P.
Company Universa Black Swan Protection Protocol XLVI L.P.
Company Unrivaled Brands, Inc.
Person Utter Anders
Company VAF2 Scott REIT, Inc.
Company VALICENTI ADVISORY SERVICES INC
Company VALUE HOLDINGS LP
Company VALUE HOLDINGS MANAGEMENT CO. LLC
Company VARIABLE ANNUITY ACCOUNT A
Person VARON LESLIE F
Company VF Portfolio 1 LLC
Company VFS US LLC
Company VHF REIT Holdings LLC
('is_fpi',) VIA optronics AG
('is_fpi',) VOX ROYALTY CORP.
None VTEX
Person Valantine Hannah
Person Vanke Troy J
Company Vaxart, Inc.
Company Vera Bradley, Inc.
Company Veralto Corp
Person Vergis Janet S.
Company Verve Therapeutics, Inc.
Company Vincerx Pharma, Inc.
('is_fpi',) Vinci Partners Investments Ltd.
Person Virani Shafique
Company Virginia Power Fuel Securitization, LLC
Company Vitro Biopharma, Inc.
Company Viva Capital 3 L.P.
Company Volare REIT, LLC
Person Volkmer Bart
Person Voynick Eileen J.
Company W.W. GRAINGER, INC.
Company WAKARA REAL ESTATE FUND LP
Person WARE ALEXANDER H
Person WAYSON KONRAD
Company WEALTHSOURCE PARTNERS, LLC
Company WEG Consolidated, LLC
Person WEISS ELIE
Company WELLCOME TRUST LTD (THE) as trustee of the WELLCOME TRUST
Company WESTFIELD ABSOLUTE RETURN FUND LP
('is_fpi',) WESTPORT FUEL SYSTEMS INC.
Company WEWARDS, INC.
Company WILLIFOOD INVESTMENTS LTD
Company WINDTREE THERAPEUTICS INC /DE/
Company WINDWARD CAPITAL MANAGEMENT CO /CA
Person WINER MICHAEL H
('is_fpi',) WIPRO LTD
Company WJ Wealth Management, LLC
Company WM TECHNOLOGY, INC.
Company WOLF ENERGY SERVICES INC.
Company WOLFF WIESE MAGANA LLC
Person WONG RODERICK
Person Wagner Richard M
Person Wahl Philip R.
Company Wally World Media, Inc
Person Walrath Michael
Company Walter Public Investments Inc.
Person Walters Michael Todd
Person Ward Chicares Elizabeth
Person Washington Rose M
Person Watson David O.
Company Wavelength Labs, Inc.
Company Wealthstar Advisors, LLC
Company Weave Communications, Inc.
Person Wenzel Ilse Dorothea
('is_fpi',) Western Copper & Gold Corp
Person Whitehead James
Company Wildcatters LLC
Company Wilkinson Properties Fund 17, LLC
Person Willey Dawn M.
Person Williams Ethel Isaacs
Company Wolverine Resources Corp.
Company Woofy, Inc.
Company Worthington Steel, Inc.
('is_fpi',) Xinyuan Real Estate Co., Ltd.
Company Xuhang Holdings Ltd
Company YELP INC
Company Yatra Online, Inc.
Company Yext, Inc.
Person Yin Peter
Person Young Camille S
Person Yozamp John Henry
Company Yuenglings Ice Cream Corp
Company ZEROSPO
Company ZEUUS, INC.
Company ZG Energy DART Fund LP
('is_fpi',) ZKH Group Ltd
Person ZWEIER GEORGE
Company ZebRadar SPV One, a Series of Vauban Platform LP
Company Zerve AI seed, a Series of Vauban Platform LP
Company Zeskind Benjamin J.
Company Ziptility, Inc.
Person Zugelder Dan
Company abrdn Global Infrastructure Income Fund
Company phase2body, inc.


ADDITIVE COUNT ( INCLUDES PREVIOUS COUNT )
Persons: 8949
Companies: 10408
None: 29
Other flags:
  ('is_fpi',): 506
  ('is_mmf',): 173
  ('is_fpi', 'is_fpi'): 6
  ('is_insurance',): 1
  ('is_bdc',): 6
  ('is_oef',): 2
TOTAL: 
20080

============ CLOSED ==============

"""
