class EFTsQuery:
    """

        - For exhibit search
        - For items search
        - Not for filing search
        - Not for company search
        
    """

    BASE = "https://efts.sec.gov/LATEST/search-index?"
    EX21_1 = BASE + "fileType=EX-21.1"

    def __init__(self, start=2003, end=None):
        if start < 2003:
            raise Exception("Likely to not operate in any results pre-2003 - use Paper parser instead")

        if not end:
            # include current year fully
            end = datetime.datetime.now().year

        # go until one year *after* the end, to capture full final year
        self.start_year = start
        self.end_year = end
        self.small_db = {}
        self.joints = {}
        self.params = []

        for year in range(self.start_year + 1, self.end_year + 2):
            self.params.append(f"&startdt={year - 1}-01-01&enddt={year}-01-01")

    def subsidiaries(self, param=None):
        """

         Takes care of:
             - Single filer sharing EX21.1 list (the 95% case)
             - Joint filer sharing EX21.1 list (the 5% case)
             - Multiple 21s per filer/joint using CIK as primary key
            
        """

        if not param:
            print(f"====== START from {self.start_year} to {self.end_year} ======")
            for param in self.params:
                self.subsidiaries(param)
            return self.small_db

        print(f"Querying: {param}")

        base_url = self.EX21_1 + param
        from_offset = 0
        total_hits = None

        while True:
            url = f"{base_url}&from={from_offset}"
            response = Request(url).fetch(as_json=True)

            hits = response.get("hits", {}).get("hits", [])
            total_hits = response["hits"]["total"]["value"]
            if not hits:
                break

            for _i in hits:
                i = _i["_source"]

                ciks = i["ciks"]

                # Pick the first CIK as the key; this is typically the parent
                if not ciks:
                    print("ERROR: Skipping filing with no CIKs:", i)
                    continue

                file_type = (i.get("file_type") or "").strip().upper()

                # Skip any non-EX-21.1 exhibits — strictly match to avoid EX-99.x etc.
                if file_type != "EX-21.1":
                    print(f"ERROR: Skipping non-21.1 exhibit type: {file_type}")
                    continue

                cik = ciks[0]

                # A true EX-21.1 should normally have a single filer CIK (the parent)
                if len(ciks) != 1:
                    print(f"-- Multiple CIKs found - creating/inserting the tuple joint")

                    # Don't skip; sometimes joint 10-Ks include shared 21.1 exhibits.
                    # The information of seeing a joint group is already good for our DB
                    #       because joint group filing is evidence for a potentially meaningful relationship

                    cik = tuple(ciks)

                if not self.small_db.get(cik):
                    self.small_db[cik] = []

                self.small_db[cik].append(_i["_id"])

            from_offset += 100
            if from_offset >= total_hits:
                break

        print(f"  Retrieved {from_offset} / {total_hits} results for {param}")


# ------- TESTING

EFTs = EFTsQuery(start=2024, end=2025) 
original_dict = EFTs.subsidiaries()

import json

# --- temporary shit to work with .json schema

fixed = {}
for key, files in original_dict.items():
    # key might be a tuple → make it a string
    new_key = "_".join(key) if isinstance(key, tuple) else str(key)
    fixed[new_key] = files

print(json.dumps(fixed, indent=2))

# ---> Results in "CIK_SUBSIDIARIES_2024_2025.json"
# -- 116 joint groups, 3.725 single-filers
