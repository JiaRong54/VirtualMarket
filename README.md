# VirtualMarket: Game Skin Market Analytics

A read-only analytics website for Steam in-game items (skins) from **Counter-Strike 2** and **Dota 2**. It collects Steam Community Market prices on a schedule, keeps them as a time series, and shows price history, watchlists and price movements.

Capstone project for CSCI 49900 (Fall 2026), Hunter College, CUNY. Team: Arian Berisha and JiaRong (Jerome) Guo.

## Why this project

Steam items can be worth real money, but the Steam Market only shows today's price. It has no long-term history, no alerts for big moves, and no way to see whether a move lines up with a game update.

Price trackers already exist. What they don't publish is a method that connects price moves to game updates, or numbers showing how accurate that connection is. So the research question behind this project is:

> **Do game update events predict measurable price movement, and how accurately?**

The website and the collection pipeline exist to answer that question with data.

## Features

| Feature | Status |
| --- | --- |
| Market table for CS2 and Dota 2, with a game switch | Working |
| Item pages with daily Steam price history charts | Working |
| Game update markers on item charts | Working (needs `timeline/update_events.csv` filled in) |
| Price Movements: biggest gains and drops over 1, 7 and 30 days, filtered by sales | Working |
| Watchlist with change since added (saved in the browser) | Working |
| Automatic anomaly detection (unusual moves flagged) | In progress |
| Update vs. price movement correlation study | In progress |
| Compare versions of the same skin (wear, StatTrak, quality) | Working |
| User accounts | Planned |

The site is read-only on purpose. It never buys, sells or trades items.

## How it works

```
                 Steam Community Market
                          |
                          v
   EC2: backend/steam_sync.py  (systemd timer, about every 5 min)
                          |
          +---------------+-----------------+
          v                                 v
   SQLite on EBS                    website JSON files
   (steam_cloud.db)                 steam-latest.json, history/*.json
          |                                 |
          v                                 v
   backend/history_api.py           frontend (React), served by nginx
   (FastAPI, read-only)
```

1. **Collection.** `steam_sync.py` fetches Steam Market listings and price history in small batches with a delay between requests, so it stays under Steam's rate limits. A systemd timer starts the next batch 5 minutes after the last one finishes.
2. **Storage.** Every observation follows the record shape the team locked in the proposal: item name, game, timestamp, lowest price (in whole cents) and listing count. Prices are kept in cents so float math never loses a cent.
3. **Publishing.** After each batch, the sync writes static JSON files for the website: the latest prices, one file per item's daily history, and an index with each item's recent price changes.
4. **Website.** A React app reads those JSON files. It needs no server code, so any static host works.
5. **Update timeline.** `timeline/update_events.csv` lists game updates from the official patch notes. `loader/build_events.py` turns it into the markers on the charts, and the same file is the input for the correlation study.

### Data source history

The first collector called the Steam Market search endpoint directly, and Steam rejected automated requests with HTTP 429. We then collected from Skinport with an hourly AWS Lambda (see `collector/`). In November 2026 the team settled on Steam as the only source, so the Lambda was retired (its EventBridge rule is disabled, not deleted). `collector/README.md` has the details.

## Repository layout

```
backend/            Steam collection, SQLite storage, read-only API
  steam_sync.py       scheduled collector + website publisher (runs on EC2)
  steam_history.py    resumable Steam price history downloader
  steam_market.py     single-item Steam price lookups
  history_api.py      FastAPI app: GET /api/price-history
  db/schema.sql       tables for items and price observations
loader/             converters from raw data to the website's JSON
  convert_history.py  Steam history -> daily points + price movement stats
  load_steam.py       Steam listings -> steam-latest.json
  load_snapshot.py    old Skinport S3 snapshots -> rows (kept for the record)
  build_events.py     update timeline CSV -> chart markers
  tests/              pytest tests with small made-up samples
frontend/           React + TypeScript website (see frontend/README.md)
timeline/           update_events.csv, the game update timeline
deploy/aws/         install script for the EC2 collector (systemd)
collector/          retired Skinport Lambda, kept for the record
```

