from flask import Blueprint, render_template

from entities.File import File

preview_bp = Blueprint("preview_bp", __name__)


@preview_bp.route("/upload/preview/<int:file_id>", methods=["GET"])
def generatePreview(file_id: int):

    preview_data = File.getFilePreviewDetails(file_id)

    if preview_data is None:
        return "Preview data could not be found.", 404

    return render_template(
        "preview.html",
        previewData=preview_data
    )