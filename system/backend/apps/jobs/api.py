from ninja import Router, Schema
from pydantic import Field


router = Router(tags=["Jobs"])


class ScanJobCreate(Schema):
    target_ids: list[int] = Field(min_length=1)
    scanners: list[str] = Field(min_length=1)


@router.post("/jobs", response={202: dict})
def create_scan_job(request, payload: ScanJobCreate):
    return 202, {
        "id": 1,
        "kind": "scan_job",
        "resource": {"kind": "scan_job", "id": 1},
        "status": "PENDING",
        "progress": None,
        "started_at": None,
        "cancel_requested_at": None,
        "finished_at": None,
        "result": None,
        "error": None,
    }
