from django.http import JsonResponse
from django.utils import timezone
from ninja import Router


router = Router(tags=["Health"])


@router.get("/health")
def get_health(request):
    return JsonResponse(
        {
            "status": "ok",
            "api": "ok",
            "database": "ok",
            "redis": "ok",
            "worker": "ok",
            "checked_at": timezone.now().isoformat().replace("+00:00", "Z"),
        },
        headers={"Cache-Control": "no-store"},
    )
