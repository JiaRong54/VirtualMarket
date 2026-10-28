import { formatAge, formatChange, formatCount, formatPrice } from '../lib/format'
import type { WatchlistEntry } from '../types/market'

const COLUMNS = ['Item', 'Lowest price', 'Change since added', 'Listings', 'Added', '']
const WIDTHS = ['36%', '14%', '17%', '11%', '14%', '8%']

export function Watchlist() {
  // Filled from the user's saved watchlist once login exists.
  const entries: WatchlistEntry[] = []

  const summary = [
    { label: 'Items watched', value: entries.length ? formatCount(entries.length) : '--' },
    { label: 'Biggest gain', value: '--' },
    { label: 'Biggest drop', value: '--' },
  ]

  return (
    <>
      <div className="tiles tiles-3">
        {summary.map((s) => (
          <div className="tile" key={s.label}>
            <span className="tile-label">{s.label}</span>
            <span className="tile-value">{s.value}</span>
            <span className="tile-note">since each item was added</span>
          </div>
        ))}
      </div>

      <form className="card add-bar" onSubmit={(e) => e.preventDefault()}>
        <label htmlFor="add-item">Add an item</label>
        <input
          id="add-item"
          type="text"
          placeholder="Search by name, e.g. AK-47 | Redline (Field-Tested)"
          disabled
        />
        <button type="submit" disabled>
          Add
        </button>
        <span className="add-hint">Available once login is live</span>
      </form>

      <section className="card">
        <div className="card-head">
          <h2>Your watchlist</h2>
          <span className="pill">{formatCount(entries.length)} items</span>
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
                  <th key={i} className={i >= 1 && i <= 3 ? 'num' : undefined}>
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => {
                const change = formatChange(e.added_price_minor, e.latest.lowest_price_minor)
                const dir = e.latest.lowest_price_minor >= e.added_price_minor ? 'up' : 'down'
                return (
                  <tr key={e.item_name}>
                    <td className="item">{e.item_name}</td>
                    <td className="num">{formatPrice(e.latest.lowest_price_minor)}</td>
                    <td className={`num change ${dir}`}>
                      {dir === 'up' ? '▲' : '▼'} {change}
                    </td>
                    <td className="num">{formatCount(e.latest.listing_count)}</td>
                    <td className="muted">{formatAge(e.added_at)}</td>
                    <td>
                      <button type="button" className="link-btn">
                        Remove
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          {entries.length === 0 && (
            <div className="empty-state">
              <strong>No items yet</strong>
              <span>
                Items you add show here with their latest price, how many are for sale, and how
                much the price has moved since you added them.
              </span>
            </div>
          )}
        </div>
      </section>
    </>
  )
}
