"""Bounded exact pair totals; affinity and observed purchases cannot override exclusions."""

from itertools import combinations
from typing import NamedTuple, TypedDict

from fairmade.orders.domain import MAX_SUBTOTAL_MINOR


class CandidateScore(TypedDict):
    price_minor: int
    rank: tuple[int, int, int]


class Pair(NamedTuple):
    rank: tuple[int, ...]
    subtotal_minor: int
    left: str
    right: str
    observed_orders: int


def pairs(
    eligible: dict[str, CandidateScore],
    observed: dict[tuple[str, str], int],
    budget_minor: int | None,
    seller: bool,
) -> tuple[list[Pair], int]:
    ranked = []
    budget_excluded = 0
    for left, right in combinations(sorted(eligible), 2):
        first, second = eligible[left], eligible[right]
        subtotal = first["price_minor"] + second["price_minor"]
        if subtotal > MAX_SUBTOTAL_MINOR or (budget_minor is not None and subtotal > budget_minor):
            budget_excluded += 1
            continue
        affinity = tuple(a + b for a, b in zip(first["rank"], second["rank"], strict=True))
        count = observed.get((left, right), 0)
        rank = (-count,) if seller else tuple(-value for value in affinity)
        ranked.append(Pair(rank, subtotal, left, right, count))
    ranked.sort()
    return ranked, budget_excluded
