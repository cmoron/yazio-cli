"""Tests for the Yazio API client."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from yazio_cli import api


@pytest.fixture()
def token_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect token storage to a temp dir."""
    token_path = tmp_path / "yazio" / "token.json"
    monkeypatch.setattr(api, "TOKEN_PATH", token_path)
    return tmp_path


@pytest.fixture()
def valid_token() -> dict:
    return {
        "access_token": "abc123",
        "refresh_token": "ref456",
        "token_type": "bearer",
        "expires_at": time.time() + 3600,
    }


@pytest.fixture()
def expired_token() -> dict:
    return {
        "access_token": "old",
        "refresh_token": "ref456",
        "token_type": "bearer",
        "expires_at": time.time() - 100,
    }


def _mock_response(
    status_code: int = 200, json_data: dict | None = None, text: str = ""
) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.json.return_value = json_data or {}
    return resp


class TestTokenManagement:
    def test_save_and_load_token(self, token_dir: Path, valid_token: dict) -> None:
        api._save_token(valid_token)
        loaded = api._load_token()
        assert loaded is not None
        assert loaded["access_token"] == "abc123"

    def test_load_token_missing(self, token_dir: Path) -> None:
        assert api._load_token() is None

    def test_token_expired(self, expired_token: dict) -> None:
        assert api._token_expired(expired_token) is True

    def test_token_not_expired(self, valid_token: dict) -> None:
        assert api._token_expired(valid_token) is False

    def test_get_token_not_logged_in(self, token_dir: Path) -> None:
        with pytest.raises(api.AuthError, match="Not logged in"):
            api.get_token()

    def test_get_token_valid(self, token_dir: Path, valid_token: dict) -> None:
        api._save_token(valid_token)
        token = api.get_token()
        assert token["access_token"] == "abc123"

    @patch("yazio_cli.api.httpx.post")
    def test_get_token_refreshes_expired(
        self, mock_post: MagicMock, token_dir: Path, expired_token: dict
    ) -> None:
        api._save_token(expired_token)
        new_token = {
            "access_token": "new123",
            "refresh_token": "newref",
            "token_type": "bearer",
            "expires_in": 3600,
        }
        mock_post.return_value = _mock_response(200, new_token)

        token = api.get_token()
        assert token["access_token"] == "new123"
        mock_post.assert_called_once()


class TestLogin:
    @patch("yazio_cli.api.httpx.post")
    def test_login_success(self, mock_post: MagicMock, token_dir: Path) -> None:
        mock_post.return_value = _mock_response(
            200,
            {
                "access_token": "tok",
                "refresh_token": "ref",
                "expires_in": 3600,
            },
        )
        token = api.login("user@test.com", "pass")
        assert token["access_token"] == "tok"
        assert api.TOKEN_PATH.exists()

    @patch("yazio_cli.api.httpx.post")
    def test_login_failure(self, mock_post: MagicMock, token_dir: Path) -> None:
        mock_post.return_value = _mock_response(401, text="Unauthorized")
        with pytest.raises(api.AuthError, match="Login failed"):
            api.login("bad@test.com", "wrong")


