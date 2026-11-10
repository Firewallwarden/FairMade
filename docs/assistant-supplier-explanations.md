# Seller assistant supplier explanations

This feature builds on assistant foundation #38 and history extension #39.
Its main-targeted PR remains draft while prerequisites are unmerged.

The existing seller question's supplier_report_id selects one owned report.
No extra request fields or new public endpoint are introduced. Selected quote
snapshots are re-evaluated using current sourcing-input requirements and today's
UTC date; the original immutable report is not rewritten.

The supplier evidence now separates eligible and excluded alternatives:

- Eligible records include quote identity, source/date, current claim checks and
  deterministic purchase/usable-unit costs.
- Excluded records include identity, source/date, claim checks, exclusion codes
  and readable reasons. Their acceptable_saving flag is always false. They are
  supplied to the model only as explicitly excluded alternatives so it can
  explain failures; they never enter cost minima or eligible recommendation data.
- Eligible purchase-outlay and usable-unit minima remain separate objectives.
  All ties are retained. Neither objective establishes superior quality or value.

Checks explain failed/missing claims, unevaluated requirements, stale/expired
evidence, availability, unknown transport, incompatible dimensions and package
limits. A matching claim remains unverified and is not a certification.
Sourcing-input checks do not waive separate product Quality Locks.

The response's server-rendered facts give eligible costs and explicit exclusion
statements. Qualitative AI paragraphs explain requirements and limitations.
They cannot authorize a substitution or alter any recipe, rule, price or supplier
record. Original source references are evidence only and never fetched.

All details remain private to the owning seller. Buyer context is unchanged and
never reads supplier evidence. Ownership, cache/error protections, input/output
bounds and post-inference evidence revalidation remain in force. Large selections
may exceed the assistant evidence budget; narrow the selected report instead of
relaxing or silently dropping quality requirements.

Automated checks cover distinct exclusion reasons, eligible-only minima, ties,
cross-product report selection and requirement changes during generation. A
separate opt-in real Qwen test asks why the cheaper failed quote is unacceptable.
Passing these checks is not a proof of semantic correctness for every AI answer.

Frontend rendering should visually separate eligible and excluded alternatives
and keep the unverified-source and no-substitution notices. See
[the assistant contract](local-assistants.md) and
[original supplier comparison contract](api-contract.md).
