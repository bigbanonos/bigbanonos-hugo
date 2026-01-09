import csv
import os
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "data" / "songs.csv"
POSTS_DIR = ROOT / "content" / "posts"

def clean_text(text):
    if not text: return ""
    return text.strip().strip("'").strip('"').strip()

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "song"

def parse_list_field(value: str):
    if not value: return []
    return [clean_text(p) for p in value.split(",") if p.strip()]

def get_perfect_thumbnail(yt_url):
    if not yt_url: return None
    video_id = None
    if "v=" in yt_url:
        video_id = yt_url.split("v=")[1].split("&")[0]
    elif "youtu.be/" in yt_url:
        video_id = yt_url.split("youtu.be/")[1].split("?")[0]
    
    if video_id:
        return f"https://wsrv.nl/?url=https://img.youtube.com/vi/{video_id}/hqdefault.jpg&w=600&h=338&fit=cover&output=webp&q=80"
    return None

def main():
    if not CSV_PATH.exists():
        print(f"CSV not found: {CSV_PATH}")
        return

    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    created = 0

    with CSV_PATH.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_title = row.get("title", "")
            title = clean_text(raw_title)
            artist = clean_text(row.get("artist_display", ""))
            
            if artist and artist not in title:
                display_title = f"{artist} – {title}"
            else:
                display_title = title

            if not title: continue

            slug = row.get("slug", "").strip()
            if not slug:
                slug = slugify(f"{artist}-{title}")

            if "neeqah" in slug or "bhad-bhabie" in slug: continue

            post_path = POSTS_DIR / f"{slug}.md"
            tags = parse_list_field(row.get("tags", ""))
            yt_url = row.get("yt_url", "").strip()
            cover_image = get_perfect_thumbnail(yt_url)
            tags_yaml = ", ".join(f'"{t}"' for t in tags)

            front_matter_lines = [
                "---",
                f'title: "{display_title}"',
                f'slug: "{slug}"',  # <--- THIS IS THE FIX. LOCKS THE URL.
                f"date: {datetime.now().isoformat(timespec='seconds')}",
                "draft: false",
            ]
            
            if tags_yaml: front_matter_lines.append(f"tags: [{tags_yaml}]")
            if yt_url: front_matter_lines.append(f'youtube: "{yt_url}"')
            if cover_image:
                front_matter_lines.append(f'cover:\n    image: "{cover_image}"\n    alt: "{display_title}"\n    relative: false')

            front_matter_lines.append("---")
            
            body_parts = []
            if yt_url:
                video_id = yt_url.split("v=")[1].split("&")[0] if "v=" in yt_url else yt_url.split("youtu.be/")[1]
                body_parts.append(f'{{{{< youtube "{video_id}" >}}}}')
            
            notes = clean_text(row.get("notes", ""))
            if notes: body_parts.append(f"\n{notes}")

            content = "\n".join(front_matter_lines + body_parts)

            with post_path.open("w", encoding="utf-8") as f_out:
                f_out.write(content)
            
            created += 1
            if created % 500 == 0: print(f"Generated {created} locked posts...")

    print(f"--- SUCCESS: Regenerated {created} Posts with Locked URLs ---")

if __name__ == "__main__":
    main()