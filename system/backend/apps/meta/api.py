from django.http import JsonResponse
from ninja import Router

from apps.meta import services


router = Router(tags=["Meta"])


def _cached_response(payload: dict):
    return JsonResponse(payload, headers={"Cache-Control": "max-age=600"})


@router.get("/meta/protocols")
def get_meta_protocols(request):
    return _cached_response({"protocols": services.list_protocols()})


@router.get("/meta/scanners")
def get_meta_scanners(request):
    return _cached_response({"scanners": services.list_scanners()})


@router.get("/meta/algorithm-risk-table")
def get_meta_algorithm_risk_table(request):
    return _cached_response({"items": services.get_algorithm_risk_table()})
