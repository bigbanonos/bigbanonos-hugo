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
    return [p.strip() for p in value.split(",") if p.strip()]

def get_optimized_thumbnail(yt_url):
    """Extracts YouTube ID and creates a tiny, fast cover image URL."""
    if not yt_url: return None
    
    # Extract ID (supports v=ID and youtu.be/ID)
    video_id = None
    if "v=" in yt_url:
        video_id = yt_url.split("v=")[1].split("&")[0]
    elif "youtu.be/" in yt_url:
        video_id = yt_url.split("youtu.be/")[1].split("?")[0]
        
    if video_id:
        # Returns a wsrv.nl proxy URL that converts the thumbnail to WebP + resizes to 500px width
        return f"https://wsrv.nl/?url=https://img.youtube.com/vi/{video_id}/hqdefault.jpg&w=500&output=webp&q=75"
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
            title = row.get("title", "").strip()
            if not title: continue

            slug = row.get("slug", "").strip()
            if not slug:
                base = f"{row.get('artist_display','')}-{title}-{row.get('year','')}"
                slug = slugify(base)

            # --- BAN HAMMER ---
            if "neeqah" in slug or "bhad-bhabie" in slug:
                print(f"BANNED: Skipping {slug}")
                continue

            # Skip if exists? NO. We want to overwrite to apply the image fix.
            post_path = POSTS_DIR / f"{slug}.md"
            
            # (Data Extraction)
            tags = parse_list_field(row.get("tags", ""))
            yt_url = row.get("yt_url", "").strip()
            # ... (add other fields here as needed from your CSV)

            # GENERATE FAST COVER IMAGE
            cover_image = get_optimized_thumbnail(yt_url)

            # FORMAT YAML LISTS
            tags_yaml = ", ".join(f'"{t}"' for t in tags)

            front_matter_lines = [
                "---",
                f'title: "{title}"',
                f"date: {datetime.now().isoformat(timespec='seconds')}", # Refresh date
                "draft: false",
            ]
            
            if tags_yaml: front_matter_lines.append(f"tags: [{tags_yaml}]")
            if yt_url: front_matter_lines.append(f'youtube: "{yt_url}"')
            
            # THE SPEED FIX: Explicitly set a cover image
            if cover_image:
                front_matter_lines.append(f'cover:\n    image: "{cover_image}"\n    alt: "{title} Music Video"')

            front_matter_lines.append("---")
            
            # BODY CONTENT
            body_parts = []
            if row.get("artist_display"):
                body_parts.append(f"**{row.get('artist_display')} – {title}**")
                body_parts.append("")
            
            # Add Light YouTube Embed Code (Shortcode)
            if get_optimized_thumbnail(yt_url): # If we got an ID, make a real player
                 video_id = yt_url.split("v=")[1].split("&")[0] if "v=" in yt_url else yt_url.split("youtu.be/")[1]
                 body_parts.append(f'{{{{< youtube "{video_id}" >}}}}')
            elif yt_url:
                 body_parts.append(f"[Watch on YouTube]({yt_url})")

            content = "\n".join(front_matter_lines + body_parts)

            with post_path.open("w", encoding="utf-8") as f_out:
                f_out.write(content)
            
            created += 1
            if created % 500 == 0: print(f"Generated {created} posts...")

    print(f"--- SUCCESS: Regenerated {created} posts with Fast Images ---")

if __name__ == "__main__":
    main()