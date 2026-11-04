import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

COOKIE = "vm_session"
TTL = 604800

class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)

class ProfileEdit(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    steam_id: str | None = None

@contextmanager
def connection(path):
    db = sqlite3.connect(path, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        with db:
            yield db
    finally:
        db.close()


def install_accounts(app, db_path=None):
    path = Path(db_path or os.environ.get("USERS_DB", Path(__file__).parent / "db/users.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with connection(path) as db:
        db.executescript("""
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE NOT NULL,display_name TEXT NOT NULL,password_hash TEXT NOT NULL,salt TEXT NOT NULL,steam_id TEXT,created_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,expires_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS login_attempts(email TEXT PRIMARY KEY,failures INTEGER NOT NULL,window_start INTEGER NOT NULL);
""")
    secure = os.environ.get("COOKIE_SECURE", "true").lower() == "true"
    router = APIRouter(prefix="/api")

    @app.middleware("http")
    async def csrf_guard(request: Request, call_next):
        if request.method in {"POST", "PATCH", "DELETE", "PUT"} and request.url.path.startswith("/api/"):
            if request.headers.get("x-virtualmarket") != "1":
                from fastapi.responses import JSONResponse
                return JSONResponse({"detail": "Missing X-VirtualMarket header"}, status_code=403)
        result = await call_next(request)
        if request.url.path.startswith("/api/"):
            result.headers["Cache-Control"] = "no-store"
        return result

    def digest(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def password_hash(password, salt):
        return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()

    def email_key(value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise HTTPException(422, "Invalid email")
        return value

    def current_user(request: Request):
        token = request.cookies.get(COOKIE, "")
        with connection(path) as db:
            user = db.execute("SELECT u.id,u.email,u.display_name,u.steam_id FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token_hash=? AND s.expires_at>?", (digest(token), int(time.time()))).fetchone()
        if user is None:
            raise HTTPException(401, "Login required")
        return dict(user)

    @router.post("/auth/register", status_code=201)
    def register(data: Credentials):
        email = email_key(data.email)
        salt = secrets.token_hex(16)
        hashed = password_hash(data.password, salt)
        try:
            with connection(path) as db:
                db.execute("INSERT INTO users(email,display_name,password_hash,salt,created_at) VALUES(?,?,?,?,?)", (email, email.split("@")[0], hashed, salt, int(time.time())))
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Email already registered") from None
        return {"registered": True}

    @router.post("/auth/login")
    def login(data: Credentials, response: Response):
        email, now = email_key(data.email), int(time.time())
        with connection(path) as db:
            attempt = db.execute("SELECT * FROM login_attempts WHERE email=?", (email,)).fetchone()
            user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if attempt and attempt["failures"] >= 5 and now - attempt["window_start"] < 900:
            raise HTTPException(429, "Try again later", headers={"Retry-After": str(900 - (now - attempt["window_start"]))})
        salt = user["salt"] if user else "00" * 16
        hashed = password_hash(data.password, salt)
        if not user or not hmac.compare_digest(hashed, user["password_hash"]):
            with connection(path) as db:
                reset = not attempt or now - attempt["window_start"] >= 900
                db.execute("INSERT OR REPLACE INTO login_attempts VALUES(?,?,?)", (email, 1 if reset else attempt["failures"] + 1, now if reset else attempt["window_start"]))
            raise HTTPException(401, "Invalid email or password")
        token = secrets.token_urlsafe(32)
        with connection(path) as db:
            db.execute("DELETE FROM login_attempts WHERE email=?", (email,))
            db.execute("DELETE FROM sessions WHERE expires_at<=?", (now,))
            db.execute("INSERT INTO sessions VALUES(?,?,?)", (digest(token), user["id"], now + TTL))
        response.set_cookie(COOKIE, token, max_age=TTL, httponly=True, secure=secure, samesite="strict", path="/")
        return {"logged_in": True}

    @router.post("/auth/logout")
    def logout(request: Request, response: Response):
        with connection(path) as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (digest(request.cookies.get(COOKIE, "")),))
        response.delete_cookie(COOKIE, path="/", secure=secure, httponly=True, samesite="strict")
        return {"logged_out": True}

    @router.get("/me")
    def profile(user=Depends(current_user)):
        return user

    @router.patch("/me")
    def edit_profile(data: ProfileEdit, user=Depends(current_user)):
        name = data.display_name.strip()
        if not name or (data.steam_id is not None and not re.fullmatch(r"[0-9]{17}", data.steam_id)):
            raise HTTPException(422, "Invalid display name or Steam ID")
        with connection(path) as db:
            db.execute("UPDATE users SET display_name=?,steam_id=? WHERE id=?", (name, data.steam_id, user["id"]))
        return {**user, "display_name": name, "steam_id": data.steam_id}

    app.include_router(router)
