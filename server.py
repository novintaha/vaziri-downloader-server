from flask import Flask, request, jsonify, send_file
import yt_dlp
import os
import uuid

app = Flask(__name__)
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# پاک کردن فایل‌های قدیمی باقی‌مانده از اجرای قبلی
for old_file in os.listdir(DOWNLOAD_FOLDER):
    try:
        os.remove(os.path.join(DOWNLOAD_FOLDER, old_file))
    except Exception:
        pass


@app.route("/")
def home():
    return jsonify({"status": "ok", "message": "VaziriDownloader Server is running!"})


@app.route("/formats", methods=["POST"])
def get_formats():
    data = request.get_json()
    url = data.get("url")
    if not url:
        return jsonify({"error": "لینک ارسال نشده"}), 400

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "cookiefile": "/etc/secrets/cookies.txt",
        "extractor_args": {"youtube": {"player_client": ["android"]}},
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        formats_list = []
        for f in info.get("formats", []):
            if f.get("vcodec") != "none" or f.get("acodec") != "none":
                formats_list.append({
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "resolution": f.get("resolution", "audio only"),
                    "filesize": f.get("filesize"),
                })

        return jsonify({
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "formats": formats_list,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/download", methods=["POST"])
def download_video():
    data = request.get_json()
    url = data.get("url")
    format_id = data.get("format_id")

    if not url or not format_id:
        return jsonify({"error": "لینک یا فرمت مشخص نشده"}), 400

    unique_id = str(uuid.uuid4())
    output_template = os.path.join(DOWNLOAD_FOLDER, f"{unique_id}.%(ext)s")

    ydl_opts = {
        "quiet": True,
        "format": format_id,
        "outtmpl": output_template,
        "cookiefile": "/etc/secrets/cookies.txt",
        "extractor_args": {"youtube": {"player_client": ["android"]}},
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        response = send_file(filename, as_attachment=True)

        @response.call_on_close
        def cleanup():
            try:
                os.remove(filename)
            except Exception:
                pass

        return response

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)