import { useState } from 'react'
import { Link } from 'react-router'
import type { Game, PriceObservation } from '../types/market'
import { formatAge, formatCount, formatPrice } from '../lib/format'
import { itemPath } from '../lib/history'

interface MarketTableProps {
  game?: Game
  rows: PriceObservation[]
}

const COLUMNS = ['Item', 'Game', 'Lowest price', 'Listings', 'Source', 'Updated']
const WIDTHS = ['36%', '9%', '14%', '11%', '13%', '17%']
const SKELETON_ROWS = 8

// The main market table. Give it rows and it draws them.
// Give it an empty list and it draws the placeholder.
export function MarketTable({ rows, game = 'cs2' }: MarketTableProps) {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const empty = rows.length === 0
  const pages = Math.max(1, Math.ceil(rows.length / pageSize))
  const currentPage = Math.min(page, pages)
  const start = (currentPage - 1) * pageSize
  const visibleRows = rows.slice(start, start + pageSize)
  const label = empty
    ? 'awaiting data'
    : `${formatCount(start + 1)}–${formatCount(start + visibleRows.length)} of ${formatCount(rows.length)} items`

  return (
    <section className="card table-card">
      <div className="card-head">
        <h2>{game === 'dota2' ? 'Dota 2' : 'CS2'} Steam Market</h2>
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
              : visibleRows.map((r) => (
                  <tr key={`${r.item_name}-${r.timestamp}`}>
                    <td className="item">
                      <Link to={itemPath(r.item_name, game)} className="item-link">
                        {r.item_name}
                      </Link>
                    </td>
                    <td>
                      <span className="tag">{r.game}</span>
                    </td>
                    <td className="num">{formatPrice(r.lowest_price_minor)}</td>
                    <td className="num">{formatCount(r.listing_count)}</td>
                    <td className="muted">{r.source === 'steam_community_overview' || r.source === 'steam_community_search' ? 'Steam Market' : r.source}</td>
                    <td className="muted">{formatAge(r.timestamp)}</td>
                  </tr>
                ))}
          </tbody>
        </table>

        {empty && (
          <div className="table-overlay">
            <strong>No Steam listing prices available yet</strong>
            <span>
              Prices will appear after Steam Market observations are published.
              Historical sale prices are shown separately on item pages.
            </span>
          </div>
        )}
      </div>
      {!empty && (
        <nav className="market-pagination" aria-label="Market table pagination">
          <label>
            Items per page{' '}
            <select value={pageSize} onChange={(event) => {
              setPageSize(Number(event.target.value))
              setPage(1)
            }}>
              {[10, 25, 50, 100].map((size) => <option key={size} value={size}>{size}</option>)}
            </select>
          </label>
          <div className="market-page-buttons">
            <button type="button" disabled={currentPage === 1} onClick={() => setPage(1)}>First</button>
            <button type="button" disabled={currentPage === 1} onClick={() => setPage(currentPage - 1)}>Previous</button>
            <span aria-live="polite">Page {formatCount(currentPage)} of {formatCount(pages)}</span>
            <button type="button" disabled={currentPage === pages} onClick={() => setPage(currentPage + 1)}>Next</button>
            <button type="button" disabled={currentPage === pages} onClick={() => setPage(pages)}>Last</button>
          </div>
        </nav>
      )}
    </section>
  )
}

// Varied widths so the placeholder rows look like real text, not a grid.
function barWidth(row: number, col: number): number {
  const base = [78, 30, 52, 44, 50, 46][col]
  return base - ((row * 7 + col * 11) % 18)
}
