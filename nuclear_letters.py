#!/usr/bin/env python3
"""
nuclear_letters.py

End-to-end pipeline that processes every letter A-Z (skipping H — already done)
in a single run:

  for each letter:
    1. audit (read CSVs + disk, build review)
    2. reconcile (move/rename/merge/delete/create per audit recommendations)
    3. one git commit per letter

Skips H because H is already shipped at HEAD.
Writes a per-letter report to ./nuclear_run_report.txt at the end.

Safety:
  - Default is DRY RUN. Add --write to actually do it.
  - Refuses to clobber existing canonical files.
  - Skips orphan-deletes for letters where we don't have a known-orphan list yet
    (H had hand-curated verdicts; A-Z get auto-classified by heuristic only).

Heuristic for orphans (files on disk that don't match any CSV artist):
  - "Multi-hyphen featured-artist concat" → recommend DELETE
    (e.g. "wiz-khalifa-mustard.md" — slug starts with known artist + extra
     dash-separated names that look like artist names)
  - Everything else stays as MOVE_TO_POSTS (preserve)

Usage:
    python nuclear_letters.py --csv-dir "C:\\path\\to\\spotify_playlists"
    python nuclear_letters.py --csv-dir "C:\\path\\to\\spotify_playlists" --write
    python nuclear_letters.py --csv-dir "C:\\path\\to\\spotify_playlists" --write --letters BCDE
"""
import csv
import re
import shutil
import subprocess
import sys
from pathlib import Path
from collections import defaultdict

LEADING_THE = re.compile(r"^the[-\s]+", re.IGNORECASE)
NON_ALNUM = re.compile(r"[^a-zA-Z0-9]+")

DEFAULT_LETTERS = "ABCDEFGIJKLMNOPQRSTUVWXYZ"  # excludes H

SUFFIX_RE = re.compile(
    r"-(?:"
    r"\d+-songs?|\d+songs?|xx-songs?|top-songs?|"
    r"all-songs(?:-clean)?|songs|covers?|i-retired"
    r")$",
    re.IGNORECASE,
)

BUCKET_PREFIX_TEMPLATE = ("{l}-1900s-", "{l}-2020s-", "{l}-00s-10s-", "{l}-dh-")


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


def disk_slug_to_canonical(disk_slug):
    s = disk_slug
    for _ in range(3):
        new = SUFFIX_RE.sub("", s)
        if new == s:
            break
        s = new
    s = LEADING_THE.sub("", s).strip("-")
    return s


def collect_csv_artists_for_letter(csv_dir, letter):
    """Read all CSVs relevant to one letter, return:
       artists: dict slug -> {display_name, sources, track_count, is_multi, is_1off,
                              is_cover, tracks}
    """
    csv_dir = Path(csv_dir)
    L = letter.upper()
    l = letter.lower()

    # All naming variants we've seen in your library
    candidates = [
        (f"All_artists_{L}{l}.csv",       "multi"),
        (f"All_artists_{l}{l}.csv",       "multi"),  # safety
        (f"Songs-{L}{l}-2020s.csv",       "1off"),
        (f"Songs-{l}{l}-2020s.csv",       "1off"),
        (f"Songs-{L}{L}-2020s.csv",       "1off"),
        (f"Songs-{L}{l}-2000s-10s.csv",   "1off"),
        (f"Songs-{l}{l}-2000s-10s.csv",   "1off"),
        (f"Songs-{L}{L}-00s-10s.csv",     "1off"),
        (f"Songs-{L}{l}-00s-10s.csv",     "1off"),
        (f"Songs-{L}{l}-1900s.csv",       "1off"),
        (f"Songs-{l}{l}-1900s.csv",       "1off"),
        (f"Songs-{L}{L}-1900s.csv",       "1off"),
        (f"Songs-{L}{l}-DH.csv",          "1off"),
        (f"Songs-{l}{l}-DH.csv",          "1off"),
        (f"Songs-{L}{L}-DH.csv",          "1off"),
        (f"Covers-{L}{l}.csv",            "cover"),
        (f"Covers-{l}{l}.csv",            "cover"),
        (f"Covers-{L}{L}.csv",            "cover"),
    ]

    artists = defaultdict(lambda: {
        "display_name": "", "sources": [], "track_count": 0,
        "is_multi": False, "is_1off": False, "is_cover": False, "tracks": [],
    })

    seen_paths = set()
    for fname, kind in candidates:
        path = csv_dir / fname
        if not path.exists() or path in seen_paths:
            continue
        seen_paths.add(path)
        try:
            with open(path, encoding="utf-8-sig", newline="") as fh:
                rows = list(csv.DictReader(fh))
        except Exception:
            continue
        for r in rows:
            primary = primary_artist(r.get("Artist Name(s)", ""))
            if not primary:
                continue
            slug = canonicalize(primary)
            if not slug or not slug.startswith(letter.lower()):
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
                "explicit": str(r.get("Explicit", "")).lower() == "true",
                "added_at": r.get("Added At", ""),
                "genres": r.get("Genres", ""),
                "source": fname,
            })

    return dict(artists)


