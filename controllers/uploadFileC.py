import os
import uuid

from flask import Blueprint, render_template, request, jsonify
from werkzeug.utils import secure_filename

from entities.File import File

upload_bp = Blueprint("upload_bp", __name__)

TEMP_UPLOAD_FOLDER: str = "temp_uploads"
TEMP_USER_ID: int = 1

os.makedirs(TEMP_UPLOAD_FOLDER, exist_ok=True)


@upload_bp.route("/upload", methods=["GET"])
def uploadPage():
    return render_template("upload.html")


@upload_bp.route("/upload/temp", methods=["POST"])
def uploadTempFile():

    uploaded_file = request.files.get("file")

    if uploaded_file is None or uploaded_file.filename == "":
        return jsonify({
            "success": False,
            "message": "Please select a file."
        }), 400

    try:
        original_filename: str = secure_filename(uploaded_file.filename)

        file_extension: str = os.path.splitext(original_filename)[1]

        stored_filename: str = str(uuid.uuid4()) + file_extension

        temp_file_path: str = os.path.join(
            TEMP_UPLOAD_FOLDER,
            stored_filename
        )

        uploaded_file.save(temp_file_path)

        file_size: int = os.path.getsize(temp_file_path)

        file_type: str = uploaded_file.content_type or "Unknown"

        file_id: int = File.createTempFileRecord(
            owner_id=TEMP_USER_ID,
            file_name=original_filename,
            stored_filename=stored_filename,
            file_size=file_size,
            file_type=file_type,
            temp_upload_path=temp_file_path
        )

        return jsonify({
            "success": True,
            "message": "Upload completed successfully.",
            "file_id": file_id
        })

    except Exception as error:

        return jsonify({
            "success": False,
            "message": "Upload error: " + str(error)
        }), 500


@upload_bp.route("/upload/cancel/<int:file_id>", methods=["POST"])
def cancelUpload(file_id: int):

    file_record = File.getTempFileById(file_id)

    if file_record is None:
        return jsonify({
            "success": False,
            "message": "Temporary file record not found."
        }), 404

    temp_file_path: str = file_record["temp_upload_path"]

    if os.path.exists(temp_file_path):
        os.remove(temp_file_path)

    File.deleteTempFileRecord(file_id)

    return jsonify({
        "success": True,
        "message": "Temporary upload removed successfully."
    })