import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.accounts import install_accounts

class AccountTests(unittest.TestCase):
    def test_account_lifecycle_and_isolation(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"COOKIE_SECURE": "true"}):
            app = FastAPI()
            install_accounts(app, Path(folder) / "users.db")
            headers = {"X-VirtualMarket": "1"}
            with TestClient(app, base_url="https://testserver", headers=headers) as a, TestClient(app, base_url="https://testserver", headers=headers) as b:
                self.assertEqual(a.get("/api/me").status_code, 401)
                for client, email in [(a,"a@example.com"),(b,"b@example.com")]:
                    payload = {"email":email,"password":"long-password-123"}
                    self.assertEqual(client.post("/api/auth/register",json=payload).status_code,201)
                    self.assertEqual(client.post("/api/auth/register",json=payload).status_code,409)
                    login = client.post("/api/auth/login",json=payload)
                    self.assertEqual(login.status_code,200)
                    self.assertIn("HttpOnly",login.headers["set-cookie"])
                    self.assertIn("Secure",login.headers["set-cookie"])
                self.assertNotIn("password_hash",a.get("/api/me").json())
                self.assertEqual(a.patch("/api/me",json={"display_name":"Jerome","steam_id":None}).status_code,200)
                self.assertNotEqual(b.get("/api/me").json()["display_name"],"Jerome")
                self.assertEqual(a.get("/api/watchlist").status_code,404)
                token=a.cookies.get("vm_session")
                self.assertEqual(a.post("/api/auth/logout").status_code,200)
                a.cookies.set("vm_session",token)
                self.assertEqual(a.get("/api/me").status_code,401)
                for _ in range(5):
                    self.assertEqual(a.post("/api/auth/login",json={"email":"a@example.com","password":"wrong-password-123"}).status_code,401)
                self.assertEqual(a.post("/api/auth/login",json={"email":"a@example.com","password":"wrong-password-123"}).status_code,429)
                a.headers.pop("X-VirtualMarket")
                self.assertEqual(a.post("/api/auth/logout").status_code,403)

if __name__ == "__main__":
    unittest.main()
