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


def get_ydl_opts(format_id=None, output=None, download_type=None):
    """
    تنظیمات بهینه yt-dlp برای دورزدن محدودیت‌های یوتیوب
    """
    opts = {
        "quiet": False,
        "no_warnings": False,
        "nocheckcertificate": True,
        "ignoreerrors": True,
        "remote_components": ["ejs:github"],
        "extractor_args": {
            "youtube": {
                "player_client": ["web"],
                "skip": ["hls", "dash"]
            }
        },
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "restrictfilenames": True,  # اسم فایل رو ایمن کن
        "trim_file_name": 200,  # محدودیت اسم فایل
    }

    if USE_COOKIE:
        opts["cookiefile"] = WRITABLE_COOKIE_FILE
        logger.info("🍪 Using cookies for authentication")

    # تنظیمات خاص برای دانلود صدا
    if download_type == "audio":
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
        opts["outtmpl"] = output.replace(".%(ext)s", ".mp3") if output else None
    else:
        if format_id:
            opts["format"] = format_id
        else:
            opts["skip_download"] = True

    if output and download_type != "audio":
        opts["outtmpl"] = output

    return opts


def format_file_size(size_bytes):
    """تبدیل اندازه فایل به واحد قابل‌خواندن"""
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
    """تبدیل ثانیه به زمان قابل‌خواندن"""
    if not seconds:
        return "N/A"
    return str(timedelta(seconds=int(seconds)))


def categorize_formats(formats):
    """دسته‌بندی فرمت‌ها به ویدیو، صدا، ویدیو+صدا و فرمت‌های ویژه"""
    result = {
        "video": [],
        "audio": [],
        "video_audio": [],
        "all": []
    }

    for f in formats:
        format_id = f.get("format_id")
        ext = f.get("ext", "unknown")
        resolution = f.get("resolution", "unknown")
        filesize = f.get("filesize")
        vcodec = f.get("vcodec", "none")
        acodec = f.get("acodec", "none")
        fps = f.get("fps")
        tbr = f.get("tbr")
        vbr = f.get("vbr")
        abr = f.get("abr")
        format_note = f.get("format_note", "")
        quality = f.get("quality", 0)

        format_info = {
            "format_id": format_id,
            "ext": ext,
            "resolution": resolution,
            "filesize": filesize,
            "filesize_human": format_file_size(filesize),
            "vcodec": vcodec,
            "acodec": acodec,
            "fps": fps,
            "tbr": tbr,
            "vbr": vbr,
            "abr": abr,
            "format_note": format_note,
            "quality": quality,
            "has_video": vcodec != "none",
            "has_audio": acodec != "none"
        }

        result["all"].append(format_info)

        # دسته‌بندی
        has_video = vcodec != "none"
        has_audio = acodec != "none"

        if has_video and has_audio:
            result["video_audio"].append(format_info)
        elif has_video and not has_audio:
            result["video"].append(format_info)
        elif not has_video and has_audio:
            result["audio"].append(format_info)

    return result


@app.route("/")
def home():
    return jsonify({
        "status": "ok",
        "message": "VaziriDownloader Server is running",
        "cookies": "✅ Active" if USE_COOKIE else "❌ Not found",
        "endpoints": {
            "/formats": "POST - Get all available formats for a video",
            "/download": "POST - Download video/audio with specific format",
            "/download_audio": "POST - Download audio as MP3",
            "/download_best": "POST - Download best quality video+audio"
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

        all_formats = info.get("formats", [])
        categorized = categorize_formats(all_formats)

        video_info = {
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "duration_human": format_duration(info.get("duration")),
            "uploader": info.get("uploader"),
            "uploader_id": info.get("uploader_id"),
            "description": info.get("description", "")[:300] + "..." if info.get("description") and len(info.get("description", "")) > 300 else info.get("description", ""),
            "view_count": info.get("view_count"),
            "like_count": info.get("like_count"),
            "categories": info.get("categories", []),
            "tags": info.get("tags", [])[:15],
            "webpage_url": info.get("webpage_url"),
            "extractor": info.get("extractor")
        }

        summary = {
            "total_formats": len(all_formats),
            "video_only": len(categorized["video"]),
            "audio_only": len(categorized["audio"]),
            "video_audio": len(categorized["video_audio"]),
            "best_video_quality": categorized["video"][0].get("resolution") if categorized["video"] else None,
            "best_audio_quality": f"{categorized['audio'][0].get('abr', 0)} kbps" if categorized["audio"] else None,
            "best_combined_quality": categorized["video_audio"][0].get("resolution") if categorized["video_audio"] else None
        }

        logger.info(f"✅ Found {summary['total_formats']} formats for: {video_info['title']}")

        return jsonify({
            "video_info": video_info,
            "summary": summary,
            "formats": categorized,
            "recommended": {
                "best_video": categorized["video"][0] if categorized["video"] else None,
                "best_audio": categorized["audio"][0] if categorized["audio"] else None,
                "best_combined": categorized["video_audio"][0] if categorized["video_audio"] else None
            },
            "download_options": {
                "audio_mp3": "/download_audio",
                "best_quality": "/download_best",
                "custom_format": "/download"
            }
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


@app.route("/download_audio", methods=["POST"])
def download_audio():
    """دانلود صدا به صورت MP3"""
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "JSON دریافت نشد"}), 400

        url = data.get("url")
        quality = data.get("quality", "192")  # کیفیت پیش‌فرض 192 kbps

        if not url:
            return jsonify({"error": "لینک ارسال نشده"}), 400

        logger.info(f"🎵 Downloading audio from: {url} (quality: {quality} kbps)")

        filename_id = str(uuid.uuid4())
        output = os.path.join(DOWNLOAD_FOLDER, f"{filename_id}.%(ext)s")

        opts = get_ydl_opts(download_type="audio")
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": quality,
        }]
        opts["outtmpl"] = os.path.join(DOWNLOAD_FOLDER, filename_id)

        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

        filename = os.path.join(DOWNLOAD_FOLDER, f"{filename_id}.mp3")

        if not os.path.exists(filename):
            raise FileNotFoundError(f"MP3 file not found after download: {filename}")

        logger.info(f"✅ Audio download complete: {os.path.basename(filename)}")

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
        logger.error(f"❌ Error in /download_audio: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/download_best", methods=["POST"])
def download_best():
    """دانلود بهترین کیفیت ممکن (ویدیو + صدا)"""
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

        with yt_dlp.YoutubeDL(get_ydl_opts("bestvideo+bestaudio/best", output)) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        if not os.path.exists(filename):
            raise FileNotFoundError(f"File not found after download: {filename}")

        logger.info(f"✅ Best quality download complete: {os.path.basename(filename)}")

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
        logger.error(f"❌ Error in /download_best: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"🚀 Starting server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)