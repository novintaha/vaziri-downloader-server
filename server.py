from flask import Flask, request, jsonify, send_file
import yt_dlp
import os
import uuid

app = Flask(__name__)
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# پاک‌سازی فایل‌های قبلی
for old_file in os.listdir(DOWNLOAD_FOLDER):
    try:
        os.remove(os.path.join(DOWNLOAD_FOLDER, old_file))
    except Exception:
        pass

def get_ydl_opts(format_id=None, output_template=None):
    # تنظیمات کاملاً ساده شده برای جلوگیری از شناسایی به عنوان ربات
    opts = {
        "quiet": True,
        "no_warnings": True,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "nocheckcertificate": True,
        "ignoreerrors": True,
    }
    if format_id and output_template:
        opts["format"] = format_id
        opts["outtmpl"] = output_template
    else:
        opts["skip_download"] = True
    return opts

@app.route("/formats", methods=["POST"])
def get_formats():
    data = request.get_json()
    url = data.get("url")
    if not url: return jsonify({"error": "No URL"}), 400
    try:
        with yt_dlp.YoutubeDL(get_ydl_opts()) as ydl:
            info = ydl.extract_info(url, download=False)
        formats = [{"format_id": f.get("format_id"), "resolution": f.get("resolution")} 
                   for f in info.get("formats", []) if f.get("vcodec") != "none"]
        return jsonify({"title": info.get("title"), "formats": formats})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/download", methods=["POST"])
def download_video():
    data = request.get_json()
    url = data.get("url")
    format_id = data.get("format_id") or "best"
    unique_id = str(uuid.uuid4())
    filename = os.path.join(DOWNLOAD_FOLDER, f"{unique_id}.mp4")

    try:
        with yt_dlp.YoutubeDL(get_ydl_opts(format_id, filename)) as ydl:
            ydl.download([url])
        return send_file(filename, as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))