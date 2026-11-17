"""Standalone email accounts and local test page; separate from the market API."""
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from backend.UserProfile.accounts import install_accounts

def create_app(db_path=None):
    app = FastAPI(title="VirtualMarket email accounts")
    install_accounts(app, db_path)

    @app.get('/', response_class=HTMLResponse, include_in_schema=False)
    def account_page():
        return HTMLResponse(Path(__file__).with_name('frontend').joinpath('index.html').read_text(encoding='utf-8'),
                            headers={'Cache-Control': 'no-store'})

    return app


app = create_app()
