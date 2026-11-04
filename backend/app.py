from backend.history_api import create_app
from backend.accounts import install_accounts

app = create_app()
install_accounts(app)
