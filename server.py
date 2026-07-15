from flask import Flask, request, jsonify, send_file
import yt_dlp
import os
import uuid
import shutil
import logging
import traceback

app = Flask(__name__)

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

logging.basicConfig(level=logging.INFO)


@app.before_request
def log_request():
    print("===== NEW REQUEST =====")
    print("METHOD:", request.method)
    print("PATH:", request.path)
    print("BODY:", request.get_data())


# پاک کردن فایل‌های قبلی
for old_file in os.listdir(DOWNLOAD_FOLDER):
    try:
        os.remove(os.path.join(DOWNLOAD_FOLDER, old_file))
    except:
        pass


ORIGINAL_COOKIE_FILE = "/etc/secrets/cookies.txt"
WRITABLE_COOKIE_FILE = "/tmp/cookies.txt"

USE_COOKIE = False

if os.path.exists(ORIGINAL_COOKIE_FILE):
    try:
        shutil.copy(
            ORIGINAL_COOKIE_FILE,
            WRITABLE_COOKIE_FILE
        )
        USE_COOKIE = True
        logging.info("Cookie copied successfully")
    except Exception as e:
        logging.warning(
            "Cookie copy failed: " + str(e)
        )
else:
    logging.warning(
        "Cookie file not found"
    )


def get_ydl_opts(format_id=None, output=None):

    opts = {
        "quiet": False,
        "nocheckcertificate": True,
        "remote_components": [
            "ejs:github"
        ],
    }


    if USE_COOKIE:
        opts["cookiefile"] = WRITABLE_COOKIE_FILE


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
        "message": "VaziriDownloader Server is running"
    })



@app.route("/formats", methods=["POST"])
def get_formats():

    try:

        data = request.get_json(
            silent=True
        )


        if not data:
            return jsonify({
                "error": "JSON دریافت نشد"
            }),400


        url = data.get("url")


        if not url:
            return jsonify({
                "error": "لینک ارسال نشده"
            }),400



        with yt_dlp.YoutubeDL(
            get_ydl_opts()
        ) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )


        formats=[]


        for f in info.get("formats",[]):

            formats.append({

                "format_id": f.get("format_id"),

                "ext": f.get("ext"),

                "resolution": f.get(
                    "resolution",
                    "audio only"
                ),

                "filesize": f.get(
                    "filesize"
                ),

                "vcodec": f.get(
                    "vcodec"
                ),

                "acodec": f.get(
                    "acodec"
                )

            })


        return jsonify({

            "title": info.get("title"),

            "thumbnail": info.get("thumbnail"),

            "duration": info.get("duration"),

            "formats": formats

        })


    except Exception as e:

        traceback.print_exc()

        return jsonify({
            "error":str(e)
        }),500





@app.route("/download", methods=["POST"])
def download_video():

    try:

        data=request.get_json(
            silent=True
        )


        if not data:
            return jsonify({
                "error":"JSON دریافت نشد"
            }),400


        url=data.get("url")

        format_id=data.get(
            "format_id"
        )


        if not url:
            return jsonify({
                "error":"لینک ارسال نشده"
            }),400


        if not format_id:
            format_id="best"



        filename_id=str(
            uuid.uuid4()
        )


        output=os.path.join(
            DOWNLOAD_FOLDER,
            filename_id+"."+"%(ext)s"
        )


        print(
            "DOWNLOAD FORMAT:",
            format_id
        )


        with yt_dlp.YoutubeDL(
            get_ydl_opts(
                format_id,
                output
            )
        ) as ydl:


            info=ydl.extract_info(
                url,
                download=True
            )


            filename=ydl.prepare_filename(
                info
            )



        response=send_file(
            filename,
            as_attachment=True
        )


        @response.call_on_close
        def cleanup():

            try:
                if os.path.exists(filename):
                    os.remove(filename)

            except:
                pass



        return response



    except Exception as e:

        traceback.print_exc()

        return jsonify({
            "error":str(e)
        }),500





if __name__=="__main__":

    port=int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )