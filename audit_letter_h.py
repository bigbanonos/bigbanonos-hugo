#!/usr/bin/env python3
"""
audit_letter_h.py (v2)

Reconcile what's on disk under content/ and content/posts/ for letter H
against the six H CSVs. Read-only. Writes audit_letter_h_review.csv.

v2 fixes:
- broader suffix stripping for legacy slug variants (-N-songs in many forms)
- mojibake-tolerant matching (herman-d-ne -> herman-dune)
- featured-artist concat detection (heavenly-calvin-johnson stays orphan)
- typo aliasing (heraldo-negro -> helado-negro)

Usage:
    python audit_letter_h.py "C:\\path\\to\\spotify_playlists"
"""
import csv
import re
import sys
from pathlib import Path
from collections import defaultdict

LEADING_THE = re.compile(r"^the[-\s]+", re.IGNORECASE)
NON_ALNUM = re.compile(r"[^a-zA-Z0-9]+")

# Known typo / mojibake aliases (disk slug -> canonical CSV slug)
DISK_ALIASES = {
    "herman-d-ne": "herman-dune",
    "heraldo-negro": "helado-negro",
    "hidden-camera": "hidden-cameras",
    "hows-your-news": "how-s-your-news",
}

# Disk slugs that are featured-artist concats or title slugs — flag as orphan
KNOWN_ORPHAN_CONCATS = {
    "h-e-r-dj-khaled-bryson-tiller",
    "heavenly-calvin-johnson",
    "homer-hether-flikka",
    "hitkidd-gloss-up-aleza-slimeroni-k-carbon",
    "hamilton-leithauser-i-retired",
    "herman-dune-with-tankful-of-gas",
}

def canonicalize(name):
    if not name:
        return ""
    s = name.strip()
    s = LEADING_THE.sub("", s)
    folds = {
        "ü": "u", "ö": "o", "ä": "a", "é": "e", "è": "e", "ê": "e",
        "á": "a", "à": "a", "ó": "o", "ò": "o", "ñ": "n", "ç": "c",
        "í": "i", "ú": "u", "Ü": "u", "Ö": "o", "Ä": "a", "É": "e",
    }
    for k, v in folds.items():
        s = s.replace(k, v)
    s = NON_ALNUM.sub("-", s).strip("-").lower()
    return s

def primary_artist(field):
    return field.split(";")[0].strip() if field else ""

def read_csv(path):
    if not Path(path).exists():
        return []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))

def collect_csv_artists(csv_dir):
    csv_dir = Path(csv_dir)
    files = {
        "All_artists_Hh.csv":     "multi",
        "Songs-HH-2020s.csv":     "1off",
        "Songs-Hh-2000s-10s.csv": "1off",
        "Songs-Hh-1900s.csv":     "1off",
        "Songs-Hh-DH.csv":        "1off",
        "Covers-Hh.csv":          "cover",
    }
    artists = defaultdict(lambda: {
        "display_name": "", "sources": [], "track_count": 0,
        "is_multi": False, "is_1off": False, "is_cover": False,
        "tracks": [],
    })
    for fname, kind in files.items():
        for r in read_csv(csv_dir / fname):
            primary = primary_artist(r.get("Artist Name(s)", ""))
            if not primary:
                continue
            slug = canonicalize(primary)
            if not slug or not slug.startswith("h"):
                continue
            entry = artists[slug]
            if not entry["display_name"]:
                entry["display_name"] = primary
            if fname not in entry["sources"]:
                entry["sources"].append(fname)
            entry["track_count"] += 1
            if kind == "multi":   entry["is_multi"] = True
            elif kind == "1off":  entry["is_1off"] = True
            elif kind == "cover": entry["is_cover"] = True
            entry["tracks"].append({
                "name": r.get("Track Name", ""),
                "uri": r.get("Track URI", ""),
                "release_date": r.get("Release Date", ""),
                "source": fname,
            })
    return dict(artists)

BUCKET_PREFIXES = ("h-1900s-", "h-2020s-", "h-00s-10s-", "h-dh-")

def collect_disk_files():
    out = []
    for folder_name in ["content/posts", "content"]:
        folder = Path(folder_name)
        if not folder.exists():
            continue
        for p in folder.glob("*.md"):
            if not p.is_file():
                continue
            slug = p.stem.lower()
            if not slug.startswith("h"):
                continue
            if any(slug.startswith(b) for b in BUCKET_PREFIXES):
                continue
            out.append({"path": str(p), "slug": slug, "folder": folder_name})
    return out

# Aggressive suffix stripping — handles -N-songs, -top-songs, etc.
SUFFIX_RE = re.compile(
    r"-(?:"
    r"\d+-songs?|"
    r"\d+songs?|"
    r"xx-songs?|"
    r"top-songs?|"
    r"all-songs(?:-clean)?|"
    r"songs|"
    r"covers?|"
    r"i-retired"
    r")$",
    re.IGNORECASE,
)

