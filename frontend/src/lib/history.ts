// Steam price history, written by loader/steam_history.py into public/data/history/.

/** [date "2014-08-14", median sale price in cents, number sold that day] */
export type DailyPoint = [string, number, number]

export interface HistoryIndexEntry {
  item_name: string
  game: string
  file: string
  days: number
  first: string
  last: string
}

export interface ItemHistory {
  item_name: string
  game: string
  source: string
  points: DailyPoint[]
}

/** A game update to mark on the chart. Jerome's timeline goes in data/events.json. */
export interface UpdateEvent {
  date: string // "2026-10-01"
  label: string
}

const BASE = './data'

async function getJson<T>(url: string, signal?: AbortSignal): Promise<T | null> {
  try {
    const res = await fetch(url, { signal })
    if (!res.ok) return null
    return (await res.json()) as T
  } catch {
    // Missing file or not JSON (the dev server answers missing files with the page itself).
    return null
  }
}

export async function loadHistoryIndex(signal?: AbortSignal): Promise<HistoryIndexEntry[]> {
  const data = await getJson<{ items?: HistoryIndexEntry[] }>(`${BASE}/history/index.json`, signal)
  return Array.isArray(data?.items) ? data.items : []
}

export async function loadItemHistory(file: string, signal?: AbortSignal): Promise<ItemHistory | null> {
  const data = await getJson<ItemHistory>(`${BASE}/history/${encodeURIComponent(file)}`, signal)
  return data && Array.isArray(data.points) ? data : null
}

export async function loadEvents(signal?: AbortSignal): Promise<UpdateEvent[]> {
  const data = await getJson<UpdateEvent[]>(`${BASE}/events.json`, signal)
  return Array.isArray(data) ? data.filter((e) => e && e.date && e.label) : []
}

/** Link to an item's page. Names contain | and spaces, so they are encoded. */
export function itemPath(name: string): string {
  return `/item/${encodeURIComponent(name)}`
}