## Requirements

| Part | Needs |
| --- | --- |
| Frontend | Node.js 20 or newer, npm |
| Backend and loader | Python 3.9 or newer (the EC2 server); 3.12 used in development |
| Python packages | `fastapi`, `uvicorn` (API); `boto3`, `brotli`, `pytest` (loader); `httpx` (API tests) |
| Deployment | An AWS EC2 instance (Amazon Linux) with nginx, reached through SSM Session Manager |

## Setup and running

Clone the repo:

```bash
git clone https://github.com/JiaRong54/VirtualMarket.git
cd VirtualMarket
```

### 1. Website (local)

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

The site reads data from `frontend/public/data/`. That folder is not in Git (data stays in AWS or on your machine), so a fresh clone shows empty pages until you add data in step 3.

### 2. Tests

```bash
pip install -r loader/requirements.txt -r backend/requirements-api.txt httpx
python -m pytest loader/tests backend
cd frontend && npm run build      # type check + production build
```

### 3. Getting data for the website

Download Steam price history for CS2 (slow on purpose, one request every 15 seconds by default):

```bash
python backend/steam_history.py --appid 730
```

Convert it into the website's files:

```bash
python loader/convert_history.py --in backend/db/steam_history.db --site frontend/public/data
```

Add the game update markers:

```bash
python loader/build_events.py --csv timeline/update_events.csv --site frontend/public/data
```

### 4. API (optional)

```bash
uvicorn backend.history_api:app --reload
# http://127.0.0.1:8000/api/price-history?market_hash_name=AK-47%20%7C%20Redline%20(Field-Tested)
# http://127.0.0.1:8000/docs  for the interactive API page
```

It reads `backend/db/steam_cloud.db`, or the path in the `STEAM_HISTORY_DB` environment variable.

### 5. Deploying the collector on EC2

On the server, as `ssm-user` (not root), from the repo folder:

```bash
bash deploy/aws/install-steam-sync.sh
sudo systemctl start virtualmarket-sync.service          # one test run
sudo journalctl -u virtualmarket-sync.service -n 30 --no-pager
sudo systemctl enable --now virtualmarket-sync.timer     # keep it running
```

The script installs a systemd service and timer, stores data under `backend/db/`, and publishes the website JSON to `/usr/share/nginx/html/data`.

## Using the website

- **Dashboard:** the market table. Switch between CS2 and Dota 2 at the top right. Click an item to open its page.
- **Item page:** daily median sale price chart with 1 month, 6 months, 1 year and All ranges, update markers, and an **Add to watchlist** button.
- **Compare:** pick a skin to see every version (wear, StatTrak, Souvenir) in one table and one chart.
- **Watchlist:** items you follow, their price now, and the change since you added them. Saved in your browser until accounts exist.
- **Price Movements:** the biggest gains or drops over 1, 7 or 30 days. The sales filter hides items that barely trade, since one sale can move their price 50%.

## Evaluation plan

From the proposal, the project is measured on:

1. **Data freshness:** median and worst-case age of stored prices.
2. **Collection reliability:** days of unbroken collection and the number of gaps.
3. **Detection accuracy:** precision and recall of anomaly detection against price events we label by hand.
4. **Cost:** infrastructure cost per million stored observations.
5. **Update correlation:** price movement after known updates compared with normal windows, and whether the difference is statistically meaningful.

Results will be added here as they come in.

## Team and contributions

| Member | Owns |
| --- | --- |
| Arian Berisha | Data acquisition and the cloud layer (source testing, collectors, AWS setup), the frontend website (dashboard, item pages, Price Movements, Watchlist), the update timeline |
| JiaRong (Jerome) Guo | Storage and analysis: database schema, Steam collection and sync on EC2, the backend API, anomaly detection, the correlation study |

The interfaces between the two halves (the stored record shape and the website JSON format) were agreed at the start, so each side can work on its own.

## Course

CSCI 49900, Advanced Applications: A Capstone for Majors. Hunter College, CUNY, Fall 2026.
