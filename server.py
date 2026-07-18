from flask import Flask, request, jsonify, send_file
import yt_dlp
import os
import uuid
import shutil
import logging
import traceback
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

# پروکسی Webshare (اگه کار نکرد، عوضش کن)
WEBSHARE_PROXY = "http://vchzumtc:7xswbwjck90d@31.59.20.176:6754"


def get_ydl_opts(format_id=None, output=None, audio_only=False):
    opts = {
        "quiet": False,
        "verbose": True,
        "no_warnings": False,
        "nocheckcertificate": True,
        "ignoreerrors": True,
        "proxy": WEBSHARE_PROXY,
        "remote_components": ["ejs:github"],
        "extractor_args": {
            "youtube": {
                "player_client": ["tv", "web"],  # TV کلاینت کمتر SABR رو اعمال می‌کنه
                "skip": ["hls", "dash"],
                "disable_sabr": True,  # غیرفعال کردن SABR
                "sleep_interval": 5,   # تاخیر بین درخواست‌ها
                "extractor_retries": 5, # تعداد تلاش مجدد
            }
        },
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "restrictfilenames": True,
        "trim_file_name": 200,
    }

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
        "proxy": "✅ Active (Webshare)",
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

        with yt_dlp.YoutubeDL(get_ydl_opts()) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            logger.error("❌ YouTube returned no info.")
            return jsonify({
                "error": "YouTube اطلاعات ویدیو را برنگرداند."
            }), 500

        all_formats = info.get("formats", [])

        if not all_formats:
            return jsonify({"error": "هیچ فرمتی برای این ویدیو پیدا نشد"}), 404

        logger.info(f"✅ Found {len(all_formats)} total formats")

        # همه‌ی فرمت‌ها رو بدون فیلتر برمی‌گردونیم
        formats_list = []
        for f in all_formats:
            formats_list.append({
                "format_id": f.get("format_id"),
                "ext": f.get("ext", "unknown"),
                "resolution": f.get("resolution", "unknown"),
                "filesize": f.get("filesize"),
                "vcodec": f.get("vcodec", "none"),
                "acodec": f.get("acodec", "none"),
                "format_note": f.get("format_note", ""),
            })

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

        filename_id = str(uuid.uuid4())
        output = os.path.join(DOWNLOAD_FOLDER, f"{filename_id}.%(ext)s")

        with yt_dlp.YoutubeDL(get_ydl_opts(format_id, output)) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        if not os.path.exists(filename):
            raise FileNotFoundError(f"File not found: {filename}")

        response = send_file(filename, as_attachment=True)

        @response.call_on_close
        def cleanup():
            try:
                if os.path.exists(filename):
                    os.remove(filename)
            except:
                pass

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

        filename_id = str(uuid.uuid4())
        output = os.path.join(DOWNLOAD_FOLDER, f"{filename_id}.%(ext)s")

        opts = get_ydl_opts(audio_only=True, output=output)

        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

        filename = os.path.join(DOWNLOAD_FOLDER, f"{filename_id}.mp3")

        if not os.path.exists(filename):
            raise FileNotFoundError(f"MP3 not found: {filename}")

        response = send_file(filename, as_attachment=True)

        @response.call_on_close
        def cleanup():
            try:
                if os.path.exists(filename):
                    os.remove(filename)
            except:
                pass

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

        filename_id = str(uuid.uuid4())
        output = os.path.join(DOWNLOAD_FOLDER, f"{filename_id}.%(ext)s")

        with yt_dlp.YoutubeDL(get_ydl_opts("bestvideo+bestaudio/best", output)) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        if not os.path.exists(filename):
            raise FileNotFoundError(f"File not found: {filename}")

        response = send_file(filename, as_attachment=True)

        @response.call_on_close
        def cleanup():
            try:
                if os.path.exists(filename):
                    os.remove(filename)
            except:
                pass

        return response

    except Exception as e:
        logger.error(f"❌ Error in /download_best: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"🚀 Starting server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)