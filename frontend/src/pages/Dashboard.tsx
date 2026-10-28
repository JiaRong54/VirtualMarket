import { useEffect, useMemo, useState } from 'react'
import { MarketTable } from '../components/MarketTable'
import { loadLatestSnapshot, type Snapshot } from '../lib/api'
import { formatAge, formatCount } from '../lib/format'

// How many rows the table shows. The full catalog is about 21,000 items.
const SHOW = 100

export function Dashboard() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)

  // Load the latest snapshot once when the page opens.
  useEffect(() => {
    const controller = new AbortController()
    loadLatestSnapshot(controller.signal).then((s) => {
      if (!controller.signal.aborted) setSnapshot(s)
    })
    return () => controller.abort()
  }, [])

  // Most expensive first, top 100.
  const rows = useMemo(() => {
    if (!snapshot) return []
    return [...snapshot.rows]
      .sort((a, b) => b.lowest_price_minor - a.lowest_price_minor)
      .slice(0, SHOW)
  }, [snapshot])

  const tiles = [
    {
      label: 'Items tracked',
      value: snapshot ? formatCount(snapshot.item_count) : '--',
      note: 'from the latest snapshot',
    },
    {
      label: 'Last snapshot',
      value: snapshot?.collected_at ? formatAge(snapshot.collected_at) : '--',
      note: 'hourly, from Skinport',
    },
    { label: 'Biggest move today', value: '--', note: 'once detection is live' },
    { label: 'On your watchlist', value: '--', note: 'once login is live' },
  ]

  return (
    <>
      <div className="tiles">
        {tiles.map((t) => (
          <div className="tile" key={t.label}>
            <span className="tile-label">{t.label}</span>
            <span className="tile-value">{t.value}</span>
            <span className="tile-note">{t.note}</span>
          </div>
        ))}
      </div>

      <MarketTable rows={rows} total={snapshot?.item_count ?? 0} />
    </>
  )
}
