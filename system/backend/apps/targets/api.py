from ninja import Query, Router


router = Router(tags=["Targets"])


@router.get("/targets")
def list_targets(request, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    return {
        "items": [],
        "total": 0,
        "offset": offset,
        "limit": limit,
    }
