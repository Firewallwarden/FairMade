"""Read-only structural validation of the combined pending backend."""

import json
import re
from pathlib import Path
from urllib.parse import unquote

from alembic.config import Config
from alembic.script import ScriptDirectory

from fairmade.main import create_app

root = Path(__file__).resolve().parents[1]
schema = create_app("sqlite://").openapi()
ids = []
for path in schema["paths"].values():
    for operation in path.values():
        if isinstance(operation, dict) and "operationId" in operation:
            ids.append(operation["operationId"])
assert len(ids) == len(set(ids)), "Duplicate OpenAPI operation identifier"


def check_refs(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "$ref" and item.startswith("#/"):
                current = schema
                for component in item[2:].split("/"):
                    current = current[component.replace("~1", "/").replace("~0", "~")]
            else:
                check_refs(item)
    elif isinstance(value, list):
        for item in value:
            check_refs(item)


check_refs(schema)
components = schema["components"]["schemas"]
required = {
    "insights",
    "cost_calendar",
    "bundles",
    "forecast",
    "recommendations",
    "include_recipe_inputs",
    "pricing_review_id",
}
for name in ("SellerQuestion", "SellerScope"):
    assert required <= components[name]["properties"].keys(), name
for name in ("BuyerQuestion", "BuyerScope"):
    assert {"listing_ids", "basket", "bundles"} <= components[name]["properties"].keys(), name
assert "DraftContent" in components
assert "composition" in components["DraftContent"]["properties"]
paths = schema["paths"]
for suffix in (
    "insights",
    "cost-calendar",
    "forecasts",
    "supplier-recommendations",
    "pricing-recommendations",
):
    assert f"/api/v1/products/{'{product_id}'}/{suffix}" in paths
assert "/api/v1/buyer/bundles/suggest" in paths
assert "/api/v1/seller/bundles/suggest" in paths
assert "/api/v1/orders/{order_id}/messages" in paths
heads = ScriptDirectory.from_config(Config(str(root / "backend/alembic.ini"))).get_heads()
assert heads == ["0029"], heads

json_files = list((root / "backend/examples").rglob("*.json"))
for file in json_files:
    json.loads(file.read_text(encoding="utf-8"))

broken = []
checked = 0
for file in [*(root / "docs").rglob("*.md"), root / "backend/README.md"]:
    for target in re.findall(r"\]\(([^)]+)\)", file.read_text(encoding="utf-8")):
        target = target.strip("<>").split("#", 1)[0]
        if not target or "://" in target or target.startswith(("mailto:", "data:")):
            continue
        checked += 1
        if not (file.parent / unquote(target)).exists():
            broken.append(f"{file.relative_to(root)} -> {target}")
assert not broken, broken
print(f"OpenAPI: {len(ids)} unique operations, all local references resolved")
print(f"Scopes: every pending seller/buyer extension retained; Alembic head: {heads[0]}")
print(f"Examples: {len(json_files)} valid JSON files; docs: {checked} local links valid")
