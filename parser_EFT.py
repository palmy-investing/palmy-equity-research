class EFTsQuery:
    """

      When to use EFTs?  
        - Exhibit search
        - Items (8-K...)
        
      When to not use EFTs?
        - Blind Company <> CIK match up -- just search q=Morgan Stanley or keyword=Morgan Stanley and find out why
        - Filing search / regular stuff

      Very first version ----
    
    """

    BASE = "https://efts.sec.gov/LATEST/search-index?"
    EX21_1 = BASE + "fileType=21.1"

    def __init__(self, start=2003, end=None):

        if start < 2003:
            raise Exception(f"Likely to not operate in any results pre-2003 - use Paper parser instead")

        if not end:
            # including the entire span (e.g. 2025-2026 == until cur month)
            end = datetime.datetime.now().year + 1

        self.small_db = {}
        self.start_year = start
        self.end_year = end
        self.params = []

        for i in range(start, end):
            self.params.append(f"&startdt={i - 1}-01-01&enddt={i}-01-01")

    def subsidiaries(self, param=None):
        """ returns all (cik: [ex21.1....]) matches who have a path that's a EX 21.1 """

        # You cannot paginate beyond 10 000 rows through the public search-index URL.
        # each result is capped at 10.000
        # Narrow the query so that each sub-query returns < 10 000 docs, then aggregate the slices.
        if not param:

            print(f"====== START from {self.start_year} to {self.end_year} ======")

            for param in self.params:
                self.subsidiaries(param)

            return self.small_db

        response = Request(self.EX21_1 + param).fetch(as_json=True)
        hits = response["hits"]["hits"]

        for _i in hits:

            i = _i["_source"]

            if len(i["ciks"]) != 1:
                print(
                    "ERROR: Why does this file have multiple ciks? "
                    "That should be the case for joints etc. but not for a subsidiary 21.1 file type"
                )
                print(i)
                continue

            cik = i["ciks"][0]

            # allow all form types
            # devise: better scrape 1x too often than loosing potential relations !

            # 59.873 21-1 are coming from 10-K btw. 2003-noww

            if not self.small_db.get(cik):
                self.small_db[cik] = []

            if i["file_type"] != "EX-21.1":
                print("ERROR: Why do we have: {} if it should've only match EX-21.1s?".format(i["file_type"]))
                continue

            # _id contains a concrete result we still have to normalized [TODO]
            self.small_db[cik].append(_i["_id"])


ETFs = EFTsQuery()
ETFs = EFTsQuery(start=2024, end=2025)
print(ETFs.subsidiaries())

# ---> Results in "CIK_SUBSIDIARIES_2024_2025.json"
# (3.7k) iterations in total



 
