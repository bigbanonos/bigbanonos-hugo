#!/usr/bin/env python3
"""
classify_artists.py

Walks every artist post in content/posts/*.md, finds the matching CSV file
in the spotify_playlists folder (or counts embeds in the post itself if no
CSV is found), determines:

  - last_release: latest Release Date across the artist's tracks
  - track_count:  number of tracks (real, from CSV when possible)
  - active:       boolean, last_release >= 2020-01-01
  - bucket:       one of FAUCET / STILL_DRIPPING / NEW_LEAK / VAULT /
                  CRYSTALLIZED / ARTIFACT

Writes these as YAML fields on each post. Idempotent — re-running just
refreshes the values.

Thresholds:
  10+ tracks = "deep"
  5-9 tracks = "mid"
  1-4 tracks = "low"

Buckets:
                | 10+         | 5-9             | 1-4
  ----------------|-------------|------------------|------------------
  >= 2020 (active)| FAUCET      | STILL_DRIPPING   | NEW_LEAK
  <  2020 (legacy)| THE_VAULT   | CRYSTALLIZED     | ARTIFACT

Usage:
    python classify_artists.py --csv-dir "C:\\path\\to\\spotify_playlists"
    python classify_artists.py --csv-dir "C:\\path\\to\\spotify_playlists" --write
"""
import csv
import re
import sys
from pathlib import Path
from collections import defaultdict, Counter

LEADING_THE = re.compile(r"^the[-\s_]+", re.IGNORECASE)
NON_ALNUM = re.compile(r"[^a-zA-Z0-9]+")

ARTIST_FILE_RE = re.compile(
    r"^(.+?)_-_(?:\d+|XX|XXX|X+|\d+\+|Top|All|DH|IP|Rap)_Songs?\.csv$",
    re.IGNORECASE,
)

CUTOFF = "2020-01-01"

# Track-count buckets
THRESHOLD_DEEP = 10
THRESHOLD_MID = 5

# YAML markers
YAML_OPEN = "---\n"
YAML_CLOSE = "\n---"

# Field names we manage (will be removed and rewritten on each pass)
MANAGED_FIELDS = ("last_release", "track_count", "active", "bucket")


def canonicalize(name):
    if not name:
        return ""
    s = LEADING_THE.sub("", name.strip())
    folds = {
        "ü": "u", "ö": "o", "ä": "a", "é": "e", "è": "e", "ê": "e",
        "á": "a", "à": "a", "ó": "o", "ò": "o", "ñ": "n", "ç": "c",
        "í": "i", "ú": "u", "ø": "o", "å": "a", "ß": "ss",
    }
    for k, v in folds.items():
        s = s.replace(k, v)
    s = NON_ALNUM.sub("-", s).strip("-").lower()
    return s


def build_csv_index(csv_dir):
    """Map slug -> (path, [tracks])."""
    csv_dir = Path(csv_dir)
    index = {}
    for path in sorted(csv_dir.glob("*.csv")):
        m = ARTIST_FILE_RE.match(path.name)
        if not m:
            continue
        artist_name = m.group(1).replace("_", " ").strip()
        slug = canonicalize(artist_name)
        if not slug:
            continue
        try:
            with open(path, encoding="utf-8-sig", newline="") as fh:
                rows = list(csv.DictReader(fh))
        except Exception:
            continue
        if not rows:
            continue
        tracks = []
        for r in rows:
            rd = (r.get("Release Date", "") or "").strip()
            if not rd:
                continue
            # Normalize partial dates
            if len(rd) == 4:
                rd = rd + "-01-01"
            elif len(rd) == 7:
                rd = rd + "-01"
            tracks.append(rd)
        if tracks:
            index[slug] = (path.name, tracks)
    return index


def determine_bucket(last_release, track_count):
    if not last_release:
        return "ARTIFACT", False  # no data → safe default
    active = last_release >= CUTOFF
    if track_count >= THRESHOLD_DEEP:
        bucket = "FAUCET" if active else "THE_VAULT"
    elif track_count >= THRESHOLD_MID:
        bucket = "STILL_DRIPPING" if active else "CRYSTALLIZED"
    else:
        bucket = "NEW_LEAK" if active else "ARTIFACT"
    return bucket, active


def strip_managed_fields(yaml_block):
    """Remove any existing managed fields from a YAML block."""
    lines = yaml_block.split("\n")
    out = []
    for line in lines:
        # Skip lines that start with one of our managed field names
        stripped = line.lstrip()
        if any(stripped.startswith(f"{fld}:") for fld in MANAGED_FIELDS):
            continue
        out.append(line)
    return "\n".join(out)


def add_managed_fields(yaml_block, last_release, track_count, active, bucket):
    """Append our managed fields to a YAML block (before any trailing newline)."""
    yaml_block = yaml_block.rstrip()
    additions = [
        f"last_release: '{last_release}'" if last_release else "last_release: ''",
        f"track_count: {track_count}",
        f"active: {'true' if active else 'false'}",
        f"bucket: '{bucket}'",
    ]
    return yaml_block + "\n" + "\n".join(additions)


