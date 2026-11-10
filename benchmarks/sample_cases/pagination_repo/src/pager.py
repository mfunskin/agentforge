def collect_pages(fetch_page):
    result = []
    cursor = None
    while True:
        items, cursor = fetch_page(cursor)
        if not items or cursor is None:
            break
        result.extend(items)
    return result
