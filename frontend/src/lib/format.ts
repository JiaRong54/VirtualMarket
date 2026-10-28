// Display helpers. Prices are stored as whole cents, so we only
// turn them into dollars at the very last step, when drawing them.

const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
const count = new Intl.NumberFormat('en-US')

/** 1240 -> "$12.40" */
export function formatPrice(minor: number): string {
  return usd.format(minor / 100)
}

/** Axis labels: "$3.25" for small steps, "$40" for whole dollars, "$1.2K" from $1,000 up. */
export function formatPriceTick(minor: number, stepMinor: number): string {
  const dollars = minor / 100
  if (Math.abs(dollars) >= 1000) return `$${(dollars / 1000).toFixed(dollars % 1000 === 0 ? 0 : 1)}K`
  if (stepMinor % 100 !== 0) return `$${dollars.toFixed(2)}`
  return `$${dollars.toFixed(0)}`
}

const dayFmt = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' })

/** "2014-08-14" -> "Aug 14, 2014" */
export function formatDay(isoDate: string): string {
  return dayFmt.format(new Date(isoDate))
}

/** 21770 -> "21,770" */
export function formatCount(n: number): string {
  return count.format(n)
}

/** (1240, 1364) -> "+10.0%" ; works on cents so there are no float surprises */
export function formatChange(fromMinor: number, toMinor: number): string {
  if (fromMinor === 0) return '--'
  const pct = ((toMinor - fromMinor) / fromMinor) * 100
  const sign = pct > 0 ? '+' : ''
  return `${sign}${pct.toFixed(1)}%`
}

/** "2026-10-14T16:00:00Z" -> "12 min ago" */
export function formatAge(iso: string, now: number = Date.now()): string {
  const minutes = Math.round((now - new Date(iso).getTime()) / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  return `${Math.round(hours / 24)} d ago`
}
