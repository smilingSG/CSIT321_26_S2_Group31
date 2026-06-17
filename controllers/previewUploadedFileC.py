from flask import Blueprint, render_template, redirect, session, url_for

from entities.File import File

preview_bp = Blueprint("preview_bp", __name__)


@preview_bp.route("/upload/preview/<int:file_id>", methods=["GET"])
def generatePreview(file_id: int):

    owner_id = session.get("user_id")

    if owner_id is None:
        return redirect(url_for("login_bp.login"))

    preview_data = File.getFilePreviewDetails(
        file_id,
        owner_id
    )

    if preview_data is None:
        return "Preview data could not be found.", 404

    return render_template(
        "preview.html",
        previewData=preview_data
    )
