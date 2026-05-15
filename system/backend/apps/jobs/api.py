from typing import Literal

from django.db import transaction
from django.http import JsonResponse
from ninja import Query, Router
from pydantic import Field

from apps.core.errors import error_response
from apps.core.pagination import empty_page, page_envelope
from apps.core.schemas import StrictSchema
from apps.jobs import services
from apps.jobs.models import AsyncJob, ScanJob


router = Router(tags=["Jobs"])


JobStatusParam = Literal["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]
JobKindParam = Literal["scan_job", "discovery", "recompute"]
JobSortParam = Literal["id", "-id", "created_at", "-created_at", "finished_at", "-finished_at"]
ScannerId = Literal[
    "network",
    "agent.cert_store",
    "agent.pkg_keyring",
    "agent.ssh_userkey",
    "agent.ssh_config",
    "agent.keystore",
    "agent.app_cert_files",
    "agent.private_key_files",
    "agent.app_config",
]


class ScanJobCreate(StrictSchema):
    target_ids: list[int] = Field(min_length=1)
    scanners: list[ScannerId] = Field(min_length=1)


@router.get("/jobs")
def list_jobs(
    request,
    status: JobStatusParam | None = None,
    kind: JobKindParam | None = None,
    sort: JobSortParam = "-id",
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    queryset = AsyncJob.objects.all()
    if status:
        queryset = queryset.filter(status=status)
    if kind:
        queryset = queryset.filter(kind=kind)
    queryset = queryset.order_by(sort)
    total = queryset.count()
    items = [services.serialize_job(job) for job in queryset[offset : offset + limit]]
    if not items:
        return empty_page(offset=offset, limit=limit)
    return page_envelope(items, offset=offset, limit=limit, total=total)


@router.post("/jobs", response={202: dict})
def create_scan_job(request, payload: ScanJobCreate):
    try:
        with transaction.atomic():
            async_job = AsyncJob.objects.create(
                kind="scan_job",
                status=AsyncJob.PENDING,
                request_payload=payload.model_dump(),
            )
            scan_job = ScanJob.objects.create(
                async_job=async_job,
                target_ids=payload.target_ids,
                scanner_selection=payload.scanners,
            )
            async_job.resource_id = scan_job.id
            async_job.save(update_fields=["resource_id"])
            services.enqueue_scan_job(scan_job)
    except services.EnqueueUnavailable:
        return error_response("service_unavailable", "Worker queue is unavailable.", status=503)
    return 202, services.serialize_job(async_job)


@router.get("/jobs/{job_id}")
def get_job(request, job_id: int):
    try:
        async_job = AsyncJob.objects.get(id=job_id)
    except AsyncJob.DoesNotExist:
        return error_response("not_found", "Resource not found.", status=404)
    return JsonResponse(services.serialize_job(async_job), headers={"Cache-Control": "no-store"})


@router.post("/jobs/{job_id}/cancel")
def cancel_job(request, job_id: int):
    try:
        with transaction.atomic():
            async_job = AsyncJob.objects.select_for_update().get(id=job_id)
            if not services.request_cancel(async_job):
                return error_response(
                    "job_not_cancellable",
                    "Job is not cancellable.",
                    {"job_id": async_job.id, "kind": async_job.kind, "status": async_job.status},
                    status=409,
                )
            async_job.refresh_from_db()
    except AsyncJob.DoesNotExist:
        return error_response("not_found", "Resource not found.", status=404)
    return JsonResponse(services.serialize_job(async_job), status=202)


@router.get("/jobs/{job_id}/logs")
def list_job_logs(
    request,
    job_id: int,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    try:
        async_job = AsyncJob.objects.get(id=job_id)
    except AsyncJob.DoesNotExist:
        return error_response("not_found", "Resource not found.", status=404)
    if not hasattr(async_job, "scan_job"):
        return page_envelope([], offset=offset, limit=limit, total=0)
    queryset = async_job.run_logs.select_related("target").filter(target__isnull=False).order_by("id")
    total = queryset.count()
    items = [services.serialize_run_log(log) for log in queryset[offset : offset + limit]]
    return page_envelope(items, offset=offset, limit=limit, total=total)
