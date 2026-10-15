import os
import time
import random
import re
import requests
import gdown

# ==================== CONFIGURATION ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Naya Instagram Page ID (Lifestyle page ka)
IG_USER_ID = "17841417988076711"

# Naya Long-Lived Access Token Yahan Set Hai:
ACCESS_TOKEN = "EAGksz627CCUBSiKCpmZAt3ZBQOcpSue9ULD5e9pXCzSRX1jZAAbS5rxNRFjqofyLZBwtrsz7C2QkbSZCa7gj419kEIfK98Bjis3tdCjHXNcHytZApCRyr9p6FL4vP206h1KaqPuXX4nVip9K6t7sDUETXAu3cNzZCb9RTGLQfMZA1j3xeFyRZAMb5EJz0E2kr"

# Google Drive Folder Link (Yahan aap apna link daal sakte hain)
FOLDER_URL = "https://drive.google.com/drive/folders/1eKpm4q11Eq3ATsotjpWddiEdr4uTFk6p?usp=sharing"

CAPTIONS_FILE = os.path.join(BASE_DIR, "Captions.txt")
POSTED_LOG_FILE = os.path.join(BASE_DIR, "uploaded_reels.txt")

# Google Drive Direct Download Link for Thumbnail
THUMBNAIL_URL = "https://drive.google.com/uc?export=download&id=1vmrZIx-tfNc5DzGFinYMYIPuG_0emEoJ"
# =======================================================


def natural_sort_key(file_obj):
    """Sorts filenames numerically (1, 2, 3... 10, 11... 100) instead of alphabetically."""
    file_name = getattr(file_obj, 'path', str(file_obj))
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', file_name)]

def load_posted_history():
    """Reads already uploaded video names/IDs from log file."""
    if not os.path.exists(POSTED_LOG_FILE):
        return set()
    with open(POSTED_LOG_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def mark_as_posted(video_identifier):
    """Appends uploaded video name/ID to log file."""
    with open(POSTED_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{video_identifier}\n")

def get_random_caption_with_top5_hashtags():
    """Picks a random non-empty caption block from Captions.txt."""
    default_caption = "#lifestyle #reels #viral #trending #aesthetic"

    if not os.path.exists(CAPTIONS_FILE):
        return default_caption

    with open(CAPTIONS_FILE, "r", encoding="utf-8") as f:
        content = f.read().strip()

    blocks = [b.strip() for b in re.split(r'\n\s*\n', content) if b.strip()]
    
    if not blocks:
        return default_caption

    selected_block = random.choice(blocks)
    hashtags = re.findall(r'#\w+', selected_block)
    text_without_tags = re.sub(r'#\w+', '', selected_block).strip()

    if hashtags:
        random.shuffle(hashtags)
        top_5_hashtags = hashtags[:5]
        return f"{text_without_tags}\n\n{' '.join(top_5_hashtags)}"
    else:
        return selected_block if selected_block else default_caption

def fetch_drive_files():
    """Lists all video files in Google Drive folder using gdown without downloading."""
    print("📂 Scanning Google Drive folder for videos...")
    if not FOLDER_URL.strip():
        print("❌ Error: Google Drive Folder URL blank hai! Kripya FOLDER_URL mein link daalein.")
        return []
    try:
        files = gdown.download_folder(url=FOLDER_URL, quiet=True, skip_download=True)
        files.sort(key=natural_sort_key)
        return files
    except Exception as e:
        print("❌ Drive Fetching Error:", e)
        return []

def upload_and_publish_reel(video_url, caption, video_id_name):
    """Uploads Reel and waits for Meta processing before publishing."""
    print(f"\n🎬 Processing Upload for: {video_id_name}")
    print(f"📝 Selected Caption Preview:\n{caption[:80]}...")
    print(f"🖼️ Applying Custom Cover URL: {THUMBNAIL_URL}")

    clean_token = ACCESS_TOKEN.strip()

    # 1. Create Media Container with Custom Cover URL
    container_url = f"https://graph.facebook.com/v22.0/{IG_USER_ID}/media"
    params = {
        "access_token": clean_token,
        "caption": caption,
        "media_type": "REELS",
        "video_url": video_url,
        "cover_url": THUMBNAIL_URL
    }

    res = requests.post(container_url, params=params).json()

    if "id" not in res:
        print("❌ Container Creation Error:", res)
        if res.get('error', {}).get('code') == 100:
            print("🚨 Token Invalid Ya Expired Ho Gaya Hai! Kripya ACCESS_TOKEN Refresh Karein.")
        return False

    creation_id = res["id"]
    print(f"✅ Container Created (ID: {creation_id}). Checking Meta server processing status...")

    # Dynamic Processing Status Check Loop
    status_url = f"https://graph.facebook.com/v22.0/{creation_id}"
    status_params = {
        "fields": "status_code",
        "access_token": clean_token
    }

    max_retries = 24  # Wait up to 4 minutes (24 * 10s)
    for attempt in range(max_retries):
        time.sleep(10)
        status_res = requests.get(status_url, params=status_params).json()
        status_code = status_res.get("status_code", "IN_PROGRESS")

        if status_code == "FINISHED":
            print("✅ Video Processing Finished on Meta Servers!")
            break
        elif status_code == "ERROR":
            print(f"❌ Meta Video Processing Failed: {status_res}")
            return False
        else:
            print(f"⏳ Processing in progress on Meta ({attempt+1}/{max_retries})...")

    # 2. Publish Reel
    publish_url = f"https://graph.facebook.com/v22.0/{IG_USER_ID}/media_publish"
    pub_params = {
        "access_token": clean_token,
        "creation_id": creation_id
    }

    pub_res = requests.post(publish_url, params=pub_params).json()

    if "id" in pub_res:
        print(f"🚀 Reel Successfully Published! Post ID: {pub_res['id']}")
        mark_as_posted(video_id_name)
        return True
    else:
        print("❌ Publishing Error:", pub_res)
        return False

def run_single_reel_automation():
    posted_set = load_posted_history()
    print(f"📋 Total videos previously uploaded: {len(posted_set)}")

    all_files = fetch_drive_files()
    if not all_files:
        return

    # Filter out already uploaded videos
    pending_files = []
    for f in all_files:
        file_identifier = getattr(f, 'path', getattr(f, 'id', str(f)))
        if file_identifier not in posted_set:
            pending_files.append(f)

    print(f"🎯 Total pending videos left for upload: {len(pending_files)}")

    if not pending_files:
        print("🎉 Saare videos pehle hi upload ho chuke hain!")
        return

    # Sirf 1 single pending file uthayenge is run ke liye
    file_obj = pending_files[0]
    file_id = getattr(file_obj, 'id', None)
    file_name = getattr(file_obj, 'path', str(file_id))
    
    if not file_id:
        print("❌ File ID nahi mila!")
        return

    # 25 se 35 minutes ke beech ka random delay (seconds mein: 1500 se 2100)
    random_delay = random.randint(1500, 2100)
    print(f"⏳ Random wait of {random_delay // 60} minutes before uploading this reel...")
    time.sleep(random_delay)

    direct_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    caption = get_random_caption_with_top5_hashtags()
    
    success = upload_and_publish_reel(direct_url, caption, file_name)

    if success:
        print("🚀 Ek reel successfully upload ho gayi, ab script band ho rahi hai!")
    else:
        print("⚠️ Video upload fail ho gaya.")

if __name__ == "__main__":
    run_single_reel_automation()
