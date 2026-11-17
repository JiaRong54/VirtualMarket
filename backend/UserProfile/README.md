# Local Email Accounts

This standalone service implements email registration, password login, current
account lookup, logout, and persistent per-account watchlists. It serves a local
test page at `/` and API documentation at `/docs`. The React Profile, Watchlist,
and item pages now use this service through the Vite development proxy. This
change has not been deployed to AWS.
No Steam ID, profile editing, email verification, or password reset is included.

## Files

- `schema.sql`: users, watchlist_items, sessions, login_attempts, and session expiration index.
- `accounts.py`: account routes, password hashing, cookies, and login throttling.
- `watchlist.py`: authenticated list, add, and remove routes.
- `app.py`: standalone FastAPI service and local test page.
- `frontend/index.html`: register, confirm password, login, and logout UI.
- Local-only `tests/test_accounts.py`: lifecycle, isolation, validation, persistence, expiration,
  hashing, throttling, request-header checks, and legacy-schema preservation.
- Local-only `tests/test_watchlist.py`: watchlist persistence, isolation, and validation.
  Test scripts and test data are retained locally and are not included in this upload.

## Run locally

From the repository root, with Python 3.10 or later:

```powershell
python -m pip install -r backend/requirements-api.txt
$env:COOKIE_SECURE = "false"
python -m uvicorn backend.UserProfile.app:app --host 127.0.0.1 --port 8001
```

Open http://127.0.0.1:8001. Register with an email and a 12-128 character password,
then sign in, refresh the page, and sign out. Confirmation is checked in the page
and never stored. Email addresses are normalized to lowercase; email ownership
is not verified. This is for local testing and is not a production-ready auth rollout.

The default database is `backend/db/users.db`. Override with `USERS_DB` if needed.
Startup creates empty tables. Existing accounts and sessions survive restarts.
Passwords use salted scrypt hashes; only hashes of session tokens are stored.
The browser uses HttpOnly, SameSite=Strict cookies. Secure cookies are the default;
COOKIE_SECURE=false is only for local HTTP. Write requests require X-VirtualMarket: 1.
Five failed logins per normalized email within 15 minutes temporarily block login.
Old prototype schemas are rejected without deleting data; migrate them explicitly.

When the local-only test files are present, run
`python -m unittest discover -s backend/UserProfile/tests -v`.

## User watchlist schema

`watchlist_items` stores each account's saved items, linked to `users.id`:

- `user_id`: owning account; deleting the account deletes its saved items.
- `game`: `cs2` or `dota2`.
- `item_name`: exact market item name, including wear or quality.
- `added_at`: original addition time as an ISO 8601 UTC string, matching the frontend.
- `added_price_minor`: original price in whole USD cents, or NULL if unknown.

The primary key `(user_id, game, item_name)` prevents duplicate items within an
account while allowing different users to save the same item. It also supports
looking up the list by user. Startup creates this table without replacing existing
accounts or sessions. Running the schema again preserves existing saved items.

`GET /api/watchlist` returns `{user, items}` for the authenticated account.
`POST /api/watchlist` accepts `game`, `item_name`, and optional
`added_price_minor`; the server sets `added_at`. Repeated adds preserve the
original values. `DELETE /api/watchlist` accepts `game` and `item_name` in a JSON
body. All routes select the owner from the session; payloads cannot set `user_id`.
The frontend sends `X-VirtualMarket-User` with mutations to reject edits from a
stale tab if another tab has switched accounts.

Start this service on port 8001, then run `npm run dev` in `frontend` and open
the frontend's `/#/profile`. Register or sign in, save an item, open Watchlist,
then sign out and back in to restore the list. Both Profile and Watchlist use
the same shared account state. Failed writes show an error and leave the list
unchanged. Session expiration clears the account list when detected.

Old `vm-watchlist-v1` browser data is left untouched but is no longer displayed
or automatically imported into an account. Browser-local data has no verified
owner; an explicit import flow can be added separately.

## Later on AWS

Run the service on EC2 behind the site's HTTPS reverse proxy; SQLite can remain
on persistent EBS storage outside `/usr/share/nginx/html`. Set USERS_DB to that
private path and use secure cookies. Preserve the database during code updates,
back it up, and review migrations before applying them. RDS is optional for later
scaling; this local version does not require it. Add deployment-level rate limits
and review authentication before public access. Do not upload users.db, session
cookies, passwords, or local test databases to GitHub or public S3.

The production proxy must forward `/api/auth/*`, `/api/me`, and `/api/watchlist`
to this service on the same origin as the frontend. Vite's proxy only applies to
`npm run dev`, not static hosting or `npm run preview`. The rest of the market
pages still read exported market data.
