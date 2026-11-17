"""Account-owned watchlists; the session, never request data, selects the owner."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .accounts import connection


class ItemKey(BaseModel):
    model_config = ConfigDict(extra="forbid")
    game: Literal["cs2", "dota2"]
    item_name: str = Field(min_length=1, max_length=512, pattern=r"\S")


class NewItem(ItemKey):
    added_price_minor: int | None = Field(default=None, strict=True, ge=0, le=9007199254740991)


def install_watchlist(app, db_path, current_user):
    """Register routes using the existing account session validator."""
    router = APIRouter(prefix="/api/watchlist")

    def write_user(request: Request, user=Depends(current_user)):
        # A stale tab must not modify a different account after another tab logs in.
        expected = request.headers.get("X-VirtualMarket-User")
        if expected is not None and expected != str(user["id"]):
            raise HTTPException(409, "Account changed. Refresh before editing your watchlist.")
        return user

    @router.get("")
    def get_watchlist(user=Depends(current_user)):
        """Return this account and its saved list, even without market data."""
        with connection(db_path) as db:
            rows = db.execute(
                "SELECT game,item_name,added_at,added_price_minor FROM watchlist_items "
                "WHERE user_id=? ORDER BY added_at DESC,game,item_name", (user["id"],)
            ).fetchall()
        return {"user": user, "items": [dict(row) for row in rows]}

    @router.post("")
    def add_watchlist_item(item: NewItem, user=Depends(write_user)):
        """Save once; repeated requests preserve the original time and price."""
        added_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        with connection(db_path) as db:
            db.execute(
                "INSERT INTO watchlist_items(user_id,game,item_name,added_at,added_price_minor) "
                "VALUES(?,?,?,?,?) ON CONFLICT(user_id,game,item_name) DO NOTHING",
                (user["id"], item.game, item.item_name, added_at, item.added_price_minor),
            )
            row = db.execute(
                "SELECT game,item_name,added_at,added_price_minor FROM watchlist_items "
                "WHERE user_id=? AND game=? AND item_name=?",
                (user["id"], item.game, item.item_name),
            ).fetchone()
        return dict(row)

    @router.delete("")
    def remove_watchlist_item(item: ItemKey, user=Depends(write_user)):
        """Delete only this user's matching item; retries are harmless."""
        with connection(db_path) as db:
            db.execute("DELETE FROM watchlist_items WHERE user_id=? AND game=? AND item_name=?",
                       (user["id"], item.game, item.item_name))
        return {"removed": True}

    app.include_router(router)
