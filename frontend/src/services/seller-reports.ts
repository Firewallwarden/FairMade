import { privateRequest } from './session'
import { integer, list, money, nullable, object, page, text } from './decode'

export const getPricingReviews = (id: string, signal?: AbortSignal) =>
  privateRequest(
    `/products/${id}/pricing-reviews?limit=100`,
    page((value) => {
      const data = object(value)
      return { id: text(data.id), reviewed_on: text(data.reviewed_on) }
    }),
    { signal },
  )
export const getCostBasis = (id: string, signal?: AbortSignal) =>
  privateRequest(
    `/products/${id}/sales-cost-basis`,
    (value) => {
      const data = object(value)
      return {
        revision: integer(data.revision),
        analysis_id: nullable(data.analysis_id, text),
      }
    },
    { signal },
  )
export const setCostBasis = (
  id: string,
  revision: number,
  analysisId: string | null,
) =>
  privateRequest(`/products/${id}/sales-cost-basis`, object, {
    method: 'PUT',
    json: { expected_revision: revision, analysis_id: analysisId },
  })

export const getInsights = (
  id: string,
  days: number,
  analysisId: string | null,
) =>
  privateRequest(
    `/products/${id}/insights`,
    (value) => {
      const data = object(value)
      if (data.insight_version !== 'seller-insights-v1')
        throw new Error('Unsupported insights')
      const pricing = object(data.pricing)
      return {
        as_of_date: text(data.as_of_date),
        selling_unit: text(data.selling_unit),
        pricing: {
          status: text(pricing.status),
          price: nullable(pricing.price, money),
          unit_cost: nullable(pricing.unit_cost, money),
          profit_per_unit: nullable(pricing.profit_per_unit, money),
          break_even_price: nullable(pricing.break_even_price, money),
        },
        alerts: list(data.alerts, (value) => {
          const alert = object(value)
          return {
            code: text(alert.code),
            severity: text(alert.severity),
            message: text(alert.message),
            suggested_review: text(alert.suggested_review),
          }
        }),
        details: {
          costs: data.costs,
          receipts: data.receipts,
          production: data.production,
          materials: data.materials,
        },
        notices: list(data.notices, text),
      }
    },
    { method: 'POST', json: { period_days: days, analysis_id: analysisId } },
  )

export const getForecast = (id: string, lookback: number, horizon: number) =>
  privateRequest(
    `/products/${id}/forecasts`,
    (value) => {
      const data = object(value)
      if (data.forecast_version !== 'observed-sales-rate-v1')
        throw new Error('Unsupported forecast')
      const history = object(data.history)
      return {
        status: text(data.status),
        selling_unit: text(data.selling_unit),
        daily_rate: nullable(data.daily_rate, money),
        projected_units: nullable(data.projected_units, money),
        history: {
          start_date: text(history.start_date),
          end_date: text(history.end_date),
          units: integer(history.units),
          sale_dates: integer(history.sale_dates),
        },
        inventory: object(data.inventory),
        warnings: list(data.warnings, text),
        notices: list(data.notices, text),
      }
    },
    {
      method: 'POST',
      json: { lookback_days: lookback, horizon_days: horizon },
    },
  )

export const getCostCalendar = (id: string, months: number) =>
  privateRequest(
    `/products/${id}/cost-calendar`,
    (value) => {
      const data = object(value)
      if (data.calendar_version !== 'saved-cost-calendar-v1')
        throw new Error('Unsupported calendar')
      return {
        selling_unit: text(data.selling_unit),
        status: text(data.calendar_evidence_status),
        seasonality: text(data.seasonality_status),
        months: list(data.months, (value) => {
          const month = object(value)
          return {
            month: text(month.month),
            status: text(month.status),
            unit_cost: nullable(month.unit_cost, money),
            record_count: integer(month.record_count),
          }
        }),
        comparisons: list(data.year_over_year, object),
        notices: list(data.notices, text),
      }
    },
    { method: 'POST', json: { months } },
  )

export const getPriceAdvice = (id: string, reviewId: string) =>
  privateRequest(
    `/products/${id}/pricing-recommendations`,
    (value) => {
      const data = object(value)
      if (data.advice_version !== 'conditional-price-range-v1')
        throw new Error('Unsupported advice')
      const range = (value: unknown) => {
        const item = object(value)
        return { minimum: money(item.minimum), maximum: money(item.maximum) }
      }
      return {
        status: text(data.status),
        quality_status: text(data.quality_status),
        selling_unit: text(data.analysis_selling_unit),
        break_even: money(data.break_even_price),
        target: range(data.seller_target_range),
        recommended: nullable(data.recommended_review_range, range),
        reasons: list(data.reasons, text),
        notices: list(data.notices, text),
        sources: list(data.market_sources, object),
      }
    },
    { method: 'POST', json: { review_id: reviewId } },
  )

export const getSalesSummary = (start: string, end: string) =>
  privateRequest(
    `/seller/sales?${new URLSearchParams({ start_date: start, end_date: end })}`,
    (value) => {
      const data = object(value)
      if (data.report_version !== 'sandbox-sales-v1')
        throw new Error('Unsupported sales')
      return {
        sales_count: integer(data.sales_count),
        gross_sales: money(data.gross_sales),
        completed_refunds: money(data.completed_refunds),
        estimated_profit: nullable(data.estimated_profit, money),
        missing_fee_count: integer(data.missing_fee_count),
        missing_cost_count: integer(data.missing_cost_count),
        covered_sales_count: integer(data.covered_sales_count),
        warnings: list(data.warnings, text),
      }
    },
  )
