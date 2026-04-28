from django.urls import path
from ninja import NinjaAPI

from apps.core.errors import register_exception_handlers
from apps.health.api import router as health_router
from apps.jobs.api import router as jobs_router
from apps.meta.api import router as meta_router
from apps.targets.api import router as targets_router


api = NinjaAPI(title="Context-Aware PQC Risk Assessment API", version="0.1.0")
register_exception_handlers(api)

api.add_router("", health_router)
api.add_router("", jobs_router)
api.add_router("", meta_router)
api.add_router("", targets_router)

urlpatterns = [
    path("api/", api.urls),
]
