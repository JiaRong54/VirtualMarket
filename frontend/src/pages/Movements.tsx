import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router'
import { PagePlaceholder } from '../components/PagePlaceholder'
import { formatChange, formatCount, formatDay, formatPrice } from '../lib/format'
import { itemPath, loadHistoryIndex, type HistoryIndexEntry } from '../lib/history'

// How far back to compare. The keys match "prev" in history/index.json.
const WINDOWS = [
  { id: '1', label: '1 day' },
  { id: '7', label: '7 days' },
  { id: '30', label: '30 days' },
]

// Items that barely sell jump around on one sale, so they are hidden by default.
const MIN_SOLD = [
  { value: 0, label: 'Any' },
  { value: 10, label: '10+' },
  { value: 100, label: '100+' },
]

const SHOW = 50
const WIDTHS = ['38%', '8%', '11%', '11%', '10%', '10%', '12%']

interface Mover {
  item: HistoryIndexEntry
  from: number
  to: number
  pct: number
}

export function Movements() {
  const [items, setItems] = useState<HistoryIndexEntry[] | null>(null)
  const [windowId, setWindowId] = useState('7')
  const [direction, setDirection] = useState<'up' | 'down'>('up')
  const [minSold, setMinSold] = useState(10)

  useEffect(() => {
    const controller = new AbortController()
    loadHistoryIndex(controller.signal).then((list) => {
      if (!controller.signal.aborted) setItems(list)
    })
    return () => controller.abort()
  }, [])

  // An index.json made before the converter added price stats has none.
  const hasStats = (items ?? []).some((it) => it.price !== undefined && it.prev)

  const movers = useMemo(() => {
    const list: Mover[] = []
    for (const item of items ?? []) {
      const from = item.prev?.[windowId]
      const to = item.price
      if (from == null || to === undefined || from === 0) continue
      if ((item.sold_7d ?? 0) < minSold) continue
      list.push({ item, from, to, pct: (to - from) / from })
    }
    list.sort((a, b) => (direction === 'up' ? b.pct - a.pct : a.pct - b.pct))
    return list.filter((m) => (direction === 'up' ? m.pct > 0 : m.pct < 0)).slice(0, SHOW)
  }, [items, windowId, direction, minSold])

  const windowLabel = WINDOWS.find((w) => w.id === windowId)?.label ?? ''

  return (
    <>
      <section className="card">
        <div className="card-head">
          <h2>{direction === 'up' ? 'Biggest gains' : 'Biggest drops'}</h2>
          <span className="pill">
            {items === null ? 'loading' : `${formatCount(movers.length)} items, last ${windowLabel}`}
          </span>
        </div>

        <div className="movers-controls">
          <div className="range-row" role="group" aria-label="Compare against">
            {WINDOWS.map((w) => (
              <button
                key={w.id}
                type="button"
                className={w.id === windowId ? 'range-btn on' : 'range-btn'}
                aria-pressed={w.id === windowId}
                onClick={() => setWindowId(w.id)}
              >
                {w.label}
              </button>
            ))}
          </div>

          <div className="range-row" role="group" aria-label="Direction">
            {(['up', 'down'] as const).map((d) => (
              <button
                key={d}
                type="button"
                className={d === direction ? 'range-btn on' : 'range-btn'}
                aria-pressed={d === direction}
                onClick={() => setDirection(d)}
              >
                {d === 'up' ? 'Gains' : 'Drops'}
              </button>
            ))}
          </div>

          <label className="movers-filter">
            Sold in last 7 days
            <select value={minSold} onChange={(e) => setMinSold(Number(e.target.value))}>
              {MIN_SOLD.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        {items !== null && !hasStats ? (
          <div className="empty-state">
            <strong>No price movement data yet</strong>
            <span>
              Run loader/convert_history.py again on the Steam history. It now adds each item's recent
              prices to index.json, which this page reads.
            </span>
          </div>
        ) : movers.length > 0 ? (
          <div className="table-wrap">
            <table className="market">
              <colgroup>
                {WIDTHS.map((w, i) => (
                  <col key={i} style={{ width: w }} />
                ))}
              </colgroup>
              <thead>
                <tr>
                  <th>Item</th>
                  <th>Game</th>
                  <th className="num">Before</th>
                  <th className="num">Now</th>
                  <th className="num">Change</th>
                  <th className="num">Sold (7d)</th>
                  <th>As of</th>
                </tr>
              </thead>
              <tbody>
                {movers.map(({ item, from, to }) => (
                  <tr key={item.file}>
                    <td className="item">
                      <Link to={itemPath(item.item_name)} className="item-link">
                        {item.item_name}
                      </Link>
                    </td>
                    <td className="muted">{item.game.toUpperCase()}</td>
                    <td className="num">{formatPrice(from)}</td>
                    <td className="num">{formatPrice(to)}</td>
                    <td className={`num change ${to > from ? 'up' : 'down'}`}>{formatChange(from, to)}</td>
                    <td className="num">{formatCount(item.sold_7d ?? 0)}</td>
                    <td className="muted">{formatDay(item.last)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : items !== null ? (
          <div className="empty-state">
            <strong>Nothing matches</strong>
            <span>Try a longer time window or a lower sales filter.</span>
          </div>
        ) : null}

        <p className="movers-note">
          Prices are Steam median sale prices per day. Change compares the item's last day with the
          same item {windowLabel} earlier.
        </p>
      </section>

      <PagePlaceholder
        summary="Next: unusual moves flagged automatically and lined up against game update dates. This is where our research question shows up in the app."
        willShow={[
          "A flag on moves far outside the item's normal range",
          'Game update markers on the same timeline',
          'Filter by game and by date range',
        ]}
        needs={['Anomaly detection output (Jerome)', 'Game update event timeline (Jerome)']}
      />
    </>
  )
}