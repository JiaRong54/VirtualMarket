import { HashRouter, Navigate, Route, Routes } from 'react-router'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { Watchlist } from './pages/Watchlist'
import { Compare } from './pages/Compare'
import { Movements } from './pages/Movements'
import { Profile } from './pages/Profile'
import { Item } from './pages/Item'

// HashRouter keeps the page name after a # in the URL (/#/watchlist).
// The part after # never reaches the server, so any static host
// (S3, GitHub Pages) serves index.html for every page with no extra setup.
export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="watchlist" element={<Watchlist />} />
          <Route path="compare" element={<Compare />} />
          <Route path="movements" element={<Movements />} />
          <Route path="profile" element={<Profile />} />
          <Route path="item/:name" element={<Item />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </HashRouter>
  )
}
