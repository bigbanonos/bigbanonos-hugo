import os
import re

CONTENT_DIR = os.path.join('content', 'posts')

# Regex to find HTML images: <img src="HTTPS://..." ...>
# We capture the URL inside the quotes.
IMG_SRC_REGEX = re.compile(r'(<img[^>]+src=["\'])(https?://[^"\']+)(["\'][^>]*>)', re.IGNORECASE)

# Regex to find Markdown images: ![alt](HTTPS://...)
MD_IMG_REGEX = re.compile(r'(!\[.*?\]\()(https?://[^)]+)(\))', re.IGNORECASE)

def optimize_url(url):
    # If already optimized, skip
    if "wsrv.nl" in url:
        return url
    
    # Skip if it's a relative path (local image)
    if not url.startswith("http"):
        return url

    # THE MAGIC: 
    # 1. output=webp (Next-gen format, tiny file size)
    # 2. w=500 (Resize to mobile friendly width)
    # 3. q=75 (Quality 75%, barely visible difference, huge savings)
    return f"https://wsrv.nl/?url={url}&w=500&output=webp&q=75"

def clean_file(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    original = content

    # 1. Fix HTML <img> tags
    # Replaces: src="https://big.jpg" 
    # With:     src="https://wsrv.nl/?url=https://big.jpg..."
    def replace_html(match):
        prefix = match.group(1)
        url = match.group(2)
        suffix = match.group(3)
        return f"{prefix}{optimize_url(url)}{suffix}"
    
    content = IMG_SRC_REGEX.sub(replace_html, content)

    # 2. Fix Markdown images ![alt](url)
    def replace_md(match):
        prefix = match.group(1)
        url = match.group(2)
        suffix = match.group(3)
        return f"{prefix}{optimize_url(url)}{suffix}"

    content = MD_IMG_REGEX.sub(replace_md, content)

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    print("--- STARTING IMAGE OPTIMIZATION ---")
    count = 0
    files = [f for f in os.listdir(CONTENT_DIR) if f.endswith(".md")]
    
    for filename in files:
        if clean_file(os.path.join(CONTENT_DIR, filename)):
            count += 1
            if count % 100 == 0:
                print(f"Optimized {count} posts...")
                
    print(f"--- SUCCESS: Compressed images in {count} posts. ---")

if __name__ == "__main__":
    main()