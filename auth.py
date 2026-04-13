#!/usr/bin/env python3
"""
bigbanonos: get a Spotify access token via the official OAuth flow.

Setup once:
  1. https://developer.spotify.com/dashboard -> Create app
     - Redirect URI: http://127.0.0.1:8888/callback
     - Tick "Web API"
  2. Copy Client ID + Client Secret from the app's Settings
  3. Edit the two constants below, OR set env vars:
       export SPOTIFY_CLIENT_ID="..."
       export SPOTIFY_CLIENT_SECRET="..."
  4. python3 auth.py

It will:
  - open your browser to Spotify's consent page
  - catch the redirect locally on port 8888
  - exchange the code for a token
  - print the token to your terminal

Then:
  export SPOTIFY_TOKEN="<the token it printed>"
  python3 spotify_pull.py > all_playlists.json
"""
import os, sys, base64, json, secrets, webbrowser
import urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

CLIENT_ID     = os.environ.get("SPOTIFY_CLIENT_ID",     "PASTE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "PASTE_CLIENT_SECRET")
REDIRECT_URI  = "http://127.0.0.1:8888/callback"
SCOPES        = "playlist-read-private playlist-read-collaborative"
STATE         = secrets.token_urlsafe(16)

auth_code = {"value": None}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.urlparse(self.path).query
        params = dict(urllib.parse.parse_qsl(q))
        if params.get("state") != STATE:
            self.send_response(400); self.end_headers()
            self.wfile.write(b"state mismatch"); return
        auth_code["value"] = params.get("code")
        self.send_response(200); self.send_header("Content-Type","text/html"); self.end_headers()
        self.wfile.write(b"<h1>OK. Token captured. You can close this tab.</h1>")
    def log_message(self, *a, **k): pass  # silence

def main():
    if CLIENT_ID.startswith("PASTE") or CLIENT_SECRET.startswith("PASTE"):
        sys.exit("Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET first.")

    # 1. send user to Spotify consent
    auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
        "response_type": "code",
        "client_id": CLIENT_ID,
        "scope": SCOPES,
        "redirect_uri": REDIRECT_URI,
        "state": STATE,
    })
    print("Opening browser for Spotify consent...", file=sys.stderr)
    webbrowser.open(auth_url)

    # 2. catch the redirect
    srv = HTTPServer(("127.0.0.1", 8888), Handler)
    while auth_code["value"] is None:
        srv.handle_request()

    # 3. exchange code -> token
    creds = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    body = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": auth_code["value"],
        "redirect_uri": REDIRECT_URI,
    }).encode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=body,
        headers={"Authorization": f"Basic {creds}",
                 "Content-Type":  "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req) as r:
        tok = json.loads(r.read())

    print("\n--- ACCESS TOKEN (valid ~1hr) ---")
    print(tok["access_token"])
    print("\nNext:")
    print(f'  export SPOTIFY_TOKEN="{tok["access_token"]}"')
    print("  python3 spotify_pull.py > all_playlists.json")

if __name__ == "__main__":
    main()
