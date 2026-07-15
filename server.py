from flask import Flask, request, jsonify, send_file
import yt_dlp
import os
import uuid
import shutil
import logging

app = Flask(__name__)
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

logging.basicConfig(level=logging.INFO)

for old_file in os.listdir(DOWNLOAD_FOLDER):
    try:
        os.remove(os.path.join(DOWNLOAD_FOLDER, old_file))
    except Exception:
        pass

# فایل کوکی اصلی (فقط-خواندنی روی Render)
ORIGINAL_COOKIE_FILE = "/etc/secrets/cookies.txt"
# مسیر قابل‌نوشتن که ازش واقعاً استفاده می‌کنیم
WRITABLE_COOKIE_FILE = "/tmp/cookies.txt"

USE_COOKIE = False
if os.path.exists(ORIGINAL_COOKIE_FILE):
    try:
        shutil.copy(ORIGINAL_COOKIE_FILE, WRITABLE_COOKIE_FILE)
        USE_COOKIE = True
        logging.info("✅ Cookie file copied to writable location.")
    except Exception as e:
        logging.warning(f"⚠️ Could not copy cookie file: {e}")
else:
    logging.warning("⚠️ Cookie file not found, proceeding without cookies.")


def get_ydl_opts(format_id=None, output_template=None):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android"],
            }
        },
    }
    if USE_COOKIE:
        opts["cookiefile"] = WRITABLE_COOKIE_FILE
    if format_id and output_template:
        opts["format"] = format_id
        opts["outtmpl"] = output_template
    else: