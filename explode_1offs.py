#!/usr/bin/env python3
"""
Explode a 1-off bucket CSV into individual artist post .md files.

Reads a CSV like Songs-Aa-2020s.csv and produces one Hugo post per track,
matching the 4batz template format. Detects collisions with existing
content/ files and skips them with a report.

Usage (from repo root):
    python3 explode_1offs.py path/to/Songs-Aa-2020s.csv

For all 2020s buckets at once:
    for f in path/to/Songs-*-2020s.csv; do python3 explode_1offs.py "$f"; done

Outputs to: content/
Skips: any artist whose .md already exists (prints "skipped" report)
"""
import csv
import re
import sys
from pathlib import Path
from datetime import datetime

CONTENT_DIR = Path("content")
TAG_GENRES_PATH = Path("tag_genres.py")  # to consult for known artists

# ---------------------------------------------------------------------------
# Per-artist slug overrides for cases where the CSV name doesn't match
# the URL slug we want. Map: lowercase-CSV-name -> desired slug.
# Add entries here as you spot more cases like Alpenglow (CSV says "Alpen Glow").
# ---------------------------------------------------------------------------
NAME_OVERRIDES = {
    "alpen glow": "alpenglow",
}

# ---------------------------------------------------------------------------
# Genre buckets used by the homepage filter
# ---------------------------------------------------------------------------
KNOWN_GENRES = {"pop", "indie", "rock", "rap", "rnb", "dancehall", "electronic", "folk"}

# Map Spotify micro-genres to your 8 buckets.
# Order matters: more specific first.
SPOTIFY_GENRE_MAP = [
    # Dancehall family
    ("dancehall", "dancehall"), ("reggae", "dancehall"), ("ragga", "dancehall"),
    ("riddim", "dancehall"), ("soca", "dancehall"), ("shatta", "dancehall"),
    ("dub", "dancehall"),
    # Rap family
    ("hip hop", "rap"), ("hip-hop", "rap"), ("rap", "rap"), ("trap", "rap"),
    ("drill", "rap"), ("grime", "rap"), ("boom bap", "rap"), ("g-funk", "rap"),
    ("hyphy", "rap"), ("gangster", "rap"),
    # R&B family
    ("r&b", "rnb"), ("rnb", "rnb"), ("soul", "rnb"), ("funk", "rnb"),
    ("trap soul", "rnb"), ("neo soul", "rnb"), ("gospel", "rnb"),
    ("worship", "rnb"), ("doo-wop", "rnb"),
    # Electronic family
    ("electronic", "electronic"), ("house", "electronic"), ("techno", "electronic"),
    ("edm", "electronic"), ("dnb", "electronic"), ("drum and bass", "electronic"),
    ("breakbeat", "electronic"), ("idm", "electronic"), ("downtempo", "electronic"),
    ("ambient", "electronic"), ("dubstep", "electronic"), ("electroclash", "electronic"),
    ("witch house", "electronic"), ("uk funky", "electronic"),
    ("lo-fi house", "electronic"), ("rally house", "electronic"),
    # Folk family
    ("folk", "folk"), ("country", "folk"), ("americana", "folk"), ("bluegrass", "folk"),
    ("alt country", "folk"), ("texas country", "folk"), ("red dirt", "folk"),
    ("honky tonk", "folk"), ("singer-songwriter", "folk"), ("blues", "folk"),
    ("jazz", "folk"), ("chanson", "folk"),
    # Indie family
    ("indie folk", "indie"), ("indie rock", "indie"), ("indie pop", "indie"),
    ("indie r&b", "indie"), ("indie electronic", "indie"), ("bedroom pop", "indie"),
    ("chillwave", "indie"), ("dream pop", "indie"), ("shoegaze", "indie"),
    ("indie", "indie"),
    # Rock family
    ("rock", "rock"), ("punk", "rock"), ("metal", "rock"), ("hardcore", "rock"),
    ("grunge", "rock"), ("post-punk", "rock"), ("new wave", "rock"),
    ("garage", "rock"), ("emo", "rock"),
    # Pop family (catches everything else pop-flavored)
    ("hyperpop", "pop"), ("synthpop", "pop"), ("k-pop", "pop"), ("j-pop", "pop"),
    ("city pop", "pop"), ("french indie pop", "pop"),
    ("afrobeats", "pop"), ("afropop", "pop"), ("afroswing", "pop"),
    ("afropiano", "pop"), ("afrobeat", "pop"),
    ("neoperreo", "pop"), ("reggaeton", "pop"), ("italian trap", "pop"),
    ("moroccan rap", "pop"),
    ("pop", "pop"),
]


