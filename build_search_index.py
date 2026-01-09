import os
import json
import re

# CONFIG
POSTS_DIR = os.path.join('content', 'posts')
OUTPUT_FILE = os.path.join('static', 'index.json')

def parse_post(filepath, filename):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # Extract Title
    title_match = re.search(r'title:\s*"(.*?)"', content)
    title = title_match.group(1) if title_match else filename.replace(".md", "")

    # Extract Tags
    tags_match = re.search(r'tags:\s*\[(.*?)\]', content)
    tags = []
    if tags_match:
        # Clean up tags: "tag1", "tag2" -> [tag1, tag2]
        raw_tags = tags_match.group(1)
        tags = [t.strip().strip('"').strip("'") for t in raw_tags.split(',') if t.strip()]

    # Extract Slug (URL)
    slug = filename.replace(".md", "")
    
    return {
        "title": title,
        "permalink": f"/{slug}/",
        "tags": tags,
        # We DO NOT include body text. It crashes the browser.
        "summary": f"{title} - {', '.join(tags)}"
    }

def main():
    print("--- BUILDING SEARCH INDEX ---")
    
    # Ensure static folder exists
    if not os.path.exists('static'):
        os.makedirs('static')

    posts = []
    if os.path.exists(POSTS_DIR):
        for filename in os.listdir(POSTS_DIR):
            if filename.endswith(".md"):
                post_data = parse_post(os.path.join(POSTS_DIR, filename), filename)
                posts.append(post_data)
    
    # Save to static/index.json
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(posts, f)
        
    print(f"--- SUCCESS: Indexed {len(posts)} posts into {OUTPUT_FILE} ---")

if __name__ == "__main__":
    main()