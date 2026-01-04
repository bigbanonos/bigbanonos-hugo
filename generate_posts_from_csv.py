import csv
import os
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "data" / "songs.csv"
POSTS_DIR = ROOT / "content" / "posts"

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "song"

def parse_list_field(value: str):
    if not value: return []
    parts = [p.strip() for p in value.split(",") if p.strip()]
    return parts

def main():
    if not CSV_PATH.exists():
        print(f"CSV not found: {CSV_PATH}")
        return

    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    created = 0

    with CSV_PATH.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = row.get("title", "").strip()
            if not title: continue

            slug = row.get("slug", "").strip()
            if not slug:
                base = f"{row.get('artist_display','')}-{title}-{row.get('year','')}"
                slug = slugify(base)

            # --- BLOCK LIST: THIS STOPS THEM FOREVER ---
            # This ensures neeqah and bhad-bhabie are skipped
            if "neeqah" in slug or "bhad-bhabie" in slug:
                print(f"BANNED: Skipping {slug}")
                continue
            # -------------------------------------------

            post_path = POSTS_DIR / f"{slug}.md"
            if post_path.exists():
                # Skip if already exists so we don't overwrite manual edits
                continue

            # (Standard build logic)
            artist_display = row.get("artist_display", "").strip()
            artists_handles = parse_list_field(row.get("artists_handles", ""))
            tags = parse_list_field(row.get("tags", ""))
            year = row.get("year", "").strip()
            album = row.get("album", "").strip()
            label = row.get("label", "").strip()
            genres = row.get("genres", "").strip()
            yt_url = row.get("yt_url", "").strip()
            spotify_track_url = row.get("spotify_track_url", "").strip()
            spotify_playlist_url = row.get("spotify_playlist_url", "").strip()
            notes = row.get("notes", "").strip()

            date_str = row.get("date", "").strip()
            if date_str:
                try: date_obj = datetime.fromisoformat(date_str)
                except ValueError: date_obj = datetime.today()
            else: date_obj = datetime.today()
            iso_date = date_obj.isoformat(timespec="seconds")

            artists_yaml = ", ".join(f'"{a}"' for a in artists_handles)
            tags_yaml = ", ".join(f'"{t}"' for t in tags)

            front_matter_lines = [
                "---",
                f'title: "{title}"',
                f"date: {iso_date}",
                "draft: false",
            ]
            if artists_yaml: front_matter_lines.append(f"artists: [{artists_yaml}]")
            if tags_yaml: front_matter_lines.append(f"tags: [{tags_yaml}]")
            if album: front_matter_lines.append(f'album: "{album}"')
            if label: front_matter_lines.append(f'label: "{label}"')
            if year: front_matter_lines.append(f'year: "{year}"')
            if genres: front_matter_lines.append(f'genres: "{genres}"')
            if yt_url: front_matter_lines.append(f'youtube: "{yt_url}"')
            if spotify_track_url: front_matter_lines.append(f'spotify_track: "{spotify_track_url}"')
            if spotify_playlist_url: front_matter_lines.append(f'spotify_playlist: "{spotify_playlist_url}"')
            front_matter_lines.append("---")
            
            body_parts = []
            if artist_display:
                body_parts.append(f"**{artist_display} – {title}**")
                body_parts.append("")
            if notes:
                body_parts.append(notes)
                body_parts.append("")
            if yt_url: body_parts.append(f"[YouTube]({yt_url})")
            if spotify_track_url: body_parts.append(f"[Spotify track]({spotify_track_url})")
            if spotify_playlist_url: body_parts.append(f"[Playlist]({spotify_playlist_url})")

            # Construct the final file content
            content = "\n".join(front_matter_lines) + "\n\n" + "\n".join(body_parts) + "\n"
            
            # Write to file
            post_path.write_text(content, encoding="utf-8")
            print(f"Created: {slug}")
            created += 1

    print(f"Done. Created {created} new posts.")

if __name__ == "__main__":
    main()