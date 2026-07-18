from flask import Flask, request, jsonify, send_file
import yt_dlp
import os
import uuid
import shutil
import logging
import traceback
import time
from pathlib import Path
from datetime import timedelta

app = Flask(__name__)

DOWNLOAD_FOLDER = "downloads"
Path(DOWNLOAD_FOLDER).mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============== لیست پروکسی‌های شما ==============
PROXY_LIST = [
    "http://vchzumtc:7xswbwjck90d@31.59.20.176:6754",
    "http://vchzumtc:7xswbwjck90d@31.56.127.193:7684",
    "http://vchzumtc:7xswbwjck90d@45.38.107.97:6014",
    "http://vchzumtc:7xswbwjck90d@198.105.121.200:6462",
    "http://vchzumtc:7xswbwjck90d@64.137.96.74:6641",
    "http://vchzumtc:7xswbwjck90d@198.23.243.226:6361",
    "http://vchzumtc:7xswbwjck90d@38.154.185.97:6370",
    "http://vchzumtc:7xswbwjck90d@84.247.60.125:6095",
    "http://vchzumtc:7xswbwjck90d@142.111.67.146:5611",
    "http://vchzumtc:7xswbwjck90d@191.96.254.138:6185",
]
# ===============================================


@app.before_request
def log_request():
    logger.info(f"📥 {request.method} {request.path}")
    body = request.get_data()
    if body:
        logger.info(f"📦 BODY: {body[:200]}...")


def cleanup_old_files():
    for old_file in os.listdir(DOWNLOAD_FOLDER):
        try:
            os.remove(os.path.join(DOWNLOAD_FOLDER, old_file))
            logger.info(f"🗑️ Removed old file: {old_file}")
        except Exception as e:
            logger.warning(f"Could not remove {old_file}: {e}")


cleanup_old_files()

ORIGINAL_COOKIE_FILE = "/etc/secrets/cookies.txt"
WRITABLE_COOKIE_FILE = "/tmp/cookies.txt"
USE_COOKIE = False


def get_ydl_opts_with_proxy(format_id=None, output=None, audio_only=False, proxy=None):
    """تنظیمات yt-dlp با یک پروکسی مشخص"""
    opts = {
        "quiet": False,
        "verbose": True,
        "no_warnings": False,
        "nocheckcertificate": True,
        "ignoreerrors": True,
        "noprogress": True,
        "no_part": True,
        "no_mtime": True,
        "remote_components": ["ejs:github"],
        "extractor_args": {
            "youtube": {
                "player_client": ["android"],
                "skip": ["hls", "dash"],
                "sleep_interval": 3,
                "extractor_retries": 2,
            }
        },
        "user_agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
        "restrictfilenames": True,
        "trim_file_name": 200,
    }

    if proxy:
        opts["proxy"] = proxy
        logger.info(f"🌐 Trying proxy: {proxy.split('@')[-1] if '@' in proxy else proxy}")

    if USE_COOKIE:
        opts["cookiefile"] = WRITABLE_COOKIE_FILE

    if audio_only:
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
        if output:
            opts["outtmpl"] = output.replace(".%(ext)s", ".mp3")
    else:
        if format_id:
            opts["format"] = format_id
        else:
            opts["skip_download"] = True
        if output:
            opts["outtmpl"] = output

    return opts


def try_download_with_proxies(url, format_id, output, audio_only=False):
    """همه‌ی پروکسی‌ها رو یکی‌یکی امتحان کن تا یکی جواب بده"""
    last_error = None

    for i, proxy in enumerate(PROXY_LIST):
        try:
            logger.info(f"🔄 Trying proxy {i+1}/{len(PROXY_LIST)}...")
            
            opts = get_ydl_opts_with_proxy(format_id, output, audio_only, proxy)
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                if audio_only:
                    ydl.download([url])
                    filename = output.replace(".%(ext)s", ".mp3")
                else:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                
                if os.path.exists(filename):
                    logger.info(f"✅ Success with proxy {i+1}")
                    return filename
                else:
                    raise Exception("File not created")
                    
        except Exception as e:
            error_msg = str(e)
            logger.warning(f"❌ Proxy {i+1} failed: {error_msg[:100]}")
            last_error = e
            continue

    # اگه هیچ پروکسی‌ای جواب نداد
    raise Exception(f"All proxies failed. Last error: {last_error}")


def format_file_size(size_bytes):
    if not size_bytes:
        return None
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def format_duration(seconds):
    if not seconds:
        return "N/A"
    return str(timedelta(seconds=int(seconds)))


