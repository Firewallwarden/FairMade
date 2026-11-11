# Consistent economic selection across seller reports

When seller questions or saved scopes combine pricing_review_id with insights,
both reports now use the pricing review's selected analysis. A newer saved
analysis does not silently become the insight baseline. The calendar remains a
separate historical window, explicitly labeled as save-time snapshots.

Without a pricing review, explicit analysis_id and default latest-analysis
behavior are unchanged. A conflicting explicit analysis_id still fails with
PRICING_SOURCE_MISMATCH before inference. Current quality/source checks, owner
authorization, exact financial facts and qualitative model projections remain.

This additive compatibility fix depends on #38 through #44, #50, #54 and #55.
The main-targeted PR contains those prerequisites and remains draft until they
are integrated and its remaining diff is refreshed and validated. No migration,
provider, endpoint, schema field or disclosure policy is added.

Regression checks cover review-selected, explicitly selected and latest analysis,
plus two saved turns across application restarts and qualitative projections.
The prior merged implementation reproduced a mismatched analysis identifier;
using the already resolved selected_id fixes it without duplicating selection.
