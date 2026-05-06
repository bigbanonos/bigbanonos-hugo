#!/usr/bin/env python3
"""
reconcile_letter_h.py

Reads audit_letter_h_review.csv and executes the recommended actions.

Default mode is DRY RUN — prints what would happen, makes no changes.
Add --write to actually do it.

Actions handled:
  KEEP                — no-op
  MOVE_AND_RENAME     — move file from content/ to content/posts/<slug>.md
  RENAME              — rename in place to content/posts/<slug>.md
  MERGE_THEN_DELETE   — keep richer of two files at canonical path, delete other
  MERGE_REVIEW        — picks the larger file, keeps it at canonical, reports the rest for manual review
  CREATE              — generate new post from CSV with Spotify embeds
  REVIEW (orphans)    — handled by hardcoded classification (see ORPHAN_VERDICTS below)

For CREATE actions, reads from the source CSVs in --csv-dir to build the post body.

Usage:
    python reconcile_letter_h.py --csv-dir "C:\\path\\to\\spotify_playlists"
    python reconcile_letter_h.py --csv-dir "C:\\path\\to\\spotify_playlists" --write

Requires audit_letter_h_review.csv in current directory.
"""
import csv
import re
import shutil
import sys
from pathlib import Path
from collections import defaultdict

AUDIT_CSV = "audit_letter_h_review.csv"

# Hardcoded verdicts for the 13 H orphans. JOFALLON approved.
ORPHAN_VERDICTS = {
    # Featured-artist concat junk — DELETE
    "content/posts/h-e-r-dj-khaled-bryson-tiller.md": "DELETE",
    "content/posts/heavenly-calvin-johnson.md": "DELETE",
    "content/posts/hitkidd-gloss-up-aleza-slimeroni-k-carbon.md": "DELETE",
    "content/posts/homer-hether-flikka.md": "DELETE",
    # Title-relic / dupe slugs — DELETE
    "content/hamilton-leithauser-i-retired.md": "DELETE",
    "content/herman-dune-with-tankful-of-gas.md": "DELETE",
    "content/hurray-for-riff-raff-3-songs.md": "DELETE",
    # Hunx redundancy — DELETE
    "content/hunx.md": "DELETE",
    "content/hunx-his-punx-5-songs.md": "DELETE",
    # Real artists not yet in any CSV — MOVE to content/posts/, flag for "pull CSV later"
    "content/haircut-100.md": "MOVE_TO_POSTS",
    "content/half-seas-over.md": "MOVE_TO_POSTS",
    "content/heartless-bastards.md": "MOVE_TO_POSTS",
    "content/howling-hex.md": "MOVE_TO_POSTS",
}

# Track changes for reporting
class Report:
    def __init__(self):
        self.moved = []
        self.renamed = []
        self.deleted = []
        self.merged = []
        self.created = []
        self.review_needed = []
        self.errors = []
        self.skipped = []

    def summary(self):
        print(f"\n{'='*60}")
        print("RECONCILIATION SUMMARY")
        print(f"{'='*60}")
        print(f"  Moved:           {len(self.moved)}")
        print(f"  Renamed:         {len(self.renamed)}")
        print(f"  Merged:          {len(self.merged)}")
        print(f"  Deleted:         {len(self.deleted)}")
        print(f"  Created:         {len(self.created)}")
        print(f"  Skipped:         {len(self.skipped)}")
        print(f"  Manual review:   {len(self.review_needed)}")
        print(f"  Errors:          {len(self.errors)}")
        if self.review_needed:
            print(f"\nManual review needed:")
            for s in self.review_needed:
                print(f"  - {s}")
        if self.errors:
            print(f"\nErrors:")
            for s in self.errors:
                print(f"  - {s}")


def normalize_path(p):
    """Convert any path style to forward-slash for comparison."""
    return str(p).replace("\\", "/")


def to_path(p):
    return Path(str(p).replace("\\", "/"))