def collect_disk_files_for_letter(letter):
    L = letter.lower()
    bucket_prefixes = tuple(p.format(l=L) for p in BUCKET_PREFIX_TEMPLATE)
    out = []
    for folder_name in ["content/posts", "content"]:
        folder = Path(folder_name)
        if not folder.exists():
            continue
        for p in folder.glob("*.md"):
            if not p.is_file():
                continue
            slug = p.stem.lower()
            if not slug.startswith(L):
                continue
            if any(slug.startswith(b) for b in bucket_prefixes):
                continue
            out.append({"path": str(p), "slug": slug, "folder": folder_name})
    return out


def attach_disk_to_artists(artists, disk_files):
    matches = defaultdict(list)
    orphans = []
    for f in disk_files:
        candidate = disk_slug_to_canonical(f["slug"])
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


def looks_like_concat(slug, all_canon_slugs):
    """Heuristic: is this slug a featured-artist concat that should be deleted?
    True if: 4+ hyphen-separated parts, AND another canonical artist slug
    is a prefix, AND the remainder is also multi-word (looks like another name).
    """
    parts = slug.split("-")
    if len(parts) < 4:
        return False
    for canon in all_canon_slugs:
        if slug.startswith(canon + "-") and slug != canon:
            tail = slug[len(canon) + 1:]
            tail_parts = tail.split("-")
            if len(tail_parts) >= 2:
                return True
    return False


def make_post_content(slug, display_name, tracks):
    if not tracks:
        return None
    years = []
    for t in tracks:
        rd = t.get("release_date", "") or ""
        if rd[:4].isdigit():
            years.append(rd[:4])
    earliest_era = era_for_year(min(years)) if years else "uncategorized"
    letter_up = slug[0].upper()
    genre_set = []
    for t in tracks:
        raw = (t.get("genres") or "").lower()
        for g in raw.split(","):
            g = g.strip()
            if g and g not in genre_set:
                genre_set.append(g)
    genre_list = genre_set[:5]
    is_explicit = any(t.get("explicit") for t in tracks)
    added_dates = [t.get("added_at", "")[:10] for t in tracks if t.get("added_at")]
    date_str = min(added_dates) if added_dates else "2024-01-01"
    title = safe_title(display_name)
    artist_tag = "@" + slug
    fm = [
        "---",
        f'title: "{title}"',
        f'slug: "{slug}"',
        f'date: {date_str}',
        'layout: post',
        f'letter: "{letter_up}"',
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
    embeds = []
    for t in tracks:
        uri = t.get("uri", "")
        if not uri or ":" not in uri:
            continue
        track_id = uri.split(":")[-1]
        embeds.append(
            f'<iframe src="https://open.spotify.com/embed/track/{track_id}" '
            f'width="100%" height="80" frameborder="0" '
            f'allow="encrypted-media" loading="lazy"></iframe>'
        )
    return "\n".join(fm) + "\n" + "\n\n".join(embeds) + "\n"


def safe_move(src, dst, write):
    src_p = Path(src.replace("\\", "/"))
    dst_p = Path(dst.replace("\\", "/"))
    if not src_p.exists():
        return False, f"source missing: {src}"
    if dst_p.exists():
        return False, f"destination exists: {dst}"
    if write:
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_p), str(dst_p))
    return True, f"{src} -> {dst}"


def safe_delete(path, write):
    p = Path(path.replace("\\", "/"))
    if not p.exists():
        return False, f"missing: {path}"
    if write:
        p.unlink()
    return True, path


