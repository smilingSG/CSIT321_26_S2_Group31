import os
import uuid
from typing import Optional

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
    total_fragments: Optional[str] = request.form.get("total_fragments")
    required_fragments: Optional[str] = request.form.get("required_fragments")

    if uploaded_file is None or uploaded_file.filename == "":
        return jsonify({"success": False, "message": "Please select a file."}), 400

    if total_fragments is None or required_fragments is None:
        return jsonify({"success": False, "message": "Please enter fragment settings."}), 400

    try:
        total_fragments_int: int = int(total_fragments)
        required_fragments_int: int = int(required_fragments)
    except ValueError:
        return jsonify({"success": False, "message": "Fragment values must be valid numbers."}), 400

    if total_fragments_int < 2:
        return jsonify({"success": False, "message": "Total fragments must be at least 2."}), 400

    if required_fragments_int < 1:
        return jsonify({"success": False, "message": "Required fragments must be at least 1."}), 400

    if required_fragments_int > total_fragments_int:
        return jsonify({"success": False, "message": "Required fragments cannot be greater than total fragments."}), 400

    try:
        original_filename: str = secure_filename(uploaded_file.filename)
        file_extension: str = os.path.splitext(original_filename)[1]
        stored_filename: str = str(uuid.uuid4()) + file_extension
        temp_file_path: str = os.path.join(TEMP_UPLOAD_FOLDER, stored_filename)

        uploaded_file.save(temp_file_path)

        file_size: int = os.path.getsize(temp_file_path)
        file_type: str = uploaded_file.content_type or "Unknown"

        file_id: int = File.createTempFileRecord(
            owner_id=TEMP_USER_ID,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_size=file_size,
            file_type=file_type,
            total_fragments=total_fragments_int,
            required_fragments=required_fragments_int
        )

        return jsonify({
            "success": True,
            "message": "File uploaded to temporary storage. File is ready for confirmation.",
            "file_id": file_id,
            "stored_filename": stored_filename
        })

    except Exception as error:
        return jsonify({"success": False, "message": "Upload error: " + str(error)}), 500


@upload_bp.route("/upload/cancel/<int:file_id>", methods=["POST"])
def cancelUpload(file_id: int):
    file_record = File.getTempFileById(file_id)

    if file_record is None:
        return jsonify({"success": False, "message": "Temporary file record not found."}), 404

    stored_filename: str = file_record["stored_filename"]
    temp_file_path: str = os.path.join(TEMP_UPLOAD_FOLDER, stored_filename)

    if os.path.exists(temp_file_path):
        os.remove(temp_file_path)

    File.deleteTempFileRecord(file_id)

    return jsonify({
        "success": True,
        "message": "Temporary upload has been cancelled and removed."
    })