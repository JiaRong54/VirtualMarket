// Axis helpers shared by the price charts.

const DAY = 86_400_000
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** Round axis bounds and 4 to 6 evenly spaced ticks, in cents. */
export function niceScale(min: number, max: number) {
  if (min === max) {
    const pad = Math.max(1, Math.round(min * 0.1))
    min -= pad
    max += pad
  }
  const raw = (max - min) / 4
  const mag = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? 10 * mag
  const lo = Math.max(0, Math.floor(min / step) * step)
  const hi = Math.ceil(max / step) * step
  const ticks: number[] = []
  for (let v = lo; v <= hi + step / 2; v += step) ticks.push(Math.round(v))
  return { lo, hi, step: Math.round(step), ticks }
}

/** Year ticks for long ranges, month ticks for months, day ticks for weeks. At most about 8. */
export function timeTicks(t0: number, t1: number): { t: number; label: string }[] {
  const days = (t1 - t0) / DAY
  const start = new Date(t0)
  const out: { t: number; label: string }[] = []

  if (days > 3 * 365) {
    const y0 = start.getUTCFullYear() + 1
    const y1 = new Date(t1).getUTCFullYear()
    const k = Math.ceil((y1 - y0 + 1) / 8)
    for (let yr = y0; yr <= y1; yr += k) out.push({ t: Date.UTC(yr, 0, 1), label: String(yr) })
  } else if (days > 60) {
    const months = Math.round(days / 30.4)
    const k = Math.max(1, Math.ceil(months / 7))
    const yr = start.getUTCFullYear()
    const mo = start.getUTCMonth() + 1
    for (let i = 0; i <= months + 1; i += k) {
      const d = new Date(Date.UTC(yr, mo + i, 1))
      const m = d.getUTCMonth()
      out.push({ t: d.getTime(), label: m === 0 || out.length === 0 ? `${MON[m]} ${d.getUTCFullYear()}` : MON[m] })
    }
  } else {
    const k = Math.max(1, Math.ceil(days / 7))
    for (let t = Date.UTC(start.getUTCFullYear(), start.getUTCMonth(), start.getUTCDate() + 1); t <= t1; t += k * DAY) {
      const d = new Date(t)
      out.push({ t, label: `${MON[d.getUTCMonth()]} ${d.getUTCDate()}` })
    }
  }
  return out
}
