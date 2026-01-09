import os

# CONFIG
CONTENT_DIR = os.path.join('content', 'posts')

# THE GARBAGE MAP (Weird crap -> Clean text)
REPLACEMENTS = {
    "â€™": "'",
    "â€œ": '"',
    "â€": '"',
    "â€“": "-",
    "â€”": "-",
    "Â": "",       # specific weird space
    "Ã©": "e",
    "Ã": "a",
    "â€¦": "..."
}

def clean_file(filepath):
    # Open as binary first to avoid encoding crashes, then decode safely
    with open(filepath, 'rb') as f:
        raw = f.read()
    
    # Decode as UTF-8 (replace errors so it doesn't crash)
    content = raw.decode('utf-8', errors='replace')
    original = content

    # 1. FIX ENCODING GARBAGE
    for garbage, clean in REPLACEMENTS.items():
        content = content.replace(garbage, clean)

    # 2. FIX DUPLICATE TAGS IN BODY (Optional cleanup)
    # This removes lines starting with "tags:" inside the post body
    lines = content.split('\n')
    new_lines = []
    in_front_matter = False
    dash_count = 0
    
    for line in lines:
        if line.strip() == '---':
            dash_count += 1
        
        # Keep everything in the front matter (top section)
        if dash_count < 2:
            new_lines.append(line)
        else:
            # We are in the body now. Remove junk.
            if line.strip().lower().startswith('tags: @'):
                continue # Skip the ugly tags line in the body
            if 'first posted by' in line.lower():
                continue # Skip the blogspot link
            new_lines.append(line)

    content = '\n'.join(new_lines)

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def main():
    print("--- STARTING BLEACH ---")
    count = 0
    for filename in os.listdir(CONTENT_DIR):
        if filename.endswith(".md"):
            if clean_file(os.path.join(CONTENT_DIR, filename)):
                count += 1
    print(f"--- CLEANED {count} FILES ---")

if __name__ == "__main__":
    main()