def safe_move(src, dst, write, report, kind="moved"):
    """Move src to dst. Refuses if dst exists."""
    src_p = to_path(src)
    dst_p = to_path(dst)
    if not src_p.exists():
        report.errors.append(f"{kind.upper()}: source missing: {src}")
        return False
    if dst_p.exists():
        report.errors.append(f"{kind.upper()}: destination already exists: {dst}")
        return False
    if write:
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_p), str(dst_p))
    msg = f"{src} -> {dst}"
    if kind == "moved":
        report.moved.append(msg)
    else:
        report.renamed.append(msg)
    print(f"  [MOVE] {msg}")
    return True


def safe_delete(path, write, report):
    p = to_path(path)
    if not p.exists():
        report.errors.append(f"DELETE: file missing: {path}")
        return False
    if write:
        p.unlink()
    report.deleted.append(str(path))
    print(f"  [DEL]  {path}")
    return True


def safe_merge(legacy_path, canonical_path, write, report):
    """Pick whichever file is larger, keep at canonical, delete the other.
    For now the rule is: if legacy is bigger, replace canonical with legacy then delete legacy.
    Otherwise just delete legacy. JOFALLON can manually inspect afterward.
    """
    legacy = to_path(legacy_path)
    canonical = to_path(canonical_path)
    if not legacy.exists() or not canonical.exists():
        report.errors.append(f"MERGE: missing file. legacy={legacy_path} canonical={canonical_path}")
        return False
    legacy_size = legacy.stat().st_size
    canonical_size = canonical.stat().st_size
    if legacy_size > canonical_size:
        # Legacy is richer; promote it
        if write:
            shutil.copy2(str(legacy), str(canonical))
            legacy.unlink()
        report.merged.append(f"PROMOTED legacy ({legacy_size}b) over canonical ({canonical_size}b): {legacy_path} -> {canonical_path}")
        print(f"  [MERG] {legacy_path} (richer, {legacy_size}b) -> {canonical_path}, then delete legacy")
    else:
        # Canonical is richer or same; just delete legacy
        if write:
            legacy.unlink()
        report.merged.append(f"KEPT canonical ({canonical_size}b), deleted legacy ({legacy_size}b): {legacy_path}")
        print(f"  [MERG] kept {canonical_path} ({canonical_size}b), deleted {legacy_path} ({legacy_size}b)")
    return True


# ---------------------------------------------------------------------------
# CREATE: generate posts from CSV
# ---------------------------------------------------------------------------

LEADING_THE = re.compile(r"^the[-\s]+", re.IGNORECASE)
NON_ALNUM = re.compile(r"[^a-zA-Z0-9]+")

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


def safe_title(s):
    return s.replace('"', '').replace("'", "'").strip()


