import { useCallback, useEffect, useState } from 'react'
import type { Game } from '../types/market'

// The watchlist lives in the browser (localStorage) until user accounts exist.
// Each browser keeps its own list. Clearing site data clears it.

/** What we save for each watched item. */
export interface SavedItem {
  item_name: string
  game: Game
  added_at: string // ISO 8601 in UTC
  added_price_minor: number | null // price in cents when added, null if no price was known
}

const KEY = 'vm-watchlist-v1'
const CHANGED = 'vm-watchlist-changed' // lets every open page update when the list changes

function isSavedItem(x: unknown): x is SavedItem {
  if (typeof x !== 'object' || x === null) return false
  const s = x as SavedItem
  return typeof s.item_name === 'string' && s.item_name.length > 0
    && (s.game === 'cs2' || s.game === 'dota2')
    && typeof s.added_at === 'string'
    && (s.added_price_minor === null || Number.isSafeInteger(s.added_price_minor))
}

/** Saved items, or an empty list if storage is empty, broken, or blocked. */
export function readWatchlist(): SavedItem[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(KEY) ?? '[]')
    return Array.isArray(parsed) ? parsed.filter(isSavedItem) : []
  } catch {
    return []
  }
}

function writeWatchlist(items: SavedItem[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(items))
  } catch {
    // Storage full or blocked (some private windows). The list still works until reload.
  }
  window.dispatchEvent(new Event(CHANGED))
}

const same = (a: SavedItem, name: string, game: Game) => a.item_name === name && a.game === game

/** React hook: the current list plus add/remove helpers. */
export function useWatchlist() {
  const [items, setItems] = useState<SavedItem[]>(readWatchlist)

  useEffect(() => {
    const refresh = () => setItems(readWatchlist())
    window.addEventListener(CHANGED, refresh) // this tab
    window.addEventListener('storage', refresh) // other tabs
    return () => {
      window.removeEventListener(CHANGED, refresh)
      window.removeEventListener('storage', refresh)
    }
  }, [])

  const has = useCallback((name: string, game: Game) => items.some((i) => same(i, name, game)), [items])

  const add = useCallback((name: string, game: Game, priceMinor: number | null) => {
    const current = readWatchlist()
    if (current.some((i) => same(i, name, game))) return
    writeWatchlist([
      ...current,
      { item_name: name, game, added_at: new Date().toISOString(), added_price_minor: priceMinor },
    ])
  }, [])

  const remove = useCallback((name: string, game: Game) => {
    writeWatchlist(readWatchlist().filter((i) => !same(i, name, game)))
  }, [])

  return { items, has, add, remove }
}
