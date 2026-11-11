# CS2 website data directory

The game identifier remains `cs2` (Steam app 730). Its website directory is
`data/csgo2`; Dota 2 remains in `data/dota2`.

| Publisher | Output argument |
| --- | --- |
| CS2 sync | `--web-data /usr/share/nginx/html/data/csgo2` |
| Dota 2 sync | `--web-data /usr/share/nginx/html/data/dota2` |
| CS2 history converter | `--site frontend/public/data/csgo2` |
| Timeline converter (both games) | `--site frontend/public/data` |

The timeline converter takes the parent directory and creates both game folders.
The history converter and sync publisher take the individual game's directory.
If `VITE_PRICES_URL` is configured, update it as well: it overrides the CS2 URL.

## Existing EC2 deployment

Stop the sync timer and service before copying data. Keep Nginx running.
Back up the deployed frontend and service configuration first. Copy, do not
delete, the old CS2 files:

```bash
sudo systemctl stop virtualmarket-sync.timer
sudo systemctl stop virtualmarket-sync.service
sudo install -d -o ssm-user -g ssm-user -m 755 /usr/share/nginx/html/data/csgo2
sudo cp -a /usr/share/nginx/html/data/history /usr/share/nginx/html/data/csgo2/
sudo cp -a /usr/share/nginx/html/data/steam-latest.json /usr/share/nginx/html/data/csgo2/
sudo cp -a /usr/share/nginx/html/data/steam-status.json /usr/share/nginx/html/data/csgo2/
if sudo test -f /usr/share/nginx/html/data/events.json; then
  sudo cp -a /usr/share/nginx/html/data/events.json /usr/share/nginx/html/data/csgo2/
fi
```

Update the effective CS2 ExecStart `--web-data` argument to the CS2 folder.
On the existing server, `zz-batch-size.conf` overrides the main service command,
so editing only the base service is insufficient. Preserve the cookie path,
delay, history limit, and Dota 2 ExecStartPost. Run `systemctl daemon-reload`
after editing and inspect the effective commands before starting collection.

The current local backend was reorganized to `backend.steam.steam_sync`.
If deploying that reorganization, update BOTH game commands to use
`/usr/bin/python3 -m backend.steam.steam_sync` rather than the removed file path.
The working directory must remain the repository root.

Build the integrated frontend, including Compare and Watchlist. Deploy assets and
index.html from the resulting build, without copying dist/data over live data.
Check CS2 and Dota 2 quotes and history in the browser. Generate events only
after reviewing and merging real timeline rows; a header-only CSV clears events.
Run one sync batch successfully, then restart the timer. Keep the old root-level
CS2 files until validation and rollback are no longer needed.

Source code, tests, and these instructions belong in GitHub. Runtime JSON,
databases, credentials, and generated frontend builds do not.
