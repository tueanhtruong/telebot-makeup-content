"""Token management utilities for TikTok OAuth."""

import json
import os
import time
from typing import Optional

import requests


def load_token_from_file(token_file: str) -> Optional[dict]:
    """Load token from auth-token.json if it exists."""
    if os.path.exists(token_file):
        try:
            with open(token_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading token file: {e}")
            return None
    return None


def save_token_to_file(token_data: dict, token_file: str) -> None:
    """Save token to auth-token.json."""
    try:
        with open(token_file, "w", encoding="utf-8") as f:
            json.dump(token_data, f, indent=2, ensure_ascii=False)
        print(f"✅ Token saved to {token_file}")
    except Exception as e:
        print(f"Error saving token file: {e}")


def is_token_expired(token_data: Optional[dict]) -> bool:
    """Check if token is expired based on saved timestamp."""
    if not token_data:
        return True
    
    if "saved_at" not in token_data:
        return True
    
    expires_in = token_data.get("expires_in", 0)
    saved_at = token_data.get("saved_at", 0)
    current_time = time.time()
    
    # Add a 5-minute buffer before actual expiration
    return current_time - saved_at > expires_in - 300


def refresh_access_token(
    refresh_token: str,
    client_key: str,
    client_secret: str,
) -> Optional[dict]:
    """Refresh access token using refresh_token."""
    print("🔄 Refreshing access token...")
    try:
        resp = requests.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_key":     client_key,
                "client_secret":  client_secret,
                "grant_type":     "refresh_token",
                "refresh_token":  refresh_token,
            },
        )
        resp.raise_for_status()
        token_data = resp.json()
        print("Refresh token response:", json.dumps(token_data, indent=2))
        
        # Refresh token response returns access_token at top level, not under "data"
        if token_data.get("access_token"):
            token_data["saved_at"] = time.time()
            print("✅ Token refreshed successfully")
            return token_data
        else:
            print("❌ Failed to refresh token")
            return None
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print(f"❌ Refresh token failed with 401 Unauthorized")
            raise Exception("401 - Refresh token invalid or expired")
        print(f"❌ Refresh token failed: {e}")
        return None
    except Exception as e:
        print(f"❌ Refresh token failed: {e}")
        return None
