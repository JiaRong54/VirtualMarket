import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { CompareChart, type Series } from '../components/CompareChart'
import { SERIES_COLORS } from '../lib/seriesColors'
import { formatChange, formatCount, formatPrice } from '../lib/format'
import { itemPath, loadHistoryIndex, loadItemHistory, type HistoryIndexEntry } from '../lib/history'
import { RANGES, type Range } from '../lib/ranges'
import { groupVariants } from '../lib/variants'
import type { Game } from '../types/market'

const MAX_VARIANTS = SERIES_COLORS.length
const SUGGESTIONS = 8

// Variants of the same skin side by side: "AK-47 | Redline" in every wear,
// with and without StatTrak™. Uses the same Steam history files as the item pages.
export function Compare() {
  const [params, setParams] = useSearchParams()
  const game: Game = params.get('game') === 'dota2' ? 'dota2' : 'cs2'
  const skin = params.get('skin') ?? ''

  const [index, setIndex] = useState<{ game: Game; items: HistoryIndexEntry[] } | null>(null)
  const [histories, setHistories] = useState<{ skin: string; series: Series[] } | null>(null)
  const [range, setRange] = useState<Range>('1Y')
  const [query, setQuery] = useState(skin)

  useEffect(() => {
    const controller = new AbortController()
    loadHistoryIndex(controller.signal, game).then((items) => {
      if (!controller.signal.aborted) setIndex({ game, items })
    })
    return () => controller.abort()
  }, [game])

  const items = index?.game === game ? index.items : null
  const groups = useMemo(() => groupVariants(items ?? [], game), [items, game])
  const variants = (groups.get(skin) ?? []).slice(0, MAX_VARIANTS)

  // Skins with the most sales, offered when nothing is picked yet.
  const popular = useMemo(
    () =>
      [...groups.entries()]
        .map(([name, list]) => ({ name, count: list.length, sold: list.reduce((s, v) => s + (v.sold_7d ?? 0), 0) }))
        .sort((a, b) => b.sold - a.sold)
        .slice(0, SUGGESTIONS),
    [groups],
  )

  // Load every variant's daily history for the chart.
  useEffect(() => {
    const list = (groups.get(skin) ?? []).slice(0, MAX_VARIANTS)
    if (list.length === 0) return
    const controller = new AbortController()
    Promise.all(list.map((v) => loadItemHistory(v.file, controller.signal, game))).then((loaded) => {
      if (controller.signal.aborted) return
      setHistories({
        skin,
        series: list.map((v, i) => ({ label: v.variant, points: loaded[i]?.points ?? [] })),
      })
    })
    return () => controller.abort()
  }, [groups, skin, game])

  const series = histories?.skin === skin ? histories.series : null
  const cheapest = Math.min(...variants.map((v) => v.price ?? Infinity))

  function pick(name: string) {
    setQuery(name)
    setParams(game === 'dota2' ? { game, skin: name } : { skin: name })
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (groups.has(query.trim())) pick(query.trim())
  }

  const known = groups.has(query.trim())
  let hint = `${formatCount(groups.size)} ${game === 'dota2' ? 'Dota 2' : 'CS2'} skins come in more than one version`
  if (items === null) hint = 'Loading skins'
  else if (query.trim() && !known) hint = 'No skin with that exact name and more than one version'

  return (
    <>
      <form className="card add-bar" onSubmit={onSubmit}>
        <label htmlFor="compare-skin">Skin</label>
        <input
          id="compare-skin"
          type="text"
          list="compare-skins"
          placeholder={game === 'dota2' ? 'e.g. Dragonclaw Hook' : 'e.g. AK-47 | Redline'}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoComplete="off"
        />
        <datalist id="compare-skins">
          {[...groups.keys()].sort().map((n) => (
            <option key={n} value={n} />
          ))}
        </datalist>
        <button type="submit" disabled={!known}>
          Compare
        </button>
        <span className="add-hint">{hint}</span>
      </form>

      {!skin || variants.length === 0 ? (
        <section className="card">
          <div className="card-head">
            <h2>{skin ? `No versions found for "${skin}"` : 'Most traded skins with several versions'}</h2>
          </div>
          {items !== null && popular.length === 0 ? (
            <div className="empty-state">
              <strong>No history loaded yet</strong>
              <span>Run loader/convert_history.py on the Steam history. This page uses the same files as the item pages.</span>
            </div>
          ) : (
            <div className="chip-row">
              {popular.map((p) => (
                <button key={p.name} type="button" className="chip" onClick={() => pick(p.name)}>
                  {p.name}
                  <small>{p.count} versions</small>
                </button>
              ))}
            </div>
          )}
        </section>
      ) : (
        <>
          <section className="card">
            <div className="card-head">
              <h2>{skin}</h2>
              <span className="pill">{variants.length} versions</span>
            </div>
            <div className="table-wrap">
              <table className="market">
                <colgroup>
                  {['36%', '16%', '16%', '16%', '16%'].map((w, i) => (
                    <col key={i} style={{ width: w }} />
                  ))}
                </colgroup>
                <thead>
                  <tr>
                    <th>Version</th>
                    <th className="num">Price now</th>
                    <th className="num">vs cheapest</th>
                    <th className="num">7 day change</th>
                    <th className="num">Sold (7d)</th>
                  </tr>
                </thead>
                <tbody>
                  {variants.map((v, i) => {
                    const week = v.prev?.['7'] ?? null
                    return (
                      <tr key={v.file}>
                        <td className="item">
                          <i className="swatch" style={{ background: SERIES_COLORS[i] }} />
                          <Link to={itemPath(v.item_name, game)} className="item-link">
                            {v.variant}
                          </Link>
                        </td>
                        <td className="num">{v.price !== undefined ? formatPrice(v.price) : '--'}</td>
                        <td className="num muted">
                          {v.price === undefined || !Number.isFinite(cheapest)
                            ? '--'
                            : v.price === cheapest
                              ? 'cheapest'
                              : `${(v.price / cheapest).toFixed(1)}x`}
                        </td>
                        <td className={`num change ${week === null || v.price === undefined ? '' : v.price >= week ? 'up' : 'down'}`}>
                          {week === null || v.price === undefined ? '--' : formatChange(week, v.price)}
                        </td>
                        <td className="num">{formatCount(v.sold_7d ?? null)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </section>

          <div className="range-row" role="group" aria-label="Time range">
            {RANGES.map((r) => (
              <button
                key={r.id}
                type="button"
                className={r.id === range ? 'range-btn on' : 'range-btn'}
                aria-pressed={r.id === range}
                onClick={() => setRange(r.id)}
              >
                {r.label}
              </button>
            ))}
          </div>

          <section className="card">
            <div className="card-head">
              <h2>Steam median sale price by version</h2>
            </div>
            {series === null ? <div className="chart-empty">Loading</div> : <CompareChart series={series} range={range} />}
            <p className="chart-note">
              One line per version, colored as in the table. Hover to read every version's price on the same day.
            </p>
          </section>
        </>
      )}
    </>
  )
}
