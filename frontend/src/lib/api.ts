import type { PriceObservation } from '../types/market'

/** What the loader writes to latest.json (and what the API will return). */
export interface Snapshot {
  snapshot_key: string | null
  collected_at: string | null
  item_count: number
  skipped_no_listings: number
  rows: PriceObservation[]
}

// Where prices come from.
// Today: the file the loader writes to public/data/latest.json.
// Later: Jerome's API, by setting VITE_PRICES_URL in a .env file.
const PRICES_URL = import.meta.env.VITE_PRICES_URL ?? './data/latest.json'

/** Latest snapshot, or null when there is no data yet. Never throws. */
export async function loadLatestSnapshot(signal?: AbortSignal): Promise<Snapshot | null> {
  try {
    const res = await fetch(PRICES_URL, { signal })
    if (!res.ok) return null
    const data: unknown = await res.json()
    return isSnapshot(data) ? data : null
  } catch {
    // Missing file, network error, or not JSON: show the placeholder.
    return null
  }
}

function isSnapshot(data: unknown): data is Snapshot {
  return typeof data === 'object' && data !== null && Array.isArray((data as Snapshot).rows)
}
