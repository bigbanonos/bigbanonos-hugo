#!/usr/bin/env python3
"""
rebuild_manifest.py

Reads:
  - content/posts/*.md           (all artist pages, multi-track + 1-off explosions)
  - content/tunes/<year>/<artist>/index.md  (tune pages, 2025 + 2026)
  - static/playlist_manifest.json (existing, for genre_primary/secondary preservation)

Emits:
  - static/playlist_manifest.json (overwritten, full rebuild)
  - static/playlist_manifest.json.backup-<timestamp> (safety)

Schema matches what layouts/index.html expects:
  {
    "name": "The Hold Steady",
    "kind": "artist" | "1off_bucket" | "cover" | "tune",
    "letter": "H",
    "era": "2000s-2010s" | "2020s" | "1900s" | "all",
    "genre_primary": "indie",
    "genre_secondary": "rock",
    "tag": "dancehall" | null,
    "tracks": 26,
    "sort_name": "hold-steady",
    "year": "2026"  (only for tunes)
  }

Usage:
    python rebuild_manifest.py            # dry run
    python rebuild_manifest.py --write
"""
import json
import re
import sys
import shutil
from datetime import datetime
from pathlib import Path
from collections import defaultdict

LEADING_THE = re.compile(r"^the[-\s_]+", re.IGNORECASE)
NON_ALNUM = re.compile(r"[^a-zA-Z0-9]+")

# Map full Spotify micro-genres to the 8 BigBanonos buckets.
# This is best-effort; manual overrides in old manifest will win.
GENRE_BUCKETS = {
    # POP
    "pop": "pop", "art pop": "pop", "indie pop": "pop", "synth-pop": "pop",
    "dance pop": "pop", "electropop": "pop", "k-pop": "pop", "j-pop": "pop",
    "bedroom pop": "pop", "hyperpop": "pop", "girl group": "pop",
    "alternative dance": "pop", "swedish pop": "pop", "spanish pop": "pop",
    # INDIE
    "indie": "indie", "indie rock": "indie", "indie folk": "indie",
    "indietronica": "indie", "alt-indie": "indie", "freak folk": "indie",
    "shoegaze": "indie", "lo-fi": "indie",
    # ROCK
    "rock": "rock", "classic rock": "rock", "punk": "rock", "punk rock": "rock",
    "post-punk": "rock", "hard rock": "rock", "metal": "rock",
    "alternative rock": "rock", "garage rock": "rock", "psychedelic rock": "rock",
    "folk rock": "rock", "noise rock": "rock", "post-rock": "rock",
    "math rock": "rock", "indie surf": "rock",
    # RAP
    "rap": "rap", "hip hop": "rap", "hip-hop": "rap", "trap": "rap",
    "drill": "rap", "boom bap": "rap", "conscious hip hop": "rap",
    "west coast hip hop": "rap", "atlanta hip hop": "rap", "detroit hip hop": "rap",
    "memphis hip hop": "rap", "uk drill": "rap", "afrobeats": "rap",
    # R&B
    "r&b": "rnb", "rnb": "rnb", "alternative r&b": "rnb", "neo soul": "rnb",
    "soul": "rnb", "trap soul": "rnb", "pbr&b": "rnb", "dark r&b": "rnb",
    # DANCEHALL
    "dancehall": "dancehall", "reggae": "dancehall", "soca": "dancehall",
    "shatta": "dancehall", "riddim": "dancehall", "ragga": "dancehall",
    "reggae fusion": "dancehall",
    # ELECTRONIC
    "electronic": "electronic", "techno": "electronic", "house": "electronic",
    "ambient": "electronic", "edm": "electronic", "idm": "electronic",
    "deep house": "electronic", "minimal techno": "electronic", "trance": "electronic",
    "drum and bass": "electronic", "dubstep": "electronic", "bass": "electronic",
    "footwork": "electronic", "electroclash": "electronic", "witch house": "electronic",
    # FOLK
    "folk": "folk", "country": "folk", "americana": "folk", "old-time": "folk",
    "bluegrass": "folk", "outlaw country": "folk", "folk pop": "folk",
    "texas country": "folk", "red dirt": "folk", "honky tonk": "folk",
}


def canonicalize(name):
    if not name:
        return ""
    s = LEADING_THE.sub("", name.strip())
    folds = {
        "ü": "u", "ö": "o", "ä": "a", "é": "e", "è": "e", "ê": "e",
        "á": "a", "à": "a", "ó": "o", "ò": "o", "ñ": "n", "ç": "c",
        "í": "i", "ú": "u",
    }
    for k, v in folds.items():
        s = s.replace(k, v)
    s = NON_ALNUM.sub("-", s).strip("-").lower()
    return s


