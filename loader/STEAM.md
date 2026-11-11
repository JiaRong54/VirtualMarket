# Steam listing prices for the website

The dashboard and item listing tiles now read `data/csgo2/steam-latest.json`, not the
legacy Skinport `data/latest.json`. They accept only USD Steam overview/search
observations. History charts still use `convert_history.py` and `data/csgo2/history/`.

## On EC2, from the repository root

After the changed code is available on EC2, export an existing market database:

```bash
python3 loader/load_steam.py --db backend/db/market.db
```

The database is not in Git. Restore your original `market.db` from the migration
files/S3 first, or collect a live observation with the existing Steam backend:

```bash
python3 loader/load_steam.py --name 'AK-47 | Redline (Field-Tested)'
```

This performs one Steam request, saves the result to `backend/db/market.db`, and
exports the latest observation for each supported item. Repeat `--name` to fetch
several exact names, with a default 15-second pause between requests. It does not
start a scheduler or discover the entire market. On Steam failure the command
stops; successfully saved observations remain and the previous site file remains.

The separately prepared AWS collector writes search rows to `cloud_market_items`.
Once that collector is installed and has completed a search page, export them with:

```bash
python3 loader/load_steam.py --cloud-db /var/lib/virtualmarket/steam_history.db
```

Both `--db` and `--cloud-db` can be supplied to combine observations, keeping the
newest per game/item. This exporter does not install the AWS collector. Its current
implementation is in the original local checkout, pending integration/deployment.

Build the frontend after creating the file:

```bash
cd frontend
npm ci
npm run build
```

Vite copies the generated JSON into `dist/data/csgo2/steam-latest.json`. Serve `dist/`
with Nginx. Later data updates need not rebuild the JavaScript: use `--json` to
write directly to the actual web root's `data/csgo2/steam-latest.json`. Grant the exporter
write access to that data directory; do not run the collector as root just to
write web data. The file is replaced atomically and uses mode 0644 for web reads.

If an old `.env` sets `VITE_PRICES_URL` to Skinport, remove that override or point it
at this Steam snapshot before building. The new frontend rejects Skinport rows
even when an override points at an old file.

## Data meanings and limits

- `lowest_price_minor` is a listing price in integer USD cents, never a historical
  median sale price.
- `listing_count` is `null` when the overview endpoint does not provide it. The UI
  shows `--`, not zero or 24-hour sales volume.
- Each row retains its actual observation timestamp. Generating a file does not
  make old observations fresh, and no fixed update frequency is claimed.
- Only CS2 (730) and Dota 2 (570) are displayed because those are the current
  frontend's supported games. Other games are skipped and counted by the exporter.
- A zero-row export fails without replacing the previous published snapshot.
- Search rows require USD requested currency plus matching dollar text and cents.
- Raw databases, generated data, AWS credentials and Steam cookies are not committed.

Test with `python3 -m unittest discover -s loader/tests -p test_load_steam.py -v`.
