"""Private input projection and exact public declaration facts; never infer final contents."""

from sqlalchemy.orm import Session

from fairmade.assistants.schemas import Evidence, Paragraph
from fairmade.auth import api_error
from fairmade.models import Product, ProductRecipe
from fairmade.recipes.schemas import RecipeData

TITLE = "Private recorded recipe production inputs"
POLICY = [
    "Recipe inputs are private seller records, not declared finished-product ingredients.",
    "Feed, processing aids, waste and packaging may be production inputs; "
    "do not infer their presence or quantity in the final product.",
    "Recorded quantities describe the whole recipe's raw usage, including waste; "
    "do not infer per-unit composition, ingredient proportions or nutritional values.",
    "No allergen absence, safety, health benefit, suitability or certification is established.",
    "No recipe, stock, production-cost analysis, Quality Lock or publication is changed.",
]


def recipe_evidence(db: Session, product: Product) -> Evidence:
    row = db.get(ProductRecipe, product.id)
    data = {"product_id": product.id, "status": "missing_recipe", "inputs": [], "policy": POLICY}
    if row is not None:
        recipe = RecipeData.model_validate(row.content)
        if len(recipe.ingredients) > 20:
            raise api_error(
                409, "RECIPE_EXPLANATION_TOO_LARGE", "Recipe exceeds explanation scope."
            )
        # Explicit allowlist: purchase costs, labor, instructions and notes never enter this fact.
        data.update(
            status="recorded_inputs",
            recipe_revision=row.revision,
            sellable_units=recipe.sellable_units,
            inputs=[
                {"label": item.label, "raw_quantity": item.quantity.model_dump(mode="json")}
                for item in recipe.ingredients
            ],
        )
    return Evidence(key="e1", title=TITLE, basis="seller_recorded_unverified", data=data)


def context(fact: Evidence) -> dict | None:
    if fact.title != TITLE:
        return None
    return {
        "status": fact.data["status"],
        "production_input_labels": [row["label"] for row in fact.data["inputs"]],
        "policy": fact.data["policy"],
    }


def public_context(passport: dict) -> dict:
    declaration = passport.get("composition")
    if declaration is None:
        return {
            "status": "not_disclosed",
            "policy": "Composition is unknown; "
            "never infer ingredients, materials or safety from names.",
        }
    return {
        "status": "seller_declared_unverified",
        "completeness": declaration["completeness"],
        "items": [
            {key: value for key, value in item.items() if key != "declared_quantity"}
            for item in declaration["items"]
        ],
        "policy": "Roles/specifications/completeness are seller declarations, not verified facts. "
        "No omitted allergen absence, safety, nutrition, "
        "compatibility or suitability is inferred.",
    }


def statements(fact: Evidence) -> list[Paragraph]:
    texts = []
    if fact.title == TITLE:
        if fact.data["status"] == "missing_recipe":
            texts.append(
                "No recorded recipe inputs are available; finished composition remains unknown."
            )
        for row in fact.data["inputs"]:
            value = row["raw_quantity"]
            texts.append(
                f"Recorded production input {row['label']}: raw quantity {value['value']} "
                f"{value['unit']} for a recipe reporting {fact.data['sellable_units']} "
                "sellable units. This is not finished-product composition."
            )
    elif fact.title == "Currently approved public listing and Passport":
        declaration = fact.data["passport"]["payload"].get("composition")
        if declaration is None:
            return []
        unit = fact.data["payload"]["product"]["selling_unit"]
        texts.append(
            f"Seller-declared composition completeness: {declaration['completeness']}. "
            "This is unverified and does not establish allergen absence or safety."
        )
        for item in declaration["items"]:
            text = f"Seller-declared {item['kind']}: {item['label']}."
            if item.get("reported_role"):
                text += " Reported role: " + item["reported_role"] + "."
            if item.get("reported_specification"):
                text += " Reported specification: " + item["reported_specification"] + "."
            quantity = item.get("declared_quantity")
            if quantity:
                text += f" Declared quantity per {unit}: {quantity['value']} {quantity['unit']}."
            texts.append(text)
    return [Paragraph(text=text, evidence_keys=[fact.key]) for text in texts]
