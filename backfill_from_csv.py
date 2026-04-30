#!/usr/bin/env python3
"""
backfill_from_csv.py

Walk a folder of Exportify CSVs and backfill the matching canonical post for
each artist. Produces sparse, embed-only post bodies. Replaces existing body
content (per MOVE FORWARD directive).

Filename -> artist slug examples:
    Eddington_Again_-_2_Songs.csv      -> eddington-again
    Dusty_Springfield_-_XX_Songs.csv   -> dusty-springfield
    D'Vo_-_XX_Songs.csv                 -> d-vo
    E-40_-_2_Songs.csv                  -> e-40
    EARTHGANG_-_3_Songs.csv             -> earthgang

Usage:
    python backfill_from_csv.py "C:\\path\\to\\spotify_playlists"            # dry run
    python backfill_from_csv.py "C:\\path\\to\\spotify_playlists" --write    # do it

Defaults: skips posts that have YAML `manual: true`. Newest tracks first.
"""
import csv
import re
import sys
from pathlib import Path
from collections import defaultdict

CONTENT_DIRS = [Path("content"), Path("content/posts")]
SLUG_RE = re.compile(r"[^a-z0-9]+")

def slugify(s):
    return SLUG_RE.sub("-", s.lower()).strip("-")

def slug_from_csv_filename(name):
    """Eddington_Again_-_2_Songs.csv -> eddington-again
       D'Vo_-_XX_Songs.csv -> d-vo
       E-40_-_2_Songs.csv -> e-40
       dvsn_-_XX_Songs.csv -> dvsn
       dvsn_wrapped.csv -> None (skip - not a standard playlist)
    """
    stem = Path(name).stem
    # standard pattern: <artist>_-_<N>_Songs (where N is a number or 'XX')
    m = re.match(r"^(.+?)_-_(?:\d+|XX)_Songs?$", stem, re.IGNORECASE)
    if not m:
        return None
    artist_raw = m.group(1).replace("_", " ")
    return slugify(artist_raw)

def find_post_for_slug(slug):
    """Look for an existing canonical post matching this slug.
    Order: content/<slug>.md, content/posts/<slug>.md, then fuzzy filename match
    BUT only fuzzy-match files with -N-songs / -top-songs suffixes (legacy naming)
    so we don't accidentally clobber concert reviews, year-end lists, etc.
    """
    for d in CONTENT_DIRS:
        direct = d / f"{slug}.md"
        if direct.exists():
            return direct
    # tight fuzzy match: only legacy "-N-songs" or "-top-songs" patterns
    safe_suffix_re = re.compile(rf"^{re.escape(slug)}-(?:\d+-songs?|top-songs?|xx-songs?)$", re.IGNORECASE)
    for d in CONTENT_DIRS:
        if not d.exists():
            continue
        for f in d.glob(f"{slug}-*.md"):
            if safe_suffix_re.match(f.stem):
                return f
    return None

def parse_front_matter(text):
    if not text.startswith("---"):
        return "", text, {}
    end = text.find("\n---", 4)
    if end == -1:
        return "", text, {}
    fm_text = text[4:end]
    body = text[end+4:].lstrip("\n")
    # parse out simple top-level fields we care about
    fields = {}
    for line in fm_text.splitlines():
        m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*):\s*(.*?)$", line)
        if m and not line.startswith(" "):
            fields[m.group(1)] = m.group(2).strip()
    return text[:end+4], body, fields

def parse_tags_block(fm_text):
    """Extract the existing tags block as raw text so we preserve it."""
    lines = fm_text.splitlines()
    out = []
    in_tags = False
    for line in lines:
        if line.startswith("tags:"):
            in_tags = True
            out.append(line)
            continue
        if in_tags:
            if line.startswith(("  ", "\t")) or line.strip().startswith("-"):
                out.append(line)
            elif line.strip() == "":
                continue
            else:
                break
    return "\n".join(out) if out else ""

def derive_era(release_dates):
    """Pick eras based on years present in track release dates."""
    eras = set()
    for d in release_dates:
        m = re.match(r"(\d{4})", d or "")
        if not m:
            continue
        year = int(m.group(1))
        if year >= 2020:
            eras.add("2020s")
        elif year >= 2000:
            eras.add("2000s-2010s")
        else:
            eras.add("1900s")
    return sorted(eras) if eras else []

def parse_genres(genre_strings):
    """Genres come as comma-separated strings per row. Aggregate, dedupe, top 5."""
    seen = []
    for gs in genre_strings:
        if not gs:
            continue
        for g in gs.split(","):
            g = g.strip().lower()
            if g and g not in seen:
                seen.append(g)
    return seen[:5]