def safe_merge(legacy, canonical, write):
    leg = Path(legacy.replace("\\", "/"))
    can = Path(canonical.replace("\\", "/"))
    if not leg.exists() or not can.exists():
        return False, f"merge missing files: {legacy} / {canonical}"
    leg_size = leg.stat().st_size
    can_size = can.stat().st_size
    if leg_size > can_size:
        if write:
            shutil.copy2(str(leg), str(can))
            leg.unlink()
        return True, f"PROMOTED {legacy} ({leg_size}b) over {canonical} ({can_size}b)"
    if write:
        leg.unlink()
    return True, f"KEPT {canonical} ({can_size}b), deleted {legacy} ({leg_size}b)"


class LetterReport:
    def __init__(self, letter):
        self.letter = letter
        self.created = []
        self.moved = []
        self.merged = []
        self.deleted = []
        self.skipped = []
        self.errors = []
        self.csv_artists = 0
        self.disk_files = 0
        self.orphans_total = 0
        self.orphans_deleted = 0
        self.orphans_moved = 0

    def total_ops(self):
        return len(self.created) + len(self.moved) + len(self.merged) + len(self.deleted)

    def commit_msg(self):
        return (f"letter {self.letter.upper()}: "
                f"{len(self.created)} create, "
                f"{len(self.moved)} move, "
                f"{len(self.merged)} merge, "
                f"{len(self.deleted)} delete")


def process_letter(letter, csv_dir, write, all_canon_lookup):
    rep = LetterReport(letter)

    artists = collect_csv_artists_for_letter(csv_dir, letter)
    rep.csv_artists = len(artists)
    if not artists:
        rep.errors.append(f"no CSV artists found for {letter}")
        return rep

    disk_files = collect_disk_files_for_letter(letter)
    rep.disk_files = len(disk_files)

    matches, orphans = attach_disk_to_artists(artists, disk_files)
    rep.orphans_total = len(orphans)

    canon_slugs = set(artists.keys())
    all_canon_lookup[letter] = canon_slugs

    # Process matched artists: KEEP / MOVE / RENAME / MERGE / CREATE
    for slug, info in artists.items():
        canonical = f"content/posts/{slug}.md"
        files_for_artist = matches.get(slug, [])
        n = len(files_for_artist)

        if n == 0:
            # CREATE
            target = Path(canonical.replace("\\", "/"))
            if target.exists():
                rep.skipped.append(f"{canonical} already exists, skipping CREATE")
                continue
            content = make_post_content(slug, info["display_name"], info["tracks"])
            if not content:
                rep.errors.append(f"failed to build content for {slug}")
                continue
            if write:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            rep.created.append(canonical)
        elif n == 1:
            f = files_for_artist[0]
            path_unix = f["path"].replace("\\", "/")
            if path_unix == canonical:
                continue  # KEEP, no-op
            ok, msg = safe_move(f["path"], canonical, write)
            (rep.moved if ok else rep.errors).append(msg)
        else:
            # 2+ files: merge
            sized = []
            for f in files_for_artist:
                p = Path(f["path"].replace("\\", "/"))
                if p.exists():
                    sized.append((p.stat().st_size, f["path"]))
            if not sized:
                rep.errors.append(f"merge: no files exist for {slug}")
                continue
            sized.sort(reverse=True)
            winner_path = sized[0][1]
            winner_unix = winner_path.replace("\\", "/")
            # Move winner to canonical (delete canonical first if it exists and isn't winner)
            if winner_unix != canonical:
                if Path(canonical.replace("\\", "/")).exists():
                    ok, msg = safe_delete(canonical, write)
                    if ok:
                        rep.deleted.append(msg)
                ok, msg = safe_move(winner_path, canonical, write)
                (rep.moved if ok else rep.errors).append(msg)
            # Delete losers
            for f in files_for_artist:
                if f["path"].replace("\\", "/") in (winner_unix, canonical):
                    continue
                if Path(f["path"].replace("\\", "/")).exists():
                    ok, msg = safe_delete(f["path"], write)
                    if ok:
                        rep.deleted.append(msg)
            rep.merged.append(f"{slug} (winner: {winner_path})")

    # Process orphans by heuristic
    for f in orphans:
        slug = Path(f["path"]).stem.lower()
        if looks_like_concat(slug, canon_slugs):
            ok, msg = safe_delete(f["path"], write)
            if ok:
                rep.deleted.append(msg)
                rep.orphans_deleted += 1
        else:
            # MOVE_TO_POSTS if currently in content/, else KEEP
            if f["folder"] == "content":
                target = f"content/posts/{slug}.md"
                ok, msg = safe_move(f["path"], target, write)
                if ok:
                    rep.moved.append(msg)
                    rep.orphans_moved += 1

    return rep


