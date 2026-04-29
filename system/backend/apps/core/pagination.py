def page_envelope(items: list[dict], offset: int = 0, limit: int = 20, total: int | None = None):
    return {
        "items": items,
        "total": len(items) if total is None else total,
        "offset": offset,
        "limit": limit,
    }


def empty_page(offset: int = 0, limit: int = 20):
    return page_envelope([], offset=offset, limit=limit, total=0)
