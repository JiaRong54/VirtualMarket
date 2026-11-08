import type { Game } from '../types/market'
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
  // Added by convert_history.py for the Price Movements page.
  // Missing in an index.json made before that, so they are optional.
  price?: number // last day's price, in cents
  prev?: Record<string, number | null> // price 1, 7 and 30 days before the last day
  sold_7d?: number // units sold over the last 7 days
}

export interface ItemHistory {
  item_name: string
  game: string
  source: string
  points: DailyPoint[]
}

/** A game update to mark on the chart. Written by loader/build_events.py from timeline/update_events.csv. */
export interface UpdateEvent {
  date: string // "2026-10-01"
  label: string
}

const BASE = './data'

async function getJson<T>(url: string, signal?: AbortSignal): Promise<T | null> {
  try {
    const res = await fetch(url, { signal, cache: 'no-cache' })
    if (!res.ok) return null
    return (await res.json()) as T
  } catch {
    // Missing file or not JSON (the dev server answers missing files with the page itself).
    return null
  }
}

export async function loadHistoryIndex(signal?: AbortSignal, game: Game = 'cs2'): Promise<HistoryIndexEntry[]> {
  const data = await getJson<{ items?: HistoryIndexEntry[] }>(`${BASE}${game === 'dota2' ? '/dota2' : ''}/history/index.json`, signal)
  return Array.isArray(data?.items) ? data.items.filter((item) => item.game === game) : []
}

export async function loadItemHistory(file: string, signal?: AbortSignal, game: Game = 'cs2'): Promise<ItemHistory | null> {
  const data = await getJson<ItemHistory>(`${BASE}${game === 'dota2' ? '/dota2' : ''}/history/${encodeURIComponent(file)}`, signal)
  return data && data.game === game && Array.isArray(data.points) ? data : null
}

export async function loadEvents(signal?: AbortSignal, game: Game = 'cs2'): Promise<UpdateEvent[]> {
  const data = await getJson<UpdateEvent[]>(`${BASE}${game === 'dota2' ? '/dota2' : ''}/events.json`, signal)
  return Array.isArray(data) ? data.filter((e) => e && e.date && e.label) : []
}

/** Link to an item's page. Names contain | and spaces, so they are encoded. */
export function itemPath(name: string, game: Game = 'cs2'): string {
  return `${game === 'dota2' ? '/dota2' : ''}/item/${encodeURIComponent(name)}`
}
