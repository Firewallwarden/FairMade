"""Bounded pagination shared by API modules."""

from typing import Annotated

from fastapi import Query

Limit = Annotated[int, Query(ge=1, le=100)]
# Reject impractical integer query parameters before SQLite binding can overflow.
Offset = Annotated[int, Query(ge=0, le=9_223_372_036_854_775_807)]