def process_post(path, csv_index, write):
    """Read post, find matching CSV, classify, rewrite YAML."""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None

    if not text.startswith(YAML_OPEN):
        return None

    yaml_end = text.find("\n---", 3)
    if yaml_end < 0:
        return None

    yaml_block = text[4:yaml_end]
    body = text[yaml_end:]

    slug = path.stem.lower()

    # Find matching CSV
    csv_match = csv_index.get(slug)
    if csv_match:
        _csv_name, tracks = csv_match
        track_count = len(tracks)
        last_release = max(tracks) if tracks else ""
        last_release = last_release[:10]
    else:
        # Fall back to counting embeds in the post body
        track_count = body.count("open.spotify.com/embed/track/")
        last_release = ""  # can't compute without CSV

    bucket, active = determine_bucket(last_release, track_count)

    # Rewrite YAML
    new_yaml = strip_managed_fields(yaml_block)
    new_yaml = add_managed_fields(new_yaml, last_release, track_count, active, bucket)
    new_text = YAML_OPEN + new_yaml + body

    if write:
        path.write_text(new_text, encoding="utf-8")

    return {
        "slug": slug,
        "track_count": track_count,
        "last_release": last_release,
        "active": active,
        "bucket": bucket,
        "had_csv": csv_match is not None,
    }


def main():
    args = sys.argv[1:]
    write = "--write" in args
    csv_dir = None
    for i, a in enumerate(args):
        if a == "--csv-dir" and i + 1 < len(args):
            csv_dir = args[i + 1]

    if not csv_dir:
        print('Usage: python classify_artists.py --csv-dir "C:\\path\\to\\spotify_playlists" [--write]')
        sys.exit(1)

    mode = "WRITE" if write else "DRY RUN"
    print(f"\n{'='*60}")
    print(f"CLASSIFY ARTISTS — {mode}")
    print(f"{'='*60}\n")

    print(f"Indexing CSVs in {csv_dir}...")
    csv_index = build_csv_index(csv_dir)
    print(f"  Found {len(csv_index)} per-artist CSVs\n")

    posts_dir = Path("content/posts")
    if not posts_dir.exists():
        print(f"ERROR: {posts_dir} not found")
        sys.exit(1)

    post_files = sorted(posts_dir.glob("*.md"))
    print(f"Processing {len(post_files)} artist posts...\n")

    bucket_counts = Counter()
    no_csv = []
    no_release = []
    results = []
    for p in post_files:
        r = process_post(p, csv_index, write)
        if not r:
            continue
        results.append(r)
        bucket_counts[r["bucket"]] += 1
        if not r["had_csv"]:
            no_csv.append(r["slug"])
        if not r["last_release"]:
            no_release.append(r["slug"])

    print(f"{'='*60}")
    print("BUCKET DISTRIBUTION")
    print(f"{'='*60}")
    print(f"  Active artists (released since {CUTOFF}):")
    for b in ("FAUCET", "STILL_DRIPPING", "NEW_LEAK"):
        n = bucket_counts.get(b, 0)
        print(f"    {b:18s} {n:>5}")
    print(f"  Inactive artists (last release before {CUTOFF}):")
    for b in ("THE_VAULT", "CRYSTALLIZED", "ARTIFACT"):
        n = bucket_counts.get(b, 0)
        print(f"    {b:18s} {n:>5}")
    print(f"\n  Total classified: {sum(bucket_counts.values())}")
    print(f"  Posts without matching CSV (fell back to embed-counting): {len(no_csv)}")

    # Show some interesting cases
    actives = sorted([r for r in results if r["active"]],
                     key=lambda x: (-x["track_count"], x["slug"]))
    legacies = sorted([r for r in results if not r["active"] and r["last_release"]],
                      key=lambda x: (-x["track_count"], x["slug"]))

    print(f"\n{'='*60}")
    print(f"TOP 15 FAUCETS (active + deepest catalog)")
    print(f"{'='*60}")
    for r in actives[:15]:
        print(f"  {r['slug']:40s} {r['track_count']:>3} tr  last: {r['last_release']}")

    print(f"\n{'='*60}")
    print(f"TOP 15 VAULT (inactive + deepest catalog)")
    print(f"{'='*60}")
    for r in legacies[:15]:
        print(f"  {r['slug']:40s} {r['track_count']:>3} tr  last: {r['last_release']}")

    if not write:
        print(f"\n{'='*60}")
        print(f"DRY RUN. To apply, re-run with --write")
        print(f"{'='*60}")
    else:
        print(f"\n{'='*60}")
        print(f"WROTE {sum(1 for r in results)} posts with managed YAML fields.")
        print(f"Next: python rebuild_manifest.py --write")
        print(f"{'='*60}")


if __name__ == "__main__":
    main()
