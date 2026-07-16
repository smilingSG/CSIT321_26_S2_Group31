from io import BytesIO

from flask import Blueprint
from flask import redirect
from flask import send_file
from flask import session
from flask import url_for

from entities.ShareLink import ShareLink


download_file_bp = Blueprint("download_file_bp", __name__)


class DownloadFileC:

    @staticmethod
    def downloadSharedFile(share_token: str,
                           user_id: int):

        return ShareLink.downloadSharedFile(
            share_token=share_token,
            user_id=user_id
        )


@download_file_bp.route("/share/<share_token>/download", methods=["GET"])
def downloadSharedFile(share_token: str):

    user_id = session.get("user_id")

    if user_id is None:
        return redirect(url_for("login_bp.login"))

    file_result, error_message = DownloadFileC.downloadSharedFile(
        share_token=share_token,
        user_id=user_id
    )

    if file_result is None:
        return error_message, 404

    return send_file(
        BytesIO(file_result["fileBytes"]),
        as_attachment=True,
        download_name=file_result["fileName"],
        mimetype=file_result["fileType"]
    )
