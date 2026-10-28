// Shared data types for the frontend.
// These mirror the record shape we locked in the proposal, so the table
// can take rows straight from the API once it exists.

export type Game = 'cs2' | 'dota2'

/** One price observation for one item at one moment in time. */
export interface PriceObservation {
  item_name: string // Steam market hash name, e.g. "AK-47 | Redline (Field-Tested)"
  game: Game
  timestamp: string // ISO 8601 in UTC, e.g. "2026-10-14T16:00:00Z"
  lowest_price_minor: number // whole cents: 1240 means $12.40
  listing_count: number // how many are for sale right now
  source: string // where the price came from, e.g. "skinport"
}

/** One item on a user's watchlist, with the price when it was added. */
export interface WatchlistEntry {
  item_name: string
  game: Game
  added_at: string // ISO 8601 in UTC
  added_price_minor: number // whole cents when it was added
  latest: PriceObservation // most recent observation for this item
}
