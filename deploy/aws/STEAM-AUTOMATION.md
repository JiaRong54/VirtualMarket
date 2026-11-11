# EC2 Steam collection

Run from the repository root as the repository owner. The installer creates
systemd service and timer definitions; it does not start them.

```bash
bash deploy/aws/install-steam-sync.sh
sudo systemctl start virtualmarket-sync.service
sudo journalctl -u virtualmarket-sync.service -n 30 --no-pager
```

The base service collects CS2 into /usr/share/nginx/html/data/csgo2.
Dota 2 requires its own command with --game dota2, a separate database, and
--web-data /usr/share/nginx/html/data/dota2. Existing EC2 drop-ins override
the base commands: inspect systemctl cat virtualmarket-sync.service before
starting collection. Update all old backend/steam_sync.py command paths to
python3 -m backend.steam.steam_sync when deploying this backend layout.

See [data directory migration](CS2-DATA-LAYOUT.md) for existing server steps.
Retain the request delays and cooldown handling. A timer interval is not a
promise that every item's price or history updates at that frequency.

After a successful manual run:

```bash
sudo systemctl enable --now virtualmarket-sync.timer
sudo systemctl list-timers virtualmarket-sync.timer
```

Databases belong in backend/db, outside the public website directory. Keep
Steam session credentials in /var/lib/virtualmarket-sync/steam-session, with
restricted permissions; never commit them. The service reads that file each run.
History prices represent sales history, not current minimum listing prices.
Back up databases independently; the installer does not configure S3 backups.

Publish frontend assets and index.html without overwriting the live data folder.
Stop both timer and service before maintenance. Stopping collection does not
stop EC2 or storage charges.