def build_csv_index(csv_dir):
    """Read all 6 H CSVs, return dict: slug -> list of track rows from all sources."""
    files = [
        "All_artists_Hh.csv",
        "Songs-HH-2020s.csv",
        "Songs-Hh-2000s-10s.csv",
        "Songs-Hh-1900s.csv",
        "Songs-Hh-DH.csv",
        "Covers-Hh.csv",
    ]
    index = defaultdict(list)
    csv_dir = Path(csv_dir)
    for fname in files:
        path = csv_dir / fname
        if not path.exists():
            continue
        with open(path, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                primary = primary_artist(r.get("Artist Name(s)", ""))
                if not primary:
                    continue
                slug = canonicalize(primary)
                if slug:
                    r["__source__"] = fname
                    r["__primary__"] = primary
                    index[slug].append(r)
    return index


def era_for_year(year):
    if not year:
        return None
    try:
        y = int(year[:4])
    except (ValueError, TypeError):
        return None
    if y >= 2020:
        return "2020s"
    if y >= 2000:
        return "2000s-2010s"
    return "1900s"


def make_post_content(slug, display_name, tracks):
    """Build markdown for a new artist post.
    Schema follows existing canonical format with Spotify iframe embeds."""
    if not tracks:
        return None

    # Determine era from earliest release
    years = []
    for t in tracks:
        rd = t.get("Release Date", "") or ""
        if rd[:4].isdigit():
            years.append(rd[:4])
    earliest_era = era_for_year(min(years)) if years else "uncategorized"

    # Determine letter
    letter = slug[0].upper()

    # Genres: collect from CSV "Genres" column, lowercase, dedupe
    genre_set = []
    for t in tracks:
        raw = (t.get("Genres") or "").lower()
        for g in raw.split(","):
            g = g.strip()
            if g and g not in genre_set:
                genre_set.append(g)
    genre_list = genre_set[:5]  # cap to 5

    # Explicit if any track is explicit
    is_explicit = any(str(t.get("Explicit", "")).lower() == "true" for t in tracks)

    # Date: use earliest Added At
    added_dates = [t.get("Added At", "")[:10] for t in tracks if t.get("Added At", "")]
    date_str = min(added_dates) if added_dates else "2024-01-01"

    # Build front matter
    title = safe_title(display_name)
    artist_tag = "@" + slug
    fm = [
        "---",
        f'title: "{title}"',
        f'slug: "{slug}"',
        f'date: {date_str}',
        'layout: post',
        f'letter: "{letter}"',
        f'era: "{earliest_era}"',
    ]
    if genre_list:
        fm.append("genre:")
        for g in genre_list:
            fm.append(f'  - "{g}"')
    if is_explicit:
        fm.append("explicit: true")
    fm.append("tags:")
    fm.append(f"  - '{artist_tag}'")
    fm.append("---")
    fm.append("")

    # Body: one Spotify iframe per track, in order
    embeds = []
    for t in tracks:
        uri = t.get("Track URI", "")
        if not uri or ":" not in uri:
            continue
        track_id = uri.split(":")[-1]
        embeds.append(
            f'<iframe src="https://open.spotify.com/embed/track/{track_id}" '
            f'width="100%" height="80" frameborder="0" '
            f'allow="encrypted-media" loading="lazy"></iframe>'
        )

    return "\n".join(fm) + "\n" + "\n\n".join(embeds) + "\n"


def execute_create(slug, display_name, csv_index, write, report):
    target = to_path(f"content/posts/{slug}.md")
    if target.exists():
        report.skipped.append(f"CREATE: {target} already exists, skipping")
        print(f"  [SKIP] {target} exists")
        return
    tracks = csv_index.get(slug, [])
    if not tracks:
        report.errors.append(f"CREATE: no CSV tracks found for {slug}")
        return
    content = make_post_content(slug, display_name, tracks)
    if not content:
        report.errors.append(f"CREATE: failed to build content for {slug}")
        return
    if write:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    report.created.append(str(target))
    print(f"  [NEW]  {target} ({len(tracks)} tracks)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    write = "--write" in args
    csv_dir = None
    for i, a in enumerate(args):
        if a == "--csv-dir" and i + 1 < len(args):
            csv_dir = args[i + 1]

    if not csv_dir:
        print('Usage: python reconcile_letter_h.py --csv-dir "C:\\path\\to\\spotify_playlists" [--write]')
        sys.exit(1)

    if not Path(AUDIT_CSV).exists():
        print(f"ERROR: {AUDIT_CSV} not found. Run audit_letter_h.py first.")
        sys.exit(1)

    mode = "WRITE" if write else "DRY RUN"
    print(f"\n{'='*60}")
    print(f"RECONCILE LETTER H — {mode}")
    print(f"{'='*60}\n")

    print(f"Loading CSV index from {csv_dir}...")
    csv_index = build_csv_index(csv_dir)
    print(f"Indexed {len(csv_index)} unique artists across H CSVs\n")

    report = Report()

    # Read audit, processing rows until orphan section
    with open(AUDIT_CSV, encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        in_orphans = False
        for row in reader:
            slug = row.get("expected_slug", "").strip()
            if not slug:
                continue
            if slug.startswith("==="):
                in_orphans = True
                continue
            if slug == "expected_slug":
                # second header row (orphan section)
                in_orphans = True
                continue

            if not in_orphans:
                handle_matched_row(row, csv_index, write, report)

    # Handle orphans by hardcoded verdict
    print(f"\n--- Orphan handling ---")
    for orphan_path, verdict in ORPHAN_VERDICTS.items():
        if verdict == "DELETE":
            safe_delete(orphan_path, write, report)
        elif verdict == "MOVE_TO_POSTS":
            slug = Path(orphan_path).stem
            dst = f"content/posts/{slug}.md"
            safe_move(orphan_path, dst, write, report, kind="moved")

    report.summary()

    if not write:
        print(f"\n{'='*60}")
        print("DRY RUN COMPLETE — no files were modified.")
        print("To actually execute, re-run with --write")
        print(f"{'='*60}")


def handle_matched_row(row, csv_index, write, report):
    slug = row["expected_slug"].strip()
    display_name = row.get("display_name", "").strip() or slug
    action = row.get("recommended_action", "").strip()
    existing = row.get("existing_files", "").strip()
    file_count = int(row.get("file_count", "0") or 0)

    canonical = f"content/posts/{slug}.md"

    if action == "KEEP":
        return  # silent no-op

    if action == "CREATE":
        execute_create(slug, display_name, csv_index, write, report)
        return

    if action == "MOVE_AND_RENAME":
        files = [f.strip() for f in existing.split(";") if f.strip()]
        if len(files) != 1:
            report.errors.append(f"MOVE_AND_RENAME: expected 1 file, got {len(files)} for {slug}")
            return
        safe_move(files[0], canonical, write, report, kind="moved")
        return

    if action == "RENAME":
        files = [f.strip() for f in existing.split(";") if f.strip()]
        if len(files) != 1:
            report.errors.append(f"RENAME: expected 1 file, got {len(files)} for {slug}")
            return
        safe_move(files[0], canonical, write, report, kind="renamed")
        return

    if action == "MERGE_THEN_DELETE":
        files = [f.strip() for f in existing.split(";") if f.strip()]
        if len(files) != 2:
            report.errors.append(f"MERGE_THEN_DELETE: expected 2 files, got {len(files)} for {slug}")
            return
        # Identify which is canonical, which is legacy
        canonical_norm = normalize_path(canonical)
        legacy_files = [f for f in files if normalize_path(f) != canonical_norm]
        if len(legacy_files) != 1:
            report.errors.append(f"MERGE_THEN_DELETE: can't identify legacy for {slug}: {files}")
            return
        safe_merge(legacy_files[0], canonical, write, report)
        return

    if action == "MERGE_REVIEW":
        # Pick larger file, keep at canonical, delete others
        files = [f.strip() for f in existing.split(";") if f.strip()]
        if len(files) < 2:
            report.errors.append(f"MERGE_REVIEW: <2 files for {slug}: {files}")
            return
        # Find which (if any) is already at canonical
        canonical_norm = normalize_path(canonical)
        already_canonical = [f for f in files if normalize_path(f) == canonical_norm]
        legacies = [f for f in files if normalize_path(f) != canonical_norm]
        # Pick richest among all
        sized = []
        for f in files:
            p = to_path(f)
            if p.exists():
                sized.append((p.stat().st_size, f))
        if not sized:
            report.errors.append(f"MERGE_REVIEW: no files exist on disk for {slug}")
            return
        sized.sort(reverse=True)
        winner = sized[0][1]
        # If winner is not at canonical, move it there (and delete original); delete other legacies
        if normalize_path(winner) != canonical_norm:
            # First, ensure canonical doesn't exist (delete it if it's a smaller dupe)
            if to_path(canonical).exists():
                safe_delete(canonical, write, report)
            safe_move(winner, canonical, write, report, kind="renamed")
        for f in files:
            if normalize_path(f) == normalize_path(winner) or normalize_path(f) == canonical_norm:
                continue
            if to_path(f).exists():
                safe_delete(f, write, report)
        report.review_needed.append(
            f"{slug}: kept richest ({winner}), removed others. Verify content quality at {canonical}."
        )
        return

    # Unknown action — skip with note
    report.skipped.append(f"Unknown action '{action}' for {slug}, skipped.")


if __name__ == "__main__":
    main()
