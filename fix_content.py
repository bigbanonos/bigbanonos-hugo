import os
import re
import shutil

# CONFIG
ROOT_POSTS = 'posts'              # The "Homeless" folder currently at your root
DEST_DIR = os.path.join('content', 'posts') # The "Home" where Hugo lives

# REGEX TO KILL IFRAMES
YOUTUBE_REGEX = re.compile(r'<iframe[^>]*src=["\'](?:https?:)?//(?:www\.)?(?:youtube\.com/embed/|youtu\.be/)([\w-]+)[^"\']*["\'][^>]*>.*?</iframe>', re.IGNORECASE | re.DOTALL)
SPOTIFY_REGEX = re.compile(r'<iframe[^>]*src=["\'](https://open\.spotify\.com/embed/[^"\']+?)["\'][^>]*>.*?</iframe>', re.IGNORECASE | re.DOTALL)

def main():
    # 1. Ensure the destination exists
    if not os.path.exists(DEST_DIR):
        os.makedirs(DEST_DIR)
        print(f"Created folder: {DEST_DIR}")

    # 2. Determine where to look
    if os.path.exists(ROOT_POSTS):
        source_dir = ROOT_POSTS
        move_mode = True
        print(f"Found 'posts' folder at root. Moving files to {DEST_DIR}...")
    else:
        source_dir = DEST_DIR
        move_mode = False
        print(f"No root 'posts' folder found. Scanning {DEST_DIR} instead...")

    count = 0
    files = [f for f in os.listdir(source_dir) if f.endswith('.md')]

    if not files:
        print("ERROR: Found 0 .md files. Are your posts named .txt or .csv?")
        return

    for filename in files:
        src_path = os.path.join(source_dir, filename)
        dest_path = os.path.join(DEST_DIR, filename)

        # READ
        try:
            with open(src_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            print(f"Skipping broken file {filename}: {e}")
            continue

        # CLEAN
        content = content.replace('draft: true', 'draft: false') # Unhide
        content = YOUTUBE_REGEX.sub(r'{{< youtube "\1" >}}', content) # Lite YouTube
        content = SPOTIFY_REGEX.sub(r'{{< spotify "\1" >}}', content) # Lite Spotify

        # WRITE TO NEW HOME
        with open(dest_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # DELETE OLD HOME (If we moved it)
        if move_mode and src_path != dest_path:
            os.remove(src_path)

        count += 1
        if count % 500 == 0:
            print(f"Processed {count} files...")

    print(f"--- SUCCESS: Moved and Optimized {count} posts ---")

if __name__ == "__main__":
    main()