import type { Game, PriceObservation } from '../types/market'

/** What the loader writes to latest.json (and what the API will return). */
export interface Snapshot {
  source: 'steam'
  currency: 'USD'
  snapshot_key: string | null
  collected_at: string | null
  item_count: number
  skipped_no_listings: number
  rows: PriceObservation[]
}

// Where prices come from.
// Steam-only filename prevents an old Skinport snapshot from being reused.
// Later: Jerome's API, by setting VITE_PRICES_URL in a .env file.
const PRICES_URL = import.meta.env.VITE_PRICES_URL ?? './data/steam-latest.json'

/** Latest snapshot, or null when there is no data yet. Never throws. */
export async function loadLatestSnapshot(signal?: AbortSignal, game: Game = 'cs2'): Promise<Snapshot | null> {
  try {
    const res = await fetch(game === 'dota2' ? './data/dota2/steam-latest.json' : PRICES_URL, { signal, cache: 'no-cache' })
    if (!res.ok) return null
    const data: unknown = await res.json()
    if (!isSnapshot(data)) return null
    const rows = data.rows.filter((row) => row.game === game)
    return { ...data, rows, item_count: rows.length,
      collected_at: rows.reduce<string | null>((latest, row) =>
        latest === null || Date.parse(row.timestamp) > Date.parse(latest) ? row.timestamp : latest, null) }
  } catch {
    // Missing file, network error, or not JSON: show the placeholder.
    return null
  }
}

function isSnapshot(data: unknown): data is Snapshot {
  if (typeof data !== 'object' || data === null) return false
  const snapshot = data as Snapshot
  return snapshot.source === 'steam' && snapshot.currency === 'USD'
    && Array.isArray(snapshot.rows) && snapshot.item_count === snapshot.rows.length
    && (snapshot.collected_at === null || Number.isFinite(Date.parse(snapshot.collected_at)))
    && snapshot.rows.every((row) => row !== null && typeof row === 'object'
      && ['steam_community_overview', 'steam_community_search'].includes(row.source)
      && ['cs2', 'dota2'].includes(row.game)
      && typeof row.item_name === 'string' && row.item_name.trim().length > 0
      && typeof row.timestamp === 'string' && Number.isFinite(Date.parse(row.timestamp))
      && Number.isSafeInteger(row.lowest_price_minor) && row.lowest_price_minor >= 0
      && (row.listing_count === null || (Number.isSafeInteger(row.listing_count) && row.listing_count >= 0)))
}
