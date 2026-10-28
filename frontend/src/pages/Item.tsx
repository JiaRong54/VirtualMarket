import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router'
import { PriceChart } from '../components/PriceChart'
import { RANGES, type Range } from '../lib/ranges'
import { loadLatestSnapshot } from '../lib/api'
import { formatCount, formatDay, formatPrice } from '../lib/format'
import {
  loadEvents,
  loadHistoryIndex,
  loadItemHistory,
  type ItemHistory,
  type UpdateEvent,
} from '../lib/history'
import type { PriceObservation } from '../types/market'

interface Loaded {
  name: string // which item this data is for
  history: ItemHistory | null
  listing: PriceObservation | null
  events: UpdateEvent[]
}

// One item: Steam sales history (Jerome's data) next to the current
// Skinport listing (Arian's collector).
export function Item() {
  const { name = '' } = useParams()
  const [data, setData] = useState<Loaded | null>(null)
  const [range, setRange] = useState<Range>('ALL')
  // Data for a previously opened item counts as still loading.
  const loaded = data?.name === name ? data : null

  useEffect(() => {
    const controller = new AbortController()
    const { signal } = controller
    ;(async () => {
      const [index, snapshot, events] = await Promise.all([
        loadHistoryIndex(signal),
        loadLatestSnapshot(signal),
        loadEvents(signal),
      ])
      const entry = index.find((e) => e.item_name === name)
      const history = entry ? await loadItemHistory(entry.file, signal) : null
      if (signal.aborted) return
      const listing = snapshot?.rows.find((r) => r.item_name === name) ?? null
      setData({ name, history, listing, events })
    })()
    return () => controller.abort()
  }, [name])

  const points = useMemo(() => loaded?.history?.points ?? [], [loaded])
  const last = points.at(-1)
  const recent = points.slice(-30)
  const avgSold = recent.length ? Math.round(recent.reduce((s, p) => s + p[2], 0) / recent.length) : null

  const tiles = [
    {
      label: 'Lowest ask now',
      value: loaded?.listing ? formatPrice(loaded.listing.lowest_price_minor) : '--',
      note: 'Skinport, latest snapshot',
    },
    {
      label: 'Listed now',
      value: loaded?.listing ? formatCount(loaded.listing.listing_count) : '--',
      note: 'Skinport, latest snapshot',
    },
    {
      label: 'Last median sale',
      value: last ? formatPrice(last[1]) : '--',
      note: last ? `Steam, ${formatDay(last[0])}` : 'Steam history',
    },
    {
      label: 'Sold per day',
      value: avgSold !== null ? formatCount(avgSold) : '--',
      note: 'Steam, 30 day average',
    },
  ]

  return (
    <>
      <div className="item-head">
        <Link to="/" className="back-link">
          Back to market
        </Link>
        <h2>{name}</h2>
        <span className="tag">{loaded?.history?.game ?? loaded?.listing?.game ?? 'cs2'}</span>
      </div>

      <div className="tiles">
        {tiles.map((t) => (
          <div className="tile" key={t.label}>
            <span className="tile-label">{t.label}</span>
            <span className="tile-value">{t.value}</span>
            <span className="tile-note">{t.note}</span>
          </div>
        ))}
      </div>

      {loaded && points.length > 0 && (
        <div className="range-row" role="group" aria-label="Time range">
          {RANGES.map((r) => (
            <button
              key={r.id}
              type="button"
              className={r.id === range ? 'range-btn on' : 'range-btn'}
              aria-pressed={r.id === range}
              onClick={() => setRange(r.id)}
            >
              {r.label}
            </button>
          ))}
        </div>
      )}

      <section className="card">
        <div className="card-head">
          <h2>Steam median sale price</h2>
          <span className="pill">
            {loaded === null ? 'loading' : points.length ? `${formatCount(points.length)} days of history` : 'no history'}
          </span>
        </div>

        {loaded === null ? (
          <div className="chart-empty">Loading</div>
        ) : points.length === 0 ? (
          <div className="empty-state">
            <strong>No Steam history loaded for this item</strong>
            <span>
              Run loader/convert_history.py on the downloaded Steam history to add it. Items with history are
              listed on the Price Movements page.
            </span>
          </div>
        ) : (
          <>
            <PriceChart points={points} range={range} events={loaded.events} />
            <p className="chart-note">
              One point per day, from Steam Community Market sale medians.
              {loaded.events.length === 0 && ' Game update markers appear once the update timeline is added.'}
            </p>
            <details className="data-table">
              <summary>Data table, last 30 days</summary>
              <table className="market">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th className="num">Median sale</th>
                    <th className="num">Sold</th>
                  </tr>
                </thead>
                <tbody>
                  {[...recent].reverse().map(([date, price, sold]) => (
                    <tr key={date}>
                      <td>{formatDay(date)}</td>
                      <td className="num">{formatPrice(price)}</td>
                      <td className="num">{formatCount(sold)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          </>
        )}
      </section>
    </>
  )
}
