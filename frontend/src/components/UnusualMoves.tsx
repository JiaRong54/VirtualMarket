import type { Game } from '../types/market'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router'
import { formatCount, formatDay, formatPrice } from '../lib/format'
import { itemPath, loadAnomalies, type AnomalyReport } from '../lib/history'

// Anomaly detection v1, written by loader/flag_anomalies.py.
// A flag is a day whose price change was far outside the item's last 30 days of changes.

const SHOW = 25
const WIDTHS = ['32%', '14%', '9%', '10%', '8%', '27%']

export function UnusualMoves({ game = 'cs2' }: { game?: Game }) {
  // The loaded report, remembered with its game so switching games shows "loading".
  const [loaded, setLoaded] = useState<{ game: Game; report: AnomalyReport | null } | null>(null)
  const report = loaded?.game === game ? loaded.report : undefined
  const [onlyNearUpdate, setOnlyNearUpdate] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    loadAnomalies(controller.signal, game).then((r) => {
      if (!controller.signal.aborted) setLoaded({ game, report: r })
    })
    return () => controller.abort()
  }, [game])

  const rows = useMemo(
    () => (report?.flags ?? []).filter((f) => !onlyNearUpdate || f.update).slice(0, SHOW),
    [report, onlyNearUpdate],
  )

  const s = report?.summary
  const pct = (x: number) => `${Math.round(x * 100)}%`

  return (
    <section className="card">
      <div className="card-head">
        <h2>Unusual moves</h2>
        <span className="pill">{report === undefined ? 'loading' : s ? `${formatCount(s.flags)} flags` : 'no data yet'}</span>
      </div>

      {s && report ? (
        <>
          <div className="tiles tiles-3 anomaly-tiles">
            <div className="tile">
              <span className="tile-label">Flagged days</span>
              <span className="tile-value">{formatCount(s.flags)}</span>
              <span className="tile-note">
                out of {formatCount(s.days_scored)} days across {formatCount(s.items)} items
              </span>
            </div>
            <div className="tile">
              <span className="tile-label">Flags near a game update</span>
              <span className="tile-value">{pct(s.share_flags_near_update)}</span>
              <span className="tile-note">
                vs {pct(s.share_days_near_update)} of all days (0 to {report.settings.after_update_days} days after)
              </span>
            </div>
            <div className="tile">
              <span className="tile-label">More likely after an update</span>
              <span className="tile-value">{s.ratio == null ? 'n/a' : `${s.ratio.toFixed(1)}x`}</span>
              <span className="tile-note">1.0x would mean updates make no difference</span>
            </div>
          </div>

          <div className="movers-controls">
            <label className="movers-filter">
              <input type="checkbox" checked={onlyNearUpdate} onChange={(e) => setOnlyNearUpdate(e.target.checked)} />
              Only flags right after a game update
            </label>
          </div>

          {rows.length > 0 ? (
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
                    <th>Day</th>
                    <th className="num">Change</th>
                    <th className="num">Price</th>
                    <th className="num">Score</th>
                    <th>Nearest update</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((f) => (
                    <tr key={`${f.file}-${f.date}`}>
                      <td className="item">
                        <Link to={itemPath(f.item_name, game)} className="item-link">
                          {f.item_name}
                        </Link>
                      </td>
                      <td className="muted">{formatDay(f.date)}</td>
                      <td className={`num change ${f.change_pct > 0 ? 'up' : 'down'}`}>
                        {f.change_pct > 0 ? '+' : ''}
                        {f.change_pct.toFixed(1)}%
                      </td>
                      <td className="num">{formatPrice(f.price)}</td>
                      <td className="num">{Math.abs(f.z).toFixed(1)}</td>
                      <td className={f.update ? 'update-cell' : 'muted'}>
                        {f.update ? `${f.update.label} (+${f.update.days_after}d)` : 'none within 3 days'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state">
              <strong>No flags match</strong>
              <span>Turn off the update filter to see every flagged day.</span>
            </div>
          )}

          <p className="movers-note">
            Score: how many times bigger the day's move was than the item's normal daily move over the previous{' '}
            {report.settings.window_days} days. Days at {report.settings.threshold} or more are flagged. Days with fewer than{' '}
            {report.settings.min_sold} sales are skipped. Last run {formatDay(report.generated.slice(0, 10))}.
          </p>
        </>
      ) : report === null ? (
        <div className="empty-state">
          <strong>No anomaly data yet</strong>
          <span>Run loader/flag_anomalies.py on the server after the history files update.</span>
        </div>
      ) : null}
    </section>
  )
}
