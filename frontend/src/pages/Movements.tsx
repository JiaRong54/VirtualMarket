import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { PagePlaceholder } from '../components/PagePlaceholder'
import { formatCount, formatDay } from '../lib/format'
import { itemPath, loadHistoryIndex, type HistoryIndexEntry } from '../lib/history'

export function Movements() {
  const [items, setItems] = useState<HistoryIndexEntry[] | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    loadHistoryIndex(controller.signal).then((list) => {
      if (!controller.signal.aborted) setItems(list)
    })
    return () => controller.abort()
  }, [])

  return (
    <>
      <section className="card">
        <div className="card-head">
          <h2>Items with Steam price history</h2>
          <span className="pill">{items === null ? 'loading' : `${formatCount(items.length)} items`}</span>
        </div>
        {items && items.length > 0 ? (
          <div className="table-wrap">
            <table className="market">
              <thead>
                <tr>
                  <th>Item</th>
                  <th className="num">Days</th>
                  <th>From</th>
                  <th>To</th>
                </tr>
              </thead>
              <tbody>
                {items.map((it) => (
                  <tr key={it.file}>
                    <td className="item">
                      <Link to={itemPath(it.item_name)} className="item-link">
                        {it.item_name}
                      </Link>
                    </td>
                    <td className="num">{formatCount(it.days)}</td>
                    <td className="muted">{formatDay(it.first)}</td>
                    <td className="muted">{formatDay(it.last)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">
            <strong>No price history loaded yet</strong>
            <span>Run loader/steam_history.py on the saved Steam files. Each item then gets a chart.</span>
          </div>
        )}
      </section>

      <PagePlaceholder
        summary="Unusual price moves flagged automatically, lined up against the dates of game updates. This is where our research question shows up in the app."
        willShow={[
          'Flagged items with the size and direction of the move',
          'Game update markers on the same timeline',
          'Filter by game and by date range',
        ]}
        needs={['Anomaly detection output (Jerome)', 'Game update event timeline (Jerome)']}
      />
    </>
  )
}
