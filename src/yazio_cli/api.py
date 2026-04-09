"""Yazio API client — unofficial, reverse-engineered from https://github.com/juriadams/yazio"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx

JsonDict = dict[str, Any]

BASE_URL = "https://yzapi.yazio.com/v15"
WEB_URL = "https://www.yazio.com"
CLIENT_ID = "1_4hiybetvfksgw40o0sog4s884kwc840wwso8go4k8c04goo4c"
CLIENT_SECRET = "6rok2m65xuskgkgogw40wkkk8sw0osg84s8cggsc4woos4s8o"

TOKEN_PATH = Path.home() / ".config" / "yazio" / "token.json"


class AuthError(Exception):
    pass


class ApiError(Exception):
    def __init__(self, status: int, body: str):
        self.status = status
        self.body = body
        super().__init__(f"HTTP {status}: {body}")


def _save_token(token: JsonDict) -> None:
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(json.dumps(token, indent=2))


def _load_token() -> JsonDict | None:
    if not TOKEN_PATH.exists():
        return None
    result: JsonDict = json.loads(TOKEN_PATH.read_text())
    return result


def _token_expired(token: JsonDict) -> bool:
    expires_at: float = token.get("expires_at", 0)
    return time.time() >= expires_at


def login(username: str, password: str) -> JsonDict:
    """Authenticate with Yazio and cache the token."""
    resp = httpx.post(
        f"{BASE_URL}/oauth/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "password",
            "username": username,
            "password": password,
        },
    )
    if resp.status_code != 200:
        raise AuthError(f"Login failed ({resp.status_code}): {resp.text}")
    token: JsonDict = resp.json()
    token["expires_at"] = time.time() + token.get("expires_in", 3600)
    _save_token(token)
    return token


def _refresh(token: JsonDict) -> JsonDict:
    """Refresh an expired token."""
    resp = httpx.post(
        f"{BASE_URL}/oauth/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": token["refresh_token"],
        },
    )
    if resp.status_code != 200:
        raise AuthError(f"Token refresh failed ({resp.status_code}): {resp.text}")
    new_token: JsonDict = resp.json()
    new_token["expires_at"] = time.time() + new_token.get("expires_in", 3600)
    _save_token(new_token)
    return new_token


def web_login(session_cookie: str) -> JsonDict:
    """Extract API tokens from the Yazio web session cookie."""
    import re

    client = httpx.Client(
        cookies={"yz_session": session_cookie},
        headers={"User-Agent": "Mozilla/5.0"},
        follow_redirects=True,
    )
    resp = client.get(f"{WEB_URL}/fr/app/account")
    if resp.status_code != 200:
        raise AuthError(f"Web login failed ({resp.status_code})")

    text = resp.text
    idx = text.find("accessToken")
    if idx < 0:
        raise AuthError("No accessToken found in web page — session cookie may be expired")

    chunk = text[idx : idx + 600]
    tokens = re.findall(r'"([a-f0-9]{40,})"', chunk)
    if len(tokens) < 2:
        raise AuthError(f"Could not extract tokens from web page (found {len(tokens)} candidates)")

    token = {
        "access_token": tokens[0],
        "refresh_token": tokens[1],
        "token_type": "bearer",
        "expires_at": time.time() + 3600,
    }

    # Verify the token works
    test = httpx.get(
        f"{BASE_URL}/user/goals/unmodified?date=2026-01-01",
        headers={"Authorization": f"Bearer {token['access_token']}"},
    )
    if test.status_code != 200:
        raise AuthError(f"Extracted token is invalid (API returned {test.status_code})")

    _save_token(token)
    return token


def get_token() -> JsonDict:
    """Load a valid token, refreshing if needed."""
    token = _load_token()
    if token is None:
        raise AuthError("Not logged in. Run: yazio login  OR  yazio web-login")
    if _token_expired(token):
        token = _refresh(token)
    return token


def _headers(token: JsonDict) -> dict[str, str]:
    return {"Authorization": f"Bearer {token['access_token']}"}


def _get(path: str, token: JsonDict | None = None) -> JsonDict:
    if token is None:
        token = get_token()
    resp = httpx.get(f"{BASE_URL}{path}", headers=_headers(token))
    if resp.status_code == 204:
        return {}
    if resp.status_code >= 400:
        raise ApiError(resp.status_code, resp.text)
    result: JsonDict = resp.json()
    return result


def _post(path: str, body: JsonDict, token: JsonDict | None = None) -> JsonDict:
    if token is None:
        token = get_token()
    resp = httpx.post(f"{BASE_URL}{path}", json=body, headers=_headers(token))
    if resp.status_code == 204:
        return {}
    if resp.status_code >= 400:
        raise ApiError(resp.status_code, resp.text)
    result: JsonDict = resp.json()
    return result


def _delete(path: str, body: list[Any] | JsonDict, token: JsonDict | None = None) -> None:
    if token is None:
        token = get_token()
    resp = httpx.request("DELETE", f"{BASE_URL}{path}", json=body, headers=_headers(token))
    if resp.status_code >= 400:
        raise ApiError(resp.status_code, resp.text)


# --- Public API ---


def daily_summary(date: str) -> JsonDict:
    return _get(f"/user/widgets/daily-summary?date={date}")


def consumed_items(date: str) -> JsonDict:
    return _get(f"/user/consumed-items?date={date}")


def water_intake(date: str) -> JsonDict:
    return _get(f"/user/water-intake?date={date}")


def goals(date: str) -> JsonDict:
    return _get(f"/user/goals/unmodified?date={date}")


def exercises(date: str) -> JsonDict:
    return _get(f"/user/exercises?date={date}")


def weight(start: str, end: str) -> JsonDict:
    return _get(f"/user/bodyvalues/weight?start={start}&end={end}")


def settings() -> JsonDict:
    return _get("/user/settings")


def search_products(query: str, country: str = "FR", sex: str = "male") -> list[JsonDict]:
    result: list[JsonDict] = _get(  # type: ignore[assignment]
        f"/products/search?query={query}&countries={country}&sex={sex}"
    )
    return result


def get_product(product_id: str) -> JsonDict:
    return _get(f"/products/{product_id}")


def add_consumed_item(
    product_id: str,
    amount: float,
    date: str,
    meal: str,
    serving_id: str | None = None,
) -> JsonDict:
    entry: JsonDict = {
        "product_id": product_id,
        "date": date,
        "daytime": meal,
        "amount": amount,
    }
    if serving_id:
        entry["serving_id"] = serving_id
    return _post("/user/consumed-items", {"products": [entry]})


def remove_consumed_item(item_id: str) -> None:
    _delete("/user/consumed-items", [item_id])
