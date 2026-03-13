"""
FortiSASE API OAuth2 Token Manager
Handles initial auth, automatic refresh, and token expiry for the FortiSASE REST API.
"""

import time
import requests
from dataclasses import dataclass, field
from typing import Optional


TOKEN_URL = "https://customerapiauth.fortinet.com/api/v1/oauth/token/"


@dataclass
class TokenState:
    access_token: str
    refresh_token: str
    expires_at: float          # absolute epoch time
    token_type: str = "Bearer"
    scope: str = "read write"


class FortiSASEAuth(requests.auth.AuthBase):
    """
    Drop-in requests AuthBase that handles:
      - Initial password-grant authentication
      - Transparent access token refresh before expiry
      - Attaches Bearer token to every request automatically

    Usage:
        auth = FortiSASEAuth(api_id="your_api_id", password="your_password")
        session = requests.Session()
        session.auth = auth

        # Token is fetched/refreshed automatically on every call
        resp = session.get("https://your-tenant.fortisase.com/api/v1/...")
    """

    # Refresh the token this many seconds before it actually expires
    REFRESH_BUFFER_SECONDS = 60

    def __init__(self, api_id: str, password: str, client_id: str = "FortiSASE"):
        self.api_id = api_id
        self.password = password
        self.client_id = client_id
        self._token: Optional[TokenState] = None

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_access_token(self) -> str:
        """Return a valid access token, refreshing or re-authenticating as needed."""
        if self._token is None:
            self._authenticate()
        elif self._is_expired():
            self._refresh()
        return self._token.access_token

    def revoke(self) -> None:
        """Forget the stored tokens (forces re-auth on next call)."""
        self._token = None

    # ------------------------------------------------------------------
    # requests.auth.AuthBase interface
    # ------------------------------------------------------------------

    def __call__(self, r: requests.PreparedRequest) -> requests.PreparedRequest:
        r.headers["Authorization"] = f"Bearer {self.get_access_token()}"
        return r

    # ------------------------------------------------------------------
    # Internal token management
    # ------------------------------------------------------------------

    def _authenticate(self) -> None:
        """Perform initial password-grant flow."""
        payload = {
            "username": self.api_id,
            "password": self.password,
            "client_id": self.client_id,
            "client_secret": "",
            "grant_type": "password",
        }
        data = self._post_token(payload)
        self._token = TokenState(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=time.time() + data["expires_in"],
            token_type=data.get("token_type", "Bearer"),
            scope=data.get("scope", "read write"),
        )

    def _refresh(self) -> None:
        """Use the refresh token to obtain a new access token."""
        payload = {
            "client_id": self.client_id,
            "grant_type": "refresh_token",
            "refresh_token": self._token.refresh_token,
        }
        try:
            data = self._post_token(payload)
            self._token = TokenState(
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
                expires_at=time.time() + data["expires_in"],
                token_type=data.get("token_type", "Bearer"),
                scope=data.get("scope", "read write"),
            )
        except requests.HTTPError:
            # Refresh token itself may have expired — fall back to full re-auth
            self._authenticate()

    def _is_expired(self) -> bool:
        return time.time() >= (self._token.expires_at - self.REFRESH_BUFFER_SECONDS)

    @staticmethod
    def _post_token(payload: dict) -> dict:
        resp = requests.post(TOKEN_URL, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "success":
            raise ValueError(f"Token endpoint returned failure: {data}")
        return data


# ------------------------------------------------------------------
# Example usage
# ------------------------------------------------------------------

if __name__ == "__main__":
    import os

    auth = FortiSASEAuth(
        api_id=os.environ["FORTISASE_API_ID"],
        password=os.environ["FORTISASE_PASSWORD"],
    )

    session = requests.Session()
    session.auth = auth

    # All subsequent calls automatically carry a valid Bearer token
    # and will silently refresh it when needed.
    response = session.get("https://your-tenant.fortisase.com/api/v1/monitor/user/info")
    print(response.status_code, response.json())
