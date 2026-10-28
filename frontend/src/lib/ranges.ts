// Time ranges for the price chart's buttons.
export type Range = '1M' | '6M' | '1Y' | 'ALL'

export const RANGES: { id: Range; label: string; days: number | null }[] = [
  { id: '1M', label: '1 month', days: 30 },
  { id: '6M', label: '6 months', days: 182 },
  { id: '1Y', label: '1 year', days: 365 },
  { id: 'ALL', label: 'All', days: null },
]
