import os

from flask import Blueprint
from flask import jsonify
from flask import session

from entities.File import File
from entities.Fragment import Fragment


cancel_processing_bp = Blueprint(
    "cancel_processing_bp",
    __name__
)


@cancel_processing_bp.route(
    "/upload/process/cancel/<int:file_id>",
    methods=["POST"]
)
def cancelProcessing(file_id: int):

    owner_id = session.get("user_id")

    if owner_id is None:
        return jsonify({
            "success": False,
            "message": "Please log in before cancelling processing."
        }), 401

    file_record = File.getProcessingFileDetails(
        file_id,
        owner_id
    )

    if file_record is None:
        return jsonify({
            "success": False,
            "message": "Processing file record not found."
        }), 404

    encrypted_temp_path = file_record["encrypted_temp_path"]

    Fragment.deletePendingFragments(file_id)

    if encrypted_temp_path is not None and os.path.exists(encrypted_temp_path):
        os.remove(encrypted_temp_path)

    File.deleteProcessingFileRecord(
        file_id,
        owner_id
    )

    return jsonify({
        "success": True,
        "message": "Processing file removed successfully."
    })
