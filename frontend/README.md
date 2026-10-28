# Frontend: Game Skin Market Analytics

The web app for our CSCI 49900 capstone. This is the layout foundation: one page with navigation for every planned section and a placeholder where the main market table goes. No live data is connected yet.

## Stack

| Tool | What it does here |
| --- | --- |
| [React](https://react.dev/learn) | Builds the UI out of components (sidebar, table, pages) |
| [TypeScript](https://www.typescriptlang.org/docs/handbook/intro.html) | JavaScript with types, so a price row always has the fields we expect |
| [Vite](https://vite.dev/guide/) | Runs the dev server and builds the production files |
| [React Router](https://reactrouter.com/) | Switches between sections without reloading the page |

## Run it

Needs Node.js 20 or newer.

```bash
cd frontend
npm install       # first time only
npm run dev       # opens at http://localhost:5173
```

Other commands:

```bash
npm run build     # type-checks, then writes the site to dist/
npm run preview   # serves dist/ to check the production build
npm run lint      # checks code style
```

## Folder map

```
src/
  main.tsx              entry point, loads styles
  App.tsx               routes: which page shows for which URL
  config.ts             the list of sections (sidebar + router read it)
  index.css             all styles; colors are tokens at the top
  types/market.ts       PriceObservation, the shape of one price row
  lib/format.ts         cents to "$12.40", counts, "12 min ago", "+10.0%"
  lib/api.ts            loads the latest snapshot (file today, API later)
  components/
    Layout.tsx          sidebar, top bar, and the slot pages render into
    MarketTable.tsx     the main table; shows placeholder rows when empty
    PagePlaceholder.tsx stand-in for sections not built yet
    Icon.tsx            small inline icons
  pages/
    Dashboard.tsx       summary tiles + market table
    Watchlist.tsx
    Compare.tsx
    Movements.tsx       price movements
    Profile.tsx
```

## Where data plugs in

The dashboard loads the latest snapshot through `src/lib/api.ts`. By default it reads `public/data/latest.json`, the file the loader writes:

```bash
cd loader
python load_snapshot.py --latest --json ../frontend/public/data/latest.json
```

Reload the page and the table shows the 100 most expensive items, with the item count and snapshot age in the tiles. No file means the placeholder.

When Jerome's API is up, point the site at it with a `.env` file in `frontend/` (no code change):

```
VITE_PRICES_URL=https://<api-address>/prices/latest
```

The API needs to return the same shape as `latest.json`: an object with a `rows` list.

### Item pages and Steam history

Each item has a page at `#/item/<name>`. Click an item in the market table, or on the Price Movements page. It shows the current Skinport price next to a chart of Steam sale history. The history comes from `public/data/history/`, written by `loader/convert_history.py --site ../frontend/public/data`.

Game updates show as lines on the chart once `public/data/events.json` exists:

```json
[
  { "date": "2026-10-01", "label": "Operation release" }
]
```

Each row follows the record shape we locked in the proposal:

```ts
interface PriceObservation {
  item_name: string
  game: 'cs2' | 'dota2'
  timestamp: string          // ISO 8601, UTC
  lowest_price_minor: number // whole cents: 1240 = $12.40
  listing_count: number
  source: string             // e.g. "skinport"
}
```

Prices travel as whole cents and only become dollars when drawn on screen. That avoids floating point rounding errors (0.1 + 0.2 is not exactly 0.3 in JavaScript).

## Why the URLs have a `#`

Pages live at `/#/watchlist`, `/#/compare`, and so on. Everything after the `#` stays in the browser and never reaches the server, so any static host (an S3 bucket, GitHub Pages) can serve the whole app from one `index.html` with no extra configuration. If we later put CloudFront in front of S3 and add a rewrite rule, we can switch to clean URLs.

## Adding a section

1. Add an entry to `SECTIONS` in `src/config.ts`
2. Create the page in `src/pages/`
3. Add a `<Route>` for it in `src/App.tsx`
