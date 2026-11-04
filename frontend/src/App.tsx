import { HashRouter, Navigate, Route, Routes, useSearchParams } from 'react-router'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { Compare } from './pages/Compare'
import { Movements } from './pages/Movements'
import { Profile } from './pages/Profile'
import { Item } from './pages/Item'

// HashRouter keeps the page name after a # in the URL (/#/profile).
// The part after # never reaches the server, so any static host
// (S3, GitHub Pages) serves index.html for every page with no extra setup.
function MarketPage() {
  const [params] = useSearchParams()
  const game = params.get('game') === 'dota2' ? 'dota2' : 'cs2'
  return <Dashboard key={game} game={game} />
}

export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<MarketPage />} />
          <Route path="dota2" element={<Navigate to="/?game=dota2" replace />} />
          <Route path="dota2/item/:name" element={<Item key="dota2-item" game="dota2" />} />
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
