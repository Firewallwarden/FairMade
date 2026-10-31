"""Private append-only price observations and immutable comparison reports."""

from uuid import UUID

from fastapi import APIRouter
from fastapi.exceptions import RequestValidationError
from sqlalchemy import select

from fairmade.auth import AUTH_ERRORS, DB, VerifiedSeller, api_error
from fairmade.comparisons.schemas import (
    ComparisonRequest,
    ObservationCreate,
    ObservationResponse,
    ObservationSnapshot,
    ReportResponse,
    ReportSummary,
    today,
)
from fairmade.comparisons.service import COMPARISON_VERSION, compare
from fairmade.comparisons.units import named_unit_matches
from fairmade.models import PriceComparison, PriceObservation
from fairmade.products import Limit, Offset, owned_product
from fairmade.schemas import ErrorResponse, Page, ProductResponse

router = APIRouter(
    prefix="/api/v1/products/{product_id}",
    tags=["finished-product comparisons"],
    responses={**AUTH_ERRORS, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)


@router.post("/price-observations", status_code=201, response_model=ObservationResponse)
def create_observation(
    product_id: UUID,
    body: ObservationCreate,
    db: DB,
    seller: VerifiedSeller,
) -> PriceObservation:
    product = owned_product(db, seller, product_id)
    observation = PriceObservation(
        product_id=product.id,
        details=body.model_dump(mode="json"),
        basis="seller_reported_unverified",
    )
    db.add(observation)
    db.commit()
    return observation


@router.get("/price-observations", response_model=Page[ObservationResponse])
def list_observations(
    product_id: UUID,
    db: DB,
    seller: VerifiedSeller,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict:
    product = owned_product(db, seller, product_id)
    items = db.scalars(
        select(PriceObservation)
        .where(PriceObservation.product_id == product.id)
        .order_by(PriceObservation.created_at.desc(), PriceObservation.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/price-observations/{observation_id}", response_model=ObservationResponse)
def get_observation(
    product_id: UUID,
    observation_id: UUID,
    db: DB,
    seller: VerifiedSeller,
) -> PriceObservation:
    product = owned_product(db, seller, product_id)
    observation = db.scalar(
        select(PriceObservation).where(
            PriceObservation.id == str(observation_id),
            PriceObservation.product_id == product.id,
        )
    )
    if observation is None:
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    return observation


@router.post("/price-comparisons", status_code=201, response_model=ReportResponse)
def create_report(
    product_id: UUID,
    body: ComparisonRequest,
    db: DB,
    seller: VerifiedSeller,
) -> PriceComparison:
    product = owned_product(db, seller, product_id)
    if not named_unit_matches(product.product_type, body.target_quantity.unit):
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("body", "target_quantity", "unit"),
                    "msg": "Named egg/dozen/loaf units must match the target product type",
                    "input": body.target_quantity.unit,
                }
            ]
        )
    observations = db.scalars(
        select(PriceObservation).where(
            PriceObservation.product_id == product.id,
            PriceObservation.id.in_([str(value) for value in body.observation_ids]),
        )
    ).all()
    if len(observations) != len(body.observation_ids):
        # Do not disclose whether an ID belongs to a different product or seller.
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    by_id = {item.id: item for item in observations}
    snapshots = [
        ObservationSnapshot(id=value, details=by_id[str(value)].details)
        for value in body.observation_ids
    ]
    as_of_date = today()
    result = compare(body, snapshots, product.product_type, as_of_date)
    report = PriceComparison(
        product_id=product.id,
        comparison_version=COMPARISON_VERSION,
        as_of_date=as_of_date,
        basis="seller_reported_unverified",
        request_snapshot=body.model_dump(mode="json"),
        product_snapshot=ProductResponse.model_validate(product).model_dump(mode="json"),
        result=result.model_dump(mode="json"),
    )
    db.add(report)
    db.commit()
    return report


@router.get("/price-comparisons", response_model=Page[ReportSummary])
def list_reports(
    product_id: UUID,
    db: DB,
    seller: VerifiedSeller,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict:
    product = owned_product(db, seller, product_id)
    items = db.scalars(
        select(PriceComparison)
        .where(PriceComparison.product_id == product.id)
        .order_by(PriceComparison.created_at.desc(), PriceComparison.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/price-comparisons/{report_id}", response_model=ReportResponse)
def get_report(
    product_id: UUID,
    report_id: UUID,
    db: DB,
    seller: VerifiedSeller,
) -> PriceComparison:
    product = owned_product(db, seller, product_id)
    report = db.scalar(
        select(PriceComparison).where(
            PriceComparison.id == str(report_id),
            PriceComparison.product_id == product.id,
        )
    )
    if report is None:
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    return report
