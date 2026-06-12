from flask import Blueprint
from flask import render_template

from entities.File import File


encrypt_file_bp = Blueprint(
    "encrypt_file_bp",
    __name__
)


@encrypt_file_bp.route(
    "/upload/process/<int:file_id>",
    methods=["GET"]
)
def encryptFile(file_id: int):

    encryption_success = File.encryptFile(file_id)

    if encryption_success is False:
        return "File encryption failed.", 400

    processing_data = File.getProcessingSummary(file_id)

    if processing_data is None:
        return "Processing summary could not be found.", 404

    return render_template(
        "processing.html",
        processingData=processing_data
    )