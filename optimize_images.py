import os
import re

CONTENT_DIR = os.path.join('content', 'posts')

# Finds cover images in Front Matter (PaperMod specific)
# Looks for: cover: "https://..." OR image: "https://..."
FRONT_MATTER_REGEX = re.compile(r'(^|\n)\s*(cover|image|featured_image):\s*["\'](https?://[^"\']+)["\']', re.IGNORECASE)

# Finds standard markdown images ![...](https://...)
MARKDOWN_REGEX = re.compile(r'\!\[.*?\]\((https?://[^)\s]+)(?:.*?)?\)', re.IGNORECASE)

def optimize_url(url):
    if "wsrv.nl" in url: return url
    # Force compression
    return f"https://wsrv.nl/?url={url}&w=500&output=webp&q=75"

def clean_file(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    original = content

    # 1. Fix Front Matter (Cover Images)
    def replace_fm(match):
        prefix = match.group(1) + match.group(2) + ': "'
        url = match.group(3)
        return f'{prefix}{optimize_url(url)}"'
    
    content = FRONT_MATTER_REGEX.sub(replace_fm, content)

    # 2. Fix Markdown Body Images
    def replace_md(match):
        url = match.group(1)
        return f"![image]({optimize_url(url)})"

    content = MARKDOWN_REGEX.sub(replace_md, content)

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    print("--- STARTING NUCLEAR OPTIMIZATION ---")
    count = 0
    if os.path.exists(CONTENT_DIR):
        for filename in os.listdir(CONTENT_DIR):
            if filename.endswith(".md"):
                if clean_file(os.path.join(CONTENT_DIR, filename)):
                    count += 1
                    if count % 200 == 0: print(f"Nuked {count} posts...")
    
    print(f"--- SUCCESS: Optimized {count} posts ---")

if __name__ == "__main__":
    main()