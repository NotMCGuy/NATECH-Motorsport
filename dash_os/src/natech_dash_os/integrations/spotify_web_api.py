from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

SPOTIFY_ACCOUNTS_URL = "https://accounts.spotify.com"
SPOTIFY_API_BASE_URL = "https://api.spotify.com/v1"
SPOTIFY_AUTH_TOKEN_URL = f"{SPOTIFY_ACCOUNTS_URL}/api/token"
DEFAULT_REDIRECT_URI = "http://127.0.0.1:8765/callback"
DEFAULT_SCOPES: tuple[str, ...] = (
    "user-modify-playback-state",
    "user-read-currently-playing",
)


@dataclass(slots=True)
class SpotifyNowPlaying:
    is_playing: bool
    track_name: str
    artists: str
    album: str
    progress_ms: int
    duration_ms: int
    device_name: str
    artwork_url: str


def _token_store_path_from_env() -> Path:
    configured = os.getenv("SPOTIFY_TOKEN_STORE", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".natech_dash_os" / "spotify_tokens.json"


def _base64_url_no_padding(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _pkce_code_challenge(verifier: str) -> str:
    hashed = hashlib.sha256(verifier.encode("ascii")).digest()
    return _base64_url_no_padding(hashed)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_retry_after_seconds(raw: str | None) -> float | None:
    if raw is None:
        return None
    try:
        parsed = float(raw.strip())
    except ValueError:
        return None
    return max(0.0, parsed)


def _redirect_uri_is_valid(redirect_uri: str) -> bool:
    parsed = urlparse(redirect_uri)
    if parsed.scheme == "https":
        return True
    if parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "::1"}:
        return True
    return False


class SpotifyWebApiClient:
    def __init__(
        self,
        access_token: str,
        *,
        client_id: str | None = None,
        refresh_token: str | None = None,
        redirect_uri: str = DEFAULT_REDIRECT_URI,
        scopes: tuple[str, ...] = DEFAULT_SCOPES,
        token_store_path: Path | None = None,
    ) -> None:
        access = access_token.strip()
        if not access:
            raise ValueError("Spotify access token cannot be empty.")
        redirect = redirect_uri.strip() or DEFAULT_REDIRECT_URI
        if not _redirect_uri_is_valid(redirect):
            raise ValueError(
                "Spotify redirect URI must be HTTPS, or loopback HTTP (127.0.0.1 / [::1]) for local development."
            )

        self.access_token = access
        self.client_id = client_id.strip() if client_id else None
        self.refresh_token = refresh_token.strip() if refresh_token else None
        self.redirect_uri = redirect
        self.scopes = tuple(scope for scope in scopes if scope)
        self.token_store_path = token_store_path or _token_store_path_from_env()

        self._last_error = ""
        self._pkce_state: str | None = None
        self._pkce_code_verifier: str | None = None

    @property
    def last_error(self) -> str:
        return self._last_error

    @classmethod
    def from_environment(cls) -> "SpotifyWebApiClient | None":
        token_store_path = _token_store_path_from_env()
        token = os.getenv("SPOTIFY_ACCESS_TOKEN", "").strip()
        client_id = os.getenv("SPOTIFY_CLIENT_ID", "").strip() or None
        refresh_token = os.getenv("SPOTIFY_REFRESH_TOKEN", "").strip() or None
        redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "").strip() or DEFAULT_REDIRECT_URI

        scopes_env = os.getenv("SPOTIFY_SCOPES", "").strip()
        if scopes_env:
            scopes = tuple(scope for scope in (part.strip() for part in scopes_env.split()) if scope)
        else:
            scopes = DEFAULT_SCOPES

        stored = cls._load_tokens(token_store_path)
        if stored is not None:
            stored_access = stored.get("access_token")
            if isinstance(stored_access, str) and stored_access.strip():
                token = stored_access.strip()

            stored_refresh = stored.get("refresh_token")
            if isinstance(stored_refresh, str) and stored_refresh.strip():
                refresh_token = stored_refresh.strip()

            if client_id is None:
                stored_client_id = stored.get("client_id")
                if isinstance(stored_client_id, str) and stored_client_id.strip():
                    client_id = stored_client_id.strip()

            if not os.getenv("SPOTIFY_REDIRECT_URI", "").strip():
                stored_redirect = stored.get("redirect_uri")
                if isinstance(stored_redirect, str) and stored_redirect.strip():
                    redirect_uri = stored_redirect.strip()

            stored_scopes = stored.get("scopes")
            if isinstance(stored_scopes, list):
                scopes = tuple(str(scope).strip() for scope in stored_scopes if str(scope).strip())

        if not token:
            return None

        return cls(
            token,
            client_id=client_id,
            refresh_token=refresh_token,
            redirect_uri=redirect_uri,
            scopes=scopes,
            token_store_path=token_store_path,
        )

    @staticmethod
    def _load_tokens(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return body if isinstance(body, dict) else None

    def _save_tokens(self) -> None:
        data = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scopes": list(self.scopes),
            "updated_at": int(time.time()),
        }
        try:
            self.token_store_path.parent.mkdir(parents=True, exist_ok=True)
            self.token_store_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            if os.name != "nt":
                os.chmod(self.token_store_path, 0o600)
        except OSError:
            # If persistence fails we still keep the in-memory token.
            pass

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    def start_pkce_authorization(self) -> str | None:
        if not self.client_id:
            self._last_error = "Missing SPOTIFY_CLIENT_ID for PKCE authorization."
            return None

        self._pkce_state = secrets.token_urlsafe(24)
        self._pkce_code_verifier = _base64_url_no_padding(secrets.token_bytes(48))

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scopes),
            "code_challenge_method": "S256",
            "code_challenge": _pkce_code_challenge(self._pkce_code_verifier),
            "state": self._pkce_state,
        }
        self._last_error = ""
        return f"{SPOTIFY_ACCOUNTS_URL}/authorize?{urlencode(params)}"

    def complete_pkce_authorization(self, callback_url: str) -> bool:
        parsed = urlparse(callback_url.strip())
        query = parse_qs(parsed.query)

        error_text = (query.get("error") or [""])[0].strip()
        if error_text:
            self._last_error = f"Spotify authorization error: {error_text}."
            return False

        code = (query.get("code") or [""])[0].strip()
        state = (query.get("state") or [""])[0].strip()
        if not code:
            self._last_error = "Spotify callback did not include an authorization code."
            return False
        if not state or state != self._pkce_state:
            self._last_error = "Spotify callback state mismatch."
            return False
        if not self._pkce_code_verifier or not self.client_id:
            self._last_error = "Spotify PKCE verifier was not initialized."
            return False

        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "code_verifier": self._pkce_code_verifier,
        }
        ok = self._submit_token_request(payload)
        if ok:
            self._pkce_state = None
            self._pkce_code_verifier = None
        return ok

    def _submit_token_request(self, payload: dict[str, str]) -> bool:
        encoded = urlencode(payload).encode("utf-8")
        for attempt in range(3):
            request = Request(
                SPOTIFY_AUTH_TOKEN_URL,
                data=encoded,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
            try:
                with urlopen(request, timeout=5.0) as response:  # noqa: S310
                    body = json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                body_raw = self._read_http_error_body(exc)
                retry_after_s = _parse_retry_after_seconds(exc.headers.get("Retry-After"))
                if exc.code == 429 and attempt < 2:
                    time.sleep(self._backoff_delay_seconds(attempt, retry_after_s))
                    continue
                self._last_error = self._build_api_error_message(exc.code, body_raw, retry_after_s)
                return False
            except (URLError, TimeoutError, OSError, json.JSONDecodeError):
                if attempt < 2:
                    time.sleep(self._backoff_delay_seconds(attempt, None))
                    continue
                self._last_error = "Spotify token request failed due to a network error."
                return False

            next_token = str(body.get("access_token", "")).strip()
            if not next_token:
                self._last_error = "Spotify token response did not include an access token."
                return False

            self.access_token = next_token
            refresh = body.get("refresh_token")
            if isinstance(refresh, str) and refresh.strip():
                self.refresh_token = refresh.strip()
            self._save_tokens()
            self._last_error = ""
            return True
        return False

    def _refresh_access_token(self) -> bool:
        if not self.refresh_token or not self.client_id:
            self._last_error = "Spotify refresh token or client ID missing."
            return False
        return self._submit_token_request(
            {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
            }
        )

    @staticmethod
    def _read_http_error_body(exc: HTTPError) -> bytes | None:
        try:
            return exc.read()
        except OSError:
            return None

    @staticmethod
    def _decode_error_message(body: bytes | None) -> str:
        if not body:
            return ""
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return ""

        if isinstance(payload, dict):
            top_error = payload.get("error")
            if isinstance(top_error, dict):
                message = top_error.get("message")
                if isinstance(message, str):
                    return message.strip()
            if isinstance(top_error, str):
                return top_error.strip()

            message = payload.get("error_description")
            if isinstance(message, str):
                return message.strip()
        return ""

    @classmethod
    def _build_api_error_message(
        cls,
        status_code: int,
        body: bytes | None,
        retry_after_s: float | None = None,
    ) -> str:
        api_message = cls._decode_error_message(body)
        if status_code == 401:
            base = "Spotify authorization expired or invalid."
        elif status_code == 403:
            base = "Spotify rejected the request. Check Premium account and required scopes."
        elif status_code == 429:
            wait_text = f" Retry after {retry_after_s:.1f}s." if retry_after_s is not None else ""
            base = f"Spotify rate limit reached.{wait_text}"
        else:
            base = f"Spotify API error ({status_code})."

        if api_message:
            return f"{base} {api_message}"
        return base

    @staticmethod
    def _backoff_delay_seconds(attempt: int, retry_after_s: float | None) -> float:
        if retry_after_s is not None:
            return min(12.0, retry_after_s)
        return min(6.0, 0.5 * (2**attempt))

    def _request_json(self, url: str) -> tuple[int, Any | None]:
        status, body = self._request("GET", url)
        if status == 204:
            self._last_error = ""
            return status, None
        if body is None:
            return status, None
        try:
            return status, json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self._last_error = "Spotify returned an invalid JSON payload."
            return 0, None

    def _request(self, method: str, url: str, *, body: bytes | None = None) -> tuple[int, bytes | None]:
        self._last_error = ""
        auth_retry_attempted = False

        for attempt in range(3):
            request = Request(url, headers=self._headers(), data=body, method=method)
            try:
                with urlopen(request, timeout=4.0) as response:  # noqa: S310
                    status = getattr(response, "status", 200)
                    if status == 204:
                        return 204, None
                    return status, response.read()
            except HTTPError as exc:
                response_body = self._read_http_error_body(exc)
                retry_after_s = _parse_retry_after_seconds(exc.headers.get("Retry-After"))

                if exc.code == 401 and not auth_retry_attempted and self._refresh_access_token():
                    auth_retry_attempted = True
                    continue

                if exc.code == 429 and attempt < 2:
                    time.sleep(self._backoff_delay_seconds(attempt, retry_after_s))
                    continue

                self._last_error = self._build_api_error_message(exc.code, response_body, retry_after_s)
                return exc.code, response_body
            except (URLError, TimeoutError, OSError):
                if attempt < 2:
                    time.sleep(self._backoff_delay_seconds(attempt, None))
                    continue
                self._last_error = "Spotify request failed due to a network error."
                return 0, None
        return 0, None

    def get_now_playing(self) -> SpotifyNowPlaying | None:
        status, data = self._request_json(f"{SPOTIFY_API_BASE_URL}/me/player/currently-playing")
        if status == 204:
            return None
        if status != 200 or not isinstance(data, dict):
            return None

        item = data.get("item") or {}
        if not isinstance(item, dict):
            return None

        artists_raw = item.get("artists") or []
        artists: list[str] = []
        if isinstance(artists_raw, list):
            for artist in artists_raw:
                if isinstance(artist, dict):
                    name = str(artist.get("name", "")).strip()
                    if name:
                        artists.append(name)

        album_name = ""
        artwork_url = ""
        album_data = item.get("album")
        if isinstance(album_data, dict):
            album_name = str(album_data.get("name", "")).strip()
            images = album_data.get("images")
            if isinstance(images, list):
                for image in images:
                    if isinstance(image, dict):
                        url = str(image.get("url", "")).strip()
                        if url:
                            artwork_url = url
                            break

        if not artists:
            show_data = item.get("show")
            if isinstance(show_data, dict):
                publisher = str(show_data.get("publisher", "")).strip()
                if publisher:
                    artists.append(publisher)
                if not album_name:
                    album_name = str(show_data.get("name", "")).strip()
                images = show_data.get("images")
                if isinstance(images, list):
                    for image in images:
                        if isinstance(image, dict):
                            url = str(image.get("url", "")).strip()
                            if url:
                                artwork_url = url
                                break

        device_data = data.get("device") or {}
        device_name = str(device_data.get("name", "")).strip() if isinstance(device_data, dict) else ""

        self._last_error = ""
        return SpotifyNowPlaying(
            is_playing=bool(data.get("is_playing")),
            track_name=str(item.get("name", "")).strip(),
            artists=", ".join(artists),
            album=album_name,
            progress_ms=_safe_int(data.get("progress_ms"), 0),
            duration_ms=_safe_int(item.get("duration_ms"), 0),
            device_name=device_name,
            artwork_url=artwork_url,
        )

    def pause_playback(self, device_id: str | None = None) -> bool:
        # OpenAPI path: /me/player/pause
        url = f"{SPOTIFY_API_BASE_URL}/me/player/pause"
        if device_id:
            url += "?" + urlencode({"device_id": device_id})
        status, _ = self._request("PUT", url)
        return status == 204

    def start_resume_playback(self, device_id: str | None = None) -> bool:
        # OpenAPI path: /me/player/play
        url = f"{SPOTIFY_API_BASE_URL}/me/player/play"
        if device_id:
            url += "?" + urlencode({"device_id": device_id})
        status, _ = self._request("PUT", url)
        return status == 204

    def skip_next(self, device_id: str | None = None) -> bool:
        # OpenAPI path: /me/player/next
        url = f"{SPOTIFY_API_BASE_URL}/me/player/next"
        if device_id:
            url += "?" + urlencode({"device_id": device_id})
        status, _ = self._request("POST", url)
        return status == 204

    def skip_previous(self, device_id: str | None = None) -> bool:
        # OpenAPI path: /me/player/previous
        url = f"{SPOTIFY_API_BASE_URL}/me/player/previous"
        if device_id:
            url += "?" + urlencode({"device_id": device_id})
        status, _ = self._request("POST", url)
        return status == 204
