#!/usr/bin/env python3
"""
Tag playlist_manifest.json with genre_primary and genre_secondary.

Run from your Hugo site root:
    python3 tag_genres.py

Reads:  static/playlist_manifest.json
Writes: static/playlist_manifest.json (in place, with backup)

Add new letters to GENRES below as you process them. The script is idempotent —
re-running just refreshes the tags.
"""
import json
import shutil
from pathlib import Path

MANIFEST = Path("static/playlist_manifest.json")

# ---------------------------------------------------------------------------
# Genre map: slug -> (primary, secondary_or_None)
# Slugs match the URL slug your build produces. Keys are lowercased + hyphenated.
# Add letters as you go. The H block is filled in.
# ---------------------------------------------------------------------------
GENRES = {
    # ===== H =====
    "h-e-r":                       ("rnb",        None),
    "haim":                        ("indie",      "pop"),
    "half-pint":                   ("dancehall",  None),
    "halo-benders":                ("indie",      None),
    "hamilton-leithauser":         ("indie",      "rock"),
    "handsome-furs":               ("indie",      "electronic"),
    "hank-ballard-the-midnighters":("rnb",        "rock"),
    "hannah-cohen":                ("indie",      "folk"),
    "harry-nilsson":               ("folk",       "pop"),
    "haru-nemuri":                 ("rock",       None),         # experimental noise/punk lives in rock bucket
    "hatchie":                     ("pop",        "indie"),
    "heart":                       ("rock",       None),
    "heatmiser":                   ("indie",      "rock"),
    "heavenly":                    ("indie",      "pop"),
    "heavy-trash":                 ("rock",       None),
    "hefner":                      ("indie",      "folk"),
    "heidecker-wood":              ("folk",       "rock"),
    "helena-deland":               ("indie",      "folk"),
    "hemlocke-springs":            ("pop",        "indie"),
    "heraldo-negro":               ("electronic", "indie"),
    "herbert":                     ("electronic", None),
    "herman-dune":                 ("folk",       "indie"),
    "hether-3-5-songs":            ("indie",      "pop"),
    "hidden-camera":               ("indie",      None),
    "hilary-duff":                 ("pop",        None),
    "hitkidd":                     ("rap",        None),
    "hives":                       ("rock",       None),
    "hoagy-carmichael":            ("folk",       None),         # american songbook lives nearest folk
    "hold-steady":                 ("indie",      "rock"),
    "hole":                        ("rock",       "indie"),
    "hollies":                     ("rock",       "pop"),
    "homer":                       ("rnb",        None),
    "hoodcelebrityy":              ("dancehall",  "rap"),
    "horsegirl":                   ("indie",      "rock"),
    "hospitality":                 ("indie",      "pop"),
    "hot-boys":                    ("rap",        None),
    "hot-chip":                    ("electronic", "pop"),
    "hovvdy":                      ("indie",      "folk"),
    "how-s-your-news":             ("indie",      None),
    "hunx":                        ("rock",       "pop"),
    "hurray-for-the-riff-raff":    ("indie",      "folk"),
    "hvob":                        ("electronic", None),
    "hyd":                         ("pop",        "electronic"),
    # ===== H 1-offs and covers =====
    "covers-hh":                   ("indie",      None),         # default cover bucket — can re-classify per cover later

    # Add A–G and I–Z here as you process them.
}


def slug_of(record):
    """Match the slug logic in the index template's buildHref()."""
    kind = record.get("kind")
    letter = (record.get("letter") or "#").lower()
    era = (record.get("era") or "").lower()
    if kind == "1off_bucket":
        if era in ("dh", "dancehall"):
            era = "dh"
        return f"{letter}-{era}-1offs"
    if kind == "cover":
        return f"covers-{letter}{letter}"
    # artist — strip suffixes the way the template does, then slugify
    name = (record.get("name") or "").strip()
    import re
    s = name
    s = re.sub(r"\s*[-\u2013\u2014]\s*(XX+|\d+\+?)\s*(Songs?|Remixes?|IP\s*Songs?|DH\s*Songs?|Rap\s*Songs?|Top\s*Songs?|Sons|Sogs)\s*$", "", s, flags=re.I)
    s = re.sub(r"\s*[-\u2013\u2014]\s*DH\s*SONGS?\s*$", "", s, flags=re.I)
    s = re.sub(r"\s*[-\u2013\u2014]\s*Top\s*Songs?\s*$", "", s, flags=re.I)
    s = re.sub(r"\s*[-\u2013\u2014]\s*Best\s*Song\s*$", "", s, flags=re.I)
    s = re.sub(r"\s*[-\u2013\u2014]\s*Covers?\s*$", "", s, flags=re.I)
    s = re.sub(r"\s*[-\u2013\u2014]\s*INSTRUMENTAL\s*Songs?\s*$", "", s, flags=re.I)
    s = re.sub(r"\s*[-\u2013\u2014]\s*IRISH\s*Songs?\s*$", "", s, flags=re.I)
    s = re.sub(r"\s*[-\u2013\u2014]\s*[\w\s]+\s*Songs?\s*$", "", s, flags=re.I)
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s


def main():
    if not MANIFEST.exists():
        raise SystemExit(f"Manifest not found: {MANIFEST.resolve()}")
    backup = MANIFEST.with_suffix(".json.bak")
    shutil.copy(MANIFEST, backup)
    print(f"Backup: {backup}")

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("Expected manifest to be a JSON list.")

    tagged = 0
    untagged_h = []
    for r in data:
        if r.get("kind") not in ("artist", "1off_bucket", "cover"):
            continue
        s = slug_of(r)
        if s in GENRES:
            primary, secondary = GENRES[s]
            r["genre_primary"] = primary
            if secondary:
                r["genre_secondary"] = secondary
            else:
                r.pop("genre_secondary", None)
            tagged += 1
        elif (r.get("letter") or "").upper() == "H":
            untagged_h.append((s, r.get("name")))

    MANIFEST.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Tagged: {tagged}")
    if untagged_h:
        print(f"\nH artists/buckets in manifest with no genre tag yet ({len(untagged_h)}):")
        for s, n in untagged_h:
            print(f"  {s:40s}  {n}")


if __name__ == "__main__":
    main()
