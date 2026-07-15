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

ORIGINAL_COOKIE_FILE = "/etc/secrets/cookies.txt"
WRITABLE_COOKIE_FILE = "/tmp/cookies.txt"

USE_COOKIE = False
if os.path.exists(ORIGINAL_COOKIE_FILE):
    try:
        shutil.copy(ORIGINAL_COOKIE_FILE, WRITABLE_COOKIE_FILE)
        USE_COOKIE = True
        logging.info("Cookie file copied to writable location.")
    except Exception as e:
        logging.warning("Could not copy cookie file: " + str(e))
else:
    logging.warning("Cookie file not found, proceeding without cookies.")


def get_ydl_opts(format_id=None, output_template=None):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "ignore_no_formats_error": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["web", "android"],
            }
        },
    }
    if USE_COOKIE:
        opts["cookiefile"] = WRITABLE_COOKIE_FILE
    if format_id and output_template:
        opts["format"] = format_id
        opts["outtmpl"] = output_template
    else:
        opts["skip_download"] = True
    return opts


@app.route("/")
def home():
    return jsonify({"status": "ok", "message": "VaziriDownloader Server is running!"})


@app.route("/formats", methods=["POST"])
def get_formats():
    data = request.get_json()
    url = data.get("url")
    if not url:
        return jsonify({"error": "لینک ارسال نشده"}), 400
    try:
        with yt_dlp.YoutubeDL(get_ydl_opts()) as ydl:
            info = ydl.extract_info(url, download=False)

        raw_formats = info.get("formats") or []
        formats_list = []
        for f in raw_formats:
            if f.get("vcodec") != "none" or f.get("acodec") != "none":
                formats_list.append({
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "resolution": f.get("resolution", "audio only"),
                    "filesize": f.get("filesize"),
                })

        if not formats_list:
            return jsonify({"error": "فرمتی برای این ویدیو پیدا نشد"}), 500

        return jsonify({
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "formats": formats_list,
        })
    except Exception as e:
        app.logger.error("Error in /formats: " + str(e))
        return jsonify({"error": str(e)}), 500


@app.route("/download", methods=["POST"])
def download_video():
    data = request.get_json()
    url = data.get("url")
    format_id = data.get("format_id")
    if not url:
        return jsonify({"error": "لینک ارسال نشده"}), 400
    if not format_id:
        format_id = "best"

    unique_id = str(uuid.uuid4())
    output_template = os.path.join(DOWNLOAD_FOLDER, unique_id + ".%(ext)s")

    try:
        with yt_dlp.YoutubeDL(get_ydl_opts(format_id, output_template)) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        response = send_file(filename, as_attachment=True)

        @response.call_on_close
        def cleanup():
            try:
                if os.path.exists(filename):
                    os.remove(filename)
            except Exception:
                pass

        return response

    except Exception as e:
        app.logger.error("Error in /download: " + str(e))
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)