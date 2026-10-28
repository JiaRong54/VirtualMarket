import { Link } from 'react-router'
import type { PriceObservation } from '../types/market'
import { formatAge, formatCount, formatPrice } from '../lib/format'
import { itemPath } from '../lib/history'

interface MarketTableProps {
  rows: PriceObservation[]
  /** Items in the whole snapshot; rows may be only the top slice. */
  total?: number
}

const COLUMNS = ['Item', 'Game', 'Lowest price', 'Listings', 'Source', 'Updated']
const WIDTHS = ['36%', '9%', '14%', '11%', '13%', '17%']
const SKELETON_ROWS = 8

// The main market table. Give it rows and it draws them.
// Give it an empty list and it draws the placeholder.
export function MarketTable({ rows, total = rows.length }: MarketTableProps) {
  const empty = rows.length === 0
  const label = empty
    ? 'awaiting data'
    : rows.length < total
      ? `top ${formatCount(rows.length)} of ${formatCount(total)} by price`
      : `${formatCount(rows.length)} items`

  return (
    <section className="card table-card">
      <div className="card-head">
        <h2>CS2 market</h2>
        <span className="pill">{label}</span>
      </div>

      <div className="table-wrap">
        <table className={empty ? 'market is-empty' : 'market'}>
          <colgroup>
            {WIDTHS.map((w, i) => (
              <col key={i} style={{ width: w }} />
            ))}
          </colgroup>
          <thead>
            <tr>
              {COLUMNS.map((c, i) => (
                <th key={c} className={i >= 2 && i <= 3 ? 'num' : undefined}>
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {empty
              ? Array.from({ length: SKELETON_ROWS }, (_, i) => (
                  <tr key={i} aria-hidden="true">
                    {COLUMNS.map((c, j) => (
                      <td key={c} className={j >= 2 && j <= 3 ? 'num' : undefined}>
                        <span className="bar" style={{ width: `${barWidth(i, j)}%` }} />
                      </td>
                    ))}
                  </tr>
                ))
              : rows.map((r) => (
                  <tr key={`${r.item_name}-${r.timestamp}`}>
                    <td className="item">
                      <Link to={itemPath(r.item_name)} className="item-link">
                        {r.item_name}
                      </Link>
                    </td>
                    <td>
                      <span className="tag">{r.game}</span>
                    </td>
                    <td className="num">{formatPrice(r.lowest_price_minor)}</td>
                    <td className="num">{formatCount(r.listing_count)}</td>
                    <td className="muted">{r.source}</td>
                    <td className="muted">{formatAge(r.timestamp)}</td>
                  </tr>
                ))}
          </tbody>
        </table>

        {empty && (
          <div className="table-overlay">
            <strong>Market table goes here</strong>
            <span>
              Rows appear once a snapshot is loaded. Run the loader to write
              public/data/latest.json, or point VITE_PRICES_URL at the API.
            </span>
          </div>
        )}
      </div>
    </section>
  )
}

// Varied widths so the placeholder rows look like real text, not a grid.
function barWidth(row: number, col: number): number {
  const base = [78, 30, 52, 44, 50, 46][col]
  return base - ((row * 7 + col * 11) % 18)
}