def disk_slug_to_canonical(disk_slug):
    s = disk_slug
    if s in DISK_ALIASES:
        return DISK_ALIASES[s]
    if s in KNOWN_ORPHAN_CONCATS:
        return None
    for _ in range(3):
        new = SUFFIX_RE.sub("", s)
        if new == s:
            break
        s = new
    s = LEADING_THE.sub("", s).strip("-")
    return s

def attach_disk_to_artists(artists, disk_files):
    matches = defaultdict(list)
    orphans = []
    for f in disk_files:
        candidate = disk_slug_to_canonical(f["slug"])
        if candidate is None:
            orphans.append(f)
            continue
        if candidate in artists:
            matches[candidate].append(f)
            continue
        soft = None
        for canon in artists.keys():
            if candidate == canon:
                soft = canon
                break
            if candidate.startswith(canon) and len(candidate) - len(canon) <= 4:
                tail = candidate[len(canon):].strip("-")
                if not tail or tail.isdigit():
                    soft = canon
                    break
        if soft:
            matches[soft].append(f)
        else:
            orphans.append(f)
    return matches, orphans

def recommend(artist_slug, info, files_for_artist):
    n = len(files_for_artist)
    canonical_path_unix = f"content/posts/{artist_slug}.md"
    if n == 0:
        return ("CREATE", f"No file. Create content/posts/{artist_slug}.md from CSV.")
    if n == 1:
        f = files_for_artist[0]
        path_unix = f["path"].replace("\\", "/")
        if path_unix == canonical_path_unix:
            return ("KEEP", "Already at canonical location.")
        elif f["folder"] == "content":
            return ("MOVE_AND_RENAME", f"Move {f['path']} -> {canonical_path_unix}")
        else:
            return ("RENAME", f"Rename {f['path']} -> {canonical_path_unix}")
    has_canonical = any(
        f["path"].replace("\\", "/") == canonical_path_unix
        for f in files_for_artist
    )
    if has_canonical and n == 2:
        legacy = [f for f in files_for_artist
                  if f["path"].replace("\\", "/") != canonical_path_unix][0]
        return ("MERGE_THEN_DELETE",
                f"Canonical exists. Merge richer content from {legacy['path']} "
                f"into {canonical_path_unix}, delete legacy.")
    return ("MERGE_REVIEW",
            f"{n} files for one artist: " +
            "; ".join(f["path"] for f in files_for_artist))

def main():
    if len(sys.argv) < 2:
        print('Usage: python audit_letter_h.py "C:\\path\\to\\spotify_playlists"')
        sys.exit(1)
    csv_dir = sys.argv[1]
    print(f"Reading CSVs from: {csv_dir}")
    artists = collect_csv_artists(csv_dir)
    print(f"  Found {len(artists)} unique H artists in CSVs")
    disk_files = collect_disk_files()
    print(f"  Found {len(disk_files)} H-prefix .md files on disk")
    matches, orphans = attach_disk_to_artists(artists, disk_files)
    matched_count = sum(len(v) for v in matches.values())
    print(f"  Matched {matched_count} disk files to {len(matches)} artists")
    print(f"  {len(orphans)} orphan files")

    out_path = Path("audit_letter_h_review.csv")
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([
            "expected_slug", "display_name", "source_csvs", "track_count",
            "is_multi_track", "is_1off_only", "is_cover_artist",
            "existing_files", "file_count",
            "recommended_action", "notes",
        ])
        for slug in sorted(artists.keys()):
            info = artists[slug]
            files_here = matches.get(slug, [])
            action, notes = recommend(slug, info, files_here)
            w.writerow([
                slug, info["display_name"],
                "; ".join(info["sources"]),
                info["track_count"],
                info["is_multi"],
                info["is_1off"] and not info["is_multi"],
                info["is_cover"],
                "; ".join(f["path"] for f in files_here),
                len(files_here),
                action, notes,
            ])
        w.writerow([])
        w.writerow(["=== ORPHAN FILES (on disk, no CSV match) ==="])
        w.writerow([
            "expected_slug", "display_name", "source_csvs", "track_count",
            "is_multi_track", "is_1off_only", "is_cover_artist",
            "existing_files", "file_count",
            "recommended_action", "notes",
        ])
        for f in orphans:
            w.writerow([
                "(orphan)", "", "", "", "", "", "",
                f["path"], 1, "REVIEW",
                "Disk file but no CSV match. Either pull a CSV for this artist, "
                "rename to canonical, or delete (likely featured-artist concat slug).",
            ])
    print(f"\nWrote {out_path.resolve()}")
    print("Open in Excel, review the recommended_action column, override anything wrong.")

if __name__ == "__main__":
    main()