def slugify(name):
    """Match the slug used by your URLs. Honors NAME_OVERRIDES for special cases."""
    raw = (name or "").strip()
    override = NAME_OVERRIDES.get(raw.lower())
    if override:
        return override
    s = re.sub(r"[^a-zA-Z0-9]+", "-", raw).strip("-").lower()
    return s


def parse_release_year(date_str):
    """Get the year from a Spotify release date (could be 'YYYY', 'YYYY-MM', or 'YYYY-MM-DD')."""
    if not date_str:
        return None
    m = re.match(r"(\d{4})", date_str)
    return m.group(1) if m else None


def primary_artist(artist_field):
    """Pick the first artist when CSV gives 'A1;A2;A3'."""
    if not artist_field:
        return ""
    return artist_field.split(";")[0].strip()


def featured_artists(artist_field):
    """Return the rest after the primary."""
    if not artist_field or ";" not in artist_field:
        return []
    return [a.strip() for a in artist_field.split(";")[1:] if a.strip()]


def map_spotify_genre(spotify_genres_field):
    """Map Spotify's comma-separated micro-genres to a primary bucket from the homepage 8.

    Returns (primary, secondary) where secondary may be None.
    """
    if not spotify_genres_field:
        return (None, None)

    raw = [g.strip().lower() for g in spotify_genres_field.split(",") if g.strip()]
    if not raw:
        return (None, None)

    # Score buckets by number of matching micro-genres
    bucket_hits = {}
    bucket_first_seen = {}
    for i, mg in enumerate(raw):
        for needle, bucket in SPOTIFY_GENRE_MAP:
            if needle in mg:
                bucket_hits[bucket] = bucket_hits.get(bucket, 0) + 1
                bucket_first_seen.setdefault(bucket, i)
                break  # only first match per micro-genre

    if not bucket_hits:
        return (None, None)

    # Sort by hits desc, then by first-seen asc (preserve CSV order tiebreaker)
    sorted_buckets = sorted(bucket_hits.items(),
                            key=lambda kv: (-kv[1], bucket_first_seen[kv[0]]))
    primary = sorted_buckets[0][0]
    secondary = sorted_buckets[1][0] if len(sorted_buckets) > 1 else None
    return (primary, secondary)


def load_known_artist_genres():
    """Pull GENRES dict from tag_genres.py without executing it.

    Returns {slug: (primary, secondary)} for artists we already tagged.
    """
    if not TAG_GENRES_PATH.exists():
        return {}
    src = TAG_GENRES_PATH.read_text(encoding="utf-8")
    # Match lines like:   "slug-name": ("primary", "secondary"),  OR ... None),
    pattern = re.compile(
        r'^\s*"([\w\-]+)":\s*\("([\w]+)",\s*(?:"([\w]+)"|None)\),',
        re.M,
    )
    out = {}
    for m in pattern.finditer(src):
        slug, primary, secondary = m.group(1), m.group(2), m.group(3)
        out[slug] = (primary, secondary)
    return out


def derive_genre(artist_slug, spotify_genres_field, known_genres):
    """Pick a primary+secondary genre for this artist's post.

    Priority:
        1. Known artist from tag_genres.py
        2. Spotify genres mapped to our 8 buckets
        3. None
    """
    if artist_slug in known_genres:
        return known_genres[artist_slug]
    return map_spotify_genre(spotify_genres_field)


def description_from_genres(spotify_genres_field, year):
    """Make a short prose description like 'Bedroom pop from 2024.'"""
    raw = [g.strip() for g in (spotify_genres_field or "").split(",") if g.strip()]
    if raw:
        # Use the most specific (first-listed) micro-genre, capitalize it nicely
        g = raw[0]
        # Capitalize only the first letter, keep things like "r&b" lowercase mid-word OK
        g_pretty = g[0].upper() + g[1:] if g else g
        if year:
            return f"{g_pretty} from {year}."
        return f"{g_pretty}."
    if year:
        return f"From {year}."
    return ""


