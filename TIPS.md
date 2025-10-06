
@ParserIDX -- Scaling

I'd suggest to use smth like (my v1 sketch)

@shared_task(ignore_results=True)
def init_historic_entities_by_idx(start, end, in_process=False, finished=False):
    """
    Initialize historic entities from IDX files in the range [start, end].
    Spawns tasks in chunks for memory efficiency. Handles classification via forms, regex, or as FilerAwaitingClassification.
    """

    # Mapping from classification string to model
    INDICATORS = {
        "Company": Company,
        "Person": Person,
        None: FilerAwaitingClassification,  # fallback
        tuple: Company,                     # flags returned by ParserIDX
    }

    # ---------------------------
    # Step 1: Process finishing task (regex classification of pending FilerAwaitingClassification)
    # ---------------------------
    if finished:
        logging.info("============= FINISHING: Transporting FilerAwaitingClassification via REGEX =============")
        qs = FilerAwaitingClassification.objects.values_list("cik", "name")
        logging.info(f"---- {qs.count()} entities yet to be classified")

        for cik, name in qs.iterator():
            class_by_regex = ENTS.classify_by_re(name)
            if not class_by_regex:
                logging.error(
                    f"Unable to identify entity: {name} (CIK {cik}). Will require /submissions/ lookup as last resort."
                )
                continue

            cls = INDICATORS.get(class_by_regex, FilerAwaitingClassification)
            instance = cls()
            instance.cik = cik

            if isinstance(instance, Person):
                instance.original_full_name = name
            else:
                instance.company_name_raw = name

            instance.save()

    # ---------------------------
    # Step 2: Split range and spawn group if not in-process
    # ---------------------------
    if not in_process:
        # Chunk the range by 1 year (or adjust step as needed)
        step = 1
        _range = [(s, min(s + step, end)) for s in range(start, end, step)]

        # Schedule group tasks
        workflow = chord(
            group(init_historic_entities_by_idx.s(s, e, True) for s, e in _range)
        )(init_historic_entities_by_idx.s(start, end, True, True))  # finished callback

        logging.info("========= STARTED HISTORIC ENTITY INIT ==========")
        return True

    # ---------------------------
    # Step 3: Actual parsing process
    # ---------------------------
    results = ParserIDX(start=start, end=end).parse()  # Returns {cik: {"name": ..., "other_names": ..., "entity": ...}}

    for cik, data in results.items():
        name = data.get("name")
        other_names = data.get("other_names", [])
        entity = data.get("entity")

        # Log other names if present
        if other_names:
            logging.info(f"TODO OTHER NAMES: {name} has these: {', '.join(str(n) for n in other_names)}")

        # Determine model class and attributes
        if entity in INDICATORS:
            cls = INDICATORS[entity]
            attrs = []
        else:
            cls = INDICATORS.get(type(entity), Company)
            attrs = entity if isinstance(entity, (tuple, list)) else []

        # Check if entity already exists
        instance = None
        
        if cls is Person:
            
            try:
                instance = Person.objects.get(cik=cik)
                
            except ObjectDoesNotExist:
                instance = cls()
                instance.cik = cik
                instance.original_full_name = name
                
        elif cls is Company:
            
            try:
                instance = Company.objects.get(cik=cik)
                
                # Add new flags if present
                if attrs:
                    for attr in attrs:
                        setattr(instance, attr, True)
                    instance.save()
                
                continue
                
            except ObjectDoesNotExist:
                instance = cls()
                instance.cik = cik
                instance.company_name_raw = name
                
                for attr in attrs:
                    setattr(instance, attr, True)
                    
        else: 
            
            # FilerAwaitingClassification
            instance = cls()
            instance.cik = cik
            instance.name = name

        # Save new instance
        instance.save()
 
