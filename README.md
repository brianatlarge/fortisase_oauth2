# FortiSASE OAuth2 Token Manager

A lightweight Python module for authenticating with the FortiSASE REST API. Handles initial authentication, transparent token refresh, and Bearer token injection — no manual token management required.

## Requirements

- Python 3.7+
- `requests`

```bash
pip install requests
```

## Quick Start

```python
import requests
from fortisase_auth import FortiSASEAuth

auth = FortiSASEAuth(
    api_id="your_api_id",
    password="your_password",
)

session = requests.Session()
session.auth = auth

# Tokens are fetched and refreshed automatically
response = session.get("https://your-tenant.fortisase.com/api/v1/monitor/user/info")
print(response.json())
```

## Configuration

It is strongly recommended to load credentials from environment variables rather than hardcoding them.

```bash
export FORTISASE_API_ID=your_api_id
export FORTISASE_PASSWORD=your_password
```

```python
import os
from fortisase_auth import FortiSASEAuth

auth = FortiSASEAuth(
    api_id=os.environ["FORTISASE_API_ID"],
    password=os.environ["FORTISASE_PASSWORD"],
)
```

### Constructor Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `api_id` | `str` | required | FortiCloud IAM API user ID (`apiId` value) |
| `password` | `str` | required | FortiCloud IAM API user password |
| `client_id` | `str` | `"FortiSASE"` | OAuth2 client ID (rarely needs changing) |

### Class Attributes

| Attribute | Default | Description |
|---|---|---|
| `REFRESH_BUFFER_SECONDS` | `60` | How many seconds before expiry to proactively refresh the token |

## How It Works

The module implements `requests.auth.AuthBase`, which means it plugs directly into any `requests.Session` or one-off `requests.get/post` call via the `auth=` parameter.

```
First request
    └─► No token stored → POST /oauth/token (password grant)
        └─► Stores access_token + refresh_token + expiry time
            └─► Attaches Bearer token to request

Subsequent requests (token still valid)
    └─► Attaches existing Bearer token — no network call

Request made within 60s of expiry (or after)
    └─► POST /oauth/token (refresh_token grant)
        └─► Updates stored tokens
            └─► Attaches new Bearer token to request

Refresh token itself expired
    └─► Falls back to full password grant automatically
```

The token endpoint used is:
```
POST https://customerapiauth.fortinet.com/api/v1/oauth/token/
```

## API Reference

### `FortiSASEAuth`

#### `get_access_token() -> str`
Returns a valid access token string, refreshing or re-authenticating as needed. Useful if you need to pass the token manually to another library or HTTP client.

```python
token = auth.get_access_token()
headers = {"Authorization": f"Bearer {token}"}
```

#### `revoke() -> None`
Clears all stored tokens. The next request will trigger a full re-authentication.

```python
auth.revoke()
```

## Setting Up a FortiCloud API User

Before using this module, you need a FortiCloud IAM API user with access to FortiSASE. The general steps are:

1. Log into the [FortiCloud IAM portal](https://www.forticloud.com) as an Admin user
2. Create a permission profile of type **Local** for FortiSASE access
3. Create a new API user, assign the permission profile, and download the credentials
4. Use the downloaded `apiId` and `password` values with this module

Refer to the [FortiSASE API documentation](https://docs.fortinet.com/fortisase) for full setup details.

## Notes

- FortiSASE uses a non-standard OAuth2 password grant with an empty `client_secret`. Standard OAuth2 libraries (e.g. `oauthlib`, `authlib`) require workarounds for this; a custom implementation avoids that complexity.
- Access tokens expire after **3600 seconds** (1 hour) by default.
- The `scope` is `read write` for full API access.
