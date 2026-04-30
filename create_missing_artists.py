#!/usr/bin/env python3
"""
create_missing_artists.py

Walk a folder of Exportify CSVs. For each CSV whose artist does NOT have an
existing post, CREATE a new post at content/<slug>.md with clean YAML and
stacked Spotify embeds. Same format as the backfill output.

Skips CSVs that already match an existing post (those use backfill_from_csv.py).

Usage:
    python create_missing_artists.py "C:\\path\\to\\spotify_playlists"            # dry run
    python create_missing_artists.py "C:\\path\\to\\spotify_playlists" --write    # do it
"""
import csv
import re
import sys
from pathlib import Path

CONTENT_DIRS = [Path("content"), Path("content/posts")]
OUT_DIR = Path("content")  # new posts land at content/<slug>.md (root, like Heart)
SLUG_RE = re.compile(r"[^a-z0-9]+")

def slugify(s):
    return SLUG_RE.sub("-", s.lower()).strip("-")

def slug_from_csv_filename(name):
    stem = Path(name).stem
    m = re.match(r"^(.+?)_-_(?:\d+|XX)_Songs?$", stem, re.IGNORECASE)
    if not m:
        return None
    return slugify(m.group(1).replace("_", " "))

def find_post_for_slug(slug):
    for d in CONTENT_DIRS:
        if (d / f"{slug}.md").exists():
            return d / f"{slug}.md"
    safe = re.compile(rf"^{re.escape(slug)}-(?:\d+-songs?|top-songs?|xx-songs?)$", re.IGNORECASE)
    for d in CONTENT_DIRS:
        if not d.exists():
            continue
        for f in d.glob(f"{slug}-*.md"):
            if safe.match(f.stem):
                return f
    return None

def title_from_slug(slug):
    out = []
    for p in slug.split("-"):
        if not p:
            continue
        if any(c.isdigit() for c in p):
            out.append(p)
        else:
            out.append(p.capitalize())
    return " ".join(out)

def title_from_csv(rows, slug):
    """Try to get a clean artist name from CSV's Artist Name(s) column."""
    for r in rows:
        a = (r.get("Artist Name(s)") or "").split(";")[0].strip()
        if a:
            return a
    return title_from_slug(slug)

def derive_era(release_dates):
    eras = set()
    for d in release_dates:
        m = re.match(r"(\d{4})", d or "")
        if not m:
            continue
        y = int(m.group(1))
        if y >= 2020:
            eras.add("2020s")
        elif y >= 2000:
            eras.add("2000s-2010s")
        else:
            eras.add("1900s")
    return sorted(eras)

def parse_genres(strings):
    seen = []
    for s in strings:
        if not s:
            continue
        for g in s.split(","):
            g = g.strip().lower()
            if g and g not in seen:
                seen.append(g)
    return seen[:5]

def spotify_embed(uri):
    if not uri:
        return ""
    tid = uri.split(":")[-1]
    return (f'<iframe src="https://open.spotify.com/embed/track/{tid}" '
            f'width="100%" height="80" frameborder="0" '
            f'allow="encrypted-media" loading="lazy"></iframe>')

def first_letter(slug):
    if not slug:
        return "#"
    c = slug[0].lower()
    return c.upper() if c.isalpha() else "#"

def earliest_added_date(rows):
    """Use the earliest 'Added At' from CSV as the post's date."""
    dates = []
    for r in rows:
        a = r.get("Added At") or ""
        m = re.match(r"(\d{4}-\d{2}-\d{2})", a)
        if m:
            dates.append(m.group(1))
    return min(dates) if dates else "2024-01-01"

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    write = "--write" in sys.argv

    if not args:
        print("Usage: python create_missing_artists.py <csv_dir> [--write]")
        sys.exit(1)

    csv_dir = Path(args[0])
    if not csv_dir.exists():
        print(f"ERROR: {csv_dir} not found")
        sys.exit(1)

    csvs = sorted(csv_dir.glob("*.csv"))
    print(f"Scanning {len(csvs)} CSVs...")

    bad_filename = 0
    skipped_exists = 0
    created = 0
    examples = []

    for csv_path in csvs:
        slug = slug_from_csv_filename(csv_path.name)
        if not slug:
            bad_filename += 1
            continue
        if find_post_for_slug(slug):
            skipped_exists += 1
            continue

        # this CSV has no existing post. create one.
        try:
            with csv_path.open(encoding="utf-8-sig", newline="") as fh:
                rows = list(csv.DictReader(fh))
        except Exception as e:
            print(f"  WARN: could not read {csv_path.name}: {e}")
            continue
        if not rows:
            continue

        rows.sort(key=lambda r: r.get("Release Date") or "0000", reverse=True)

        title = title_from_csv(rows, slug)
        date = earliest_added_date(rows)
        eras = derive_era([r.get("Release Date", "") for r in rows])
        genres = parse_genres([r.get("Genres", "") for r in rows])
        explicit = any(str(r.get("Explicit", "")).lower() == "true" for r in rows)
        letter = first_letter(slug)
        artist_tag = "@" + slug

        embeds = [spotify_embed(r.get("Track URI", "")) for r in rows]
        embeds = [e for e in embeds if e]

        fm = [
            "---",
            f'title: "{title}"',
            f'slug: "{slug}"',
            f"date: {date}",
            "layout: post",
            f'letter: "{letter}"',
        ]
        if eras:
            fm.append("era:")
            for e in eras:
                fm.append(f'  - "{e}"')
        if genres:
            fm.append("genre:")
            for g in genres:
                fm.append(f'  - "{g}"')
        if explicit:
            fm.append("explicit: true")
        fm.append("tags:")
        fm.append(f"  - '{artist_tag}'")
        fm.append("---")

        content = "\n".join(fm) + "\n\n" + "\n\n".join(embeds) + "\n"

        out_path = OUT_DIR / f"{slug}.md"
        if write:
            out_path.write_text(content, encoding="utf-8")
        created += 1
        if len(examples) < 10:
            examples.append(f"  {csv_path.name} -> {out_path}")

    mode = "WRITTEN" if write else "DRY RUN"
    print(f"\n=== {mode} ===")
    print(f"  CSVs scanned:                {len(csvs)}")
    print(f"  Skipped (post already exists): {skipped_exists}")
    print(f"  Skipped (bad CSV filename):    {bad_filename}")
    print(f"  Posts {'created' if write else 'would-create'}: {created}")
    if examples:
        print(f"\nFirst {len(examples)} new posts:")
        for ex in examples:
            print(ex)
    if not write:
        print("\nDry run only. To actually create:")
        print(f'  python create_missing_artists.py "{csv_dir}" --write')

if __name__ == "__main__":
    main()
