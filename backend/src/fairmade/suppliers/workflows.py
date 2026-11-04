"""Save a sourcing decision's exact requirements, evidence and calculated result."""

from sqlalchemy.orm import Session

from fairmade.evidence import today
from fairmade.models import Product, SourcingInput, SupplierComparison
from fairmade.schemas import ProductResponse
from fairmade.suppliers import repository
from fairmade.suppliers.schemas import (
    SourcingInputResponse,
    SupplierComparisonRequest,
    SupplierQuoteSnapshot,
)
from fairmade.suppliers.service import COMPARISON_VERSION, compare_suppliers


def save_comparison(
    db: Session,
    product: Product,
    sourcing_input: SourcingInput,
    request: SupplierComparisonRequest,
) -> SupplierComparison:
    repository.lock_revision(db, sourcing_input, request.expected_rule_revision)
    quotes = repository.selected_quotes(db, sourcing_input.id, request.quote_ids)
    input_snapshot = SourcingInputResponse.model_validate(sourcing_input)
    as_of_date = today()
    result = compare_suppliers(
        request,
        [SupplierQuoteSnapshot(id=quote.id, details=quote.details) for quote in quotes],
        input_snapshot.rules,
        input_snapshot.rule_revision,
        as_of_date,
    )
    report = SupplierComparison(
        sourcing_input_id=sourcing_input.id,
        as_of_date=as_of_date,
        rule_revision=sourcing_input.rule_revision,
        comparison_version=COMPARISON_VERSION,
        basis="seller_reported_unverified",
        request_snapshot=request.model_dump(mode="json"),
        sourcing_input_snapshot=input_snapshot.model_dump(mode="json"),
        product_snapshot=ProductResponse.model_validate(product).model_dump(mode="json"),
        result=result.model_dump(mode="json"),
    )
    db.add(report)
    db.commit()
    return report
