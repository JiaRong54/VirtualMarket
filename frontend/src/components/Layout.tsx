import { NavLink, Outlet, useLocation } from 'react-router'
import { PIPELINE, SECTIONS } from '../config'
import { Icon } from './Icon'

// The frame every page sits inside: sidebar on the left, top bar,
// and an <Outlet /> where the current page is drawn.
export function Layout() {
  const { pathname } = useLocation()
  const current = pathname.startsWith('/item/')
    ? { label: 'Item details', blurb: 'Steam sales history next to the current Skinport price' }
    : (SECTIONS.find((s) => s.path === pathname) ?? SECTIONS[0])

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          Game Skin
          <small>Market Analytics</small>
        </div>

        <nav className="nav" aria-label="Sections">
          {SECTIONS.map((s) => (
            <NavLink key={s.path} to={s.path} end={s.path === '/'} className="nav-link">
              <Icon name={s.icon} />
              {s.label}
            </NavLink>
          ))}
        </nav>

        <dl className="pipeline">
          <div>
            <dt>Source</dt>
            <dd>{PIPELINE.source}</dd>
          </div>
          <div>
            <dt>Refresh</dt>
            <dd>{PIPELINE.refresh}</dd>
          </div>
          <div>
            <dt>Game</dt>
            <dd>{PIPELINE.game}</dd>
          </div>
        </dl>
      </aside>

      <div className="main">
        <div className="banner">Development build. Backend API not connected yet.</div>

        <header className="topbar">
          <div>
            <h1>{current.label}</h1>
            <p>{current.blurb}</p>
          </div>
          <div className="topbar-tools">
            <div className="game-switch" role="group" aria-label="Game">
              <button type="button" className="on">
                CS2
              </button>
              <button type="button" disabled title="Coming after CS2 is validated">
                Dota 2
              </button>
            </div>
            <input className="search" type="search" placeholder="Search items" disabled />
          </div>
        </header>

        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
