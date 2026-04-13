#!/usr/bin/env python3
"""
bigbanonos: pull EVERY playlist from your Spotify account in one shot.

Setup (one time, ~3 min):
  1. Go to https://developer.spotify.com/console/get-current-user-playlists/
  2. Click "Get Token" -> check scope: playlist-read-private, playlist-read-collaborative
  3. Copy the token, paste it below as TOKEN, OR set env var: export SPOTIFY_TOKEN="..."
  4. python3 spotify_pull.py > all_playlists.json

Output: a flat JSON array of {name, owner, tracks, id, uri, public}
This is the universal manifest -- feed it to build_posts.py later.
Tokens expire after ~1 hour; if you get 401, just regenerate.
"""
import json, os, sys, urllib.request, urllib.error, time

TOKEN = os.environ.get("SPOTIFY_TOKEN", "PASTE_TOKEN_HERE")

def get(url):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            wait = int(e.headers.get("Retry-After", "2"))
            print(f"rate-limited, waiting {wait}s", file=sys.stderr); time.sleep(wait)
            return get(url)
        if e.code == 401:
            sys.exit("401 — token expired or missing scopes. Get a fresh one.")
        raise

def pull_all():
    url = "https://api.spotify.com/v1/me/playlists?limit=50"
    out = []
    page = 1
    while url:
        print(f"page {page}...", file=sys.stderr)
        data = get(url)
        for p in data.get("items", []):
            if not p: continue
            out.append({
                "name":   p.get("name", ""),
                "owner":  (p.get("owner") or {}).get("id", ""),
                "tracks": (p.get("tracks") or {}).get("total", 0),
                "id":     p.get("id", ""),
                "uri":    p.get("uri", ""),
                "public": p.get("public", False),
            })
        url = data.get("next")
        page += 1
    return out

if __name__ == "__main__":
    if TOKEN == "PASTE_TOKEN_HERE":
        sys.exit("Set SPOTIFY_TOKEN env var or edit the TOKEN constant in this file.")
    playlists = pull_all()
    print(json.dumps(playlists, indent=2, ensure_ascii=False))
    print(f"\n# pulled {len(playlists)} playlists", file=sys.stderr)
