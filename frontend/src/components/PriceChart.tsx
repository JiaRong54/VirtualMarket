import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react'
import type { DailyPoint, UpdateEvent } from '../lib/history'
import { formatCount, formatDay, formatPrice, formatPriceTick } from '../lib/format'
import { RANGES, type Range } from '../lib/ranges'
import { niceScale, timeTicks } from '../lib/chartScale'

const HEIGHT = 340
const M = { top: 24, right: 20, bottom: 36, left: 72 }
const DAY = 86_400_000

interface Point {
  t: number
  date: string
  price: number
  sold: number
}

interface PriceChartProps {
  points: DailyPoint[]
  range: Range
  events?: UpdateEvent[]
}

// Line chart of one item's Steam median sale price, one point per day.
// Hover or use the arrow keys to read a day's price and number sold.
export function PriceChart({ points, range, events = [] }: PriceChartProps) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(900)
  // The hovered day, remembered with the range it belongs to so a range change clears it.
  const [hoverState, setHoverState] = useState<{ range: Range; i: number } | null>(null)
  const hover = hoverState?.range === range ? hoverState.i : null
  const setHover = (i: number | null) => setHoverState(i === null ? null : { range, i })

  const data = useMemo<Point[]>(() => {
    const all = points.map(([date, price, sold]) => ({ t: Date.parse(date), date, price, sold }))
    const days = RANGES.find((r) => r.id === range)?.days
    if (!days || all.length === 0) return all
    const cutoff = all[all.length - 1].t - days * DAY
    return all.filter((p) => p.t >= cutoff)
  }, [points, range])
  const tooFew = data.length < 2

  // Draw at the card's real width so text never stretches.
  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => setWidth(Math.max(300, Math.floor(entry.contentRect.width))))
    ro.observe(el)
    return () => ro.disconnect()
  }, [tooFew])

  if (tooFew) {
    return (
      <div ref={wrapRef} className="chart-empty">
        Not enough history in this range.
      </div>
    )
  }

  const innerW = width - M.left - M.right
  const innerH = HEIGHT - M.top - M.bottom
  const t0 = data[0].t
  const t1 = data[data.length - 1].t
  const y = niceScale(Math.min(...data.map((d) => d.price)), Math.max(...data.map((d) => d.price)))
  const xOf = (t: number) => M.left + ((t - t0) / (t1 - t0)) * innerW
  const yOf = (v: number) => M.top + (1 - (v - y.lo) / (y.hi - y.lo)) * innerH

  const line = data.map((d, i) => `${i ? 'L' : 'M'}${xOf(d.t).toFixed(1)},${yOf(d.price).toFixed(1)}`).join('')
  const area = `${line}L${xOf(t1).toFixed(1)},${yOf(y.lo)}L${xOf(t0).toFixed(1)},${yOf(y.lo)}Z`
  const xTicks = timeTicks(t0, t1).filter((tk) => tk.t >= t0 && tk.t <= t1)
  const marks = events
    .map((e) => ({ ...e, t: Date.parse(e.date) }))
    .filter((e) => e.t >= t0 && e.t <= t1)

  const nearest = (px: number) => {
    const t = t0 + ((px - M.left) / innerW) * (t1 - t0)
    let lo = 0
    let hi = data.length - 1
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1
      if (data[mid].t < t) lo = mid
      else hi = mid
    }
    return t - data[lo].t < data[hi].t - t ? lo : hi
  }

  const onMove = (e: PointerEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    setHover(nearest(e.clientX - rect.left))
  }

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const last = data.length - 1
    const step = e.shiftKey ? 30 : 1
    const at = hover ?? last
    const next =
      e.key === 'ArrowLeft' ? Math.max(0, at - step)
        : e.key === 'ArrowRight' ? Math.min(last, at + step)
          : e.key === 'Home' ? 0
            : e.key === 'End' ? last
              : null
    if (next !== null) {
      e.preventDefault()
      setHover(next)
    }
  }

  const h = hover !== null && hover < data.length ? data[hover] : null
  const tipLeft = h ? Math.min(Math.max(xOf(h.t), 90), width - 90) : 0

  return (
    <div
      ref={wrapRef}
      className="chart-wrap"
      tabIndex={0}
      onKeyDown={onKey}
      onBlur={() => setHover(null)}
      aria-label="Median sale price chart. Use the left and right arrow keys to read each day."
    >
      <svg width={width} height={HEIGHT} onPointerMove={onMove} onPointerLeave={() => setHover(null)} aria-hidden="true">
        {y.ticks.map((v) => (
          <g key={v}>
            <line className="grid" x1={M.left} x2={width - M.right} y1={yOf(v)} y2={yOf(v)} />
            <text className="tick" x={M.left - 10} y={yOf(v)} textAnchor="end" dominantBaseline="middle">
              {formatPriceTick(v, y.step)}
            </text>
          </g>
        ))}
        {xTicks.map((tk) => (
          <text key={tk.t} className="tick" x={xOf(tk.t)} y={HEIGHT - 12} textAnchor="middle">
            {tk.label}
          </text>
        ))}

        {marks.map((m) => {
          // Labels near the right edge go on the left of their line so they aren't cut off.
          const flip = xOf(m.t) + 8 + m.label.length * 7 > width - M.right
          return (
            <g key={`${m.date}-${m.label}`}>
              <line className="event-line" x1={xOf(m.t)} x2={xOf(m.t)} y1={M.top} y2={M.top + innerH} />
              <text
                className="event-label"
                x={xOf(m.t) + (flip ? -4 : 4)}
                y={M.top + 12}
                textAnchor={flip ? 'end' : 'start'}
              >
                {m.label}
              </text>
            </g>
          )
        })}

        <path className="area" d={area} />
        <path className="line" d={line} />

        {h && (
          <g>
            <line className="crosshair" x1={xOf(h.t)} x2={xOf(h.t)} y1={M.top} y2={M.top + innerH} />
            <circle className="dot" cx={xOf(h.t)} cy={yOf(h.price)} r={5} />
          </g>
        )}
      </svg>

      {h && (
        <div className="chart-tip" style={{ left: tipLeft }}>
          <strong>{formatPrice(h.price)}</strong>
          <span>{formatDay(h.date)}</span>
          <span>{formatCount(h.sold)} sold</span>
        </div>
      )}
    </div>
  )
}
