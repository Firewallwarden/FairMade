"""Only an explicitly approved public quality summary may influence public ordering."""

from fairmade.models import MarketplaceListing, PassportPublication

MAX_CANDIDATES = 1000


def with_public_quality(statement):
    return statement.join(
        PassportPublication, PassportPublication.id == MarketplaceListing.published_publication_id
    ).add_columns(PassportPublication.payload["quality_summary"].label("ordering_quality"))
