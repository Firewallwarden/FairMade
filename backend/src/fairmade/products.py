"""Authenticated product management and append-only pricing history."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import select

from fairmade.auth import AUTH_ERRORS, DB, Authenticated, api_error
from fairmade.models import Analysis, Product
from fairmade.pricing.schemas import PricingRequest
from fairmade.pricing.service import calculate
from fairmade.schemas import (
    AnalysisResponse,
    AnalysisSummary,
    ErrorResponse,
    Page,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)

router = APIRouter(
    prefix="/api/v1/products",
    tags=["products"],
    responses={**AUTH_ERRORS, 404: {"model": ErrorResponse}},
)
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


def owned_product(db: DB, auth: Authenticated, product_id: UUID) -> Product:
    product = db.scalar(
        select(Product).where(
            Product.id == str(product_id),
            Product.seller_id == auth.seller_id,
        )
    )
    if product is None:
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    return product


@router.post("", response_model=ProductResponse, status_code=201)
def create_product(body: ProductCreate, db: DB, auth: Authenticated) -> Product:
    product = Product(seller_id=auth.seller_id, **body.model_dump())
    db.add(product)
    db.commit()
    return product


@router.get("", response_model=Page[ProductResponse])
def list_products(db: DB, auth: Authenticated, limit: Limit = 20, offset: Offset = 0) -> dict:
    items = db.scalars(
        select(Product)
        .where(Product.seller_id == auth.seller_id)
        .order_by(Product.created_at.desc(), Product.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: UUID, db: DB, auth: Authenticated) -> Product:
    return owned_product(db, auth, product_id)


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: UUID,
    body: ProductUpdate,
    db: DB,
    auth: Authenticated,
) -> Product:
    product = owned_product(db, auth, product_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(product, key, value)
    db.commit()
    return product


@router.post("/{product_id}/analyses", response_model=AnalysisResponse, status_code=201)
def save_analysis(
    product_id: UUID,
    body: PricingRequest,
    db: DB,
    auth: Authenticated,
) -> Analysis:
    product = owned_product(db, auth, product_id)
    result = calculate(body)
    analysis = Analysis(
        product_id=product.id,
        calculation_version=result.calculation_version,
        product_snapshot=ProductResponse.model_validate(product).model_dump(mode="json"),
        inputs=body.model_dump(mode="json"),
        result=result.model_dump(mode="json"),
    )
    db.add(analysis)
    db.commit()
    return analysis


@router.get("/{product_id}/analyses", response_model=Page[AnalysisSummary])
def list_analyses(
    product_id: UUID,
    db: DB,
    auth: Authenticated,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict:
    owned_product(db, auth, product_id)
    items = db.scalars(
        select(Analysis)
        .where(Analysis.product_id == str(product_id))
        .order_by(Analysis.created_at.desc(), Analysis.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/{product_id}/analyses/{analysis_id}", response_model=AnalysisResponse)
def get_analysis(
    product_id: UUID,
    analysis_id: UUID,
    db: DB,
    auth: Authenticated,
) -> Analysis:
    owned_product(db, auth, product_id)
    analysis = db.scalar(
        select(Analysis).where(
            Analysis.id == str(analysis_id),
            Analysis.product_id == str(product_id),
        )
    )
    if analysis is None:
        raise api_error(404, "NOT_FOUND", "Resource not found.")
    return analysis
