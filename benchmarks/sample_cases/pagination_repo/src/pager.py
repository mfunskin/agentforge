def collect_pages(fetch_page):
    result = []
    cursor = None
    seen = set()
    while True:
        items, next_cursor = fetch_page(cursor)
        if not items or next_cursor is None or next_cursor in seen:
            break
        result.extend(items)
        seen.add(next_cursor)
        cursor = next_cursor
    return result