@app.route("/")
def home():
    return jsonify({
        "status": "ok",
        "message": "VaziriDownloader Server is running",
        "proxies_count": len(PROXY_LIST),
        "endpoints": {
            "/formats": "POST - Get all available formats",
            "/download": "POST - Download with specific format",
            "/download_audio": "POST - Download as MP3",
            "/download_best": "POST - Download best quality"
        }
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

        # برای گرفتن فرمت‌ها هم پروکسی رو امتحان می‌کنیم
        last_error = None
        for i, proxy in enumerate(PROXY_LIST):
            try:
                logger.info(f"🔄 Trying proxy {i+1} for formats...")
                opts = get_ydl_opts_with_proxy(proxy=proxy)
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    break  # اگه موفق شد، از حلقه خارج شو
            except Exception as e:
                logger.warning(f"❌ Proxy {i+1} failed for formats: {str(e)[:100]}")
                last_error = e
                if i == len(PROXY_LIST) - 1:
                    raise last_error
                continue

        if not info:
            return jsonify({"error": "YouTube اطلاعات ویدیو را برنگرداند."}), 500

        all_formats = info.get("formats", [])

        if not all_formats:
            return jsonify({"error": "هیچ فرمتی برای این ویدیو پیدا نشد"}), 404

        logger.info(f"✅ Found {len(all_formats)} total formats")

        formats_list = []
        for f in all_formats:
            if f.get("url") and not f.get("has_drm", False):
                formats_list.append({
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext", "unknown"),
                    "resolution": f.get("resolution", "unknown"),
                    "filesize": f.get("filesize"),
                    "vcodec": f.get("vcodec", "none"),
                    "acodec": f.get("acodec", "none"),
                    "format_note": f.get("format_note", ""),
                })

        if not formats_list:
            return jsonify({"error": "هیچ فرمت قابل دانلودی پیدا نشد"}), 404

        return jsonify({
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "formats": formats_list
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

        # امتحان کردن همه‌ی پروکسی‌ها
        filename = try_download_with_proxies(url, format_id, output, audio_only=False)

        logger.info(f"✅ Download complete: {os.path.basename(filename)} (size: {os.path.getsize(filename)} bytes)")

        response = send_file(
            filename,
            as_attachment=True,
            download_name=os.path.basename(filename)
        )

        @response.call_on_close
        def cleanup():
            time.sleep(5)
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


@app.route("/download_audio", methods=["POST"])
def download_audio():
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "JSON دریافت نشد"}), 400

        url = data.get("url")
        if not url:
            return jsonify({"error": "لینک ارسال نشده"}), 400

        logger.info(f"🎵 Downloading audio from: {url}")

        filename_id = str(uuid.uuid4())
        output = os.path.join(DOWNLOAD_FOLDER, f"{filename_id}.%(ext)s")

        filename = try_download_with_proxies(url, None, output, audio_only=True)

        if not os.path.exists(filename):
            raise FileNotFoundError(f"MP3 not found: {filename}")

        logger.info(f"✅ Audio download complete: {os.path.basename(filename)}")

        response = send_file(
            filename,
            as_attachment=True,
            download_name=os.path.basename(filename)
        )

        @response.call_on_close
        def cleanup():
            time.sleep(5)
            try:
                if os.path.exists(filename):
                    os.remove(filename)
                    logger.info(f"🗑️ Cleaned up: {os.path.basename(filename)}")
            except Exception as e:
                logger.warning(f"⚠️ Cleanup failed: {e}")

        return response

    except Exception as e:
        logger.error(f"❌ Error in /download_audio: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/download_best", methods=["POST"])
def download_best():
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "JSON دریافت نشد"}), 400

        url = data.get("url")
        if not url:
            return jsonify({"error": "لینک ارسال نشده"}), 400

        logger.info(f"🌟 Downloading best quality from: {url}")

        filename_id = str(uuid.uuid4())
        output = os.path.join(DOWNLOAD_FOLDER, f"{filename_id}.%(ext)s")

        filename = try_download_with_proxies(url, "bestvideo+bestaudio/best", output, audio_only=False)

        logger.info(f"✅ Best quality download complete: {os.path.basename(filename)}")

        response = send_file(
            filename,
            as_attachment=True,
            download_name=os.path.basename(filename)
        )

        @response.call_on_close
        def cleanup():
            time.sleep(5)
            try:
                if os.path.exists(filename):
                    os.remove(filename)
                    logger.info(f"🗑️ Cleaned up: {os.path.basename(filename)}")
            except Exception as e:
                logger.warning(f"⚠️ Cleanup failed: {e}")

        return response

    except Exception as e:
        logger.error(f"❌ Error in /download_best: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"🚀 Starting server on port {port}")
    logger.info(f"📋 Loaded {len(PROXY_LIST)} proxies")
    app.run(host="0.0.0.0", port=port, debug=False)