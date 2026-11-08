import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router'
import { loadLatestSnapshot } from '../lib/api'
import { formatAge, formatChange, formatCount, formatPrice } from '../lib/format'
import { itemPath, loadHistoryIndex } from '../lib/history'
import { useWatchlist } from '../lib/watchlist'
import type { Game } from '../types/market'

const GAMES: Game[] = ['cs2', 'dota2']
const COLUMNS = ['Item', 'Game', 'Price now', 'Change since added', 'Listings', 'Added', '']
const WIDTHS = ['34%', '8%', '12%', '15%', '10%', '12%', '9%']

/** Latest known price and listing count for one item. */
interface Quote {
  price: number | null // cents
  listings: number | null
}

const keyOf = (game: Game, name: string) => `${game}|${name}`

// Builds "game|name" -> latest price for every item we have data for.
// Uses the newest Steam listing when there is one, otherwise the last daily sale median.
async function loadQuotes(signal: AbortSignal): Promise<Map<string, Quote>> {
  const quotes = new Map<string, Quote>()
  const results = await Promise.all(
    GAMES.map(async (game) => ({
      game,
      index: await loadHistoryIndex(signal, game),
      snapshot: await loadLatestSnapshot(signal, game),
    })),
  )
  for (const { game, index, snapshot } of results) {
    for (const entry of index) {
      quotes.set(keyOf(game, entry.item_name), { price: entry.price ?? null, listings: null })
    }
    for (const row of snapshot?.rows ?? []) {
      quotes.set(keyOf(game, row.item_name), { price: row.lowest_price_minor, listings: row.listing_count })
    }
  }
  return quotes
}

export function Watchlist() {
  const { items, add, remove, has } = useWatchlist()
  const [quotes, setQuotes] = useState<Map<string, Quote> | null>(null)
  const [query, setQuery] = useState('')
  const [game, setGame] = useState<Game>('cs2')

  useEffect(() => {
    const controller = new AbortController()
    loadQuotes(controller.signal).then((q) => {
      if (!controller.signal.aborted) setQuotes(q)
    })
    return () => controller.abort()
  }, [])

  // Names offered in the add box, for the selected game.
  const names = useMemo(() => {
    const prefix = `${game}|`
    return [...(quotes?.keys() ?? [])].filter((k) => k.startsWith(prefix)).map((k) => k.slice(prefix.length)).sort()
  }, [quotes, game])

  const rows = items.map((saved) => {
    const quote = quotes?.get(keyOf(saved.game, saved.item_name)) ?? null
    const now = quote?.price ?? null
    const from = saved.added_price_minor
    const pct = now !== null && from !== null && from > 0 ? (now - from) / from : null
    return { saved, quote, now, pct }
  })

  const moved = rows.filter((r) => r.pct !== null)
  const best = moved.reduce<(typeof rows)[number] | null>((b, r) => (b === null || r.pct! > b.pct! ? r : b), null)
  const worst = moved.reduce<(typeof rows)[number] | null>((w, r) => (w === null || r.pct! < w.pct! ? r : w), null)

  const summary = [
    { label: 'Items watched', value: formatCount(items.length), note: 'saved in this browser' },
    {
      label: 'Biggest gain',
      value: best && best.pct! > 0 ? formatChange(best.saved.added_price_minor!, best.now!) : '--',
      note: best && best.pct! > 0 ? best.saved.item_name : 'since each item was added',
    },
    {
      label: 'Biggest drop',
      value: worst && worst.pct! < 0 ? formatChange(worst.saved.added_price_minor!, worst.now!) : '--',
      note: worst && worst.pct! < 0 ? worst.saved.item_name : 'since each item was added',
    },
  ]

  const trimmed = query.trim()
  const known = names.includes(trimmed)
  const canAdd = known && !has(trimmed, game)

  function onAdd(e: React.FormEvent) {
    e.preventDefault()
    if (!canAdd) return
    add(trimmed, game, quotes?.get(keyOf(game, trimmed))?.price ?? null)
    setQuery('')
  }

  let hint = 'Pick a name from the list'
  if (quotes === null) hint = 'Loading item names'
  else if (trimmed && !known) hint = 'No item with that exact name'
  else if (known && !canAdd) hint = 'Already on your watchlist'

  return (
    <>
      <div className="tiles tiles-3">
        {summary.map((s) => (
          <div className="tile" key={s.label}>
            <span className="tile-label">{s.label}</span>
            <span className="tile-value">{s.value}</span>
            <span className="tile-note">{s.note}</span>
          </div>
        ))}
      </div>

      <form className="card add-bar" onSubmit={onAdd}>
        <label htmlFor="add-item">Add an item</label>
        <select value={game} onChange={(e) => setGame(e.target.value as Game)} aria-label="Game">
          <option value="cs2">CS2</option>
          <option value="dota2">Dota 2</option>
        </select>
        <input
          id="add-item"
          type="text"
          list="watch-names"
          placeholder="Start typing, e.g. AK-47 | Redline (Field-Tested)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoComplete="off"
        />
        <datalist id="watch-names">
          {names.map((n) => (
            <option key={n} value={n} />
          ))}
        </datalist>
        <button type="submit" disabled={!canAdd}>
          Add
        </button>
        <span className="add-hint">{hint}. You can also add items from their item page.</span>
      </form>

      <section className="card">
        <div className="card-head">
          <h2>Your watchlist</h2>
          <span className="pill">{formatCount(items.length)} items</span>
        </div>

        <div className="table-wrap">
          <table className="market">
            <colgroup>
              {WIDTHS.map((w, i) => (
                <col key={i} style={{ width: w }} />
              ))}
            </colgroup>
            <thead>
              <tr>
                {COLUMNS.map((c, i) => (
                  <th key={i} className={i >= 2 && i <= 4 ? 'num' : undefined}>
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(({ saved, quote, now, pct }) => (
                <tr key={keyOf(saved.game, saved.item_name)}>
                  <td className="item">
                    <Link to={itemPath(saved.item_name, saved.game)} className="item-link">
                      {saved.item_name}
                    </Link>
                  </td>
                  <td className="muted">{saved.game === 'dota2' ? 'DOTA 2' : 'CS2'}</td>
                  <td className="num">{now !== null ? formatPrice(now) : quotes === null ? '...' : '--'}</td>
                  <td className={`num change ${pct === null ? '' : pct >= 0 ? 'up' : 'down'}`}>
                    {pct === null ? '--' : `${pct >= 0 ? '▲' : '▼'} ${formatChange(saved.added_price_minor!, now!)}`}
                  </td>
                  <td className="num">{formatCount(quote?.listings ?? null)}</td>
                  <td className="muted">{formatAge(saved.added_at)}</td>
                  <td>
                    <button type="button" className="link-btn" onClick={() => remove(saved.item_name, saved.game)}>
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {items.length === 0 && (
            <div className="empty-state">
              <strong>No items yet</strong>
              <span>
                Add items above or from any item page. Each one shows its latest price, how many are for sale, and
                how much the price has moved since you added it.
              </span>
            </div>
          )}
        </div>
      </section>
    </>
  )
}
