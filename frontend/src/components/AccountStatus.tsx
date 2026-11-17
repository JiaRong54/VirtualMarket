import { useWatchlist } from '../lib/watchlist'

/** Show failed saves and connection errors rather than pretending success. */
export function AccountStatus() {
  const { busy, error, refresh } = useWatchlist()
  if (error) return <div className="account-status" role="alert">
    <span>{error}</span>
    <button type="button" className="link-btn" disabled={busy} onClick={() => void refresh()}>Reload account</button>
  </div>
  if (busy) return <p className="account-status" role="status">Syncing account…</p>
  return null
}