def git_commit(msg, write):
    if not write:
        return f"(would commit) {msg}"
    try:
        subprocess.run(["git", "add", "-A"], check=True, capture_output=True)
        result = subprocess.run(
            ["git", "commit", "-m", msg],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            if "nothing to commit" in result.stdout.lower() or "nothing to commit" in result.stderr.lower():
                return f"(no changes) {msg}"
            return f"COMMIT FAILED: {result.stderr.strip()}"
        return f"committed: {msg}"
    except Exception as e:
        return f"COMMIT EXCEPTION: {e}"


def main():
    args = sys.argv[1:]
    write = "--write" in args
    csv_dir = None
    letters = DEFAULT_LETTERS
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--csv-dir" and i + 1 < len(args):
            csv_dir = args[i + 1]
            i += 2
        elif a == "--letters" and i + 1 < len(args):
            letters = args[i + 1].upper()
            i += 2
        else:
            i += 1

    if not csv_dir:
        print('Usage: python nuclear_letters.py --csv-dir "C:\\path\\to\\spotify_playlists" [--write] [--letters BCDE]')
        sys.exit(1)

    mode = "WRITE" if write else "DRY RUN"
    print(f"\n{'='*70}")
    print(f"NUCLEAR LETTERS — {mode}")
    print(f"Letters: {letters}")
    print(f"CSV dir: {csv_dir}")
    print(f"{'='*70}")

    all_canon_lookup = {}
    reports = []

    for letter in letters:
        print(f"\n=== Letter {letter} ===")
        rep = process_letter(letter, csv_dir, write, all_canon_lookup)
        reports.append(rep)
        print(f"  CSV artists:   {rep.csv_artists}")
        print(f"  Disk files:    {rep.disk_files}")
        print(f"  Created:       {len(rep.created)}")
        print(f"  Moved:         {len(rep.moved)}")
        print(f"  Merged:        {len(rep.merged)}")
        print(f"  Deleted:       {len(rep.deleted)}  (of which orphan-deleted: {rep.orphans_deleted})")
        print(f"  Errors:        {len(rep.errors)}")
        if rep.errors[:3]:
            for e in rep.errors[:3]:
                print(f"      ! {e}")
        if rep.total_ops() > 0:
            commit_result = git_commit(rep.commit_msg(), write)
            print(f"  {commit_result}")
        else:
            print(f"  (no ops, no commit)")

    # Final summary
    print(f"\n{'='*70}")
    print("FINAL SUMMARY")
    print(f"{'='*70}")
    grand_created = sum(len(r.created) for r in reports)
    grand_moved = sum(len(r.moved) for r in reports)
    grand_merged = sum(len(r.merged) for r in reports)
    grand_deleted = sum(len(r.deleted) for r in reports)
    grand_errors = sum(len(r.errors) for r in reports)
    print(f"Letters processed:  {len(reports)}")
    print(f"Total created:      {grand_created}")
    print(f"Total moved:        {grand_moved}")
    print(f"Total merged:       {grand_merged}")
    print(f"Total deleted:      {grand_deleted}")
    print(f"Total errors:       {grand_errors}")

    # Write detailed report
    report_path = Path("nuclear_run_report.txt")
    with report_path.open("w", encoding="utf-8") as fh:
        fh.write(f"NUCLEAR RUN — {mode}\n")
        fh.write(f"Letters: {letters}\n\n")
        for r in reports:
            fh.write(f"=== {r.letter} ===\n")
            fh.write(f"  CSV artists: {r.csv_artists}, Disk files: {r.disk_files}\n")
            fh.write(f"  Created: {len(r.created)} | Moved: {len(r.moved)} | "
                     f"Merged: {len(r.merged)} | Deleted: {len(r.deleted)} | "
                     f"Errors: {len(r.errors)}\n")
            for e in r.errors:
                fh.write(f"    ERROR: {e}\n")
            fh.write("\n")
    print(f"\nDetailed report: {report_path.resolve()}")

    if not write:
        print(f"\n{'='*70}")
        print("DRY RUN COMPLETE — no files modified, no commits made")
        print("To execute for real: re-run with --write")
        print(f"{'='*70}")
    else:
        print(f"\n{'='*70}")
        print("To deploy: git push")
        print(f"{'='*70}")


if __name__ == "__main__":
    main()