def build_post_md(track, known_genres, era):
    """Return (slug, markdown_content) for a single track row."""
    track_name = track.get("Track Name", "").strip()
    album = track.get("Album Name", "").strip()
    artists_field = track.get("Artist Name(s)", "").strip()
    release_date = track.get("Release Date", "").strip()
    spotify_uri = track.get("Track URI", "").strip()
    spotify_genres = track.get("Genres", "").strip()

    primary = primary_artist(artists_field)
    if not primary:
        return None, None  # skip malformed rows

    slug = slugify(primary)
    if not slug:
        return None, None

    # If we used a NAME_OVERRIDES entry, derive the display title from the
    # override too (e.g. "alpenglow" -> "Alpenglow") so the page title matches.
    if NAME_OVERRIDES.get(primary.strip().lower()):
        display_title = slug.capitalize() if "-" not in slug else " ".join(p.capitalize() for p in slug.split("-"))
    else:
        display_title = primary

    # Spotify track ID from URI like spotify:track:6xxzSU0zbf1l5xX1wIzIlt
    track_id = spotify_uri.split(":")[-1] if ":" in spotify_uri else ""

    year = parse_release_year(release_date)
    primary_genre, secondary_genre = derive_genre(slug, spotify_genres, known_genres)
    description = description_from_genres(spotify_genres, year)

    # Build tag list
    tags = [f"@{slug.replace('-', '')}", "1-off", era]
    feats = featured_artists(artists_field)
    for f in feats:
        tags.append(f"@{slugify(f).replace('-', '')}")

    # Build front matter
    fm_lines = ["---"]
    fm_lines.append(f'title: "{display_title}"')
    fm_lines.append(f"date: {release_date if release_date else datetime.now().strftime('%Y-%m-%d')}")
    fm_lines.append('category: "1off"')
    if primary_genre:
        fm_lines.append(f'genre_primary: "{primary_genre}"')
    if secondary_genre:
        fm_lines.append(f'genre_secondary: "{secondary_genre}"')
    fm_lines.append(f'era: "{era}"')
    fm_lines.append("tags:")
    for t in tags:
        fm_lines.append(f"  - '{t}'")
    fm_lines.append("---")

    # Build body
    body_lines = []
    if description:
        body_lines.append("")
        body_lines.append(description)

    body_lines.append("")
    feat_str = ""
    if feats:
        feat_str = " feat. " + ", ".join(feats)
    album_str = f" — *{album}*" if album and album != track_name else ""
    year_str = f" ({year})" if year else ""
    body_lines.append(f"**{track_name}**{feat_str}{album_str}{year_str}")
    body_lines.append("")

    if track_id:
        body_lines.append(
            f'<iframe style="border-radius:12px" '
            f'src="https://open.spotify.com/embed/track/{track_id}" '
            f'width="100%" height="152" frameBorder="0" allowfullscreen="" '
            f'allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" '
            f'loading="lazy"></iframe>'
        )

    content = "\n".join(fm_lines) + "\n" + "\n".join(body_lines) + "\n"
    return slug, content


def era_from_filename(csv_path):
    """Songs-Aa-2020s.csv -> 2020s; Songs-Aa-1900s.csv -> 1900s; etc."""
    name = csv_path.stem  # 'Songs-Aa-2020s'
    parts = name.rsplit("-", 1)
    if len(parts) == 2:
        return parts[1]
    return "all"


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 explode_1offs.py path/to/Songs-Xx-2020s.csv [more.csv ...]")
        sys.exit(1)

    if not CONTENT_DIR.exists():
        print(f"ERROR: {CONTENT_DIR} not found. Run this from your Hugo repo root.")
        sys.exit(1)

    known_genres = load_known_artist_genres()
    print(f"Loaded {len(known_genres)} known-artist genres from {TAG_GENRES_PATH}\n")

    grand_created = 0
    grand_skipped = 0
    grand_already = []
    grand_malformed = 0

    for csv_path_str in sys.argv[1:]:
        csv_path = Path(csv_path_str)
        if not csv_path.exists():
            print(f"WARNING: {csv_path} not found, skipping.")
            continue

        era = era_from_filename(csv_path)
        print(f"\n=== {csv_path.name} (era={era}) ===")

        with csv_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for track in reader:
                slug, content = build_post_md(track, known_genres, era)
                if not slug:
                    grand_malformed += 1
                    continue

                target = CONTENT_DIR / f"{slug}.md"
                if target.exists():
                    grand_already.append((slug, csv_path.name))
                    grand_skipped += 1
                    continue

                target.write_text(content, encoding="utf-8")
                grand_created += 1
                print(f"  created  {slug}.md")

    print(f"\n=== Summary ===")
    print(f"Created:   {grand_created}")
    print(f"Skipped (already exists): {grand_skipped}")
    print(f"Malformed rows: {grand_malformed}")
    if grand_already:
        print(f"\nArtists already on site (you may want to manually add the new track to their page):")
        for slug, src in grand_already:
            print(f"  {slug:35s}  (from {src})")


if __name__ == "__main__":
    main()
