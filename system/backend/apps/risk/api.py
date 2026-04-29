from django.http import JsonResponse
from ninja import Router
from pydantic import Field

from apps.core.schemas import StrictSchema
from apps.jobs.services import serialize_dt
from apps.risk.models import RiskWeights


router = Router(tags=["Risk"])


class RiskWeightsPayload(StrictSchema):
    wA: float = Field(ge=0.5, le=2.0)
    wD: float = Field(ge=0.5, le=2.0)
    wE: float = Field(ge=0.5, le=2.0)
    wL: float = Field(ge=0.5, le=2.0)
    wC: float = Field(ge=0.5, le=2.0)


def _get_weights():
    return RiskWeights.objects.order_by("id").first() or RiskWeights.objects.create()


def _serialize(weights):
    return {
        "wA": weights.wA,
        "wD": weights.wD,
        "wE": weights.wE,
        "wL": weights.wL,
        "wC": weights.wC,
        "updated_at": serialize_dt(weights.updated_at),
    }


@router.get("/risk/weights")
def get_risk_weights(request):
    return _serialize(_get_weights())


@router.put("/risk/weights")
def put_risk_weights(request, payload: RiskWeightsPayload):
    weights = _get_weights()
    for field, value in payload.model_dump().items():
        setattr(weights, field, value)
    weights.save()
    return JsonResponse(_serialize(weights))
