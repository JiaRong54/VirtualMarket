import { useEffect, useMemo, useRef, useState, type PointerEvent } from 'react'
import type { DailyPoint } from '../lib/history'
import { formatDay, formatPrice, formatPriceTick } from '../lib/format'
import { RANGES, type Range } from '../lib/ranges'
import { niceScale, timeTicks } from '../lib/chartScale'
import { SERIES_COLORS } from '../lib/seriesColors'

const HEIGHT = 340
const M = { top: 20, right: 20, bottom: 36, left: 72 }
const DAY = 86_400_000

export interface Series {
  label: string
  points: DailyPoint[]
}

interface CompareChartProps {
  series: Series[]
  range: Range
}

// Several variants of one skin on one chart, one line each.
// Hover to read every variant's price on the same day.
export function CompareChart({ series, range }: CompareChartProps) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(900)
  const [hoverT, setHoverT] = useState<number | null>(null)

  // Every line is cut at the same start date, based on the newest day across all of them.
  const lines = useMemo(() => {
    const parsed = series.map((s) => s.points.map(([date, price]) => ({ t: Date.parse(date), date, price })))
    const end = Math.max(...parsed.flatMap((p) => (p.length ? [p[p.length - 1].t] : [0])))
    const days = RANGES.find((r) => r.id === range)?.days
    const cutoff = days ? end - days * DAY : -Infinity
    return parsed.map((p) => p.filter((d) => d.t >= cutoff))
  }, [series, range])

  const all = lines.flat()
  const tooFew = all.length < 2

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

  const t0 = Math.min(...all.map((d) => d.t))
  const t1 = Math.max(...all.map((d) => d.t))
  const span = t1 - t0 || DAY
  const innerW = width - M.left - M.right
  const innerH = HEIGHT - M.top - M.bottom
  const y = niceScale(Math.min(...all.map((d) => d.price)), Math.max(...all.map((d) => d.price)))
  const xOf = (t: number) => M.left + ((t - t0) / span) * innerW
  const yOf = (v: number) => M.top + (1 - (v - y.lo) / (y.hi - y.lo)) * innerH
  const xTicks = timeTicks(t0, t1).filter((tk) => tk.t >= t0 && tk.t <= t1)

  // For the hovered day, each variant's price on that day or the closest day before it.
  const atHover = hoverT === null ? [] : lines.map((line) => {
    let best: (typeof line)[number] | null = null
    for (const d of line) if (d.t <= hoverT) best = d
    return best
  })

  const onMove = (e: PointerEvent<SVGSVGElement>) => {
    const px = e.clientX - e.currentTarget.getBoundingClientRect().left
    const t = t0 + ((px - M.left) / innerW) * span
    setHoverT(Math.min(t1, Math.max(t0, Math.round(t / DAY) * DAY)))
  }

  const tipLeft = hoverT !== null ? Math.min(Math.max(xOf(hoverT), 110), width - 110) : 0

  return (
    <div ref={wrapRef} className="chart-wrap">
      <svg width={width} height={HEIGHT} onPointerMove={onMove} onPointerLeave={() => setHoverT(null)} aria-hidden="true">
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

        {lines.map((line, i) => (
          <path
            key={series[i].label}
            d={line.map((d, j) => `${j ? 'L' : 'M'}${xOf(d.t).toFixed(1)},${yOf(d.price).toFixed(1)}`).join('')}
            fill="none"
            stroke={SERIES_COLORS[i % SERIES_COLORS.length]}
            strokeWidth={2}
            strokeLinejoin="round"
          />
        ))}

        {hoverT !== null && (
          <g>
            <line className="crosshair" x1={xOf(hoverT)} x2={xOf(hoverT)} y1={M.top} y2={M.top + innerH} />
            {atHover.map((d, i) =>
              d ? (
                <circle key={i} cx={xOf(d.t)} cy={yOf(d.price)} r={4} fill={SERIES_COLORS[i % SERIES_COLORS.length]} stroke="#fff" strokeWidth={1.5} />
              ) : null,
            )}
          </g>
        )}
      </svg>

      {hoverT !== null && (
        <div className="chart-tip compare-tip" style={{ left: tipLeft }}>
          <span>{formatDay(new Date(hoverT).toISOString().slice(0, 10))}</span>
          {atHover.map((d, i) =>
            d ? (
              <span key={i} className="compare-tip-row">
                <i style={{ background: SERIES_COLORS[i % SERIES_COLORS.length] }} />
                {series[i].label}
                <strong>{formatPrice(d.price)}</strong>
              </span>
            ) : null,
          )}
        </div>
      )}
    </div>
  )
}
