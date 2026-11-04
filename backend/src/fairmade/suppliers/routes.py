"""Private seller APIs. Supplier source references never trigger network calls."""

from uuid import UUID

from fastapi import APIRouter

from fairmade.auth import AUTH_ERRORS, DB, VerifiedSeller
from fairmade.models import SourcingInput, SupplierComparison, SupplierQuote
from fairmade.ownership import require_owned_product
from fairmade.pagination import Limit, Offset
from fairmade.quality.schemas import ReplaceQualityLocks
from fairmade.schemas import ErrorResponse, Page
from fairmade.suppliers import repository
from fairmade.suppliers.schemas import (
    SourcingInputCreate,
    SourcingInputResponse,
    SupplierComparisonRequest,
    SupplierQuoteCreate,
    SupplierQuoteResponse,
    SupplierReportResponse,
    SupplierReportSummary,
)
from fairmade.suppliers.workflows import save_comparison

router = APIRouter(
    prefix="/api/v1/products/{product_id}/sourcing-inputs",
    tags=["supplier comparisons"],
    responses={**AUTH_ERRORS, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
CONFLICT = {409: {"model": ErrorResponse}}


@router.post("", response_model=SourcingInputResponse, status_code=201)
def create_input(
    product_id: UUID,
    body: SourcingInputCreate,
    db: DB,
    seller: VerifiedSeller,
) -> SourcingInput:
    product = require_owned_product(db, seller.id, product_id)
    sourcing_input = SourcingInput(product_id=product.id, label=body.label)
    db.add(sourcing_input)
    db.commit()
    return sourcing_input


@router.get("", response_model=Page[SourcingInputResponse])
def list_inputs(
    product_id: UUID,
    db: DB,
    seller: VerifiedSeller,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict:
    product = require_owned_product(db, seller.id, product_id)
    items = repository.list_inputs(db, product.id, limit, offset)
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/{input_id}", response_model=SourcingInputResponse)
def get_input(
    product_id: UUID,
    input_id: UUID,
    db: DB,
    seller: VerifiedSeller,
) -> SourcingInput:
    _, sourcing_input = repository.require_input(db, seller.id, product_id, input_id)
    return sourcing_input


@router.put(
    "/{input_id}/quality-locks",
    response_model=SourcingInputResponse,
    responses=CONFLICT,
)
def replace_requirements(
    product_id: UUID,
    input_id: UUID,
    body: ReplaceQualityLocks,
    db: DB,
    seller: VerifiedSeller,
) -> SourcingInput:
    _, sourcing_input = repository.require_input(db, seller.id, product_id, input_id)
    repository.replace_rules(
        db,
        sourcing_input,
        body.expected_revision,
        [rule.model_dump(mode="json") for rule in body.rules],
    )
    db.commit()
    return sourcing_input


@router.post("/{input_id}/supplier-quotes", response_model=SupplierQuoteResponse, status_code=201)
def create_quote(
    product_id: UUID,
    input_id: UUID,
    body: SupplierQuoteCreate,
    db: DB,
    seller: VerifiedSeller,
) -> SupplierQuote:
    _, sourcing_input = repository.require_input(db, seller.id, product_id, input_id)
    quote = SupplierQuote(
        sourcing_input_id=sourcing_input.id,
        basis="seller_reported_unverified",
        details=body.model_dump(mode="json"),
    )
    db.add(quote)
    db.commit()
    return quote


@router.get("/{input_id}/supplier-quotes", response_model=Page[SupplierQuoteResponse])
def list_quotes(
    product_id: UUID,
    input_id: UUID,
    db: DB,
    seller: VerifiedSeller,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict:
    _, sourcing_input = repository.require_input(db, seller.id, product_id, input_id)
    items = repository.list_quotes(db, sourcing_input.id, limit, offset)
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/{input_id}/supplier-quotes/{quote_id}", response_model=SupplierQuoteResponse)
def get_quote(
    product_id: UUID,
    input_id: UUID,
    quote_id: UUID,
    db: DB,
    seller: VerifiedSeller,
) -> SupplierQuote:
    _, sourcing_input = repository.require_input(db, seller.id, product_id, input_id)
    return repository.selected_quotes(db, sourcing_input.id, [quote_id])[0]


@router.post(
    "/{input_id}/supplier-comparisons",
    response_model=SupplierReportResponse,
    status_code=201,
    responses=CONFLICT,
)
def create_report(
    product_id: UUID,
    input_id: UUID,
    body: SupplierComparisonRequest,
    db: DB,
    seller: VerifiedSeller,
) -> SupplierComparison:
    product, sourcing_input = repository.require_input(db, seller.id, product_id, input_id)
    return save_comparison(db, product, sourcing_input, body)


@router.get("/{input_id}/supplier-comparisons", response_model=Page[SupplierReportSummary])
def list_reports(
    product_id: UUID,
    input_id: UUID,
    db: DB,
    seller: VerifiedSeller,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict:
    _, sourcing_input = repository.require_input(db, seller.id, product_id, input_id)
    items = repository.list_reports(db, sourcing_input.id, limit, offset)
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/{input_id}/supplier-comparisons/{report_id}", response_model=SupplierReportResponse)
def get_report(
    product_id: UUID,
    input_id: UUID,
    report_id: UUID,
    db: DB,
    seller: VerifiedSeller,
) -> SupplierComparison:
    _, sourcing_input = repository.require_input(db, seller.id, product_id, input_id)
    return repository.require_report(db, sourcing_input.id, report_id)
