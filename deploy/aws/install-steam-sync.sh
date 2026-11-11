#!/bin/bash
# Run as the regular repository owner, after applying the automation patch.
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "$0")/../.." && pwd)"
RUN_USER="$(id -un)"
if [ "$RUN_USER" = root ]; then
    echo 'Run this script as ssm-user, without sudo; it asks sudo for installation steps.' >&2
    exit 1
fi
test -f "$PROJECT_DIR/loader/load_steam.py"
test -f "$PROJECT_DIR/backend/steam/steam_sync.py"
python3 -c 'import sys; assert sys.version_info >= (3, 9), "Python 3.9+ is required"'
mkdir -p "$PROJECT_DIR/backend/db"
sudo install -d -m 700 -o "$RUN_USER" -g "$(id -gn)" /var/lib/virtualmarket-sync
sudo install -d -m 755 -o "$RUN_USER" -g "$(id -gn)" /usr/share/nginx/html/data
# The publisher owns only the data subtree; website code remains root-owned.
sudo chown -R "$RUN_USER:$(id -gn)" /usr/share/nginx/html/data
sudo tee /etc/systemd/system/virtualmarket-sync.service >/dev/null <<UNIT
[Unit]
Description=Collect CS2 and Dota 2 Steam data and publish website JSON
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
User=$RUN_USER
WorkingDirectory=$PROJECT_DIR
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 -m backend.steam.steam_sync --db "$PROJECT_DIR/backend/db/steam_cloud.db" --market-db "$PROJECT_DIR/backend/db/market.db" --web-data /usr/share/nginx/html/data/csgo2 --cookie-file /var/lib/virtualmarket-sync/steam-session
TimeoutStartSec=30min
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths="$PROJECT_DIR/backend/db" /usr/share/nginx/html/data
UNIT
sudo tee /etc/systemd/system/virtualmarket-sync.timer >/dev/null <<'UNIT'
[Unit]
Description=Continue Steam collection five minutes after each completed batch
[Timer]
OnBootSec=2min
OnUnitInactiveSec=5min
Unit=virtualmarket-sync.service
[Install]
WantedBy=timers.target
UNIT
sudo systemctl daemon-reload
sudo systemd-analyze verify /etc/systemd/system/virtualmarket-sync.service /etc/systemd/system/virtualmarket-sync.timer
echo 'Installed. No timer was started.'
echo 'Test once: sudo systemctl start virtualmarket-sync.service'
echo 'Inspect:   sudo journalctl -u virtualmarket-sync.service -n 30 --no-pager'
echo 'Enable:    sudo systemctl enable --now virtualmarket-sync.timer'
