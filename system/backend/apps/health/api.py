from django.http import JsonResponse
from django.utils import timezone
from ninja import Router

from apps.health import services


router = Router(tags=["Health"])


def _aggregate_status(components: dict[str, str]) -> str:
    if components["api"] == "down" or components["database"] == "down":
        return "down"
    if any(status in {"degraded", "down"} for status in components.values()):
        return "degraded"
    return "ok"


@router.get("/health")
def get_health(request):
    components = services.get_component_statuses()
    return JsonResponse(
        {
            "status": _aggregate_status(components),
            "api": components["api"],
            "database": components["database"],
            "redis": components["redis"],
            "worker": components["worker"],
            "checked_at": timezone.now().isoformat().replace("+00:00", "Z"),
        },
        headers={"Cache-Control": "no-store"},
    )
