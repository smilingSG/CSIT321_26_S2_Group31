import os

from flask import Blueprint, jsonify

from entities.File import File

replace_bp = Blueprint("replace_bp", __name__)

TEMP_UPLOAD_FOLDER: str = "temp_uploads"


@replace_bp.route("/upload/replace/<int:file_id>", methods=["POST"])
def replaceTempFile(file_id: int):

    file_record = File.getTempFileById(file_id)

    if file_record is None:
        return jsonify({
            "success": False,
            "message": "Temporary file record not found."
        }), 404

    stored_filename: str = file_record["stored_filename"]

    temp_file_path: str = os.path.join(
        TEMP_UPLOAD_FOLDER,
        stored_filename
    )

    if os.path.exists(temp_file_path):
        os.remove(temp_file_path)

    File.deleteTempFileRecord(file_id)

    return jsonify({
        "success": True,
        "message": "Temporary file removed. Please upload a replacement file."
    })