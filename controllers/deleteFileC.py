import os

from flask import Blueprint
from flask import jsonify

from entities.File import File

delete_bp = Blueprint(
    "delete_bp",
    __name__
)

TEMP_UPLOAD_FOLDER = "temp_uploads"


@delete_bp.route(
    "/upload/delete/<int:file_id>",
    methods=["POST"]
)
def deleteFile(file_id: int):

    file_record = File.getTempFileById(
        file_id
    )

    if file_record is None:
        return jsonify({
            "success": False,
            "message": "File not found."
        }), 404

    temp_file_path = file_record["temp_upload_path"]

    if os.path.exists(temp_file_path):
        os.remove(temp_file_path)

    File.removeFile(file_id)

    return jsonify({
        "success": True,
        "message": "File deleted."
    })