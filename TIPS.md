
@ParserIDX -- Scaling

I'd suggest to use smth like (my v1 sketch)

    if not in_process:
        _range = [(s, e) for s, e in range(start, end)]
        group(init_historic_entities_by_idx.s(s, e, True) for s, e in _range).apply_async()
        logging.info("========= STARTED ============")
        return True
    
    results = ParserIDX(start=start, end=end).parse()

    # db lookups - db creations... for 1Y of full EDGAR filer data
