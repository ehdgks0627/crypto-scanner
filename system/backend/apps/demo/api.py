from django.core.management import call_command
from django.http import JsonResponse
from ninja import Router
from pydantic import Field

from apps.core.schemas import StrictSchema
from apps.demo import services


router = Router(tags=["Demo"])


class DemoResetPayload(StrictSchema):
    seed_database: bool = Field(default=True)
    reset_session: bool = Field(default=True)


@router.post("/demo/reset")
def reset_demo(request, payload: DemoResetPayload):
    if payload.seed_database:
        call_command("seed_testbed_demo", "--reset")
        call_command("seed_demo_labels")
    if payload.reset_session:
        services.reset_session()
    return JsonResponse(services.demo_session(), status=200)


@router.get("/demo/session")
def get_demo_session(request):
    return services.demo_session()


@router.post("/demo/session/start")
def start_demo_session(request):
    services.reset_session()
    return JsonResponse(services.demo_session(), status=200)


@router.post("/demo/session/next")
def advance_demo_session(request):
    return JsonResponse(services.advance_session(), status=200)


@router.get("/demo/session/events")
def get_demo_events(request):
    return {"items": services.demo_events()}
