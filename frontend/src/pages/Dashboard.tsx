import type { Game } from '../types/market'
import { useEffect, useMemo, useState } from 'react'
import { MarketTable } from '../components/MarketTable'
import { loadLatestSnapshot, type Snapshot } from '../lib/api'
import { formatAge, formatCount } from '../lib/format'

export function Dashboard({ game = 'cs2' }: { game?: Game }) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)

  // Pick up cloud-published observations without rebuilding or reloading the page.
  useEffect(() => {
    const controller = new AbortController()
    let pending = false
    const refresh = async () => {
      if (pending) return
      pending = true
      const next = await loadLatestSnapshot(controller.signal, game)
      if (!controller.signal.aborted && next) setSnapshot(next)
      pending = false
    }
    void refresh()
    const timer = window.setInterval(() => void refresh(), 60_000)
    return () => {
      controller.abort()
      window.clearInterval(timer)
    }
  }, [game])

  // Keep the full catalog; the table paginates it.
  const rows = useMemo(() => {
    if (!snapshot) return []
    return [...snapshot.rows]
      .sort((a, b) => b.lowest_price_minor - a.lowest_price_minor)
  }, [snapshot])

  const tiles = [
    {
      label: 'Items tracked',
      value: snapshot ? formatCount(snapshot.item_count) : '--',
      note: 'from the latest snapshot',
    },
    {
      label: 'Latest observation',
      value: snapshot?.collected_at ? formatAge(snapshot.collected_at) : '--',
      note: 'Steam Market; each row has its own update time',
    },
    { label: 'Biggest move today', value: '--', note: 'once detection is live' },
  ]

  return (
    <>
      <div className="tiles tiles-3">
        {tiles.map((t) => (
          <div className="tile" key={t.label}>
            <span className="tile-label">{t.label}</span>
            <span className="tile-value">{t.value}</span>
            <span className="tile-note">{t.note}</span>
          </div>
        ))}
      </div>

      <MarketTable rows={rows} game={game} />
    </>
  )
}
