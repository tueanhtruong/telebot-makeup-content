"""Authentication utilities for TikTok OAuth."""

import hashlib
import json
import random
import secrets
import string
import threading
import time
import urllib.parse
import webbrowser
from base64 import urlsafe_b64encode
from typing import Optional

import requests


# Global callback holder
auth_code_holder = {}
server_done = threading.Event()


def generate_code_verifier(length: int = 64) -> str:
    """Generate PKCE code verifier."""
    alphabet = string.ascii_letters + string.digits + "-._~"
    return "".join(random.choice(alphabet) for _ in range(length))


def generate_code_challenge(verifier: str) -> str:
    """Generate PKCE code challenge from verifier."""
    digest = hashlib.sha256(verifier.encode()).digest()
    return urlsafe_b64encode(digest).rstrip(b"=").decode()


def build_auth_url(
    code_challenge: str,
    state: str,
    client_key: str,
    redirect_uri: str,
    scopes: str,
) -> str:
    """Build TikTok authorization URL."""
    params = {
        "client_key":            client_key,
        "scope":                 scopes,
        "response_type":         "code",
        "redirect_uri":          redirect_uri,
        "state":                 state,
        "code_challenge":        code_challenge,
        "code_challenge_method": "S256",
    }
    return "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode(params)


def get_access_token(
    code: str,
    code_verifier: str,
    client_key: str,
    client_secret: str,
    redirect_uri: str,
) -> Optional[dict]:
    """Exchange authorization code for access token."""
    try:
        resp = requests.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_key":    client_key,
                "client_secret": client_secret,
                "code":          code,
                "grant_type":    "authorization_code",
                "redirect_uri":  redirect_uri,
                "code_verifier": code_verifier,
            },
        )
        resp.raise_for_status()
        token_data = resp.json()
        
        if token_data.get("data", {}).get("access_token"):
            token_data = token_data["data"]
            token_data["saved_at"] = time.time()
            return token_data
        return token_data
    except Exception as e:
        print(f"Error getting access token: {e}")
        return None


# Callback handler for OAuth
import http.server


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback."""
    
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()

        if "code" in params:
            auth_code_holder["code"]  = params["code"][0]
            auth_code_holder["state"] = params.get("state", [""])[0]
            self.wfile.write(b"<h2>Auth successful! You can close this tab.</h2>")
        else:
            error = params.get("error", ["unknown"])[0]
            self.wfile.write(f"<h2>Auth failed: {error}</h2>".encode())

        server_done.set()

    def log_message(self, *args):
        """Silence request logs."""
        pass


def start_local_server(port: int = 8080) -> http.server.HTTPServer:
    """Start local HTTP server for OAuth callback."""
    server = http.server.HTTPServer(("localhost", port), CallbackHandler)
    thread = threading.Thread(target=server.handle_request)
    thread.daemon = True
    thread.start()
    return server


def open_browser_and_wait(auth_url: str, timeout: int = 120) -> bool:
    """Open browser for authorization and wait for callback."""
    print("Opening TikTok login in your browser...")
    webbrowser.get('firefox').open(auth_url)
    
    # Wait for redirect callback
    server_done.wait(timeout=timeout)
    
    return "code" in auth_code_holder


def get_auth_code() -> Optional[str]:
    """Get the authorization code from callback."""
    return auth_code_holder.get("code")


def reset_auth_state() -> None:
    """Reset auth state for next authentication."""
    global auth_code_holder, server_done
    auth_code_holder = {}
    server_done = threading.Event()