class TestApiCalls:
    @patch("yazio_cli.api.httpx.get")
    def test_daily_summary(self, mock_get: MagicMock, token_dir: Path, valid_token: dict) -> None:
        api._save_token(valid_token)
        mock_get.return_value = _mock_response(
            200,
            {
                "goals": {"energy.energy": 2000},
                "water_intake": 1500,
                "steps": 5000,
                "meals": {},
            },
        )
        result = api.daily_summary("2026-04-09")
        assert result["goals"]["energy.energy"] == 2000
        mock_get.assert_called_once()
        assert "/user/widgets/daily-summary?date=2026-04-09" in mock_get.call_args[0][0]

    @patch("yazio_cli.api.httpx.get")
    def test_consumed_items(self, mock_get: MagicMock, token_dir: Path, valid_token: dict) -> None:
        api._save_token(valid_token)
        mock_get.return_value = _mock_response(
            200,
            {
                "products": [{"product_id": "abc", "amount": 100}],
                "simple_products": [],
                "recipe_portions": [],
            },
        )
        result = api.consumed_items("2026-04-09")
        assert len(result["products"]) == 1

    @patch("yazio_cli.api.httpx.get")
    def test_search_products(self, mock_get: MagicMock, token_dir: Path, valid_token: dict) -> None:
        api._save_token(valid_token)
        mock_get.return_value = _mock_response(
            200,
            {
                "products": [{"id": "p1", "name": "Poulet"}],
            },
        )
        result = api.search_products("poulet")
        assert "products" in result

    @patch("yazio_cli.api.httpx.get")
    def test_weight(self, mock_get: MagicMock, token_dir: Path, valid_token: dict) -> None:
        api._save_token(valid_token)
        mock_get.return_value = _mock_response(
            200,
            {
                "items": [{"date": "2026-04-09", "value": 64.5}],
            },
        )
        result = api.weight("2026-03-10", "2026-04-09")
        assert "items" in result
        assert "/user/bodyvalues/weight?start=2026-03-10&end=2026-04-09" in mock_get.call_args[0][0]

    @patch("yazio_cli.api.httpx.get")
    def test_api_error_raised(
        self, mock_get: MagicMock, token_dir: Path, valid_token: dict
    ) -> None:
        api._save_token(valid_token)
        mock_get.return_value = _mock_response(400, text="Bad Request")
        with pytest.raises(api.ApiError, match="HTTP 400"):
            api.daily_summary("2026-04-09")

    @patch("yazio_cli.api.httpx.get")
    def test_204_returns_empty(
        self, mock_get: MagicMock, token_dir: Path, valid_token: dict
    ) -> None:
        api._save_token(valid_token)
        mock_get.return_value = _mock_response(204)
        result = api.water_intake("2026-04-09")
        assert result == {}

    @patch("yazio_cli.api.httpx.post")
    def test_add_consumed_item(
        self, mock_post: MagicMock, token_dir: Path, valid_token: dict
    ) -> None:
        api._save_token(valid_token)
        mock_post.return_value = _mock_response(200, {"ok": True})
        result = api.add_consumed_item("prod1", 150.0, "2026-04-09", "lunch")
        assert result["ok"] is True
        call_kwargs = mock_post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["products"][0]["product_id"] == "prod1"
        assert body["products"][0]["amount"] == 150.0

    @patch("yazio_cli.api.httpx.request")
    def test_remove_consumed_item(
        self, mock_req: MagicMock, token_dir: Path, valid_token: dict
    ) -> None:
        api._save_token(valid_token)
        mock_req.return_value = _mock_response(200)
        api.remove_consumed_item("item-uuid")
        mock_req.assert_called_once()
        assert mock_req.call_args[0][0] == "DELETE"


class TestWebLogin:
    @patch("yazio_cli.api.httpx.get")
    @patch("yazio_cli.api.httpx.Client")
    def test_web_login_success(
        self, mock_client_cls: MagicMock, mock_get: MagicMock, token_dir: Path
    ) -> None:
        html = (
            'stuff before {"accessToken":107,"refreshToken":109},'
            '["Ref",108],"aabbccdd00112233445566778899aabbccddeeff00112233445566",'
            '["Ref",110],"ffeeddccbbaa99887766554433221100ffeeddccbbaa99887766" more'
        )
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get.return_value = _mock_response(200, text=html)
        mock_client.get.return_value.text = html

        mock_get.return_value = _mock_response(200)

        token = api.web_login("Fe26.2**fakecookie")
        assert token["access_token"] == "aabbccdd00112233445566778899aabbccddeeff00112233445566"
        assert token["refresh_token"] == "ffeeddccbbaa99887766554433221100ffeeddccbbaa99887766"
        assert api.TOKEN_PATH.exists()

    @patch("yazio_cli.api.httpx.Client")
    def test_web_login_no_token_in_html(self, mock_client_cls: MagicMock, token_dir: Path) -> None:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get.return_value = _mock_response(200)
        mock_client.get.return_value.text = "<html>no tokens here</html>"

        with pytest.raises(api.AuthError, match="No accessToken"):
            api.web_login("bad-cookie")
