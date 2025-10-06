
@ParserIDX -- Scaling

I'd suggest to use smth like (my v1 sketch)

    # process
    # spawn Company | Person or add one or more new flags
    # or continue create FilerAwaitingClassification
    #   --- And see if the next iteration e.g. finds "cik" + flag = company 
    #        del FilerAwaitingClassification and add Company new !

    if not in_process:
        _range = [(s, e) for s, e in range(start, end)]
        group(init_historic_entities_by_idx.s(s, e, True) for s, e in _range).apply_async()
        logging.info("========= STARTED ============")
        return True
    
    results = ParserIDX(start=start, end=end).parse()

