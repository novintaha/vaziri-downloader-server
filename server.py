from flask import Flask, request, jsonify, send_file
import yt_dlp
import os
import uuid
import shutil
import logging
import traceback
from pathlib import Path

app = Flask(__name__)

# تنظیمات پایه
DOWNLOAD_FOLDER = "downloads"
Path(DOWNLOAD_FOLDER).mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@app.before_request
def log_request():
    """لاگ تمام درخواست‌ها برای دیباگ"""
    logger.info(f"📥 {request.method} {request.path}")
    body = request.get_data()
    if body:
        logger.info(f"📦 BODY: {body[:200]}...")


# پاک‌سازی فایل‌های قبلی
def cleanup_old_files():
    for old_file in os.listdir(DOWNLOAD_FOLDER):
        try:
            os.remove(os.path.join(DOWNLOAD_FOLDER, old_file))
            logger.info(f"🗑️ Removed old file: {old_file}")
        except Exception as e:
            logger.warning(f"Could not remove {old_file}: {e}")


cleanup_old_files()

# تنظیمات کوکی
ORIGINAL_COOKIE_FILE = "/etc/secrets/cookies.txt"
WRITABLE_COOKIE_FILE = "/tmp/cookies.txt"
USE_COOKIE = False

if os.path.exists(ORIGINAL_COOKIE_FILE):
    try:
        shutil.copy(ORIGINAL_COOKIE_FILE, WRITABLE_COOKIE_FILE)
        USE_COOKIE = True
        logger.info("✅ Cookie copied successfully to /tmp/cookies.txt")
    except Exception as e:
        logger.warning(f"⚠️ Cookie copy failed: {e}")
else:
    logger.warning("⚠️ Cookie file not found in /etc/secrets/")


def get_ydl_opts(format_id=None, output=None):
    """
    تنظیمات بهینه yt-dlp برای دورزدن محدودیت‌های یوتیوب
    """
    opts = {
        "quiet": False,  # برای دیباگ، خطاها رو نشون بده
        "no_warnings": False,
        "nocheckcertificate": True,
        "ignoreerrors": True,
        "remote_components": ["ejs:github"],  # حل چالش‌های جاوااسکریپت
        "extractor_args": {
            "youtube": {
                "player_client": ["web"],  # فقط کلاینت وب برای جلوگیری از تداخل با کوکی
                "skip": ["hls", "dash"]  # رد کردن استریم‌های HLS و DASH برای سرعت بیشتر
            }
        },
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    }

    if USE_COOKIE:
        opts["cookiefile"] = WRITABLE_COOKIE_FILE
        logger.info("🍪 Using cookies for authentication")

    if format_id:
        opts["format"] = format_id
    else:
        opts["skip_download"] = True

    if output:
        opts["outtmpl"] = output

    return opts


@app.route("/")
def home():
    return jsonify({
        "status": "ok",
        "message": "VaziriDownloader Server is running",
        "cookies": "✅ Active" if USE_COOKIE else "❌ Not found"
    })


@app.route("/formats", methods=["POST"])
def get_formats():
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "JSON دریافت نشد"}), 400

        url = data.get("url")
        if not url:
            return jsonify({"error": "لینک ارسال نشده"}), 400

        logger.info(f"🔍 Getting formats for: {url}")

        with yt_dlp.YoutubeDL(get_ydl_opts()) as ydl:
            info = ydl.extract_info(url, download=False)

        formats = []
        for f in info.get("formats", []):
            # فقط فرمت‌هایی که ویدیو یا صدا دارند
            if f.get("vcodec") != "none" or f.get("acodec") != "none":
                formats.append({
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "resolution": f.get("resolution", "audio only"),
                    "filesize": f.get("filesize"),
                    "vcodec": f.get("vcodec"),
                    "acodec": f.get("acodec"),
                })

        if not formats:
            return jsonify({"error": "هیچ فرمتی برای این ویدیو پیدا نشد"}), 404

        logger.info(f"✅ Found {len(formats)} formats for: {info.get('title')}")

        return jsonify({
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "formats": formats
        })

    except Exception as e:
        logger.error(f"❌ Error in /formats: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/download", methods=["POST"])
def download_video():
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "JSON دریافت نشد"}), 400

        url = data.get("url")
        format_id = data.get("format_id")

        if not url:
            return jsonify({"error": "لینک ارسال نشده"}), 400

        if not format_id:
            format_id = "best"
            logger.info(f"ℹ️ No format_id provided, using 'best'")

        logger.info(f"⬇️ Downloading: {url} with format: {format_id}")

        filename_id = str(uuid.uuid4())
        output = os.path.join(DOWNLOAD_FOLDER, f"{filename_id}.%(ext)s")

        with yt_dlp.YoutubeDL(get_ydl_opts(format_id, output)) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        if not os.path.exists(filename):
            raise FileNotFoundError(f"File not found after download: {filename}")

        logger.info(f"✅ Download complete: {os.path.basename(filename)}")

        response = send_file(filename, as_attachment=True)

        @response.call_on_close
        def cleanup():
            try:
                if os.path.exists(filename):
                    os.remove(filename)
                    logger.info(f"🗑️ Cleaned up: {os.path.basename(filename)}")
            except Exception as e:
                logger.warning(f"⚠️ Cleanup failed: {e}")

        return response

    except Exception as e:
        logger.error(f"❌ Error in /download: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"🚀 Starting server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)