def parse_yaml_front_matter(text):
    """Tiny YAML parser for our specific front-matter shape.
    Handles: scalar strings, scalar dates, lists, nested simple values.
    Not bulletproof. We control the writers, so it's fine."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 4)
    if end < 0:
        return {}
    fm_text = text[4:end].strip()

    out = {}
    current_key = None
    current_list = None
    for line in fm_text.split("\n"):
        if not line.strip():
            continue
        # List item
        if line.startswith("  - ") or line.startswith("- "):
            val = line.lstrip(" -").strip()
            val = strip_quotes(val)
            if current_list is not None:
                current_list.append(val)
            continue
        # key: value
        if ":" in line:
            k, _, v = line.partition(":")
            k = k.strip()
            v = v.strip()
            if v == "":
                # List or nested follows
                current_key = k
                current_list = []
                out[k] = current_list
            else:
                out[k] = strip_quotes(v)
                current_key = None
                current_list = None
    # If a list ended up empty, treat as scalar
    for k, v in list(out.items()):
        if isinstance(v, list) and len(v) == 0:
            del out[k]
    return out


def strip_quotes(s):
    s = s.strip()
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        return s[1:-1].replace("''", "'")
    return s


def get_first(value):
    """Front matter values can be scalar or list — get the first."""
    if isinstance(value, list):
        return value[0] if value else None
    return value


def map_genres_to_buckets(genre_value):
    """Take a list of micro-genres or a single genre string, return (primary, secondary)."""
    if not genre_value:
        return None, None
    if isinstance(genre_value, str):
        candidates = [genre_value]
    else:
        candidates = list(genre_value)

    buckets = []
    for raw in candidates:
        if not raw:
            continue
        low = raw.lower().strip()
        # Try direct match first
        if low in GENRE_BUCKETS:
            b = GENRE_BUCKETS[low]
            if b not in buckets:
                buckets.append(b)
            continue
        # Try fuzzy match — substring of known keys
        for key, bucket in GENRE_BUCKETS.items():
            if key in low or low in key:
                if bucket not in buckets:
                    buckets.append(bucket)
                break
    primary = buckets[0] if buckets else None
    secondary = buckets[1] if len(buckets) > 1 else None
    return primary, secondary


def count_embeds(body):
    """Count Spotify track embeds in the body."""
    return body.count("open.spotify.com/embed/track/")


def load_existing_manifest():
    """Read static/playlist_manifest.json and return dict keyed by name (lowercase).
    Excludes 1off_bucket and cover records — those should not be in the new manifest."""
    p = Path("static/playlist_manifest.json")
    if not p.exists():
        return {}
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return {}
    out = {}
    for r in data:
        if not isinstance(r, dict):
            continue
        # Skip vestigial bucket / cover records — they're replaced by individual tunes
        if r.get("kind") in ("1off_bucket", "cover"):
            continue
        key = (r.get("name", "") or "").lower().strip()
        if key:
            out[key] = r
    return out


def process_artist_post(path, existing_lookup):
    """Read an artist post, return manifest record or None."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None
    fm = parse_yaml_front_matter(text)
    if not fm:
        return None

    name = fm.get("title", "") or path.stem
    name = strip_quotes(name)
    slug = fm.get("slug") or path.stem
    slug = strip_quotes(slug)
    letter = (fm.get("letter") or first_letter_of(slug)).upper()

    era_val = fm.get("era")
    era = get_first(era_val) or "all"

    body = text[text.find("\n---", 4) + 4:] if "\n---" in text[4:] else ""
    track_count = count_embeds(body)
    if track_count == 0:
        track_count = 1  # fall back so empty pages still render

    # Genre: existing manifest wins, then map from YAML
    existing = existing_lookup.get(name.lower())
    primary = secondary = None
    tag = None
    if existing:
        primary = existing.get("genre_primary")
        secondary = existing.get("genre_secondary")
        tag = existing.get("tag")
    if not primary:
        primary, secondary = map_genres_to_buckets(fm.get("genre"))
    if primary == "dancehall":
        tag = "dancehall"

    return {
        "name": name,
        "kind": "artist",
        "letter": letter,
        "era": era,
        "genre_primary": primary,
        "genre_secondary": secondary,
        "tag": tag,
        "tracks": track_count,
        "sort_name": slug,
        "active": parse_bool(fm.get("active")),
        "bucket": strip_quotes(fm.get("bucket", "") or ""),
        "last_release": strip_quotes(fm.get("last_release", "") or ""),
        "track_count_real": parse_int(fm.get("track_count")),
    }


def parse_bool(val):
    """Convert YAML-parsed value into a real bool."""
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower().strip("'\"")
    return s in ("true", "yes", "1")


def parse_int(val):
    """Convert YAML-parsed value into an int."""
    if val is None:
        return 0
    if isinstance(val, int):
        return val
    s = str(val).strip().strip("'\"")
    try:
        return int(s)
    except (TypeError, ValueError):
        return 0


def first_letter_of(slug):
    if not slug:
        return "#"
    c = slug[0].upper()
    return c if c.isalpha() else "#"


def process_tune_page(path, existing_lookup):
    """Read a tune page (content/tunes/<year>/<slug>/index.md)."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None
    fm = parse_yaml_front_matter(text)
    if not fm:
        return None

    title = strip_quotes(fm.get("title", "") or "")
    name = title.split("—")[0].strip() if "—" in title else title
    if not name:
        name = path.parent.name

    artist_slug = strip_quotes(fm.get("artist_slug") or fm.get("slug") or path.parent.name)
    letter = (fm.get("letter") or first_letter_of(artist_slug)).upper()
    year = strip_quotes(fm.get("year") or path.parent.parent.name)
    track_count = int(fm.get("track_count") or 1) if str(fm.get("track_count", "")).isdigit() else 1

    primary, secondary = map_genres_to_buckets(fm.get("genre"))
    tag = "dancehall" if primary == "dancehall" else None

    return {
        "name": f"{name} ({year})",
        "kind": "tune",
        "letter": letter,
        "era": "2020s",
        "year": year,
        "genre_primary": primary,
        "genre_secondary": secondary,
        "tag": tag,
        "tracks": track_count,
        "sort_name": f"{year}-{artist_slug}",
        "tune_url": f"/tunes/{year}/{artist_slug}/",
    }


def main():
    write = "--write" in sys.argv

    print(f"\n{'='*60}")
    print(f"REBUILD MANIFEST — {'WRITE' if write else 'DRY RUN'}")
    print(f"{'='*60}\n")

    # Backup existing
    existing_path = Path("static/playlist_manifest.json")
    if existing_path.exists() and write:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = Path(f"static/playlist_manifest.json.backup-{ts}")
        shutil.copy2(existing_path, backup)
        print(f"Backed up old manifest -> {backup.name}\n")

    existing_lookup = load_existing_manifest()
    print(f"Loaded existing manifest: {len(existing_lookup)} records (for genre preservation)")

    records = []

    # Artist posts
    posts_dir = Path("content/posts")
    if posts_dir.exists():
        post_files = sorted(posts_dir.glob("*.md"))
        print(f"\nProcessing {len(post_files)} artist posts...")
        for p in post_files:
            rec = process_artist_post(p, existing_lookup)
            if rec:
                records.append(rec)

    # Tunes
    tunes_dir = Path("content/tunes")
    tune_files = []
    if tunes_dir.exists():
        for year_dir in sorted(tunes_dir.iterdir()):
            if not year_dir.is_dir():
                continue
            for artist_dir in sorted(year_dir.iterdir()):
                if not artist_dir.is_dir():
                    continue
                idx = artist_dir / "index.md"
                if idx.exists():
                    tune_files.append(idx)
        print(f"\nProcessing {len(tune_files)} tune pages...")
        for p in tune_files:
            rec = process_tune_page(p, existing_lookup)
            if rec:
                records.append(rec)

    # Stats
    by_kind = defaultdict(int)
    by_letter = defaultdict(int)
    by_genre = defaultdict(int)
    for r in records:
        by_kind[r.get("kind")] += 1
        by_letter[r.get("letter") or "?"] += 1
        gp = r.get("genre_primary")
        if gp:
            by_genre[gp] += 1

    print(f"\n{'='*60}")
    print(f"MANIFEST STATS")
    print(f"{'='*60}")
    print(f"Total records: {len(records)}")
    print(f"\nBy kind:")
    for k, n in sorted(by_kind.items()):
        print(f"  {k:20s} {n}")
    print(f"\nBy letter:")
    for l in sorted(by_letter.keys()):
        print(f"  {l}: {by_letter[l]}")
    print(f"\nBy genre_primary:")
    for g, n in sorted(by_genre.items(), key=lambda x: -x[1]):
        print(f"  {g:15s} {n}")

    no_genre = sum(1 for r in records if not r.get("genre_primary"))
    print(f"\nRecords with no genre_primary: {no_genre} (will not match genre filter)")

    if write:
        existing_path.parent.mkdir(parents=True, exist_ok=True)
        with open(existing_path, "w", encoding="utf-8") as fh:
            json.dump(records, fh, indent=2, ensure_ascii=False)
        print(f"\nWrote: {existing_path}")
    else:
        print("\nDRY RUN. Re-run with --write.")


if __name__ == "__main__":
    main()
