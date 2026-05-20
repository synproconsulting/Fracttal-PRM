// Sprint 18 / FPRM-287 — shared currency formatting (display only, no FX).
// All persisted amounts are numeric; symbols are applied at render time using
// the Quote.currency_code header.

export const CURRENCY_SYMBOL = {
  USD: '$', EUR: '€', GBP: '£',
  AUD: 'A$', CAD: 'CA$', ZAR: 'R',
  AED: 'AED ', SAR: 'SAR ', EGP: 'EGP ',
}

export function formatCurrency(value, currencyCode = 'USD') {
  if (value === null || value === undefined || value === '') return '—'
  const num = Number(value)
  if (!Number.isFinite(num)) return '—'
  const sym = CURRENCY_SYMBOL[currencyCode] || `${currencyCode} `
  return `${sym}${num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}
