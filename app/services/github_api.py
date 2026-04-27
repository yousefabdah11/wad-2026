from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings


async def exchange_github_code(code: str) -> str:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
                "redirect_uri": settings.github_redirect_uri,
            },
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
    if "access_token" not in data:
        msg = str(data.get("error_description") or data.get("error") or "token_error")
        raise ValueError(msg)
    return str(data["access_token"])


async def fetch_github_profile(access_token: str) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        user_resp = await client.get("https://api.github.com/user", headers=headers)
        user_resp.raise_for_status()
        profile = user_resp.json()

        email = profile.get("email")
        if email is None:
            emails_resp = await client.get("https://api.github.com/user/emails", headers=headers)
            if emails_resp.status_code == 200:
                rows = emails_resp.json()
                if not isinstance(rows, list):
                    rows = []
                for row in rows:
                    if row.get("primary") and row.get("email"):
                        email = row["email"]
                        break
                    if row.get("verified") and row.get("email") and email is None:
                        email = row["email"]
        profile["resolved_email"] = email
    return profile
