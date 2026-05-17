from django.urls import path
from ninja import NinjaAPI

from apps.agents.api import router as agents_router
from apps.assets.api import router as assets_router
from apps.core.errors import register_exception_handlers
from apps.dashboard.api import router as dashboard_router
from apps.discoveries.api import router as discoveries_router
from apps.health.api import router as health_router
from apps.jobs.api import router as jobs_router
from apps.meta.api import router as meta_router
from apps.performance.api import router as performance_router
from apps.risk.api import router as risk_router
from apps.snapshots.api import router as snapshots_router
from apps.targets.api import router as targets_router


api = NinjaAPI(title="Context-Aware PQC Risk Assessment API", version="0.1.0")
register_exception_handlers(api)

api.add_router("", agents_router)
api.add_router("", assets_router)
api.add_router("", dashboard_router)
api.add_router("", discoveries_router)
api.add_router("", health_router)
api.add_router("", jobs_router)
api.add_router("", meta_router)
api.add_router("", performance_router)
api.add_router("", risk_router)
api.add_router("", snapshots_router)
api.add_router("", targets_router)

urlpatterns = [
    path("api/", api.urls),
]
