# Backend Layout

Run all commands from the repository root with Python 3.10 or later.

- api/: read-only market history HTTP API.
- steam/: Steam download, collection, and website publishing.
- db/: database utilities, schema, and ignored runtime databases.
- tests/: market API and Steam tests.
- docs/: API documentation.
- requirements-api.txt: API runtime and HTTP test dependencies.

## Commands

```bash
python -m pip install -r backend/requirements-api.txt
python -m uvicorn backend.api.history_api:app --host 127.0.0.1 --port 8000
python -m backend.steam.steam_history --help
python -m backend.steam.steam_market --help
python -m backend.steam.steam_sync --help
python -m unittest discover -s backend/tests -t . -v
```

Database files remain in backend/db. Environment overrides remain supported.
Use module commands instead of executing moved files directly.

## Later Deployment

The installation script now uses backend.steam.steam_sync. Before deploying,
stop the existing sync timer and service, update the code, and rerun
bash deploy/aws/install-steam-sync.sh. Validate one run before enabling the timer.
Existing installed services retain the old path until reconfigured.
Custom history API services must use backend.api.history_api:app.
Archived ZIPs and patches in output/ and tmp/ remain historical snapshots;
regenerate deployment packages from the new layout before deploying.
No AWS changes were made during this local reorganization.
