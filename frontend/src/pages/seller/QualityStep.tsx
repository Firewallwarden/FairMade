import { useCallback, useState } from 'react'
import type { FormEvent } from 'react'
import { Field } from '../../components/FormFields'
import { fieldValue } from '../../utils/form'
import { ErrorNotice } from '../../components/Feedback'
import { ruleDescription } from '../../utils/presentation'
import { useResource } from '../../hooks/useResource'
import { useAction } from '../../hooks/useAction'
import { evaluateQuality, getLocks, saveLocks } from '../../services/seller'
import type { QualityClaim, QualityRule } from '../../services/quality-contract'

export function QualityStep({ productId }: { productId: string }) {
  const resource = useResource(
    useCallback((signal) => getLocks(productId, signal), [productId]),
  )
  const action = useAction()
  const [ruleType, setRuleType] = useState<'boolean' | 'choice' | 'numeric'>(
    'boolean',
  )
  const [evaluation, setEvaluation] = useState<Awaited<
    ReturnType<typeof evaluateQuality>
  > | null>(null)

  function addRule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const fields = new FormData(form)
    const locks = resource.data
    if (!locks) return
    void action.run(async () => {
      const base = {
        key: fieldValue(fields, 'rule-key'),
        label: fieldValue(fields, 'rule-label'),
      }
      let rule: QualityRule
      if (ruleType === 'boolean')
        rule = {
          ...base,
          type: 'boolean',
          expected: fieldValue(fields, 'rule-expected') === 'true',
        }
      else if (ruleType === 'choice')
        rule = {
          ...base,
          type: 'choice',
          allowed_values: fieldValue(fields, 'rule-choices')
            .split(',')
            .map((value) => value.trim())
            .filter(Boolean),
        }
      else
        rule = {
          ...base,
          type: 'numeric',
          minimum: fieldValue(fields, 'rule-minimum') || null,
          maximum: fieldValue(fields, 'rule-maximum') || null,
          unit: fieldValue(fields, 'rule-unit'),
        }
      await saveLocks(productId, locks.revision, [...locks.rules, rule])
      form.reset()
      setEvaluation(null)
      resource.reload()
    }, 'Requirement saved. Existing evaluations remain historical and may no longer apply.')
  }

  function evaluate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fields = new FormData(event.currentTarget)
    const locks = resource.data
    if (!locks) return
    void action.run(async () => {
      const claims: Record<string, QualityClaim> = {}
      locks.rules.forEach((rule) => {
        const value = fieldValue(fields, `claim-${rule.key}`)
        if (!value) return
        claims[rule.key] =
          rule.type === 'boolean'
            ? { type: rule.type, value: value === 'true' }
            : rule.type === 'choice'
              ? { type: rule.type, value }
              : { type: rule.type, value, unit: rule.unit }
      })
      setEvaluation(
        await evaluateQuality(productId, {
          candidate_label: fieldValue(fields, 'candidate-label'),
          expected_revision: locks.revision,
          claims,
        }),
      )
    }, 'Claim check saved. This does not independently verify the claims.')
  }

  return (
    <section className="workspace-panel">
      <p className="eyebrow">Protect what makes it yours</p>
      <h2>Quality is a requirement.</h2>
      <p>
        Define mandatory standards before evaluating a supplier or ingredient
        change. Missing evidence cannot establish compliance, and a failed
        requirement is never an acceptable saving.
      </p>
      <ErrorNotice error={resource.error || action.error} />
      {action.notice && (
        <p className="calculator-notice" role="status">
          {action.notice}
        </p>
      )}
      {resource.loading && <p role="status">Loading Quality Locks…</p>}
      {resource.data && (
        <>
          <ul>
            {resource.data.rules.map((rule) => (
              <li key={rule.key}>
                <strong>{rule.label}</strong> — {ruleDescription(rule)}{' '}
                <button
                  className="calculator-remove"
                  type="button"
                  disabled={action.busy}
                  aria-label={`Remove requirement ${rule.label}`}
                  onClick={() => {
                    const locks = resource.data
                    if (locks)
                      void action.run(async () => {
                        await saveLocks(
                          productId,
                          locks.revision,
                          locks.rules.filter((item) => item.key !== rule.key),
                        )
                        setEvaluation(null)
                        resource.reload()
                      }, 'Requirement removed. Review historical evaluations before relying on them.')
                  }}
                >
                  Remove requirement
                </button>
              </li>
            ))}
          </ul>
          {!resource.data.rules.length && (
            <p>No Quality Locks configured yet.</p>
          )}
          <details>
            <summary>Add a mandatory requirement</summary>
            <form onSubmit={addRule}>
              <fieldset
                disabled={action.busy || resource.data.rules.length >= 100}
                className="calculator-form"
              >
                <legend className="sr-only">New Quality Lock</legend>
                <div className="calculator-grid">
                  <Field
                    name="rule-label"
                    title="Requirement name"
                    required
                    maxLength={200}
                    pattern=".*\S.*"
                    placeholder="e.g. Organic flour"
                  />
                  <Field
                    name="rule-key"
                    title="Unique attribute key"
                    required
                    maxLength={64}
                    pattern="[a-z][a-z0-9_]{0,63}"
                    placeholder="e.g. organic_flour"
                  />
                  <label className="calculator-field">
                    Requirement type
                    <select
                      value={ruleType}
                      onChange={(event) => {
                        const value = event.target.value
                        if (
                          value === 'boolean' ||
                          value === 'choice' ||
                          value === 'numeric'
                        )
                          setRuleType(value)
                      }}
                    >
                      <option value="boolean">Yes / no</option>
                      <option value="choice">Allowed choices</option>
                      <option value="numeric">Numeric limits</option>
                    </select>
                  </label>
                  {ruleType === 'boolean' && (
                    <label className="calculator-field">
                      Required value
                      <select name="rule-expected">
                        <option value="true">Yes / true</option>
                        <option value="false">No / false</option>
                      </select>
                    </label>
                  )}
                  {ruleType === 'choice' && (
                    <Field
                      name="rule-choices"
                      title="Allowed choices, separated by commas"
                      required
                      maxLength={2000}
                    />
                  )}
                  {ruleType === 'numeric' && (
                    <>
                      <Field
                        name="rule-minimum"
                        title="Minimum (optional)"
                        type="number"
                        step="0.000001"
                        min="-1000000000"
                        max="1000000000"
                      />
                      <Field
                        name="rule-maximum"
                        title="Maximum (optional)"
                        type="number"
                        step="0.000001"
                        min="-1000000000"
                        max="1000000000"
                      />
                      <Field
                        name="rule-unit"
                        title="Unit"
                        required
                        maxLength={200}
                        pattern=".*\S.*"
                      />
                    </>
                  )}
                </div>
                <div className="workspace-actions">
                  <button type="submit" className="button-primary">
                    Save requirement
                  </button>
                </div>
              </fieldset>
            </form>
          </details>
          <h3>Check a candidate’s reported claims</h3>
          <form onSubmit={evaluate}>
            <fieldset
              disabled={action.busy || !resource.data.rules.length}
              className="calculator-form"
            >
              <legend className="sr-only">
                Evaluate candidate against Quality Locks
              </legend>
              <Field
                name="candidate-label"
                title="Candidate name"
                required
                maxLength={200}
                pattern=".*\S.*"
              />
              <div className="calculator-grid">
                {resource.data.rules.map((rule) => (
                  <label className="calculator-field" key={rule.key}>
                    {rule.label} · seller-reported
                    {rule.type === 'numeric' ? (
                      <input
                        name={`claim-${rule.key}`}
                        type="number"
                        step="0.000001"
                        min="-1000000000"
                        max="1000000000"
                        placeholder={`Unknown, or value in ${rule.unit}`}
                      />
                    ) : (
                      <select name={`claim-${rule.key}`}>
                        <option value="">Unknown / no evidence</option>
                        {rule.type === 'boolean' ? (
                          <>
                            <option value="true">Yes / true</option>
                            <option value="false">No / false</option>
                          </>
                        ) : (
                          rule.allowed_values.map((value) => (
                            <option key={value} value={value}>
                              {value}
                            </option>
                          ))
                        )}
                      </select>
                    )}
                  </label>
                ))}
              </div>
              <div className="workspace-actions">
                <button className="button-primary" type="submit">
                  Check & save claims
                </button>
              </div>
            </fieldset>
          </form>
        </>
      )}
      {evaluation && (
        <div className="calculator-notice" role="status">
          <h3>
            {evaluation.candidate_label}:{' '}
            {evaluation.status.replaceAll('_', ' ')}
          </h3>
          <ul>
            {evaluation.checks.map((check) => (
              <li key={check.key}>
                {check.label}: {check.message}
              </li>
            ))}
          </ul>
          <p>
            {evaluation.status === 'failed'
              ? 'Do not treat this candidate as an acceptable saving.'
              : evaluation.status === 'passed'
                ? 'Reported claims match these rules. This is not independent verification.'
                : 'Compliance has not been established.'}
          </p>
        </div>
      )}
      <button
        className="calculator-secondary"
        disabled={action.busy}
        onClick={() => {
          setEvaluation(null)
          resource.reload()
        }}
      >
        Reload current requirements
      </button>
    </section>
  )
}