def spotify_embed(uri):
    """spotify:track:XXXX -> compact iframe."""
    if not uri:
        return ""
    tid = uri.split(":")[-1]
    return (f'<iframe src="https://open.spotify.com/embed/track/{tid}" '
            f'width="100%" height="80" frameborder="0" '
            f'allow="encrypted-media" loading="lazy"></iframe>')

def build_yaml(slug, fields, csv_genres, csv_eras, has_explicit, existing_tags_block):
    """Compose new YAML preserving the manual fields we care about."""
    # title: prefer existing, else derive from slug
    title = fields.get("title", "").strip().strip('"').strip("'")
    if not title:
        title = " ".join(p.capitalize() if not any(c.isdigit() for c in p) else p
                         for p in slug.split("-") if p)
    date = fields.get("date", "2020-01-01")
    date_match = re.match(r"\d{4}-\d{2}-\d{2}", date)
    date = date_match.group(0) if date_match else "2020-01-01"

    lines = ["---", f'title: "{title}"', f'slug: "{slug}"', f"date: {date}", "layout: post"]
    if csv_eras:
        lines.append("era:")
        for e in csv_eras:
            lines.append(f'  - "{e}"')
    if csv_genres:
        lines.append("genre:")
        for g in csv_genres:
            lines.append(f'  - "{g}"')
    if has_explicit:
        lines.append("explicit: true")
    if existing_tags_block:
        lines.append(existing_tags_block)
    lines.append("---")
    return "\n".join(lines)

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    write = "--write" in sys.argv

    if not args:
        print("Usage: python backfill_from_csv.py <csv_dir> [--write]")
        sys.exit(1)

    csv_dir = Path(args[0])
    if not csv_dir.exists():
        print(f"ERROR: {csv_dir} does not exist.")
        sys.exit(1)

    csvs = sorted(csv_dir.glob("*.csv"))
    print(f"Found {len(csvs)} CSVs in {csv_dir}")

    matched = 0
    no_match = 0
    skipped_manual = 0
    skipped_bad_filename = 0
    written = 0
    no_match_examples = []

    for csv_path in csvs:
        slug = slug_from_csv_filename(csv_path.name)
        if not slug:
            skipped_bad_filename += 1
            continue

        post = find_post_for_slug(slug)
        if not post:
            no_match += 1
            if len(no_match_examples) < 10:
                no_match_examples.append(f"{csv_path.name} -> {slug}")
            continue

        matched += 1

        # read CSV rows
        try:
            with csv_path.open(encoding="utf-8-sig", newline="") as fh:
                rows = list(csv.DictReader(fh))
        except Exception as e:
            print(f"  WARN: could not read {csv_path.name}: {e}")
            continue
        if not rows:
            continue

        # check existing post for manual flag
        try:
            text = post.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = post.read_text(encoding="utf-8", errors="replace")
        old_fm, old_body, fields = parse_front_matter(text)
        if fields.get("manual", "").lower() == "true":
            skipped_manual += 1
            continue

        # sort tracks newest -> oldest
        rows.sort(key=lambda r: r.get("Release Date") or "0000", reverse=True)

        embeds = [spotify_embed(r.get("Track URI", "")) for r in rows]
        embeds = [e for e in embeds if e]

        csv_genres = parse_genres([r.get("Genres", "") for r in rows])
        csv_eras = derive_era([r.get("Release Date", "") for r in rows])
        has_explicit = any(str(r.get("Explicit", "")).lower() == "true" for r in rows)

        existing_tags = parse_tags_block(old_fm[4:-4] if old_fm else "")
        new_yaml = build_yaml(slug, fields, csv_genres, csv_eras, has_explicit, existing_tags)
        new_body = "\n\n".join(embeds) + "\n"

        new_text = new_yaml + "\n\n" + new_body

        if write:
            post.write_text(new_text, encoding="utf-8")
        written += 1

    print(f"\n=== {'WRITTEN' if write else 'DRY RUN'} ===")
    print(f"  CSVs found:                  {len(csvs)}")
    print(f"  Matched to existing posts:   {matched}")
    print(f"  Posts {'updated' if write else 'would-update'}: {written}")
    print(f"  Skipped (manual: true flag): {skipped_manual}")
    print(f"  Skipped (bad CSV filename):  {skipped_bad_filename}")
    print(f"  No matching post:            {no_match}")

    if no_match_examples:
        print(f"\nFirst {len(no_match_examples)} unmatched (these need new posts created):")
        for ex in no_match_examples:
            print(f"  {ex}")

    if not write:
        print(f'\nDry run only. To actually backfill:')
        print(f'  python backfill_from_csv.py "{csv_dir}" --write')

if __name__ == "__main__":
    main()
