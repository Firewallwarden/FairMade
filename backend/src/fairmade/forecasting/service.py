"""Owner-scoped fresh projections, independent of model output and HTTP handlers."""

from datetime import timedelta

from sqlalchemy.orm import Session

from fairmade import stock
from fairmade.auth import api_error
from fairmade.database import utcnow
from fairmade.forecasting.domain import calculate
from fairmade.forecasting.repository import observations
from fairmade.forecasting.schemas import ForecastRequest, ForecastResponse
from fairmade.ownership import require_owned_product


def load(
    db: Session, account_id: str, product_id: str, request: ForecastRequest
) -> ForecastResponse:
    product = require_owned_product(db, account_id, product_id)
    now = utcnow()
    today = now.date()
    rows = observations(
        db, account_id, product.id, today - timedelta(days=request.lookback_days), today
    )
    return calculate(
        product_id=product.id,
        product_type=product.product_type,
        selling_unit=product.selling_unit,
        created_on=product.created_at.date(),
        today=today,
        request=request,
        observations=rows,
        stock=stock.balance(db, product.id, now),
    )


def forecast(
    db: Session, account_id: str, product_id: str, request: ForecastRequest
) -> ForecastResponse:
    original = load(db, account_id, product_id, request)
    db.expire_all()
    current = load(db, account_id, product_id, request)
    if current != original:
        raise api_error(409, "FORECAST_CHANGED", "Forecast evidence changed; try again.")
    return current
