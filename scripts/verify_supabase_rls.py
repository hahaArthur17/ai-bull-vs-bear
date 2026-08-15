#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from app.config import get_settings


@dataclass(frozen=True)
class Session:
    user_id: str
    access_token: str


class RlsVerifier:
    def __init__(
        self,
        supabase_url: str,
        anon_key: str,
        client: httpx.Client | None = None,
    ) -> None:
        self.supabase_url = supabase_url.rstrip("/")
        self.anon_key = anon_key
        self.client = client or httpx.Client(timeout=15.0)

    def sign_in(self, email: str, password: str) -> Session:
        response = self.client.post(
            f"{self.supabase_url}/auth/v1/token",
            params={"grant_type": "password"},
            headers={"apikey": self.anon_key, "Content-Type": "application/json"},
            json={"email": email, "password": password},
        )
        self._require(response, {200}, "sign in")
        payload = response.json()
        return Session(
            user_id=str(payload["user"]["id"]),
            access_token=str(payload["access_token"]),
        )

    def stock_id(self, ticker: str = "AAPL") -> int:
        response = self.client.get(
            f"{self.supabase_url}/rest/v1/stocks",
            params={"select": "id", "ticker": f"eq.{ticker}", "limit": "1"},
            headers={
                "apikey": self.anon_key,
                "Authorization": f"Bearer {self.anon_key}",
            },
        )
        self._require(response, {200}, "read public stock")
        rows = response.json()
        if not rows:
            raise RuntimeError(f"Stock {ticker} is not seeded")
        return int(rows[0]["id"])

    def verify(self, user_a: Session, user_b: Session, stock_id: int) -> dict[str, bool]:
        self._delete_own_watchlist(user_a, stock_id)
        self._delete_own_watchlist(user_b, stock_id)
        try:
            self._insert_watchlist(user_a, user_a.user_id, stock_id)
            owner_rows = self._read_watchlist(user_a, user_a.user_id, stock_id)
            cross_rows_a = self._read_watchlist(user_a, user_b.user_id, stock_id)

            cross_write = self._watchlist_request(
                "POST",
                user_a,
                json={"user_id": user_b.user_id, "stock_id": stock_id},
                prefer="return=minimal",
            )
            cross_write_rejected = cross_write.status_code in {400, 401, 403}

            self._insert_watchlist(user_b, user_b.user_id, stock_id)
            cross_rows_b = self._read_watchlist(user_b, user_a.user_id, stock_id)

            with httpx.Client(timeout=15.0) as reconnect_client:
                reconnected = RlsVerifier(
                    self.supabase_url,
                    self.anon_key,
                    reconnect_client,
                )
                persisted_rows = reconnected._read_watchlist(
                    user_a,
                    user_a.user_id,
                    stock_id,
                )
            report = {
                "owner_read_allowed": len(owner_rows) == 1,
                "cross_user_reads_hidden": cross_rows_a == [] and cross_rows_b == [],
                "cross_user_write_rejected": cross_write_rejected,
                "database_reconnect_persisted": len(persisted_rows) == 1,
            }
            if not all(report.values()):
                raise RuntimeError(f"RLS verification failed: {report}")
            return report
        finally:
            self._delete_own_watchlist(user_a, stock_id)
            self._delete_own_watchlist(user_b, stock_id)

    def _watchlist_request(
        self,
        method: str,
        session: Session,
        **kwargs: object,
    ) -> httpx.Response:
        headers = {
            "apikey": self.anon_key,
            "Authorization": f"Bearer {session.access_token}",
            "Content-Type": "application/json",
        }
        prefer = kwargs.pop("prefer", None)
        if prefer:
            headers["Prefer"] = str(prefer)
        return self.client.request(
            method,
            f"{self.supabase_url}/rest/v1/watchlists",
            headers=headers,
            **kwargs,
        )

    def _insert_watchlist(self, session: Session, user_id: str, stock_id: int) -> None:
        response = self._watchlist_request(
            "POST",
            session,
            json={"user_id": user_id, "stock_id": stock_id},
            prefer="return=minimal",
        )
        self._require(response, {201}, "insert owned watchlist row")

    def _read_watchlist(
        self,
        session: Session,
        user_id: str,
        stock_id: int,
    ) -> list[dict[str, object]]:
        response = self._watchlist_request(
            "GET",
            session,
            params={
                "select": "user_id,stock_id",
                "user_id": f"eq.{user_id}",
                "stock_id": f"eq.{stock_id}",
            },
        )
        self._require(response, {200}, "read watchlist row")
        return response.json()

    def _delete_own_watchlist(self, session: Session, stock_id: int) -> None:
        response = self._watchlist_request(
            "DELETE",
            session,
            params={
                "user_id": f"eq.{session.user_id}",
                "stock_id": f"eq.{stock_id}",
            },
            prefer="return=minimal",
        )
        self._require(response, {200, 204}, "clean up watchlist row")

    @staticmethod
    def _require(response: httpx.Response, statuses: set[int], operation: str) -> None:
        if response.status_code not in statuses:
            raise RuntimeError(f"Supabase {operation} failed with status {response.status_code}")


def main() -> None:
    settings = get_settings()
    required = {
        "SUPABASE_URL": settings.supabase_url,
        "SUPABASE_ANON_KEY": settings.supabase_anon_key,
        "SUPABASE_RLS_USER_A_EMAIL": settings.supabase_rls_user_a_email,
        "SUPABASE_RLS_USER_A_PASSWORD": settings.supabase_rls_user_a_password,
        "SUPABASE_RLS_USER_B_EMAIL": settings.supabase_rls_user_b_email,
        "SUPABASE_RLS_USER_B_PASSWORD": settings.supabase_rls_user_b_password,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")

    verifier = RlsVerifier(str(settings.supabase_url), str(settings.supabase_anon_key))
    user_a = verifier.sign_in(
        str(settings.supabase_rls_user_a_email),
        str(settings.supabase_rls_user_a_password),
    )
    user_b = verifier.sign_in(
        str(settings.supabase_rls_user_b_email),
        str(settings.supabase_rls_user_b_password),
    )
    report = verifier.verify(user_a, user_b, verifier.stock_id())
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
