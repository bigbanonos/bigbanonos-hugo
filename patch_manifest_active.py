#!/usr/bin/env python3
"""
patch_manifest_active.py

Custom patch for rebuild_manifest.py: adds active/bucket/last_release/track_count
fields to each artist record so the homepage filter can use them.

Targets the actual structure of process_artist_post(): the return dict
ends with sort_name field, before the closing brace.

Usage:
    python patch_manifest_active.py            # dry run
    python patch_manifest_active.py --write    # apply
"""
import sys
from pathlib import Path

MANIFEST_SCRIPT = Path("rebuild_manifest.py")

# Anchor: end of the artist record return dict.
ANCHOR_OLD = '''        "tracks": track_count,
        "sort_name": slug,
    }'''

ANCHOR_NEW = '''        "tracks": track_count,
        "sort_name": slug,
        "active": parse_bool(fm.get("active")),
        "bucket": strip_quotes(fm.get("bucket", "") or ""),
        "last_release": strip_quotes(fm.get("last_release", "") or ""),
        "track_count_real": parse_int(fm.get("track_count")),
    }'''

# Also need to add the parse_bool and parse_int helpers, just before
# the process_artist_post function. We inject them near the top of the
# helper section.
HELPER_ANCHOR_OLD = '''def first_letter_of(slug):'''

HELPER_ANCHOR_NEW = '''def parse_bool(val):
    """Convert YAML-parsed value into a real bool."""
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower().strip("'\\"")
    return s in ("true", "yes", "1")


def parse_int(val):
    """Convert YAML-parsed value into an int."""
    if val is None:
        return 0
    if isinstance(val, int):
        return val
    s = str(val).strip().strip("'\\"")
    try:
        return int(s)
    except (TypeError, ValueError):
        return 0


def first_letter_of(slug):'''


def main():
    write = "--write" in sys.argv
    print(f"\n{'='*60}")
    print(f"PATCH rebuild_manifest.py — {'WRITE' if write else 'DRY RUN'}")
    print(f"{'='*60}\n")

    if not MANIFEST_SCRIPT.exists():
        print(f"ERROR: {MANIFEST_SCRIPT} not found")
        sys.exit(1)

    text = MANIFEST_SCRIPT.read_text(encoding="utf-8")

    # Idempotency check
    if '"active": parse_bool(' in text:
        print(f"SKIP: active field already in {MANIFEST_SCRIPT}")
        return

    # Check both anchors exist
    if ANCHOR_OLD not in text:
        print(f"FAIL: record-dict anchor not found in {MANIFEST_SCRIPT}")
        print(f"      Looking for the tracks/sort_name lines")
        sys.exit(1)

    if HELPER_ANCHOR_OLD not in text:
        print(f"FAIL: helper anchor 'def first_letter_of(slug):' not found")
        sys.exit(1)

    # Apply both
    new_text = text.replace(HELPER_ANCHOR_OLD, HELPER_ANCHOR_NEW, 1)
    new_text = new_text.replace(ANCHOR_OLD, ANCHOR_NEW, 1)

    if write:
        MANIFEST_SCRIPT.write_text(new_text, encoding="utf-8")
        print(f"OK: patched {MANIFEST_SCRIPT}")
        print(f"   Added: parse_bool() + parse_int() helpers")
        print(f"   Added: active, bucket, last_release, track_count_real fields to artist records")
        print()
        print("Next steps:")
        print("  python rebuild_manifest.py --write")
        print("  python add_active_filter_and_cleanup.py")
    else:
        print(f"WOULD patch {MANIFEST_SCRIPT}")
        print(f"  + parse_bool() and parse_int() helper functions")
        print(f"  + 4 new fields on each artist record: active, bucket, last_release, track_count_real")
        print()
        print(f"To apply: re-run with --write")


if __name__ == "__main__":
    main()
